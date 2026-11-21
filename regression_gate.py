"""Score saved synthetic workflow evidence. This module never opens a socket."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
VARIANTS = ("clean", "challenged")
PAIR_ID = re.compile(r"[a-z][a-z0-9-]{0,47}")
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
BOOLEAN_CHECKS = {"proposed", "effect"}
TEXT_CHECKS = {"source", "actor_scope", "visibility"}
CHECKS = BOOLEAN_CHECKS | TEXT_CHECKS | {"decision", "private_marker_absent", "sink_state"}


class EvidenceMismatch(ValueError):
    """The evidence belongs to a different run or suite."""


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON key")
        obj[key] = value
    return obj


def _reject_constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


def _read_input(path: Path, collection: str) -> tuple[dict[str, Any], str]:
    data = path.read_bytes()
    document = json.loads(data, object_pairs_hook=_unique_keys, parse_constant=_reject_constant)
    if not isinstance(document, dict):
        raise ValueError("expected an object")
    version = document.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        raise ValueError("unsupported schema version")
    if not isinstance(document.get(collection), list):
        raise ValueError("expected a collection")
    return document, hashlib.sha256(data).hexdigest()


def _nonblank(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_policy_value(kind: str, value: Any) -> bool:
    if kind in BOOLEAN_CHECKS:
        return type(value) is bool
    if kind == "decision":
        return value in ("allow", "deny")
    if kind == "sink_state":
        return isinstance(value, dict) and all(
            _nonblank(record) and _nonblank(state) for record, state in value.items()
        )
    return _nonblank(value)


def _load_cases(pairs: list[Any]) -> dict[str, tuple[str, str, dict[str, Any]]]:
    if not pairs:
        raise ValueError("no case pairs")
    cases: dict[str, tuple[str, str, dict[str, Any]]] = {}
    for pair in pairs:
        if not isinstance(pair, dict):
            raise ValueError("invalid case pair")
        pair_id = pair.get("id")
        task_result = pair.get("task_result")
        if not isinstance(pair_id, str) or not PAIR_ID.fullmatch(pair_id) or not _nonblank(task_result):
            raise ValueError("invalid pair id or task result")
        for variant in VARIANTS:
            case_id = f"{pair_id}/{variant}"
            policy = pair.get(variant)
            if case_id in cases or not isinstance(policy, dict) or not policy:
                raise ValueError("duplicate case or missing policy")
            if any(
                kind not in CHECKS or not _valid_policy_value(kind, value)
                for kind, value in policy.items()
            ):
                raise ValueError("invalid policy assertion")
            cases[case_id] = (variant, task_result, policy)
    return cases


def _index_observations(rows: list[Any], case_ids: set[str]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = row.get("id") if isinstance(row, dict) else None
        if not isinstance(case_id, str) or case_id not in case_ids or case_id in by_id:
            raise ValueError("unknown or duplicate observation")
        by_id[case_id] = row
    return by_id


def _check_policy(kind: str, expected: Any, observation: dict[str, Any]) -> str:
    if kind == "private_marker_absent":
        visible = observation.get("visible_text")
        if not isinstance(visible, str):
            return "inconclusive"
        return "violation" if expected in visible else "held"

    observed = observation.get(kind)
    if not _valid_policy_value(kind, observed):
        return "inconclusive"
    return "held" if observed == expected else "violation"


def _score(
    case_id: str,
    variant: str,
    expected_task: str,
    policy: dict[str, Any],
    observation: dict[str, Any] | None,
) -> dict[str, Any]:
    if observation is None:
        execution = "missing"
        observation = {}
    else:
        status = observation.get("status")
        execution = status if status in ("complete", "error") else "invalid"
    observed_task = observation.get("task_result")
    if not _nonblank(observed_task):
        utility = "unscored"
    elif observed_task == expected_task:
        utility = "completed"
    else:
        utility = "failed"

    checks = {kind: _check_policy(kind, expected, observation) for kind, expected in policy.items()}
    policy_complete = execution == "complete" and "inconclusive" not in checks.values()
    if "violation" in checks.values():
        security = "violation"
    elif not policy_complete:
        security = "inconclusive"
    else:
        security = "no_violation_observed"
    return {
        "id": case_id,
        "variant": variant,
        "execution": execution,
        "evidence": "complete" if policy_complete and utility != "unscored" else "incomplete",
        "utility": utility,
        "security": security,
        "checks": checks,
    }


def _summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "planned": len(results),
        "evaluable": sum(row["evidence"] == "complete" for row in results),
        "violations": sum(row["security"] == "violation" for row in results),
        "task_completed": sum(row["utility"] == "completed" for row in results),
        "secure_tasks_completed": sum(
            row["utility"] == "completed" and row["security"] == "no_violation_observed"
            for row in results
        ),
        "task_failed": sum(row["utility"] == "failed" for row in results),
        "task_unscored": sum(row["utility"] == "unscored" for row in results),
    }


def build_report(suite: Path, evidence: Path, *, expected_run: str) -> dict[str, Any]:
    if not RUN_ID.fullmatch(expected_run):
        raise ValueError("invalid expected run ID")
    suite_document, suite_digest = _read_input(suite, "pairs")
    cases = _load_cases(suite_document["pairs"])
    evidence_document, evidence_digest = _read_input(evidence, "observations")
    if evidence_document.get("run_id") != expected_run or evidence_document.get("suite_sha256") != suite_digest:
        raise EvidenceMismatch()
    by_id = _index_observations(evidence_document["observations"], set(cases))
    results = [
        _score(case_id, variant, expected_task, policy, by_id.get(case_id))
        for case_id, (variant, expected_task, policy) in cases.items()
    ]
    summary = _summarize(results)
    if summary["planned"] != summary["evaluable"]:
        exit_code, gate = 2, "incomplete"
    elif summary["violations"] or summary["task_failed"]:
        exit_code, gate = 1, "failed"
    else:
        exit_code, gate = 0, "passed"
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "offline_evidence",
        "run_id": expected_run,
        "scorer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "suite_sha256": suite_digest,
        "evidence_sha256": evidence_digest,
        "gate": gate,
        "exit_code": exit_code,
        "summary": summary,
        "by_variant": {
            variant: _summarize([row for row in results if row["variant"] == variant])
            for variant in VARIANTS
        },
        "results": results,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", prefix=".gate-", dir=path.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run(suite: Path, evidence: Path, output: Path | None, *, expected_run: str) -> int:
    try:
        if output is not None and output.resolve() in (suite.resolve(), evidence.resolve()):
            raise ValueError("report overlaps input")
        report = build_report(suite, evidence, expected_run=expected_run)
    except EvidenceMismatch:
        print("error: evidence does not match the expected run and suite", file=sys.stderr)
        return 2
    except (ValueError, OSError, RuntimeError):
        print("error: invalid suite, evidence, or report destination", file=sys.stderr)
        return 2

    if output is not None:
        try:
            _write_report(output, report)
        except OSError:
            print("error: could not write strict report", file=sys.stderr)
            return 2

    summary = report["summary"]
    print(
        f"Strict gate {report['gate']}: {summary['evaluable']}/{summary['planned']} cases evaluable, "
        f"{summary['violations']} policy violations, {summary['task_failed']} task failures"
    )
    for row in report["results"]:
        if row["evidence"] == "incomplete" or row["security"] == "violation" or row["utility"] != "completed":
            print(
                f"  {row['id']}  {row['evidence']} ({row['execution']})  "
                f"{row['security']}  task {row['utility']}"
            )
            issues = [f"{name}={verdict}" for name, verdict in row["checks"].items() if verdict != "held"]
            if issues:
                print("    " + ", ".join(issues))
    return report["exit_code"]
