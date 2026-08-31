"""Record the administrator responsible for each schedule import.

Revision ID: 20260901_0004
Revises: 20260831_0003
Create Date: 2026-09-01
"""
from alembic import op
import sqlalchemy as sa

revision = "20260901_0004"
down_revision = "20260831_0003"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return any(item["name"] == column for item in sa.inspect(op.get_bind()).get_columns(table))


def _has_index(table: str, index_name: str) -> bool:
    if not _has_table(table):
        return False
    return any(item["name"] == index_name for item in sa.inspect(op.get_bind()).get_indexes(table))


def upgrade() -> None:
    if _has_table("import_history") and not _has_column("import_history", "imported_by"):
        with op.batch_alter_table("import_history") as batch_op:
            batch_op.add_column(sa.Column("imported_by", sa.String(length=255), nullable=True))

    if _has_table("import_history") and not _has_index("import_history", "ix_import_history_imported_by"):
        op.create_index("ix_import_history_imported_by", "import_history", ["imported_by"], unique=False)


def downgrade() -> None:
    if _has_table("import_history") and _has_index("import_history", "ix_import_history_imported_by"):
        op.drop_index("ix_import_history_imported_by", table_name="import_history")

    if _has_table("import_history") and _has_column("import_history", "imported_by"):
        with op.batch_alter_table("import_history") as batch_op:
            batch_op.drop_column("imported_by")
