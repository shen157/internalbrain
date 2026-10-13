import hashlib
import json

from copy import deepcopy
from datetime import (
    datetime,
    timezone
)

from app.connectors.registry import (
    load_all_resources
)

from app.retrieval.retrieval_service import (
    RetrievalService
)

from app.security.audit_logger import (
    AuditLogger
)


class SyncService:

    def __init__(
        self,
        retrieval_service=None,
        permission_store=None,
        resource_loader=None,
        audit_logger=None
    ):

        self.retrieval_service = (
            retrieval_service
            or RetrievalService()
        )

        self.permission_store = (
            permission_store
            or self.retrieval_service
            .permission_store
        )

        self.resource_loader = (
            resource_loader
            or load_all_resources
        )

        self.audit_logger = (
            audit_logger
            or AuditLogger()
        )

        self.last_sync_at = None

        self.fingerprints = (
            self._build_fingerprint_map(
                self.retrieval_service
                .resources
            )
        )


    # =====================================================
    # Helpers
    # =====================================================

    def _resource_key(
        self,
        resource
    ):

        return (
            resource["source"],
            resource["resource_id"]
        )


    def _resource_fingerprint(
        self,
        resource
    ):

        payload = {
            "resource_id":
                resource[
                    "resource_id"
                ],

            "source":
                resource[
                    "source"
                ],

            "resource_type":
                resource[
                    "resource_type"
                ],

            "title":
                resource[
                    "title"
                ],

            "content":
                resource[
                    "content"
                ],

            "updated_at":
                resource[
                    "updated_at"
                ],

            "source_url":
                resource.get(
                    "source_url"
                ),

            "metadata":
                resource.get(
                    "metadata",
                    {}
                )
        }


        canonical = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            default=str
        )


        return hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        ).hexdigest()


    def _build_fingerprint_map(
        self,
        resources
    ):

        return {
            self._resource_key(
                resource
            ):
            self._resource_fingerprint(
                resource
            )

            for resource
            in resources
        }


    def _parse_timestamp(
        self,
        value
    ):

        if not value:
            return None


        try:

            timestamp = (
                datetime.fromisoformat(
                    value.replace(
                        "Z",
                        "+00:00"
                    )
                )
            )


            if (
                timestamp.tzinfo
                is None
            ):

                timestamp = (
                    timestamp.replace(
                        tzinfo=timezone.utc
                    )
                )


            return timestamp


        except (
            ValueError,
            AttributeError
        ):

            return None


    # =====================================================
    # Resource Sync
    # =====================================================

    def sync_resources(self):

        sync_started = (
            datetime.now(
                timezone.utc
            )
        )


        # Load latest source state
        latest_resources = (
            self.resource_loader()
        )


        latest_resources = deepcopy(
            latest_resources
        )


        new_fingerprints = (
            self._build_fingerprint_map(
                latest_resources
            )
        )


        old_keys = set(
            self.fingerprints.keys()
        )

        new_keys = set(
            new_fingerprints.keys()
        )


        added_keys = (
            new_keys
            - old_keys
        )

        removed_keys = (
            old_keys
            - new_keys
        )


        common_keys = (
            old_keys
            & new_keys
        )


        updated_keys = {
            key
            for key
            in common_keys
            if (
                self.fingerprints[key]
                !=
                new_fingerprints[key]
            )
        }


        sync_completed = (
            datetime.now(
                timezone.utc
            )
        )


        indexed_at = (
            sync_completed.isoformat()
        )


        # Add sync metadata
        for resource in latest_resources:

            metadata = (
                resource.setdefault(
                    "metadata",
                    {}
                )
            )

            metadata[
                "indexed_at"
            ] = indexed_at


        # Replace current retrieval state
        self.retrieval_service.replace_resources(
            latest_resources
        )


        # Save fingerprints WITHOUT indexed_at
        self.fingerprints = (
            new_fingerprints
        )


        self.last_sync_at = (
            indexed_at
        )


        # ==========================================
        # Freshness latency for changed resources
        # ==========================================

        freshness_latencies_ms = []


        changed_keys = (
            added_keys
            | updated_keys
        )


        for resource in latest_resources:

            key = self._resource_key(
                resource
            )


            if key not in changed_keys:
                continue


            source_updated_at = (
                self._parse_timestamp(
                    resource.get(
                        "updated_at"
                    )
                )
            )


            if source_updated_at is None:
                continue


            latency_seconds = (
                sync_completed
                -
                source_updated_at
            ).total_seconds()


            # Clock skew / future timestamps
            if latency_seconds < 0:
                continue


            freshness_latencies_ms.append(
                latency_seconds
                * 1000
            )


        sync_duration_ms = (
            (
                sync_completed
                -
                sync_started
            ).total_seconds()
            * 1000
        )


        result = {

            "sync_started_at":
                sync_started.isoformat(),

            "sync_completed_at":
                indexed_at,

            "sync_duration_ms":
                sync_duration_ms,

            "total_resources":
                len(
                    latest_resources
                ),

            "added_count":
                len(
                    added_keys
                ),

            "updated_count":
                len(
                    updated_keys
                ),

            "removed_count":
                len(
                    removed_keys
                ),

            "added_resources":
                sorted(
                    [
                        f"{source}:{resource_id}"
                        for source, resource_id
                        in added_keys
                    ]
                ),

            "updated_resources":
                sorted(
                    [
                        f"{source}:{resource_id}"
                        for source, resource_id
                        in updated_keys
                    ]
                ),

            "removed_resources":
                sorted(
                    [
                        f"{source}:{resource_id}"
                        for source, resource_id
                        in removed_keys
                    ]
                ),

            "max_freshness_latency_ms":
                (
                    max(
                        freshness_latencies_ms
                    )
                    if freshness_latencies_ms
                    else None
                ),

            "mean_freshness_latency_ms":
                (
                    sum(
                        freshness_latencies_ms
                    )
                    /
                    len(
                        freshness_latencies_ms
                    )
                    if freshness_latencies_ms
                    else None
                )
        }


        # ==========================================
        # Audit
        # ==========================================

        self.audit_logger.log_event(
            event_type="resource_sync",
            user_id="system",
            action="sync_resources",

            details={
                "total_resources":
                    result[
                        "total_resources"
                    ],

                "added_count":
                    result[
                        "added_count"
                    ],

                "updated_count":
                    result[
                        "updated_count"
                    ],

                "removed_count":
                    result[
                        "removed_count"
                    ],

                "sync_duration_ms":
                    result[
                        "sync_duration_ms"
                    ]
            }
        )


        return result


    # =====================================================
    # Permission Sync
    # =====================================================

    def sync_permissions(self):

        started = (
            datetime.now(
                timezone.utc
            )
        )


        self.permission_store.reload()


        completed = (
            datetime.now(
                timezone.utc
            )
        )


        duration_ms = (
            (
                completed
                -
                started
            ).total_seconds()
            * 1000
        )


        result = {

            "sync_completed_at":
                completed.isoformat(),

            "sync_duration_ms":
                duration_ms,

            "status":
                "success"
        }


        self.audit_logger.log_event(
            event_type="permission_sync",
            user_id="system",
            action="sync_permissions",

            details=result
        )


        return result


    # =====================================================
    # Full Sync
    # =====================================================

    def sync_all(self):

        resource_result = (
            self.sync_resources()
        )

        permission_result = (
            self.sync_permissions()
        )


        return {
            "resources":
                resource_result,

            "permissions":
                permission_result
        }