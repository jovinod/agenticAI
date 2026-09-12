import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_DIR = str(Path(__file__).parent)


def _server_params() -> StdioServerParameters:
    # The MCP SDK spawns the server with a minimal environment, not a copy
    # of the caller's -- only what's explicitly passed here reaches
    # search_server.py. Built fresh per call so a changed/unset key is
    # always honored, not captured once at import time.
    #
    # IDENTITY_ENDPOINT/IDENTITY_HEADER are Container Apps' managed-identity
    # token endpoint credentials, not secrets themselves -- forwarding them
    # is what lets the subprocess's own DefaultAzureCredential reach Key
    # Vault at all. Without them ManagedIdentityCredential has no IMDS-
    # equivalent endpoint to call and fails closed.
    env = {
        "TAVILY_API_KEY": os.environ.get("TAVILY_API_KEY", ""),
        "KEY_VAULT_URI": os.environ.get("KEY_VAULT_URI", ""),
    }
    for name in ("IDENTITY_ENDPOINT", "IDENTITY_HEADER", "IDENTITY_SERVER_THUMBPRINT"):
        if name in os.environ:
            env[name] = os.environ[name]

    return StdioServerParameters(
        command=sys.executable,
        args=["search_server.py"],
        cwd=SERVER_DIR,
        env=env,
    )


# Kept for callers/tests that reach for the connection parameters directly.
server_params = _server_params()


async def list_search_tools() -> list:
    """Discovery: retrieve registered tool schemas. Spends no provider budget."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.list_tools()
            return response.tools


async def search_via_mcp(query: str, max_results: int = 5) -> list[str]:
    """Execution: crosses the external boundary and spends provider budget."""
    async with stdio_client(_server_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search",
                {"query": query, "max_results": max_results},
            )
            return [block.text for block in result.content if hasattr(block, "text")]
