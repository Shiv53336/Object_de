"""Guards for running on Windows: every text read or write names its encoding (Windows defaults to
cp1252, which breaks on the rupee sign and other non-ASCII text), and the CLI commands work there."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from trademind.cli import app

ROOT = Path(__file__).resolve().parents[1]


def _unencoded_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        keywords = {k.arg for k in node.keywords}
        if "encoding" in keywords:
            continue
        if name in {"read_text", "write_text"}:
            bad.append(f"{path.name}:{node.lineno} {name}")
        elif name == "open" and not (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                                     and func.value.id == "webbrowser"):
            mode_args = node.args[1:2] if isinstance(func, ast.Name) else node.args[:1]
            modes = [a.value for a in mode_args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
            modes += [k.value.value for k in node.keywords
                      if k.arg == "mode" and isinstance(k.value, ast.Constant)]
            if not any("b" in str(m) for m in modes):
                bad.append(f"{path.name}:{node.lineno} open")
        elif name == "run" and "text" in keywords:
            bad.append(f"{path.name}:{node.lineno} subprocess text=True")
    return bad


def test_all_text_io_names_an_encoding() -> None:
    files = [*(ROOT / "src").rglob("*.py"), *(ROOT / "tests").rglob("*.py"), *(ROOT / "deploy").rglob("*.py")]
    offenders = [x for f in files for x in _unencoded_calls(f)]
    assert offenders == []


def test_preflight_reports_missing_history_offline() -> None:
    result = CliRunner().invoke(app, ["preflight", "--for", "backtest", "--no-online"])
    assert result.exit_code == 1
    assert "FAIL  history" in result.output and "NOT READY" in result.output


def test_paper_check_needs_a_live_run() -> None:
    result = CliRunner().invoke(app, ["paper", "check", "--day", "2025-09-03", "--no-kite"])
    assert result.exit_code == 2
    assert "no finished live paper run" in result.output


@pytest.mark.skipif(sys.platform != "win32", reason="needs Windows PowerShell")
@pytest.mark.parametrize("script", sorted((ROOT / "deploy" / "windows").glob("*.ps1")), ids=lambda p: p.name)
def test_powershell_scripts_parse(script: Path) -> None:
    command = (
        "$e = $null; [System.Management.Automation.Language.Parser]::ParseFile("
        f"'{script}', [ref]$null, [ref]$e) | Out-Null; $e.Count"
    )
    out = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                         capture_output=True, text=True, encoding="utf-8", check=True)
    assert out.stdout.strip() == "0", out.stdout


def test_login_accepts_the_whole_redirect_url() -> None:
    from trademind.cli import _request_token

    url = "http://127.0.0.1/?action=login&type=login&status=success&request_token=Ab12Cd34Ef56"
    assert _request_token(url) == "Ab12Cd34Ef56"
    assert _request_token("  Ab12Cd34Ef56Gh78Ij90Kl12  ") == "Ab12Cd34Ef56Gh78Ij90Kl12"


def test_data_validate_all_symbols() -> None:
    args = ["data", "validate", "--symbol", "all", "--source", "synthetic", "--start", "2025-09-01",
            "--end", "2025-09-03"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert "symbols clean" in result.output and "NIFTY 50: " in result.output
