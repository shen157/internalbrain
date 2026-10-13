import json
from collections import defaultdict
from pathlib import Path

from app.data.loader import (
    get_user
)

from app.retrieval.retrieval_service import (
    RetrievalService
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


TEST_CASE_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "retrieval_holdout_cases.json"
)


RESULT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "retrieval_holdout_v1.json"
)


TOP_K = 5


def safe_mean(values):

    if not values:
        return 0.0

    return (
        sum(values)
        /
        len(values)
    )


def load_test_cases():

    with open(
        TEST_CASE_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def evaluate_holdout():

    service = (
        RetrievalService()
    )

    test_cases = (
        load_test_cases()
    )


    recall_scores = []

    reciprocal_ranks = []

    hit_scores = []

    case_results = []


    total_returned = 0

    unauthorized_returned = 0

    negative_cases = 0

    negative_passed = 0


    category_stats = defaultdict(
        lambda: {
            "positive_recall": [],
            "positive_hit": [],
            "positive_rr": [],
            "negative_cases": 0,
            "negative_passed": 0
        }
    )


    for case in test_cases:

        response = (
            service.search(
                user_id=
                    case["user_id"],

                query=
                    case["query"],

                top_k=
                    TOP_K,

                method=
                    "hybrid"
            )
        )


        results = (
            response["results"]
        )


        returned_ids = [
            item["resource"]["resource_id"]
            for item in results
        ]


        # ==========================================
        # Permission validation
        # ==========================================

        user = (
            get_user(
                case["user_id"]
            )
        )


        case_unauthorized = 0


        for item in results:

            total_returned += 1

            resource = (
                item["resource"]
            )


            allowed = (
                service
                .permission_engine
                .can_access(
                    user,
                    resource
                )
            )


            if not allowed:

                unauthorized_returned += 1

                case_unauthorized += 1


        category = (
            case.get(
                "category",
                "uncategorized"
            )
        )


        # ==========================================
        # Negative case
        # ==========================================

        if case["expect_no_results"]:

            negative_cases += 1

            category_stats[
                category
            ][
                "negative_cases"
            ] += 1


            passed = (
                len(results)
                ==
                0
            )


            if passed:

                negative_passed += 1

                category_stats[
                    category
                ][
                    "negative_passed"
                ] += 1


            case_results.append({
                "test_id":
                    case["test_id"],

                "category":
                    category,

                "user_id":
                    case["user_id"],

                "query":
                    case["query"],

                "returned_ids":
                    returned_ids,

                "expect_no_results":
                    True,

                "passed":
                    passed,

                "unauthorized_results":
                    case_unauthorized
            })


            print(
                f"{case['test_id']} | "
                f"{category} | "
                f"Negative | "
                f"Results: {len(results)} | "
                f"{'PASS' if passed else 'FAIL'}"
            )


            continue


        # ==========================================
        # Positive case
        # ==========================================

        expected = (
            case["expected_sources"]
        )


        hits = [
            resource_id
            for resource_id in expected
            if resource_id in returned_ids
        ]


        recall_at_5 = (
            len(hits)
            /
            len(expected)

            if expected
            else 0.0
        )


        hit_at_5 = (
            1.0
            if hits
            else 0.0
        )


        first_rank = None


        for rank, resource_id in enumerate(
            returned_ids,
            start=1
        ):

            if resource_id in expected:

                first_rank = rank
                break


        reciprocal_rank = (
            1.0 / first_rank
            if first_rank is not None
            else 0.0
        )


        recall_scores.append(
            recall_at_5
        )

        hit_scores.append(
            hit_at_5
        )

        reciprocal_ranks.append(
            reciprocal_rank
        )


        category_stats[
            category
        ][
            "positive_recall"
        ].append(
            recall_at_5
        )

        category_stats[
            category
        ][
            "positive_hit"
        ].append(
            hit_at_5
        )

        category_stats[
            category
        ][
            "positive_rr"
        ].append(
            reciprocal_rank
        )


        case_results.append({
            "test_id":
                case["test_id"],

            "category":
                category,

            "user_id":
                case["user_id"],

            "query":
                case["query"],

            "expected_sources":
                expected,

            "returned_ids":
                returned_ids,

            "hits":
                hits,

            "recall_at_5":
                recall_at_5,

            "hit_at_5":
                hit_at_5,

            "first_relevant_rank":
                first_rank,

            "reciprocal_rank":
                reciprocal_rank,

            "unauthorized_results":
                case_unauthorized
        })


        print(
            f"{case['test_id']} | "
            f"{category} | "
            f"Recall@5: "
            f"{recall_at_5:.2%} | "
            f"Hit@5: "
            f"{hit_at_5:.0%} | "
            f"RR: "
            f"{reciprocal_rank:.4f}"
        )


    # ==============================================
    # Aggregate metrics
    # ==============================================

    mean_recall_at_5 = (
        safe_mean(
            recall_scores
        )
    )


    hit_at_5 = (
        safe_mean(
            hit_scores
        )
    )


    mrr = (
        safe_mean(
            reciprocal_ranks
        )
    )


    unauthorized_rate = (
        unauthorized_returned
        /
        total_returned

        if total_returned
        else 0.0
    )


    negative_accuracy = (
        negative_passed
        /
        negative_cases

        if negative_cases
        else 0.0
    )


    # ==============================================
    # Category metrics
    # ==============================================

    category_summary = {}


    for category, stats in (
        category_stats.items()
    ):

        category_summary[
            category
        ] = {

            "mean_recall_at_5":
                safe_mean(
                    stats[
                        "positive_recall"
                    ]
                ),

            "hit_at_5":
                safe_mean(
                    stats[
                        "positive_hit"
                    ]
                ),

            "mrr":
                safe_mean(
                    stats[
                        "positive_rr"
                    ]
                ),

            "negative_cases":
                stats[
                    "negative_cases"
                ],

            "negative_accuracy":
                (
                    stats[
                        "negative_passed"
                    ]
                    /
                    stats[
                        "negative_cases"
                    ]

                    if stats[
                        "negative_cases"
                    ]
                    else None
                )
        }


    return {

        "version":
            "retrieval_holdout_v1",

        "retriever":
            "hybrid_v5_2",

        "top_k":
            TOP_K,

        "total_cases":
            len(test_cases),

        "positive_cases":
            len(recall_scores),

        "negative_cases":
            negative_cases,

        "mean_recall_at_5":
            mean_recall_at_5,

        "hit_at_5":
            hit_at_5,

        "mrr":
            mrr,

        "unauthorized_retrieval_rate":
            unauthorized_rate,

        "negative_case_accuracy":
            negative_accuracy,

        "category_metrics":
            category_summary,

        "results":
            case_results
    }


def save_results(summary):

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
        "\n===== UNTOUCHED RETRIEVAL HOLDOUT ====="
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
        f"Positive Cases: "
        f"{summary['positive_cases']}"
    )


    print(
        f"Negative Cases: "
        f"{summary['negative_cases']}"
    )


    print(
        f"Mean Recall@5: "
        f"{summary['mean_recall_at_5']:.2%}"
    )


    print(
        f"Hit@5: "
        f"{summary['hit_at_5']:.2%}"
    )


    print(
        f"MRR: "
        f"{summary['mrr']:.4f}"
    )


    print(
        "Unauthorized Retrieval Rate: "
        f"{summary['unauthorized_retrieval_rate']:.2%}"
    )


    print(
        "Negative Case Accuracy: "
        f"{summary['negative_case_accuracy']:.2%}"
    )


    save_results(
        summary
    )


    print(
        "\nResults saved to: "
        f"{RESULT_PATH}"
    )