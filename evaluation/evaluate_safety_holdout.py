import json
from collections import defaultdict
from pathlib import Path

from app.security.safety_guard import (
    SafetyGuard
)

from app.llm.citation_validator import (
    validate_citations
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


CASE_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "safety_holdout_cases.json"
)


RESULT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "safety_holdout_v1.json"
)


def load_cases():

    with open(
        CASE_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def safe_rate(
    numerator,
    denominator
):

    if denominator == 0:
        return 0.0

    return (
        numerator
        /
        denominator
    )


def evaluate_case(
    guard,
    case
):

    stage = (
        case[
            "stage"
        ]
    )


    # =====================================================
    # Query
    # =====================================================

    if stage == "query":

        return (
            guard.check_query(
                case[
                    "text"
                ]
            ),
            None
        )


    # =====================================================
    # Retrieved Content
    # =====================================================

    if stage == "content":

        resource = {
            "resource_id":
                case[
                    "test_id"
                ],

            "source":
                "test",

            "title":
                case.get(
                    "title",
                    ""
                ),

            "content":
                case.get(
                    "content",
                    ""
                )
        }


        return (
            guard.check_resource(
                resource
            ),
            None
        )


    # =====================================================
    # Output
    # =====================================================

    if stage == "output":

        citations = [
            {
                "citation_id":
                    citation_id
            }

            for citation_id
            in case.get(
                "available_citations",
                []
            )
        ]


        citation_validation = (
            validate_citations(
                answer=
                    case[
                        "answer"
                    ],

                citations=
                    citations
            )
        )


        decision = (
            guard.check_output(
                answer=
                    case[
                        "answer"
                    ],

                citation_validation=
                    citation_validation
            )
        )


        return (
            decision,
            citation_validation
        )


    raise ValueError(
        f"Unknown stage: {stage}"
    )


def evaluate_holdout():

    guard = (
        SafetyGuard()
    )


    cases = (
        load_cases()
    )


    results = []

    correct = 0

    attack_cases = 0
    attack_blocked = 0

    benign_cases = 0
    benign_passed = 0


    stage_stats = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0
        }
    )


    for case in cases:

        decision, citation_validation = (
            evaluate_case(
                guard,
                case
            )
        )


        expected_allowed = (
            case[
                "expected_allowed"
            ]
        )


        actual_allowed = (
            decision[
                "allowed"
            ]
        )


        passed = (
            expected_allowed
            ==
            actual_allowed
        )


        stage = (
            case[
                "stage"
            ]
        )


        category = (
            case[
                "category"
            ]
        )


        stage_stats[
            stage
        ][
            "total"
        ] += 1


        if passed:

            correct += 1

            stage_stats[
                stage
            ][
                "correct"
            ] += 1


        if category == "attack":

            attack_cases += 1

            if not actual_allowed:

                attack_blocked += 1


        else:

            benign_cases += 1

            if actual_allowed:

                benign_passed += 1


        result = {
            "test_id":
                case[
                    "test_id"
                ],

            "stage":
                stage,

            "category":
                category,

            "expected_allowed":
                expected_allowed,

            "actual_allowed":
                actual_allowed,

            "reason":
                decision[
                    "reason"
                ],

            "passed":
                passed
        }


        if citation_validation is not None:

            result[
                "citation_validation"
            ] = (
                citation_validation
            )


        results.append(
            result
        )


        print(
            f"{case['test_id']} | "
            f"{stage} | "
            f"{category} | "
            f"expected="
            f"{'ALLOW' if expected_allowed else 'BLOCK'} | "
            f"actual="
            f"{'ALLOW' if actual_allowed else 'BLOCK'} | "
            f"{'PASS' if passed else 'FAIL'}"
        )


    stage_summary = {}


    for stage, stats in (
        stage_stats.items()
    ):

        stage_summary[
            stage
        ] = {
            "total_cases":
                stats[
                    "total"
                ],

            "accuracy":
                safe_rate(
                    stats[
                        "correct"
                    ],
                    stats[
                        "total"
                    ]
                )
        }


    return {

        "version":
            "safety_holdout_v1",

        "safety_guard":
            "safety_guard_v2",

        "total_cases":
            len(
                cases
            ),

        "correct_cases":
            correct,

        "overall_accuracy":
            safe_rate(
                correct,
                len(
                    cases
                )
            ),

        "attack_cases":
            attack_cases,

        "attack_block_rate":
            safe_rate(
                attack_blocked,
                attack_cases
            ),

        "benign_cases":
            benign_cases,

        "benign_pass_rate":
            safe_rate(
                benign_passed,
                benign_cases
            ),

        "false_positive_rate":
            (
                1.0
                -
                safe_rate(
                    benign_passed,
                    benign_cases
                )
            ),

        "stage_metrics":
            stage_summary,

        "results":
            results
    }


def save_results(
    summary
):

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
            summary,
            f,
            indent=2,
            ensure_ascii=False
        )


if __name__ == "__main__":

    print(
        "\n===== SAFETY UNTOUCHED HOLDOUT ====="
    )


    summary = (
        evaluate_holdout()
    )


    print(
        "\n===== HOLDOUT SUMMARY ====="
    )


    print(
        f"Total Cases: "
        f"{summary['total_cases']}"
    )


    print(
        f"Correct Cases: "
        f"{summary['correct_cases']}"
    )


    print(
        f"Overall Accuracy: "
        f"{summary['overall_accuracy']:.2%}"
    )


    print(
        f"Attack Block Rate: "
        f"{summary['attack_block_rate']:.2%}"
    )


    print(
        f"Benign Pass Rate: "
        f"{summary['benign_pass_rate']:.2%}"
    )


    print(
        f"False Positive Rate: "
        f"{summary['false_positive_rate']:.2%}"
    )


    print(
        "\n===== STAGE METRICS ====="
    )


    for stage, metrics in (
        summary[
            "stage_metrics"
        ].items()
    ):

        print(
            f"{stage}: "
            f"Accuracy="
            f"{metrics['accuracy']:.2%}"
        )


    save_results(
        summary
    )


    print(
        "\nResults saved to: "
        f"{RESULT_PATH}"
    )