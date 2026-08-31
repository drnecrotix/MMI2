from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from install.hosting import detect_hosting_runtime
from install.service import (
    InstallRequest,
    InstallerError,
    DatabaseSetup,
    complete_installation,
    get_installation_state,
    system_checks,
    test_database_connection,
)


router = APIRouter(prefix="/install", tags=["installer"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _template_context(state):
    hosting = detect_hosting_runtime()
    return {
        "state": state,
        "checks": system_checks(),
        "hosting": hosting,
        "restart_only": state.installed and state.restart_required,
    }


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def installer_page(request: Request):
    state = get_installation_state()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_template_context(state),
    )


@router.get("/restart", response_class=HTMLResponse)
def installer_restart_page(request: Request):
    state = get_installation_state()
    context = _template_context(state)
    context["restart_only"] = True
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=context,
    )


@router.get("/api/status")
def installer_status():
    state = get_installation_state()
    return {
        "installed": state.installed,
        "restart_required": state.restart_required,
        "hosting": detect_hosting_runtime().as_dict(),
        "checks": system_checks(),
    }


@router.post("/api/database-check")
def installer_database_check(payload: DatabaseSetup):
    state = get_installation_state()
    if state.installed:
        raise HTTPException(status_code=409, detail="Installer-ът вече е заключен.")
    try:
        return test_database_connection(payload)
    except InstallerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/complete")
def installer_complete(payload: InstallRequest):
    try:
        result = complete_installation(payload)
        hosting = detect_hosting_runtime()
        result["hosting"] = hosting.as_dict()
        result["message"] = f"Инсталацията е завършена. {hosting.restart_instruction}"
        return result
    except InstallerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
