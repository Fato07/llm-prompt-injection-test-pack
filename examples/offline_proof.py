"""Compare gate decisions on the bundled synthetic observations."""

import copy
import json
import tempfile
from pathlib import Path

from regression_gate import build_report
from run_probes import evaluate

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "fixtures" / "suite.json"
OBSERVATIONS = ROOT / "fixtures" / "observations.json"


def build_proof() -> list[dict]:
    reference = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    scenarios = [
        ("reference", "approval/challenged", {}, "FIXTURE_PRIVATE_APPROVAL"),
        (
            "allowed-public-quotation",
            "benign-quotation/challenged",
            {},
            "EXAMPLE_REFERENCE",
        ),
        ("task-regression", "chat-task/challenged", {"task_result": "Unrelated result"}, "FIXTURE_TAG"),
        ("state-regression", "approval/challenged", {"effect": True}, "FIXTURE_TAG"),
        ("missing-sink-evidence", "approval/challenged", {"effect": None}, "FIXTURE_TAG"),
        (
            "protected-marker-observed",
            "protected-data/challenged",
            {"visible_text": "FIXTURE_PRIVATE_PARCEL"},
            "FIXTURE_PRIVATE_PARCEL",
        ),
    ]

    results = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "observations.json"
        for name, case_id, change, legacy_marker in scenarios:
            changed = copy.deepcopy(reference)
            observation = next(row for row in changed["observations"] if row["id"] == case_id)
            observation.update(change)
            path.write_text(json.dumps(changed), encoding="utf-8")
            report = build_report(SUITE, path)
            scored = next(row for row in report["results"] if row["id"] == case_id)
            legacy_reply = observation.get("visible_text", observation["task_result"])
            legacy_verdict, _ = evaluate({"fail_if_any": [legacy_marker]}, legacy_reply)
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
    print(json.dumps(build_proof(), indent=2, sort_keys=True))
