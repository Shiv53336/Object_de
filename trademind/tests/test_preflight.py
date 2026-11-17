"""Morning readiness checks (`trademind preflight`) and the Windows-friendly helpers they rely on."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pandas as pd
import pytest

from trademind.services.broker_gateway.kite import TokenStore
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.store import ParquetStore
from trademind.services.ops import preflight as pf
from trademind.shared.clock import IST
from trademind.shared.config import config_hash, runtime_paths
from trademind.shared.dotenv import load_env_file, parse_env
from trademind.shared.power import keep_awake, on_battery

TODAY = date(2025, 9, 3)  # a Wednesday


def _store_with(small_cfg, tmp_path, symbols: list[str], days: int) -> ParquetStore:
    store = ParquetStore(tmp_path / "bars")
    for sym in symbols:
        ts = [pd.Timestamp(TODAY - timedelta(days=k), tz=IST) + pd.Timedelta(hours=9, minutes=15)
              for k in range(1, days + 1)]
        store.write(sym, "1minute", pd.DataFrame({"ts": ts, "open": 1.0, "high": 1.0, "low": 1.0,
                                                  "close": 1.0, "volume": 1}))
    return store


def _by_name(checks: list[pf.Check]) -> dict[str, pf.Check]:
    return {c.name: c for c in checks}


def test_history_fails_without_market_symbol(small_cfg, tmp_path) -> None:
    store = _store_with(small_cfg, tmp_path, ["AAA", "BBB"], 40)
    checks = _by_name(pf.check_history(small_cfg, store, TODAY, "paper"))
    assert checks["history"].status == pf.FAIL


def test_history_ok_and_flags_short_and_stale(small_cfg, tmp_path) -> None:
    others = [x for x in build_instruments(small_cfg.settings) if x != "BBB"]
    store = _store_with(small_cfg, tmp_path, others, 40)
    store.write("BBB", "1minute", pd.DataFrame({"ts": [pd.Timestamp("2025-08-01 09:15", tz=IST)],
                                                "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0,
                                                "volume": 1}))
    checks = _by_name(pf.check_history(small_cfg, store, TODAY, "paper"))
    assert checks["history"].status == pf.OK
    assert checks["freshness"].status == pf.WARN and "BBB" in checks["freshness"].detail
    assert checks["depth"].status == pf.WARN and "BBB (1)" in checks["depth"].detail


def test_env_and_token_fail_for_paper_only(tmp_path) -> None:
    paths = runtime_paths()
    env = _by_name(pf.check_env({}, "paper"))
    assert env["kite keys"].status == pf.FAIL and env["telegram"].status == pf.WARN
    assert _by_name(pf.check_env({}, "backtest"))["kite keys"].status == pf.WARN
    assert pf.check_token(paths, TODAY, "paper").status == pf.FAIL
    TokenStore(paths.data_dir / "kite_token.json").save("tok", TODAY)
    assert pf.check_token(paths, TODAY, "paper").status == pf.OK
    assert pf.check_token(paths, TODAY + timedelta(days=1), "paper").status == pf.FAIL


def test_session_time_and_weekend(small_cfg) -> None:
    morning = pd.Timestamp("2025-09-03 08:50", tz=IST)
    assert pf.check_session_time(small_cfg, morning).status == pf.OK
    assert pf.check_session_time(small_cfg, morning + pd.Timedelta(hours=1)).status == pf.WARN
    saturday = pd.Timestamp("2025-09-06 09:00", tz=IST)
    assert "not a trading day" in pf.check_session_time(small_cfg, saturday).detail


def test_clock_skew_levels() -> None:
    local = pd.Timestamp("2025-09-03 03:20:00", tz="UTC")
    assert pf.check_clock("Wed, 03 Sep 2025 03:20:01 GMT", local).status == pf.OK
    assert pf.check_clock("Wed, 03 Sep 2025 03:19:55 GMT", local).status == pf.WARN
    assert pf.check_clock("Wed, 03 Sep 2025 03:19:30 GMT", local).status == pf.FAIL
    assert pf.check_clock(None, local).status == pf.WARN


def test_timezone_must_be_ist() -> None:
    assert pf.check_timezone(timedelta(hours=5, minutes=30)).status == pf.OK
    assert pf.check_timezone(timedelta(0)).status == pf.WARN


def test_disk_and_journal_and_summary(tmp_path) -> None:
    assert pf.check_disk(tmp_path, free_bytes=int(5e9)).status == pf.OK
    assert pf.check_disk(tmp_path, free_bytes=int(1e9)).status == pf.WARN
    assert pf.check_disk(tmp_path / "missing" / "dir", free_bytes=int(1e8)).status == pf.FAIL

    def broken() -> bool:
        raise OSError("no database")

    assert pf.check_journal(broken).status == pf.FAIL
    text, code = pf.summarize([pf.Check("a", pf.OK, "fine"), pf.Check("b", pf.WARN, "hm")])
    assert code == 0 and text.endswith("READY (1 warnings)")
    _, code = pf.summarize([pf.Check("a", pf.FAIL, "broken")])
    assert code == 1


def test_parse_env_handles_quotes_comments_and_export() -> None:
    text = "# comment\nexport A=1\nB = \"two words\"\nC='x # y'\nD=plain # note\nnot a line\n=E\n"
    assert parse_env(text) == {"A": "1", "B": "two words", "C": "x # y", "D": "plain"}


def test_load_env_file_never_overrides(tmp_path) -> None:
    path = tmp_path / ".env"
    path.write_text("KITE_API_KEY=from_file\nNEW_ONE=yes\n", encoding="utf-8")
    env = {"KITE_API_KEY": "already"}
    assert load_env_file(path, env) == ["NEW_ONE"]
    assert env == {"KITE_API_KEY": "already", "NEW_ONE": "yes"}
    assert load_env_file(tmp_path / "missing.env", env) == []


def test_config_hash_ignores_line_endings(tmp_path) -> None:
    from tests.conftest import CONFIG_DIR

    lf, crlf = tmp_path / "lf", tmp_path / "crlf"
    for d in (lf, crlf):
        d.mkdir()
    for f in CONFIG_DIR.iterdir():
        if f.is_file():
            data = f.read_bytes().replace(b"\r\n", b"\n")
            (lf / f.name).write_bytes(data)
            (crlf / f.name).write_bytes(data.replace(b"\n", b"\r\n"))
    assert config_hash(lf) == config_hash(crlf)


def test_sqlite_url_uses_forward_slashes(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TRADEMIND_DATA_DIR", str(tmp_path / "data"))
    assert "\\" not in runtime_paths().database_url


@pytest.mark.skipif(sys.platform == "win32", reason="non-Windows behaviour")
def test_power_helpers_are_noops_off_windows() -> None:
    with keep_awake() as awake:
        assert awake is False
    assert on_battery() is None


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_keep_awake_is_accepted_on_windows() -> None:
    with keep_awake() as awake:
        assert awake is True
    assert on_battery() in (True, False, None)


def test_tests_never_read_a_real_env_file() -> None:
    assert os.environ["TRADEMIND_ENV_FILE"].endswith("no-such.env")
