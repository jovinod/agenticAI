"""
A minimal MCP server exposing one tool: web search via Tavily.

Adapted from buynobuy's skills/utils/search.py::_tavily() — simplified to just
the primary backend for this first pass (no DuckDuckGo/Playwright fallback yet).

Run standalone for testing: uv run python mcp_server/search_server.py
In production this gets spawned as a subprocess by the worker (stdio transport) —
see decisions.md ("MCP search server — local shape now, real shape later").
"""
import os
import pathlib
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from tavily import TavilyClient

# File-relative, not cwd-relative — the client spawns this as a subprocess and its
# working directory isn't guaranteed to be backend/worker/ where .env.local lives.
load_dotenv(pathlib.Path(__file__).parent.parent / ".env.local")

mcp = MCPServer("search-server")


@mcp.tool()
def search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return a list of {title, content, url} results."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise EnvironmentError("TAVILY_API_KEY not set")

    response = TavilyClient(api_key=api_key).search(
        query=query, max_results=max_results, include_answer=False
    )
    return [
        {"title": r.get("title", ""), "content": r.get("content", ""), "url": r.get("url", "")}
        for r in response.get("results", [])
    ]


if __name__ == "__main__":
    mcp.run()
