#!/usr/bin/env bash
# Runs on a fresh GitHub-hosted machine from main's own copy of this script, with the write token.
# Takes the agent's commits from the bundle as data (nothing in them is executed), checks them,
# pushes $BRANCH and opens a pull request. Only agent/* branches; only descendants of main.
set -euo pipefail

case "$BRANCH" in agent/*) ;; *) echo "refusing to push $BRANCH" >&2; exit 1 ;; esac
OUT="${RUNNER_TEMP:-/tmp}/agent-out"
BUNDLE="$OUT/agent.bundle"
[ -f "$BUNDLE" ] || { echo "No bundle: nothing to publish."; exit 0; }

git bundle verify -q "$BUNDLE"
git fetch -q "$BUNDLE" "refs/heads/agent:refs/heads/agent-incoming"
if ! git merge-base --is-ancestor origin/main agent-incoming; then
  echo "::error::The agent's commits do not build on main; not pushing." >&2
  exit 1
fi
# Last line of defence: never push anything that looks like a credential.
if git diff origin/main..agent-incoming | grep '^+' \
    | grep -Eq 'sk-ant-[A-Za-z0-9_-]{10,}|(AKIA|ASIA)[A-Z0-9]{16}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}'; then
  echo "::error::The changes contain something that looks like a credential. Not pushing; check the run." >&2
  exit 1
fi

git push -q origin "agent-incoming:refs/heads/${BRANCH}"

title="agent: $(printf '%s' "$TASK" | tr '\n' ' ' | cut -c1-70)"
{
  echo "**Request:** $TASK"
  echo
  echo "Claude Code: \`${CLAUDE_OUTCOME}\` · ruff + pytest on a clean GitHub machine: \`${VERIFY_OUTCOME}\` · run: ${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
  echo
  cat "$OUT/result.md" 2>/dev/null || echo "(no result recorded)"
} > "$OUT/pr-body.md"

draft=()
if [ "$CLAUDE_OUTCOME" != "success" ] || [ "$VERIFY_OUTCOME" != "success" ]; then
  draft=(--draft)
fi
if url=$(gh pr create --base main --head "$BRANCH" --title "$title" --body-file "$OUT/pr-body.md" "${draft[@]}"); then
  echo "Pull request: $url"
  echo "::notice title=Pull request::$url"
else
  compare="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/compare/main...${BRANCH}"
  echo "Could not open a pull request (allow Actions to create PRs in the repo settings). Branch: $compare"
  echo "::notice title=Branch pushed::$compare"
fi
