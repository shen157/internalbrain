import argparse
import json
import re
import statistics
import time

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.services import retrieval_service

from app.data.loader import get_user

from app.llm.answer_service import (
    AnswerService
)

from app.security.audit_logger import (
    AuditLogger
)


# =========================================================
# Paths
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


RESULT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "backend_latency_v1.json"
)


BENCHMARK_AUDIT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "benchmark_audit.jsonl"
)


# =========================================================
# Benchmark Configuration
# =========================================================

BENCHMARK_QUERIES = [

    (
        "u001",
        "What is blocking the payment migration "
        "and when is the revised cutover date?"
    ),

    (
        "u002",
        "Which issue tracks JWT signing key rotation?"
    ),

    (
        "u003",
        "Summarize the main payment migration risks."
    ),

    (
        "u001",
        "Which issue backfills five years of "
        "historical analytics events?"
    ),

    (
        "u008",
        "Which October company notes mention "
        "the payment cutover change?"
    )
]


AUTH_USERS = [
    "u001",
    "u002",
    "u004",
    "u007",
    "u008"
]


RETRIEVAL_ROUNDS = 5

E2E_ROUNDS = 3

PERMISSION_CHANGE_ROUNDS = 10

REAL_LLM_ROUNDS = 2


LIVE_PERMISSION_USER = (
    "u004"
)


LIVE_PERMISSION_CHANNEL = (
    "C-PAY"
)


LIVE_PERMISSION_RESOURCE = (
    "C-PAY:2026-09-24T14:05:00Z"
)


LIVE_PERMISSION_QUERY = (
    "dual-write rollback surface "
    "one-way backfill PAY-104"
)


# =========================================================
# Deterministic LLM
# =========================================================

class DeterministicLLM:

    model = (
        "benchmark-deterministic-llm"
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
                "I could not find enough information "
                "to answer this question."
            )


        citation_id = (
            match.group(1)
        )


        return (
            "Grounded benchmark response "
            f"[{citation_id}]."
        )


# =========================================================
# Statistics Helpers
# =========================================================

def percentile(
    values,
    percentile_value
):

    if not values:
        return None


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
        percentile_value
    )


    lower_index = int(
        position
    )


    upper_index = min(
        lower_index + 1,
        len(ordered) - 1
    )


    fraction = (
        position
        -
        lower_index
    )


    return (
        ordered[lower_index]
        +
        (
            ordered[upper_index]
            -
            ordered[lower_index]
        )
        *
        fraction
    )


def summarize(
    values
):

    if not values:

        return {
            "count": 0,
            "min_ms": None,
            "mean_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "max_ms": None
        }


    return {

        "count":
            len(values),

        "min_ms":
            min(values),

        "mean_ms":
            statistics.mean(
                values
            ),

        "p50_ms":
            percentile(
                values,
                0.50
            ),

        "p95_ms":
            percentile(
                values,
                0.95
            ),

        "max_ms":
            max(values)
    }


def timed_call(
    function
):

    started = (
        time.perf_counter()
    )


    result = (
        function()
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


    return (
        result,
        elapsed_ms
    )


# =========================================================
# Authorization Benchmark
# =========================================================

def benchmark_authorization():

    users = {
        user_id:
            get_user(
                user_id
            )

        for user_id
        in AUTH_USERS
    }


    samples = []


    # 20 × 5 = 100 samples
    for _ in range(20):

        for user_id in AUTH_USERS:

            user = (
                users[
                    user_id
                ]
            )


            _, elapsed_ms = (
                timed_call(

                    lambda user=user:
                        retrieval_service
                        .get_authorized_resources(
                            user
                        )
                )
            )


            samples.append(
                elapsed_ms
            )


    return (
        summarize(
            samples
        )
    )


# =========================================================
# Retrieval Benchmark
# =========================================================

def benchmark_retrieval():

    # Warm-up:
    # model loading / cache initialization is excluded
    # from steady-state latency.

    for user_id, query in (
        BENCHMARK_QUERIES
    ):

        retrieval_service.search(

            user_id=
                user_id,

            query=
                query,

            top_k=
                5,

            method=
                "hybrid"
        )


    samples = []


    for _ in range(
        RETRIEVAL_ROUNDS
    ):

        for user_id, query in (
            BENCHMARK_QUERIES
        ):

            _, elapsed_ms = (
                timed_call(

                    lambda
                    user_id=user_id,
                    query=query:
                        retrieval_service.search(

                            user_id=
                                user_id,

                            query=
                                query,

                            top_k=
                                5,

                            method=
                                "hybrid"
                        )
                )
            )


            samples.append(
                elapsed_ms
            )


    return (
        summarize(
            samples
        )
    )


# =========================================================
# Deterministic Backend E2E Benchmark
# =========================================================

def benchmark_e2e_backend():

    if (
        BENCHMARK_AUDIT_PATH
        .exists()
    ):

        BENCHMARK_AUDIT_PATH.unlink()


    benchmark_audit = (
        AuditLogger(
            log_path=
                BENCHMARK_AUDIT_PATH
        )
    )


    service = (
        AnswerService(

            retrieval_service=
                retrieval_service,

            llm_client=
                DeterministicLLM(),

            audit_logger=
                benchmark_audit
        )
    )


    # Warm-up

    for user_id, query in (
        BENCHMARK_QUERIES
    ):

        service.answer(
            user_id=
                user_id,

            query=
                query,

            top_k=
                5
        )


    samples = []

    successful = 0


    for _ in range(
        E2E_ROUNDS
    ):

        for user_id, query in (
            BENCHMARK_QUERIES
        ):

            result, elapsed_ms = (
                timed_call(

                    lambda
                    user_id=user_id,
                    query=query:
                        service.answer(

                            user_id=
                                user_id,

                            query=
                                query,

                            top_k=
                                5
                        )
                )
            )


            samples.append(
                elapsed_ms
            )


            if (
                result.get(
                    "llm_called"
                )
                is True
                and
                result.get(
                    "safety_blocked"
                )
                is False
            ):

                successful += 1


    return {

        "latency":
            summarize(
                samples
            ),

        "successful_requests":
            successful,

        "total_requests":
            len(
                samples
            ),

        "success_rate":
            (
                successful
                /
                len(samples)

                if samples
                else 0.0
            ),

        "llm":
            (
                "deterministic test double; "
                "remote model latency excluded"
            )
    }


# =========================================================
# Live Permission Change Benchmark
# =========================================================

def benchmark_permission_change():

    client = (
        TestClient(
            app
        )
    )


    def mutate(
        action
    ):

        return client.post(

            "/demo/permissions/"
            "slack/membership",

            json={

                "actor_user_id":
                    "u005",

                "target_user_id":
                    LIVE_PERMISSION_USER,

                "channel_id":
                    LIVE_PERMISSION_CHANNEL,

                "action":
                    action,

                "reason":
                    (
                        "Backend latency benchmark"
                    )
            },

            headers={
                "X-InternalBrain-Actor": "u005"
            }
        )


    # Reset baseline

    reset_response = (
        mutate(
            "revoke"
        )
    )

    reset_response.raise_for_status()


    api_samples = []

    propagation_samples = []

    propagation_successes = 0


    for _ in range(
        PERMISSION_CHANGE_ROUNDS
    ):

        # -----------------------------------------
        # Grant API latency
        # -----------------------------------------

        grant_response, grant_ms = (
            timed_call(
                lambda:
                    mutate(
                        "grant"
                    )
            )
        )


        grant_response.raise_for_status()


        api_samples.append(
            grant_ms
        )


        # -----------------------------------------
        # Grant -> first retrieval observing change
        # -----------------------------------------

        propagation_started = (
            time.perf_counter()
        )


        search_response = (
            retrieval_service
            .search(

                user_id=
                    LIVE_PERMISSION_USER,

                query=
                    LIVE_PERMISSION_QUERY,

                top_k=
                    10,

                method=
                    "hybrid"
            )
        )


        returned_ids = [

            item[
                "resource"
            ][
                "resource_id"
            ]

            for item
            in search_response[
                "results"
            ]
        ]


        propagation_ms = (
            (
                time.perf_counter()
                -
                propagation_started
            )
            *
            1000
            +
            grant_ms
        )


        target_visible = (
            LIVE_PERMISSION_RESOURCE
            in returned_ids
        )


        if target_visible:

            propagation_successes += 1


        propagation_samples.append(
            propagation_ms
        )


        # -----------------------------------------
        # Restore DENY
        # -----------------------------------------

        revoke_response = (
            mutate(
                "revoke"
            )
        )

        revoke_response.raise_for_status()


    # Final baseline verification

    final_search = (
        retrieval_service
        .search(

            user_id=
                LIVE_PERMISSION_USER,

            query=
                LIVE_PERMISSION_QUERY,

            top_k=
                10,

            method=
                "hybrid"
        )
    )


    final_ids = [

        item[
            "resource"
        ][
            "resource_id"
        ]

        for item
        in final_search[
            "results"
        ]
    ]


    return {

        "grant_api_latency":
            summarize(
                api_samples
            ),

        "permission_propagation_latency":
            summarize(
                propagation_samples
            ),

        "propagation_success_rate":
            (
                propagation_successes
                /
                PERMISSION_CHANGE_ROUNDS
            ),

        "reindex_required":
            False,

        "baseline_restored":
            (
                LIVE_PERMISSION_RESOURCE
                not in final_ids
            )
    }


# =========================================================
# Real LLM E2E Benchmark
# =========================================================

def benchmark_real_llm():

    benchmark_audit = (
        AuditLogger(
            log_path=
                BENCHMARK_AUDIT_PATH
        )
    )


    # No injected llm_client:
    # AnswerService uses the real configured LLMClient.

    service = (
        AnswerService(

            retrieval_service=
                retrieval_service,

            audit_logger=
                benchmark_audit
        )
    )


    samples = []

    successful = 0

    failures = []


    # One warm-up request

    warm_user, warm_query = (
        BENCHMARK_QUERIES[0]
    )


    try:

        service.answer(

            user_id=
                warm_user,

            query=
                warm_query,

            top_k=
                5
        )

    except Exception as error:

        failures.append(
            f"warmup: {str(error)}"
        )


    for _ in range(
        REAL_LLM_ROUNDS
    ):

        for user_id, query in (
            BENCHMARK_QUERIES
        ):

            started = (
                time.perf_counter()
            )


            try:

                result = (
                    service.answer(

                        user_id=
                            user_id,

                        query=
                            query,

                        top_k=
                            5
                    )
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


                samples.append(
                    elapsed_ms
                )


                if (
                    result.get(
                        "llm_called"
                    )
                    is True
                ):

                    successful += 1


            except Exception as error:

                failures.append(
                    str(error)
                )


    return {

        "latency":
            summarize(
                samples
            ),

        "successful_requests":
            successful,

        "measured_requests":
            len(
                samples
            ),

        "failure_count":
            len(
                failures
            ),

        "failures":
            failures,

        "includes_remote_llm":
            True
    }


# =========================================================
# Main
# =========================================================

def main(
    include_real_llm=False
):

    print(
        "\n===== INTERNALBRAIN BACKEND LATENCY BENCHMARK ====="
    )


    print(
        "\n[1/4] Authorization..."
    )

    authorization = (
        benchmark_authorization()
    )


    print(
        "[2/4] Hybrid Retrieval..."
    )

    retrieval = (
        benchmark_retrieval()
    )


    print(
        "[3/4] Backend E2E..."
    )

    e2e_backend = (
        benchmark_e2e_backend()
    )


    print(
        "[4/4] Live Permission Change..."
    )

    permission_change = (
        benchmark_permission_change()
    )


    real_llm = None


    if include_real_llm:

        print(
            "[Optional] Real LLM E2E..."
        )

        real_llm = (
            benchmark_real_llm()
        )


    result = {

        "version":
            "backend_latency_v1",

        "resource_count":
            retrieval_service
            .resource_count(),

        "authorization_latency":
            authorization,

        "hybrid_retrieval_latency":
            retrieval,

        "backend_e2e_latency":
            e2e_backend,

        "live_permission_change":
            permission_change,

        "real_llm_e2e_latency":
            real_llm
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
        "\n===== BACKEND LATENCY SUMMARY ====="
    )


    print(
        "\nAuthorization:"
    )

    print(
        f"p50 = "
        f"{authorization['p50_ms']:.3f} ms"
    )

    print(
        f"p95 = "
        f"{authorization['p95_ms']:.3f} ms"
    )


    print(
        "\nHybrid Retrieval:"
    )

    print(
        f"p50 = "
        f"{retrieval['p50_ms']:.3f} ms"
    )

    print(
        f"p95 = "
        f"{retrieval['p95_ms']:.3f} ms"
    )


    print(
        "\nBackend E2E "
        "(remote LLM excluded):"
    )

    print(
        f"p50 = "
        f"{e2e_backend['latency']['p50_ms']:.3f} ms"
    )

    print(
        f"p95 = "
        f"{e2e_backend['latency']['p95_ms']:.3f} ms"
    )

    print(
        f"Success Rate = "
        f"{e2e_backend['success_rate']:.2%}"
    )


    permission_api = (
        permission_change[
            "grant_api_latency"
        ]
    )


    propagation = (
        permission_change[
            "permission_propagation_latency"
        ]
    )


    print(
        "\nLive Permission Grant API:"
    )

    print(
        f"p50 = "
        f"{permission_api['p50_ms']:.3f} ms"
    )

    print(
        f"p95 = "
        f"{permission_api['p95_ms']:.3f} ms"
    )


    print(
        "\nPermission Propagation "
        "(grant -> retrievable):"
    )

    print(
        f"p50 = "
        f"{propagation['p50_ms']:.3f} ms"
    )

    print(
        f"p95 = "
        f"{propagation['p95_ms']:.3f} ms"
    )

    print(
        "Success Rate = "
        f"{permission_change['propagation_success_rate']:.2%}"
    )


    if real_llm is not None:

        print(
            "\nReal LLM E2E:"
        )

        if (
            real_llm[
                "latency"
            ][
                "count"
            ]
            >
            0
        ):

            print(
                f"p50 = "
                f"{real_llm['latency']['p50_ms']:.3f} ms"
            )

            print(
                f"p95 = "
                f"{real_llm['latency']['p95_ms']:.3f} ms"
            )


        print(
            f"Failures = "
            f"{real_llm['failure_count']}"
        )


    print(
        "\nResults saved to: "
        f"{RESULT_PATH}"
    )


if __name__ == "__main__":

    parser = (
        argparse.ArgumentParser()
    )


    parser.add_argument(
        "--real-llm",
        action="store_true",
        help=(
            "Also benchmark real remote "
            "LLM end-to-end latency."
        )
    )


    args = (
        parser.parse_args()
    )


    main(
        include_real_llm=
            args.real_llm
    )
