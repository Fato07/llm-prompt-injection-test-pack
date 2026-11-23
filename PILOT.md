# Offline strict gate pilot

One retrieval-app team and one tool-using-agent team complete this packet independently. Each team returns one `receipt.json`. Use only local synthetic tasks, records and observations. This exercise works without model calls, credentials, production data or real tools.

## 1. Set up the pinned preview

Use Git, Python 3.10 or newer and a POSIX shell on macOS, Linux or WSL. In a fresh folder containing this file and the supplied `pilot/` folder, run the block below. The kit contains `pilot/case.json`, `pilot/record.py` and `pilot/example_export.py`. Run every later command from the same folder. You can open a new shell there between steps.

```sh
(
  set -eu
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10 or newer is required.")'
  git -c advice.detachedHead=false clone --quiet --depth 1 --single-branch \
    --branch v0.1.0-preview.1 https://github.com/Fato07/llm-prompt-injection-test-pack.git preview
  expected_sha=3acc3464725975e668e77ec9cf9cdc0a5563d73a
  actual_sha=$(git -C preview rev-parse HEAD)
  if [ "$actual_sha" != "$expected_sha" ]; then
    printf 'Preview commit mismatch.\nExpected commit %s\nActual commit   %s\n' \
      "$expected_sha" "$actual_sha" >&2
    exit 1
  fi
  mkdir -m 700 pilot-local
  python3 pilot/record.py start
)
```

Git fetches the public checkout during setup. All scoring and example exports after setup are local. If setup fails before the receipt command can run, write a minimal `receipt.json` with `kind`, `team_alias`, `team_role`, the attempted `revision`, and an `onboarding_blocker` describing the failing prerequisite. See step 5 for field values. For a retry, start from a fresh copy of the kit. Keep the preview checkout unchanged.

## 2. Get the first result

```sh
python3 pilot/record.py reference
```

The timer started at the end of step 1 and stops when the recorder reads the fresh strict report. Clone and prerequisite setup are outside the five-minute target. Confirm gate exit `0` and `12/12` evaluable. The recorder saves elapsed nanoseconds, the gate's process exit, and the report for the receipt. A partial run should still be reported. The command prints the gate exit separately from the recorder's own exit.

## 3. Explain the diagnosis case

```sh
python3 pilot/record.py diagnosis
```

Open `pilot-local/diagnosis-report.json` in a text editor. Use the report alone. Record the gate exit, case ID, task outcome from `utility`, failed assertion name from `checks`, and a one- or two-sentence explanation tying those fields together. Leave the supplied input file closed during the exercise.

## 4. Export a synthetic pair

Have your local orchestrator create the run ID before collecting observations:

```sh
python3 -c 'from uuid import uuid4; print("pilot-" + uuid4().hex)' > pilot-local/run-id.txt
```

Choose a route in this folder:

- **Own harness.** Use one workflow or adapter you already own and dummy data. Set synthetic expectations in `pilot-local/suite.json` before execution. Run a clean and a challenged variant, then emit the observations to `pilot-local/observations.json`. A retrieval app can record an allowed dummy document's source label when other dummy sources are present. A tool-using agent can record an approval decision and inspect an in-memory fake sink after approval and denial. In both roles, record the actual workflow task result and the fields below. If adapting the example, write a collector against your own harness so the observations come from that harness.
- **Example.** Use the command for your role to see the export format with a complete dummy run. Use a fresh kit folder to attempt an own-harness run after practicing with an example.
- **Blocked.** Skip scoring if you could not write both inputs. Return the receipt with the export blocker, including the first step you could not complete.

Example for the retrieval-app team:

```sh
python3 pilot/example_export.py retrieval-app
```

Example for the tool-using-agent team:

```sh
python3 pilot/example_export.py tool-using-agent
```

Use this contract for your own harness:

| File | Required content |
| --- | --- |
| `pilot-local/suite.json` | `schema_version` of `2` and a `pairs` array. Each pair has a unique lowercase ID such as `sample-pair`, one expected nonblank `task_result` shared by both variants, and `clean` and `challenged` assertion objects. Retrieval assertions can use `source`. Approval assertions can use `decision` and `sink_state`. |
| `pilot-local/observations.json` | `schema_version` of `2`, `run_id` read from `run-id.txt`, a lowercase SHA-256 `suite_sha256` of the exact suite bytes, and an `observations` array. Each row has `id` such as `sample-pair/clean`, `status` of `complete` or `error`, the actual `task_result`, and the values observed for the assertions. |

For a retrieval example, a row observes the label in `source` and the returned dummy task output in `task_result`. For a fake approval, record `allow` or `deny` in `decision`, inspect the sink, and record its actual record-to-value object in `sink_state`. An inspected empty sink is `{}`. The pinned checkout's `preview/EVIDENCE.md` documents all supported fields.

When both files exist, run:

```sh
python3 pilot/record.py export
```

The scorer receives the expected ID from `run-id.txt` independently of the saved evidence. Exit `0` is a complete pass, exit `1` is a complete scored regression, and exit `2` signals invalid, mismatched or incomplete input or a report failure. Keep the receipt even if the export is partial or invalid.

## 5. Return one receipt

```sh
python3 pilot/record.py receipt
```

Open `pilot-local/receipt.json` in a text editor. Replace the participant fields using this table. Leave the recorder's report objects, process exits, timings and bindings as generated.

| Field | What to report |
| --- | --- |
| `kind`, `team_alias`, `team_role` | Use `independent-pilot` for an actual team run or `local-rehearsal` for a practice run. Use a distinct, non-sensitive alias for each team. Set the role to `retrieval-app` or `tool-using-agent`. |
| `worked_without_coaching`, `onboarding_blocker` | Set the first field to `true` or `false`. Describe where you first got stuck, including setup, or leave the blocker as `null`. |
| `diagnosis.*` | Fill the observed gate exit as a number, case ID, task outcome, failed assertion, and your explanation from step 3. |
| `export.source`, `export.collection_boundary`, `export.blocker` | Keep `example` for the bundled example or choose `own-harness` or `blocked`. Describe the local component and boundary you observed in one sentence. Include the first integration blocker or leave it as `null`. |

If a step could not be completed, keep its missing fields as `null` and describe the blocker. Return only `receipt.json` after confirming all labels and free text are safe to share. The recorder includes sanitized reports and binding metadata. Keep suite inputs, observations, task text and sink values local. Remove the temporary folder once you have saved the receipt.
