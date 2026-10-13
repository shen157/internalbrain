import json
from pathlib import Path

from app.data.loader import get_user

from app.retrieval.retrieval_service import (
    RetrievalService
)


TEST_CASE_PATH = Path(
    "evaluation/retrieval_test_cases.json"
)

RESULT_DIR = Path(
    "evaluation/results"
)


def load_test_cases():

    with open(
        TEST_CASE_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def evaluate_retrieval(
    method="bm25"
):

    service = RetrievalService()

    test_cases = load_test_cases()

    case_results = []

    recall_scores = []
    reciprocal_ranks = []

    total_returned = 0
    unauthorized_returned = 0

    negative_cases = 0
    negative_cases_passed = 0


    for case in test_cases:

        response = service.search(
            user_id=case["user_id"],
            query=case["query"],
            top_k=5,
            method=method
        )

        results = response["results"]

        returned_ids = [
            item["resource"]["resource_id"]
            for item in results
        ]


        # ==========================================
        # Security check
        # ==========================================

        user = get_user(
            case["user_id"]
        )

        case_unauthorized = 0

        for item in results:

            resource = item["resource"]

            total_returned += 1

            allowed = (
                service.permission_engine
                .can_access(
                    user,
                    resource
                )
            )

            if not allowed:
                unauthorized_returned += 1
                case_unauthorized += 1


        # ==========================================
        # Negative security case
        # ==========================================

        if case["expect_no_results"]:

            negative_cases += 1

            passed = (
                len(results) == 0
            )

            if passed:
                negative_cases_passed += 1

            case_results.append({
                "test_id":
                    case["test_id"],

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
                f"Negative Case | "
                f"Results: {len(results)} | "
                f"{'PASS' if passed else 'FAIL'}"
            )

            continue


        # ==========================================
        # Recall@5
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
            len(hits) / len(expected)
            if expected
            else 0
        )

        recall_scores.append(
            recall_at_5
        )


        # ==========================================
        # MRR
        # ==========================================

        first_rank = None

        for rank, resource_id in enumerate(
            returned_ids,
            start=1
        ):

            if resource_id in expected:

                first_rank = rank
                break


        reciprocal_rank = (
            1 / first_rank
            if first_rank is not None
            else 0
        )

        reciprocal_ranks.append(
            reciprocal_rank
        )


        case_results.append({
            "test_id":
                case["test_id"],

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

            "first_relevant_rank":
                first_rank,

            "reciprocal_rank":
                reciprocal_rank,

            "unauthorized_results":
                case_unauthorized
        })


        print(
            f"{case['test_id']} | "
            f"Recall@5: "
            f"{recall_at_5:.2%} | "
            f"RR: "
            f"{reciprocal_rank:.4f}"
        )


    # ==============================================
    # Aggregate Metrics
    # ==============================================

    mean_recall_at_5 = (
        sum(recall_scores)
        / len(recall_scores)

        if recall_scores
        else 0
    )


    mrr = (
        sum(reciprocal_ranks)
        / len(reciprocal_ranks)

        if reciprocal_ranks
        else 0
    )


    unauthorized_retrieval_rate = (
        unauthorized_returned
        / total_returned

        if total_returned > 0
        else 0
    )


    negative_case_accuracy = (
        negative_cases_passed
        / negative_cases

        if negative_cases > 0
        else 0
    )


    summary = {

        "retriever":
            method,

        "top_k":
            5,

        "total_cases":
            len(test_cases),

        "positive_cases":
            len(recall_scores),

        "negative_cases":
            negative_cases,

        "mean_recall_at_5":
            mean_recall_at_5,

        "mrr":
            mrr,

        "unauthorized_retrieval_rate":
            unauthorized_retrieval_rate,

        "negative_case_accuracy":
            negative_case_accuracy,

        "results":
            case_results
    }

    return summary


def save_results(summary, version="v1"):

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    retriever = summary["retriever"]

    output_path = (
        RESULT_DIR
        / f"retrieval_{retriever}_{version}.json"
    )

    with open(
        output_path,
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
        f"\nResults saved to: "
        f"{output_path}"
    )

if __name__ == "__main__":

    method = "hybrid"

    print(
        f"\n===== "
        f"{method.upper()} "
        f"Retrieval Evaluation ====="
    )

    summary = evaluate_retrieval(
        method=method
    )

    print(
        f"\nCases: "
        f"{summary['total_cases']}"
    )

    print(
        f"Mean Recall@5: "
        f"{summary['mean_recall_at_5']:.2%}"
    )

    print(
        f"MRR: "
        f"{summary['mrr']:.4f}"
    )

    print(
        f"Unauthorized Retrieval Rate: "
        f"{summary['unauthorized_retrieval_rate']:.2%}"
    )

    print(
        f"Negative Case Accuracy: "
        f"{summary['negative_case_accuracy']:.2%}"
    )

    save_results(
        summary,
        version="v5_2"
    )