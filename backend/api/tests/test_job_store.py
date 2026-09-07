import os
import tempfile
import unittest

from job_store import JobStore


class TestJobStore(unittest.TestCase):
    def setUp(self) -> None:
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

    def tearDown(self) -> None:
        os.remove(self.path)

    def test_queued_job_persists_across_a_new_connection(self) -> None:
        JobStore(self.path).create_job("job-1", ["AAPL"])

        reopened = JobStore(self.path)
        job = reopened.get_job("job-1")

        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["tickers"], ["AAPL"])

    def test_a_claimed_job_cannot_be_claimed_again(self) -> None:
        store = JobStore(self.path)
        store.create_job("job-1", ["AAPL"])

        first = store.claim_next_job()
        second = store.claim_next_job()

        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_completing_a_job_stores_its_result(self) -> None:
        store = JobStore(self.path)
        store.create_job("job-1", ["AAPL"])
        store.claim_next_job()

        store.complete_job("job-1", {"summary": ["AAPL: done"]})

        job = store.get_job("job-1")
        self.assertEqual(job["status"], "done")
        self.assertEqual(job["result"], {"summary": ["AAPL: done"]})


if __name__ == "__main__":
    unittest.main()
