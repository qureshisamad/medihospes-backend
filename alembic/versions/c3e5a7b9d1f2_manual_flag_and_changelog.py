"""manual-edit flag on cells + roster change log

Revision ID: c3e5a7b9d1f2
Revises: b2d4f6a8c0e1
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e5a7b9d1f2"
down_revision: Union[str, None] = "b2d4f6a8c0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "roster_assignments",
        sa.Column(
            "is_manual", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.create_table(
        "roster_change_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("employee_name", sa.String(length=200), nullable=True),
        sa.Column("work_date", sa.Date(), nullable=True),
        sa.Column("detail", sa.String(length=400), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=True),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_roster_change_log_id"), "roster_change_log", ["id"]
    )
    op.create_index(
        op.f("ix_roster_change_log_work_date"), "roster_change_log", ["work_date"]
    )
    op.create_index(
        op.f("ix_roster_change_log_changed_at"), "roster_change_log", ["changed_at"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_roster_change_log_changed_at"), table_name="roster_change_log")
    op.drop_index(op.f("ix_roster_change_log_work_date"), table_name="roster_change_log")
    op.drop_index(op.f("ix_roster_change_log_id"), table_name="roster_change_log")
    op.drop_table("roster_change_log")
    op.drop_column("roster_assignments", "is_manual")
