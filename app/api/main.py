from typing import Optional

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Query
)

from app.api.schemas import (
    QueryRequest,
    SyncRequest,
    SlackPermissionChangeRequest
)

from app.api.services import (
    answer_service,
    retrieval_service,
    sync_service,
    audit_logger
)

from app.data.loader import (
    get_user
)

from app.security.audit_query_service import (
    AuditQueryService
)


app = FastAPI(

    title=
        "InternalBrain API",

    description=(
        "Permission-aware enterprise "
        "knowledge assistant API"
    ),

    version=
        "1.0.0"
)


audit_query_service = (
    AuditQueryService(
        audit_logger
    )
)


REVIEWER_ROLES = {
    "compliance_officer"
}


def require_reviewer(
    actor_user_id:
        Optional[str]
):
    """Authorize demo administration endpoints by the acting user's role."""

    if not actor_user_id:

        raise HTTPException(
            status_code=403,
            detail=(
                "Reviewer authorization is required."
            )
        )


    try:

        actor = get_user(
            actor_user_id
        )

    except KeyError:

        raise HTTPException(
            status_code=403,
            detail=(
                "Reviewer authorization failed."
            )
        )


    if actor.get("role") not in REVIEWER_ROLES:

        raise HTTPException(
            status_code=403,
            detail=(
                "This endpoint is restricted to "
                "reviewers and compliance officers."
            )
        )


    return actor


# =========================================================
# Health
# =========================================================

@app.get(
    "/health"
)
def health():

    return {

        "status":
            "ok",

        "service":
            "InternalBrain",

        "version":
            "1.0.0",

        "resource_count":
            retrieval_service
            .resource_count()
    }


# =========================================================
# Query
# =========================================================

@app.post(
    "/query"
)
def query(
    request:
        QueryRequest
):

    try:

        return (
            answer_service.answer(

                user_id=
                    request.user_id,

                query=
                    request.query,

                top_k=
                    request.top_k
            )
        )


    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(
                error
            )
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "InternalBrain query failed: "
                f"{str(error)}"
            )
        )


# =========================================================
# Sync
# =========================================================

@app.post(
    "/sync"
)
def sync(
    request:
        SyncRequest,

    x_internalbrain_actor:
        Optional[str]
        =
        Header(
            default=None,
            alias="X-InternalBrain-Actor"
        )
):

    require_reviewer(
        x_internalbrain_actor
    )

    try:

        if (
            request.mode
            ==
            "resources"
        ):

            return (
                sync_service
                .sync_resources()
            )


        if (
            request.mode
            ==
            "permissions"
        ):

            return (
                sync_service
                .sync_permissions()
            )


        return (
            sync_service
            .sync_all()
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Sync failed: "
                f"{str(error)}"
            )
        )


# =========================================================
# Permission Reload
# =========================================================

@app.post(
    "/permissions/reload"
)
def reload_permissions(
    x_internalbrain_actor:
        Optional[str]
        =
        Header(
            default=None,
            alias="X-InternalBrain-Actor"
        )
):

    require_reviewer(
        x_internalbrain_actor
    )

    try:

        return (
            sync_service
            .sync_permissions()
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Permission reload failed: "
                f"{str(error)}"
            )
        )


# =========================================================
# Demo Permission Status
# =========================================================

@app.get(
    "/demo/permissions/slack/"
    "{channel_id}/users/{user_id}"
)
def slack_permission_status(
    channel_id: str,
    user_id: str,
    x_internalbrain_actor:
        Optional[str]
        =
        Header(
            default=None,
            alias="X-InternalBrain-Actor"
        )
):

    require_reviewer(
        x_internalbrain_actor
    )

    store = (
        retrieval_service
        .permission_store
    )


    try:

        get_user(
            user_id
        )

    except KeyError:

        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown user: "
                f"{user_id}"
            )
        )


    channel = (
        store
        .get_slack_channel(
            channel_id
        )
    )


    if channel is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Unknown Slack channel: "
                f"{channel_id}"
            )
        )


    members = (
        store
        .get_slack_members(
            channel_id
        )
    )


    is_member = (
        user_id
        in members
    )


    is_private = (
        channel.get(
            "is_private",
            False
        )
    )


    access_allowed = (
        True
        if not is_private
        else is_member
    )


    return {

        "channel_id":
            channel_id,

        "channel_name":
            channel.get(
                "name"
            ),

        "is_private":
            is_private,

        "user_id":
            user_id,

        "is_member":
            is_member,

        "access_allowed":
            access_allowed,

        "permission_source":
            "query_time_permission_store"
    }


# =========================================================
# Demo Permission Mutation
# =========================================================

@app.post(
    "/demo/permissions/slack/membership"
)
def change_slack_membership(
    request:
        SlackPermissionChangeRequest,

    x_internalbrain_actor:
        Optional[str]
        =
        Header(
            default=None,
            alias="X-InternalBrain-Actor"
        )
):

    require_reviewer(
        x_internalbrain_actor
    )


    if request.actor_user_id != x_internalbrain_actor:

        raise HTTPException(
            status_code=403,
            detail=(
                "The permission-change actor must match "
                "the authorized reviewer."
            )
        )

    store = (
        retrieval_service
        .permission_store
    )


    try:

        get_user(
            request.target_user_id
        )

    except KeyError:

        raise HTTPException(
            status_code=404,
            detail=(
                "Unknown target user: "
                f"{request.target_user_id}"
            )
        )


    channel = (
        store
        .get_slack_channel(
            request.channel_id
        )
    )


    if channel is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "Unknown Slack channel: "
                f"{request.channel_id}"
            )
        )


    if not channel.get(
        "is_private",
        False
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Slack membership mutation demo "
                "requires a private channel."
            )
        )


    members_before = list(
        store.get_slack_members(
            request.channel_id
        )
    )


    before_member = (
        request.target_user_id
        in members_before
    )


    if (
        request.action
        ==
        "grant"
    ):

        store.add_slack_member(

            channel_id=
                request.channel_id,

            user_id=
                request.target_user_id
        )


    elif (
        request.action
        ==
        "revoke"
    ):

        store.remove_slack_member(

            channel_id=
                request.channel_id,

            user_id=
                request.target_user_id
        )


    members_after = list(
        store.get_slack_members(
            request.channel_id
        )
    )


    after_member = (
        request.target_user_id
        in members_after
    )


    changed = (
        before_member
        !=
        after_member
    )


    audit_event = (
        audit_logger.log_event(

            event_type=
                "permission_change",

            user_id=
                request.actor_user_id,

            action=(
                f"{request.action}_"
                f"slack_membership"
            ),

            resource_id=
                request.channel_id,

            auth_decision=(
                "granted"
                if after_member
                else "revoked"
            ),

            details={

                "target_user_id":
                    request.target_user_id,

                "channel_id":
                    request.channel_id,

                "channel_name":
                    channel.get(
                        "name"
                    ),

                "before_member":
                    before_member,

                "after_member":
                    after_member,

                "changed":
                    changed,

                "reason":
                    request.reason,

                "query_time_enforced":
                    True,

                "reindex_required":
                    False,

                "persistence":
                    (
                        "in_memory_until_"
                        "reload_or_restart"
                    )
            }
        )
    )


    return {

        "status":
            "success",

        "action":
            request.action,

        "actor_user_id":
            request.actor_user_id,

        "target_user_id":
            request.target_user_id,

        "channel_id":
            request.channel_id,

        "channel_name":
            channel.get(
                "name"
            ),

        "is_private":
            True,

        "before_member":
            before_member,

        "after_member":
            after_member,

        "access_allowed":
            after_member,

        "changed":
            changed,

        "query_time_enforced":
            True,

        "reindex_required":
            False,

        "persistence":
            (
                "in_memory_until_"
                "reload_or_restart"
            ),

        "audit_event_id":
            audit_event[
                "event_id"
            ]
    }


# =========================================================
# Audit Verification
# =========================================================

@app.get(
    "/audit/verify"
)
def verify_audit():

    try:

        return (
            audit_logger
            .verify_chain()
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Audit verification failed: "
                f"{str(error)}"
            )
        )


# =========================================================
# Audit Inquiry
#
# Demo/admin endpoint protected by the acting user's reviewer role.
# Production deployments should replace the demo identity header with
# authenticated SSO/session claims.
# =========================================================

@app.get(
    "/audit/events"
)
def search_audit_events(

    event_type:
        Optional[str]
        =
        None,

    user_id:
        Optional[str]
        =
        None,

    query_id:
        Optional[str]
        =
        None,

    action:
        Optional[str]
        =
        None,

    resource_id:
        Optional[str]
        =
        None,

    limit:
        int
        =
        Query(
            default=50,
            ge=1,
            le=200
        ),

    newest_first:
        bool
        =
        True,

    x_internalbrain_actor:
        Optional[str]
        =
        Header(
            default=None,
            alias="X-InternalBrain-Actor"
        )
):

    require_reviewer(
        x_internalbrain_actor
    )

    try:

        return (
            audit_query_service
            .search_events(

                event_type=
                    event_type,

                user_id=
                    user_id,

                query_id=
                    query_id,

                action=
                    action,

                resource_id=
                    resource_id,

                limit=
                    limit,

                newest_first=
                    newest_first
            )
        )


    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(
                error
            )
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Audit inquiry failed: "
                f"{str(error)}"
            )
        )
