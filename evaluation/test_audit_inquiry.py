import json
import re
import statistics
import time

from pathlib import Path

from fastapi.testclient import (
    TestClient
)

from app.api.main import (
    app
)

from app.api.services import (
    retrieval_service
)

from app.llm.answer_service import (
    AnswerService
)

from app.security.audit_logger import (
    AuditLogger
)

from app.security.audit_query_service import (
    AuditQueryService
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


TEMP_AUDIT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "audit_inquiry_test_log.jsonl"
)


RESULT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "audit_inquiry_v1.json"
)


# =========================================================
# Deterministic LLM
# =========================================================

class DeterministicLLM:

    model = (
        "audit-test-llm"
    )


    def generate(
        self,
        system_prompt,
        user_prompt
    ):

        match = re.search(
            r"\[(S\d+)\]",
            user_prompt
        )


        if match is None:

            return (
                "No authorized context."
            )


        return (
            "Grounded audit test answer "
            f"[{match.group(1)}]."
        )


# =========================================================
# Statistics
# =========================================================

def percentile(
    values,
    p
):

    ordered = sorted(
        values
    )


    if len(ordered) == 1:
        return ordered[0]


    position = (
        (
            len(ordered)
            - 1
        )
        *
        p
    )


    lower = int(
        position
    )


    upper = min(
        lower + 1,
        len(ordered) - 1
    )


    fraction = (
        position
        -
        lower
    )


    return (
        ordered[lower]
        +
        (
            ordered[upper]
            -
            ordered[lower]
        )
        *
        fraction
    )


def summarize_latency(
    samples
):

    return {

        "count":
            len(samples),

        "mean_ms":
            statistics.mean(
                samples
            ),

        "p50_ms":
            percentile(
                samples,
                0.50
            ),

        "p95_ms":
            percentile(
                samples,
                0.95
            ),

        "max_ms":
            max(
                samples
            )
    }


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    print(
        "\n===== AUDIT INQUIRY TEST ====="
    )


    if TEMP_AUDIT_PATH.exists():

        TEMP_AUDIT_PATH.unlink()


    audit_logger = (
        AuditLogger(
            log_path=
                TEMP_AUDIT_PATH
        )
    )


    query_service = (
        AuditQueryService(
            audit_logger
        )
    )


    answer_service = (
        AnswerService(

            retrieval_service=
                retrieval_service,

            llm_client=
                DeterministicLLM(),

            audit_logger=
                audit_logger
        )
    )


    # =====================================================
    # 1. Generate a real E2E query trace
    # =====================================================

    answer_result = (
        answer_service.answer(

            user_id=
                "u002",

            query=(
                "Which issue tracks "
                "JWT signing key rotation?"
            ),

            top_k=
                5
        )
    )


    query_id = (
        answer_result[
            "query_id"
        ]
    )


    trace = (
        query_service
        .search_events(

            query_id=
                query_id,

            limit=
                100,

            newest_first=
                False
        )
    )


    event_types = [

        event[
            "event_type"
        ]

        for event
        in trace[
            "events"
        ]
    ]


    expected_event_types = {

        "query_received",
        "input_safety",
        "authorization_retrieval",
        "retrieved_content_safety",
        "context_assembled",
        "llm_generation",
        "citation_validation",
        "output_safety",
        "final_response"
    }


    actual_event_types = set(
        event_types
    )


    missing_event_types = sorted(
        expected_event_types
        -
        actual_event_types
    )


    trace_complete = (
        len(
            missing_event_types
        )
        ==
        0
    )


    # =====================================================
    # 2. Permission-change audit event
    # =====================================================

    permission_event = (
        audit_logger.log_event(

            event_type=
                "permission_change",

            user_id=
                "audit-test-admin",

            action=
                "grant_slack_membership",

            resource_id=
                "C-PAY",

            auth_decision=
                "granted",

            details={

                "target_user_id":
                    "u004",

                "query_time_enforced":
                    True,

                "reindex_required":
                    False
            }
        )
    )


    permission_search = (
        query_service
        .search_events(

            event_type=
                "permission_change",

            user_id=
                "audit-test-admin",

            resource_id=
                "C-PAY",

            limit=
                20
        )
    )


    permission_filter_pass = (
        permission_search[
            "matched_count"
        ]
        ==
        1
        and
        permission_search[
            "events"
        ][0][
            "event_id"
        ]
        ==
        permission_event[
            "event_id"
        ]
    )


    target_user_search = (
        query_service
        .search_events(

            event_type=
                "permission_change",

            user_id=
                "u004",

            resource_id=
                "C-PAY",

            limit=
                20
        )
    )


    target_user_filter_pass = (
        target_user_search[
            "matched_count"
        ]
        ==
        1
        and
        target_user_search[
            "events"
        ][0][
            "event_id"
        ]
        ==
        permission_event[
            "event_id"
        ]
    )


    # =====================================================
    # 3. Chain Integrity
    # =====================================================

    integrity_before = (
        audit_logger
        .verify_chain()
    )


    event_count_before_queries = (
        integrity_before[
            "event_count"
        ]
    )


    # =====================================================
    # 4. Inquiry Latency
    # =====================================================

    latency_samples = []


    for _ in range(50):

        started = (
            time.perf_counter()
        )


        query_service.search_events(

            event_type=
                "permission_change",

            limit=
                50
        )


        elapsed_ms = (
            (
                time.perf_counter()
                -
                started
            )
            *
            1000
        )


        latency_samples.append(
            elapsed_ms
        )


    latency = (
        summarize_latency(
            latency_samples
        )
    )


    integrity_after = (
        audit_logger
        .verify_chain()
    )


    read_only_pass = (
        event_count_before_queries
        ==
        integrity_after[
            "event_count"
        ]
    )


    # =====================================================
    # 5. Real API Endpoint Smoke Test
    # =====================================================

    client = (
        TestClient(
            app
        )
    )


    # Generate one identifiable permission event
    # in the real application audit log.

    revoke_response = (
        client.post(

            "/demo/permissions/"
            "slack/membership",

            json={

                "actor_user_id":
                    "u005",

                "target_user_id":
                    "u004",

                "channel_id":
                    "C-PAY",

                "action":
                    "revoke",

                "reason":
                    "Audit inquiry API test"
            },

            headers={
                "X-InternalBrain-Actor": "u005"
            }
        )
    )


    revoke_response.raise_for_status()


    grant_response = (
        client.post(

            "/demo/permissions/"
            "slack/membership",

            json={

                "actor_user_id":
                    "u005",

                "target_user_id":
                    "u004",

                "channel_id":
                    "C-PAY",

                "action":
                    "grant",

                "reason":
                    "Audit inquiry API test"
            },

            headers={
                "X-InternalBrain-Actor": "u005"
            }
        )
    )


    grant_response.raise_for_status()


    api_query_response = (
        client.get(

            "/audit/events",

            params={

                "event_type":
                    "permission_change",

                "user_id":
                    "u005",

                "resource_id":
                    "C-PAY",

                "limit":
                    20
            },

            headers={
                "X-InternalBrain-Actor": "u005"
            }
        )
    )


    api_query_response.raise_for_status()


    api_payload = (
        api_query_response.json()
    )


    api_endpoint_pass = (
        api_payload[
            "chain_valid"
        ]
        is True
        and
        api_payload[
            "matched_count"
        ]
        >=
        2
    )


    # Restore baseline

    restore_response = (
        client.post(

            "/demo/permissions/"
            "slack/membership",

            json={

                "actor_user_id":
                    "u005",

                "target_user_id":
                    "u004",

                "channel_id":
                    "C-PAY",

                "action":
                    "revoke",

                "reason":
                    "Restore baseline after audit test"
            },

            headers={
                "X-InternalBrain-Actor": "u005"
            }
        )
    )


    restore_response.raise_for_status()


    real_chain = (
        client.get(
            "/audit/verify"
        )
    )


    real_chain.raise_for_status()


    real_chain_valid = (
        real_chain.json()[
            "valid"
        ]
    )


    # =====================================================
    # 6. Final Checks
    # =====================================================

    checks = {

        "query_trace_complete":
            trace_complete,

        "permission_filter_correct":
            permission_filter_pass,

        "permission_target_user_filter_correct":
            target_user_filter_pass,

        "temp_chain_valid":
            (
                integrity_after[
                    "valid"
                ]
                is True
            ),

        "audit_query_is_read_only":
            read_only_pass,

        "api_endpoint_works":
            api_endpoint_pass,

        "real_audit_chain_valid":
            (
                real_chain_valid
                is True
            )
    }


    passed = all(
        checks.values()
    )


    trace_completeness = (
        (
            len(
                expected_event_types
            )
            -
            len(
                missing_event_types
            )
        )
        /
        len(
            expected_event_types
        )
    )


    result = {

        "version":
            "audit_inquiry_v1",

        "query_id":
            query_id,

        "expected_trace_event_count":
            len(
                expected_event_types
            ),

        "observed_trace_event_types":
            event_types,

        "missing_trace_event_types":
            missing_event_types,

        "trace_completeness":
            trace_completeness,

        "permission_filter_matched_count":
            permission_search[
                "matched_count"
            ],

        "audit_inquiry_latency":
            latency,

        "checks":
            checks,

        "passed":
            passed
    }


    RESULT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        RESULT_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )


    print(
        "\nQuery ID:",
        query_id
    )


    print(
        "\nObserved trace:"
    )


    for event_type in event_types:

        print(
            " -",
            event_type
        )


    print(
        "\nTrace completeness: "
        f"{trace_completeness:.2%}"
    )


    print(
        "\nAudit Inquiry Latency:"
    )


    print(
        f"p50 = "
        f"{latency['p50_ms']:.3f} ms"
    )


    print(
        f"p95 = "
        f"{latency['p95_ms']:.3f} ms"
    )


    print(
        "\n===== CHECKS ====="
    )


    for name, value in checks.items():

        print(
            f"{name}: "
            f"{'PASS' if value else 'FAIL'}"
        )


    print(
        "\nOverall:",
        "PASS"
        if passed
        else "FAIL"
    )


    print(
        "\nResults saved to:",
        RESULT_PATH
    )
