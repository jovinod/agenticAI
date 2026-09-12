import asyncio
import time
import unittest
from unittest.mock import patch

from graph import build_graph

DELAY = 0.2

FAKE_STOCK_DATA = {
    "ticker": "AAPL",
    "price": 105.0,
    "currency": "USD",
    "pe_ratio": -5.0,
    "fifty_two_week_high": 200.0,
    "fifty_two_week_low": 100.0,
}


def delayed_chat_returning(node_tokens: dict[str, int]):
    """A fake chat that answers based on the system prompt's first word
    of its role hint, tagging usage per specialist -- proving the
    reducer sums independent contributions, not a shared counter."""

    async def chat(messages, tools):
        await asyncio.sleep(DELAY)
        system_prompt = messages[0]["content"]
        if "synthesizer" in system_prompt:
            node = "synthesizer"
        elif "fundamentals analyst" in system_prompt:
            node = "fundamentals"
        elif "technical analyst" in system_prompt:
            node = "technical"
        else:
            node = "news"
        return {
            "message": {"role": "assistant", "content": f"{node} summary"},
            "usage": {"total_tokens": node_tokens[node]},
        }

    return chat


class TestResearchGraph(unittest.TestCase):
    def setUp(self) -> None:
        market_patcher = patch("graph.fetch_stock_data", return_value=FAKE_STOCK_DATA)
        self.addCleanup(market_patcher.stop)
        market_patcher.start()

        async def fake_search(query: str, max_results: int = 5) -> list[str]:
            return ['[{"title": "headline", "url": "https://example.com"}]']

        search_patcher = patch("graph.search", side_effect=fake_search)
        self.addCleanup(search_patcher.stop)
        search_patcher.start()

    def test_three_specialists_overlap(self) -> None:
        with patch(
            "model_client.chat",
            side_effect=delayed_chat_returning(
                {"fundamentals": 10, "technical": 20, "news": 30, "synthesizer": 5}
            ),
        ):
            graph = build_graph()
            start = time.monotonic()
            asyncio.run(graph.ainvoke({"ticker": "AAPL"}))
            elapsed = time.monotonic() - start

        # Three specialists each sleep DELAY; a synthesizer call follows
        # sequentially after risk. Overlap means this is well under 3x.
        self.assertLess(elapsed, DELAY * 2.5)

    def test_usage_reducer_sums_concurrent_contributions(self) -> None:
        with patch(
            "model_client.chat",
            side_effect=delayed_chat_returning(
                {"fundamentals": 10, "technical": 20, "news": 30, "synthesizer": 5}
            ),
        ):
            graph = build_graph()
            result = asyncio.run(graph.ainvoke({"ticker": "AAPL"}))

        total = sum(entry.get("total_tokens", 0) for entry in result["usage_log"])
        self.assertEqual(total, 65)

    def test_risk_flags_come_from_the_real_deterministic_rules(self) -> None:
        with patch(
            "model_client.chat",
            side_effect=delayed_chat_returning(
                {"fundamentals": 1, "technical": 1, "news": 1, "synthesizer": 1}
            ),
        ):
            graph = build_graph()
            result = asyncio.run(graph.ainvoke({"ticker": "AAPL"}))

        # FAKE_STOCK_DATA has price near its 52-week low and a negative P/E.
        self.assertIn("near_52_week_low", result["risk_summary"])
        self.assertIn("unprofitable", result["risk_summary"])

    def test_the_final_report_reflects_the_synthesizer(self) -> None:
        with patch(
            "model_client.chat",
            side_effect=delayed_chat_returning(
                {"fundamentals": 1, "technical": 1, "news": 1, "synthesizer": 1}
            ),
        ):
            graph = build_graph()
            result = asyncio.run(graph.ainvoke({"ticker": "AAPL"}))

        self.assertEqual(result["final_report"], "synthesizer summary")


if __name__ == "__main__":
    unittest.main()
