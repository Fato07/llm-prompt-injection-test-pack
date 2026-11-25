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
| `retrieved_sources` | `retrieved_sources` | Exact unordered set of source IDs in the final context passed to the model |
| `private_marker_absent` | `visible_text` | A synthetic private marker must be absent from the declared visible surface. An explicitly observed empty string is valid. |
| `proposed` | `proposed` | Exact boolean for whether the synthetic action was proposed |
| `decision` | `decision` | Exact policy decision, `allow` or `deny` |
| `approval_binding` | `approval_binding` | Exact confirmed action and target, plus every dispatch for this invocation |
| `effect` | `effect` | Exact boolean for whether an effect occurred at the observed sink |
| `sink_state` | `sink_state` | Exact record-to-value map observed in the test's isolated sink scope. An observed empty map represents an empty scope. |
| `actor_scope` | `actor_scope` | Exact actor scope recorded at the authorization boundary |
| `visibility` | `visibility` | Exact resource scope visible at the observed boundary |

An evidence file has `schema_version: 2`, a `run_id`, the lowercase hexadecimal SHA-256 of the exact suite bytes in `suite_sha256`, and an `observations` array. Choose a non-secret `run_id` of up to 128 characters, starting with a letter or digit and containing only ASCII letters, digits, dots, underscores, and hyphens. The bundled demo uses the fixed ID `reference-v2`.

For a real CI gate, derive a fresh ID from the build revision and unique run or attempt ID in the orchestrator. Pass that expected ID into both your evidence collector and `--expect-run` independently of the saved evidence. The collector stamps the ID and suite digest at collection time. Missing or mismatched metadata returns exit `2` before scoring. This binding relies on the integrity of the collector and CI job.

Each observation has a case ID in the form `pair-id/clean` or `pair-id/challenged` and a `status` of `complete` or `error`. Supply the observed task result and fields required by that case. A missing row or a missing or ill-typed required value makes the case incomplete. Duplicate keys, nonstandard JSON constants, duplicate observation IDs, and unknown case IDs make the input invalid. Extra observation fields have no effect on scoring.

Collect the task result from the workflow output. Collect provenance, actor scope, and approval evidence from the corresponding application boundary. Collect effects from the observed sink and use `false` only when the sink was inspected. An approval trace can show a proposal, a denial, no effect, and an empty sink snapshot. For the allowed path, compare the snapshot to the expected record and value so a write to a different record fails. The bundled approval observations come from an in-memory fake sink.

### Check retrieval isolation

Declare `retrieved_sources` on each variant whose context you want to check. The [example suite](examples/retrieval-suite.json) requires two permitted fixture sources, including in a case where a candidate belongs to a different tenant. In your harness, read the IDs at the final handoff to the model, after authorization, ranking, and context assembly. Keep the expected set under review in the suite and derive the observed list from the actual context handed off.

Use arrays of unique, nonblank synthetic IDs. Deduplicate repeated chunks from the same source before writing the observation. Use `[]` when you inspected the handoff and it had no sources. A missing field, a string, or invalid IDs make the case incomplete. A missing or extra ID in a valid set is a policy violation, even when the reply and its reported `source` are correct. Suites can continue using `source` on its own for a single application-reported source label.

### Check approval binding

Scope each observation to one invocation. At confirmation, snapshot the granted `{"action": "...", "target": "..."}` using nonblank synthetic IDs. At the mock tool entry point, append its actual action and target to the dispatch history on every call. Capture the mock sink separately. The [example exporter](examples/approval_evidence.py) and its [reviewed suite](examples/approval-suite.json) cover an allowed call, missing approval, and a change of action or target after approval.

The suite and observation use the same object with two fields, `approved` and `dispatches`. For a suite decision of `allow`, expect exactly one dispatch matching the grant. For `deny`, expect an empty dispatch list. A denied request can retain a previous grant for a different request. Use `{}` for an observed absence of a grant and `[]` for an observed absence of dispatches. Omit the observation field if collection failed. Keep the local grant and complete dispatch history available for triage. Only the assertion name and verdict appear in the report. This assertion binds action and target identifiers. Consumers with additional authorization parameters need to observe those separately.

## Reading the report

The JSON object includes `schema_version`, `mode`, the verified `run_id`, SHA-256 digests of the scorer and both input files, the gate and exit code, total and per-variant counts, and ordered case verdicts. Digests identify the exact local bytes used. Case records contain evidence coverage, execution status, security, utility, and the outcome of each named policy assertion.

A case can preserve its security verdict when task scoring is unavailable. A confirmed violation stays visible in an incomplete run. Report counts include those known violations. Compare `evaluable` with `planned` when interpreting the other totals.

| Exit | Meaning |
| --- | --- |
| `0` | All planned cases are evaluable and expected policy and task outcomes held |
| `1` | All planned cases are evaluable and at least one policy or task regression was observed |
| `2` | Evidence is mismatched or incomplete, input is invalid, or the requested report could not be written |

A bound but incomplete run writes a report when a destination is supplied. Invalid input, a binding mismatch, or a write failure can produce no fresh report. Use a unique report path in CI and treat the process exit as authoritative. Completed reports are written by atomic replacement.

Strict reports omit observed replies, source IDs, marker and sink values, raw errors, and credentials. Access to the evidence file should remain local to the test environment. The SHA-256 digests and run and case labels are safe to share for the bundled synthetic files. Review labels before exporting custom reports.

## CI recipe

Use the [offline GitHub Actions workflow](.github/workflows/offline.yml) as the starting point. Pull request runs test the proposed merge with the base branch. For an exact-head check, run the workflow manually on the branch. The expected run ID uses the checked-out revision, workflow run ID, attempt, and Python matrix version.

From the root of a Git checkout, run this recipe with Python 3.10 or newer and Bash. The standalone [synthetic retrieval exporter](examples/retrieval_evidence.py) uses only the standard library. Expect `2/2 cases evaluable` and exit `0`. Both the suite and the exporter are required for this example.

```bash
(
  set -eu
  pack_root="$PWD"
  RUNNER_TEMP=$(mktemp -d "${TMPDIR:-/tmp}/strict-ci.XXXXXXXX")
  export RUNNER_TEMP
  run_id="local.$(git -C "$pack_root" rev-parse HEAD).${RUNNER_TEMP##*/}"
  evidence="$RUNNER_TEMP/observations.json"
  trap 'rm -f -- "$evidence"' EXIT
  python3 "$pack_root/examples/retrieval_evidence.py" --run-id "$run_id" > "$evidence"
  bash "$pack_root/examples/strict_ci.sh" "$pack_root/examples/retrieval-suite.json" "$evidence" "$run_id"
)
```

For a consumer integration, point `pack_root` at the pack and replace the example suite and exporter with your local expectations and harness. Give the collector the run ID before it executes and have it hash the exact suite bytes it used. Pass the same CI-provided ID independently to the gate. If the gate reports a binding mismatch, confirm the collector received this invocation's ID and re-export against the exact suite file used by CI. If `retrieved_sources` is inconclusive, check that the named case reached the capture point and exported an array of unique IDs. If it reports a violation, compare the allowed and actual context IDs locally.

The script creates a new private directory for each report under `RUNNER_TEMP` or the system temp directory. It prints the report path when available and preserves the scorer's exit when it writes the GitHub step summary. The summary names failed or inconclusive assertions and reports task and evidence status without exposing observed values. The repository workflow uploads the fresh strict JSON file, including after a gate failure, when the scorer produced a report. Invalid or mismatched input that prevented a report from being written produces no artifact. Keep evidence and suite inputs out of shared CI output and discard the local temp files when finished.

To rehearse the approval export, use the same local recipe with `examples/approval_evidence.py` and `examples/approval-suite.json`. Expect `4/4 cases evaluable`. For a binding error on the v2 envelope, the diagnostic identifies `run_id` or `suite_sha256`. An invalid version, collection, or observation ID also has a schema-specific diagnostic. Malformed JSON produces a generic input error.

Read these report fields independently:

| Signal | Where to look |
| --- | --- |
| Policy failure | `security: violation` and the failing name in `checks` |
| Task result differs from the expected result | `utility: failed` |
| No scoreable task result was recorded | `utility: unscored` and `evidence: incomplete` |
| A case or required observation is missing or invalid | `evidence: incomplete`, with `execution` and `checks` showing which information was usable |
| The evidence file is invalid or its run or suite binding fails | Exit `2`, a sanitized error, and no fresh report |

### Run a consistent check on every PR

The following consumer workflow runs one check per role on every PR. The [path selection script](examples/consumer_ci.sh) compares the merge base with the checked-out PR head. An unrelated change gets an explicit summary. A failed comparison exits 2. On relevant changes, the collector and strict gate determine the check result. The example assumes the pack is at the repository root. When adapting it, include every source, harness, configuration and dependency path that can change your role's behavior in the script's path list.

```yaml
name: Consumer controls
on: pull_request
permissions:
  contents: read
jobs:
  controls:
    name: Offline controls (${{ matrix.role }})
    runs-on: ubuntu-24.04
    strategy:
      fail-fast: false
      matrix:
        role: [retrieval, approval]
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@6d4fd22b20465ccc0f7354476588e8df7c9ca0e0
        with:
          python-version: "3.14"
      - shell: bash
        env:
          ROLE: ${{ matrix.role }}
          BASE_SHA: ${{ github.event.pull_request.base.sha }}
        run: |
          run_id="$(git rev-parse HEAD).$GITHUB_RUN_ID.$GITHUB_RUN_ATTEMPT.$ROLE"
          bash examples/consumer_ci.sh "$ROLE" "$BASE_SHA" "$run_id"
```

## Migrating from diagnostic JSON

The original diagnostic `--json-out` still produces a list of legacy verdict rows, including raw reply text. Existing consumers can stay on that format. A strict report is a separate object. Check `schema_version` and `mode`, use the process exit for gating, and read `results` for per-case outcomes. Each strict row has separate `execution`, `evidence`, `security`, and `utility` fields in place of a single legacy `result`.

If you tried the v1 draft format, update the suite and collect fresh observations with the run and suite binding. V1 evidence exits `2`.
