import json

from copy import deepcopy
from datetime import (
    datetime,
    timezone
)

from pathlib import Path

from app.connectors.registry import (
    load_all_resources
)

from app.retrieval.retrieval_service import (
    RetrievalService
)

from app.sync.sync_service import (
    SyncService
)

from app.security.audit_logger import (
    AuditLogger
)


RESULT_DIR = Path(
    "evaluation/results"
)


TEST_AUDIT_LOG = (
    RESULT_DIR
    / "freshness_test_audit.jsonl"
)


TARGET_RESOURCE = (
    "GDRIVE-PAY-001"
)


MARKER = (
    "novafreeze-271"
)


QUERY = (
    MARKER
)


def evaluate_freshness():

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    if TEST_AUDIT_LOG.exists():

        TEST_AUDIT_LOG.unlink()


    # =====================================================
    # Initial source state
    # =====================================================

    base_resources = (
        load_all_resources()
    )


    source_state = {
        "resources":
            deepcopy(
                base_resources
            )
    }


    # This simulates reading
    # the latest external source.
    def mock_resource_loader():

        return deepcopy(
            source_state[
                "resources"
            ]
        )


    retrieval_service = (
        RetrievalService(
            resources=deepcopy(
                base_resources
            )
        )
    )


    audit_logger = (
        AuditLogger(
            TEST_AUDIT_LOG
        )
    )


    sync_service = (
        SyncService(
            retrieval_service=
                retrieval_service,

            permission_store=
                retrieval_service
                .permission_store,

            resource_loader=
                mock_resource_loader,

            audit_logger=
                audit_logger
        )
    )


    # =====================================================
    # 1. Before source update
    # =====================================================

    before = (
        retrieval_service.search(
            user_id="u001",
            query=QUERY,
            top_k=5,
            method="hybrid"
        )
    )


    before_ids = [
        item["resource"][
            "resource_id"
        ]
        for item
        in before["results"]
    ]


    before_found = (
        TARGET_RESOURCE
        in before_ids
    )


    # =====================================================
    # 2. Simulate external source update
    # =====================================================

    update_time = (
        datetime.now(
            timezone.utc
        )
    )


    for resource in (
        source_state[
            "resources"
        ]
    ):

        if (
            resource[
                "resource_id"
            ]
            ==
            TARGET_RESOURCE
        ):

            resource[
                "content"
            ] += (
                "\nFreshness test marker: "
                f"{MARKER}."
            )


            resource[
                "updated_at"
            ] = (
                update_time
                .isoformat()
            )


            break


    # =====================================================
    # 3. Execute Sync
    # =====================================================

    sync_result = (
        sync_service
        .sync_resources()
    )


    # =====================================================
    # 4. Search Again
    # =====================================================

    after = (
        retrieval_service.search(
            user_id="u001",
            query=QUERY,
            top_k=5,
            method="hybrid"
        )
    )


    after_ids = [
        item["resource"][
            "resource_id"
        ]
        for item
        in after["results"]
    ]


    after_found = (
        TARGET_RESOURCE
        in after_ids
    )


    # =====================================================
    # 5. Check indexed_at
    # =====================================================

    indexed_at_present = False


    for resource in (
        retrieval_service
        .resources
    ):

        if (
            resource[
                "resource_id"
            ]
            ==
            TARGET_RESOURCE
        ):

            indexed_at_present = (
                "indexed_at"
                in resource[
                    "metadata"
                ]
            )

            break


    # =====================================================
    # Results
    # =====================================================

    update_detected = (
        (
            "gdrive:"
            + TARGET_RESOURCE
        )
        in sync_result[
            "updated_resources"
        ]
    )


    retrieval_refresh_pass = (
        not before_found
        and after_found
    )


    passed = (
        update_detected
        and retrieval_refresh_pass
        and indexed_at_present
    )


    return {

        "version":
            "freshness_v1",

        "target_resource":
            TARGET_RESOURCE,

        "marker":
            MARKER,

        "before_found":
            before_found,

        "after_found":
            after_found,

        "update_detected":
            update_detected,

        "indexed_at_present":
            indexed_at_present,

        "retrieval_refresh_pass":
            retrieval_refresh_pass,

        "sync_duration_ms":
            sync_result[
                "sync_duration_ms"
            ],

        "freshness_latency_ms":
            sync_result[
                "max_freshness_latency_ms"
            ],

        "updated_resources":
            sync_result[
                "updated_resources"
            ],

        "passed":
            passed
    }


def save_results(
    summary
):

    output_path = (
        RESULT_DIR
        / "freshness_v1.json"
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
        evaluate_freshness()
    )


    print(
        "===== Freshness Evaluation ====="
    )


    print(
        f"Before Update Found: "
        f"{summary['before_found']}"
    )

    print(
        f"Update Detected: "
        f"{summary['update_detected']}"
    )

    print(
        f"After Sync Found: "
        f"{summary['after_found']}"
    )

    print(
        f"indexed_at Present: "
        f"{summary['indexed_at_present']}"
    )

    print(
        f"Sync Duration: "
        f"{summary['sync_duration_ms']:.2f} ms"
    )


    freshness = (
        summary[
            "freshness_latency_ms"
        ]
    )


    if freshness is not None:

        print(
            f"Freshness Latency: "
            f"{freshness:.2f} ms"
        )


    print(
        f"Test Result: "
        f"{'PASS' if summary['passed'] else 'FAIL'}"
    )


    save_results(
        summary
    )