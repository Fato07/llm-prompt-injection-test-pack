# Offline regression gate release notes

The strict gate scores six paired workflows from saved synthetic observations. It reports policy outcomes and task completion independently, fails on missing evidence, and writes a versioned artifact suitable for reviewing a CI run. The dependency-free `--self-test` diagnostic quickstart remains available.

## Reproduce the proof

From the repository root with Python 3.10 or later, run the loopback demo, strict reference run, and offline tests. The demo has a deliberately leaky mock. Expect 36 diagnostic rows, with 2 passes, 34 marker findings and zero request errors. The strict reference should report 12 of 12 cases evaluable and exit `0`.

```sh
python3 run_probes.py --self-test
python3 run_probes.py --strict --suite fixtures/suite.json \
  --evidence fixtures/observations.json --expect-run reference-v2 --json-out report-strict.json
python3 -m unittest discover -s tests -v
python3 -m examples.reference_evidence
python3 -m examples.offline_proof
```

The strict reference artifact is [examples/strict-gate.json](examples/strict-gate.json). The reference generator produces synthetic evidence, including approval observations from an in-memory fake sink. The proof script varies one scenario at a time. Where a case has a marker assertion, both modes inspect the same visible text for the same private marker. The diagnostic has no oracle for task completion or sink effects, so those comparisons are labeled unsupported. [Proof results](examples/proof-results.json)

| Scenario | Diagnostic marker rule | Strict result |
| --- | --- | --- |
| Reference, with the approval denied and no sink effect | Unsupported | All required outcomes held, exit `0` |
| Public quotation with the same private marker policy in both modes | `PASS` | Legitimate result and private-data assertion held, exit `0` |
| Unrelated response to a legitimate task | Unsupported | Utility failed, exit `1` |
| Synthetic effect recorded after denial | Unsupported | Policy violation, exit `1` |
| Allowed action writes the wrong fake record | Unsupported | Sink state violation, exit `1` |
| Sink snapshot missing | Unsupported | Evidence incomplete, exit `2` |
| Private synthetic marker observed at the visible surface | `FAIL` | Policy violation, exit `1` |

This comparison measures scorer behavior on known synthetic observations. The public quotation illustrates why an assertion must identify the private marker. Configuring the public phrase as the forbidden marker would test a different policy. Product verification depends on evidence from the application's own test harness. The CI workflow runs the same fixtures and contract tests with the standard library.

The contract tests cover stale run IDs, changed suite bytes, wrong-record effects, malformed evidence, and legacy diagnostic compatibility. The checked-in reference files use LF so Git line-ending conversion does not change their digests.

## Stable release checklist

- Record the candidate commit and fixture digests. Verify the offline workflow passes for the candidate and retain the sanitized reports.
- Collect one uncoached `receipt.json` per role from the [pilot kit](PILOT.md). Both receipts must show 12/12 evaluable reference cases, elapsed time against the five-minute target, and a correct diagnosis based on the report. At least one must show a complete v2 export from the participant's own synthetic harness.
- Review the sanitized receipts and resolve conflicting results and recurring blockers. Keep raw evidence, reviewer materials, and rehearsal receipts private. Rehearsals do not count toward independent validation.
