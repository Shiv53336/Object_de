from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from trademind.services.broker_gateway.kite import (
    ALLOWED_METHODS,
    AuthError,
    InstrumentDirectory,
    KiteGateway,
    KiteSource,
    ReadOnlyClient,
    TokenStore,
    date_chunks,
)
from trademind.services.instrument_registry.registry import build_instruments
from trademind.services.market_data.aggregate import BarAggregator
from trademind.shared.clock import IST
from trademind.shared.config import AppConfig

from .helpers import ts

# ---- fakes ---------------------------------------------------------------------------------


class NetworkException(Exception):
    pass


class TokenException(Exception):
    pass


class FakeKite:
    def __init__(self, fail_times: int = 0, exc: type[Exception] = NetworkException) -> None:
        self.calls: list[tuple] = []
        self.fail_times = fail_times
        self.exc = exc

    def historical_data(self, token, start, end, interval, continuous=False, oi=False):
        self.calls.append(("historical_data", token, start, end, interval))
        if self.fail_times:
            self.fail_times -= 1
            raise self.exc("Too many requests")
        rows, d = [], start.date()
        while d <= end.date():
            if d.weekday() < 5:
                for k in range(3):
                    t = datetime(d.year, d.month, d.day, 9, 15 + k, tzinfo=IST)
                    rows.append({"date": t, "open": 100.0, "high": 101.0, "low": 99.0,
                                 "close": 100.5, "volume": 10})
            d += timedelta(days=1)
        return rows

    def instruments(self, exchange=None):
        return DUMP[DUMP["exchange"] == exchange].to_dict("records") if exchange else DUMP.to_dict("records")

    def login_url(self):
        return "https://kite.example/login"

    def generate_session(self, request_token, api_secret):
        return {"access_token": f"tok-{request_token}"}

    def place_order(self, **kw):  # must never be reachable
        raise AssertionError("order call reached the client")


DUMP = pd.DataFrame(
    [
        {"instrument_token": 256265, "tradingsymbol": "NIFTY 50", "name": "NIFTY 50", "exchange": "NSE",
         "instrument_type": "EQ", "segment": "INDICES", "expiry": None, "lot_size": 0, "tick_size": 0.0},
        {"instrument_token": 738561, "tradingsymbol": "RELIANCE", "name": "RELIANCE", "exchange": "NSE",
         "instrument_type": "EQ", "segment": "NSE", "expiry": None, "lot_size": 1, "tick_size": 0.1},
        {"instrument_token": 1, "tradingsymbol": "NIFTY25DECFUT", "name": "NIFTY", "exchange": "NFO",
         "instrument_type": "FUT", "segment": "NFO-FUT", "expiry": date(2025, 12, 30), "lot_size": 65,
         "tick_size": 0.1},
        {"instrument_token": 2, "tradingsymbol": "NIFTY25NOVFUT", "name": "NIFTY", "exchange": "NFO",
         "instrument_type": "FUT", "segment": "NFO-FUT", "expiry": date(2025, 11, 25), "lot_size": 75,
         "tick_size": 0.1},
        {"instrument_token": 3, "tradingsymbol": "NIFTY25N1824000CE", "name": "NIFTY", "exchange": "NFO",
         "instrument_type": "CE", "segment": "NFO-OPT", "expiry": date(2025, 11, 18), "lot_size": 75,
         "tick_size": 0.05},
        {"instrument_token": 4, "tradingsymbol": "RELIANCE25NOVFUT", "name": "RELIANCE", "exchange": "NFO",
         "instrument_type": "FUT", "segment": "NFO-FUT", "expiry": date(2025, 11, 25), "lot_size": 500,
         "tick_size": 0.1},
    ]
)


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.t

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.t += s


def _gateway(client, clock: FakeClock | None = None) -> KiteGateway:
    c = clock or FakeClock()
    return KiteGateway(client, clock=c, sleep=c.sleep)


# ---- gateway -------------------------------------------------------------------------------


def test_read_only_client_blocks_everything_else() -> None:
    ro = ReadOnlyClient(FakeKite())
    assert ro.login_url().startswith("https://")
    for name in ("place_order", "orders", "positions", "margins", "holdings"):
        with pytest.raises(AttributeError, match="read-only"):
            getattr(ro, name)
    assert "historical_data" in ALLOWED_METHODS and len(ALLOWED_METHODS) == 8


def test_date_chunks_cover_range_without_gaps() -> None:
    chunks = date_chunks(date(2025, 1, 1), date(2025, 6, 30), 60)
    assert chunks[0][0] == date(2025, 1, 1) and chunks[-1][1] == date(2025, 6, 30)
    for (_, b), (c, _) in zip(chunks, chunks[1:], strict=False):
        assert c == b + timedelta(days=1)
    assert all((b - a).days < 60 for a, b in chunks)
    assert date_chunks(date(2025, 1, 2), date(2025, 1, 2), 60) == [(date(2025, 1, 2), date(2025, 1, 2))]


def test_throttle_spaces_calls() -> None:
    clock = FakeClock()
    g = _gateway(FakeKite(), clock)
    for _ in range(3):
        g.historical(1, datetime(2025, 9, 1), datetime(2025, 9, 1, 23, 59), "minute")
    assert clock.sleeps == pytest.approx([1 / 3, 1 / 3])


def test_retry_on_rate_limit_then_give_up() -> None:
    clock = FakeClock()
    ok = _gateway(FakeKite(fail_times=2), clock)
    assert ok.historical(1, datetime(2025, 9, 1), datetime(2025, 9, 1, 23, 59), "minute")
    assert 1.0 in clock.sleeps and 2.0 in clock.sleeps
    bad = _gateway(FakeKite(fail_times=10))
    with pytest.raises(NetworkException):
        bad.historical(1, datetime(2025, 9, 1), datetime(2025, 9, 1, 23, 59), "minute")


def test_expired_session_raises_auth_error() -> None:
    g = _gateway(FakeKite(fail_times=1, exc=TokenException))
    with pytest.raises(AuthError, match="trademind login"):
        g.historical(1, datetime(2025, 9, 1), datetime(2025, 9, 1, 23, 59), "minute")


def test_token_store_expires_daily(tmp_path) -> None:
    store = TokenStore(tmp_path / "kite_token.json")
    assert store.load(date(2025, 9, 2)) is None
    store.save("abc", date(2025, 9, 2))
    assert store.load(date(2025, 9, 2)) == "abc"
    assert store.load(date(2025, 9, 3)) is None
    assert oct(store.path.stat().st_mode)[-3:] == "600"


def test_session_exchange() -> None:
    assert _gateway(FakeKite()).create_session("rt", "secret") == "tok-rt"


def test_kite_source_chunks_and_normalizes(tmp_path) -> None:
    fake = FakeKite()
    directory = InstrumentDirectory.load_or_fetch(_gateway(fake), tmp_path, date(2025, 11, 17))
    src = KiteSource(_gateway(fake), directory)
    df = src.get_bars("RELIANCE", "1minute", date(2025, 7, 1), date(2025, 9, 30))
    hist = [c for c in fake.calls if c[0] == "historical_data"]
    assert len(hist) == 2 and all(c[1] == 738561 and c[4] == "minute" for c in hist)
    assert str(df["ts"].dt.tz) == "Asia/Kolkata" and df["ts"].is_monotonic_increasing
    assert len(df) == 3 * 66  # 66 weekdays, three bars each
    assert df["ts"].iloc[0] == ts("09:15", date(2025, 7, 1))


def test_instrument_directory(cfg: AppConfig, tmp_path) -> None:
    fake = FakeKite()
    d = InstrumentDirectory.load_or_fetch(_gateway(fake), tmp_path, date(2025, 11, 17))
    assert (tmp_path / "instruments-2025-11-17.csv").exists()
    assert d.token("NIFTY 50") == 256265
    assert d.lot_and_tick("NIFTY 50", "index", date(2025, 11, 17)) == (75, 0.1)  # nearest future
    assert d.lot_and_tick("RELIANCE", "stock", date(2025, 11, 17)) == (1, 0.1)
    exp = d.expiries(date(2025, 11, 17))
    assert exp["NIFTY 50"] == [date(2025, 11, 18), date(2025, 11, 25), date(2025, 12, 30)]
    assert exp["STOCKS"] == [date(2025, 11, 25)]
    again = InstrumentDirectory.load_or_fetch(_gateway(FakeKite()), tmp_path, date(2025, 11, 17))
    assert again.token("RELIANCE") == 738561  # served from the cached file
    inst = build_instruments(cfg.settings, {"NIFTY 50": (65, 0.1)})
    assert inst["NIFTY 50"].lot_size == 65 and inst["NIFTY BANK"].lot_size == 30


# ---- aggregator ----------------------------------------------------------------------------


def _t(hhmmss: str) -> pd.Timestamp:
    h, m, s = map(int, hhmmss.split(":"))
    return pd.Timestamp(datetime(2025, 9, 2, h, m, s), tz=IST)


def test_ohlc_and_volume_from_ticks(cfg: AppConfig) -> None:
    agg = BarAggregator(cfg.settings.session)
    assert agg.on_tick("A", _t("09:15:01"), 100.0, 10) == []
    agg.on_tick("A", _t("09:15:20"), 102.0, 25)
    agg.on_tick("A", _t("09:15:40"), 99.0, 40)
    agg.on_tick("A", _t("09:15:59"), 101.0, 50)
    (b1,) = agg.on_tick("A", _t("09:16:05"), 101.5, 60)
    assert (b1["ts"], b1["open"], b1["high"], b1["low"], b1["close"], b1["volume"]) == (
        _t("09:15:00"), 100.0, 102.0, 99.0, 101.0, 50)
    (b2,) = agg.flush(_t("09:17:00"))
    assert b2["ts"] == _t("09:16:00") and b2["volume"] == 10


def test_out_of_order_tick_within_bar_keeps_latest_close(cfg: AppConfig) -> None:
    agg = BarAggregator(cfg.settings.session)
    agg.on_tick("A", _t("09:20:10"), 100.0)
    agg.on_tick("A", _t("09:20:50"), 103.0)
    agg.on_tick("A", _t("09:20:30"), 97.0)
    (b,) = agg.flush(_t("09:21:00"))
    assert (b["high"], b["low"], b["close"], b["volume"]) == (103.0, 97.0, 103.0, 0)


def test_empty_minute_produces_no_bar_and_late_ticks_ignored(cfg: AppConfig) -> None:
    agg = BarAggregator(cfg.settings.session)
    agg.on_tick("A", _t("09:15:10"), 100.0)
    (b,) = agg.on_tick("A", _t("09:18:10"), 101.0)
    assert b["ts"] == _t("09:15:00")
    assert agg.on_tick("A", _t("09:15:30"), 99.0) == [] and agg.late_ticks == 1
    assert agg.flush(_t("09:18:30")) == []  # 09:18 bar not finished yet
    assert [x["ts"] for x in agg.flush(_t("09:19:00"))] == [_t("09:18:00")]


def test_outside_session_ignored_and_seed(cfg: AppConfig) -> None:
    agg = BarAggregator(cfg.settings.session)
    assert agg.on_tick("A", _t("09:14:59"), 100.0, 5) == []
    assert agg.on_tick("A", _t("15:30:00"), 100.0, 5) == []
    assert agg.flush(_t("15:40:00")) == []
    agg.seed("A", 1000, _t("10:00:00"))
    assert agg.on_tick("A", _t("10:00:30"), 100.0, 1100) == []  # already backfilled minute
    agg.on_tick("A", _t("10:01:30"), 100.0, 1100)
    (b,) = agg.flush(_t("10:02:00"))
    assert b["volume"] == 100


# ---- CLI with a fake Kite ------------------------------------------------------------------


def test_cli_login_and_download(monkeypatch, tmp_path) -> None:
    from typer.testing import CliRunner

    import trademind.cli as cli

    monkeypatch.setenv("KITE_API_KEY", "k")
    monkeypatch.setenv("KITE_API_SECRET", "s")
    monkeypatch.setattr(cli, "make_kite_client", lambda key, token=None: ReadOnlyClient(FakeKite()))
    monkeypatch.setattr(FakeKite, "profile", lambda self: {"user_name": "Test"}, raising=False)
    monkeypatch.setattr(cli, "_now", lambda: pd.Timestamp("2025-11-17 08:30", tz=IST))
    runner = CliRunner()
    r = runner.invoke(cli.app, ["login"], input="rt123\n")
    assert r.exit_code == 0 and "Logged in as Test" in r.output
    r = runner.invoke(cli.app, ["data", "download", "--start", "2025-09-01", "--end", "2025-09-05",
                                "--symbols", "RELIANCE"])
    assert r.exit_code == 0, r.output
    assert "RELIANCE: +15 bars" in r.output


def test_cli_download_requires_login(monkeypatch) -> None:
    from typer.testing import CliRunner

    import trademind.cli as cli

    monkeypatch.setenv("KITE_API_KEY", "k")
    r = CliRunner().invoke(cli.app, ["data", "download", "--start", "2025-09-01", "--end", "2025-09-02"])
    assert r.exit_code == 2 and "trademind login" in r.output
