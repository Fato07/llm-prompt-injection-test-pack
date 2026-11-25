#!/usr/bin/env bash
# Run from the root of the checked-out PR head, with base history available.
set -eu
if [[ $# != 3 || ! ${1:-} =~ ^(approval|retrieval)$ || ! ${2:-} =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Usage: bash examples/consumer_ci.sh approval|retrieval BASE_SHA RUN_ID' >&2
  exit 2
fi
role=$1
base=$2
run_id=$3
status=0
git diff --quiet --no-ext-diff --no-renames "$base...HEAD" -- \
  ".github/workflows" "src/$role" tests regression_gate.py run_probes.py \
  examples/consumer_ci.sh examples/strict_ci.sh "examples/${role}_evidence.py" \
  "examples/$role-suite.json" || status=$?
case $status in
  0)
    note="The $role gate was not needed for the changed paths."
    echo "$note"
    if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then echo "$note" >> "$GITHUB_STEP_SUMMARY"; fi
    exit 0 ;;
  1) ;;
  *)
    note='Could not compare the PR head with its base. Check the fetched history.'
    echo "$note" >&2
    if [[ -n ${GITHUB_STEP_SUMMARY:-} ]]; then echo "$note" >> "$GITHUB_STEP_SUMMARY"; fi
    exit 2 ;;
esac

evidence=$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/consumer-evidence.XXXXXXXX")
trap 'rm -f -- "$evidence"' EXIT
"${PYTHON:-python3}" "examples/${role}_evidence.py" --run-id "$run_id" > "$evidence"
bash examples/strict_ci.sh "examples/$role-suite.json" "$evidence" "$run_id"
