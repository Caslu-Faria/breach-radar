"""create breaches table

Revision ID: cacfe7a705cd
Revises:
Create Date: 2026-06-13 17:23:13.375740

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cacfe7a705cd"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "breaches",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("domain", sa.String(), nullable=True),
        sa.Column("breach_date", sa.String(length=10), nullable=True),
        sa.Column("added_date", sa.String(length=25), nullable=True),
        sa.Column("pwn_count", sa.Integer(), nullable=False),
        sa.Column("data_classes", sa.JSON(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_sensitive", sa.Boolean(), nullable=False),
        sa.Column("is_spam_list", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("breaches")
