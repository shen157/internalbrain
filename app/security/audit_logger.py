import hashlib
import json
import uuid

from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]


DEFAULT_AUDIT_PATH = (
    PROJECT_ROOT
    / "data"
    / "audit"
    / "audit_log.jsonl"
)


GENESIS_HASH = "GENESIS"


class AuditLogger:

    def __init__(
        self,
        log_path=None
    ):

        self.log_path = (
            Path(log_path)
            if log_path
            else DEFAULT_AUDIT_PATH
        )

        self.log_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )


    # =====================================================
    # Hash Helpers
    # =====================================================

    def _canonical_json(
        self,
        data
    ):

        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False
        )


    def _calculate_hash(
        self,
        event
    ):

        canonical = (
            self._canonical_json(
                event
            )
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()


    def _get_last_hash(self):

        if not self.log_path.exists():
            return GENESIS_HASH

        last_line = None

        with open(
            self.log_path,
            "r",
            encoding="utf-8"
        ) as f:

            for line in f:

                if line.strip():
                    last_line = line


        if last_line is None:
            return GENESIS_HASH


        try:

            event = json.loads(
                last_line
            )

            return event[
                "current_hash"
            ]

        except (
            json.JSONDecodeError,
            KeyError
        ):

            raise ValueError(
                "Audit log is malformed. "
                "Cannot safely append new events."
            )


    # =====================================================
    # Write Event
    # =====================================================

    def log_event(
        self,
        event_type,
        user_id=None,
        query_id=None,
        action=None,
        resource_id=None,
        auth_decision=None,
        details=None
    ):

        previous_hash = (
            self._get_last_hash()
        )


        event = {

            "event_id":
                str(uuid.uuid4()),

            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "query_id":
                query_id,

            "user_id":
                user_id,

            "event_type":
                event_type,

            "action":
                action,

            "resource_id":
                resource_id,

            "auth_decision":
                auth_decision,

            "details":
                details or {},

            "previous_hash":
                previous_hash
        }


        current_hash = (
            self._calculate_hash(
                event
            )
        )


        event["current_hash"] = (
            current_hash
        )


        with open(
            self.log_path,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                json.dumps(
                    event,
                    ensure_ascii=False
                )
                + "\n"
            )


        return event


    # =====================================================
    # Verify Hash Chain
    # =====================================================

    def verify_chain(self):

        if not self.log_path.exists():

            return {
                "valid":
                    True,

                "event_count":
                    0,

                "broken_line":
                    None,

                "reason":
                    None
            }


        expected_previous_hash = (
            GENESIS_HASH
        )

        event_count = 0


        with open(
            self.log_path,
            "r",
            encoding="utf-8"
        ) as f:

            for line_number, line in enumerate(
                f,
                start=1
            ):

                if not line.strip():
                    continue


                # ---------------------------------
                # JSON validity
                # ---------------------------------

                try:

                    event = json.loads(
                        line
                    )

                except json.JSONDecodeError:

                    return {
                        "valid":
                            False,

                        "event_count":
                            event_count,

                        "broken_line":
                            line_number,

                        "reason":
                            "invalid_json"
                    }


                event_count += 1


                # ---------------------------------
                # Chain continuity
                # ---------------------------------

                if (
                    event.get(
                        "previous_hash"
                    )
                    !=
                    expected_previous_hash
                ):

                    return {
                        "valid":
                            False,

                        "event_count":
                            event_count,

                        "broken_line":
                            line_number,

                        "event_id":
                            event.get(
                                "event_id"
                            ),

                        "reason":
                            "previous_hash_mismatch"
                    }


                # ---------------------------------
                # Recalculate current hash
                # ---------------------------------

                stored_hash = (
                    event.get(
                        "current_hash"
                    )
                )


                event_without_hash = (
                    event.copy()
                )

                event_without_hash.pop(
                    "current_hash",
                    None
                )


                recalculated_hash = (
                    self._calculate_hash(
                        event_without_hash
                    )
                )


                if (
                    stored_hash
                    != recalculated_hash
                ):

                    return {
                        "valid":
                            False,

                        "event_count":
                            event_count,

                        "broken_line":
                            line_number,

                        "event_id":
                            event.get(
                                "event_id"
                            ),

                        "reason":
                            "current_hash_mismatch"
                    }


                expected_previous_hash = (
                    stored_hash
                )


        return {
            "valid":
                True,

            "event_count":
                event_count,

            "broken_line":
                None,

            "reason":
                None
        }