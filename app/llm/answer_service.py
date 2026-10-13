import hashlib
import uuid

from app.retrieval.retrieval_service import RetrievalService
from app.retrieval.context_assembler import ContextAssembler

from app.llm.prompt_builder import build_answer_prompt
from app.llm.client import LLMClient
from app.llm.citation_validator import validate_citations

from app.security.safety_guard import (
    SafetyGuard,
    BLOCKED_QUERY_MESSAGE,
    UNVERIFIED_ANSWER_MESSAGE,
)

from app.security.audit_logger import AuditLogger


ABSTAIN_MESSAGE = (
    "I could not find enough information "
    "to answer this question."
)


class AnswerService:

    def __init__(
        self,
        retrieval_service=None,
        context_assembler=None,
        llm_client=None,
        safety_guard=None,
        audit_logger=None,
    ):

        self.retrieval_service = (
            retrieval_service
            or RetrievalService()
        )

        self.context_assembler = (
            context_assembler
            or ContextAssembler()
        )

        self.llm_client = llm_client

        self.safety_guard = (
            safety_guard
            or SafetyGuard()
        )

        self.audit_logger = (
            audit_logger
            or AuditLogger()
        )


    def _get_llm_client(self):

        if self.llm_client is None:
            self.llm_client = LLMClient()

        return self.llm_client


    def answer(
        self,
        user_id,
        query,
        top_k=5,
    ):

        # ==================================================
        # 0. Create Query ID
        # ==================================================

        query_id = str(
            uuid.uuid4()
        )


        # ==================================================
        # 1. Query Received
        # ==================================================

        self.audit_logger.log_event(
            event_type="query_received",
            user_id=user_id,
            query_id=query_id,
            action="query",
            details={
                "query": query
            },
        )


        # ==================================================
        # 2. Input Safety Guard
        # ==================================================

        query_decision = (
            self.safety_guard
            .check_query(query)
        )


        self.audit_logger.log_event(
            event_type="input_safety",
            user_id=user_id,
            query_id=query_id,
            action="check_query",
            auth_decision=(
                "allowed"
                if query_decision["allowed"]
                else "blocked"
            ),
            details={
                "reason":
                    query_decision["reason"]
            },
        )


        # --------------------------------------------------
        # Input attack blocked
        # --------------------------------------------------

        if not query_decision["allowed"]:

            self.audit_logger.log_event(
                event_type="final_response",
                user_id=user_id,
                query_id=query_id,
                action="blocked",
                details={
                    "llm_called": False,
                    "safety_stage": "input",
                    "reason":
                        query_decision["reason"],
                },
            )

            return {
                "user_id":
                    user_id,

                "query_id":
                    query_id,

                "query":
                    query,

                "answer":
                    BLOCKED_QUERY_MESSAGE,

                "citations":
                    [],

                "source_count":
                    0,

                "llm_called":
                    False,

                "abstained":
                    True,

                "safety_blocked":
                    True,

                "safety_reason":
                    query_decision["reason"],

                "blocked_resources":
                    [],

                "citation_validation":
                    None,
            }


        # ==================================================
        # 3. Permission-Aware Retrieval
        # ==================================================

        retrieval_response = (
            self.retrieval_service
            .search(
                user_id=user_id,
                query=query,
                top_k=top_k,
                method="hybrid",
            )
        )


        retrieved_ids = [
            item["resource"]["resource_id"]
            for item
            in retrieval_response["results"]
        ]


        self.audit_logger.log_event(
            event_type="authorization_retrieval",
            user_id=user_id,
            query_id=query_id,
            action="permission_aware_retrieval",
            details={
                "total_resources":
                    retrieval_response[
                        "total_resources"
                    ],

                "authorized_resources":
                    retrieval_response[
                        "authorized_resources"
                    ],

                "denied_resources":
                    (
                        retrieval_response[
                            "total_resources"
                        ]
                        -
                        retrieval_response[
                            "authorized_resources"
                        ]
                    ),

                "retrieved_resource_ids":
                    retrieved_ids,

                "retrieval_method":
                    "hybrid_v5_2",
            },
        )


        # ==================================================
        # 4. Retrieved Content Safety Guard
        # ==================================================

        content_filter = (
            self.safety_guard
            .filter_retrieval_results(
                retrieval_response[
                    "results"
                ]
            )
        )


        self.audit_logger.log_event(
            event_type="retrieved_content_safety",
            user_id=user_id,
            query_id=query_id,
            action="filter_retrieved_content",
            details={
                "blocked_count":
                    content_filter[
                        "blocked_count"
                    ],

                "blocked_resources":
                    content_filter[
                        "blocked_resources"
                    ],
            },
        )


        safe_results = (
            content_filter[
                "safe_results"
            ]
        )


        # ==================================================
        # 5. Context Assembly
        # ==================================================

        context_package = (
            self.context_assembler
            .build(
                safe_results
            )
        )


        self.audit_logger.log_event(
            event_type="context_assembled",
            user_id=user_id,
            query_id=query_id,
            action="build_context",
            details={
                "source_count":
                    context_package[
                        "source_count"
                    ],

                "context_chars":
                    context_package[
                        "context_chars"
                    ],

                "citation_ids": [
                    citation[
                        "citation_id"
                    ]
                    for citation
                    in context_package[
                        "citations"
                    ]
                ],
            },
        )


        # ==================================================
        # 6. Fail Closed if Context is Empty
        # ==================================================

        if (
            context_package[
                "source_count"
            ]
            == 0
        ):

            self.audit_logger.log_event(
                event_type="final_response",
                user_id=user_id,
                query_id=query_id,
                action="abstain",
                details={
                    "llm_called":
                        False,

                    "reason":
                        "no_authorized_relevant_context",
                },
            )

            return {
                "user_id":
                    user_id,

                "query_id":
                    query_id,

                "query":
                    query,

                "answer":
                    ABSTAIN_MESSAGE,

                "citations":
                    [],

                "source_count":
                    0,

                "llm_called":
                    False,

                "abstained":
                    True,

                "safety_blocked":
                    False,

                "safety_reason":
                    None,

                "blocked_resources":
                    content_filter[
                        "blocked_resources"
                    ],

                "citation_validation":
                    None,
            }


        # ==================================================
        # 7. Safe Prompt Builder
        # ==================================================

        prompt = build_answer_prompt(
            query=query,
            context=context_package[
                "context"
            ],
        )


        # ==================================================
        # 8. LLM Generation
        # ==================================================

        client = (
            self._get_llm_client()
        )


        generated_answer = (
            client.generate(
                system_prompt=prompt[
                    "system_prompt"
                ],
                user_prompt=prompt[
                    "user_prompt"
                ],
            )
        )

        # The model is explicitly instructed to return the standard abstention
        # message when the retrieved context is not sufficient.  That is a safe
        # terminal result, not an uncited factual answer.
        llm_abstained = (
            generated_answer.strip()
            ==
            ABSTAIN_MESSAGE
        )


        self.audit_logger.log_event(
            event_type="llm_generation",
            user_id=user_id,
            query_id=query_id,
            action="generate_answer",
            details={
                "llm_called":
                    True,

                "model":
                    client.model,
            },
        )


        # ==================================================
        # 9. Citation Validation
        # ==================================================

        if llm_abstained:

            citation_validation = {
                "valid": True,
                "available_ids": sorted(
                    citation.get("citation_id")
                    for citation in context_package["citations"]
                    if citation.get("citation_id")
                ),
                "used_ids": [],
                "invalid_ids": [],
                "missing_citations": False,
                "citation_required": False,
                "reason": "standard_abstention",
            }

        else:

            citation_validation = (
                validate_citations(
                    generated_answer,
                    context_package[
                        "citations"
                    ],
                )
            )


        self.audit_logger.log_event(
            event_type="citation_validation",
            user_id=user_id,
            query_id=query_id,
            action="validate_citations",
            details={
                "valid":
                    citation_validation[
                        "valid"
                    ],

                "used_ids":
                    citation_validation[
                        "used_ids"
                    ],

                "invalid_ids":
                    citation_validation[
                        "invalid_ids"
                    ],
            },
        )


        # ==================================================
        # 10. Output Safety Guard
        # ==================================================

        output_decision = (
            self.safety_guard
            .check_output(
                answer=generated_answer,
                citation_validation=
                    citation_validation,
            )
        )


        # IMPORTANT:
        # Log output safety BEFORE possible return.
        self.audit_logger.log_event(
            event_type="output_safety",
            user_id=user_id,
            query_id=query_id,
            action="check_output",
            auth_decision=(
                "allowed"
                if output_decision["allowed"]
                else "blocked"
            ),
            details={
                "reason":
                    output_decision[
                        "reason"
                    ]
            },
        )


        # --------------------------------------------------
        # Unsafe / unverified output
        # --------------------------------------------------

        if not output_decision["allowed"]:

            blocked_answer_hash = (
                hashlib.sha256(
                    generated_answer.encode(
                        "utf-8"
                    )
                ).hexdigest()
            )


            self.audit_logger.log_event(
                event_type="final_response",
                user_id=user_id,
                query_id=query_id,
                action="blocked",
                details={
                    "llm_called":
                        True,

                    "safety_stage":
                        "output",

                    "reason":
                        output_decision[
                            "reason"
                        ],

                    "answer_sha256":
                        blocked_answer_hash,
                },
            )


            return {
                "user_id":
                    user_id,

                "query_id":
                    query_id,

                "query":
                    query,

                "answer":
                    UNVERIFIED_ANSWER_MESSAGE,

                "citations":
                    [],

                "source_count":
                    context_package[
                        "source_count"
                    ],

                "llm_called":
                    True,

                "abstained":
                    True,

                "safety_blocked":
                    True,

                "safety_reason":
                    output_decision[
                        "reason"
                    ],

                "blocked_resources":
                    content_filter[
                        "blocked_resources"
                    ],

                "citation_validation":
                    citation_validation,
            }


        # --------------------------------------------------
        # Safe LLM abstention after irrelevant context
        # --------------------------------------------------

        if llm_abstained:

            self.audit_logger.log_event(
                event_type="final_response",
                user_id=user_id,
                query_id=query_id,
                action="abstain",
                details={
                    "llm_called": True,
                    "abstained": True,
                    "reason":
                        "insufficient_context_after_generation",
                    "source_count": 0,
                },
            )

            return {
                "user_id": user_id,
                "query_id": query_id,
                "query": query,
                "answer": ABSTAIN_MESSAGE,
                "citations": [],
                "source_count": 0,
                "llm_called": True,
                "abstained": True,
                "safety_blocked": False,
                "safety_reason": None,
                "blocked_resources":
                    content_filter["blocked_resources"],
                "citation_validation":
                    citation_validation,
            }


        # ==================================================
        # 11. Final Safe Answer
        # ==================================================

        answer_hash = (
            hashlib.sha256(
                generated_answer.encode(
                    "utf-8"
                )
            ).hexdigest()
        )


        self.audit_logger.log_event(
            event_type="final_response",
            user_id=user_id,
            query_id=query_id,
            action="answer",
            details={
                "llm_called":
                    True,

                "abstained":
                    False,

                "source_count":
                    context_package[
                        "source_count"
                    ],

                "answer_sha256":
                    answer_hash,

                "citation_ids":
                    citation_validation[
                        "used_ids"
                    ],
            },
        )


        return {
            "user_id":
                user_id,

            "query_id":
                query_id,

            "query":
                query,

            "answer":
                generated_answer,

            "citations":
                context_package[
                    "citations"
                ],

            "source_count":
                context_package[
                    "source_count"
                ],

            "llm_called":
                True,

            "abstained":
                False,

            "safety_blocked":
                False,

            "safety_reason":
                None,

            "blocked_resources":
                content_filter[
                    "blocked_resources"
                ],

            "citation_validation":
                citation_validation,
        }
