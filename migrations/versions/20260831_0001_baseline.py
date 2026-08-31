"""Adopt the current MMI2 schema as the Alembic baseline.

Revision ID: 20260831_0001
Revises:
Create Date: 2026-08-31

The upgrade is intentionally adoption-safe: current development databases created
with SQLAlchemy metadata are accepted without trying to recreate their tables.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260831_0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _index_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {item["name"] for item in inspector.get_indexes(table) if item.get("name")}


def _ensure_index(name: str, table: str, columns: list[str], *, unique: bool = False) -> None:
    if name not in _index_names(table):
        op.create_index(name, table, columns, unique=unique)


def upgrade() -> None:
    if not _has_table("employees"):
        op.create_table(
            "employees",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("work_number", sa.String(length=64), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("team", sa.String(length=1), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("ix_employees_work_number", "employees", ["work_number"], unique=True)
    _ensure_index("ix_employees_full_name", "employees", ["full_name"])
    _ensure_index("ix_employees_team", "employees", ["team"])

    if not _has_table("shift_entries"):
        op.create_table(
            "shift_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("shift_type", sa.String(length=32), nullable=False),
            sa.Column("raw_code", sa.String(length=64), nullable=False),
            sa.Column("source_file", sa.String(length=255), nullable=False),
            sa.Column("imported_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("employee_id", "work_date", name="uq_employee_work_date"),
        )
    _ensure_index("ix_shift_entries_employee_id", "shift_entries", ["employee_id"])
    _ensure_index("ix_shift_entries_work_date", "shift_entries", ["work_date"])
    _ensure_index("ix_shift_entries_shift_type", "shift_entries", ["shift_type"])

    if not _has_table("import_history"):
        op.create_table(
            "import_history",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("month", sa.Integer(), nullable=False),
            sa.Column("employees", sa.Integer(), nullable=False),
            sa.Column("shifts", sa.Integer(), nullable=False),
            sa.Column("schedule_blocks", sa.Integer(), nullable=False),
            sa.Column("duplicate_employee_rows", sa.Integer(), nullable=False),
            sa.Column("conflicting_days", sa.Integer(), nullable=False),
            sa.Column("imported_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("ix_import_history_content_hash", "import_history", ["content_hash"])
    _ensure_index("ix_import_history_year", "import_history", ["year"])
    _ensure_index("ix_import_history_month", "import_history", ["month"])
    _ensure_index("ix_import_history_imported_at", "import_history", ["imported_at"])

    if not _has_table("manual_edit_history"):
        op.create_table(
            "manual_edit_history",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("work_date", sa.Date(), nullable=True),
            sa.Column("field_name", sa.String(length=64), nullable=False),
            sa.Column("old_value", sa.String(length=255), nullable=False),
            sa.Column("new_value", sa.String(length=255), nullable=False),
            sa.Column("changed_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _ensure_index("ix_manual_edit_history_employee_id", "manual_edit_history", ["employee_id"])
    _ensure_index("ix_manual_edit_history_work_date", "manual_edit_history", ["work_date"])
    _ensure_index("ix_manual_edit_history_field_name", "manual_edit_history", ["field_name"])
    _ensure_index("ix_manual_edit_history_changed_at", "manual_edit_history", ["changed_at"])


def downgrade() -> None:
    # This is an adoption baseline for databases that may predate Alembic.
    # A destructive downgrade could delete real schedules, so baseline downgrade
    # intentionally leaves the adopted schema intact.
    pass
