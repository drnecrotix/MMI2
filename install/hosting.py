from __future__ import annotations

from dataclasses import asdict, dataclass
import os


@dataclass(frozen=True)
class HostingRuntime:
    platform: str
    label: str
    restart_title: str
    restart_instruction: str
    entrypoint: str

    def as_dict(self) -> dict:
        return asdict(self)


def detect_hosting_runtime() -> HostingRuntime:
    marker = os.environ.get("MMI2_HOSTING_PLATFORM", "").strip().lower()

    if marker == "n0c":
        return HostingRuntime(
            platform="n0c",
            label="PlanetHoster N0C",
            restart_title="Рестартирай Python приложението в N0C",
            restart_instruction=(
                "Отвори N0C/MG Panel → Languages → Python, избери MMI2 приложението "
                "и използвай Restart/Reload. След това отвори сайта отново."
            ),
            entrypoint="run.py → app",
        )

    if marker == "cpanel":
        return HostingRuntime(
            platform="cpanel",
            label="cPanel / CloudLinux Passenger",
            restart_title="Рестартирай Python приложението в cPanel",
            restart_instruction=(
                "Отвори cPanel → Setup Python App / Python Selector, избери MMI2 "
                "и натисни Restart. След това отвори сайта отново."
            ),
            entrypoint="passenger_wsgi.py → application",
        )

    if marker == "passenger" or any(key.startswith("PASSENGER_") for key in os.environ):
        return HostingRuntime(
            platform="passenger",
            label="Phusion Passenger",
            restart_title="Рестартирай Passenger приложението",
            restart_instruction=(
                "Използвай Restart/Reload в hosting control panel или стандартния "
                "Passenger restart механизъм за приложението, след което отвори сайта отново."
            ),
            entrypoint="Passenger WSGI",
        )

    return HostingRuntime(
        platform="generic",
        label="Generic ASGI / Docker / VPS",
        restart_title="Рестартирай приложението",
        restart_instruction=(
            "Рестартирай Uvicorn/systemd service-а или Docker container-а, който стартира MMI2, "
            "след което отвори сайта отново."
        ),
        entrypoint="app.main:app",
    )
