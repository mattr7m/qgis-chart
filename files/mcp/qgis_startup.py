# Installed as <profile>/python/startup.py by the qgis-chart mcp init
# container. Hardens a QGIS that is driven headlessly over MCP:
#
# 1. Silent bad-layer handling — the app's HandleBadLayers dialog is modal and
#    unconditional; headless it wedges the event loop + plugin socket forever
#    (qgis-agent#42). Swapped at start AND re-asserted after QgisApp installs
#    its own GUI handler.
# 2. Modal watchdog — any modal in this session is illegitimate (no human to
#    answer it). Detect, log title/class, dismiss. Qt timers fire inside
#    nested modal event loops, so this works mid-wedge.
# 3. qgis-mcp socket autostart fallback.
#
# CRITICAL — lifetime anchoring: this file's exec namespace is DISCARDED after
# the deferred callables release it, so module-level refs here get garbage
# collected. A GC'd QTimer never fires, and a GC'd bad-layer handler leaves
# QGIS holding a DANGLING pointer (observed as the silent load_project hang —
# the first fix's own bug). Everything stateful is therefore anchored on
# qgis.utils, which persists in sys.modules for the process lifetime.

import os
import time

import qgis.utils

_state = {}
qgis.utils._mcp_headless_hardening = _state  # persistent anchor


def _log(line):
    try:
        with open(os.path.expanduser("~/.qgis-modal-watchdog.log"), "a") as fh:
            fh.write(time.strftime("%Y-%m-%dT%H:%M:%S%z") + " " + line + "\n")
    except OSError:
        pass


def _assert_bad_layer_handler():
    try:
        from qgis.core import QgsProject, QgsProjectBadLayerHandler

        if "bad_layer_handler" not in _state:
            _state["bad_layer_handler"] = QgsProjectBadLayerHandler()
        QgsProject.instance().setBadLayerHandler(_state["bad_layer_handler"])
        _log("silent bad-layer handler asserted")
    except Exception as exc:  # never take QGIS down from a startup hook
        _log(f"bad-layer handler assert failed: {exc!r}")


def _modal_watchdog():
    try:
        from qgis.PyQt.QtWidgets import QApplication, QDialog

        w = QApplication.activeModalWidget()
        if w is None or not isinstance(w, QDialog):
            return
        _log(f"dismissed modal: title={w.windowTitle()!r} class={type(w).__name__}")
        w.reject()
    except Exception:  # the watchdog must never be the thing that crashes QGIS
        pass


def _ensure_qgis_mcp_server():
    try:
        plugin = qgis.utils.plugins.get("qgis_mcp_plugin")
        if plugin is None or getattr(plugin, "server", None) is not None:
            return
        action = getattr(plugin, "action", None)
        if action is not None:
            action.setChecked(True)
        plugin.toggle_server(True)
    except Exception:  # never take QGIS down from a startup hook
        pass


_assert_bad_layer_handler()

try:
    from qgis.PyQt.QtCore import QTimer

    # re-assert after QgisApp has installed its own GUI bad-layer handler
    QTimer.singleShot(20000, _assert_bad_layer_handler)
    # startup.py runs before plugins load; defer until QGIS is up
    QTimer.singleShot(30000, _ensure_qgis_mcp_server)
    # session-lifetime watchdog, anchored so it cannot be collected
    timer = QTimer()
    timer.setInterval(7000)
    timer.timeout.connect(_modal_watchdog)
    timer.start()
    _state["watchdog_timer"] = timer
    _state["fns"] = (_assert_bad_layer_handler, _modal_watchdog, _ensure_qgis_mcp_server)
    _log("hardening armed (watchdog 7s, handler re-assert 20s)")
except Exception as exc:
    _log(f"hardening arm failed: {exc!r}")
