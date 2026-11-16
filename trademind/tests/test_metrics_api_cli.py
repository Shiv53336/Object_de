from __future__ import annotations

import math
import re

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from trademind.api.main import create_app
from trademind.cli import app
from trademind.services.learning.metrics import compute_metrics, max_drawdown, scoreboard, to_markdown

# ---- metrics -------------------------------------------------------------------------------


def _trades() -> pd.DataFrame:
    rows = [  # r, net, gross, costs, exit_reason, mfe_r, target, target_hit_after_stop
        (2.0, 200, 210, 10, "TARGET", 2.1, 1.0, None),
        (-1.0, -100, -90, 10, "STOP", 0.2, 1.0, True),
        (-1.0, -100, -90, 10, "STOP", 0.8, 1.0, False),
        (0.5, 50, 60, 10, "SQUAREOFF", 1.0, None, None),
        (-1.0, -100, -90, 10, "STOP", 0.1, None, None),
        (3.0, 300, 310, 10, "TARGET", 3.0, 1.0, None),
    ]
    df = pd.DataFrame(rows, columns=["r_multiple", "net_pnl", "gross_pnl", "costs", "exit_reason",
                                     "mfe_r", "target", "target_hit_after_stop"])
    df["exit_ts"] = pd.date_range("2025-09-01", periods=6, freq="D", tz="Asia/Kolkata")
    df["trade_id"] = [f"t{i}" for i in range(6)]
    df["instance_id"] = ["a@5minute"] * 3 + ["b@5minute"] * 3
    df["context"] = [{"time_bucket": "open"}, {"time_bucket": "midday"}] * 3
    return df


def test_metrics_hand_built() -> None:
    m = compute_metrics(_trades(), min_trades=100)
    assert m["n_trades"] == 6 and m["insufficient_sample"]
    assert m["win_rate"] == pytest.approx(0.5)
    assert m["expectancy_r"] == pytest.approx(2.5 / 6)
    assert m["profit_factor"] == pytest.approx(550 / 300)
    assert m["max_drawdown_r"] == pytest.approx(2.5)  # 2,1,0,0.5,-0.5: peak 2 to -0.5
    assert m["avg_win_r"] == pytest.approx(5.5 / 3) and m["avg_loss_r"] == pytest.approx(-1.0)
    assert m["false_breakout_rate"] == pytest.approx(2 / 6)
    assert m["stopped_then_right_rate"] == pytest.approx(0.5)
    assert m["cost_share"] == pytest.approx(60 / 850)


def test_metrics_edge_cases() -> None:
    assert compute_metrics(_trades().iloc[:0], 100)["n_trades"] == 0
    wins = _trades().iloc[[0, 5]]
    assert math.isinf(compute_metrics(wins, 1)["profit_factor"])
    assert max_drawdown(pd.Series([-1.0, -1.0, 3.0]).to_numpy()) == 2.0


def test_scoreboard_grouping_and_markdown() -> None:
    board = scoreboard(_trades(), 100, by="time_bucket")
    assert list(board["instance_id"]) == ["a@5minute", "a@5minute", "b@5minute", "b@5minute"]
    md = to_markdown(board)
    assert "time_bucket" in md and "3*" not in md and "2*" in md


# ---- api -----------------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path) -> TestClient:
    return TestClient(create_app(f"sqlite:///{tmp_path / 'api.sqlite'}", api_token="secret"))


AUTH = {"Authorization": "Bearer secret"}


def test_health_is_public(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["db"] == "ok" and r.json()["mode"] == "PAPER"


def test_dashboard_page_is_static(client: TestClient) -> None:
    r = client.get("/dashboard")
    assert r.status_code == 200 and "TRADEMIND" in r.text and "Authorization" in r.text
    assert client.get("/", follow_redirects=False).headers["location"] == "/dashboard"


def test_endpoints_need_token(client: TestClient, tmp_path) -> None:
    assert client.get("/runs").status_code == 401
    assert client.get("/runs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/runs", headers=AUTH).json() == []
    assert client.get("/runs/nope/scoreboard", headers=AUTH).status_code == 404
    unset = TestClient(create_app(f"sqlite:///{tmp_path / 'x.sqlite'}", api_token=""))
    assert unset.get("/runs").status_code == 503


# ---- cli -----------------------------------------------------------------------------------


def test_cli_backtest_report_and_api_roundtrip(tmp_path) -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["backtest", "--start", "2025-09-01", "--end", "2025-09-03",
                            "--instances", "orb_momentum@5minute,sweep_reversal@5minute"])
    assert r.exit_code == 0, r.output
    run_id = re.search(r"run_id: (\w+)", r.output).group(1)
    assert "| instance_id |" in r.output
    r2 = runner.invoke(app, ["report", "--run-id", run_id, "--by", "time_bucket"])
    assert r2.exit_code == 0 and "time_bucket" in r2.output
    assert runner.invoke(app, ["runs"]).output.startswith(run_id)
    client = TestClient(create_app(api_token="secret"))
    assert client.get(f"/runs/{run_id}/scoreboard", headers=AUTH).status_code == 200


def test_cli_rejects_holdout_and_unknown_instance() -> None:
    runner = CliRunner()
    r = runner.invoke(app, ["backtest", "--start", "2026-05-01", "--end", "2026-05-05"])
    assert r.exit_code == 2 and "holdout" in r.output
    r = runner.invoke(app, ["backtest", "--start", "2025-09-01", "--end", "2025-09-02",
                            "--instances", "nope@5minute"])
    assert r.exit_code == 2 and "unknown or disabled" in r.output


def test_cli_strategies_and_version() -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["version"]).output.strip() == "0.1.0"
    out = runner.invoke(app, ["strategies"]).output
    assert "orb_momentum@5minute" in out and "(not implemented)" not in out
