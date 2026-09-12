import asyncio
import os
import unittest
import uuid


@unittest.skipUnless(
    os.environ.get("REDIS_URL"), "no REDIS_URL exported -- skipping the live call"
)
class TestProgress(unittest.TestCase):
    def test_a_completed_agents_key_appears_while_unfinished_agents_remain_absent(
        self,
    ) -> None:
        import progress

        job_id = f"test-{uuid.uuid4()}"
        ticker = "AAPL"

        async def run():
            await progress.write_progress(job_id, ticker, "technical", "momentum: up")
            return await progress.read_progress(
                job_id, ticker, ["fundamentals", "technical", "news"]
            )

        completed = asyncio.run(run())

        self.assertEqual(completed, {"technical": "momentum: up"})


if __name__ == "__main__":
    unittest.main()
