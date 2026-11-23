#!/usr/bin/env bash
# Runs on the self-hosted machine after Claude Code, with no GitHub credentials: commits anything
# left uncommitted and packs the agent's commits into $RUNNER_TEMP/agent-out/agent.bundle, next to
# the result report. The GitHub-hosted jobs take it from there (docs/AGENT.md).
set -euo pipefail
OUT="${RUNNER_TEMP:-/tmp}/agent-out"
mkdir -p "$OUT"
cp "${RUNNER_TEMP:-/tmp}/agent/result.md" "$OUT/result.md" 2>/dev/null || echo "(no result recorded)" > "$OUT/result.md"

if [ -n "$(git status --porcelain)" ]; then
  git add -A
  git commit -q -m "agent: changes left uncommitted at the end of the run"
fi
if [ -z "$(git rev-list origin/main..HEAD)" ]; then
  echo "No file changes."
  echo "changed=false" >> "${GITHUB_OUTPUT:-/dev/null}"
  exit 0
fi
git branch -f agent HEAD
git bundle create "$OUT/agent.bundle" origin/main..agent
echo "changed=true" >> "${GITHUB_OUTPUT:-/dev/null}"
