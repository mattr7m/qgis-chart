"""Run the qgis-mcp MCP server on an externally reachable address.

Handles both mcp SDK generations, since the sidecar resolves qgis-mcp (and its
mcp dependency, constrained only to <3 upstream) fresh at container start:

- mcp 1.x (FastMCP): host/port/transport_security live in pydantic Settings,
  but FASTMCP_* env vars are ignored (init kwargs outrank env) and a
  localhost-only DNS-rebinding allowlist auto-enables — so mutate the settings
  before run(). Verified on 1.26.0/1.28.1.
- mcp >= 2.0 (MCPServer aliased to FastMCP upstream): Settings no longer has
  host/port; run(transport, **kwargs) forwards them to
  run_streamable_http_async(host, port, ..., transport_security). Verified on
  2.0.0.

transport_security=None disables the DNS-rebinding Host allowlist in both
generations — required because clients address this server by its Kubernetes
Service DNS name; the endpoint is ClusterIP-only, never on an Ingress.
"""

import os

import qgis_mcp.server as _server
from qgis_mcp.server import mcp

host = os.environ.get("MCP_LISTEN_HOST", "0.0.0.0")
port = int(os.environ.get("MCP_LISTEN_PORT", "8000"))

# Carried behavioral override: disable the destructive-op elicitation gate.
#
# qgis-mcp >= 0.9 wraps execute_code / remove_layer / delete_features /
# delete_field / remove_layout / execute_connection_sql in an MCP elicitation
# confirm ("Execute arbitrary PyQGIS code?"). Its documented fail-open for
# clients without elicitation support does not fire in practice (the mcp 2.0
# SDK sends the elicit request regardless and waits), so any client that does
# not answer elicitation HANGS FOREVER on those tools — observed as the
# operator-fleet write-path outage (qgis-agent#42).
#
# In this deployment the confirmation adds nothing: the endpoint is
# ClusterIP-only and the "user" being asked is the calling agent itself. This
# restores pre-0.9 semantics — the tools stay marked destructiveHint, so
# clients that want call-time gating still can. Guarded so older refs without
# the gate keep working; MCP_ELICIT_CONFIRM=1 re-enables upstream behavior.
if hasattr(_server, "_confirm_destructive") and os.environ.get(
    "MCP_ELICIT_CONFIRM", "0"
) != "1":

    async def _confirm_always(ctx, message):
        return True

    _server._confirm_destructive = _confirm_always

if "host" in getattr(type(mcp.settings), "model_fields", {}):  # mcp 1.x
    mcp.settings.host = host
    mcp.settings.port = port
    mcp.settings.transport_security = None
    mcp.run(transport="streamable-http")
else:  # mcp >= 2.0
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        transport_security=None,
    )
