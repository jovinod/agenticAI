import os

from mcp.server.mcpserver import MCPServer
from tavily import TavilyClient

TAVILY_SECRET_NAME = "tavily-api-key"
KEY_VAULT_URI = os.environ.get("KEY_VAULT_URI", "")

_cached_key: str | None = None


def _get_tavily_key() -> str:
    """The search service owns Tavily secret retrieval -- the worker no
    longer creates a subprocess or reads this secret itself. Local
    development reads an environment variable; deployed, it uses this
    service's own Managed Identity to read Key Vault. Cached after
    first fetch rather than adding a vault round trip to every search.
    """
    global _cached_key
    if _cached_key is not None:
        return _cached_key

    env_key = os.environ.get("TAVILY_API_KEY")
    if env_key:
        _cached_key = env_key
        return _cached_key

    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=KEY_VAULT_URI, credential=credential)
    _cached_key = client.get_secret(TAVILY_SECRET_NAME).value
    return _cached_key


mcp = MCPServer("search-server")


@mcp.tool()
def search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return title, content, and URL results."""
    tavily_api_key = _get_tavily_key()

    response = TavilyClient(api_key=tavily_api_key).search(
        query=query,
        max_results=max_results,
        include_answer=False,
    )
    return [
        {
            "title": result.get("title", ""),
            "content": result.get("content", ""),
            "url": result.get("url", ""),
        }
        for result in response.get("results", [])
    ]


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8811))
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=port,
        stateless_http=True,
        json_response=True,
    )
