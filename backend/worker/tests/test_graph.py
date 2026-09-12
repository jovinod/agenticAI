import asyncio
import json
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

FAKE_EXTENDED_DATA = {
    "roe": 0.15,
    "debt_to_equity": 50,
    "free_cash_flow_history": [10.0, 12.0],
    "eps_history": {"2023": 5.0, "2024": 6.0},
    "monthly_prices": {"2023-01": 100, "2024-01": 120},
    "current_price": 105.0,
}


def delayed_chat_returning(node_tokens: dict[str, int]):
    """A fake chat that answers based on the system prompt's role hint,
    tagging usage per node -- proving the reducer sums independent
    contributions, not a shared counter."""

    async def chat(messages, tools):
        await asyncio.sleep(DELAY)
        system_prompt = messages[0]["content"]
        if "decision agent" in system_prompt:
            node = "decision"
            content = json.dumps(
                {"recommendation": "BUY", "overall_score": 7, "summary": "decision summary"}
            )
        elif "devil's advocate" in system_prompt:
            node = "devil_advocate"
            content = "dissent summary"
        elif "fundamentals analyst" in system_prompt:
            node = "fundamentals"
            content = f"{node} summary"
        elif "technical analyst" in system_prompt:
            node = "technical"
            content = f"{node} summary"
        else:
            node = "news"
            content = f"{node} summary"
        return {
            "message": {"role": "assistant", "content": content},
            "usage": {"total_tokens": node_tokens.get(node, 0)},
        }

    return chat


class TestResearchGraph(unittest.TestCase):
    def setUp(self) -> None:
        market_patcher = patch("graph.fetch_stock_data", return_value=FAKE_STOCK_DATA)
        self.addCleanup(market_patcher.stop)
        market_patcher.start()

        extended_patcher = patch(
            "graph.fetch_extended_data", return_value=FAKE_EXTENDED_DATA
        )
        self.addCleanup(extended_patcher.stop)
        extended_patcher.start()

        async def fake_search(query: str, max_results: int = 5) -> list[str]:
            return ['[{"title": "headline", "url": "https://example.com"}]']

        search_patcher = patch("graph.search", side_effect=fake_search)
        self.addCleanup(search_patcher.stop)
        search_patcher.start()

        record_patcher = patch("graph.record_research")
        self.addCleanup(record_patcher.stop)
        record_patcher.start()

        async def fake_search_reports(query: str, limit: int = 5) -> list[dict]:
            return []

        prior_patcher = patch("graph.search_reports", side_effect=fake_search_reports)
        self.addCleanup(prior_patcher.stop)
        prior_patcher.start()

        async def fake_write_progress(job_id, ticker, agent_name, summary) -> None:
            return None

        progress_patcher = patch("graph.write_progress", side_effect=fake_write_progress)
        self.addCleanup(progress_patcher.stop)
        progress_patcher.start()

        async def fake_publish_embedding_job(job_id, ticker, market, report_text) -> None:
            return None

        publish_patcher = patch(
            "graph.publish_embedding_job", side_effect=fake_publish_embedding_job
        )
        self.addCleanup(publish_patcher.stop)
        publish_patcher.start()

    def test_three_specialists_overlap(self) -> None:
        with patch(
            "model_client.chat",
            side_effect=delayed_chat_returning(
                {"fundamentals": 10, "technical": 20, "news": 30, "decision": 5}
            ),
        ):
            graph = build_graph()
            start = time.monotonic()
            asyncio.run(graph.ainvoke({"ticker": "AAPL"}))
            elapsed = time.monotonic() - start

        # Three specialists each sleep DELAY; devil's advocate and decision
        # follow sequentially after risk. Overlap means this is well under
        # what four fully-serial DELAY-length calls would take.
        self.assertLess(elapsed, DELAY * 3.5)

    def test_usage_reducer_sums_concurrent_contributions(self) -> None:
        with patch(
            "model_client.chat",
            side_effect=delayed_chat_returning(
                {"fundamentals": 10, "technical": 20, "news": 30, "decision": 5}
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
                {"fundamentals": 1, "technical": 1, "news": 1, "decision": 1}
            ),
        ):
            graph = build_graph()
            result = asyncio.run(graph.ainvoke({"ticker": "AAPL"}))

        # FAKE_STOCK_DATA has price near its 52-week low and a negative P/E.
        self.assertIn("near_52_week_low", result["risk_summary"])
        self.assertIn("unprofitable", result["risk_summary"])

    def test_the_final_report_reflects_the_decision_not_a_synthesizer(self) -> None:
        with patch(
            "model_client.chat",
            side_effect=delayed_chat_returning(
                {"fundamentals": 1, "technical": 1, "news": 1, "decision": 1}
            ),
        ):
            graph = build_graph()
            result = asyncio.run(graph.ainvoke({"ticker": "AAPL"}))

        self.assertEqual(result["final_report"], "decision summary")
        self.assertEqual(result["recommendation"], "BUY")
        self.assertIn("dissent", result)

    def test_deterministic_decision_fields_come_from_real_data(self) -> None:
        with patch(
            "model_client.chat",
            side_effect=delayed_chat_returning(
                {"fundamentals": 1, "technical": 1, "news": 1, "decision": 1}
            ),
        ):
            graph = build_graph()
            result = asyncio.run(graph.ainvoke({"ticker": "AAPL"}))

        self.assertEqual(result["hard_stops_triggered"], [])
        self.assertIn("label", result["intrinsic_value"])


if __name__ == "__main__":
    unittest.main()
