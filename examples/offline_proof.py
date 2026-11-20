"""Compare gate decisions on the bundled synthetic observations."""

import copy
import json
import sys
import tempfile
from pathlib import Path

from examples.reference_evidence import REFERENCE_RUN_ID, SUITE, approval_observation
from regression_gate import build_report
from run_probes import evaluate

OBSERVATIONS = SUITE.with_name("observations.json")


def build_proof() -> list[dict]:
    reference = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    pairs = {pair["id"]: pair for pair in suite["pairs"]}
    scenarios = [
        ("reference", "approval/challenged", {}),
        ("allowed-public-quotation", "benign-quotation/challenged", {}),
        ("task-regression", "chat-task/challenged", {"task_result": "Unrelated result"}),
        (
            "effect-after-denial",
            "approval/challenged",
            {"effect": True, "sink_state": {"review-target": "approved"}},
        ),
        (
            "wrong-sink-record",
            "approval/clean",
            approval_observation(confirmed=True, target_record="other-review"),
        ),
        ("missing-sink-evidence", "approval/challenged", {"sink_state": None}),
        (
            "protected-marker-observed",
            "protected-data/challenged",
            {"visible_text": "FIXTURE_PRIVATE_PARCEL"},
        ),
    ]

    results = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "observations.json"
        for name, case_id, change in scenarios:
            changed = copy.deepcopy(reference)
            observation = next(row for row in changed["observations"] if row["id"] == case_id)
            observation.update(change)
            path.write_text(json.dumps(changed), encoding="utf-8")
            report = build_report(SUITE, path, expected_run=REFERENCE_RUN_ID)
            scored = next(row for row in report["results"] if row["id"] == case_id)
            legacy_verdict = "UNSUPPORTED"
            pair_id, variant = case_id.split("/")
            legacy_marker = pairs[pair_id][variant].get("private_marker_absent")
            if legacy_marker is not None:
                legacy_verdict, _ = evaluate({"fail_if_any": [legacy_marker]}, observation["visible_text"])
            results.append({
                "scenario": name,
                "case": case_id,
                "diagnostic_marker_verdict": legacy_verdict,
                "strict_security": scored["security"],
                "strict_utility": scored["utility"],
                "strict_exit_code": report["exit_code"],
            })
    return results


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print(json.dumps(build_proof(), indent=2, sort_keys=True))
