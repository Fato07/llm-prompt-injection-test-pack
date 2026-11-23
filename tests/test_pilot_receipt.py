import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import regression_gate
from pilot import record


ROOT = Path(__file__).resolve().parents[1]


class PilotReceiptTests(unittest.TestCase):
    def test_receipt_keeps_partial_coverage_and_omits_raw_observations(self):
        evidence = json.loads((ROOT / "fixtures/observations.json").read_bytes())
        evidence["observations"].pop()
        evidence["observations"][0]["unused"] = "LOCAL_TEST_OBSERVATION"
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            observations = work / "observations.json"
            observations.write_text(json.dumps(evidence), encoding="utf-8")
            report = regression_gate.build_report(
                ROOT / "fixtures/suite.json", observations, expected_run="reference-v2",
            )
            (work / "reference-report.json").write_text(json.dumps(report), encoding="utf-8")
            (work / "reference-result.json").write_text('{"process_exit": 2}', encoding="utf-8")

            with patch.object(record, "WORK", work), patch("builtins.print"):
                record.write_receipt(record.REFERENCE_REVISION)

            receipt_text = (work / "receipt.json").read_text(encoding="utf-8")
            receipt = json.loads(receipt_text)
            reference = receipt["reference"]
            counts = reference["report"]["summary"]
            self.assertEqual((reference["process_exit"], counts["evaluable"], counts["planned"]), (2, 11, 12))
            self.assertIsNone(receipt["diagnosis"]["failed_assertion"])
            self.assertNotIn("LOCAL_TEST_OBSERVATION", receipt_text)
