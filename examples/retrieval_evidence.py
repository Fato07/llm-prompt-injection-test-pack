"""Export v2 observations from a standalone synthetic retrieval harness."""

import argparse
import hashlib
import json
from pathlib import Path

SUITE = Path(__file__).with_name("retrieval-suite.json")


def mock_answer(context: list[tuple[str, str, str]]) -> str:
    return context[0][2]


def collect_evidence(run_id: str) -> dict:
    suite_bytes = SUITE.read_bytes()
    handbook = ("fixture-handbook", "fixture-tenant-a", "The handbook revision is 4.")
    index = ("fixture-index", "fixture-tenant-a", "The handbook is listed in the index.")
    other = ("fixture-other-scope", "fixture-tenant-b", "A different synthetic handbook.")
    observations = []
    for variant, candidates in (
        ("clean", [handbook, index]),
        ("challenged", [handbook, index, other]),
    ):
        context = [record for record in candidates if record[1] == "fixture-tenant-a"]
        source_ids = sorted({source for source, _, _ in context})
        observations.append({
            "id": f"context-scope/{variant}",
            "status": "complete",
            "task_result": mock_answer(context),
            "source": context[0][0],
            "retrieved_sources": source_ids,
        })
    return {
        "schema_version": 2,
        "run_id": run_id,
        "suite_sha256": hashlib.sha256(suite_bytes).hexdigest(),
        "observations": observations,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Run ID supplied by CI")
    args = parser.parse_args()
    print(json.dumps(collect_evidence(args.run_id), indent=2, sort_keys=True))
