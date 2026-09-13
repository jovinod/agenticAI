import asyncio
import os
import socket
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import search_client

MCP_SEARCH_DIR = Path(__file__).parent.parent.parent / "mcp-search"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@unittest.skipUnless(MCP_SEARCH_DIR.exists(), "backend/mcp-search is missing")
class TestSearchViaMcp(unittest.TestCase):
    """Chapter 18: the worker no longer spawns its own search subprocess
    or reads the Tavily secret -- it only knows the deployed mcp-search
    service's URL and the MCP protocol. This test proves the real
    streamable-HTTP client against a real instance of that service."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = _free_port()
        env = {**os.environ, "TAVILY_API_KEY": "test-local-key", "PORT": str(cls.port)}
        cls.process = subprocess.Popen(
            ["uv", "run", "python", "search_server.py"],
            cwd=MCP_SEARCH_DIR,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        cls.url = f"http://127.0.0.1:{cls.port}/mcp"
        cls._wait_until_ready()

    @classmethod
    def _wait_until_ready(cls) -> None:
        deadline = time.monotonic() + 15
        last_error = None
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.5):
                    return
            except OSError as exc:
                last_error = exc
                time.sleep(0.3)
        raise RuntimeError(f"search server did not start: {last_error}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.process.terminate()
        cls.process.wait(timeout=10)

    def test_discovery_lists_exactly_the_search_tool(self) -> None:
        with patch.object(search_client, "MCP_SEARCH_URL", self.url):
            tools = asyncio.run(search_client.list_search_tools())

        self.assertEqual([tool.name for tool in tools], ["search"])

    def test_a_real_session_initializes_and_returns_a_scanned_result(self) -> None:
        with patch.object(search_client, "MCP_SEARCH_URL", self.url), patch(
            "search_client.scan_documents",
            AsyncMock(side_effect=lambda docs: [True] * len(docs)),
        ):
            results = asyncio.run(search_client.search_via_mcp("AAPL earnings", max_results=1))

        self.assertEqual(len(results), 1)

    def test_a_flagged_result_becomes_the_placeholder(self) -> None:
        with patch.object(search_client, "MCP_SEARCH_URL", self.url), patch(
            "search_client.scan_documents", AsyncMock(return_value=[False])
        ):
            results = asyncio.run(search_client.search_via_mcp("hostile query", max_results=1))

        self.assertEqual(results, [search_client.REMOVED_MESSAGE])


if __name__ == "__main__":
    unittest.main()
