from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    team: Mapped[str | None] = mapped_column(String(1), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    shifts: Mapped[list["ShiftEntry"]] = relationship(back_populates="employee", cascade="all, delete-orphan")


class ShiftEntry(Base):
    __tablename__ = "shift_entries"
    __table_args__ = (UniqueConstraint("employee_id", "work_date", name="uq_employee_work_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    shift_type: Mapped[str] = mapped_column(String(32), index=True)
    raw_code: Mapped[str] = mapped_column(String(64), default="")
    source_file: Mapped[str] = mapped_column(String(255), default="")
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    employee: Mapped[Employee] = relationship(back_populates="shifts")


class ImportHistory(Base):
    __tablename__ = "import_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer, index=True)
    employees: Mapped[int] = mapped_column(Integer, default=0)
    shifts: Mapped[int] = mapped_column(Integer, default=0)
    schedule_blocks: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_employee_rows: Mapped[int] = mapped_column(Integer, default=0)
    conflicting_days: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="admin", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ManualEditHistory(Base):
    __tablename__ = "manual_edit_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    work_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    field_name: Mapped[str] = mapped_column(String(64), index=True)
    old_value: Mapped[str] = mapped_column(String(255), default="")
    new_value: Mapped[str] = mapped_column(String(255), default="")
    changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
