from typing import Literal

from pydantic import (
    BaseModel,
    Field
)


# =========================================================
# Query
# =========================================================

class QueryRequest(
    BaseModel
):

    user_id: str

    query: str

    top_k: int = Field(
        default=5,
        ge=1,
        le=20
    )


# =========================================================
# Sync
# =========================================================

class SyncRequest(
    BaseModel
):

    mode: Literal[
        "resources",
        "permissions",
        "all"
    ] = "all"


# =========================================================
# Live Permission Demo
# =========================================================

class SlackPermissionChangeRequest(
    BaseModel
):

    actor_user_id: str = (
        "demo-admin"
    )

    target_user_id: str

    channel_id: str

    action: Literal[
        "grant",
        "revoke"
    ]

    reason: str = Field(
        default=(
            "Live permission change demo"
        ),
        max_length=200
    )