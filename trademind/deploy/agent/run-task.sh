#!/usr/bin/env bash
# Runs one Claude Code request headless on Amazon Bedrock. Called by .github/workflows/trademind-agent.yml
# from trademind/, on branch $BRANCH, with TASK, MODEL and BUDGET_USD set and short-lived credentials
# for a Bedrock-only role in the environment.
set -euo pipefail

: "${TASK:?the request is empty}"
: "${MODEL:?no model}"
: "${AWS_REGION:?no AWS credentials; check the TRADEMIND_AGENT_ROLE_ARN repository variable}"
OUT="${RUNNER_TEMP:-/tmp}/agent"
mkdir -p "$OUT"

export CLAUDE_CODE_USE_BEDROCK=1
export ANTHROPIC_MODEL="$MODEL"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="${FAST_MODEL:-$MODEL}"
# Claude never sees GitHub credentials or the runner's internal tokens.
unset GH_TOKEN GITHUB_TOKEN ACTIONS_RUNTIME_TOKEN ACTIONS_ID_TOKEN_REQUEST_TOKEN \
  ACTIONS_ID_TOKEN_REQUEST_URL ANTHROPIC_API_KEY ANTHROPIC_BASE_URL

prompt="$(cat deploy/agent/prompt.md)

## The request

$TASK"

# Extra tools for the server only. Here the agent user has no secrets, no Docker and no AWS
# beyond Bedrock, so ad hoc Python is safe. .claude/settings.json deny rules still win.
set +e
claude -p "$prompt" \
  --permission-mode acceptEdits \
  --allowedTools "Bash(python *)" "Bash(python3 *)" "Bash(trademind *)" \
    "Bash(sudo -n -u ec2-user /opt/trademind/trademind/deploy/agent/status.sh)" \
  --max-turns "${MAX_TURNS:-80}" \
  --max-budget-usd "${BUDGET_USD:-3}" \
  --output-format stream-json --verbose \
  | tee "$OUT/transcript.jsonl" | python3 deploy/agent/agentlog.py progress
code=${PIPESTATUS[0]}
set -e

python3 deploy/agent/agentlog.py summary "$OUT/transcript.jsonl" > "$OUT/result.md"
cat "$OUT/result.md" >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
echo "=== AGENT RESULT ==="
cat "$OUT/result.md"
echo "=== END AGENT RESULT ==="
python3 deploy/agent/agentlog.py notice "Agent result" --quiet < "$OUT/result.md"
exit "$code"
