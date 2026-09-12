import os

from mcp.server.mcpserver import MCPServer
from tavily import TavilyClient

from secret_client import get_tavily_key

mcp = MCPServer("search-server")


def _resolve_tavily_key() -> str | None:
    """Key Vault is the one authoritative home once deployed
    (KEY_VAULT_URI set); a directly passed TAVILY_API_KEY remains the
    local-development fallback from Chapter 5."""
    if os.environ.get("KEY_VAULT_URI"):
        return get_tavily_key()
    return os.environ.get("TAVILY_API_KEY")


@mcp.tool()
def search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return title, content, and URL results."""
    tavily_api_key = _resolve_tavily_key()
    if not tavily_api_key:
        raise EnvironmentError("TAVILY_API_KEY not set")

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
    mcp.run()
