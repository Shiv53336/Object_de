#!/usr/bin/env bash
# Runs one Claude Code request headless. Called by .github/workflows/trademind-agent.yml from trademind/,
# on branch $BRANCH, with TASK set.
#
# Which account pays (docs/AGENT.md, "Cost and auth"):
#   1. The Claude subscription (Pro/Max), when CLAUDE_CODE_OAUTH_TOKEN is set. No per-token cost.
#   2. Amazon Bedrock, when there is no subscription token or its usage limit stopped the run, and only
#      while this month's Bedrock spend is below AGENT_BEDROCK_MONTHLY_USD (default 0: off). The spend
#      ledger lives on the runner and fails closed: unreadable means no fallback. The ledger is only a
#      convenience, since the agent can write to it; the hard limit is AWS-side (Terraform gives the
#      role no Bedrock access at 0, and a budget action denies it once the month's cap is reached).
set -euo pipefail

: "${TASK:?the request is empty}"
OUT="${RUNNER_TEMP:-/tmp}/agent"
LEDGER="${AGENT_LEDGER:-$HOME/tm-data/agent-bedrock-spend.csv}"
CAP="${AGENT_BEDROCK_MONTHLY_USD:-0}"
BUDGET="${BUDGET_USD:-3}"
ALIAS="${MODEL_ALIAS:-sonnet}"
BEDROCK_MODEL="${BEDROCK_MODEL:-global.anthropic.claude-sonnet-5-5}"
LOG="deploy/agent/agentlog.py"
mkdir -p "$OUT" "$(dirname "$LEDGER")"

# Claude never sees GitHub credentials or the runner's internal tokens, and the shell commands it
# runs do not inherit provider credentials.
unset GH_TOKEN GITHUB_TOKEN ACTIONS_RUNTIME_TOKEN ACTIONS_ID_TOKEN_REQUEST_TOKEN \
  ACTIONS_ID_TOKEN_REQUEST_URL ANTHROPIC_API_KEY ANTHROPIC_BASE_URL
export CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1

prompt="$(cat deploy/agent/prompt.md)

## The request

$TASK"

# attempt PROVIDER MODEL BUDGET: one Claude Code run; transcript in $OUT/transcript.jsonl.
attempt() {
  local provider=$1 model=$2 budget=$3
  (
    if [ "$provider" = "subscription" ]; then
      unset CLAUDE_CODE_USE_BEDROCK AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
    else
      unset CLAUDE_CODE_OAUTH_TOKEN
      export CLAUDE_CODE_USE_BEDROCK=1 ANTHROPIC_MODEL="$model"
      export ANTHROPIC_DEFAULT_HAIKU_MODEL="${FAST_MODEL:-$model}"
    fi
    # Extra tools for the server only: here the agent user has no secrets, no Docker and no AWS
    # beyond Bedrock. .claude/settings.json deny rules still win.
    set +e
    claude -p "$prompt" \
      --model "$model" \
      --permission-mode acceptEdits \
      --allowedTools "Bash(python *)" "Bash(python3 *)" "Bash(trademind *)" \
        "Bash(sudo -n -u ec2-user /opt/trademind/trademind/deploy/agent/status.sh)" \
      --max-turns "${MAX_TURNS:-80}" \
      --max-budget-usd "$budget" \
      --output-format stream-json --verbose \
      2>"$OUT/stderr.txt" | tee "$OUT/transcript.jsonl" | python3 "$LOG" progress
    exit "${PIPESTATUS[0]}"
  )
}

code=1
ran=""
note=""
if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  echo "== Claude subscription, model $ALIAS"
  attempt subscription "$ALIAS" "$BUDGET" && code=0 || code=$?
  ran="Claude subscription ($ALIAS; the cost shown is notional, the plan covers it)"
  cat "$OUT/stderr.txt" >&2 || true
  if [ "$code" -ne 0 ] && python3 "$LOG" limit-hit "$OUT/transcript.jsonl" "$OUT/stderr.txt"; then
    note="The subscription's usage limit was reached."
    ran=""
  fi
fi

if [ -z "$ran" ]; then
  if ! spent=$(python3 "$LOG" spend-month "$LEDGER"); then
    spent="$CAP"  # unreadable ledger: fail closed
    note="$note The Bedrock spend ledger could not be read, so the fallback is off."
  fi
  left=$(python3 -c "print(round(max(0.0, $CAP - $spent), 2))")
  if [ -z "${AWS_REGION:-}" ]; then
    note="$note No Bedrock fallback: the TRADEMIND_AGENT_ROLE_ARN variable is not set."
  elif python3 -c "import sys; sys.exit(0 if $left >= 0.5 else 1)"; then
    budget=$(python3 -c "print(min(float('$BUDGET'), $left))")
    echo "== Bedrock, model $BEDROCK_MODEL, run cap \$$budget (this month \$$spent of \$$CAP)"
    attempt bedrock "$BEDROCK_MODEL" "$budget" && code=0 || code=$?
    cat "$OUT/stderr.txt" >&2 || true
    python3 "$LOG" spend-add "$LEDGER" "$OUT/transcript.jsonl" "$budget"
    ran="Bedrock ($BEDROCK_MODEL)"
  else
    note="$note Bedrock fallback skipped: this month's \$$CAP allowance is used (\$$spent)."
  fi
fi

if [ -n "$ran" ]; then
  python3 "$LOG" summary "$OUT/transcript.jsonl" > "$OUT/result.md"
  printf '\nRan on: %s. %s\n' "$ran" "$note" >> "$OUT/result.md"
else
  code=1
  if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
    hint="Try again after the plan's limit resets, or raise AGENT_BEDROCK_MONTHLY_USD."
  else
    hint="Set the CLAUDE_CODE_OAUTH_TOKEN secret (docs/AGENT.md, setup step 0)."
  fi
  printf 'Not run. %s\n%s\n' "${note# }" "$hint" > "$OUT/result.md"
fi

cat "$OUT/result.md" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "=== AGENT RESULT ==="
cat "$OUT/result.md"
echo "=== END AGENT RESULT ==="
python3 "$LOG" notice "Agent result" --quiet < "$OUT/result.md"
exit "$code"
