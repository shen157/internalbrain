import json
from pathlib import Path

from app.data.loader import get_user

from app.connectors.registry import (
    get_resource
)

from app.auth.permission_store import (
    PermissionStore
)

from app.auth.permission_engine import (
    PermissionEngine
)


RESULT_DIR = Path(
    "evaluation/results"
)


def test_slack_permission_revocation():

    alice = get_user("u001")

    message = get_resource(
        "slack",
        "C-PAY:2026-09-14T09:10:00Z"
    )


    permission_store = (
        PermissionStore()
    )

    engine = PermissionEngine(
        permission_store
    )


    before_revocation = (
        engine.can_access(
            alice,
            message
        )
    )


    permission_store.remove_slack_member(
        "C-PAY",
        "u001"
    )


    after_revocation = (
        engine.can_access(
            alice,
            message
        )
    )


    passed = (
        before_revocation
        and not after_revocation
    )


    return {
        "test_id":
            "LIVE-PERM-001",

        "user_id":
            "u001",

        "channel_id":
            "C-PAY",

        "resource_id":
            message["resource_id"],

        "before_revocation":
            before_revocation,

        "after_revocation":
            after_revocation,

        "passed":
            passed
    }


def save_result(result):

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_path = (
        RESULT_DIR
        / "live_permission_v1_0.json"
    )


    with open(
        output_path,
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
        f"\nResults saved to: "
        f"{output_path}"
    )


if __name__ == "__main__":

    result = (
        test_slack_permission_revocation()
    )


    print(
        "===== Live Permission Test ====="
    )

    print(
        f"Before Revocation: "
        f"{result['before_revocation']}"
    )

    print(
        f"After Revocation: "
        f"{result['after_revocation']}"
    )

    print(
        f"Test Result: "
        f"{'PASS' if result['passed'] else 'FAIL'}"
    )


    save_result(result)