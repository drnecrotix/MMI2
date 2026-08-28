from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    work_number: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), index=True)
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
