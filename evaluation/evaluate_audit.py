import json
import shutil

from pathlib import Path

from app.security.audit_logger import (
    AuditLogger
)


RESULT_DIR = Path(
    "evaluation/results"
)

TEST_LOG = (
    RESULT_DIR
    / "audit_test_log.jsonl"
)

TAMPERED_LOG = (
    RESULT_DIR
    / "audit_test_log_tampered.jsonl"
)


def evaluate_audit():

    RESULT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )


    # -----------------------------------------
    # Clean old test logs
    # -----------------------------------------

    for path in [
        TEST_LOG,
        TAMPERED_LOG
    ]:

        if path.exists():
            path.unlink()


    logger = AuditLogger(
        TEST_LOG
    )


    # -----------------------------------------
    # Create test chain
    # -----------------------------------------

    logger.log_event(
        event_type="query_received",
        user_id="u001",
        query_id="Q-TEST-001",
        action="query",
        details={
            "query":
                "payment migration"
        }
    )


    logger.log_event(
        event_type="authorization_retrieval",
        user_id="u001",
        query_id="Q-TEST-001",
        action="retrieve",
        details={
            "authorized_resources":
                46
        }
    )


    logger.log_event(
        event_type="final_response",
        user_id="u001",
        query_id="Q-TEST-001",
        action="answer",
        details={
            "llm_called":
                True
        }
    )


    # -----------------------------------------
    # Verify valid chain
    # -----------------------------------------

    valid_result = (
        logger.verify_chain()
    )


    # -----------------------------------------
    # Create tampered copy
    # -----------------------------------------

    shutil.copy(
        TEST_LOG,
        TAMPERED_LOG
    )


    lines = []

    with open(
        TAMPERED_LOG,
        "r",
        encoding="utf-8"
    ) as f:

        lines = f.readlines()


    second_event = json.loads(
        lines[1]
    )

    # Simulate attacker editing audit log
    second_event[
        "user_id"
    ] = "u999"


    lines[1] = (
        json.dumps(
            second_event,
            ensure_ascii=False
        )
        + "\n"
    )


    with open(
        TAMPERED_LOG,
        "w",
        encoding="utf-8"
    ) as f:

        f.writelines(lines)


    tampered_logger = (
        AuditLogger(
            TAMPERED_LOG
        )
    )


    tampered_result = (
        tampered_logger
        .verify_chain()
    )


    valid_chain_pass = (
        valid_result["valid"]
        is True
    )

    tamper_detection_pass = (
        tampered_result["valid"]
        is False
    )


    summary = {

        "version":
            "audit_v1",

        "valid_chain_test":
            valid_chain_pass,

        "tamper_detection_test":
            tamper_detection_pass,

        "valid_chain_result":
            valid_result,

        "tampered_chain_result":
            tampered_result,

        "all_passed":
            (
                valid_chain_pass
                and
                tamper_detection_pass
            )
    }


    return summary


def save_results(summary):

    output_path = (
        RESULT_DIR
        / "audit_evaluation_v1.json"
    )


    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
            ensure_ascii=False
        )


    print(
        f"\nResults saved to: "
        f"{output_path}"
    )


if __name__ == "__main__":

    summary = evaluate_audit()


    print(
        "===== Audit Evaluation ====="
    )

    print(
        f"Valid Chain Test: "
        f"{'PASS' if summary['valid_chain_test'] else 'FAIL'}"
    )

    print(
        f"Tamper Detection Test: "
        f"{'PASS' if summary['tamper_detection_test'] else 'FAIL'}"
    )

    print(
        f"All Passed: "
        f"{summary['all_passed']}"
    )


    print(
        "\nValid Chain:"
    )

    print(
        summary[
            "valid_chain_result"
        ]
    )


    print(
        "\nTampered Chain:"
    )

    print(
        summary[
            "tampered_chain_result"
        ]
    )


    save_results(summary)