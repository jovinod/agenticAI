import asyncio
import os
import unittest

from search_client import list_search_tools, search_via_mcp


class TestDiscovery(unittest.TestCase):
    def test_the_server_is_reachable_without_a_provider_key(self) -> None:
        # Registration and discovery must not require TAVILY_API_KEY --
        # only execution does. Unset it here so this test proves that,
        # even if a real key happens to be exported in the shell.
        real_key = os.environ.pop("TAVILY_API_KEY", None)
        try:
            tools = asyncio.run(list_search_tools())
        finally:
            if real_key is not None:
                os.environ["TAVILY_API_KEY"] = real_key

        self.assertEqual([tool.name for tool in tools], ["search"])

    def test_the_schema_names_query_and_max_results(self) -> None:
        tools = asyncio.run(list_search_tools())
        search_tool = next(tool for tool in tools if tool.name == "search")

        properties = search_tool.input_schema["properties"]
        self.assertIn("query", properties)
        self.assertIn("max_results", properties)
        self.assertIn("query", search_tool.input_schema.get("required", []))


class TestExecution(unittest.TestCase):
    @unittest.skipIf(
        os.environ.get("TAVILY_API_KEY"),
        "a real TAVILY_API_KEY is present -- this run cannot prove the missing-key path",
    )
    def test_missing_key_reports_an_error_not_a_crash(self) -> None:
        import search_client
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        async def call() -> bool:
            async with stdio_client(search_client.server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("search", {"query": "test"})
                    return result.is_error

        self.assertTrue(asyncio.run(call()))

    @unittest.skipUnless(
        os.environ.get("TAVILY_API_KEY"),
        "no TAVILY_API_KEY exported -- skipping the live call",
    )
    def test_a_bounded_live_call_retains_source_urls(self) -> None:
        texts = asyncio.run(
            search_via_mcp("Apple latest quarterly earnings", max_results=3)
        )

        self.assertLessEqual(len(texts), 3)
        self.assertGreater(len(texts), 0)
        for text in texts:
            self.assertIn("url", text.lower())


if __name__ == "__main__":
    unittest.main()
