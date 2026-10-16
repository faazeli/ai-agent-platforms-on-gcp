"""Run the MCP server over Streamable HTTP:  python -m mcp_finops
The MCP endpoint is http://HOST:PORT/mcp
"""

import httpx

from .cost_api_client import CostApiClient
from .server import build_server
from .settings import Settings


def main() -> None:
    settings = Settings()
    http = httpx.AsyncClient(base_url=settings.cost_api_url, timeout=settings.cost_api_timeout_seconds)
    server = build_server(CostApiClient(http, settings.problem_base_url))
    server.run(transport="http", host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
