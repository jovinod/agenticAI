import asyncio
import unittest
from unittest.mock import patch

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

        market_patcher = patch("worker.fetch_stock_data", return_value=FAKE_STOCK_DATA)
        self.addCleanup(market_patcher.stop)
        market_patcher.start()

        async def fake_search(query: str, max_results: int = 5) -> list[str]:
            return ['[{"title": "Fake headline", "url": "https://example.com"}]']

        search_patcher = patch("worker.search_via_mcp", side_effect=fake_search)
        self.addCleanup(search_patcher.stop)
        search_patcher.start()

    def test_process_message_completes_the_job(self) -> None:
        asyncio.run(worker.process_message("job-1", ["AAPL"], delay_seconds=0))

        with Session(worker.engine) as session:
            job = session.exec(select(Job).where(Job.job_id == "job-1")).first()

        self.assertEqual(job.status, "done")
        self.assertIn("AAPL", job.result)

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
