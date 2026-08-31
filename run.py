"""N0C/CloudLinux Python startup file.

N0C's Python manager uses ``run.py`` as the startup file and ``app`` as the
entry point. Passenger is WSGI-based, while MMI2 is a FastAPI ASGI app, so
``a2wsgi.ASGIMiddleware`` bridges the protocols.
"""

from pathlib import Path
import os
import sys

from a2wsgi import ASGIMiddleware


PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ``setdefault`` is intentional: cPanel's passenger_wsgi.py sets its own
# marker before importing this shared adapter.
os.environ.setdefault("MMI2_HOSTING_PLATFORM", "n0c")

from app.main import app as asgi_app  # noqa: E402


app = ASGIMiddleware(asgi_app, wait_time=5.0)
# Some Passenger/cPanel configurations look specifically for ``application``.
application = app
