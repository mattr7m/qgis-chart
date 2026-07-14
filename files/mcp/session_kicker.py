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

import glob
import os
import socket
import time
import urllib.request

JUPYTER_URL = os.environ.get("JUPYTER_URL", "http://127.0.0.1:8888")
TOKEN = os.environ.get("JUPYTER_TOKEN", "")
SOCKET_PORT = int(os.environ.get("QGIS_MCP_PORT", "9876"))
INTERVAL = int(os.environ.get("KICK_INTERVAL", "60"))
# home PVC, mounted read-only for diagnostics; empty disables them
HOME_DIR = os.environ.get("NB_HOME", "")
# emit session diagnostics every Nth failed kick
DIAG_EVERY = int(os.environ.get("DIAG_EVERY", "5"))


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


def diagnostics():
    """The Xfce/QGIS session logs to files on the home PVC that kubectl logs
    cannot reach; surface the relevant tails here (read-only mount)."""
    checks = {
        "autostart entry": f"{HOME_DIR}/.config/autostart/qgis-mcp.desktop",
        "plugin __init__": f"{HOME_DIR}/.local/share/QGIS/QGIS3/profiles/default"
        "/python/plugins/qgis_mcp_plugin/__init__.py",
        "profile ini": f"{HOME_DIR}/.local/share/QGIS/QGIS3/profiles/default"
        "/QGIS/QGIS3.ini",
    }
    for label, path in checks.items():
        print(f"[diag] {label}: {'present' if os.path.exists(path) else 'MISSING'} ({path})", flush=True)
    vnc_logs = sorted(glob.glob(f"{HOME_DIR}/.vnc/*.log"), key=os.path.getmtime)
    if not vnc_logs:
        print("[diag] no ~/.vnc/*.log yet — VNC session has not started", flush=True)
        return
    newest = vnc_logs[-1]
    try:
        with open(newest, errors="replace") as fh:
            tail = fh.readlines()[-40:]
        print(f"[diag] tail of {newest}:", flush=True)
        for line in tail:
            print("[vnc] " + line.rstrip()[:300], flush=True)
    except OSError as exc:
        print(f"[diag] cannot read {newest}: {exc}", flush=True)


was_up = None
downs = 0
while True:
    try:
        up = socket_up()
        if up and up != was_up:
            print(f"plugin socket 127.0.0.1:{SOCKET_PORT} is up", flush=True)
        if not up:
            status = kick()
            downs += 1
            print(
                f"plugin socket down; kicked {JUPYTER_URL}/desktop/ -> HTTP {status}",
                flush=True,
            )
            if HOME_DIR and downs % DIAG_EVERY == 0:
                diagnostics()
        else:
            downs = 0
        was_up = up
    except Exception as exc:  # keep kicking through transient jupyter errors
        print(f"kick failed: {exc}", flush=True)
    time.sleep(INTERVAL)
