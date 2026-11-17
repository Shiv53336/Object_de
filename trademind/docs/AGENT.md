# Ops agent: Claude Code on the server

You ask for something in plain words. Claude Code runs on the TRADEMIND server, does the work (commands, tests, backtests, code changes), reads the results and reports back. Code changes come back as a pull request for you to merge.

```
you ──► Claude in chat / GitHub "Run workflow" / dispatch.sh
          │  workflow_dispatch (mode, request, model, budget)
          ▼
GitHub Actions ──► self-hosted runner on the EC2 instance (user `agent`)
          ▼
claude -p  on your Claude Pro/Max plan (Sonnet by default, Opus on request);
           if the plan's usage limit is hit: Amazon Bedrock, within a monthly cap
          │  edits, runs pytest / ruff / trademind, commits on agent/<run>
          ▼
workflow re-runs ruff + pytest, pushes agent/<run>, opens a pull request
          ▼
result: run annotations, job summary, PR description
```

## Using it

| You want | How |
|---|---|
| Anything (run tests, a backtest, explain code, do a task card, fix a bug) | `deploy/agent/dispatch.sh task "<request>"` |
| A bigger model or budget | `MODEL=opus BUDGET_USD=8 deploy/agent/dispatch.sh task "<request>"` |
| Health of the server (containers, timers, last daily run, disk) | `deploy/agent/dispatch.sh status` |
| Put merged `main` live | `deploy/agent/dispatch.sh deploy` (refused 08:35–15:35 IST on weekdays) |
| The result of an earlier run | `deploy/agent/dispatch.sh result <run-id>` |

`dispatch.sh` needs `gh` signed in to GitHub. You can also start a run from GitHub (Actions > trademind-agent > Run workflow), or ask Claude in chat, which runs `dispatch.sh` for you and reads back the result.

Runs queue one at a time. A request is a single headless session: the agent cannot ask you questions mid-run, so be specific, and it states the choices it made in its report.

## What the agent can and cannot do

| Can | Cannot |
|---|---|
| Read and edit the repo on a fresh `agent/<run>` branch | Push, touch `main`, merge, or use `gh` (the workflow pushes, after its own checks) |
| Run `pytest`, `ruff`, `trademind backtest/report/runs/strategies`, Python | `trademind validate` (holdout), `login`, `data download`, `paper` |
| Run backtests on synthetic data in its own folder | Read the production `.env`, `data/`, Kite token, or the server's git token |
| Read server status through `status.sh` | Use Docker, deploy, or change the production checkout |
| Use your Claude plan, or Claude on Bedrock as the fallback | Use the instance role or any other AWS service |

How each line is enforced:

- **OS user.** The `agent` user is not in the `docker` group. The production `.env`, `data/` and `/opt/trademind/.git/config` are owner-only.
- **Firewall.** An iptables owner rule blocks `agent` from the instance metadata service, so the instance role's credentials are out of reach.
- **AWS.** The workflow gets credentials through GitHub OIDC for a role whose only permission is invoking Claude on Bedrock. Its trust policy accepts only this repository's `main` branch.
- **Sudo.** The rule allows exactly `status.sh` and `deploy-main.sh` as `ec2-user`, with no arguments. Both live in the production checkout, which `agent` cannot write.
- **Claude Code permissions.** `.claude/settings.json` deny rules (push, gh, docker, curl, aws, `.env`, `validate`, editing `test_no_order_code.py`) win over any allow rule.
- **Credential hygiene.** The workflow strips GitHub tokens from Claude's environment, and shell commands Claude runs do not inherit provider credentials (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`). `publish.sh` refuses to push a diff that contains anything shaped like an Anthropic, AWS or GitHub key. Checkout keeps no credentials. Only `publish.sh` gets the token, and it pushes only `agent/*` branches.
- **Review gate.** Every change lands as a pull request; it is opened as a draft if Claude failed or `ruff`/`pytest` failed. GitHub does not start `trademind-ci` for pushes made with the workflow token, so the agent workflow's own `ruff` + `pytest` result is the check shown in the PR.

`CLAUDE.md` hard rules apply to every request (no order code, paper only, no tuning, no core changes without a card).

## One-time setup

0. **Claude plan token.** On your laptop, signed in to Claude Code with your Pro (or Max) account, run `claude setup-token`. Save the printed token in GitHub: Settings > Secrets and variables > Actions > **Secrets** > `CLAUDE_CODE_OAUTH_TOKEN`. It lasts about a year. Without it, every run goes to Bedrock.
1. **Terraform** (apply again): adds the GitHub OIDC provider and the Bedrock-only role for the fallback, and sets the budget alarm to $60:
   ```bash
   cd trademind/infra/terraform && terraform apply && terraform output agent_role_arn
   ```
   If the AWS account already has a GitHub OIDC provider, set `create_github_oidc_provider = false` in `terraform.tfvars`.
2. **GitHub repo settings:**
   - Settings > Secrets and variables > Actions > **Variables**: add `TRADEMIND_AGENT_ROLE_ARN` = the output above.
   - Optional: `AGENT_BEDROCK_MONTHLY_USD` (default `20`; `0` turns the fallback off).
   - Optional variables: `TRADEMIND_AGENT_SONNET_MODEL`, `TRADEMIND_AGENT_OPUS_MODEL` and `TRADEMIND_AGENT_FAST_MODEL`, to override the defaults `global.anthropic.claude-sonnet-5-5` and `global.anthropic.claude-opus-5-5`.
   - Settings > Actions > General > Workflow permissions: tick **Allow GitHub Actions to create and approve pull requests**.
3. **Bedrock** (fallback only): in the console (ap-south-1) > Model catalog, open the Anthropic models and submit the one-time use-case form if asked. The Claude 5.5 models are reached through the `global.` inference profiles from Mumbai.
4. **Runner:** in GitHub, Settings > Actions > Runners > New self-hosted runner > Linux / ARM64, and copy the token from the `./config.sh` line. On the server, through SSM:
   ```bash
   sudo su - ec2-user
   cd /opt/trademind && git pull
   sudo RUNNER_TOKEN=<token> bash trademind/deploy/agent/setup.sh
   ```
5. **Try it:** `deploy/agent/dispatch.sh status`, then `deploy/agent/dispatch.sh task "run the test suite and tell me the count"`.

## Cost and auth

Budget ceiling: Rs 10,000 a month for everything (breakdown in `OPERATIONS.md`). Claude Max does not fit it; Pro does.

1. **Claude plan first.** With `CLAUDE_CODE_OAUTH_TOKEN` set, runs use your Pro plan: no per-token cost. They share the plan's 5-hour and weekly limits with your chats.
2. **Bedrock only as a fallback.** It is used when there is no token, or when the plan's usage limit stopped the run. It is allowed only while this month's Bedrock spend is under `AGENT_BEDROCK_MONTHLY_USD`, which defaults to $20 (about Rs 2,100).
   - The runner keeps a ledger in `~agent/tm-data/agent-bedrock-spend.csv`.
   - Each Bedrock run is capped at the lower of `budget_usd` and what is left of the month's allowance.
   - When the allowance is used up, the run stops and says so.
3. **Every run is bounded.** Each run stops at 80 turns, and every report says which account it ran on.
4. **AWS backstop.** The AWS budget alarm (`monthly_budget_usd`, $60) covers the server and both Bedrock caps.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Run waits on "Waiting for a runner" | On the server: `sudo systemctl status 'actions.runner.*'`; restart with `cd ~agent/actions-runner && sudo ./svc.sh start` |
| `Could not assume role` / `Not authorized to perform sts:AssumeRoleWithWebIdentity` | `TRADEMIND_AGENT_ROLE_ARN` missing or wrong, or the run was not on `main` |
| Bedrock `AccessDeniedException` or model not found | Enable the model in the Bedrock console; check the model variables; `aws bedrock list-inference-profiles --region ap-south-1` |
| `sudo: a password is required` | `sudo visudo -cf /etc/sudoers.d/trademind-agent`; rerun `setup.sh` |
| PR not opened, branch link shown instead | Step 2: allow Actions to create pull requests |
| "Not run … usage limit" | The plan's limit is reached and the Bedrock allowance is used or off; wait for the reset (see `/usage` in Claude Code) |
| Runs suddenly go to Bedrock | The plan token expired or hit its limit; run `claude setup-token` again and update the secret |
| Agent says a command was denied | Expected for anything outside its permissions; widen `.claude/settings.json` only by a reviewed PR |
