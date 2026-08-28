"""
MCP-based tool — the search MCP server is spawned as a subprocess per call
(Option A, stdio transport; see decisions.md for the Option B graduation plan).

Deliberately NOT wired into process_ticker's automatic flow — calling this on
every ticker would burn the limited Tavily budget (see decisions.md) for no
real benefit until Phase 4 has an LLM that actually decides when a search is
worth making. Call this manually/directly for now.
"""
import os
import pathlib
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from tools.prompt_shields import scan_documents

_SERVER_DIR = pathlib.Path(__file__).parent.parent / "mcp_server"

# Phase 8, Stage D -- resolved ONCE here, not inside the spawned subprocess.
# Two real reasons, found live: (1) the MCP stdio client only passes a narrow
# safe-list of env vars to the child by default (HOME/PATH/etc, not arbitrary
# ones like KEY_VAULT_URL) -- fetching inside the subprocess was relying on
# fragile inheritance, not a guarantee. (2) a subprocess is spawned fresh per
# search_web call, so a Key Vault round-trip *inside* the subprocess happened
# on every single call -- the added latency pushed a real multi-search job
# (NVDA, 4 searches) past the Service Bus message's lock duration, causing a
# real MessageLockLostError in production. Resolving once here and passing
# the plain value down via `env=` avoids both problems at once.
KEY_VAULT_URL = os.environ.get("KEY_VAULT_URL")
if KEY_VAULT_URL:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    _kv_client = SecretClient(vault_url=KEY_VAULT_URL, credential=DefaultAzureCredential())
    _TAVILY_API_KEY = _kv_client.get_secret("tavily-api-key").value
else:
    _TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

_SERVER_PARAMS = StdioServerParameters(
    command="uv", args=["run", "python", "search_server.py"], cwd=_SERVER_DIR,
    env={"TAVILY_API_KEY": _TAVILY_API_KEY},
)


async def search_via_mcp(query: str, max_results: int = 5) -> list[dict]:
    async with stdio_client(_SERVER_PARAMS) as (read, write):
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
