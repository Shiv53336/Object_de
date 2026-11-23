"""Run coverage (sessions actually simulated) and live bid/ask quotes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runs") as batch:
        batch.add_column(sa.Column("n_sessions", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("first_session", sa.Date(), nullable=True))
        batch.add_column(sa.Column("last_session", sa.Date(), nullable=True))
    op.create_table(
        "quotes",
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.run_id"), nullable=False),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_bid", sa.Float(), nullable=True),
        sa.Column("first_ask", sa.Float(), nullable=True),
        sa.Column("last_bid", sa.Float(), nullable=True),
        sa.Column("last_ask", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("run_id", "symbol", "ts"),
    )


def downgrade() -> None:
    op.drop_table("quotes")
    with op.batch_alter_table("runs") as batch:
        batch.drop_column("last_session")
        batch.drop_column("first_session")
        batch.drop_column("n_sessions")
