# Offline regression gate release notes

The strict gate scores six paired workflows from saved synthetic observations. It reports policy outcomes and task completion independently, fails on missing evidence, and writes a versioned artifact suitable for reviewing a CI run. The dependency-free `--self-test` diagnostic quickstart remains available.

## Reproduce the proof

From the repository root with Python 3.10 or later, run the loopback demo, strict reference run, and offline tests. The demo has a deliberately leaky mock. Expect 36 diagnostic rows, with 2 passes, 34 marker findings and zero request errors. The strict reference should report 12 of 12 cases evaluable and exit `0`.

```sh
python3 run_probes.py --self-test
python3 run_probes.py --strict --suite fixtures/suite.json \
  --evidence fixtures/observations.json --json-out report-strict.json
python3 -m unittest discover -s tests -v
python3 -m examples.offline_proof
```

The strict reference artifact is [examples/strict-gate.json](examples/strict-gate.json). The proof script makes local, temporary copies of the reference observations, alters one recorded outcome at a time, and compares the existing diagnostic marker rule against the strict gate. It uses the same synthetic case observations for both scores. The report contains no response bodies. [Proof results](examples/proof-results.json)

| Scenario | Diagnostic marker rule | Strict result |
| --- | --- | --- |
| Reference, with the approval denied and no sink effect | `PASS` | All required outcomes held, exit `0` |
| Public quotation with a marker configured as forbidden in the legacy rule | `FAIL` | Legitimate result and private-data assertion held, exit `0` |
| Unrelated response to a legitimate task | `PASS` | Utility failed, exit `1` |
| Synthetic effect recorded after denial | `PASS` | Policy violation, exit `1` |
| Sink effect missing | `PASS` | Evidence incomplete, exit `2` |
| Private synthetic marker observed at the visible surface | `FAIL` | Policy violation, exit `1` |

This comparison measures scorer behavior on known synthetic observations. The actions and state in the approval and tenant examples are fixture data. Product verification depends on evidence from the application's own test harness. The CI workflow runs the same fixtures and contract tests with the standard library.

The local release check used fresh copies of the changes over base commit `18be285d4de24deaa3debd108ae4a7b93fc8a0f6`. All 12 tests passed on Python 3.10.20 and 3.14.7. The strict CLI returned the expected `0`, `1`, and `2` process statuses, and both example artifacts reproduced byte-for-byte on both interpreters.

## Publication and independent validation

Publication requires authorization to commit, push, open a PR, or cut a release. Once authorized, record the commit and fixture digests and publish the sanitized artifacts and reproduction instructions. The existing workflow definition can produce hosted CI evidence once published.

Recruit two independent pilot teams with authorized test harnesses. Record each team's time to its first successful offline score and whether it can explain one regression solely from the report. A comparison against other tools remains a separate measurement. Use equivalent static fixtures and disclose versions, setup, supported signals, and any scope mismatch before drawing a comparative conclusion.
