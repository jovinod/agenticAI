import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from main import app


class TestResearchContract(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch.object(main, "JOB_DELAY_SECONDS", 0)
    def test_create_and_read_research_job(self) -> None:
        response = self.client.post(
            "/research",
            json={"tickers": ["aapl", "MSFT"]},
        )

        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]

        status_response = self.client.get(f"/research/{job_id}")
        self.assertEqual(status_response.json()["status"], "done")

    def test_rejects_malformed_tickers(self) -> None:
        response = self.client.post(
            "/research",
            json={"tickers": ["not-a-ticker"]},
        )

        self.assertEqual(response.status_code, 422)

    def test_rejects_empty_ticker_list(self) -> None:
        response = self.client.post("/research", json={"tickers": []})

        self.assertEqual(response.status_code, 422)

    def test_unknown_job_id_returns_404(self) -> None:
        response = self.client.get("/research/does-not-exist")

        self.assertEqual(response.status_code, 404)

    def test_job_reports_running_before_its_deadline(self) -> None:
        response = self.client.post(
            "/research",
            json={"tickers": ["AAPL"]},
        )
        job_id = response.json()["job_id"]

        status_response = self.client.get(f"/research/{job_id}")

        self.assertEqual(status_response.json()["status"], "running")
        self.assertIsNone(status_response.json()["result"])


if __name__ == "__main__":
    unittest.main()
