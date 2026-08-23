"""Entrypoint for running one of the four chat MCP servers (chat_implementation_plan.md §5).

Local dev / MCP Inspector (stdio, the default):
    python run_mcp_server.py catalog
    npx @modelcontextprotocol/inspector python run_mcp_server.py catalog

Railway (each of the 4 servers is its own service/Start Command, streamable-http):
    MCP_TRANSPORT=streamable-http python run_mcp_server.py catalog
Railway sets $PORT itself; MCP_HOST/MCP_PORT env vars are only a fallback for running multiple
servers side by side on one machine (e.g. local streamable-http testing without Railway).
"""

import argparse
import os

_SERVERS = {"catalog", "weather", "support", "analytics"}
# Distinct local ports per server so all four can run streamable-http side by side without Railway.
_DEFAULT_LOCAL_PORTS = {"catalog": 8101, "weather": 8102, "support": 8103, "analytics": 8104}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("server", choices=sorted(_SERVERS))
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default=None)
    args = parser.parse_args()

    transport = args.transport or os.environ.get("MCP_TRANSPORT", "stdio")

    module = __import__(f"app.mcp.{args.server}", fromlist=["mcp"])
    mcp = module.mcp

    if transport == "streamable-http":
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("PORT", os.environ.get("MCP_PORT", _DEFAULT_LOCAL_PORTS[args.server])))

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
