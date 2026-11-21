import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from examples.reference_evidence import SUITE, approval_observation

ROOT = SUITE.parents[1]


@unittest.skipUnless(shutil.which("bash"), "the CI recipe requires Bash")
class StrictCITests(unittest.TestCase):
    def test_ci_preserves_gate_exit_and_only_uses_fresh_reports(self):
        run_id = "test-revision.123.2"
        reference = json.loads(subprocess.check_output(
            [sys.executable, "-m", "examples.reference_evidence", "--run-id", run_id],
            cwd=ROOT,
        ))
        regression = copy.deepcopy(reference)
        rows = {row["id"]: row for row in regression["observations"]}
        rows["approval/clean"].update(approval_observation(confirmed=True, target_record="other-review"))
        rows["chat-task/challenged"]["task_result"] = "FIXTURE_UNRELATED_TASK_RESULT"
        incomplete = copy.deepcopy(regression)
        rows = {row["id"]: row for row in incomplete["observations"]}
        del rows["chat-task/challenged"]["task_result"]
        incomplete["observations"].remove(rows["tenant-scope/clean"])

        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            evidence = work / "evidence.json"
            summary = work / "job-summary.md"
            env = {
                **os.environ, "PYTHON": sys.executable,
                "RUNNER_TEMP": directory, "GITHUB_STEP_SUMMARY": str(summary),
            }
            scenarios = (
                ("fresh", json.dumps(reference), run_id, 0, ("12/12 cases evaluable",), (0, 0, 0)),
                ("regression", json.dumps(regression), run_id, 1, ("sink_state=violation", "task failed"), (1, 1, 0)),
                (
                    "incomplete", json.dumps(incomplete), run_id, 2,
                    ("task unscored", "tenant-scope/clean  incomplete (missing)", "visibility=inconclusive"), (1, 0, 2),
                ),
                ("stale", json.dumps(reference), "different-run", 2, ("expected run and suite",), None),
                ("malformed", "FIXTURE_RAW_ERROR", run_id, 2, ("invalid suite, evidence",), None),
            )
            for name, contents, expected_run, exit_code, details, counts in scenarios:
                with self.subTest(scenario=name):
                    evidence.write_text(contents, encoding="utf-8")
                    summary.write_text("", encoding="utf-8")
                    before = set(work.glob("strict-gate.*/strict-report.json"))
                    result = subprocess.run(
                        ["bash", str(ROOT / "examples/strict_ci.sh"), str(SUITE), str(evidence), expected_run],
                        cwd=work, env=env, capture_output=True, text=True,
                    )
                    markdown = summary.read_text(encoding="utf-8")
                    self.assertEqual(result.returncode, exit_code, result.stdout + result.stderr)
                    self.assertIn(f"Strict gate (exit {exit_code})", markdown)
                    for detail in details:
                        self.assertIn(detail, markdown)
                    new = set(work.glob("strict-gate.*/strict-report.json")) - before
                    shared = result.stdout + result.stderr + markdown
                    if counts is None:
                        self.assertTrue(before)
                        self.assertFalse(new)
                        self.assertIn("No fresh strict JSON report", markdown)
                        self.assertNotIn("12/12 cases evaluable", shared)
                    else:
                        [path] = new
                        data = path.read_text(encoding="utf-8")
                        shared += data
                        report = json.loads(data)
                        self.assertEqual(report["run_id"], expected_run)
                        self.assertEqual(report["exit_code"], exit_code)
                        self.assertEqual(tuple(
                            report["summary"][key] for key in ("violations", "task_failed", "task_unscored")
                        ), counts)
                    for sentinel in ("other-review", "FIXTURE_UNRELATED_TASK_RESULT", "FIXTURE_RAW_ERROR"):
                        self.assertNotIn(sentinel, shared)
