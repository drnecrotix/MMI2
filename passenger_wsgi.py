"""Phusion Passenger/cPanel WSGI entrypoint.

The actual ASGI-to-WSGI adapter lives in ``run.py`` so the same runtime is
used by both PlanetHoster N0C and cPanel/Passenger deployments.
"""

from run import app as application
