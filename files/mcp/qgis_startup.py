# Installed as <profile>/python/startup.py by the qgis-chart mcp init
# container. Three jobs for a QGIS that is driven headlessly over MCP:
#
# 1. Silent bad-layer handling. The app's HandleBadLayers dialog opens
#    unconditionally when any layer in a loading project fails to resolve;
#    headless, nobody clicks it, so the event loop and the qgis-mcp plugin
#    socket wedge forever (qgis-agent#42). We swap in the silent base-class
#    handler — and RE-ASSERT it on a deferred timer, because QgisApp installs
#    its own GUI handler during startup, after this file runs.
# 2. A modal watchdog. Any modal dialog in this session is illegitimate by
#    definition (there is no human to answer it) and wedges the socket. Every
#    few seconds, detect an active modal, log its title/class to
#    ~/.qgis-modal-watchdog.log (the kicker tails it — the log IS the
#    diagnosis of what popped), and dismiss it. Qt timers keep firing inside
#    a modal's nested event loop, so the watchdog works mid-wedge.
# 3. Fallback for the QgsSettings autostart seed: once plugins are loaded,
#    start the qgis-mcp socket server if it is not already running.

import os
import time

_bad_layer_handler = None  # module-level ref: setBadLayerHandler does not
# take ownership, and a garbage-collected handler crashes QGIS


def _assert_bad_layer_handler():
    global _bad_layer_handler
    try:
        from qgis.core import QgsProject, QgsProjectBadLayerHandler

        if _bad_layer_handler is None:
            _bad_layer_handler = QgsProjectBadLayerHandler()
        QgsProject.instance().setBadLayerHandler(_bad_layer_handler)
    except Exception:  # never take QGIS down from a startup hook
        pass


def _modal_watchdog():
    try:
        from qgis.PyQt.QtWidgets import QApplication, QDialog

        w = QApplication.activeModalWidget()
        if w is None or not isinstance(w, QDialog):
            return
        title = w.windowTitle() or "?"
        cls = type(w).__name__
        try:
            with open(os.path.expanduser("~/.qgis-modal-watchdog.log"), "a") as fh:
                fh.write(
                    time.strftime("%Y-%m-%dT%H:%M:%S%z")
                    + f" dismissed modal: title={title!r} class={cls}\n"
                )
        except OSError:
            pass
        w.reject()
    except Exception:  # the watchdog must never be the thing that crashes QGIS
        pass


def _ensure_qgis_mcp_server():
    try:
        from qgis import utils

        plugin = utils.plugins.get("qgis_mcp_plugin")
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
    # the watchdog runs for the life of the session
    _watchdog_timer = QTimer()
    _watchdog_timer.setInterval(7000)
    _watchdog_timer.timeout.connect(_modal_watchdog)
    _watchdog_timer.start()
except Exception:
    pass
