import asyncio
import os

from job_store import JobStore

DATABASE_PATH = os.getenv("DATABASE_PATH", "jobs.db")
POLL_INTERVAL_SECONDS = 0.5

# Intentionally temporary: stands in for real research work. Chapter 4
# replaces this with an actual market-data call.
JOB_DELAY_SECONDS = 2.0


async def process_next_job(
    store: JobStore,
    delay_seconds: float = JOB_DELAY_SECONDS,
) -> bool:
    job = store.claim_next_job()
    if job is None:
        return False

    await asyncio.sleep(delay_seconds)
    result = {
        "jobId": job["job_id"],
        "summary": [
            f"{ticker}: sample result from the Chapter 3 worker."
            for ticker in job["tickers"]
        ],
    }
    store.complete_job(job["job_id"], result)
    return True


async def main() -> None:
    store = JobStore(DATABASE_PATH)
    print("Worker started, polling for queued jobs...")
    while True:
        claimed = await process_next_job(store)
        if not claimed:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
