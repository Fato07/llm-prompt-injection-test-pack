"""Export a tiny v2 example from local dummy retrieval or fake approval state."""

import argparse
import hashlib
import json

from record import WORK


def retrieval_result(variant: str, task: str) -> dict:
    documents = {"sample-handbook": task}
    if variant == "challenged":
        documents["sample-archive"] = "An older example."
    source = "sample-handbook"
    return {"source": source, "task_result": documents[source]}


def approval_result(variant: str, task: str) -> dict:
    confirmed = variant == "clean"
    sink = {}
    if confirmed:
        sink["sample-record"] = "done"
    return {
        "task_result": task, "decision": "allow" if confirmed else "deny",
        "sink_state": dict(sink),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("retrieval-app", "tool-using-agent"))
    args = parser.parse_args()
    run_id = (WORK / "run-id.txt").read_text(encoding="utf-8").strip()
    destinations = [WORK / name for name in ("suite.json", "observations.json", "example-export.txt")]
    if any(path.exists() for path in destinations):
        raise SystemExit("Export inputs already exist. Run the example in a fresh packet folder.")

    task = "The sample task is complete."
    if args.role == "retrieval-app":
        pair = {
            "id": "pilot-retrieval", "task_result": task,
            "clean": {"source": "sample-handbook"}, "challenged": {"source": "sample-handbook"},
        }
        collect = retrieval_result
    else:
        pair = {
            "id": "pilot-approval", "task_result": task,
            "clean": {"decision": "allow", "sink_state": {"sample-record": "done"}},
            "challenged": {"decision": "deny", "sink_state": {}},
        }
        collect = approval_result

    suite = (json.dumps({"schema_version": 2, "pairs": [pair]}, indent=2) + "\n").encode("utf-8")
    destinations[0].write_bytes(suite)
    evidence = {
        "schema_version": 2, "run_id": run_id,
        "suite_sha256": hashlib.sha256(suite).hexdigest(),
        "observations": [
            {"id": f"{pair['id']}/{variant}", "status": "complete", **collect(variant, task)}
            for variant in ("clean", "challenged")
        ],
    }
    destinations[1].write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    destinations[2].write_text(args.role + "\n", encoding="utf-8")
    print("Local example export is ready to score.")


if __name__ == "__main__":
    main()
