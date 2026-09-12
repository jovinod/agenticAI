import asyncio
import os
import unittest
import uuid
from pathlib import Path

ENV_PATH = Path(__file__).parent.parent / ".env"


@unittest.skipUnless(
    ENV_PATH.exists(),
    "no local .env with DATABASE_URL / APIM_BASE_URL / APIM_SUBSCRIPTION_KEY",
)
class TestEmbedWorker(unittest.TestCase):
    def test_embedding_and_write_produces_a_searchable_row(self) -> None:
        if ENV_PATH.exists():
            for line in ENV_PATH.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())

        import embed_worker
        from models import ResearchReport
        from sqlmodel import Session, select

        job_id = f"test-{uuid.uuid4()}"
        data = {
            "job_id": job_id,
            "ticker": "AAPL",
            "market": "US",
            "report_text": "Apple's fundamentals look stable with steady revenue growth.",
        }

        asyncio.run(embed_worker.process_message(data))

        with Session(embed_worker.engine) as session:
            row = session.exec(
                select(ResearchReport).where(ResearchReport.job_id == job_id)
            ).first()

        self.assertIsNotNone(row)
        self.assertEqual(len(row.embedding), 1536)


if __name__ == "__main__":
    unittest.main()
