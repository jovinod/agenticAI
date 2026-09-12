import asyncio
import unittest
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import worker
from models import Job

FAKE_STOCK_DATA = {
    "ticker": "AAPL",
    "price": 150.0,
    "currency": "USD",
    "pe_ratio": 25.0,
    "fifty_two_week_high": 200.0,
    "fifty_two_week_low": 100.0,
}


class TestWorker(unittest.TestCase):
    async def _fake_get_checkpointer(self):
        if not hasattr(self, "_checkpointer"):
            self._checkpointer = InMemorySaver()
        return self._checkpointer

    def setUp(self) -> None:
        worker.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(worker.engine)

        with Session(worker.engine) as session:
            session.add(Job(job_id="job-1", tickers='["AAPL"]'))
            session.commit()

        # A fresh in-memory checkpointer per test, and a fresh graph built
        # against it -- the module-level cache would otherwise leak a
        # prior test's checkpointer into this one.
        worker.research_graph = None
        checkpointer_patcher = patch(
            "worker.get_checkpointer", side_effect=self._fake_get_checkpointer
        )
        self.addCleanup(checkpointer_patcher.stop)
        checkpointer_patcher.start()

        market_patcher = patch("graph.fetch_stock_data", return_value=FAKE_STOCK_DATA)
        self.addCleanup(market_patcher.stop)
        market_patcher.start()

        extended_patcher = patch("graph.fetch_extended_data", return_value={})
        self.addCleanup(extended_patcher.stop)
        extended_patcher.start()

        async def fake_search(query: str, max_results: int = 5) -> list[str]:
            return ['[{"title": "Fake headline", "url": "https://example.com"}]']

        search_patcher = patch("graph.search", side_effect=fake_search)
        self.addCleanup(search_patcher.stop)
        search_patcher.start()

        async def fake_chat(messages: list[dict], tools: list[dict]) -> dict:
            return {
                "message": {"role": "assistant", "content": "fake model summary"},
                "usage": {"total_tokens": 1},
            }

        chat_patcher = patch("model_client.chat", side_effect=fake_chat)
        self.addCleanup(chat_patcher.stop)
        chat_patcher.start()

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

    def test_process_message_completes_the_job(self) -> None:
        asyncio.run(worker.process_message("job-1", ["AAPL"], delay_seconds=0))

        with Session(worker.engine) as session:
            job = session.exec(select(Job).where(Job.job_id == "job-1")).first()

        self.assertEqual(job.status, "done")
        self.assertIn("AAPL", job.result)

    def test_a_permanently_failing_ticker_does_not_block_the_others(self) -> None:
        with Session(worker.engine) as session:
            session.add(Job(job_id="job-2", tickers='["AAPL", "BADCO"]'))
            session.commit()

        real_run = worker._run_graph_for_ticker

        async def flaky_run(ticker: str, job_id: str) -> str:
            if ticker == "BADCO":
                raise RuntimeError("exhausted retries")
            return await real_run(ticker, job_id)

        with patch("worker._run_graph_for_ticker", side_effect=flaky_run):
            asyncio.run(worker.process_message("job-2", ["AAPL", "BADCO"], delay_seconds=0))

        with Session(worker.engine) as session:
            job = session.exec(select(Job).where(Job.job_id == "job-2")).first()

        self.assertEqual(job.status, "done")
        self.assertIn("AAPL", job.result)
        self.assertIn("BADCO", job.result)
        self.assertIn("unavailable", job.result)

    def test_process_message_marks_the_job_running_first(self) -> None:
        async def observe_mid_flight() -> str:
            task = asyncio.create_task(
                worker.process_message("job-1", ["AAPL"], delay_seconds=0.05)
            )
            await asyncio.sleep(0.01)
            with Session(worker.engine) as session:
                mid_flight = session.exec(
                    select(Job).where(Job.job_id == "job-1")
                ).first()
            await task
            return mid_flight.status

        status = asyncio.run(observe_mid_flight())
        self.assertEqual(status, "running")


if __name__ == "__main__":
    unittest.main()
