import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault(
    "SERVICEBUS_CONNECTION_STRING",
    "Endpoint=sb://fake.servicebus.windows.net/;"
    "SharedAccessKeyName=fake;SharedAccessKey=ZmFrZQ==",
)
os.environ.setdefault("ENTRA_CLIENT_ID", "00000000-0000-0000-0000-000000000000")
os.environ.setdefault("ENTRA_TENANT_ID", "00000000-0000-0000-0000-000000000000")

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, create_engine

import main

# This module tests the HTTP contract (validation, status codes,
# 404s), not token validation -- that is auth.py's job and it is
# tested on its own in test_auth.py. Overriding require_user here
# keeps these tests fast and independent of a real Entra tenant.
main.app.dependency_overrides[main.require_user] = lambda: object()


class FakeSender:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def __aenter__(self) -> "FakeSender":
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        return False

    async def send_messages(self, message: object) -> None:
        self.sent.append(str(message))


class FakeServiceBusClient:
    def __init__(self) -> None:
        self.sender = FakeSender()

    def get_queue_sender(self, queue_name: str) -> FakeSender:
        return self.sender

    async def close(self) -> None:
        pass


class TestResearchContract(unittest.TestCase):
    def setUp(self) -> None:
        main.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(main.engine)

        self.openid_config_patcher = patch.object(
            main.azure_scheme.openid_config, "load_config", AsyncMock()
        )
        self.openid_config_patcher.start()

        self.client = TestClient(main.app)
        self.client.__enter__()
        self.fake_servicebus = FakeServiceBusClient()
        main.app.state.servicebus_client = self.fake_servicebus

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        self.openid_config_patcher.stop()

    def test_create_and_read_research_job(self) -> None:
        response = self.client.post(
            "/research",
            json={"tickers": ["aapl", "MSFT"]},
        )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(self.fake_servicebus.sender.sent), 1)

        job_id = response.json()["job_id"]
        status_response = self.client.get(f"/research/{job_id}")
        self.assertEqual(status_response.json()["status"], "queued")
        self.assertIsNone(status_response.json()["result"])

    def test_rejects_malformed_tickers(self) -> None:
        response = self.client.post(
            "/research",
            json={"tickers": ["not-a-ticker"]},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(len(self.fake_servicebus.sender.sent), 0)

    def test_rejects_empty_ticker_list(self) -> None:
        response = self.client.post("/research", json={"tickers": []})

        self.assertEqual(response.status_code, 422)

    def test_unknown_job_id_returns_404(self) -> None:
        response = self.client.get("/research/does-not-exist")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
