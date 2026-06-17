"""rotation library (shift cycle per category)

Revision ID: a1c2e3f4b5d6
Revises: ff0494d73eb6
Create Date: 2026-06-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c2e3f4b5d6"
down_revision: Union[str, None] = "ff0494d73eb6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rotation_patterns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("job_title", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rotation_patterns_id"), "rotation_patterns", ["id"])
    op.create_index(
        op.f("ix_rotation_patterns_job_title"), "rotation_patterns", ["job_title"]
    )

    op.create_table(
        "rotation_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("shift_type_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["pattern_id"], ["rotation_patterns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["shift_type_id"], ["shift_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pattern_id", "position", name="uq_pattern_position"),
    )
    op.create_index(op.f("ix_rotation_steps_id"), "rotation_steps", ["id"])
    op.create_index(
        op.f("ix_rotation_steps_pattern_id"), "rotation_steps", ["pattern_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_rotation_steps_pattern_id"), table_name="rotation_steps")
    op.drop_index(op.f("ix_rotation_steps_id"), table_name="rotation_steps")
    op.drop_table("rotation_steps")
    op.drop_index(
        op.f("ix_rotation_patterns_job_title"), table_name="rotation_patterns"
    )
    op.drop_index(op.f("ix_rotation_patterns_id"), table_name="rotation_patterns")
    op.drop_table("rotation_patterns")
