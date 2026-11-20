# Strict evidence format

The strict gate consumes a versioned suite and an evidence file emitted by a local test harness. Use synthetic records and sanitized identifiers. The gate scores the observations you supply. Confidence in a result depends on how the test harness collected those observations and which surfaces it covered.

```sh
python3 run_probes.py --strict --suite fixtures/suite.json \
  --evidence fixtures/observations.json --json-out report-strict.json
```

## Suite and observations

The suite has `schema_version: 1` and a nonempty `pairs` array. Give each pair a unique lowercase `id` with a letter first and up to 48 letters, digits or hyphens. IDs appear in reports and terminal output, so use fixture labels. Each pair declares one exact, nonblank `task_result` shared by its `clean` and `challenged` variants. Each variant declares one or more policy assertions.

| Suite assertion | Observation field | Meaning |
| --- | --- | --- |
| `source` | `source` | Exact source label recorded by the application |
| `private_marker_absent` | `visible_text` | A synthetic private marker must be absent from the declared visible surface. An explicitly observed empty string is valid. |
| `proposed` | `proposed` | Exact boolean for whether the synthetic action was proposed |
| `decision` | `decision` | Exact policy decision, `allow` or `deny` |
| `effect` | `effect` | Exact boolean for whether an effect occurred at the observed sink |
| `actor_scope` | `actor_scope` | Exact actor scope recorded at the authorization boundary |
| `visibility` | `visibility` | Exact resource scope visible at the observed boundary |

An evidence file has `schema_version: 1` and an `observations` array. Each row has a case ID in the form `pair-id/clean` or `pair-id/challenged` and a `status` of `complete` or `error`. Supply the observed task result and fields required by that case. A missing row or a missing or ill-typed required value makes the case incomplete. Duplicate keys, duplicate observation IDs, and unknown case IDs make the input invalid. Extra observation fields have no effect on scoring.

Collect the task result from the workflow output. Collect provenance, actor scope, and approval evidence from the corresponding application boundary. Collect effects from observed sink state and use `false` only when the sink was inspected. For example, an approval trace can show `proposed: true`, `decision: "deny"`, and `effect: false`. A denial by itself provides no sink evidence. The bundled records illustrate these cases using synthetic data.

## Reading the report

The JSON object includes `schema_version`, `mode`, SHA-256 digests of the scorer and both input files, the gate and exit code, total and per-variant counts, and ordered case verdicts. Digests identify the exact local bytes used. Case records contain evidence coverage, execution status, security, utility, and the outcome of each named policy assertion.

A case can preserve its security verdict when task scoring is unavailable. A confirmed violation stays visible in an incomplete run. Report counts include those known violations. Compare `evaluable` with `planned` when interpreting the other totals.

| Exit | Meaning |
| --- | --- |
| `0` | All planned cases are evaluable and expected policy and task outcomes held |
| `1` | All planned cases are evaluable and at least one policy or task regression was observed |
| `2` | Evidence is incomplete, input is invalid, or the requested report could not be written |

A parsed but incomplete run writes a report when a destination is supplied. Invalid input and write failures can produce no fresh report. Use a unique report path in CI and treat the process exit as authoritative. Completed reports are written by atomic replacement.

Strict reports omit input values, observed replies, marker values, raw errors, and credentials. Access to the evidence file should remain local to the test environment. The SHA-256 digests and case labels are safe to share for the bundled synthetic files. Review labels before exporting custom reports.

## Migrating from diagnostic JSON

The original diagnostic `--json-out` still produces a list of legacy verdict rows, including raw reply text. Existing consumers can stay on that format. A strict report is a separate object. Check `schema_version` and `mode`, use the process exit for gating, and read `results` for per-case outcomes. Each strict row has separate `execution`, `evidence`, `security`, and `utility` fields in place of a single legacy `result`.
