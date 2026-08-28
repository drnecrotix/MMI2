from calendar import monthrange
from datetime import date

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine, get_db
from app.models import Employee, ShiftEntry
from app.schemas import LoginRequest, MonthlyScheduleOut, ShiftOut, TokenResponse
from app.security import create_access_token, decode_access_token
from app.services.excel_import import import_schedule_xlsx
from app.services.excel_preview import preview_schedule_xlsx

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version="0.4.0",
    description="MMI2 monthly work schedule import and employee API",
)
templates = Jinja2Templates(directory="app/templates")
bearer = HTTPBearer(auto_error=False)


def current_employee(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Employee:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Липсва access token.")
    work_number = decode_access_token(credentials.credentials)
    if not work_number:
        raise HTTPException(status_code=401, detail="Невалиден или изтекъл token.")
    employee = db.scalar(select(Employee).where(Employee.work_number == work_number))
    if not employee:
        raise HTTPException(status_code=401, detail="Служителят не е намерен.")
    return employee


def require_admin_key(x_admin_key: str | None) -> None:
    if x_admin_key != settings.admin_import_key:
        raise HTTPException(status_code=403, detail="Невалиден admin key.")


@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"app_name": settings.app_name})


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html", context={"app_name": settings.app_name})


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


@app.get("/api/v1/me")
def me(employee: Employee = Depends(current_employee)):
    return {
        "work_number": employee.work_number,
        "full_name": employee.full_name,
        "team": employee.team,
    }


@app.get("/api/v1/me/schedule/{year}/{month}", response_model=MonthlyScheduleOut)
def my_schedule(
    year: int,
    month: int,
    employee: Employee = Depends(current_employee),
    db: Session = Depends(get_db),
):
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Невалиден месец.")
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    entries = db.scalars(
        select(ShiftEntry)
        .where(
            ShiftEntry.employee_id == employee.id,
            ShiftEntry.work_date >= first,
            ShiftEntry.work_date <= last,
        )
        .order_by(ShiftEntry.work_date)
    ).all()
    return MonthlyScheduleOut(
        employee_name=employee.full_name,
        work_number=employee.work_number,
        team=employee.team,
        year=year,
        month=month,
        shifts=[ShiftOut(work_date=e.work_date, shift_type=e.shift_type, raw_code=e.raw_code) for e in entries],
    )


@app.post("/api/v1/admin/preview")
async def preview_schedule(
    year: int = Form(...),
    month: int = Form(...),
    file: UploadFile = File(...),
    x_admin_key: str | None = Header(default=None),
):
    require_admin_key(x_admin_key)
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Невалиден месец.")

    content = await file.read()
    try:
        result = preview_schedule_xlsx(content, file.filename or "schedule.xlsx", year, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "status": "preview",
        "filename": file.filename,
        "year": year,
        "month": month,
        "employees_count": len(result.employees),
        "schedule_blocks": result.schedule_blocks,
        "duplicate_employee_rows": result.duplicate_employee_rows,
        "conflicting_days": result.conflicting_days,
        "unknown_codes": result.unknown_codes,
        "totals": result.totals,
        "employees": result.employees,
    }


@app.post("/api/v1/admin/import")
async def import_schedule(
    year: int = Form(...),
    month: int = Form(...),
    file: UploadFile = File(...),
    x_admin_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    require_admin_key(x_admin_key)
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Невалиден месец.")
    content = await file.read()
    try:
        result = import_schedule_xlsx(db, content, file.filename or "schedule.xlsx", year, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "imported",
        "employees": result.employees,
        "shifts": result.shifts,
        "skipped_rows": result.skipped_rows,
        "schedule_blocks": result.schedule_blocks,
        "duplicate_employee_rows": result.duplicate_employee_rows,
        "conflicting_days": result.conflicting_days,
        "year": year,
        "month": month,
    }
