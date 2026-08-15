"""
MCP-based tool — the search MCP server is spawned as a subprocess per call
(Option A, stdio transport; see decisions.md for the Option B graduation plan).

Deliberately NOT wired into process_ticker's automatic flow — calling this on
every ticker would burn the limited Tavily budget (see decisions.md) for no
real benefit until Phase 4 has an LLM that actually decides when a search is
worth making. Call this manually/directly for now.
"""
import pathlib
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

_SERVER_DIR = pathlib.Path(__file__).parent.parent / "mcp_server"
_SERVER_PARAMS = StdioServerParameters(
    command="uv", args=["run", "python", "search_server.py"], cwd=_SERVER_DIR
)


async def search_via_mcp(query: str, max_results: int = 5) -> list[dict]:
    async with stdio_client(_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search", {"query": query, "max_results": max_results}
            )
            return [block.text for block in result.content if hasattr(block, "text")]
