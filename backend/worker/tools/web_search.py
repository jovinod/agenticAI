"""
MCP-based tool -- Phase 11 graduates the search server from Option A (stdio,
spawned as a subprocess by this worker) to Option B: its own Container App
(mcp_server/), reached over HTTP, independently autoscaled. See decisions.md
for why Option A was the deliberate starting shape.

The subprocess-lifecycle problems Option A had (a Key Vault round-trip on
every single call, since a fresh subprocess started fresh each time -- see
Chapter 8's MessageLockLostError incident) are gone by construction now: the
search server resolves its own Tavily key once, in its own long-running
process, using its own Managed Identity. This file no longer touches Key
Vault at all -- it just knows where to reach the service.

Deliberately NOT wired into process_ticker's automatic flow — calling this on
every ticker would burn the limited Tavily budget (see decisions.md) for no
real benefit until Phase 4 has an LLM that actually decides when a search is
worth making. Call this manually/directly for now.
"""
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from tools.prompt_shields import scan_documents

# Local dev default matches mcp_server/search_server.py's own local port. In
# Azure, this points at the new Container App's internal-only FQDN -- no
# public ingress, since nothing outside this system ever needs to reach it.
MCP_SEARCH_URL = os.environ.get("MCP_SEARCH_URL", "http://127.0.0.1:8811/mcp")


async def search_via_mcp(query: str, max_results: int = 5) -> list[dict]:
    async with streamable_http_client(MCP_SEARCH_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search", {"query": query, "max_results": max_results}
            )
            texts = [block.text for block in result.content if hasattr(block, "text")]

    # Phase 9 (Guardrails) -- the one place untrusted third-party content
    # (whatever Tavily found on the open web) enters this project. Azure
    # OpenAI's own built-in jailbreak classifier only scans the user's own
    # message, confirmed live NOT to scan tool-role content -- this is the
    # dedicated check for content that could contain hidden instructions
    # aimed at hijacking the agent reading it, not at us directly.
    is_safe = await scan_documents(texts)
    return [
        text if safe else "[Result removed: flagged as a potential prompt injection attempt]"
        for text, safe in zip(texts, is_safe)
    ]
