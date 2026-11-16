"""Strategy metrics and scoreboard (PLAN 9.1)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

COLUMNS = [
    "n_trades",
    "win_rate",
    "expectancy_r",
    "profit_factor",
    "max_drawdown_r",
    "avg_win_r",
    "avg_loss_r",
    "total_net_pnl",
    "total_costs",
    "cost_share",
    "false_breakout_rate",
    "stopped_then_right_rate",
    "insufficient_sample",
]


def max_drawdown(r: np.ndarray) -> float:
    if len(r) == 0:
        return 0.0
    curve = np.cumsum(r)
    peak = np.maximum.accumulate(np.r_[0.0, curve])[1:]
    return float(max((peak - curve).max(), 0.0))


def compute_metrics(trades: pd.DataFrame, min_trades: int) -> dict:
    n = len(trades)
    out: dict = dict.fromkeys(COLUMNS, math.nan)
    out.update(n_trades=n, insufficient_sample=n < min_trades, total_net_pnl=0.0, total_costs=0.0)
    if n == 0:
        out["max_drawdown_r"] = 0.0
        return out
    df = trades.sort_values(["exit_ts", "trade_id"]) if "exit_ts" in trades else trades
    net = df["net_pnl"].to_numpy(dtype=float)
    r = df["r_multiple"].to_numpy(dtype=float)
    gross = df["gross_pnl"].to_numpy(dtype=float)
    win, loss = net > 0, net < 0
    out["win_rate"] = float(win.mean())
    out["expectancy_r"] = float(r.mean())
    out["avg_win_r"] = float(r[win].mean()) if win.any() else math.nan
    out["avg_loss_r"] = float(r[loss].mean()) if loss.any() else math.nan
    gains, losses = net[win].sum(), -net[loss].sum()
    out["profit_factor"] = (
        float(gains / losses) if losses > 0 else (math.inf if gains > 0 else math.nan)
    )
    out["max_drawdown_r"] = max_drawdown(r)
    out["total_net_pnl"] = float(net.sum())
    out["total_costs"] = float(df["costs"].sum())
    denom = np.abs(gross).sum()
    out["cost_share"] = float(out["total_costs"] / denom) if denom > 0 else math.nan
    stop = (df["exit_reason"] == "STOP").to_numpy()
    out["false_breakout_rate"] = float((stop & (df["mfe_r"].to_numpy(dtype=float) < 0.5)).mean())
    if "target_hit_after_stop" in df:
        th = df.loc[stop & df["target"].notna().to_numpy(), "target_hit_after_stop"].dropna()
        out["stopped_then_right_rate"] = float(th.astype(bool).mean()) if len(th) else math.nan
    return out


def scoreboard(trades: pd.DataFrame, min_trades: int, by: str | None = None) -> pd.DataFrame:
    keys = ["instance_id"] + ([by] if by else [])
    if trades.empty:
        return pd.DataFrame(columns=keys + COLUMNS)
    df = trades.copy()
    if by:
        df[by] = df["context"].map(lambda c: str((c or {}).get(by, "unknown")))
    rows = []
    for key, grp in df.groupby(keys, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(keys, key, strict=True)), **compute_metrics(grp, min_trades)})
    return pd.DataFrame(rows, columns=keys + COLUMNS)


def to_markdown(board: pd.DataFrame) -> str:
    if board.empty:
        return "_no trades_"
    show = [c for c in board.columns if c not in ("insufficient_sample", "total_costs")]
    lines = ["| " + " | ".join(show) + " |", "|" + "---|" * len(show)]
    for _, row in board.iterrows():
        cells = []
        for c in show:
            v = row[c]
            if c == "n_trades":
                cells.append(f"{int(v)}{'*' if row['insufficient_sample'] else ''}")
            elif isinstance(v, float | np.floating):
                cells.append("-" if math.isnan(v) else ("inf" if math.isinf(v) else f"{v:,.2f}"))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("`*` fewer trades than analytics.min_trades: not enough to judge.")
    return "\n".join(lines)
