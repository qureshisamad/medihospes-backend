"""Add job_titles table and convert job_title/required_role to string

Revision ID: a3b7c9d1e2f4
Revises: e9870e7fd395
Create Date: 2026-05-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b7c9d1e2f4"
down_revision: Union[str, None] = "e9870e7fd395"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create job_titles table
    op.create_table(
        "job_titles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_titles_id"), "job_titles", ["id"], unique=False)
    op.create_index(op.f("ix_job_titles_name"), "job_titles", ["name"], unique=True)

    # Convert users.job_title from enum to varchar
    # For SQLite, we need to use batch mode
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "job_title",
            existing_type=sa.Enum(
                "ADMINISTRATIVE", "NURSE", "DOCTOR", "TECHNICIAN", "SUPPORT",
                name="jobtitle",
            ),
            type_=sa.String(length=100),
            existing_nullable=False,
        )

    # Convert shifts.required_role from enum to varchar
    with op.batch_alter_table("shifts") as batch_op:
        batch_op.alter_column(
            "required_role",
            existing_type=sa.Enum(
                "ADMINISTRATIVE", "NURSE", "DOCTOR", "TECHNICIAN", "SUPPORT",
                name="jobtitle",
            ),
            type_=sa.String(length=100),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Convert back to enum
    jobtitle_enum = sa.Enum(
        "ADMINISTRATIVE", "NURSE", "DOCTOR", "TECHNICIAN", "SUPPORT",
        name="jobtitle",
    )

    with op.batch_alter_table("shifts") as batch_op:
        batch_op.alter_column(
            "required_role",
            existing_type=sa.String(length=100),
            type_=jobtitle_enum,
            existing_nullable=False,
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "job_title",
            existing_type=sa.String(length=100),
            type_=jobtitle_enum,
            existing_nullable=False,
        )

    op.drop_index(op.f("ix_job_titles_name"), table_name="job_titles")
    op.drop_index(op.f("ix_job_titles_id"), table_name="job_titles")
    op.drop_table("job_titles")
