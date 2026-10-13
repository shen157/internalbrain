import re

from app.retrieval.bm25_retriever import (
    BM25Retriever
)

from app.retrieval.semantic_retriever import (
    SemanticRetriever
)

from app.retrieval.text_utils import (
    tokenize,
    build_search_text
)


# =========================================================
# Generic concept normalization
# =========================================================

TOKEN_NORMALIZATION = {

    # blocker / blocking
    "blocker": "block",
    "blockers": "block",
    "blocks": "block",
    "blocked": "block",
    "blocking": "block",

    # delay
    "delays": "delay",
    "delayed": "delay",
    "delaying": "delay",

    # risks
    "risks": "risk",

    # issues
    "issues": "issue",

    # problems
    "problems": "problem",

    # causes
    "causes": "cause",
    "caused": "cause",
    "causing": "cause",

    # failures
    "failures": "failure",
    "failed": "failure",
    "failing": "failure",

    # timeouts
    "timeouts": "timeout",
}


ISSUE_INTENT_TOKENS = {
    "block",
    "delay",
    "risk",
    "issue",
    "problem",
    "cause",
    "failure"
}


ISSUE_EVIDENCE_TOKENS = {
    "block",
    "delay",
    "risk",
    "issue",
    "problem",
    "cause",
    "failure",
    "timeout",
    "latency",
    "incompatibility",
    "incident",
    "error",
}


QUERY_EXPANSION_GROUPS = {

    "block": [
        "block",
        "blocker",
        "blockers",
        "blocks",
        "blocked",
        "blocking",
        "risk",
        "issue",
        "problem"
    ],

    "delay": [
        "delay",
        "delays",
        "delayed",
        "delaying",
        "block",
        "blocking"
    ],

    "cause": [
        "cause",
        "caused",
        "causes",
        "reason",
        "root"
    ],

    "risk": [
        "risk",
        "risks",
        "blocker",
        "issue"
    ],

    "issue": [
        "issue",
        "issues",
        "problem",
        "blocker"
    ]
}


class HybridRetriever:

    def __init__(
        self,
        resources,
        rrf_k=60,
        bm25_weight=0.65,
        semantic_weight=0.35,
        semantic_strong_threshold=0.50,
        lexical_coverage_threshold=0.30
    ):

        self.resources = resources

        self.rrf_k = rrf_k

        self.bm25_weight = (
            bm25_weight
        )

        self.semantic_weight = (
            semantic_weight
        )

        self.semantic_strong_threshold = (
            semantic_strong_threshold
        )

        self.lexical_coverage_threshold = (
            lexical_coverage_threshold
        )

        self.bm25 = BM25Retriever(
            resources
        )

        self.semantic = SemanticRetriever(
            resources
        )


    # =====================================================
    # Token Helpers
    # =====================================================

    def _normalize_token(
        self,
        token
    ):

        return TOKEN_NORMALIZATION.get(
            token,
            token
        )


    def _concept_tokens(
        self,
        text
    ):

        result = []


        for token in tokenize(
            text
        ):

            # Preserve token
            result.append(
                self._normalize_token(
                    token
                )
            )


            # payment-migration
            # -> payment + migration
            if "-" in token:

                for part in token.split(
                    "-"
                ):

                    if part:

                        result.append(
                            self._normalize_token(
                                part
                            )
                        )


        return result


    # =====================================================
    # Query Expansion
    # =====================================================

    def _expand_bm25_query(
        self,
        query
    ):

        query_tokens = set(
            self._concept_tokens(
                query
            )
        )


        expanded_terms = []


        for concept, terms in (
            QUERY_EXPANSION_GROUPS.items()
        ):

            if concept in query_tokens:

                expanded_terms.extend(
                    terms
                )


        if not expanded_terms:

            return query


        return (
            query
            + " "
            + " ".join(
                expanded_terms
            )
        )


    # =====================================================
    # Lexical Evidence
    # =====================================================

    def _get_lexical_evidence(
        self,
        query,
        resource
    ):

        query_tokens = set(
            self._concept_tokens(
                query
            )
        )


        if not query_tokens:

            return {
                "match_count":
                    0,

                "coverage":
                    0.0,

                "required_matches":
                    0,

                "matched_tokens":
                    []
            }


        resource_tokens = set(
            self._concept_tokens(
                build_search_text(
                    resource
                )
            )
        )


        matched_tokens = (
            query_tokens
            &
            resource_tokens
        )


        match_count = len(
            matched_tokens
        )


        coverage = (
            match_count
            /
            len(
                query_tokens
            )
        )


        if len(
            query_tokens
        ) <= 2:

            required_matches = 1

        else:

            required_matches = 2


        return {

            "match_count":
                match_count,

            "coverage":
                coverage,

            "required_matches":
                required_matches,

            "matched_tokens":
                sorted(
                    matched_tokens
                )
        }


    # =====================================================
    # Query Intent
    # =====================================================

    def _has_issue_intent(
        self,
        query
    ):

        query_tokens = set(
            self._concept_tokens(
                query
            )
        )


        return bool(
            query_tokens
            &
            ISSUE_INTENT_TOKENS
        )


    # =====================================================
    # Issue Evidence
    # =====================================================

    def _get_issue_evidence_score(
        self,
        resource
    ):

        text = (
            build_search_text(
                resource
            )
            or ""
        )


        lowercase_text = (
            text.lower()
        )


        resource_tokens = set(
            self._concept_tokens(
                text
            )
        )


        evidence_tokens = (
            resource_tokens
            &
            ISSUE_EVIDENCE_TOKENS
        )


        # =============================================
        # Negated evidence
        #
        # Examples:
        # "No blockers currently"
        # "No known issues"
        # =============================================

        negated_concepts = set()


        if re.search(
            r"\bno\s+(?:known\s+)?blockers?\b",
            lowercase_text
        ):

            negated_concepts.add(
                "block"
            )


        if re.search(
            r"\bno\s+(?:known\s+)?issues?\b",
            lowercase_text
        ):

            negated_concepts.add(
                "issue"
            )


        if re.search(
            r"\bno\s+(?:known\s+)?risks?\b",
            lowercase_text
        ):

            negated_concepts.add(
                "risk"
            )


        evidence_tokens = (
            evidence_tokens
            -
            negated_concepts
        )


        return len(
            evidence_tokens
        )


    # =====================================================
    # Build Result
    # =====================================================

    def _build_result(
        self,
        key,
        ranking_score,
        fused_score,
        resource_map,
        bm25_raw_scores,
        semantic_raw_scores,
        lexical_evidence_map,
        issue_evidence_map
    ):

        lexical_info = (
            lexical_evidence_map[
                key
            ]
        )


        return {

            "resource":
                resource_map[
                    key
                ],

            # Final ranking score
            "score":
                float(
                    ranking_score
                ),

            # Original Weighted RRF score
            "rrf_score":
                float(
                    fused_score
                ),

            "bm25_score":
                float(
                    bm25_raw_scores.get(
                        key,
                        0
                    )
                ),

            "semantic_score":
                float(
                    semantic_raw_scores.get(
                        key,
                        0
                    )
                ),

            "lexical_match_count":
                lexical_info[
                    "match_count"
                ],

            "lexical_coverage":
                float(
                    lexical_info[
                        "coverage"
                    ]
                ),

            "matched_query_tokens":
                lexical_info[
                    "matched_tokens"
                ],

            "issue_evidence_score":
                issue_evidence_map.get(
                    key,
                    0
                )
        }


    # =====================================================
    # Search
    # =====================================================

    def search(
        self,
        query,
        top_k=5,
        candidate_k=20
    ):

        # =============================================
        # BM25 gets a lightweight expanded query.
        #
        # Semantic retrieval keeps the original query.
        # =============================================

        bm25_query = (
            self._expand_bm25_query(
                query
            )
        )


        bm25_results = (
            self.bm25.search(
                bm25_query,
                top_k=candidate_k
            )
        )


        semantic_results = (
            self.semantic.search(
                query,
                top_k=candidate_k
            )
        )


        fused_scores = {}

        resource_map = {}

        bm25_raw_scores = {}

        semantic_raw_scores = {}


        # =================================================
        # BM25
        # =================================================

        for rank, item in enumerate(
            bm25_results,
            start=1
        ):

            resource = (
                item[
                    "resource"
                ]
            )


            key = (
                resource[
                    "source"
                ],
                resource[
                    "resource_id"
                ]
            )


            resource_map[
                key
            ] = resource


            bm25_raw_scores[
                key
            ] = (
                item[
                    "score"
                ]
            )


            fused_scores[
                key
            ] = (
                fused_scores.get(
                    key,
                    0
                )
                +
                self.bm25_weight
                /
                (
                    self.rrf_k
                    +
                    rank
                )
            )


        # =================================================
        # Semantic
        # =================================================

        for rank, item in enumerate(
            semantic_results,
            start=1
        ):

            resource = (
                item[
                    "resource"
                ]
            )


            key = (
                resource[
                    "source"
                ],
                resource[
                    "resource_id"
                ]
            )


            resource_map[
                key
            ] = resource


            semantic_raw_scores[
                key
            ] = (
                item[
                    "score"
                ]
            )


            fused_scores[
                key
            ] = (
                fused_scores.get(
                    key,
                    0
                )
                +
                self.semantic_weight
                /
                (
                    self.rrf_k
                    +
                    rank
                )
            )


        # =================================================
        # Relevance + Answerability Gate v5
        # =================================================

        eligible = []

        lexical_evidence_map = {}

        issue_evidence_map = {}


        issue_intent = (
            self._has_issue_intent(
                query
            )
        )


        for key, fused_score in (
            fused_scores.items()
        ):

            resource = (
                resource_map[
                    key
                ]
            )


            bm25_score = (
                bm25_raw_scores.get(
                    key,
                    0
                )
            )


            semantic_score = (
                semantic_raw_scores.get(
                    key,
                    0
                )
            )


            lexical_info = (
                self._get_lexical_evidence(
                    query,
                    resource
                )
            )


            lexical_evidence_map[
                key
            ] = lexical_info


            issue_evidence_score = (
                self._get_issue_evidence_score(
                    resource
                )
            )


            issue_evidence_map[
                key
            ] = (
                issue_evidence_score
            )


            # =============================================
            # Strong lexical evidence
            #
            # v4 only required 2 matches.
            #
            # v5 additionally requires reasonable query
            # coverage, which removes cases like:
            #
            # 2 / 9 = 22%
            # 2 / 12 = 17%
            # =============================================

            lexical_evidence = (

                bm25_score > 0

                and

                lexical_info[
                    "match_count"
                ]
                >=
                lexical_info[
                    "required_matches"
                ]

                and

                lexical_info[
                    "coverage"
                ]
                >=
                self.lexical_coverage_threshold
            )


            strong_semantic_evidence = (

                semantic_score

                >=

                self.semantic_strong_threshold
            )


            if not (
                lexical_evidence
                or
                strong_semantic_evidence
            ):

                continue

            # =============================================
            # Final ranking score
            #
            # v5.2:
            # Keep Weighted RRF as the ranking signal.
            #
            # Query expansion improves candidate recall.
            # Lexical coverage is used only as a gate.
            # Issue evidence is diagnostic only and must
            # not overpower exact lexical/semantic matches.
            # =============================================

            ranking_score = (
                fused_score
            )

            eligible.append(
                (
                    key,
                    ranking_score,
                    fused_score
                )
            )

        # =================================================
        # Final Ranking
        # =================================================

        ranked = sorted(
            eligible,
            key=lambda item:
                item[1],
            reverse=True
        )


        # =================================================
        # Cross-source Diversity
        # =================================================

        selected = []

        selected_keys = set()

        used_sources = set()


        # -------------------------------------------------
        # First pass:
        # one result per source
        # -------------------------------------------------

        for (
            key,
            ranking_score,
            fused_score
        ) in ranked:

            resource = (
                resource_map[
                    key
                ]
            )


            source = (
                resource[
                    "source"
                ]
            )


            if source in used_sources:
                continue


            selected.append(
                self._build_result(
                    key=
                        key,

                    ranking_score=
                        ranking_score,

                    fused_score=
                        fused_score,

                    resource_map=
                        resource_map,

                    bm25_raw_scores=
                        bm25_raw_scores,

                    semantic_raw_scores=
                        semantic_raw_scores,

                    lexical_evidence_map=
                        lexical_evidence_map,

                    issue_evidence_map=
                        issue_evidence_map
                )
            )


            selected_keys.add(
                key
            )


            used_sources.add(
                source
            )


            if len(
                selected
            ) >= top_k:

                return selected


        # -------------------------------------------------
        # Second pass:
        # fill remaining slots
        # -------------------------------------------------

        for (
            key,
            ranking_score,
            fused_score
        ) in ranked:

            if key in selected_keys:
                continue


            selected.append(
                self._build_result(
                    key=
                        key,

                    ranking_score=
                        ranking_score,

                    fused_score=
                        fused_score,

                    resource_map=
                        resource_map,

                    bm25_raw_scores=
                        bm25_raw_scores,

                    semantic_raw_scores=
                        semantic_raw_scores,

                    lexical_evidence_map=
                        lexical_evidence_map,

                    issue_evidence_map=
                        issue_evidence_map
                )
            )


            if len(
                selected
            ) >= top_k:

                break


        return selected