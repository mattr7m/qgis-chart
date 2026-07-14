"""Keep the QGIS desktop session — and thus the qgis-mcp plugin socket — alive.

The b-data image starts JupyterLab only; TurboVNC + Xfce launch lazily when
jupyter-server-proxy's /desktop route is first requested, and QGIS starts with
the session via the Xfce autostart entry the init container installs. Headless,
nothing makes that first request — this kicker does: while the plugin socket is
down, it keeps requesting the desktop endpoint (which also relaunches the
session if it ever dies).

Runs in its own container so JUPYTER_TOKEN stays out of the environment of the
MCP-exposed server process. Stdlib only.
"""

import os
import socket
import time
import urllib.request

JUPYTER_URL = os.environ.get("JUPYTER_URL", "http://127.0.0.1:8888")
TOKEN = os.environ.get("JUPYTER_TOKEN", "")
SOCKET_PORT = int(os.environ.get("QGIS_MCP_PORT", "9876"))
INTERVAL = int(os.environ.get("KICK_INTERVAL", "60"))


def socket_up():
    try:
        with socket.create_connection(("127.0.0.1", SOCKET_PORT), timeout=3):
            return True
    except OSError:
        return False


def kick():
    req = urllib.request.Request(
        f"{JUPYTER_URL}/desktop/",
        headers={"Authorization": f"token {TOKEN}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status


was_up = None
while True:
    try:
        up = socket_up()
        if up and up != was_up:
            print(f"plugin socket 127.0.0.1:{SOCKET_PORT} is up", flush=True)
        if not up:
            status = kick()
            print(
                f"plugin socket down; kicked {JUPYTER_URL}/desktop/ -> HTTP {status}",
                flush=True,
            )
        was_up = up
    except Exception as exc:  # keep kicking through transient jupyter errors
        print(f"kick failed: {exc}", flush=True)
    time.sleep(INTERVAL)
