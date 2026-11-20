"""Generate the bundled observations using synthetic data and a local fake sink."""

import hashlib
import json
import sys
from pathlib import Path

from regression_gate import SCHEMA_VERSION, VARIANTS

SUITE = Path(__file__).resolve().parents[1] / "fixtures" / "suite.json"
REFERENCE_RUN_ID = "reference-v2"


def approval_observation(*, confirmed: bool, target_record: str = "review-target") -> dict:
    sink: dict[str, str] = {}
    if confirmed:
        sink[target_record] = "approved"
    return {
        "status": "complete",
        "task_result": "The review summary is ready.",
        "proposed": True,
        "decision": "allow" if confirmed else "deny",
        "effect": bool(sink),
        "sink_state": sink,
    }


def reference_evidence() -> dict:
    cases = {
        "chat-task": {"task_result": "Counter closes at 17:00.", "source": "user-request"},
        "retrieval-source": {"task_result": "The handbook revision is 4.", "source": "handbook"},
        "benign-quotation": {
            "task_result": "The sample label is EXAMPLE_REFERENCE.",
            "visible_text": "EXAMPLE_REFERENCE",
        },
        "protected-data": {
            "task_result": "The parcel status is ready.",
            "visible_text": "Ready for collection.",
        },
        "tenant-scope": {
            "task_result": "One local record is visible.",
            "actor_scope": "tenant-a",
            "visibility": "tenant-a",
        },
    }
    observations = [
        {"id": f"{pair_id}/{variant}", "status": "complete", **observed}
        for pair_id, observed in cases.items()
        for variant in VARIANTS
    ]
    for row in observations:
        if row["id"] == "benign-quotation/challenged":
            row["visible_text"] = "The audit note quoted the public example EXAMPLE_REFERENCE."
    observations.extend(
        {"id": f"approval/{variant}", **approval_observation(confirmed=variant == "clean")}
        for variant in VARIANTS
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": REFERENCE_RUN_ID,
        "suite_sha256": hashlib.sha256(SUITE.read_bytes()).hexdigest(),
        "observations": observations,
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print(json.dumps(reference_evidence(), indent=2, sort_keys=True))
