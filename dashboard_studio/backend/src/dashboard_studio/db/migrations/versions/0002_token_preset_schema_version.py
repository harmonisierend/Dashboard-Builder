"""add token_presets.token_schema_version

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-01
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | str | None = None
depends_on: Sequence[str] | str | None = None


def upgrade() -> None:
    op.add_column(
        "token_presets",
        sa.Column("token_schema_version", sa.Integer, nullable=False, server_default="1"),
    )


def downgrade() -> None:
    # SQLite has no native DROP COLUMN; batch mode rebuilds the table.
    with op.batch_alter_table("token_presets") as batch_op:
        batch_op.drop_column("token_schema_version")
