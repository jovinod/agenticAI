from market_data import fetch_stock_data
from search_client import search_via_mcp

FETCH_STOCK_DATA_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_stock_data",
        "description": "Fetch current price and basic fundamentals for a US-listed ticker.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
            },
            "required": ["ticker"],
        },
    },
}

SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search",
        "description": "Search the web for recent news relevant to a query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
}


async def search(query: str, max_results: int = 5) -> list[str]:
    return await search_via_mcp(query, max_results=max_results)


TOOL_SCHEMAS = [FETCH_STOCK_DATA_SCHEMA, SEARCH_SCHEMA]

TOOL_REGISTRY = {
    "fetch_stock_data": fetch_stock_data,
    "search": search,
}
