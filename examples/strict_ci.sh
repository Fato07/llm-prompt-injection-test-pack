#!/usr/bin/env bash
set -eu

if [[ $# != 3 ]]; then
  printf 'Usage: bash examples/strict_ci.sh SUITE EVIDENCE EXPECTED_RUN_ID\n' >&2
  exit 2
fi

pack_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd) || exit 2
report_dir=$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/strict-gate.XXXXXXXX") || exit 2
report="$report_dir/strict-report.json"

status=0
details=$("${PYTHON:-python3}" "$pack_root/run_probes.py" --strict \
  --suite="$1" --evidence="$2" --expect-run="$3" --json-out="$report" 2>&1) || status=$?
printf '%s\n' "$details"

if [[ -f "$report" ]]; then
  report_note='A fresh strict JSON report was written.'
  printf 'Strict JSON report: %s\n' "$report"
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf 'report_path=%s\n' "$report" >> "$GITHUB_OUTPUT" ||
      printf 'Could not set the strict report step output.\n' >&2
  fi
else
  report_note='No fresh strict JSON report was written.'
  printf '%s\n' "$report_note"
fi

if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  printf '### Strict gate (exit %s)\n\n```text\n%s\n```\n\n%s\n' \
    "$status" "$details" "$report_note" >> "$GITHUB_STEP_SUMMARY" ||
    printf 'Could not write the GitHub step summary.\n' >&2
fi
exit "$status"
