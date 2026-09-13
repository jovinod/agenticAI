import json
import os

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from prompt_shields import MAX_TOTAL_CHARACTERS, scan_documents

# Local HTTP is appropriate for the loopback default. The deployed
# Container Apps URL must be the final https:// address directly --
# internal ingress redirects HTTP to HTTPS, and following that
# redirect turns the client's POST into a GET, discarding the JSON-RPC
# initialization body. A timeout does not fix that; the URL must
# already be https://.
MCP_SEARCH_URL = os.environ.get("MCP_SEARCH_URL", "http://127.0.0.1:8811/mcp")

REMOVED_MESSAGE = "[Result removed: flagged as a potential prompt injection attempt]"


def _looks_like_json(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith("{") or stripped.startswith("[")


async def list_search_tools() -> list:
    """Discovery: retrieve registered tool schemas. Spends no provider budget."""
    async with streamable_http_client(MCP_SEARCH_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.list_tools()
            return response.tools


async def search_via_mcp(query: str, max_results: int = 5) -> list[str]:
    """The client knows only the service URL and MCP protocol -- it no
    longer creates a subprocess or reads the Tavily secret itself
    (Chapter 18 moved both to the standalone mcp-search service). Scans
    in the same place untrusted open-web text enters the process,
    immediately after results return and before any agent sees them."""
    async with streamable_http_client(MCP_SEARCH_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search", {"query": query, "max_results": max_results}
            )

    texts = [
        json.loads(item.text)["content"] if _looks_like_json(item.text) else item.text
        for item in result.content
        if hasattr(item, "text")
    ]

    # Real 10,000-character total request limit -- truncate before
    # scanning, not folded into the safety verdict.
    trimmed: list[str] = []
    budget = MAX_TOTAL_CHARACTERS
    for text in texts:
        if len(text) > budget:
            text = text[:budget]
        trimmed.append(text)
        budget -= len(text)
        if budget <= 0:
            break

    try:
        is_safe = await scan_documents(trimmed)
    except Exception:
        return trimmed

    return [text if safe else REMOVED_MESSAGE for text, safe in zip(trimmed, is_safe)]
