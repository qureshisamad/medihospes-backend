"""per-employee excluded sites (location restriction)

Revision ID: a7c9e1b3d5f6
Revises: f6b8d0a2c4e5
Create Date: 2026-10-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7c9e1b3d5f6"
down_revision: Union[str, None] = "f6b8d0a2c4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_excluded_sites",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "employee_id",
            sa.Integer(),
            sa.ForeignKey("employees.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "site_id",
            sa.Integer(),
            sa.ForeignKey("sites.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.UniqueConstraint(
            "employee_id", "site_id", name="uq_employee_excluded_site"
        ),
    )


def downgrade() -> None:
    op.drop_table("employee_excluded_sites")
