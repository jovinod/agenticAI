"""
Throwaway isolation test for search_server.py — same "prove it standalone before
wiring it in" discipline used for arq, Service Bus, and Postgres earlier.

Phase 11 -- updated for the HTTP transport graduation. Run the server first
in another shell (TAVILY_API_KEY=... uv run python search_server.py), then
run this against it.

Deliberately makes exactly ONE real Tavily call (the Tavily budget is limited —
see decisions.md). list_tools() is a protocol-level operation, no search cost.
"""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SERVER_URL = "http://127.0.0.1:8811/mcp"


async def main():
    async with streamable_http_client(SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()  # no Tavily call — protocol-level only
            print("Tools discovered:", [t.name for t in tools.tools])

            result = await session.call_tool(  # the one real Tavily call
                "search", {"query": "Apple Inc Q4 2026 earnings", "max_results": 3}
            )
            print("Search result:")
            for block in result.content:
                print(block.text if hasattr(block, "text") else block)


asyncio.run(main())
