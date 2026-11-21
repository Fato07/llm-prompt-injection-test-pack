# Offline strict gate pilot

Use this same packet with one retrieval-app team and one tool-using-agent team. Each team works independently and returns one receipt. Both teams use the same revision. This packet uses the [published preview](https://github.com/Fato07/llm-prompt-injection-test-pack/releases/tag/v0.1.0-preview.1) at commit `3acc3464725975e668e77ec9cf9cdc0a5563d73a`. For a candidate pilot, the coordinator supplies the same exact candidate revision to both teams.

Use Python 3.10 or newer, a shell, and a local copy of the pack. The exercises use synthetic records and saved observations. Keep credentials, production data, and live endpoints out of the exercises.

## 1. Get the first result

Start the timer with the pinned checkout available locally. From its root, run:

```sh
pilot_dir=$(mktemp -d "${TMPDIR:-/tmp}/strict-pilot.XXXXXXXX")
python3 run_probes.py --strict --suite fixtures/suite.json \
  --evidence fixtures/observations.json --expect-run reference-v2 \
  --json-out "$pilot_dir/reference.json"
```

Stop the timer when you can confirm the process exited `0` and the report has 12/12 evaluable cases. The target is five minutes. Record actual time and the first place you got stuck, including setup or documentation.

## 2. Explain one regression

Generate a separate evidence file for the bundled fake approval workflow. Use the resulting report to diagnose the regression.

```sh
python3 - "$pilot_dir/approval-observations.json" <<'PY'
import json
import sys
from pathlib import Path
from examples.reference_evidence import approval_observation, reference_evidence

evidence = reference_evidence()
observed = next(row for row in evidence["observations"] if row["id"] == "approval/clean")
observed.update(approval_observation(confirmed=True, target_record="other-review"))
Path(sys.argv[1]).write_text(json.dumps(evidence), encoding="utf-8")
PY
approval_status=0
python3 run_probes.py --strict --suite fixtures/suite.json \
  --evidence "$pilot_dir/approval-observations.json" --expect-run reference-v2 \
  --json-out "$pilot_dir/approval-report.json" || approval_status=$?
printf 'Gate exit %s\n' "$approval_status"
```

Open `approval-report.json`. In one or two sentences, explain the exit, whether the task completed, and which policy check failed. Use the report fields to support your answer.

## 3. Export from your own harness

Create one clean and challenged pair using your existing local test harness and dummy records. Choose one boundary you can actually observe. A retrieval app can record a synthetic source label and a task result. A tool-using agent can record a decision and a snapshot from its in-memory fake sink. Use the [v2 evidence format](https://github.com/Fato07/llm-prompt-injection-test-pack/blob/v0.1.0-preview.1/EVIDENCE.md) to define the suite and save the observations.

Have the harness or CI orchestrator choose a fresh synthetic run ID before collection. Pass it to the collector and to `--expect-run` independently. Write the digest of the exact suite bytes at collection time. Score the result with strict mode and a fresh local report path. Record the outcome, the first integration blocker, and how much custom code the export took.

## Team receipt

Copy this table once per team. Keep the evidence files local. Share the receipt and, where useful, the strict report after checking that all run and case labels are synthetic. Delete the temporary files when finished.

| Field | Result |
| --- | --- |
| Team type, tested revision, Python version | |
| Elapsed time to first valid score, exit, and evaluable count | |
| First onboarding blocker or unclear instruction | |
| Regression explanation, citing report fields | |
| Own-harness export attempted and completed, gate exit, and evaluable count | |
| First integration blocker and approximate export effort | |
