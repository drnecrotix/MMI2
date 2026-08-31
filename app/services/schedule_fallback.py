from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Employee, ShiftEntry


TEAM_PHASE = {"А": 0, "Б": 1, "В": 2, "Г": 3}
WORK_TYPES = {"day", "night"}
REST_TYPES = {"rest"}


@dataclass(frozen=True)
class FallbackShift:
    work_date: date
    shift_type: str
    raw_code: str


@dataclass(frozen=True)
class FallbackSchedule:
    shifts: list[FallbackShift]
    confidence: str
    basis: str
    reference_date: date | None


def _is_work_day(day: date, phase: int) -> bool:
    return ((day.toordinal() + phase) % 4) < 2


def _infer_phase(entries: list[ShiftEntry]) -> tuple[int | None, str]:
    comparable = [entry for entry in entries if entry.shift_type in WORK_TYPES | REST_TYPES]
    if len(comparable) < 4:
        return None, "low"

    scores: list[tuple[int, int]] = []
    for phase in range(4):
        matches = 0
        for entry in comparable:
            actual_work = entry.shift_type in WORK_TYPES
            if _is_work_day(entry.work_date, phase) == actual_work:
                matches += 1
        scores.append((matches, phase))

    scores.sort(reverse=True)
    best_matches, best_phase = scores[0]
    if len(scores) > 1 and scores[1][0] == best_matches:
        return None, "low"

    accuracy = best_matches / len(comparable)
    if len(comparable) >= 12 and accuracy >= 0.80:
        confidence = "high"
    elif accuracy >= 0.65:
        confidence = "medium"
    else:
        confidence = "low"
    return best_phase, confidence


def generate_2x2_fallback(
    db: Session,
    employee: Employee,
    year: int,
    month: int,
) -> FallbackSchedule:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    history_start = first - timedelta(days=120)

    history = db.scalars(
        select(ShiftEntry)
        .where(
            ShiftEntry.employee_id == employee.id,
            ShiftEntry.work_date >= history_start,
            ShiftEntry.work_date < first,
        )
        .order_by(ShiftEntry.work_date)
    ).all()

    phase, confidence = _infer_phase(history)
    basis = "history"
    reference_date = history[-1].work_date if history else None

    if phase is None:
        phase = TEAM_PHASE.get(employee.team or "", 0)
        confidence = "low"
        basis = "team" if employee.team in TEAM_PHASE else "default"

    shifts: list[FallbackShift] = []
    current = first
    while current <= last:
        is_work = _is_work_day(current, phase)
        shifts.append(
            FallbackShift(
                work_date=current,
                shift_type="predicted_work" if is_work else "predicted_rest",
                raw_code="≈" if is_work else "•",
            )
        )
        current += timedelta(days=1)

    return FallbackSchedule(
        shifts=shifts,
        confidence=confidence,
        basis=basis,
        reference_date=reference_date,
    )
