"""Phusion Passenger/cPanel WSGI entrypoint.

The actual ASGI-to-WSGI adapter lives in ``run.py`` so the same runtime is
used by both PlanetHoster N0C and cPanel/Passenger deployments.
"""

import os

# Set this before importing run.py; run.py uses setdefault so this explicit
# cPanel marker wins while both entrypoints still share one adapter instance.
os.environ["MMI2_HOSTING_PLATFORM"] = "cpanel"

from run import app as application  # noqa: E402
