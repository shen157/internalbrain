"""Authorization checks for reviewer-only administration endpoints."""

import unittest

from fastapi import HTTPException

from app.api.main import (
    app,
    change_slack_membership,
    search_audit_events,
    slack_permission_status,
    sync,
)
from app.api.schemas import SlackPermissionChangeRequest, SyncRequest


class ReviewerAuthorizationTests(unittest.TestCase):
    def assert_forbidden(self, callback):
        with self.assertRaises(HTTPException) as context:
            callback()
        self.assertEqual(context.exception.status_code, 403)

    def test_audit_events_requires_reviewer(self):
        self.assert_forbidden(
            lambda: search_audit_events(
                limit=1,
                x_internalbrain_actor=None,
            )
        )
        self.assert_forbidden(
            lambda: search_audit_events(
                limit=1,
                x_internalbrain_actor="u001",
            )
        )

        reviewer_result = search_audit_events(
            limit=1,
            x_internalbrain_actor="u005",
        )
        self.assertTrue(reviewer_result["chain_valid"])

    def test_sync_rejects_ordinary_user_before_mutation(self):
        self.assert_forbidden(
            lambda: sync(
                SyncRequest(mode="resources"),
                x_internalbrain_actor="u001",
            )
        )

    def test_permission_status_requires_reviewer(self):
        self.assert_forbidden(
            lambda: slack_permission_status(
                "C-PAY",
                "u004",
                x_internalbrain_actor="u004",
            )
        )

        reviewer_result = slack_permission_status(
            "C-PAY",
            "u004",
            x_internalbrain_actor="u005",
        )
        self.assertEqual(reviewer_result["channel_id"], "C-PAY")

    def test_permission_change_rejects_spoofed_actor(self):
        request = SlackPermissionChangeRequest(
            actor_user_id="demo-admin",
            target_user_id="u004",
            channel_id="C-PAY",
            action="grant",
            reason="test",
        )

        self.assert_forbidden(
            lambda: change_slack_membership(
                request,
                x_internalbrain_actor="u005",
            )
        )

    def test_reviewer_header_is_declared_on_every_admin_route(self):
        schema = app.openapi()
        protected_routes = (
            ("/sync", "post"),
            ("/permissions/reload", "post"),
            ("/demo/permissions/slack/{channel_id}/users/{user_id}", "get"),
            ("/demo/permissions/slack/membership", "post"),
            ("/audit/events", "get"),
        )

        for path, method in protected_routes:
            parameters = schema["paths"][path][method].get("parameters", [])
            headers = {
                parameter["name"]
                for parameter in parameters
                if parameter.get("in") == "header"
            }
            self.assertIn("X-InternalBrain-Actor", headers, path)


if __name__ == "__main__":
    unittest.main()
