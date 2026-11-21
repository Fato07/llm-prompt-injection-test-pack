# Strict evidence format

The strict gate consumes a versioned suite and an evidence file emitted by a local test harness. Use synthetic records and sanitized identifiers. The gate scores the observations you supply. Confidence in a result depends on how the test harness collected those observations and which surfaces it covered.

```sh
python3 run_probes.py --strict --suite fixtures/suite.json \
  --evidence fixtures/observations.json --expect-run reference-v2 --json-out report-strict.json
```

## Suite and observations

The suite has `schema_version: 2` and a nonempty `pairs` array. Give each pair a unique lowercase `id` of up to 48 characters, using letters, digits or hyphens and starting with a letter. IDs appear in reports and terminal output, so use fixture labels. Each pair declares one exact, nonblank `task_result` shared by its `clean` and `challenged` variants. Each variant declares one or more policy assertions.

| Suite assertion | Observation field | Meaning |
| --- | --- | --- |
| `source` | `source` | Exact source label recorded by the application |
| `private_marker_absent` | `visible_text` | A synthetic private marker must be absent from the declared visible surface. An explicitly observed empty string is valid. |
| `proposed` | `proposed` | Exact boolean for whether the synthetic action was proposed |
| `decision` | `decision` | Exact policy decision, `allow` or `deny` |
| `effect` | `effect` | Exact boolean for whether an effect occurred at the observed sink |
| `sink_state` | `sink_state` | Exact record-to-value map observed in the test's isolated sink scope. An observed empty map represents an empty scope. |
| `actor_scope` | `actor_scope` | Exact actor scope recorded at the authorization boundary |
| `visibility` | `visibility` | Exact resource scope visible at the observed boundary |

An evidence file has `schema_version: 2`, a `run_id`, the lowercase hexadecimal SHA-256 of the exact suite bytes in `suite_sha256`, and an `observations` array. Choose a non-secret `run_id` of up to 128 characters, starting with a letter or digit and containing only ASCII letters, digits, dots, underscores, and hyphens. The bundled demo uses the fixed ID `reference-v2`.

For a real CI gate, derive a fresh ID from the build revision and unique run or attempt ID in the orchestrator. Pass that expected ID into both your evidence collector and `--expect-run` independently of the saved evidence. The collector stamps the ID and suite digest at collection time. Missing or mismatched metadata returns exit `2` before scoring. This binding relies on the integrity of the collector and CI job.

Each observation has a case ID in the form `pair-id/clean` or `pair-id/challenged` and a `status` of `complete` or `error`. Supply the observed task result and fields required by that case. A missing row or a missing or ill-typed required value makes the case incomplete. Duplicate keys, nonstandard JSON constants, duplicate observation IDs, and unknown case IDs make the input invalid. Extra observation fields have no effect on scoring.

Collect the task result from the workflow output. Collect provenance, actor scope, and approval evidence from the corresponding application boundary. Collect effects from the observed sink and use `false` only when the sink was inspected. An approval trace can show a proposal, a denial, no effect, and an empty sink snapshot. For the allowed path, compare the snapshot to the expected record and value so a write to a different record fails. The bundled approval observations come from an in-memory fake sink.

## Reading the report

The JSON object includes `schema_version`, `mode`, the verified `run_id`, SHA-256 digests of the scorer and both input files, the gate and exit code, total and per-variant counts, and ordered case verdicts. Digests identify the exact local bytes used. Case records contain evidence coverage, execution status, security, utility, and the outcome of each named policy assertion.

A case can preserve its security verdict when task scoring is unavailable. A confirmed violation stays visible in an incomplete run. Report counts include those known violations. Compare `evaluable` with `planned` when interpreting the other totals.

| Exit | Meaning |
| --- | --- |
| `0` | All planned cases are evaluable and expected policy and task outcomes held |
| `1` | All planned cases are evaluable and at least one policy or task regression was observed |
| `2` | Evidence is mismatched or incomplete, input is invalid, or the requested report could not be written |

A bound but incomplete run writes a report when a destination is supplied. Invalid input, a binding mismatch, or a write failure can produce no fresh report. Use a unique report path in CI and treat the process exit as authoritative. Completed reports are written by atomic replacement.

Strict reports omit observed replies, marker and sink values, raw errors, and credentials. Access to the evidence file should remain local to the test environment. The SHA-256 digests and run and case labels are safe to share for the bundled synthetic files. Review labels before exporting custom reports.

## CI recipe

Use the [offline GitHub Actions step](.github/workflows/offline.yml) as the starting point. It checks out the exact PR head and uses that revision, the run ID, attempt, and Python matrix version to identify the run. Rehearse the same workflow with a local checkout and a shell that has Bash. Change `pack_root` to the path of the pack if running from a consumer repository.

```bash
(
  set -eu
  pack_root="$PWD"
  RUNNER_TEMP=$(mktemp -d "${TMPDIR:-/tmp}/strict-ci.XXXXXXXX")
  export RUNNER_TEMP
  run_id="local.$(git -C "$pack_root" rev-parse HEAD).${RUNNER_TEMP##*/}"
  evidence="$RUNNER_TEMP/observations.json"
  (cd "$pack_root" && python3 -m examples.reference_evidence --run-id "$run_id") > "$evidence"
  bash "$pack_root/examples/strict_ci.sh" "$pack_root/fixtures/suite.json" "$evidence" "$run_id"
)
```

The reference collector creates v2 evidence for the bundled suite. For a consumer integration, replace the collector and suite with your local harness and expectations. Give the collector the run ID before it executes and have it hash the exact suite bytes it used. Pass the same CI-provided ID independently to the gate.

The script creates a new private directory for each report under `RUNNER_TEMP` or the system temp directory. It prints the report path when available and preserves the scorer's exit when it writes the GitHub step summary. The summary names failed or inconclusive assertions and reports task and evidence status without exposing observed values. Exit `2` with no report means there is no current JSON artifact. Keep evidence and suite inputs out of shared CI output and discard the local temp files when finished.

Read these report fields independently:

| Signal | Where to look |
| --- | --- |
| Policy failure | `security: violation` and the failing name in `checks` |
| Task result differs from the expected result | `utility: failed` |
| No scoreable task result was recorded | `utility: unscored` and `evidence: incomplete` |
| A case or required observation is missing or invalid | `evidence: incomplete`, with `execution` and `checks` showing which information was usable |
| The evidence file is invalid or its run or suite binding fails | Exit `2`, a sanitized error, and no fresh report |

## Migrating from diagnostic JSON

The original diagnostic `--json-out` still produces a list of legacy verdict rows, including raw reply text. Existing consumers can stay on that format. A strict report is a separate object. Check `schema_version` and `mode`, use the process exit for gating, and read `results` for per-case outcomes. Each strict row has separate `execution`, `evidence`, `security`, and `utility` fields in place of a single legacy `result`.

If you tried the v1 draft format, update the suite and collect fresh observations with the run and suite binding. V1 evidence exits `2`.
