import json
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


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[1]
)


RESULT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "results"
    / "live_permission_change_v1.json"
)


TARGET_USER = (
    "u004"
)

CHANNEL_ID = (
    "C-PAY"
)

TARGET_RESOURCE_ID = (
    "C-PAY:2026-09-24T14:05:00Z"
)

QUERY = (
    "dual-write rollback surface "
    "one-way backfill PAY-104"
)


client = (
    TestClient(
        app
    )
)


def change_permission(
    action
):

    started = (
        time.perf_counter()
    )


    response = (
        client.post(

            "/demo/permissions/"
            "slack/membership",

            json={

                "actor_user_id":
                    "u005",

                "target_user_id":
                    TARGET_USER,

                "channel_id":
                    CHANNEL_ID,

                "action":
                    action,

                "reason":
                    (
                        "Automated live "
                        "permission-change test"
                    )
            },

            headers={
                "X-InternalBrain-Actor": "u005"
            }
        )
    )


    duration_ms = (
        (
            time.perf_counter()
            -
            started
        )
        *
        1000
    )


    response.raise_for_status()


    return (
        response.json(),
        duration_ms
    )


def get_permission_status():

    response = (
        client.get(

            f"/demo/permissions/"
            f"slack/{CHANNEL_ID}/"
            f"users/{TARGET_USER}",

            headers={
                "X-InternalBrain-Actor": "u005"
            }
        )
    )


    response.raise_for_status()


    return (
        response.json()
    )


def search():

    response = (
        retrieval_service
        .search(

            user_id=
                TARGET_USER,

            query=
                QUERY,

            top_k=
                10,

            method=
                "hybrid"
        )
    )


    result_ids = [

        item[
            "resource"
        ][
            "resource_id"
        ]

        for item
        in response[
            "results"
        ]
    ]


    return (
        response,
        result_ids
    )


def save_result(
    result
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
            result,
            f,
            indent=2,
            ensure_ascii=False
        )


if __name__ == "__main__":

    print(
        "\n===== LIVE PERMISSION CHANGE TEST ====="
    )


    resource_count_before = (
        retrieval_service
        .resource_count()
    )


    # =====================================================
    # 0. Reset to baseline
    # =====================================================

    change_permission(
        "revoke"
    )


    # =====================================================
    # 1. BEFORE
    # =====================================================

    before_status = (
        get_permission_status()
    )


    before_search, before_ids = (
        search()
    )


    before_has_target = (
        TARGET_RESOURCE_ID
        in before_ids
    )


    print(
        "\n--- BEFORE GRANT ---"
    )

    print(
        "Member:",
        before_status[
            "is_member"
        ]
    )

    print(
        "Access:",
        before_status[
            "access_allowed"
        ]
    )

    print(
        "Target returned:",
        before_has_target
    )

    print(
        "Results:",
        before_ids
    )


    # =====================================================
    # 2. GRANT
    # =====================================================

    grant_result, grant_latency_ms = (
        change_permission(
            "grant"
        )
    )


    # =====================================================
    # 3. AFTER
    # =====================================================

    after_status = (
        get_permission_status()
    )


    after_search, after_ids = (
        search()
    )


    after_has_target = (
        TARGET_RESOURCE_ID
        in after_ids
    )


    resource_count_after = (
        retrieval_service
        .resource_count()
    )


    print(
        "\n--- AFTER GRANT ---"
    )

    print(
        "Member:",
        after_status[
            "is_member"
        ]
    )

    print(
        "Access:",
        after_status[
            "access_allowed"
        ]
    )

    print(
        "Target returned:",
        after_has_target
    )

    print(
        "Results:",
        after_ids
    )


    # =====================================================
    # 4. Audit Integrity
    # =====================================================

    audit_response = (
        client.get(
            "/audit/verify"
        )
    )


    audit_response.raise_for_status()

    audit_result = (
        audit_response.json()
    )


    # =====================================================
    # 5. Assertions
    # =====================================================

    checks = {

        "denied_before_grant":
            (
                before_status[
                    "access_allowed"
                ]
                is False
            ),

        "target_absent_before":
            (
                before_has_target
                is False
            ),

        "allowed_after_grant":
            (
                after_status[
                    "access_allowed"
                ]
                is True
            ),

        "target_present_after":
            (
                after_has_target
                is True
            ),

        "resource_count_unchanged":
            (
                resource_count_before
                ==
                resource_count_after
            ),

        "reindex_not_required":
            (
                grant_result[
                    "reindex_required"
                ]
                is False
            ),

        "audit_chain_valid":
            (
                audit_result[
                    "valid"
                ]
                is True
            )
    }


    passed = all(
        checks.values()
    )


    result = {

        "version":
            "live_permission_change_v1",

        "user_id":
            TARGET_USER,

        "channel_id":
            CHANNEL_ID,

        "target_resource_id":
            TARGET_RESOURCE_ID,

        "query":
            QUERY,

        "before": {
            "permission":
                before_status,

            "returned_ids":
                before_ids,

            "target_returned":
                before_has_target
        },

        "grant": {
            "response":
                grant_result,

            "api_latency_ms":
                grant_latency_ms
        },

        "after": {
            "permission":
                after_status,

            "returned_ids":
                after_ids,

            "target_returned":
                after_has_target
        },

        "resource_count_before":
            resource_count_before,

        "resource_count_after":
            resource_count_after,

        "audit":
            audit_result,

        "checks":
            checks,

        "passed":
            passed
    }


    save_result(
        result
    )


    print(
        "\n===== CHECKS ====="
    )


    for name, value in (
        checks.items()
    ):

        print(
            f"{name}: "
            f"{'PASS' if value else 'FAIL'}"
        )


    print(
        "\nGrant API latency: "
        f"{grant_latency_ms:.3f} ms"
    )


    print(
        "Overall: "
        f"{'PASS' if passed else 'FAIL'}"
    )


    print(
        "\nResults saved to: "
        f"{RESULT_PATH}"
    )


    # =====================================================
    # 6. Restore baseline
    # =====================================================

    change_permission(
        "revoke"
    )
