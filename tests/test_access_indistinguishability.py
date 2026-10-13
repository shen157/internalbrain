"""Regression tests for resource-existence confidentiality.

An end user must not be able to tell whether an empty answer occurred because
the relevant resource exists but is unauthorized, or because no matching
resource exists. Internal audit metadata may differ; the public answer must not.
"""

import unittest

from app.llm.answer_service import ABSTAIN_MESSAGE, AnswerService


PUBLIC_SECURITY_FIELDS = (
    "answer",
    "citations",
    "source_count",
    "llm_called",
    "abstained",
    "safety_blocked",
    "safety_reason",
    "blocked_resources",
    "citation_validation",
)


class EmptyRetrievalService:
    """Return no results while varying permission-related internal metadata."""

    def __init__(self, *, total_resources, authorized_resources):
        self.total_resources = total_resources
        self.authorized_resources = authorized_resources

    def search(self, user_id, query, top_k=5, method="hybrid"):
        return {
            "user_id": user_id,
            "query": query,
            "method": method,
            "total_resources": self.total_resources,
            "authorized_resources": self.authorized_resources,
            "results": [],
        }


class RecordingAuditLogger:
    def __init__(self):
        self.events = []

    def log_event(self, **event):
        self.events.append(event)
        return event


class FailIfCalledLLM:
    def generate(self, system_prompt, user_prompt):
        raise AssertionError("LLM must not be called when retrieval returns no context")


class IrrelevantRetrievalService:
    """Return safe but irrelevant context so the LLM must decide to abstain."""

    def search(self, user_id, query, top_k=5, method="hybrid"):
        return {
            "user_id": user_id,
            "query": query,
            "method": method,
            "total_resources": 1,
            "authorized_resources": 1,
            "results": [
                {
                    "score": 0.2,
                    "resource": {
                        "source": "gdrive",
                        "resource_id": "TRAINING-001",
                        "title": "Security awareness training",
                        "content": "Annual training completion instructions.",
                        "updated_at": "2026-01-01T00:00:00Z",
                        "source_url": "https://example.test/training",
                    },
                }
            ],
        }


class StandardAbstainingLLM:
    model = "test-abstention-model"

    def generate(self, system_prompt, user_prompt):
        return ABSTAIN_MESSAGE


def public_projection(result):
    return {field: result.get(field) for field in PUBLIC_SECURITY_FIELDS}


class AccessIndistinguishabilityTests(unittest.TestCase):
    def run_empty_scenario(self, *, query, total_resources, authorized_resources):
        service = AnswerService(
            retrieval_service=EmptyRetrievalService(
                total_resources=total_resources,
                authorized_resources=authorized_resources,
            ),
            llm_client=FailIfCalledLLM(),
            audit_logger=RecordingAuditLogger(),
        )
        return service.answer(user_id="u007", query=query, top_k=5)

    def test_unauthorized_and_nonexistent_resources_have_same_public_result(self):
        unauthorized = self.run_empty_scenario(
            query="What was the private launch decision?",
            total_resources=1,
            authorized_resources=0,
        )
        nonexistent = self.run_empty_scenario(
            query="What is the ZXQ-991 imaginary project status?",
            total_resources=1,
            authorized_resources=1,
        )

        self.assertEqual(public_projection(unauthorized), public_projection(nonexistent))
        self.assertEqual(unauthorized["answer"], ABSTAIN_MESSAGE)
        self.assertEqual(unauthorized["citations"], [])
        self.assertEqual(unauthorized["source_count"], 0)
        self.assertFalse(unauthorized["llm_called"])
        self.assertTrue(unauthorized["abstained"])
        self.assertFalse(unauthorized["safety_blocked"])

    def test_public_abstention_text_does_not_reveal_permissions_or_resources(self):
        lowered = ABSTAIN_MESSAGE.lower()
        for forbidden in (
            "authorized",
            "unauthorized",
            "permission",
            "access denied",
            "private launch",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_standard_llm_abstention_is_not_misclassified_as_invalid_citations(self):
        logger = RecordingAuditLogger()
        service = AnswerService(
            retrieval_service=IrrelevantRetrievalService(),
            llm_client=StandardAbstainingLLM(),
            audit_logger=logger,
        )

        result = service.answer(
            user_id="u001",
            query="What happened in the Q3 security incident?",
            top_k=5,
        )

        self.assertEqual(result["answer"], ABSTAIN_MESSAGE)
        self.assertTrue(result["llm_called"])
        self.assertTrue(result["abstained"])
        self.assertFalse(result["safety_blocked"])
        self.assertEqual(result["source_count"], 0)
        self.assertEqual(result["citations"], [])
        self.assertTrue(result["citation_validation"]["valid"])
        self.assertFalse(result["citation_validation"]["citation_required"])
        self.assertEqual(
            result["citation_validation"]["reason"],
            "standard_abstention",
        )
        self.assertEqual(logger.events[-1]["action"], "abstain")


if __name__ == "__main__":
    unittest.main()
