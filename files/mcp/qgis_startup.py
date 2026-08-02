# Installed as <profile>/python/startup.py by the qgis-chart mcp init
# container. Two jobs:
# 1. Replace the GUI bad-layer handler with the silent base-class handler —
#    this QGIS is driven headlessly over MCP, and the "Handle Unavailable
#    Layers" dialog (shown UNCONDITIONALLY by the app handler when any layer
#    in a loading project fails to resolve, e.g. a memory scratch layer)
#    blocks the event loop forever with nobody to click it, wedging the
#    plugin socket (qgis-agent#42; reproduced twice). Bad layers are kept
#    silently instead — the desktop analogue of QGIS_SERVER_IGNORE_BAD_LAYERS.
# 2. Fallback for the QgsSettings autostart seed: once plugins are loaded,
#    start the qgis-mcp socket server if it is not already running.

try:
    from qgis.core import QgsProject, QgsProjectBadLayerHandler

    # keep a module-level reference: setBadLayerHandler does not take
    # ownership, and a garbage-collected handler crashes QGIS
    _bad_layer_handler = QgsProjectBadLayerHandler()
    QgsProject.instance().setBadLayerHandler(_bad_layer_handler)
except Exception:  # never take QGIS down from a startup hook
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


try:
    from qgis.PyQt.QtCore import QTimer

    # startup.py runs before plugins load; defer until QGIS is up
    QTimer.singleShot(30000, _ensure_qgis_mcp_server)
except Exception:
    pass
