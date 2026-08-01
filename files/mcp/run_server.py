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

from qgis_mcp.server import mcp

host = os.environ.get("MCP_LISTEN_HOST", "0.0.0.0")
port = int(os.environ.get("MCP_LISTEN_PORT", "8000"))

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
