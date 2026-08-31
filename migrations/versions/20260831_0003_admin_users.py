"""Add database-backed administrator accounts.

Revision ID: 20260831_0003
Revises: 20260831_0002
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = "20260831_0003"
down_revision = "20260831_0002"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _column_length(table: str, column: str) -> int | None:
    for item in sa.inspect(op.get_bind()).get_columns(table):
        if item["name"] == column:
            return getattr(item["type"], "length", None)
    return None


def upgrade() -> None:
    if _has_table("manual_edit_history") and _column_length("manual_edit_history", "changed_by") != 255:
        with op.batch_alter_table("manual_edit_history") as batch_op:
            batch_op.alter_column(
                "changed_by",
                existing_type=sa.String(length=64),
                type_=sa.String(length=255),
                existing_nullable=True,
            )

    if not _has_table("admin_users"):
        op.create_table(
            "admin_users",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_admin_users_email", "admin_users", ["email"], unique=True)
        op.create_index("ix_admin_users_role", "admin_users", ["role"], unique=False)
        op.create_index("ix_admin_users_is_active", "admin_users", ["is_active"], unique=False)


def downgrade() -> None:
    if _has_table("admin_users"):
        op.drop_index("ix_admin_users_is_active", table_name="admin_users")
        op.drop_index("ix_admin_users_role", table_name="admin_users")
        op.drop_index("ix_admin_users_email", table_name="admin_users")
        op.drop_table("admin_users")

    if _has_table("manual_edit_history") and _column_length("manual_edit_history", "changed_by") == 255:
        with op.batch_alter_table("manual_edit_history") as batch_op:
            batch_op.alter_column(
                "changed_by",
                existing_type=sa.String(length=255),
                type_=sa.String(length=64),
                existing_nullable=True,
            )
