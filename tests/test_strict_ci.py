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
    def test_consumer_check_runs_skips_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "examples").mkdir()
            for path in ("regression_gate.py", "run_probes.py", "examples/consumer_ci.sh",
                         "examples/strict_ci.sh", "examples/approval_evidence.py", "examples/approval-suite.json",
                         "examples/retrieval_evidence.py", "examples/retrieval-suite.json"):
                shutil.copyfile(ROOT / path, root / path)

            def git(*args):
                return subprocess.check_output(
                    ["git", "-c", "user.name=Local", "-c", "user.email=local@example.invalid",
                     "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args], cwd=root, text=True,
                ).strip()

            git("init", "-q")
            git("add", ".")
            git("commit", "-qm", "synthetic base")
            base = git("rev-parse", "HEAD")
            summary = root / "summary.md"

            def check(role, expected_exit, message, base_sha=base):
                summary.write_text("")
                result = subprocess.run(
                    ["bash", "examples/consumer_ci.sh", role, base_sha, "fixture-ci-run"], cwd=root,
                    env={**os.environ, "RUNNER_TEMP": directory, "PYTHON": sys.executable,
                         "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_OUTPUT": ""},
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, expected_exit, result.stdout + result.stderr)
                self.assertIn(message, result.stdout + result.stderr)
                self.assertIn(message, summary.read_text())
                self.assertFalse(list(root.glob("consumer-evidence.*")))

            (root / "README.md").write_text("Synthetic documentation edit.\n")
            git("add", "README.md")
            git("commit", "-qm", "docs only")
            check("approval", 0, "gate was not needed")
            check("retrieval", 0, "gate was not needed")
            check("approval", 2, "Could not compare", "0" * 40)
            for role, count in (("approval", "4/4"), ("retrieval", "2/2")):
                suite = root / f"examples/{role}-suite.json"
                document = json.loads(suite.read_bytes())
                suite.write_text(json.dumps(document))
                git("commit", "-qam", f"reformat {role} suite")
                check(role, 0, f"{count} cases evaluable")
                policy = document["pairs"][0]["clean"]
                if role == "approval":
                    binding = policy["approval_binding"]
                    binding["approved"]["target"] = "fixture-other"
                    binding["dispatches"][0]["target"] = "fixture-other"
                    assertion = "approval_binding"
                else:
                    policy["retrieved_sources"].pop()
                    assertion = "retrieved_sources"
                suite.write_text(json.dumps(document))
                git("commit", "-qam", f"change {role} expectation")
                check(role, 1, f"{assertion}=violation")
                document["schema_version"] = 1
                suite.write_text(json.dumps(document))
                git("commit", "-qam", "invalid suite version")
                check(role, 2, "invalid schema_version")

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
            outputs = work / "step-outputs.txt"
            env = {
                **os.environ, "PYTHON": sys.executable,
                "RUNNER_TEMP": directory, "GITHUB_STEP_SUMMARY": str(summary),
                "GITHUB_OUTPUT": str(outputs),
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
                    outputs.write_text("", encoding="utf-8")
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
                        self.assertEqual(outputs.read_text(encoding="utf-8"), "")
                        self.assertIn("No fresh strict JSON report", markdown)
                        self.assertNotIn("12/12 cases evaluable", shared)
                    else:
                        [path] = new
                        self.assertEqual(outputs.read_text(encoding="utf-8"), f"report_path={path}\n")
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
