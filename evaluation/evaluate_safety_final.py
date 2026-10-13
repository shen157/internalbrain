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
    / "safety_final_cases.json"
)


RESULT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "safety_final_v1.json"
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
    # Query Safety
    # =====================================================

    if stage == "query":

        decision = (
            guard.check_query(
                case[
                    "text"
                ]
            )
        )


        return (
            decision,
            None
        )


    # =====================================================
    # Retrieved Content Safety
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


        decision = (
            guard.check_resource(
                resource
            )
        )


        return (
            decision,
            None
        )


    # =====================================================
    # Output Safety
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
        f"Unknown safety stage: "
        f"{stage}"
    )


def evaluate_safety_final():

    guard = (
        SafetyGuard()
    )


    cases = (
        load_cases()
    )


    results = []


    total_correct = 0


    attack_cases = 0

    attack_blocked = 0


    benign_cases = 0

    benign_passed = 0


    stage_stats = defaultdict(
        lambda: {
            "total": 0,
            "correct": 0,
            "attack_cases": 0,
            "attack_blocked": 0,
            "benign_cases": 0,
            "benign_passed": 0
        }
    )


    for case in cases:

        decision, citation_validation = (
            evaluate_case(
                guard,
                case
            )
        )


        actual_allowed = (
            decision[
                "allowed"
            ]
        )


        expected_allowed = (
            case[
                "expected_allowed"
            ]
        )


        passed = (
            actual_allowed
            ==
            expected_allowed
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

            total_correct += 1

            stage_stats[
                stage
            ][
                "correct"
            ] += 1


        # =================================================
        # Benign / Attack Metrics
        # =================================================

        if category == "attack":

            attack_cases += 1

            stage_stats[
                stage
            ][
                "attack_cases"
            ] += 1


            if not actual_allowed:

                attack_blocked += 1

                stage_stats[
                    stage
                ][
                    "attack_blocked"
                ] += 1


        elif category == "benign":

            benign_cases += 1

            stage_stats[
                stage
            ][
                "benign_cases"
            ] += 1


            if actual_allowed:

                benign_passed += 1

                stage_stats[
                    stage
                ][
                    "benign_passed"
                ] += 1


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


    # =====================================================
    # Stage Summary
    # =====================================================

    stage_summary = {}


    for stage, stats in (
        stage_stats.items()
    ):

        stage_accuracy = (
            safe_rate(
                stats[
                    "correct"
                ],
                stats[
                    "total"
                ]
            )
        )


        stage_attack_block_rate = (
            safe_rate(
                stats[
                    "attack_blocked"
                ],
                stats[
                    "attack_cases"
                ]
            )
        )


        stage_benign_pass_rate = (
            safe_rate(
                stats[
                    "benign_passed"
                ],
                stats[
                    "benign_cases"
                ]
            )
        )


        stage_summary[
            stage
        ] = {

            "total_cases":
                stats[
                    "total"
                ],

            "accuracy":
                stage_accuracy,

            "attack_cases":
                stats[
                    "attack_cases"
                ],

            "attack_block_rate":
                stage_attack_block_rate,

            "benign_cases":
                stats[
                    "benign_cases"
                ],

            "benign_pass_rate":
                stage_benign_pass_rate,

            "false_positive_rate":
                (
                    1.0
                    -
                    stage_benign_pass_rate

                    if stats[
                        "benign_cases"
                    ]
                    else 0.0
                )
        }


    # =====================================================
    # Global Summary
    # =====================================================

    total_cases = (
        len(
            cases
        )
    )


    overall_accuracy = (
        safe_rate(
            total_correct,
            total_cases
        )
    )


    attack_block_rate = (
        safe_rate(
            attack_blocked,
            attack_cases
        )
    )


    benign_pass_rate = (
        safe_rate(
            benign_passed,
            benign_cases
        )
    )


    false_positive_rate = (
        1.0
        -
        benign_pass_rate
    )


    attack_miss_rate = (
        1.0
        -
        attack_block_rate
    )


    return {

        "version":
            "safety_final_v1",

        "safety_guard":
            "safety_guard_v2",

        "total_cases":
            total_cases,

        "correct_cases":
            total_correct,

        "overall_accuracy":
            overall_accuracy,

        "attack_cases":
            attack_cases,

        "attack_blocked":
            attack_blocked,

        "attack_block_rate":
            attack_block_rate,

        "attack_miss_rate":
            attack_miss_rate,

        "benign_cases":
            benign_cases,

        "benign_passed":
            benign_passed,

        "benign_pass_rate":
            benign_pass_rate,

        "false_positive_rate":
            false_positive_rate,

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
        "\n===== SAFETY FINAL EVALUATION ====="
    )


    summary = (
        evaluate_safety_final()
    )


    print(
        "\n===== FINAL SAFETY SUMMARY ====="
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
            f"{metrics['accuracy']:.2%} | "
            f"Attack Block="
            f"{metrics['attack_block_rate']:.2%} | "
            f"Benign Pass="
            f"{metrics['benign_pass_rate']:.2%}"
        )


    save_results(
        summary
    )


    print(
        "\nResults saved to: "
        f"{RESULT_PATH}"
    )