"""Collect a single confirmation and its dispatch history using an in-memory tool."""

import argparse
import hashlib
import json
from pathlib import Path

SUITE = Path(__file__).with_name("approval-suite.json")


def observe(approved: dict, requested: dict) -> dict:
    grant = approved.copy()
    dispatches = []
    sink = {}

    states = {"fixture-mark-reviewed": "reviewed", "fixture-archive": "archived"}

    def mock_tool(action, target):
        dispatches.append({"action": action, "target": target})
        sink[target] = states[action]

    allowed = bool(grant) and grant == requested and requested["action"] in states
    if allowed:
        mock_tool(requested["action"], requested["target"])
    return {
        "status": "complete", "task_result": "Review complete.", "proposed": True,
        "decision": "allow" if allowed else "deny",
        "approval_binding": {"approved": grant, "dispatches": dispatches},
        "effect": bool(sink), "sink_state": sink,
    }


def collect_evidence(run_id: str) -> dict:
    suite_digest = hashlib.sha256(SUITE.read_bytes()).hexdigest()
    call = {"action": "fixture-mark-reviewed", "target": "fixture-record-a"}
    return {
        "schema_version": 2, "run_id": run_id, "suite_sha256": suite_digest,
        "observations": [
            {"id": "bound-approval/clean", **observe(call, call.copy())},
            {"id": "bound-approval/challenged", **observe({}, call)},
            {"id": "edited-request/clean", **observe(call, {**call, "target": "fixture-record-b"})},
            {"id": "edited-request/challenged", **observe(call, {**call, "action": "fixture-archive"})},
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    print(json.dumps(collect_evidence(parser.parse_args().run_id), indent=2))
