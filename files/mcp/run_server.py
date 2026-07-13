"""Run the qgis-mcp FastMCP server on an externally reachable address.

The mcp SDK (verified on 1.26.0) ignores FASTMCP_HOST/FASTMCP_PORT here:
FastMCP.__init__ passes explicit defaults into its pydantic Settings, and init
kwargs outrank environment variables. It also auto-enables DNS-rebinding
protection with a localhost-only Host allowlist, which would reject requests
addressed to the Kubernetes Service DNS name. So mutate the settings before
run(): bind the configured address and drop the transport security block —
the endpoint is a ClusterIP Service, never exposed on an Ingress.

QGIS_MCP_HOST/QGIS_MCP_PORT (read by qgis_mcp.server itself) still point at
the plugin socket the server CONNECTS to; MCP_LISTEN_* is where it LISTENS.
"""

import os

from qgis_mcp.server import mcp

mcp.settings.host = os.environ.get("MCP_LISTEN_HOST", "0.0.0.0")
mcp.settings.port = int(os.environ.get("MCP_LISTEN_PORT", "8000"))
mcp.settings.transport_security = None
mcp.run(transport="streamable-http")
