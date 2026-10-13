import json


class AuditQueryService:

    def __init__(
        self,
        audit_logger
    ):

        self.audit_logger = (
            audit_logger
        )

        self.log_path = (
            audit_logger.log_path
        )


    # =====================================================
    # Read Events
    # =====================================================

    def _load_events(
        self
    ):

        if not self.log_path.exists():
            return []


        events = []


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


                try:

                    event = json.loads(
                        line
                    )


                except json.JSONDecodeError:

                    raise ValueError(
                        "Audit log contains invalid "
                        f"JSON at line {line_number}."
                    )


                events.append(
                    event
                )


        return events


    # =====================================================
    # Search
    # =====================================================

    def search_events(
        self,
        event_type=None,
        user_id=None,
        query_id=None,
        action=None,
        resource_id=None,
        limit=50,
        newest_first=True
    ):

        if limit < 1:
            raise ValueError(
                "limit must be >= 1"
            )


        if limit > 200:
            raise ValueError(
                "limit must be <= 200"
            )


        integrity = (
            self.audit_logger
            .verify_chain()
        )


        if not integrity[
            "valid"
        ]:

            raise ValueError(
                "Audit chain integrity "
                "verification failed."
            )


        events = (
            self._load_events()
        )


        filtered = []


        for event in events:

            if (
                event_type is not None
                and
                event.get(
                    "event_type"
                )
                !=
                event_type
            ):
                continue


            if user_id is not None:

                details = (
                    event.get(
                        "details"
                    )
                    if isinstance(
                        event.get(
                            "details"
                        ),
                        dict
                    )
                    else {}
                )

                event_user_ids = {
                    event.get(
                        "user_id"
                    ),
                    event.get(
                        "actor_user_id"
                    ),
                    event.get(
                        "target_user_id"
                    ),
                    details.get(
                        "target_user_id"
                    ),
                }

                if user_id not in event_user_ids:
                    continue


            if (
                query_id is not None
                and
                event.get(
                    "query_id"
                )
                !=
                query_id
            ):
                continue


            if (
                action is not None
                and
                event.get(
                    "action"
                )
                !=
                action
            ):
                continue


            if (
                resource_id is not None
                and
                event.get(
                    "resource_id"
                )
                !=
                resource_id
            ):
                continue


            filtered.append(
                event
            )


        matched_count = (
            len(
                filtered
            )
        )


        if newest_first:

            filtered = list(
                reversed(
                    filtered
                )
            )


        returned = (
            filtered[
                :limit
            ]
        )


        return {

            "chain_valid":
                True,

            "chain_event_count":
                integrity[
                    "event_count"
                ],

            "matched_count":
                matched_count,

            "returned_count":
                len(
                    returned
                ),

            "limit":
                limit,

            "newest_first":
                newest_first,

            "filters": {

                "event_type":
                    event_type,

                "user_id":
                    user_id,

                "query_id":
                    query_id,

                "action":
                    action,

                "resource_id":
                    resource_id
            },

            "events":
                returned
        }
