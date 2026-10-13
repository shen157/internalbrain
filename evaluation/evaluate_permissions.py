import json
from pathlib import Path

from app.data.loader import get_user

from app.connectors.registry import (
    load_all_resources,
    build_resource_index
)

from app.auth.permission_store import (
    PermissionStore
)

from app.auth.permission_engine import (
    PermissionEngine
)


TEST_CASE_PATH = Path(
    "evaluation/test_cases.json"
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


def evaluate_permissions():

    test_cases = load_test_cases()

    resources = load_all_resources()

    resource_index = (
        build_resource_index(
            resources
        )
    )

    permission_store = (
        PermissionStore()
    )

    engine = PermissionEngine(
        permission_store
    )

    results = []

    correct = 0

    true_allow = 0
    true_deny = 0

    false_allow = 0
    false_deny = 0


    for case in test_cases:

        user = get_user(
            case["user_id"]
        )

        key = (
            case["source"],
            case["resource_id"]
        )

        resource = (
            resource_index[key]
        )

        actual_access = (
            engine.can_access(
                user,
                resource
            )
        )

        expected_access = (
            case["expected_access"]
        )

        passed = (
            actual_access
            == expected_access
        )

        if passed:
            correct += 1


        if (
            expected_access
            and actual_access
        ):
            true_allow += 1

        elif (
            not expected_access
            and not actual_access
        ):
            true_deny += 1

        elif (
            not expected_access
            and actual_access
        ):
            false_allow += 1

        elif (
            expected_access
            and not actual_access
        ):
            false_deny += 1


        results.append({
            "test_id":
                case["test_id"],

            "user_id":
                case["user_id"],

            "source":
                case["source"],

            "resource_id":
                case["resource_id"],

            "expected_access":
                expected_access,

            "actual_access":
                actual_access,

            "passed":
                passed
        })


        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{case['test_id']} | "
            f"{case['user_id']} -> "
            f"{case['resource_id']} | "
            f"Expected: "
            f"{expected_access} | "
            f"Actual: "
            f"{actual_access} | "
            f"{status}"
        )


    total = len(test_cases)

    accuracy = (
        correct / total
        if total > 0
        else 0
    )


    denied_cases = (
        true_deny
        + false_allow
    )

    false_allow_rate = (
        false_allow
        / denied_cases

        if denied_cases > 0
        else 0
    )


    summary = {

        "dataset_version":
            "mock_enterprise_v1",

        "total_cases":
            total,

        "correct_cases":
            correct,

        "permission_accuracy":
            accuracy,

        "true_allow":
            true_allow,

        "true_deny":
            true_deny,

        "false_allow":
            false_allow,

        "false_deny":
            false_deny,

        "false_allow_rate":
            false_allow_rate,

        "results":
            results
    }


    return summary


def save_results(summary):

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        RESULT_DIR
        / "permission_v1_0.json"
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

    summary = (
        evaluate_permissions()
    )


    print(
        "\n===== Permission Evaluation ====="
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
        f"Permission Accuracy: "
        f"{summary['permission_accuracy']:.2%}"
    )

    print(
        f"True Allow: "
        f"{summary['true_allow']}"
    )

    print(
        f"True Deny: "
        f"{summary['true_deny']}"
    )

    print(
        f"False Allow: "
        f"{summary['false_allow']}"
    )

    print(
        f"False Deny: "
        f"{summary['false_deny']}"
    )

    print(
        f"False Allow Rate: "
        f"{summary['false_allow_rate']:.2%}"
    )


    save_results(summary)