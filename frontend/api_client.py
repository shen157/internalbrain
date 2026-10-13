"""HTTP client for the InternalBrain FastAPI backend.

The Streamlit UI must communicate with the backend exclusively through
these HTTP calls. No backend logic is duplicated here.
"""

import os
from urllib.parse import quote

import requests

DEFAULT_BASE_URL = "http://127.0.0.1:8000"

# Long timeout for /query: it includes retrieval + LLM generation.
QUERY_TIMEOUT = 120
SHORT_TIMEOUT = 15


class InternalBrainAPIError(Exception):
    """User-friendly error raised when the backend is unreachable or fails."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class InternalBrainAPIClient:
    """Small wrapper around the InternalBrain REST API."""

    def __init__(self, base_url=None):
        configured = base_url or os.environ.get("INTERNALBRAIN_API_URL") or DEFAULT_BASE_URL
        self.base_url = configured.rstrip("/")

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def _request(
        self,
        method,
        path,
        json_body=None,
        params=None,
        headers=None,
        timeout=SHORT_TIMEOUT,
    ):
        url = f"{self.base_url}{path}"
        try:
            request_args = {
                "json": json_body,
                "params": params,
                "timeout": timeout,
            }
            if headers:
                request_args["headers"] = headers
            response = requests.request(method, url, **request_args)
        except requests.exceptions.ConnectionError:
            raise InternalBrainAPIError(
                f"Cannot reach the InternalBrain backend at {self.base_url}. "
                "Is FastAPI running? (python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000)"
            )
        except requests.exceptions.Timeout:
            raise InternalBrainAPIError(
                "The InternalBrain backend did not respond in time. "
                "The LLM may still be processing — please try again."
            )
        except requests.exceptions.RequestException as exc:
            raise InternalBrainAPIError(f"Network error while contacting the backend: {exc}")

        if response.status_code >= 400:
            detail = ""
            try:
                payload = response.json()
                detail = payload.get("detail") or payload.get("message") or ""
            except Exception:
                detail = (response.text or "")[:200]
            suffix = f" — {detail}" if detail else ""
            raise InternalBrainAPIError(
                f"Backend returned HTTP {response.status_code}{suffix}",
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError:
            raise InternalBrainAPIError("Backend returned a non-JSON response.")

        if not isinstance(payload, dict):
            raise InternalBrainAPIError(
                "Backend returned an unexpected JSON response; an object was required."
            )

        return payload

    @staticmethod
    def _reviewer_headers(actor_user_id):
        if not actor_user_id:
            raise ValueError("A reviewer user ID is required")
        return {
            "X-InternalBrain-Actor": str(actor_user_id)
        }

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------
    def health(self):
        """GET /health — backend liveness + resource count."""
        return self._request("GET", "/health")

    def query(self, user_id, query, top_k=5):
        """POST /query — ask a permission-aware question."""
        return self._request(
            "POST",
            "/query",
            json_body={"user_id": user_id, "query": query, "top_k": int(top_k)},
            timeout=QUERY_TIMEOUT,
        )

    def sync_resources(self, reviewer_user_id):
        """POST /sync with mode=resources."""
        return self._request(
            "POST",
            "/sync",
            json_body={"mode": "resources"},
            headers=self._reviewer_headers(reviewer_user_id),
            timeout=120,
        )

    def sync_permissions(self, reviewer_user_id):
        """POST /permissions/reload."""
        return self._request(
            "POST",
            "/permissions/reload",
            headers=self._reviewer_headers(reviewer_user_id),
            timeout=60,
        )

    def sync_all(self, reviewer_user_id):
        """POST /sync with mode=all."""
        return self._request(
            "POST",
            "/sync",
            json_body={"mode": "all"},
            headers=self._reviewer_headers(reviewer_user_id),
            timeout=300,
        )

    def verify_audit(self):
        """GET /audit/verify — tamper-evident audit chain check."""
        return self._request("GET", "/audit/verify")

    # ------------------------------------------------------------------
    # Live permission demo (query-time authorization)
    # ------------------------------------------------------------------
    def get_slack_permission_status(self, channel_id, user_id, reviewer_user_id):
        """GET /demo/permissions/slack/{channel_id}/users/{user_id}."""
        safe_channel = quote(str(channel_id), safe="")
        safe_user = quote(str(user_id), safe="")
        return self._request(
            "GET",
            f"/demo/permissions/slack/{safe_channel}/users/{safe_user}",
            headers=self._reviewer_headers(reviewer_user_id),
        )

    def change_slack_membership(
        self, actor_user_id, target_user_id, channel_id, action, reason="Live permission demo"
    ):
        """POST /demo/permissions/slack/membership — action: grant | revoke."""
        if action not in {"grant", "revoke"}:
            raise ValueError("action must be either 'grant' or 'revoke'")
        return self._request(
            "POST",
            "/demo/permissions/slack/membership",
            json_body={
                "actor_user_id": actor_user_id,
                "target_user_id": target_user_id,
                "channel_id": channel_id,
                "action": action,
                "reason": reason,
            },
            headers=self._reviewer_headers(actor_user_id),
            timeout=60,
        )

    # ------------------------------------------------------------------
    # Audit inquiry
    # ------------------------------------------------------------------
    def search_audit_events(
        self,
        reviewer_user_id,
        event_type=None,
        user_id=None,
        query_id=None,
        action=None,
        resource_id=None,
        limit=20,
        newest_first=True,
    ):
        """GET /audit/events with optional filters (empty filters are omitted)."""
        params = {
            "event_type": event_type,
            "user_id": user_id,
            "query_id": query_id,
            "action": action,
            "resource_id": resource_id,
            "limit": int(limit),
            # Send an explicit lowercase boolean for the FastAPI query param.
            "newest_first": "true" if newest_first else "false",
        }
        params = {key: value for key, value in params.items() if value not in (None, "")}
        return self._request(
            "GET",
            "/audit/events",
            params=params,
            headers=self._reviewer_headers(reviewer_user_id),
        )
