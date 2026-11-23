"""Research ledger: an append-only, git-tracked record of what has been tested (DECISIONS D29).

Two files under `trademind/ledger/`:
  * `hypotheses.jsonl`: one line per distinct hypothesis tested on real research data, that is
    (strategy id, version, timeframe, parameter hash). Reruns and synthetic runs add nothing.
    The Bonferroni correction counts these lines across all strategies.
  * `holdout_looks.jsonl`: one line per holdout evaluation. A strategy gets `max_holdout_evals`
    looks per holdout window in total, whatever its version, timeframe or parameters.

Being in the repository, the counts survive a new laptop, a fresh database or a move to the
server, and every look shows in git history. `validate` refuses to run while the ledger has
uncommitted changes, so a look cannot be lost by not committing it.

Unreadable lines raise LedgerError rather than being skipped: the gate fails closed.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from trademind.shared.config import AppConfig
from trademind.shared.exceptions import TrademindError

REAL_SOURCES = frozenset({"parquet", "csv", "kite"})
HYPOTHESES = "hypotheses.jsonl"
LOOKS = "holdout_looks.jsonl"


class LedgerError(TrademindError):
    pass


@dataclass(frozen=True)
class Hypothesis:
    strategy_id: str
    version: str
    timeframe: str
    params_hash: str

    @property
    def key(self) -> str:
        return f"{self.strategy_id}|{self.version}|{self.timeframe}|{self.params_hash}"

    @property
    def instance_id(self) -> str:
        return f"{self.strategy_id}@{self.timeframe}"


def ledger_dir(cfg: AppConfig) -> Path:
    env = os.environ.get("TRADEMIND_LEDGER_DIR")
    return Path(env) if env else Path(cfg.config_dir).resolve().parent / "ledger"


class ResearchLedger:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # ---- storage -----------------------------------------------------------------------
    def _read(self, name: str) -> list[dict]:
        path = self.root / name
        if not path.exists():
            return []
        rows = []
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise LedgerError(f"{path}:{n} is not valid JSON; fix it by hand, never delete lines"
                                  ) from exc
            if not isinstance(row, dict):
                raise LedgerError(f"{path}:{n} is not a JSON object")
            rows.append(row)
        return rows

    def _append(self, name: str, row: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / name, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    @staticmethod
    def _stamp() -> dict:
        return {"recorded_at": datetime.now(UTC).isoformat(timespec="seconds"), "host": socket.gethostname()}

    # ---- hypotheses ----------------------------------------------------------------------
    def hypotheses(self) -> list[dict]:
        return self._read(HYPOTHESES)

    def distinct_hypotheses(self) -> int:
        return len({r["key"] for r in self.hypotheses()})

    def record_hypothesis(self, h: Hypothesis, *, run_id: str, period_start: date, period_end: date,
                          source: str) -> bool:
        """Adds the hypothesis if it is new. Returns whether it was new."""
        if source not in REAL_SOURCES:
            return False
        if h.key in {r["key"] for r in self.hypotheses()}:
            return False
        self._append(HYPOTHESES, {"key": h.key, **asdict(h), "first_run_id": run_id,
                                  "period_start": period_start.isoformat(),
                                  "period_end": period_end.isoformat(), "source": source, **self._stamp()})
        return True

    # ---- holdout looks -------------------------------------------------------------------
    def looks(self, strategy_id: str, window: tuple[date, date]) -> list[dict]:
        w = [window[0].isoformat(), window[1].isoformat()]
        return [r for r in self._read(LOOKS) if r["strategy_id"] == strategy_id and r["window"] == w]

    def record_look(self, h: Hypothesis, *, window: tuple[date, date], period: tuple[date, date],
                    research_run_id: str, holdout_run_id: str, passed: bool, source: str) -> dict:
        row = {**asdict(h), "key": h.key, "window": [window[0].isoformat(), window[1].isoformat()],
               "period": [period[0].isoformat(), period[1].isoformat()],
               "research_run_id": research_run_id, "holdout_run_id": holdout_run_id,
               "passed": passed, "source": source, **self._stamp()}
        self._append(LOOKS, row)
        return row

    # ---- git ---------------------------------------------------------------------------------
    def uncommitted(self) -> bool | None:
        """True if the ledger has changes git does not have yet; None outside a git checkout."""
        probe = self.root if self.root.exists() else self.root.parent
        try:
            out = subprocess.run(["git", "status", "--porcelain", "--", str(self.root)], cwd=probe,
                                 capture_output=True, text=True, encoding="utf-8", timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.returncode != 0:
            return None
        return bool(out.stdout.strip())
