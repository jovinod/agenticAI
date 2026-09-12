import os

from mcp.server.mcpserver import MCPServer
from tavily import TavilyClient

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

mcp = MCPServer("search-server")


@mcp.tool()
def search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return title, content, and URL results."""
    if not TAVILY_API_KEY:
        raise EnvironmentError("TAVILY_API_KEY not set")

    response = TavilyClient(api_key=TAVILY_API_KEY).search(
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
