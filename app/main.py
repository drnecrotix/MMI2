from calendar import monthrange
from datetime import date
from hashlib import sha256

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Employee, ImportHistory, ManualEditHistory, ShiftEntry
from app.schemas import (
    AdminEmployeeUpdate,
    AdminLoginRequest,
    AdminShiftUpdate,
    AdminTokenResponse,
    LoginRequest,
    MonthlyScheduleOut,
    ShiftOut,
    TokenResponse,
)
from app.security import (
    create_access_token,
    create_admin_token,
    decode_access_token,
    decode_admin_token,
    verify_admin_credentials,
)
from app.services.excel_import import _shift_type, import_schedule_xlsx
from app.services.excel_period import detect_schedule_period
from app.services.excel_preview import preview_schedule_xlsx
from app.services.schedule_compare import compare_preview_to_database
from app.services.schedule_fallback import generate_2x2_fallback

app = FastAPI(
    title=settings.app_name,
    version="0.10.0",
    description="MMI2 monthly work schedule import and employee API",
)
templates = Jinja2Templates(directory="app/templates")
bearer = HTTPBearer(auto_error=False)
TEAM_CODES = {"А", "Б", "В", "Г"}


def current_employee(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Employee:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Липсва access token.")
    work_number = decode_access_token(credentials.credentials)
    if not work_number:
        raise HTTPException(status_code=401, detail="Невалиден или изтекъл employee token.")
    employee = db.scalar(select(Employee).where(Employee.work_number == work_number))
    if not employee:
        raise HTTPException(status_code=401, detail="Служителят не е намерен.")
    return employee


def current_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Необходим е admin login.")
    username = decode_admin_token(credentials.credentials)
    if not username or username != settings.admin_username:
        raise HTTPException(status_code=401, detail="Невалидна или изтекла admin сесия.")
    return username


def resolve_period(content: bytes, filename: str, year: int | None, month: int | None) -> tuple[int, int, dict]:
    if (year is None) != (month is None):
        raise HTTPException(status_code=400, detail="Въведи едновременно година и месец или остави и двете празни за автоматично разпознаване.")
    if year is not None and month is not None:
        if not 2020 <= year <= 2100 or not 1 <= month <= 12:
            raise HTTPException(status_code=400, detail="Невалиден период.")
        return year, month, {"source": "manual", "confidence": "manual", "evidence": "въведен от администратора"}
    detected = detect_schedule_period(content, filename)
    if detected is None:
        raise HTTPException(status_code=400, detail="Месецът и годината не могат да бъдат разпознати надеждно от Excel файла. Въведи ги ръчно.")
    return detected.year, detected.month, {
        "source": "auto",
        "confidence": detected.confidence,
        "evidence": detected.evidence,
    }


def get_admin_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Служителят не е намерен.")
    return employee


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"app_name": settings.app_name})


@app.get("/admin/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_login.html", context={"app_name": settings.app_name})


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html", context={"app_name": settings.app_name})


@app.get("/admin/employees", response_class=HTMLResponse)
def admin_employees_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_employees.html", context={"app_name": settings.app_name})


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    work_number = payload.work_number.strip()
    employee = db.scalar(select(Employee).where(Employee.work_number == work_number))
    if not employee:
        raise HTTPException(status_code=404, detail="Няма служител с този работен номер.")
    return TokenResponse(
        access_token=create_access_token(employee.work_number),
        employee_name=employee.full_name,
        work_number=employee.work_number,
        team=employee.team,
    )


@app.post("/api/v1/admin/auth/login", response_model=AdminTokenResponse)
def admin_login(payload: AdminLoginRequest):
    username = payload.username.strip()
    if not verify_admin_credentials(username, payload.password):
        raise HTTPException(status_code=401, detail="Невалидно admin име или парола.")
    return AdminTokenResponse(access_token=create_admin_token(username), username=username)


@app.get("/api/v1/admin/me")
def admin_me(username: str = Depends(current_admin)):
    return {"username": username, "authenticated": True}


@app.get("/api/v1/me")
def me(employee: Employee = Depends(current_employee)):
    return {"work_number": employee.work_number, "full_name": employee.full_name, "team": employee.team}


@app.get("/api/v1/me/schedule/{year}/{month}", response_model=MonthlyScheduleOut)
def my_schedule(
    year: int,
    month: int,
    employee: Employee = Depends(current_employee),
    db: Session = Depends(get_db),
):
    if not 2020 <= year <= 2100 or month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Невалиден месец.")
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    entries = db.scalars(
        select(ShiftEntry)
        .where(ShiftEntry.employee_id == employee.id, ShiftEntry.work_date >= first, ShiftEntry.work_date <= last)
        .order_by(ShiftEntry.work_date)
    ).all()

    if entries:
        return MonthlyScheduleOut(
            employee_name=employee.full_name,
            work_number=employee.work_number,
            team=employee.team,
            year=year,
            month=month,
            schedule_source="imported",
            is_estimated=False,
            shifts=[
                ShiftOut(
                    work_date=e.work_date,
                    shift_type=e.shift_type,
                    raw_code=e.raw_code,
                    estimated=False,
                )
                for e in entries
            ],
        )

    fallback = generate_2x2_fallback(db, employee, year, month)
    warning = (
        "Графикът за този месец още не е обновен. Показан е автоматично изчислен режим 2 на 2 "
        "(2 работни / 2 почивни дни). Той е ориентировъчен и може да се различава от официалния график."
    )
    return MonthlyScheduleOut(
        employee_name=employee.full_name,
        work_number=employee.work_number,
        team=employee.team,
        year=year,
        month=month,
        schedule_source="automatic_2x2",
        is_estimated=True,
        warning=warning,
        fallback_confidence=fallback.confidence,
        fallback_basis=fallback.basis,
        fallback_reference_date=fallback.reference_date,
        shifts=[
            ShiftOut(
                work_date=e.work_date,
                shift_type=e.shift_type,
                raw_code=e.raw_code,
                estimated=True,
            )
            for e in fallback.shifts
        ],
    )


@app.post("/api/v1/admin/preview")
async def preview_schedule(
    year: int | None = Form(default=None),
    month: int | None = Form(default=None),
    file: UploadFile = File(...),
    _admin: str = Depends(current_admin),
    db: Session = Depends(get_db),
):
    content = await file.read()
    filename = file.filename or "schedule.xlsx"
    resolved_year, resolved_month, period = resolve_period(content, filename, year, month)
    try:
        result = preview_schedule_xlsx(content, filename, resolved_year, resolved_month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    comparison = compare_preview_to_database(db, result, resolved_year, resolved_month)
    return {
        "status": "preview",
        "filename": filename,
        "year": resolved_year,
        "month": resolved_month,
        "period_detection": period,
        "employees_count": len(result.employees),
        "schedule_blocks": result.schedule_blocks,
        "duplicate_employee_rows": result.duplicate_employee_rows,
        "conflicting_days": result.conflicting_days,
        "unknown_codes": result.unknown_codes,
        "totals": result.totals,
        "comparison": comparison,
        "employees": result.employees,
    }


@app.post("/api/v1/admin/import")
async def import_schedule(
    year: int | None = Form(default=None),
    month: int | None = Form(default=None),
    file: UploadFile = File(...),
    _admin: str = Depends(current_admin),
    db: Session = Depends(get_db),
):
    content = await file.read()
    filename = file.filename or "schedule.xlsx"
    resolved_year, resolved_month, period = resolve_period(content, filename, year, month)
    try:
        result = import_schedule_xlsx(db, content, filename, resolved_year, resolved_month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    history = ImportHistory(
        filename=filename,
        content_hash=sha256(content).hexdigest(),
        year=resolved_year,
        month=resolved_month,
        employees=result.employees,
        shifts=result.shifts,
        schedule_blocks=result.schedule_blocks,
        duplicate_employee_rows=result.duplicate_employee_rows,
        conflicting_days=result.conflicting_days,
    )
    db.add(history)
    db.commit()
    db.refresh(history)
    return {
        "status": "imported",
        "import_id": history.id,
        "employees": result.employees,
        "shifts": result.shifts,
        "skipped_rows": result.skipped_rows,
        "schedule_blocks": result.schedule_blocks,
        "duplicate_employee_rows": result.duplicate_employee_rows,
        "conflicting_days": result.conflicting_days,
        "year": resolved_year,
        "month": resolved_month,
        "period_detection": period,
    }


@app.get("/api/v1/admin/imports")
def import_history(_admin: str = Depends(current_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(ImportHistory).order_by(ImportHistory.imported_at.desc()).limit(100)).all()
    return {"imports": [
        {
            "id": row.id,
            "filename": row.filename,
            "year": row.year,
            "month": row.month,
            "employees": row.employees,
            "shifts": row.shifts,
            "schedule_blocks": row.schedule_blocks,
            "duplicate_employee_rows": row.duplicate_employee_rows,
            "conflicting_days": row.conflicting_days,
            "content_hash": row.content_hash,
            "imported_at": row.imported_at.isoformat(),
        } for row in rows
    ]}


@app.get("/api/v1/admin/employees")
def admin_employee_search(
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=50, ge=1, le=200),
    _admin: str = Depends(current_admin),
    db: Session = Depends(get_db),
):
    statement = select(Employee).order_by(Employee.full_name, Employee.work_number).limit(limit)
    term = q.strip()
    if term:
        pattern = f"%{term}%"
        statement = select(Employee).where(or_(Employee.work_number.ilike(pattern), Employee.full_name.ilike(pattern))).order_by(Employee.full_name, Employee.work_number).limit(limit)
    employees = db.scalars(statement).all()
    return {"employees": [{"id": e.id, "work_number": e.work_number, "full_name": e.full_name, "team": e.team} for e in employees]}


@app.get("/api/v1/admin/employees/{employee_id}/schedule/{year}/{month}")
def admin_employee_schedule(
    employee_id: int,
    year: int,
    month: int,
    _admin: str = Depends(current_admin),
    db: Session = Depends(get_db),
):
    if not 2020 <= year <= 2100 or not 1 <= month <= 12:
        raise HTTPException(status_code=400, detail="Невалиден период.")
    employee = get_admin_employee(db, employee_id)
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    entries = db.scalars(select(ShiftEntry).where(ShiftEntry.employee_id == employee.id, ShiftEntry.work_date >= first, ShiftEntry.work_date <= last).order_by(ShiftEntry.work_date)).all()
    return {
        "employee": {"id": employee.id, "work_number": employee.work_number, "full_name": employee.full_name, "team": employee.team},
        "year": year,
        "month": month,
        "shifts": [{"work_date": e.work_date.isoformat(), "shift_type": e.shift_type, "raw_code": e.raw_code, "source_file": e.source_file} for e in entries],
    }


@app.patch("/api/v1/admin/employees/{employee_id}")
def admin_update_employee(
    employee_id: int,
    payload: AdminEmployeeUpdate,
    _admin: str = Depends(current_admin),
    db: Session = Depends(get_db),
):
    employee = get_admin_employee(db, employee_id)
    changes = []
    if payload.full_name is not None:
        new_name = payload.full_name.strip()
        if len(new_name) < 3:
            raise HTTPException(status_code=400, detail="Името е твърде кратко.")
        if new_name != employee.full_name:
            changes.append(("full_name", employee.full_name, new_name))
            employee.full_name = new_name
    if payload.team is not None:
        new_team = payload.team.strip().upper()
        if new_team not in TEAM_CODES:
            raise HTTPException(status_code=400, detail="Смяната трябва да е А, Б, В или Г.")
        if new_team != employee.team:
            changes.append(("team", employee.team or "", new_team))
            employee.team = new_team
    for field_name, old_value, new_value in changes:
        db.add(ManualEditHistory(
            employee_id=employee.id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            changed_by=_admin,
        ))
    db.commit()
    return {
        "status": "updated" if changes else "unchanged",
        "employee": {"id": employee.id, "work_number": employee.work_number, "full_name": employee.full_name, "team": employee.team},
        "changes": len(changes),
    }


@app.put("/api/v1/admin/employees/{employee_id}/schedule/{work_date}")
def admin_update_shift(
    employee_id: int,
    work_date: date,
    payload: AdminShiftUpdate,
    _admin: str = Depends(current_admin),
    db: Session = Depends(get_db),
):
    employee = get_admin_employee(db, employee_id)
    shift_type, raw_code = _shift_type(payload.raw_code)
    entry = db.scalar(select(ShiftEntry).where(ShiftEntry.employee_id == employee.id, ShiftEntry.work_date == work_date))
    if entry:
        old_value = f"{entry.shift_type}|{entry.raw_code}"
        new_value = f"{shift_type}|{raw_code}"
        if old_value == new_value:
            return {"status": "unchanged", "work_date": work_date, "shift_type": shift_type, "raw_code": raw_code}
        entry.shift_type = shift_type
        entry.raw_code = raw_code
        entry.source_file = "manual-admin"
    else:
        old_value = ""
        new_value = f"{shift_type}|{raw_code}"
        entry = ShiftEntry(employee_id=employee.id, work_date=work_date, shift_type=shift_type, raw_code=raw_code, source_file="manual-admin")
        db.add(entry)
    db.add(ManualEditHistory(
        employee_id=employee.id,
        work_date=work_date,
        field_name="shift",
        old_value=old_value,
        new_value=new_value,
        changed_by=_admin,
    ))
    db.commit()
    return {"status": "updated", "work_date": work_date, "shift_type": shift_type, "raw_code": raw_code}


@app.get("/api/v1/admin/employees/{employee_id}/edits")
def admin_employee_edits(
    employee_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    _admin: str = Depends(current_admin),
    db: Session = Depends(get_db),
):
    employee = get_admin_employee(db, employee_id)
    rows = db.scalars(
        select(ManualEditHistory)
        .where(ManualEditHistory.employee_id == employee.id)
        .order_by(ManualEditHistory.changed_at.desc(), ManualEditHistory.id.desc())
        .limit(limit)
    ).all()
    return {"edits": [
        {
            "id": row.id,
            "work_date": row.work_date.isoformat() if row.work_date else None,
            "field_name": row.field_name,
            "old_value": row.old_value,
            "new_value": row.new_value,
            "changed_by": row.changed_by,
            "changed_at": row.changed_at.isoformat(),
        } for row in rows
    ]}
