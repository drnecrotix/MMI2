"""Record the authenticated admin on manual audit entries.

Revision ID: 20260831_0002
Revises: 20260831_0001
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

revision = "20260831_0002"
down_revision = "20260831_0001"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(item["name"] == column for item in inspector.get_columns(table))


def upgrade() -> None:
    if not _has_column("manual_edit_history", "changed_by"):
        op.add_column(
            "manual_edit_history",
            sa.Column("changed_by", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    if _has_column("manual_edit_history", "changed_by"):
        with op.batch_alter_table("manual_edit_history") as batch_op:
            batch_op.drop_column("changed_by")
