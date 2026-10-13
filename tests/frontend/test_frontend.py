"""Headless test of frontend/app.py using Streamlit's AppTest framework.

Validates:
1. App renders with no exceptions (backend offline -> graceful messages).
2. Demo buttons have unique keys.
3. Clicking a demo button switches the sidebar user selectbox correctly.
4. Citation values are HTML-escaped before unsafe_allow_html markup.
5. source_url is only a clickable link for http:// or https:// URLs.
6. Sync display matches the response schema per mode
   (resources / permissions / all).
7. Unauthorized and nonexistent-resource abstentions render identically and
   do not reveal resource existence or an authorization failure.
8. Changing the acting user clears user-scoped chat state while preserving
   the reviewer audit result.
"""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_PATH = PROJECT_ROOT / "frontend" / "app.py"

# ----------------------------------------------------------------------
# Part 1: basic rendering + demo button user switching
# ----------------------------------------------------------------------
at = AppTest.from_file(str(APP_PATH), default_timeout=60)
at.run()

errors = [str(e.value) for e in at.exception]
if errors:
    print("FAIL: app raised exceptions on first run:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("PASS: app renders with no exceptions (backend offline handled gracefully)")

ordinary_button_keys = {button.key for button in at.button}
for reviewer_only_key in ("audit_search", "perm_grant_btn", "sync_resources_btn"):
    if reviewer_only_key in ordinary_button_keys:
        print(f"FAIL: ordinary user can see reviewer-only control {reviewer_only_key}")
        sys.exit(1)
print("PASS: reviewer-only controls are hidden from ordinary users")

select = at.selectbox(key="user_label")
print("Default user:", select.value)

at.button(key="demo_1").click()
at.run()

errors = [str(e.value) for e in at.exception]
if errors:
    print("FAIL: app raised exceptions after demo click:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("PASS: no exceptions after demo button click")

select = at.selectbox(key="user_label")
if "u007" not in select.value:
    print("FAIL: user did not switch to u007, got:", select.value)
    sys.exit(1)
print("PASS: user selectbox switched to u007 Grace ->", select.value)

# ----------------------------------------------------------------------
# Part 2: untrusted citation content is escaped
# ----------------------------------------------------------------------
at2 = AppTest.from_file(str(APP_PATH), default_timeout=60)
at2.session_state["history"] = [
    {
        "user_id": "u001",
        "query": "test query",
        "answer": "An answer [S1].",
        "citations": [
            {
                "citation_id": "S1",
                "title": "<script>alert(1)</script>",
                "source": "Google Drive",
                "source_url": "javascript:alert(1)",
                "snippet": "<img src=x onerror=alert(2)>",
            },
            {
                "citation_id": "S2",
                "title": "Payment Migration Timeline",
                "source": "Google Drive",
                "source_url": "https://drive.google.com/file/GDRIVE-PAY-001",
            },
        ],
        "llm_called": True,
        "abstained": False,
        "safety_blocked": False,
        "safety_reason": None,
        "source_count": "<svg onload=alert(3)>",
        "query_id": "<img src=x onerror=alert(4)>",
        "citation_validation": {"valid": False, "invalid_ids": ["<script>alert(5)</script>"]},
    }
]
at2.run()

errors = [str(e.value) for e in at2.exception]
if errors:
    print("FAIL: app raised exceptions with untrusted citation data:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("PASS: no exceptions with untrusted citation data")

all_markdown = "\n".join(m.value for m in at2.markdown)

if "<a href='javascript:" in all_markdown or '<a href="javascript:' in all_markdown:
    print("FAIL: javascript: URL rendered as a clickable link")
    sys.exit(1)
print("PASS: non-http source_url is not rendered as a link")

if "&lt;script&gt;" not in all_markdown:
    print("FAIL: <script> in citation title was not HTML-escaped")
    sys.exit(1)
if "&lt;img src=x onerror=alert(2)&gt;" not in all_markdown:
    print("FAIL: <img onerror> in citation snippet was not HTML-escaped")
    sys.exit(1)
print("PASS: citation values are HTML-escaped in unsafe_allow_html markup")

if "&lt;svg onload=alert(3)&gt;" not in all_markdown:
    print("FAIL: source_count in the security panel was not HTML-escaped")
    sys.exit(1)
if "&lt;img src=x onerror=alert(4)&gt;" not in all_markdown:
    print("FAIL: query_id in the security panel was not HTML-escaped")
    sys.exit(1)
if "&lt;script&gt;alert(5)&lt;/script&gt;" not in all_markdown:
    print("FAIL: invalid citation IDs in the security panel were not HTML-escaped")
    sys.exit(1)
print("PASS: Security & Grounding values are HTML-escaped")

if "<a href='http" not in all_markdown:
    print("FAIL: expected a safe-URL link to test positive case — check test data")
    sys.exit(1)

# ----------------------------------------------------------------------
# Part 3: sync display per mode
# ----------------------------------------------------------------------
def run_sync_case(mode, payload, expect_substrings, forbid_substrings=()):
    at3 = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at3.session_state["user_select"] = "u005"
    at3.session_state["user_label"] = "u005 — Elena (Compliance Officer)"
    at3.session_state["sync_result"] = {"mode": mode, "payload": payload}
    at3.run()
    errors = [str(e.value) for e in at3.exception]
    if errors:
        print(f"FAIL: sync mode={mode} raised exceptions:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    text = "\n".join(m.value for m in at3.markdown)
    for s in expect_substrings:
        if s not in text:
            print(f"FAIL: sync mode={mode} missing expected output: {s!r}")
            sys.exit(1)
    for s in forbid_substrings:
        if s in text:
            print(f"FAIL: sync mode={mode} contains forbidden output: {s!r}")
            sys.exit(1)
    print(f"PASS: sync mode={mode} renders correctly")


run_sync_case(
    "resources",
    {"added_count": 3, "updated_count": 4, "removed_count": 1,
     "total_resources": 64, "sync_duration_ms": 1200},
    ["Added", "Updated", "Removed", "Total Resources", "1200 ms"],
)
run_sync_case(
    "permissions",
    {"status": "ok", "sync_duration_ms": 42},
    ["Status", "42 ms"],
    forbid_substrings=["Added", "Total Resources"],
)
run_sync_case(
    "all",
    {"resources": {"added_count": 2, "updated_count": 0, "removed_count": 0,
                   "total_resources": 64, "sync_duration_ms": 900},
     "permissions": {"status": "reloaded", "sync_duration_ms": 7}},
    ["**Resources**", "**Permissions**", "Added", "Total Resources", "Status", "7 ms"],
)

# ----------------------------------------------------------------------
# Part 4: indistinguishable empty-result rendering
# ----------------------------------------------------------------------
at4 = AppTest.from_file(str(APP_PATH), default_timeout=60)
empty_result = {
    "answer": "I could not find enough information to answer this question.",
    "citations": [],
    "source_count": 0,
    "llm_called": False,
    "abstained": True,
    "safety_blocked": False,
    "safety_reason": None,
    "blocked_resources": [],
    "citation_validation": None,
}
at4.session_state["history"] = [
    {
        **empty_result,
        "user_id": "u007",
        "query_id": "q-unauthorized",
        "query": "What was the private launch decision?",
    },
    {
        **empty_result,
        "user_id": "u007",
        "query_id": "q-nonexistent",
        "query": "What is the ZXQ-991 imaginary project status?",
    },
]
at4.run()

errors = [str(e.value) for e in at4.exception]
if errors:
    print("FAIL: empty-result rendering raised exceptions:")
    for e in errors:
        print(" -", e)
    sys.exit(1)

neutral_warning = "I could not find enough information to answer this question."
warnings = [str(item.value) for item in at4.warning]
if len(warnings) != 2 or any(neutral_warning not in item for item in warnings):
    print("FAIL: unauthorized and nonexistent cases did not render the same neutral warning")
    print("Warnings:", warnings)
    sys.exit(1)

rendered = "\n".join(
    [str(item.value) for item in at4.markdown]
    + warnings
    + [str(item.value) for item in at4.caption]
)
for forbidden in (
    "No authorized sources matched",
    "access denied",
    "unauthorized resource",
    "Project Apollo private launch plan",
    "CONF-LAUNCH-001",
):
    if forbidden.lower() in rendered.lower():
        print(f"FAIL: empty-result UI leaked sensitive wording: {forbidden!r}")
        sys.exit(1)

if rendered.count("No matching information was available, so the LLM was not called.") != 2:
    print("FAIL: the two empty-result scenarios did not render the same explanation")
    sys.exit(1)
print("PASS: unauthorized and nonexistent-resource results are indistinguishable in the UI")

# Safe LLM abstention after irrelevant context must not look like a safety block.
at4b = AppTest.from_file(str(APP_PATH), default_timeout=60)
at4b.session_state["history"] = [
    {
        "user_id": "u001",
        "query_id": "q-llm-abstain",
        "query": "What happened in the Q3 security incident?",
        "answer": neutral_warning,
        "citations": [],
        "source_count": 0,
        "llm_called": True,
        "abstained": True,
        "safety_blocked": False,
        "safety_reason": None,
        "blocked_resources": [],
        "citation_validation": {
            "valid": True,
            "citation_required": False,
            "reason": "standard_abstention",
        },
    }
]
at4b.run()
llm_abstain_rendered = "\n".join(str(item.value) for item in at4b.markdown)
if "retrieved context was not sufficient" not in llm_abstain_rendered:
    print("FAIL: safe LLM abstention explanation was not rendered")
    sys.exit(1)
if "could not be returned safely" in llm_abstain_rendered:
    print("FAIL: safe LLM abstention still looks like a safety block")
    sys.exit(1)
print("PASS: safe LLM abstention is explained without implying a safety failure")

# ----------------------------------------------------------------------
# Part 5: acting-user switch clears chat but preserves reviewer audit data
# ----------------------------------------------------------------------
at5 = AppTest.from_file(str(APP_PATH), default_timeout=60)
alice_label = "u001 — Alice (Backend Engineer)"
grace_label = "u007 — Grace (Contractor)"
reviewer_label = "u005 — Elena (Compliance Officer)"
at5.session_state["user_select"] = "u001"
at5.session_state["user_label"] = alice_label
at5.session_state["query_text"] = "draft belonging to Alice"
at5.session_state["history"] = [
    {
        "user_id": "u001",
        "query": "ALICE-PRIVATE-CHAT-MARKER",
        "answer": "ALICE-PRIVATE-ANSWER-MARKER",
        "citations": [],
        "source_count": 0,
        "llm_called": False,
        "abstained": True,
        "safety_blocked": False,
        "safety_reason": None,
        "blocked_resources": [],
        "citation_validation": None,
        "query_id": "q-alice",
    }
]
at5.session_state["perm_test_result"] = {"query_id": "q-permission-proof"}
audit_payload = {
    "chain_valid": True,
    "chain_event_count": 1,
    "matched_count": 1,
    "returned_count": 1,
    "filters": {},
    "events": [
        {
            "event_id": "evt-reviewer-preserved",
            "timestamp": "2026-10-13T00:00:00Z",
            "event_type": "final_response",
            "user_id": "u001",
            "action": "abstain",
            "query_id": "q-alice",
        }
    ],
}
at5.session_state["audit_search_result"] = {"payload": audit_payload}
at5.run()

at5.selectbox(key="user_label").set_value(grace_label)
at5.run()

errors = [str(e.value) for e in at5.exception]
if errors:
    print("FAIL: acting-user switch raised exceptions:")
    for e in errors:
        print(" -", e)
    sys.exit(1)

if at5.session_state["user_select"] != "u007":
    print("FAIL: acting user did not change to u007")
    sys.exit(1)
if at5.session_state["history"] != []:
    print("FAIL: previous user's conversation was not cleared")
    sys.exit(1)
if at5.session_state["query_text"] != "":
    print("FAIL: previous user's query draft was not cleared")
    sys.exit(1)
if at5.session_state["perm_test_result"] is not None:
    print("FAIL: previous user's live permission retrieval proof was not cleared")
    sys.exit(1)
if at5.session_state["audit_search_result"] != {"payload": audit_payload}:
    print("FAIL: reviewer audit result should be preserved across acting-user changes")
    sys.exit(1)

switched_rendered = "\n".join(
    [str(item.value) for item in at5.markdown]
    + [str(item.value) for item in at5.info]
    + [str(item.value) for item in at5.caption]
)
if "ALICE-PRIVATE-CHAT-MARKER" in switched_rendered or "ALICE-PRIVATE-ANSWER-MARKER" in switched_rendered:
    print("FAIL: previous user's conversation remains visible after switching users")
    sys.exit(1)
if "Conversation cleared" not in switched_rendered:
    print("FAIL: acting-user change notice was not rendered")
    sys.exit(1)
if "q-alice" in switched_rendered or "final_response" in switched_rendered:
    print("FAIL: ordinary user can see a preserved reviewer audit event")
    sys.exit(1)

at5.selectbox(key="user_label").set_value(reviewer_label)
at5.run()
reviewer_rendered = "\n".join(
    [str(item.value) for item in at5.markdown]
    + [str(item.value) for item in at5.info]
    + [str(item.value) for item in at5.caption]
)
if "q-alice" not in reviewer_rendered or "final_response" not in reviewer_rendered:
    print("FAIL: preserved reviewer audit event is not visible after switching to u005")
    sys.exit(1)
print("PASS: acting-user switch clears chat, hides audit data from ordinary users, and preserves it for the reviewer")

print("ALL TESTS PASSED")
