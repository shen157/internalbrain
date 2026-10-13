"""Unit tests for the frontend HTTP client.

These tests never start FastAPI or access the network; they verify the exact
frontend/backend contract at the requests boundary.
"""

import unittest
from unittest.mock import Mock, patch

from frontend.api_client import InternalBrainAPIClient, InternalBrainAPIError


class InternalBrainAPIClientTests(unittest.TestCase):
    def setUp(self):
        self.client = InternalBrainAPIClient("http://example.test/")

    @staticmethod
    def _response(payload, status_code=200, text=""):
        response = Mock(status_code=status_code, text=text)
        response.json.return_value = payload
        return response

    @patch("frontend.api_client.requests.request")
    def test_permission_status_encodes_path_segments(self, request):
        request.return_value = self._response({"access_allowed": False})

        self.client.get_slack_permission_status("C PAY", "u/004", "u005")

        request.assert_called_once_with(
            "GET",
            "http://example.test/demo/permissions/slack/C%20PAY/users/u%2F004",
            json=None,
            params=None,
            headers={"X-InternalBrain-Actor": "u005"},
            timeout=15,
        )

    @patch("frontend.api_client.requests.request")
    def test_permission_change_body_matches_fastapi_schema(self, request):
        request.return_value = self._response({"status": "success"})

        self.client.change_slack_membership(
            "u005", "u004", "C-PAY", "grant", reason="Unit test"
        )

        request.assert_called_once_with(
            "POST",
            "http://example.test/demo/permissions/slack/membership",
            json={
                "actor_user_id": "u005",
                "target_user_id": "u004",
                "channel_id": "C-PAY",
                "action": "grant",
                "reason": "Unit test",
            },
            params=None,
            headers={"X-InternalBrain-Actor": "u005"},
            timeout=60,
        )

    def test_permission_change_rejects_unknown_action(self):
        with self.assertRaisesRegex(ValueError, "grant.*revoke"):
            self.client.change_slack_membership(
                "u005", "u004", "C-PAY", "delete"
            )

    @patch("frontend.api_client.requests.request")
    def test_audit_search_omits_empty_filters(self, request):
        request.return_value = self._response({"events": []})

        self.client.search_audit_events(
            "u005",
            event_type="permission_change", user_id="", limit=20, newest_first=False
        )

        self.assertEqual(
            request.call_args.kwargs["params"],
            {
                "event_type": "permission_change",
                "limit": 20,
                "newest_first": "false",
            },
        )
        self.assertEqual(
            request.call_args.kwargs["headers"],
            {"X-InternalBrain-Actor": "u005"},
        )

    @patch("frontend.api_client.requests.request")
    def test_sync_sends_reviewer_header(self, request):
        request.return_value = self._response({"total_resources": 88})

        self.client.sync_resources("u005")

        self.assertEqual(
            request.call_args.kwargs["headers"],
            {"X-InternalBrain-Actor": "u005"},
        )

    @patch("frontend.api_client.requests.request")
    def test_success_response_must_be_json_object(self, request):
        request.return_value = self._response(["unexpected"])

        with self.assertRaisesRegex(InternalBrainAPIError, "object was required"):
            self.client.health()

    @patch("frontend.api_client.requests.request")
    def test_backend_error_uses_fastapi_detail(self, request):
        request.return_value = self._response(
            {"detail": "Unknown user: u999"}, status_code=404
        )

        with self.assertRaises(InternalBrainAPIError) as context:
            self.client.get_slack_permission_status("C-PAY", "u999", "u005")

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("Unknown user: u999", context.exception.message)


if __name__ == "__main__":
    unittest.main()
