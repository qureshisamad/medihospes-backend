"""rotation pattern scoped to a site (house)

Revision ID: d4f6b8a0c2e3
Revises: c3e5a7b9d1f2
Create Date: 2026-06-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f6b8a0c2e3"
down_revision: Union[str, None] = "c3e5a7b9d1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "rotation_patterns",
        sa.Column("site_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f("ix_rotation_patterns_site_id"), "rotation_patterns", ["site_id"]
    )
    op.create_foreign_key(
        "fk_rotation_patterns_site_id",
        "rotation_patterns",
        "sites",
        ["site_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_rotation_patterns_site_id", "rotation_patterns", type_="foreignkey"
    )
    op.drop_index(
        op.f("ix_rotation_patterns_site_id"), table_name="rotation_patterns"
    )
    op.drop_column("rotation_patterns", "site_id")
