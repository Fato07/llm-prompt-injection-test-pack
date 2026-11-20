import contextlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import regression_gate
import run_probes

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "fixtures" / "suite.json"
OBSERVATIONS = ROOT / "fixtures" / "observations.json"


class StrictGateTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.evidence = self.directory / "evidence.json"
        self.output = self.directory / "report.json"
        self.observations = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))

    def observation(self, case_id):
        return next(row for row in self.observations["observations"] if row["id"] == case_id)

    def run_gate(self, *, suite=SUITE, output=None, extra=()):
        self.evidence.write_text(json.dumps(self.observations), encoding="utf-8")
        argv = [
            "--strict", "--suite", str(suite), "--evidence", str(self.evidence),
            "--json-out", str(self.output if output is None else output), *extra,
        ]
        terminal = io.StringIO()
        with (
            contextlib.redirect_stdout(terminal),
            contextlib.redirect_stderr(terminal),
            patch("socket.socket", side_effect=AssertionError("strict gate used a socket")),
        ):
            status = run_probes.main(argv)
        return status, terminal.getvalue()

    def report(self):
        return json.loads(self.output.read_text(encoding="utf-8"))

    def test_clean_pairs_pass_with_a_redacted_reproducible_report(self):
        self.observation("protected-data/clean")["unused_raw_field"] = "FIXTURE_RAW_TRANSCRIPT"
        status, output = self.run_gate()
        self.assertEqual(status, 0)
        report = self.report()
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["summary"]["evaluable"], 12)
        self.assertEqual(report["summary"]["secure_tasks_completed"], 12)
        self.assertEqual(report["by_variant"]["clean"]["task_completed"], 6)
        self.assertEqual(report["by_variant"]["challenged"]["task_completed"], 6)
        for sentinel in ("EXAMPLE_REFERENCE", "FIXTURE_PRIVATE_PARCEL", "FIXTURE_RAW_TRANSCRIPT"):
            self.assertNotIn(sentinel, output + self.output.read_text(encoding="utf-8"))
        first = self.output.read_bytes()
        self.assertEqual(self.run_gate()[0], 0)
        self.assertEqual(self.output.read_bytes(), first)

    def test_task_failure_and_unauthorized_effect_are_independent(self):
        self.observation("chat-task/challenged")["task_result"] = "Unrelated result"
        self.observation("approval/challenged")["effect"] = True
        self.assertEqual(self.run_gate()[0], 1)
        report = self.report()
        self.assertEqual(report["summary"]["secure_tasks_completed"], 10)
        rows = {row["id"]: row for row in report["results"]}
        chat = rows["chat-task/challenged"]
        self.assertEqual((chat["utility"], chat["security"]), ("failed", "no_violation_observed"))
        approval = rows["approval/challenged"]
        self.assertEqual((approval["utility"], approval["security"]), ("completed", "violation"))
        self.assertEqual(approval["checks"], {"proposed": "held", "decision": "held", "effect": "violation"})

    def test_incomplete_evidence_preserves_an_observed_violation(self):
        private = "FIXTURE_PRIVATE_PARCEL"
        self.observation("protected-data/challenged")["visible_text"] = private
        del self.observation("approval/challenged")["effect"]
        self.observation("chat-task/challenged")["task_result"] = " "
        self.observations["observations"].remove(self.observation("tenant-scope/clean"))
        status, terminal = self.run_gate()
        self.assertEqual(status, 2)
        report = self.report()
        self.assertEqual(report["summary"]["violations"], 1)
        self.assertEqual(report["summary"]["evaluable"], 9)
        rows = {row["id"]: row for row in report["results"]}
        self.assertEqual(rows["approval/challenged"]["checks"]["effect"], "inconclusive")
        self.assertEqual(rows["chat-task/challenged"]["utility"], "unscored")
        self.assertEqual(rows["chat-task/challenged"]["security"], "no_violation_observed")
        self.assertEqual(rows["tenant-scope/clean"]["execution"], "missing")
        self.assertNotIn(private, terminal + self.output.read_text(encoding="utf-8"))

    def test_error_cannot_be_counted_as_complete(self):
        row = self.observation("approval/challenged")
        row.update(status="error", error="FIXTURE_RAW_ERROR")
        status, terminal = self.run_gate()
        self.assertEqual(status, 2)
        [approval] = [item for item in self.report()["results"] if item["id"] == row["id"]]
        self.assertEqual(approval["execution"], "error")
        self.assertEqual(approval["security"], "inconclusive")
        self.assertNotIn("FIXTURE_RAW_ERROR", terminal + self.output.read_text(encoding="utf-8"))

    def test_duplicate_or_unknown_records_do_not_produce_a_report(self):
        rows = self.observations["observations"]
        for case_id in (rows[0]["id"], "unknown/clean"):
            with self.subTest(case_id=case_id):
                rows.append({"id": case_id})
                self.assertEqual(self.run_gate()[0], 2)
                self.assertFalse(self.output.exists())
                rows.pop()

    def test_invalid_suite_and_report_destination_fail_closed(self):
        suite = self.directory / "invalid-suite.json"
        suite.write_text('{"schema_version": 1, "pairs": [], "pairs": []}', encoding="utf-8")
        self.assertEqual(self.run_gate(suite=suite)[0], 2)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.run_gate(output=self.evidence)[0], 2)
        self.assertEqual(json.loads(self.evidence.read_text(encoding="utf-8")), self.observations)
        self.assertEqual(self.run_gate(output=self.directory)[0], 2)
        self.assertEqual(list(self.directory.glob(".gate-*")), [])

    def test_strict_rejects_a_target_or_credential(self):
        self.assertEqual(self.run_gate(extra=("--base-url", "http://127.0.0.1:1/v1"))[0], 2)
        self.assertEqual(self.run_gate(extra=("--api-key", "FIXTURE_UNUSED"))[0], 2)
        self.assertFalse(self.output.exists())

    def test_committed_example_matches_the_reference_run(self):
        saved = ROOT / "examples" / "strict-gate.json"
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8")), regression_gate.build_report(SUITE, OBSERVATIONS))


class DiagnosticTests(unittest.TestCase):
    def test_explicit_empty_key_does_not_use_environment_key(self):
        with (
            patch.dict(os.environ, {"OPENAI_API_KEY": "FIXTURE_DONT_SEND"}),
            patch("run_probes.run_diagnostic", return_value=0) as diagnostic,
        ):
            status = run_probes.main(["--base-url", "http://127.0.0.1:1/v1", "--api-key", ""])
        self.assertEqual(status, 0)
        self.assertEqual(diagnostic.call_args.args[0].api_key, "none")

    def test_demo_keeps_legacy_report_shape_and_uses_a_dummy_key(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            env = {"OPENAI_API_KEY": "FIXTURE_DONT_SEND", "http_proxy": "http://127.0.0.1:1"}
            with (
                patch.dict(os.environ, env),
                patch("run_probes.chat_complete", wraps=run_probes.chat_complete) as complete,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                status = run_probes.main(["--self-test", "--json-out", str(report)])
            self.assertEqual(status, 0)
            self.assertEqual({call.args[1] for call in complete.call_args_list}, {"test"})
            rows = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(len(rows), 36)
            self.assertEqual(set(rows[0]), {"id", "category", "name", "hits", "reply", "error", "result"})
            self.assertEqual(sum(row["result"] == "FAIL" for row in rows), 34)

    def test_invalid_diagnostic_case_stops_before_transport(self):
        cases = [{"id": "fixture", "category": "fixture", "name": "Missing assertions", "messages": [{}]}]
        with tempfile.TemporaryDirectory() as directory:
            suite = Path(directory) / "probes.json"
            suite.write_text(json.dumps(cases), encoding="utf-8")
            with patch("run_probes.chat_complete") as complete, contextlib.redirect_stderr(io.StringIO()):
                status = run_probes.main(["--self-test", "--probes", str(suite)])
        self.assertEqual(status, 2)
        complete.assert_not_called()

    def test_transport_rejects_blank_and_hides_error_bodies(self):
        response = {"choices": [{"message": {"content": "  "}}]}
        request_args = ("http://127.0.0.1:1/v1", "fixture", "fixture", "", [], 1)
        with patch.object(run_probes.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
            with self.assertRaisesRegex(RuntimeError, "^API returned no scoreable text$"):
                run_probes.chat_complete(*request_args)
        error = urllib.error.HTTPError("http://127.0.0.1:1", 429, "fixture", {}, io.BytesIO(b"FIXTURE_RAW_ERROR"))
        with patch.object(run_probes.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "^HTTP 429$"):
                run_probes.chat_complete(*request_args)


if __name__ == "__main__":
    unittest.main()
