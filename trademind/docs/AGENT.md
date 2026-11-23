# Ops agent: Claude Code on the server

You ask for something in plain words. Claude Code runs on the TRADEMIND server, does the work (commands, tests, backtests, code changes), reads the results and reports back. Code changes come back as a pull request for you to merge.

```
you ──► Claude in chat / GitHub "Run workflow" / dispatch.sh
          │  workflow_dispatch (mode, request, model, budget)
          ▼
GitHub Actions
  task     self-hosted runner on the EC2 instance (user `agent`), read-only token
           claude -p on your Claude Pro/Max plan (Sonnet by default, Opus on request);
           Bedrock fallback only if you turned it on (off by default)
           edits, runs pytest / ruff / trademind, commits; hands back a git bundle
          ▼
  verify   GitHub-hosted runner, read-only token: ruff + pytest on the bundle
          ▼
  publish  GitHub-hosted runner: main's publish.sh pushes agent/<run>, opens a pull request
          ▼
result: run annotations, job summary, PR description
```

The machine Claude runs on never holds a token that can push. The bundle's code is tested on a throwaway GitHub-hosted machine, and the job that can push runs only the `publish.sh` from `main`, never code from the bundle.

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
| Read and edit the repo on a fresh `agent/<run>` branch | Push, touch `main`, merge, or use `gh`: there is no write token on its machine |
| Run `pytest`, `ruff`, `trademind backtest/report/runs/strategies`, Python | `trademind validate` (holdout), `login`, `data download`, `paper` |
| Run backtests on synthetic data in its own folder | Read the production `.env`, `data/`, Kite token, or the server's git token |
| Read server status through `status.sh` | Use Docker, deploy, or change the production checkout |
| Use your Claude plan, or Claude on Bedrock if you turned the fallback on | Use the instance role or any other AWS service |
| Edit `.github/workflows/` files in a commit | Get them pushed: GitHub rejects workflow-file changes pushed with the workflow token, so make those yourself |

How each line is enforced:

- **OS user.** The `agent` user is not in the `docker` group. The production `.env`, `data/` and `/opt/trademind/.git/config` are owner-only.
- **Firewall.** An iptables owner rule blocks `agent` from the instance metadata service, so the instance role's credentials are out of reach.
- **AWS.** With the fallback on, the workflow gets credentials through GitHub OIDC for a role whose only permission is invoking Claude on Bedrock. Its trust policy accepts only this repository's `main` branch. With the fallback off (the default), the role has no permissions and the workflow does not request credentials.
- **Sudo.** The rule allows exactly `status.sh` and `deploy-main.sh` as `ec2-user`, with no arguments. Both live in the production checkout, which `agent` cannot write.
- **Claude Code permissions.** `.claude/settings.json` deny rules (push, gh, docker, curl, aws, `.env`, `validate`, editing `test_no_order_code.py`) win over any allow rule.
- **Job split.** The `task` job, the only one on the self-hosted runner, has `contents: read`. Checkout keeps no credentials, the workflow strips GitHub tokens from Claude's environment, and shell commands Claude runs do not inherit provider credentials (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB`).
- **Publish checks.** `publish.sh` (always the copy on `main`) pushes only `agent/*` branches. It verifies the bundle, requires it to build on the current `main`, and refuses a diff that contains anything shaped like an Anthropic, AWS or GitHub key.
- **Review gate.** Every change lands as a pull request; it is opened as a draft if Claude failed or `ruff`/`pytest` failed. GitHub does not start `trademind-ci` for pushes made with the workflow token, so the `verify` job's `ruff` + `pytest` result is the check shown in the PR.
- **Private repo.** `setup.sh` refuses to register the runner while the repository is publicly visible: on a public repo, anyone's pull request could run code on a self-hosted runner.

**What is left.** Claude fully controls the `agent` user on the server: it can run any command as that user, read anything that user can read, and reach the internet. The protections are the four above that do not depend on Claude behaving:
- **OS permissions:** they keep `.env`, `data/` and the git token away from it.
- **Sudo:** the fixed sudo scripts.
- **No write token:** there is none on that machine.
- **Bedrock-only role:** if the fallback is on.

So keep secrets off the `agent` user, keep the repo private, and review every PR before merging.

`CLAUDE.md` hard rules apply to every request (no order code, paper only, no tuning, no core changes without a card).

## One-time setup

0. **Claude plan token.** On your laptop, signed in to Claude Code with your Pro (or Max) account, run `claude setup-token`. Save the printed token in GitHub: Settings > Secrets and variables > Actions > **Secrets** > `CLAUDE_CODE_OAUTH_TOKEN`. It lasts about a year. Without it, every run goes to Bedrock.
1. **Terraform** (apply again): adds the GitHub OIDC provider and the agent role, and sets the budget alarm to $45. The role gets Bedrock access only if `agent_bedrock_monthly_usd` is above 0 in `terraform.tfvars` (default 0):
   ```bash
   cd trademind/infra/terraform && terraform apply && terraform output agent_role_arn
   ```
   If the AWS account already has a GitHub OIDC provider, set `create_github_oidc_provider = false` in `terraform.tfvars`.
2. **GitHub repo settings:**
   - Settings > Secrets and variables > Actions > **Variables**: add `TRADEMIND_AGENT_ROLE_ARN` = the output above.
   - Optional: `AGENT_BEDROCK_MONTHLY_USD`, the Bedrock fallback in USD per month. Default `0` (off). To turn it on, set the same value here and as `agent_bedrock_monthly_usd` in Terraform, then apply.
   - Optional variables: `TRADEMIND_AGENT_SONNET_MODEL`, `TRADEMIND_AGENT_OPUS_MODEL` and `TRADEMIND_AGENT_FAST_MODEL`, to override the defaults `global.anthropic.claude-sonnet-5-5` and `global.anthropic.claude-opus-5-5`.
   - Settings > Actions > General > Workflow permissions: tick **Allow GitHub Actions to create and approve pull requests**.
3. **Bedrock** (only if you turn the fallback on): in the console (ap-south-1) > Model catalog, open the Anthropic models and submit the one-time use-case form if asked. The Claude 5.5 models are reached through the `global.` inference profiles from Mumbai.
4. **Runner** (only once the repo is private): in GitHub, Settings > Actions > Runners > New self-hosted runner > Linux / ARM64, and copy the token from the `./config.sh` line. On the server, through SSM:
   ```bash
   sudo su - ec2-user
   cd /opt/trademind && git pull
   sudo RUNNER_TOKEN=<token> bash trademind/deploy/agent/setup.sh
   ```
5. **Try it:** `deploy/agent/dispatch.sh status`, then `deploy/agent/dispatch.sh task "run the test suite and tell me the count"`.

## Cost and auth

Budget ceiling: Rs 10,000 a month for everything (breakdown in `OPERATIONS.md`). Claude Max does not fit it; Pro does.

1. **Claude plan first.** With `CLAUDE_CODE_OAUTH_TOKEN` set, runs use your Pro plan: no per-token cost. They share the plan's 5-hour and weekly limits with your chats.
2. **Bedrock fallback, off by default.** With `AGENT_BEDROCK_MONTHLY_USD` at 0, a run that hits the plan's limit stops and says so. If you turn it on, Bedrock is used when there is no token or the plan's limit stopped the run, and only while this month's Bedrock spend is under the cap:
   - **Ledger:** the runner keeps one in `~agent/tm-data/agent-bedrock-spend.csv`.
   - **Per-run cap:** each Bedrock run is capped at the lower of `budget_usd` and what is left of the month's allowance.
   - **Damaged ledger:** if the ledger cannot be read, the fallback is treated as used up.
3. **AWS hard stop.** With the fallback on, an AWS Budgets action attaches a deny-all-Bedrock policy to the agent role when the month's Bedrock spend reaches the agent and research caps combined. AWS updates cost data a few times a day, so the stop can come some hours after the cap is crossed. The code-side cap above is the first line; the AWS stop catches the case where that fails. The stop stays in place after the month ends. To lift it, open Billing > Budgets, choose the Bedrock budget, and reverse the action under Actions; or, in IAM, detach the `trademind-agent-bedrock-stop-…` policy from the agent role.
4. **Every run is bounded.** Each run stops at 80 turns, and every report says which account it ran on.
5. **AWS alarm.** The budget alarm (`monthly_budget_usd`, $45) covers the server and all Bedrock use.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Run waits on "Waiting for a runner" | On the server: `sudo systemctl status 'actions.runner.*'`; restart with `cd ~agent/actions-runner && sudo ./svc.sh start` |
| `Could not assume role` / `Not authorized to perform sts:AssumeRoleWithWebIdentity` | `TRADEMIND_AGENT_ROLE_ARN` missing or wrong, or the run was not on `main` |
| Bedrock `AccessDeniedException` or model not found | Expected if the fallback is off or the AWS stop fired. Otherwise enable the model in the Bedrock console, check the model variables, and run `aws bedrock list-inference-profiles --region ap-south-1` |
| `setup.sh` says REFUSING: repository is public | Make the repo private (Settings > General > Danger Zone), then run it again |
| PR shows "verify: failure" or is a draft | Open the run's `verify` job log; the bundle failed `ruff` or `pytest` |
| Publish push rejected: "refusing to allow a GitHub App to create or update workflow" | Expected when the change edits `.github/workflows/`: the workflow token cannot push those. Copy the change into a PR yourself |
| `sudo: a password is required` | `sudo visudo -cf /etc/sudoers.d/trademind-agent`; rerun `setup.sh` |
| PR not opened, branch link shown instead | Step 2: allow Actions to create pull requests |
| "Not run … usage limit" | The plan's limit is reached and the Bedrock allowance is used or off; wait for the reset (see `/usage` in Claude Code) |
| Runs suddenly go to Bedrock | The plan token expired or hit its limit; run `claude setup-token` again and update the secret |
| Agent says a command was denied | Expected for anything outside its permissions; widen `.claude/settings.json` only by a reviewed PR |
