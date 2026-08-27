"""
A minimal MCP server exposing one tool: web search via Tavily.

Adapted from buynobuy's skills/utils/search.py::_tavily() — simplified to just
the primary backend for this first pass (no DuckDuckGo/Playwright fallback yet).

Run standalone for testing: TAVILY_API_KEY=... uv run python mcp_server/search_server.py
(the caller normally supplies this via env=, see tools/web_search.py)
In production this gets spawned as a subprocess by the worker (stdio transport) —
see decisions.md ("MCP search server — local shape now, real shape later").
"""
import os
from mcp.server.mcpserver import MCPServer
from tavily import TavilyClient

# Phase 8, Stage D -- the caller (tools/web_search.py) resolves the real key
# once, whether from Key Vault (Azure) or .env.local (local dev), and passes
# it down explicitly via the subprocess's env= -- this process just reads it.
# Not resolved here: a fresh subprocess is spawned per search_web call, so a
# Key Vault round-trip in THIS process happened on every single call, adding
# enough latency to cause a real Service Bus message-lock timeout in
# production on a job with several searches.
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

mcp = MCPServer("search-server")


@mcp.tool()
def search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return a list of {title, content, url} results."""
    if not TAVILY_API_KEY:
        raise EnvironmentError("TAVILY_API_KEY not set")

    response = TavilyClient(api_key=TAVILY_API_KEY).search(
        query=query, max_results=max_results, include_answer=False
    )
    return [
        {"title": r.get("title", ""), "content": r.get("content", ""), "url": r.get("url", "")}
        for r in response.get("results", [])
    ]


if __name__ == "__main__":
    mcp.run()
