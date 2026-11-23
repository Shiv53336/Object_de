"""Alembic environment: runs on the connection Journal passes in (no alembic.ini needed)."""

from __future__ import annotations

from alembic import context

from trademind.database.models import metadata

connection = context.config.attributes["connection"]
context.configure(connection=connection, target_metadata=metadata, render_as_batch=True,
                  compare_type=True)
with context.begin_transaction():
    context.run_migrations()
