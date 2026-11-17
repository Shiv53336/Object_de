"""Guardrails of the ops agent harness (docs/AGENT.md): permissions, sudo rule, workflow and log tools."""

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "deploy" / "agent"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "trademind-agent.yml"


def _settings() -> dict:
    return json.loads((ROOT / ".claude" / "settings.json").read_text())


def _agentlog(*args: str, stdin: str = "") -> str:
    out = subprocess.run([sys.executable, str(AGENT / "agentlog.py"), *args], input=stdin,
                         capture_output=True, text=True, check=True)
    return out.stdout


def test_settings_deny_secrets_push_and_deploy():
    deny = set(_settings()["permissions"]["deny"])
    for rule in ["Read(./.env)", "Read(**/.env)", "Bash(git push *)", "Bash(git push)", "Bash(gh *)",
                 "Bash(docker *)", "Bash(*deploy-main.sh*)", "Bash(trademind validate *)",
                 "Edit(tests/test_no_order_code.py)"]:
        assert rule in deny


def test_settings_allow_nothing_broad_or_dangerous():
    perms = _settings()["permissions"]
    assert perms.get("defaultMode") != "bypassPermissions"
    for rule in perms["allow"]:
        assert rule not in {"Bash", "Bash(*)", "Read", "Edit", "Write"}
        for word in ("push", "gh ", "docker", "curl", "sudo", "deploy", "validate", ".env"):
            assert word not in rule, rule


def test_sudo_rule_allows_only_two_fixed_scripts_without_arguments():
    lines = [x for x in (AGENT / "sudoers").read_text().splitlines() if x and not x.startswith("#")]
    assert lines == [
        'agent ALL=(ec2-user) NOPASSWD: /opt/trademind/trademind/deploy/agent/status.sh "", '
        '/opt/trademind/trademind/deploy/agent/deploy-main.sh ""'
    ]


def test_workflow_keeps_github_token_away_from_claude():
    wf = yaml.safe_load(WORKFLOW.read_text())
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
    script = (AGENT / "run-task.sh").read_text()
    unset_at, claude_at = script.index("unset GH_TOKEN"), script.index("claude -p")
    assert unset_at < claude_at
    for name in ("GITHUB_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_RUNTIME_TOKEN"):
        assert name in script[unset_at:claude_at]


def test_publish_refuses_branches_outside_agent(tmp_path):
    env = {**os.environ, "BRANCH": "main", "RUNNER_TEMP": str(tmp_path)}
    out = subprocess.run(["bash", str(AGENT / "publish.sh")], env=env, cwd=tmp_path,
                         capture_output=True, text=True)
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
    path.write_text(TRANSCRIPT)
    text = _agentlog("summary", str(path))
    assert text.startswith("All 170 tests pass.")
    assert "status success · turns 4 · cost ~$0.50 · time 2m 05s" in text


def test_summary_without_result_keeps_last_message(tmp_path):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(TRANSCRIPT.splitlines()[:2]))
    text = _agentlog("summary", str(path))
    assert text.startswith("Running the tests.")
    assert "stopped without a final result" in text


def test_notice_escapes_and_truncates():
    out = _agentlog("notice", "Server status", "--quiet", stdin="50% done\nok")
    assert out.strip() == "::notice title=Server status::50%25 done%0Aok"
    long = _agentlog("notice", "R", "--quiet", stdin="x" * 5000)
    assert len(long) < 4100 and "truncated" in long
