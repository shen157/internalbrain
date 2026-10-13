import json
from pathlib import Path

from app.auth.permission_engine import (
    PermissionEngine
)

from app.auth.permission_store import (
    PermissionStore
)

from app.data.loader import (
    load_users,
    load_confluence_pages,
    load_jira_issues,
    load_slack_channels,
    load_gdrive_files,
    load_gdrive_folders,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


CASE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "permission_test_cases.json"
)


RESULT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "permission_final_v1.json"
)


def index_by(
    items,
    key
):

    return {
        item[key]: item
        for item in items
    }


def load_resource_indexes():

    return {

        "confluence":
            index_by(
                load_confluence_pages(),
                "id"
            ),

        "jira":
            index_by(
                load_jira_issues(),
                "key"
            ),

        "slack":
            index_by(
                load_slack_channels(),
                "id"
            ),

        "gdrive_files":
            index_by(
                load_gdrive_files(),
                "id"
            ),

        "gdrive_folders":
            index_by(
                load_gdrive_folders(),
                "id"
            ),
    }


def get_resource(
    case,
    indexes
):

    platform = (
        case[
            "platform"
        ]
    )

    resource_id = (
        case[
            "resource_id"
        ]
    )


    if platform == "confluence":

        return (
            indexes[
                "confluence"
            ][
                resource_id
            ]
        )


    if platform == "jira":

        return (
            indexes[
                "jira"
            ][
                resource_id
            ]
        )


    if platform == "slack":

        return (
            indexes[
                "slack"
            ][
                resource_id
            ]
        )


    if platform == "gdrive":

        return (
            indexes[
                "gdrive_files"
            ].get(
                resource_id
            )
            or
            indexes[
                "gdrive_folders"
            ].get(
                resource_id
            )
        )


    raise ValueError(
        f"Unknown platform: "
        f"{platform}"
    )


def evaluate_permission_final():

    with open(
        CASE_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        suite = (
            json.load(f)
        )


    users = (
        index_by(
            load_users(),
            "user_id"
        )
    )


    indexes = (
        load_resource_indexes()
    )


    store = (
        PermissionStore()
    )


    engine = (
        PermissionEngine(
            store
        )
    )


    results = []


    true_allow = 0
    true_deny = 0

    false_allow = 0
    false_deny = 0


    for case in suite[
        "cases"
    ]:

        user = (
            users[
                case[
                    "user_id"
                ]
            ]
        )


        resource = (
            get_resource(
                case,
                indexes
            )
        )


        if resource is None:

            raise KeyError(
                "Resource not found: "
                f"{case['resource_id']}"
            )


        actual_allowed = (
            engine.can_access(
                user=user,
                resource=resource,
                source=
                    case[
                        "platform"
                    ]
            )
        )


        expected_allowed = (
            case[
                "expected"
            ]
            ==
            "ALLOW"
        )


        passed = (
            actual_allowed
            ==
            expected_allowed
        )


        # ==========================================
        # Confusion Matrix
        # ==========================================

        if (
            expected_allowed
            and
            actual_allowed
        ):
            true_allow += 1


        elif (
            not expected_allowed
            and
            not actual_allowed
        ):
            true_deny += 1


        elif (
            not expected_allowed
            and
            actual_allowed
        ):
            false_allow += 1


        else:
            false_deny += 1


        results.append({

            "id":
                case[
                    "id"
                ],

            "platform":
                case[
                    "platform"
                ],

            "resource_id":
                case[
                    "resource_id"
                ],

            "user_id":
                case[
                    "user_id"
                ],

            "feature":
                case.get(
                    "feature"
                ),

            "expected":
                case[
                    "expected"
                ],

            "actual":
                (
                    "ALLOW"
                    if actual_allowed
                    else "DENY"
                ),

            "passed":
                passed,
        })


    total = len(
        results
    )


    passed_count = sum(
        1
        for result
        in results
        if result[
            "passed"
        ]
    )


    deny_cases = (
        true_deny
        +
        false_allow
    )


    false_allow_rate = (
        false_allow
        /
        deny_cases

        if deny_cases
        else 0.0
    )


    summary = {

        "version":
            "permission_final_v1",

        "suite":
            suite.get(
                "suite"
            ),

        "total_cases":
            total,

        "passed_cases":
            passed_count,

        "permission_accuracy":
            (
                passed_count
                /
                total

                if total
                else 0.0
            ),

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
            results,
    }


    return summary


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

    summary = (
        evaluate_permission_final()
    )


    print(
        "===== Final Permission Evaluation ====="
    )


    for result in (
        summary[
            "results"
        ]
    ):

        print(
            f"{result['id']} | "
            f"{result['platform']} | "
            f"{'PASS' if result['passed'] else 'FAIL'} | "
            f"expected={result['expected']} | "
            f"actual={result['actual']}"
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
        "Permission Accuracy: "
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
        "False Allow Rate: "
        f"{summary['false_allow_rate']:.2%}"
    )


    save_results(
        summary
    )


    print(
        "\nResults saved to: "
        f"{RESULT_PATH}"
    )