"""special-employee shift restriction on employees

Revision ID: f6b8d0a2c4e5
Revises: e5a7c9b1d3f4
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6b8d0a2c4e5"
down_revision: Union[str, None] = "e5a7c9b1d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "employees",
        sa.Column("shift_restriction", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("employees", "shift_restriction")
