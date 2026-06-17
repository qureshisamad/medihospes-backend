"""coverage requirements + rest rule on rotation

Revision ID: b2d4f6a8c0e1
Revises: a1c2e3f4b5d6
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2d4f6a8c0e1"
down_revision: Union[str, None] = "a1c2e3f4b5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rotation_patterns",
        sa.Column(
            "min_rest_hours",
            sa.Float(),
            nullable=False,
            server_default="11",
        ),
    )
    op.create_table(
        "coverage_requirements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern_id", sa.Integer(), nullable=False),
        sa.Column("shift_type_id", sa.Integer(), nullable=False),
        sa.Column("required_count", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(
            ["pattern_id"], ["rotation_patterns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["shift_type_id"], ["shift_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "pattern_id", "shift_type_id", name="uq_pattern_shift_coverage"
        ),
    )
    op.create_index(
        op.f("ix_coverage_requirements_id"), "coverage_requirements", ["id"]
    )
    op.create_index(
        op.f("ix_coverage_requirements_pattern_id"),
        "coverage_requirements",
        ["pattern_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_coverage_requirements_pattern_id"),
        table_name="coverage_requirements",
    )
    op.drop_index(
        op.f("ix_coverage_requirements_id"), table_name="coverage_requirements"
    )
    op.drop_table("coverage_requirements")
    op.drop_column("rotation_patterns", "min_rest_hours")
