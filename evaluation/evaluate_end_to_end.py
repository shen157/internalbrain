import json
import time

from pathlib import Path

from app.llm.answer_service import (
    AnswerService
)

from evaluation.metrics import (
    latency_summary
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


TEST_CASE_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "e2e_test_cases.json"
)


RESULT_DIR = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
)


OUTPUT_PATH = (
    RESULT_DIR
    / "end_to_end_v1.json"
)


def load_test_cases():

    with open(
        TEST_CASE_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def check_expected(
    result,
    expected
):

    checks = {}


    # ==========================================
    # Boolean fields
    # ==========================================

    for field in [
        "llm_called",
        "abstained",
        "safety_blocked"
    ]:

        if field in expected:

            checks[field] = (
                result.get(field)
                ==
                expected[field]
            )


    # ==========================================
    # Minimum source count
    # ==========================================

    if "min_sources" in expected:

        checks[
            "min_sources"
        ] = (
            result.get(
                "source_count",
                0
            )
            >=
            expected[
                "min_sources"
            ]
        )


    # ==========================================
    # Maximum source count
    # ==========================================

    if "max_sources" in expected:

        checks[
            "max_sources"
        ] = (
            result.get(
                "source_count",
                0
            )
            <=
            expected[
                "max_sources"
            ]
        )


    passed = all(
        checks.values()
    )


    return {
        "passed":
            passed,

        "checks":
            checks
    }


def evaluate_end_to_end():

    test_cases = (
        load_test_cases()
    )


    service = (
        AnswerService()
    )


    results = []

    all_latencies = []

    llm_latencies = []

    no_llm_latencies = []


    for case in test_cases:

        start = (
            time.perf_counter()
        )


        response = (
            service.answer(
                user_id=
                    case[
                        "user_id"
                    ],

                query=
                    case[
                        "query"
                    ],

                top_k=5
            )
        )


        end = (
            time.perf_counter()
        )


        latency_ms = (
            (
                end
                -
                start
            )
            *
            1000
        )


        all_latencies.append(
            latency_ms
        )


        if response.get(
            "llm_called"
        ):

            llm_latencies.append(
                latency_ms
            )

        else:

            no_llm_latencies.append(
                latency_ms
            )


        expected_result = (
            check_expected(
                response,
                case[
                    "expected"
                ]
            )
        )


        result = {

            "test_id":
                case[
                    "test_id"
                ],

            "user_id":
                case[
                    "user_id"
                ],

            "query":
                case[
                    "query"
                ],

            "passed":
                expected_result[
                    "passed"
                ],

            "checks":
                expected_result[
                    "checks"
                ],

            "latency_ms":
                latency_ms,

            "llm_called":
                response.get(
                    "llm_called"
                ),

            "abstained":
                response.get(
                    "abstained"
                ),

            "safety_blocked":
                response.get(
                    "safety_blocked"
                ),

            "source_count":
                response.get(
                    "source_count"
                ),

            "citation_valid":
                (
                    response.get(
                        "citation_validation"
                    )
                    or {}
                ).get(
                    "valid"
                )
        }


        results.append(
            result
        )


    total_cases = len(
        results
    )


    passed_cases = sum(
        1
        for item in results
        if item[
            "passed"
        ]
    )


    task_success_rate = (
        passed_cases
        /
        total_cases
        if total_cases
        else 0
    )


    summary = {

        "version":
            "end_to_end_v1",

        "total_cases":
            total_cases,

        "passed_cases":
            passed_cases,

        "task_success_rate":
            task_success_rate,

        "latency":
            {
                "all":
                    latency_summary(
                        all_latencies
                    ),

                "llm_called":
                    latency_summary(
                        llm_latencies
                    ),

                "llm_not_called":
                    latency_summary(
                        no_llm_latencies
                    )
            },

        "results":
            results
    }


    return summary


def save_results(
    summary
):

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    with open(
        OUTPUT_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
            ensure_ascii=False
        )


    print(
        "\nResults saved to:"
        f" {OUTPUT_PATH}"
    )


if __name__ == "__main__":

    summary = (
        evaluate_end_to_end()
    )


    print(
        "===== End-to-End Evaluation ====="
    )


    for result in (
        summary[
            "results"
        ]
    ):

        print(
            f"{result['test_id']} | "
            f"{'PASS' if result['passed'] else 'FAIL'} | "
            f"{result['latency_ms']:.2f} ms | "
            f"LLM={result['llm_called']} | "
            f"Sources={result['source_count']}"
        )


    print()


    print(
        f"Total Cases: "
        f"{summary['total_cases']}"
    )

    print(
        f"Passed Cases: "
        f"{summary['passed_cases']}"
    )

    print(
        f"Task Success Rate: "
        f"{summary['task_success_rate']:.2%}"
    )


    print(
        "\nAll Requests:"
    )

    print(
        summary[
            "latency"
        ][
            "all"
        ]
    )


    print(
        "\nLLM Requests:"
    )

    print(
        summary[
            "latency"
        ][
            "llm_called"
        ]
    )


    print(
        "\nNo-LLM Requests:"
    )

    print(
        summary[
            "latency"
        ][
            "llm_not_called"
        ]
    )


    save_results(
        summary
    )