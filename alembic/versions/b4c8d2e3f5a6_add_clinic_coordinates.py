"""Add latitude and longitude to clinics

Revision ID: b4c8d2e3f5a6
Revises: a3b7c9d1e2f4
Create Date: 2026-05-01 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c8d2e3f5a6"
down_revision: Union[str, None] = "a3b7c9d1e2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clinics", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("clinics", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("clinics", "longitude")
    op.drop_column("clinics", "latitude")
