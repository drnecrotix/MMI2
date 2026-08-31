"""Phusion Passenger/cPanel WSGI entrypoint for the FastAPI application.

Passenger serves WSGI applications. MMI2 is ASGI, so a2wsgi bridges the
FastAPI app to the WSGI callable Passenger expects as ``application``.
"""

from pathlib import Path
import os
import sys

from a2wsgi import ASGIMiddleware


PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app  # noqa: E402


application = ASGIMiddleware(app, wait_time=5.0)
