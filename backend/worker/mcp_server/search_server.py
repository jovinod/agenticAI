"""
A minimal MCP server exposing one tool: web search via Tavily.

Adapted from buynobuy's skills/utils/search.py::_tavily() — simplified to just
the primary backend for this first pass (no DuckDuckGo/Playwright fallback yet).

Phase 11 — graduated from Option A (stdio, spawned as a subprocess by
alpha-worker) to Option B: its own Container App, HTTP transport
(streamable-http), independently autoscaled. Resolving the Tavily key is now
this process's own job — Key Vault via its own Managed Identity in Azure, a
plain env var locally — since there's no longer a parent process resolving
it once and handing it down via subprocess env=.

Run standalone for local testing: TAVILY_API_KEY=... uv run python search_server.py
"""
import os
from mcp.server.mcpserver import MCPServer
from tavily import TavilyClient

KEY_VAULT_URL = os.environ.get("KEY_VAULT_URL")
if KEY_VAULT_URL:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    _kv_client = SecretClient(vault_url=KEY_VAULT_URL, credential=DefaultAzureCredential())
    TAVILY_API_KEY = _kv_client.get_secret("tavily-api-key").value
else:
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
    # Container Apps injects the listening port via $PORT for HTTP ingress
    # targets -- defaulting to 8811 for local runs, matching the port used
    # throughout local testing.
    port = int(os.environ.get("PORT", 8811))
    # json_response=True -- found live: the default SSE/chunked-stream response
    # shape worked perfectly on localhost (both from outside and inside the
    # container) but hung indefinitely crossing Azure Container Apps' internal
    # ingress proxy -- session.initialize() never received its response.
    # Plain single-JSON responses avoid whatever the proxy does to the
    # streamed shape.
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port, stateless_http=True, json_response=True)
