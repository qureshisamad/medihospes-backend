"""pending (benched surplus) flag on roster cells

Revision ID: e5a7c9b1d3f4
Revises: d4f6b8a0c2e3
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5a7c9b1d3f4"
down_revision: Union[str, None] = "d4f6b8a0c2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "roster_assignments",
        sa.Column(
            "is_pending", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("roster_assignments", "is_pending")
