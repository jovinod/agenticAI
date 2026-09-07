import asyncio
import os
import tempfile
import unittest

from job_store import JobStore
from worker import process_next_job


class TestWorker(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.store = JobStore(self.path)

    def tearDown(self) -> None:
        os.remove(self.path)

    def test_process_next_job_completes_a_queued_job(self) -> None:
        self.store.create_job("job-1", ["AAPL"])

        claimed = asyncio.run(process_next_job(self.store, delay_seconds=0))

        self.assertTrue(claimed)
        job = self.store.get_job("job-1")
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"]["jobId"], "job-1")
        self.assertIn("AAPL", job["result"]["summary"][0])

    def test_process_next_job_returns_false_when_queue_is_empty(self) -> None:
        claimed = asyncio.run(process_next_job(self.store, delay_seconds=0))

        self.assertFalse(claimed)


if __name__ == "__main__":
    unittest.main()
