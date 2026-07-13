# Installed as <profile>/python/startup.py by the qgis-chart mcp init
# container. Fallback for the QgsSettings autostart seed: once plugins are
# loaded, start the qgis-mcp socket server if it is not already running.


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
