#!/usr/bin/env bash
# Start an ops-agent run on the server and print its result. Needs `gh`, signed in with access to the repo.
#
#   deploy/agent/dispatch.sh task "run the full test suite and summarise failures"
#   deploy/agent/dispatch.sh status
#   deploy/agent/dispatch.sh deploy
#   MODEL=opus BUDGET_USD=8 deploy/agent/dispatch.sh task "do card T06"
#   NO_WAIT=1 deploy/agent/dispatch.sh task "..."     # start it and return the run URL
#   deploy/agent/dispatch.sh result <run-id>           # print the result of an earlier run
set -euo pipefail

REPO="${REPO:-Shiv53336/Object_de}"
WF=trademind-agent.yml
mode="${1:?usage: dispatch.sh task|status|deploy|result [request or run id]}"
shift
arg="${*:-}"

print_result() {
  local run_id=$1 run
  run=$(gh api "repos/$REPO/actions/runs/$run_id")
  echo "run:        $(jq -r .html_url <<<"$run")"
  echo "conclusion: $(jq -r '.conclusion // .status' <<<"$run")"
  for url in $(gh api "repos/$REPO/actions/runs/$run_id/jobs" --jq '.jobs[] | select(.conclusion != "skipped") | .check_run_url'); do
    gh api "${url#https://api.github.com/}/annotations" \
      --jq '.[] | select(.annotation_level == "notice" or .annotation_level == "failure") | "\n## \(.title // "")\n\(.message)"'
  done
}

if [ "$mode" = "result" ]; then
  print_result "${arg:?run id}"
  exit 0
fi
case "$mode" in task|status|deploy) ;; *) echo "mode must be task, status, deploy or result" >&2; exit 2 ;; esac
if [ "$mode" = "task" ] && [ -z "$arg" ]; then
  echo "task mode needs a request" >&2
  exit 2
fi

since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh api -X POST "repos/$REPO/actions/workflows/$WF/dispatches" -f ref=main \
  -f "inputs[mode]=$mode" -f "inputs[task]=$arg" \
  -f "inputs[model]=${MODEL:-sonnet}" -f "inputs[budget_usd]=${BUDGET_USD:-3}" >/dev/null

run_id=""
for _ in $(seq 1 30); do
  run_id=$(gh api "repos/$REPO/actions/workflows/$WF/runs?event=workflow_dispatch&created=%3E%3D$since" \
    --jq '.workflow_runs[0].id // empty')
  [ -n "$run_id" ] && break
  sleep 2
done
[ -n "$run_id" ] || { echo "dispatched, but the run did not appear yet; check the Actions tab" >&2; exit 1; }
echo "started: https://github.com/$REPO/actions/runs/$run_id"
[ -n "${NO_WAIT:-}" ] && exit 0

while [ "$(gh api "repos/$REPO/actions/runs/$run_id" --jq .status)" != "completed" ]; do
  sleep 15
done
print_result "$run_id"
