"""Read-only TRADEMIND API (BLUEPRINT 4.1, 20). No endpoint can place or change anything."""

from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from trademind import __version__
from trademind.database.journal import Journal, jsonable
from trademind.services.learning.metrics import scoreboard
from trademind.shared.config import load_config, runtime_paths


def create_app(database_url: str | None = None, api_token: str | None = None) -> FastAPI:
    cfg = load_config()
    journal = Journal(database_url or runtime_paths().database_url)
    token = api_token if api_token is not None else os.environ.get("TRADEMIND_API_TOKEN", "")
    app = FastAPI(title="TRADEMIND", version=__version__)

    def auth(authorization: Annotated[str | None, Header()] = None) -> None:
        if not token:
            raise HTTPException(503, "TRADEMIND_API_TOKEN is not configured")
        expected = f"Bearer {token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(401, "invalid or missing bearer token")

    dashboard_html = (Path(__file__).parent / "static" / "dashboard.html").read_text()

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/dashboard")

    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> str:
        """Static page with no data in it; every data call needs the API token."""
        return dashboard_html

    @app.get("/health")
    def health() -> dict:
        try:
            db = "ok" if journal.ping() else "error"
        except Exception:
            db = "error"
        return {
            "status": "ok" if db == "ok" else "degraded",
            "db": db,
            "mode": str(cfg.settings.execution.mode),
            "version": __version__,
        }

    @app.get("/runs", dependencies=[Depends(auth)])
    def runs(limit: int = Query(50, ge=1, le=500)) -> list[dict]:
        return jsonable(journal.read_runs(limit).to_dict("records"))

    @app.get("/runs/{run_id}/scoreboard", dependencies=[Depends(auth)])
    def run_scoreboard(run_id: str, by: str | None = None) -> list[dict]:
        if journal.get_run(run_id) is None:
            raise HTTPException(404, "run not found")
        board = scoreboard(journal.read_trades(run_id), cfg.settings.analytics.min_trades, by)
        return jsonable(board.to_dict("records"))

    @app.get("/runs/{run_id}/trades", dependencies=[Depends(auth)])
    def run_trades(run_id: str, limit: int = Query(500, ge=1, le=5000)) -> list[dict]:
        if journal.get_run(run_id) is None:
            raise HTTPException(404, "run not found")
        return jsonable(journal.read_trades(run_id).head(limit).to_dict("records"))

    return app
