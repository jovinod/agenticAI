import asyncio
import unittest
from unittest.mock import patch

import httpx

from isolated_retry_fixture import build_isolated_retry_graph


class TestIsolatedRetryPolicy(unittest.TestCase):
    def test_a_transient_failure_that_escapes_the_node_is_retried(self) -> None:
        call_counts: dict[str, int] = {}
        graph = build_isolated_retry_graph(call_counts)

        result = asyncio.run(graph.ainvoke({}))

        self.assertEqual(result["result"], "recovered")
        self.assertEqual(call_counts["flaky"], 2)


class TestRealNodesDoNotSwallowUnexpectedFailures(unittest.TestCase):
    """The chapter's documented gap, reproduced by the original
    illustrative code, was a broad try/except inside every node that
    returned degraded state before LangGraph's retry policy ever saw the
    exception. These prove that gap is fixed here: an unexpected model
    or search failure escapes the real node instead of being swallowed,
    so the RetryPolicy this chapter attaches actually gets to retry it.
    """

    def test_fundamentals_node_lets_a_model_failure_escape(self) -> None:
        import graph

        async def failing_chat(messages, tools):
            raise httpx.ReadError("simulated transient network failure")

        with patch(
            "graph.fetch_stock_data",
            return_value={"ticker": "AAPL", "price": 100, "currency": "USD", "pe_ratio": 10},
        ), patch("model_client.chat", side_effect=failing_chat):
            with self.assertRaises(httpx.ReadError):
                asyncio.run(graph.fundamentals_node({"ticker": "AAPL", "job_id": ""}))

    def test_decision_node_lets_a_model_failure_escape(self) -> None:
        import graph

        async def failing_chat(messages, tools):
            raise httpx.ReadError("simulated transient network failure")

        with patch("graph.fetch_extended_data", return_value={}), patch(
            "model_client.chat", side_effect=failing_chat
        ):
            with self.assertRaises(httpx.ReadError):
                asyncio.run(
                    graph.decision_node(
                        {"ticker": "AAPL", "job_id": "", "risk_summary": "", "dissent": ""}
                    )
                )


class TestWorkerContainment(unittest.TestCase):
    def test_a_permanently_failing_ticker_degrades_instead_of_raising(self) -> None:
        from containment import run_ticker_safely

        async def always_fails():
            raise RuntimeError("exhausted retries")

        result = asyncio.run(run_ticker_safely("AAPL", always_fails))

        self.assertIn("AAPL", result)
        self.assertIn("unavailable", result)

    def test_a_succeeding_ticker_returns_its_own_result_unchanged(self) -> None:
        from containment import run_ticker_safely

        async def succeeds():
            return "AAPL: real report"

        result = asyncio.run(run_ticker_safely("AAPL", succeeds))

        self.assertEqual(result, "AAPL: real report")


if __name__ == "__main__":
    unittest.main()
