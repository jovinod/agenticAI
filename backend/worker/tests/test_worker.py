import asyncio
import unittest

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import worker
from models import Job


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
