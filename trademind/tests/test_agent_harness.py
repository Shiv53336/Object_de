"""Guardrails of the ops agent harness (docs/AGENT.md): permissions, sudo rule, workflow and log tools."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "deploy" / "agent"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "trademind-agent.yml"
# The agent's shell scripts run on the Linux server only.
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="server-side bash script")
UTF8 = {**os.environ, "PYTHONIOENCODING": "utf-8"}


def _settings() -> dict:
    return json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))


def _agentlog(*args: str, stdin: str = "") -> str:
    out = subprocess.run([sys.executable, str(AGENT / "agentlog.py"), *args], input=stdin, env=UTF8,
                         capture_output=True, text=True, check=True, encoding="utf-8")
    return out.stdout


def test_settings_deny_secrets_push_and_deploy():
    deny = set(_settings()["permissions"]["deny"])
    for rule in ["Read(./.env)", "Read(**/.env)", "Bash(git push *)", "Bash(git push)", "Bash(gh *)",
                 "Bash(docker *)", "Bash(*deploy-main.sh*)", "Bash(trademind validate *)",
                 "Bash(trademind login *)", "Bash(trademind paper run*)",
                 "Edit(tests/test_no_order_code.py)"]:
        assert rule in deny


def test_settings_allow_nothing_broad_or_dangerous():
    perms = _settings()["permissions"]
    assert perms.get("defaultMode") != "bypassPermissions"
    for rule in perms["allow"]:
        assert rule not in {"Bash", "Bash(*)", "Read", "Edit", "Write"}
        banned = ("push", "gh ", "docker", "curl", "sudo", "deploy", "trademind validate", "paper run",
                  ".env")
        for word in banned:
            assert word not in rule, rule


def test_sudo_rule_allows_only_two_fixed_scripts_without_arguments():
    text = (AGENT / "sudoers").read_text(encoding="utf-8")
    lines = [x for x in text.splitlines() if x and not x.startswith("#")]
    assert lines == [
        'agent ALL=(ec2-user) NOPASSWD: /opt/trademind/trademind/deploy/agent/status.sh "", '
        '/opt/trademind/trademind/deploy/agent/deploy-main.sh ""'
    ]


def test_workflow_keeps_github_token_away_from_claude():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    task = wf["jobs"]["task"]
    assert task["runs-on"] == ["self-hosted", "trademind"]
    assert wf["concurrency"]["group"] == "trademind-agent"
    steps = {s.get("name") or s.get("uses"): s for s in task["steps"]}
    checkout = next(s for s in task["steps"] if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout["with"]["persist-credentials"] is False
    claude = steps["Claude Code"]
    assert "github.token" not in json.dumps(claude) and "GH_TOKEN" not in claude.get("env", {})
    assert "GH_TOKEN" in steps["Push branch and open pull request"]["env"]


def test_run_task_unsets_credentials_before_claude():
    script = (AGENT / "run-task.sh").read_text(encoding="utf-8")
    unset_at, claude_at = script.index("unset GH_TOKEN"), script.index("claude -p")
    assert unset_at < claude_at
    for name in ("GITHUB_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_RUNTIME_TOKEN"):
        assert name in script[unset_at:claude_at]


@posix_only
def test_publish_refuses_branches_outside_agent(tmp_path):
    env = {**os.environ, "BRANCH": "main", "RUNNER_TEMP": str(tmp_path)}
    out = subprocess.run(["bash", str(AGENT / "publish.sh")], env=env, cwd=tmp_path,
                         capture_output=True, text=True, encoding="utf-8")
    assert out.returncode == 1
    assert "refusing to push main" in out.stderr


TRANSCRIPT = "\n".join(json.dumps(e) for e in [
    {"type": "system", "subtype": "init", "model": "global.anthropic.claude-sonnet-5-5"},
    {"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Running the tests."},
        {"type": "tool_use", "name": "Bash", "input": {"command": "pytest -q"}}]}},
    {"type": "user", "message": {"content": [
        {"type": "tool_result", "is_error": True, "content": "2 failed"}]}},
    {"type": "result", "subtype": "success", "num_turns": 4, "total_cost_usd": 0.5,
     "duration_ms": 125000, "result": "All 170 tests pass."},
]) + "\nnot json\n"


def test_progress_shows_text_tools_and_errors():
    lines = _agentlog("progress", stdin=TRANSCRIPT).splitlines()
    assert lines == [
        "session started · model global.anthropic.claude-sonnet-5-5",
        "» Running the tests.",
        "[Bash] pytest -q",
        "  ! 2 failed",
        "finished · success · turns 4",
    ]


def test_summary_reports_result_cost_and_time(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text(TRANSCRIPT, encoding="utf-8")
    text = _agentlog("summary", str(path))
    assert text.startswith("All 170 tests pass.")
    assert "status success · turns 4 · cost ~$0.50 · time 2m 05s" in text


def test_summary_without_result_keeps_last_message(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(TRANSCRIPT.splitlines()[:2]), encoding="utf-8")
    text = _agentlog("summary", str(path))
    assert text.startswith("Running the tests.")
    assert "stopped without a final result" in text


def test_notice_escapes_and_truncates():
    out = _agentlog("notice", "Server status", "--quiet", stdin="50% done\nok")
    assert out.strip() == "::notice title=Server status::50%25 done%0Aok"
    long = _agentlog("notice", "R", "--quiet", stdin="x" * 5000)
    assert len(long) < 4100 and "truncated" in long


def _write(path: Path, events: list[dict]) -> str:
    path.write_text("\n".join(json.dumps(e) for e in events))
    return str(path)


def test_limit_hit_only_when_a_failed_run_mentions_the_limit(tmp_path):
    limited = _write(tmp_path / "a.jsonl", [{"type": "result", "subtype": "error_during_execution",
                                              "is_error": True,
                                              "result": "You've hit your limit · resets 3pm"}])
    other_error = _write(tmp_path / "b.jsonl", [{"type": "result", "subtype": "error_max_turns",
                                                  "is_error": True, "result": "stopped"}])
    success = _write(tmp_path / "c.jsonl", [{"type": "result", "subtype": "success", "is_error": False,
                                              "result": "The usage limit test passes."}])
    log = [sys.executable, str(AGENT / "agentlog.py"), "limit-hit"]
    assert subprocess.run([*log, limited]).returncode == 0
    assert subprocess.run([*log, other_error]).returncode == 1
    assert subprocess.run([*log, success]).returncode == 1


def test_bedrock_ledger_sums_only_this_month(tmp_path):
    ledger = tmp_path / "spend.csv"
    ledger.write_text("2000-01-05T10:00:00Z,9.0000\nbad line\n")
    _agentlog("spend-add", str(ledger), _write(tmp_path / "t.jsonl", [
        {"type": "result", "subtype": "success", "total_cost_usd": 1.25}]), "3")
    _agentlog("spend-add", str(ledger), str(tmp_path / "missing.jsonl"), "2")
    assert _agentlog("spend-month", str(ledger)).strip() == "3.25"


def test_workflow_passes_plan_token_only_to_claude():
    task = yaml.safe_load(WORKFLOW.read_text())["jobs"]["task"]
    with_token = [s.get("name") for s in task["steps"] if "CLAUDE_CODE_OAUTH_TOKEN" in json.dumps(s)]
    assert with_token == ["Claude Code"]
    aws = next(s for s in task["steps"] if "configure-aws-credentials" in str(s.get("uses", "")))
    assert aws["if"] == "vars.TRADEMIND_AGENT_ROLE_ARN != ''"


@posix_only
def test_publish_refuses_a_diff_with_a_credential(tmp_path):
    git_env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, env=git_env, check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "a.txt").write_text("hello\n")
    git("add", ".")
    git("commit", "-qm", "base")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    (tmp_path / "a.txt").write_text("hello\ntoken = sk-ant-oat01-abcdefghijklmnop\n")
    git("commit", "-qam", "leak")
    env = {**git_env, "BRANCH": "agent/1", "RUNNER_TEMP": str(tmp_path), "GH_TOKEN": "x"}
    out = subprocess.run(["bash", str(AGENT / "publish.sh")], env=env, cwd=tmp_path,
                         capture_output=True, text=True)
    assert out.returncode == 1
    assert "looks like a credential" in out.stderr
