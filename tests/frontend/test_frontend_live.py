"""Live end-to-end frontend test against a mock InternalBrain HTTP backend.

This starts a real HTTP server (no backend code is imported) and points the
Streamlit app at it via INTERNALBRAIN_API_URL, so the app exercises the real
request path: Streamlit -> HTTP -> backend -> render.

Validates:
1. Sidebar health + audit chain status.
2. Live Permission Demo: DENIED -> ALLOWED transition, re-read from backend.
3. Live retrieval proof: abstained before grant, retrievable after grant,
   abstained again after revoke.
4. Audit Inquiry: chain status, matched/returned counts, event table,
   truncated hashes.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_PATH = PROJECT_ROOT / "frontend" / "app.py"

BASE_USERS = {"u004": "David"}
LONG_HASH = "a1b2c3d4e5f6071829304152637485960a1b2c3d4e5f6071829304152637485"


class BackendState:
    def __init__(self):
        self.members = {}
        self.events = []

    def is_member(self, channel, user):
        return self.members.get((channel, user), False)

    def add_event(self, **kwargs):
        event = {
            "event_id": f"evt-{len(self.events) + 1:04d}",
            "timestamp": "2026-10-12T18:00:00Z",
            "previous_hash": LONG_HASH,
            "current_hash": LONG_HASH,
        }
        event.update(kwargs)
        self.events.append(event)
        return event["event_id"]


STATE = BackendState()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep test output clean
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reviewer_authorized(self):
        return self.headers.get("X-InternalBrain-Actor") == "u005"

    # ------------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/health":
            return self._send(200, {
                "status": "ok", "service": "InternalBrain", "version": "1.0.0",
                "resource_count": 88,
            })

        if path == "/audit/verify":
            return self._send(200, {
                "valid": True, "event_count": len(STATE.events), "broken_line": None, "reason": None,
            })

        if path.startswith("/demo/permissions/slack/"):
            if not self._reviewer_authorized():
                return self._send(403, {"detail": "Reviewer authorization is required."})
            parts = path.strip("/").split("/")
            # demo / permissions / slack / {channel} / users / {user}
            if len(parts) == 6 and parts[4] == "users":
                channel, user = parts[3], parts[5]
                member = STATE.is_member(channel, user)
                return self._send(200, {
                    "channel_id": channel,
                    "channel_name": "Payment Migration",
                    "is_private": True,
                    "user_id": user,
                    "is_member": member,
                    "access_allowed": member,
                    "permission_source": "query_time_permission_store",
                })
            return self._send(404, {"detail": "bad permission path"})

        if path == "/audit/events":
            if not self._reviewer_authorized():
                return self._send(403, {"detail": "Reviewer authorization is required."})
            event_type = (params.get("event_type") or [None])[0]
            user_id = (params.get("user_id") or [None])[0]
            action = (params.get("action") or [None])[0]
            resource_id = (params.get("resource_id") or [None])[0]
            query_id = (params.get("query_id") or [None])[0]
            limit = int((params.get("limit") or ["20"])[0])
            newest_first = (params.get("newest_first") or ["true"])[0].lower() != "false"

            matched = [
                e for e in STATE.events
                if (not event_type or e.get("event_type") == event_type)
                and (
                    not user_id
                    or user_id
                    in (
                        e.get("user_id"),
                        e.get("actor_user_id"),
                        e.get("target_user_id"),
                        (e.get("details") or {}).get("target_user_id"),
                    )
                )
                and (not action or e.get("action") == action)
                and (not resource_id or resource_id == e.get("resource_id"))
                and (not query_id or e.get("query_id") == query_id)
            ]
            if newest_first:
                matched = list(reversed(matched))
            returned = matched[:limit]
            return self._send(200, {
                "chain_valid": True,
                "chain_event_count": len(STATE.events),
                "matched_count": len(matched),
                "returned_count": len(returned),
                "limit": limit,
                "newest_first": newest_first,
                "filters": {
                    "event_type": event_type, "user_id": user_id, "query_id": query_id,
                    "action": action, "resource_id": resource_id,
                },
                "events": returned,
            })

        return self._send(404, {"detail": f"no route for {path}"})

    # ------------------------------------------------------------------
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {}

        path = urlparse(self.path).path

        if path == "/demo/permissions/slack/membership":
            if not self._reviewer_authorized():
                return self._send(403, {"detail": "Reviewer authorization is required."})
            if body.get("actor_user_id") != "u005":
                return self._send(403, {"detail": "Actor mismatch."})
            channel = body.get("channel_id", "C-PAY")
            user = body.get("target_user_id", "u004")
            action = body.get("action")
            before = STATE.is_member(channel, user)
            after = True if action == "grant" else False
            STATE.members[(channel, user)] = after
            event_id = STATE.add_event(
                event_type="permission_change",
                user_id=body.get("actor_user_id", "u005"),
                action=f"{action}_slack_membership",
                resource_id=channel,
                auth_decision="granted" if after else "revoked",
                details={
                    "target_user_id": user,
                    "channel_id": channel,
                    "before_member": before,
                    "after_member": after,
                    "query_time_enforced": True,
                    "reindex_required": False,
                    "persistence": "in_memory_until_reload_or_restart",
                },
            )
            return self._send(200, {
                "status": "success",
                "action": action,
                "actor_user_id": body.get("actor_user_id", "u005"),
                "target_user_id": user,
                "channel_id": channel,
                "before_member": before,
                "after_member": after,
                "access_allowed": after,
                "changed": before != after,
                "query_time_enforced": True,
                "reindex_required": False,
                "persistence": "in_memory_until_reload_or_restart",
                "audit_event_id": event_id,
            })

        if path == "/query":
            user = body.get("user_id")
            query = body.get("query", "")
            member = STATE.is_member("C-PAY", user)
            if member:
                event_id = STATE.add_event(
                    event_type="final_response", user_id=user,
                    query_id="q-pay-104", authorization_decision=True,
                )
                return self._send(200, {
                    "user_id": user,
                    "query_id": "q-pay-104",
                    "query": query,
                    "answer": "The rollback surface for PAY-104 is limited by the dual-write window; "
                              "a one-way backfill is required [S1].",
                    "citations": [{
                        "citation_id": "S1",
                        "source": "Slack",
                        "title": "C-PAY #payment-migration — PAY-104 rollback surface",
                        "resource_id": "SLACK-C-PAY-PAY104",
                        "resource_type": "slack_message",
                        "updated_at": "2026-11-01T10:00:00Z",
                        "source_url": "https://slack.example.com/archives/C-PAY/p123",
                        "snippet": "dual-write rollback surface one-way backfill",
                    }],
                    "source_count": 1,
                    "llm_called": True,
                    "abstained": False,
                    "safety_blocked": False,
                    "safety_reason": None,
                    "blocked_resources": [],
                    "citation_validation": {
                        "valid": True, "available_ids": ["S1"], "used_ids": ["S1"],
                        "invalid_ids": [], "missing_citations": False,
                    },
                })
            return self._send(200, {
                "user_id": user,
                "query_id": "q-pay-104-abstained",
                "query": query,
                "answer": "I could not find enough information to answer this question.",
                "citations": [],
                "source_count": 0,
                "llm_called": False,
                "abstained": True,
                "safety_blocked": False,
                "safety_reason": None,
                "blocked_resources": [],
                "citation_validation": {"valid": True, "available_ids": [], "used_ids": [], "invalid_ids": []},
            })

        if path == "/sync":
            if not self._reviewer_authorized():
                return self._send(403, {"detail": "Reviewer authorization is required."})
            mode = body.get("mode", "resources")
            if mode == "permissions":
                return self._send(200, {"status": "success", "sync_duration_ms": 42})
            resources = {
                "added_count": 3, "updated_count": 4, "removed_count": 1,
                "total_resources": 88, "sync_duration_ms": 1200,
            }
            if mode == "all":
                return self._send(200, {
                    "resources": resources,
                    "permissions": {"status": "success", "sync_duration_ms": 7},
                })
            return self._send(200, resources)

        if path == "/permissions/reload":
            if not self._reviewer_authorized():
                return self._send(403, {"detail": "Reviewer authorization is required."})
            return self._send(200, {"status": "success", "sync_duration_ms": 42})

        return self._send(404, {"detail": f"no route for {path}"})


def start_mock_backend():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def texts(at):
    parts = []
    for collection in (at.markdown, at.success, at.error, at.info, at.warning, at.caption):
        try:
            parts.extend(str(element.value) for element in collection)
        except Exception:
            pass
    for metric in at.metric:
        parts.append(f"{metric.label}={metric.value}")
    for element in at.json:
        raw = element.value
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                pass
        # ensure_ascii=False so truncated "…" markers stay readable in asserts
        parts.append(json.dumps(raw, ensure_ascii=False))
    return "\n".join(parts)


def require(condition, message):
    if not condition:
        print(f"FAIL: {message}")
        sys.exit(1)
    print(f"PASS: {message}")


def main():
    STATE.members.clear()
    STATE.events.clear()
    server, base_url = start_mock_backend()
    os.environ["INTERNALBRAIN_API_URL"] = base_url
    print(f"Mock backend running at {base_url}")

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()

    require(not at.exception, "app renders against a live backend with no exceptions")
    body = texts(at)
    require("Resources: 88" in body, "sidebar shows resource count from /health (88)")
    require("Audit Chain: Valid" in body, "sidebar shows audit chain valid")

    button_keys = {button.key for button in at.button}
    require("audit_search" not in button_keys,
            "ordinary users cannot see Audit Inquiry controls")
    require("perm_grant_btn" not in button_keys,
            "ordinary users cannot see Live Permission controls")
    require("sync_resources_btn" not in button_keys,
            "ordinary users cannot see administration sync controls")

    # Reviewer-only controls appear for Elena (u005 / compliance officer).
    at.selectbox(key="user_label").set_value("u005 — Elena (Compliance Officer)")
    at.run()
    require(not at.exception, "reviewer switch renders with no exceptions")

    # --- initial permission state (denied) -----------------------------
    body = texts(at)
    require("Denied" in body, "permission demo initially shows Access: Denied")
    require("query_time_permission_store" in body, "permission source is shown from the API")

    # --- grant --------------------------------------------------------
    at.button(key="perm_grant_btn").click()
    at.run()
    require(not at.exception, "no exception after Grant Access")
    body = texts(at)
    require("Permission change applied: grant" in body, "grant result is shown")
    require("No Re-index Required" in body, "re-index not required is shown")
    require("in_memory_until_reload_or_restart" in body, "permission persistence is shown")
    require("Demo-only state" in body, "in-memory permission warning is shown")
    require("evt-0001" in body, "audit event id from the API is shown")
    require("Allowed" in body, "current access refreshed to Allowed after grant")

    # --- live retrieval proof: after grant -----------------------------
    at.button(key="perm_test_query").click()
    at.run()
    require(not at.exception, "no exception after Test Access with Query (granted)")
    body = texts(at)
    require("Retrieval Proof" in body, "retrieval proof panel is rendered")
    require("context source(s) retrieved" in body, "granted user retrieves context sources")
    require("PAY-104 rollback surface" in body, "private C-PAY citation is visible after grant")
    require("q-pay-104" in body, "query id of the granted query is shown")

    # --- revoke -------------------------------------------------------
    at.button(key="perm_revoke_btn").click()
    at.run()
    require(not at.exception, "no exception after Revoke Access")
    body = texts(at)
    require("Permission change applied: revoke" in body, "revoke result is shown")
    require("Denied" in body, "current access refreshed to Denied after revoke")

    # --- live retrieval proof: after revoke ----------------------------
    at.button(key="perm_test_query").click()
    at.run()
    body = texts(at)
    require("Abstained — no authorized sources" in body,
            "revoked user abstains (private resource no longer retrievable)")

    # --- audit inquiry -------------------------------------------------
    at.button(key="audit_search").click()
    at.run()
    require(not at.exception, "no exception after Search Audit Events")
    body = texts(at)
    require("Audit Chain: Valid" in body, "audit inquiry shows chain valid")
    require("Matched Events=3" in body, "unfiltered search matches all three audit events")
    require("permission_change" in body, "event type is rendered in the summary table")
    require("u005" in body, "reviewer actor user id is rendered")
    audit_tables = "\n".join(
        element.value for element in at.markdown if "ib-audit-wrap" in element.value
    )
    require("u005 → u004" in audit_tables, "audit summary shows actor and target user")
    require("granted" in audit_tables and "revoked" in audit_tables,
            "real backend auth_decision values are rendered in the Decision column")
    require(LONG_HASH not in body, "full hash values are not dumped into the page")
    require("a1b2c3d4e5f6071…" in body, "hashes are truncated in the technical view")

    # --- filtered audit search ----------------------------------------
    at.selectbox(key="audit_event_type").set_value("permission_change")
    at.run()
    at.button(key="audit_search").click()
    at.run()
    body = texts(at)
    require("Matched Events=2" in body, "event_type filter keeps the two permission events")

    at.text_input(key="audit_user_id").set_value("u004")
    at.run()
    at.button(key="audit_search").click()
    at.run()
    body = texts(at)
    require("Matched Events=2" in body,
            "target user filter matches details.target_user_id in permission events")

    at.text_input(key="audit_action").set_value("grant_slack_membership")
    at.run()
    at.button(key="audit_search").click()
    at.run()
    body = texts(at)
    require("Matched Events=1" in body,
            "real grant_slack_membership action filter matches one event")

    at.text_input(key="audit_user_id").set_value("")
    at.text_input(key="audit_action").set_value("")
    at.run()

    at.selectbox(key="audit_event_type").set_value("query_received")
    at.run()
    at.button(key="audit_search").click()
    at.run()
    body = texts(at)
    require("No audit events matched these filters." in body,
            "unmatched event type renders the empty state instead of failing")

    # --- sync buttons exercise their real HTTP paths -------------------
    at.button(key="sync_resources_btn").click()
    at.run()
    body = texts(at)
    require("Sync completed (resources)" in body, "Sync Resources button completes over HTTP")
    require("Total Resources" in body and "1200 ms" in body,
            "resource sync response schema is rendered")

    at.button(key="sync_permissions_btn").click()
    at.run()
    body = texts(at)
    require("Sync completed (permissions)" in body,
            "Reload Permissions button completes over HTTP")
    require("42 ms" in body, "permission sync response schema is rendered")

    at.button(key="sync_all_btn").click()
    at.run()
    body = texts(at)
    require("Sync completed (all)" in body, "Sync All button completes over HTTP")
    require("**Resources**" in body and "**Permissions**" in body,
            "nested Sync All response is rendered")

    server.shutdown()
    print("ALL LIVE TESTS PASSED")


if __name__ == "__main__":
    main()
