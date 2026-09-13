import asyncio
import unittest
from unittest.mock import patch

from harness import _call_tool, run_agent
from tools import TOOL_REGISTRY
from devil_advocate import build_registry, dispatch


class TestDispatchEnforcementAcrossRealRegistries(unittest.TestCase):
    """Chapter 15's own point, proven against this branch's real
    registries instead of a stand-in: an invented tool name reaches the
    dispatcher and is rejected before any real registered function ever
    runs, and a name valid in one agent's registry is simply unknown to
    another -- there is no shared namespace a mistake could reach into.
    """

    def test_an_invented_function_name_is_rejected_by_the_real_tool_registry(self) -> None:
        result = asyncio.run(
            _call_tool("delete_database", {"table": "jobs"}, TOOL_REGISTRY)
        )

        self.assertEqual(result, {"error": "unknown tool: delete_database"})

    def test_a_name_valid_for_the_devil_advocate_registry_is_unknown_to_the_harness_registry(
        self,
    ) -> None:
        devil_registry = build_registry(lambda query: [])

        # "search_web" is the devil's advocate's own tool name -- the
        # harness registry (fetch_stock_data, search) has never heard of it.
        result = asyncio.run(_call_tool("search_web", {"query": "x"}, TOOL_REGISTRY))
        self.assertIn("unknown tool", result["error"])

        # And the reverse: the harness registry's own tool names mean
        # nothing to the devil's advocate's registry.
        result = asyncio.run(dispatch("fetch_stock_data", {"ticker": "AAPL"}, devil_registry))
        self.assertIn("unknown tool", result["error"])


class TestTurnBudgetIsACapNotARetry(unittest.TestCase):
    """Chapter 12 established this distinction for node-level retries;
    this is the harness-level analog, proven against the real
    harness.run_agent the worker's chapter-6 dispatch loop uses."""

    def test_a_model_that_never_stops_requesting_tools_is_cut_off_at_the_cap(self) -> None:
        call_count = 0

        async def chat(messages, tools):
            nonlocal call_count
            call_count += 1
            return {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": f"call_{call_count}",
                            "function": {"name": "search", "arguments": {"query": "x"}},
                        }
                    ],
                },
                "usage": {},
            }

        async def fake_search(query: str, max_results: int = 5) -> list[str]:
            return ["fake result"]

        with patch("tools.search_via_mcp", side_effect=fake_search):
            result = asyncio.run(
                run_agent(chat, "system", "find something", [], TOOL_REGISTRY, max_turns=3)
            )

        self.assertEqual(call_count, 3)
        self.assertEqual(result["status"], "max_turns_exceeded")


if __name__ == "__main__":
    unittest.main()
