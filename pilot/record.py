"""Run the pinned offline gate and assemble a receipt without reading raw observations."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREVIEW = ROOT / "preview"
WORK = ROOT / "pilot-local"
REFERENCE_REVISION = "3acc3464725975e668e77ec9cf9cdc0a5563d73a"


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_bytes()) if path.is_file() else None


def revision() -> str:
    return subprocess.check_output(
        ["git", "-C", str(PREVIEW), "rev-parse", "HEAD"], text=True,
    ).strip()


def score(stage: str) -> None:
    report = WORK / f"{stage}-report.json"
    result = WORK / f"{stage}-result.json"
    if report.exists() or result.exists():
        raise SystemExit("This stage already ran. Use a fresh packet folder for a repeat.")

    suite = PREVIEW / "fixtures/suite.json"
    evidence = PREVIEW / "fixtures/observations.json"
    expected_run = "reference-v2"
    if stage == "diagnosis":
        evidence = ROOT / "pilot/case.json"
    if stage == "export":
        suite = WORK / "suite.json"
        evidence = WORK / "observations.json"
        expected_run = (WORK / "run-id.txt").read_text(encoding="utf-8").strip()

    expected_suite = hashlib.sha256(suite.read_bytes()).hexdigest()
    status = subprocess.run([
        sys.executable, str(PREVIEW / "run_probes.py"), "--strict",
        "--suite", str(suite), "--evidence", str(evidence),
        "--expect-run", expected_run, "--json-out", str(report),
    ]).returncode
    scored = read_json(report)
    details = {
        "process_exit": status,
        "expected_run_id": expected_run,
        "expected_suite_sha256": expected_suite,
    }
    if stage == "reference":
        started_ns = int((WORK / "reference-start.txt").read_text(encoding="utf-8"))
        details["elapsed_ns"] = time.monotonic_ns() - started_ns
    result.write_text(json.dumps(details), encoding="utf-8")
    coverage = scored["summary"] if scored is not None else None
    print(f"Gate exit {status}.", flush=True)
    if coverage is not None:
        print(f"Evaluable {coverage['evaluable']}/{coverage['planned']}. Report: {report}")
    else:
        print("No fresh strict report was written.")


def write_receipt(checkout_revision: str) -> None:
    reference = read_json(WORK / "reference-result.json") or {}
    reference["report"] = read_json(WORK / "reference-report.json")
    export = read_json(WORK / "export-result.json") or {}
    export["source"] = "example" if (WORK / "example-export.txt").is_file() else None
    export["collection_boundary"] = None
    export["blocker"] = None
    export["report"] = read_json(WORK / "export-report.json")
    receipt = {
        "kind": None,
        "team_alias": None,
        "team_role": None,
        "worked_without_coaching": None,
        "revision": checkout_revision,
        "python_version": platform.python_version(),
        "onboarding_blocker": None,
        "reference": reference,
        "diagnosis": {
            "process_exit": None, "case_id": None, "utility": None,
            "failed_assertion": None, "explanation": None,
        },
        "export": export,
    }
    path = WORK / "receipt.json"
    with path.open("x", encoding="utf-8") as file:
        json.dump(receipt, file, indent=2)
        file.write("\n")
    print(f"Fill in the participant fields in {path}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("start", "reference", "diagnosis", "export", "receipt"))
    args = parser.parse_args()
    checkout_revision = revision()
    if checkout_revision != REFERENCE_REVISION or not WORK.is_dir():
        raise SystemExit("Run the packet setup with the pinned preview before collecting evidence.")
    if args.stage == "start":
        with (WORK / "reference-start.txt").open("x", encoding="utf-8") as file:
            file.write(str(time.monotonic_ns()))
    elif args.stage == "receipt":
        write_receipt(checkout_revision)
    else:
        score(args.stage)


if __name__ == "__main__":
    main()
