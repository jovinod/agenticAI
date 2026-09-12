import asyncio
import os
import unittest
import uuid


def _conninfo() -> str:
    """The saver expects ordinary libpq connection syntax, not
    SQLAlchemy's dialect-qualified URL."""
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+psycopg://", "postgresql://")


@unittest.skipUnless(
    os.environ.get("DATABASE_URL"), "no DATABASE_URL exported -- skipping the live call"
)
class TestPostgresCheckpoint(unittest.TestCase):
    def test_fresh_vs_resume_input_selection(self) -> None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from thread import resolve_resume_input

        async def run():
            async with AsyncPostgresSaver.from_conn_string(_conninfo()) as saver:
                await saver.setup()
                thread_id = f"test-{uuid.uuid4()}:AAPL"

                fresh_input, _ = await resolve_resume_input(
                    saver, thread_id, {"value": 0}
                )
                return fresh_input

        self.assertEqual(asyncio.run(run()), {"value": 0})

    def test_a_failure_before_fan_out_commits_reruns_all_three_specialists(self) -> None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from checkpoint_graph_fixture import build_fixture_graph

        thread_id = f"test-{uuid.uuid4()}:AAPL"
        call_counts: dict[str, int] = {}

        async def run():
            async with AsyncPostgresSaver.from_conn_string(_conninfo()) as saver:
                await saver.setup()
                config = {"configurable": {"thread_id": thread_id}}

                graph = build_fixture_graph(saver, call_counts, fail_node="news")
                with self.assertRaises(RuntimeError):
                    await graph.ainvoke({}, config)

                # Resume: a fresh build call re-registers the same nodes
                # against the same durable thread. `news` now succeeds,
                # so nothing should fail this time.
                graph = build_fixture_graph(saver, call_counts, fail_node=None)
                await graph.ainvoke(None, config)

        asyncio.run(run())

        # The whole parallel super-step reruns because it never committed.
        self.assertEqual(call_counts["fundamentals"], 2)
        self.assertEqual(call_counts["technical"], 2)
        self.assertEqual(call_counts["news"], 2)
        self.assertEqual(call_counts["risk"], 1)

    def test_a_failure_after_fan_out_commits_resumes_at_risk(self) -> None:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        from checkpoint_graph_fixture import build_fixture_graph

        thread_id = f"test-{uuid.uuid4()}:MSFT"
        call_counts: dict[str, int] = {}

        async def run():
            async with AsyncPostgresSaver.from_conn_string(_conninfo()) as saver:
                await saver.setup()
                config = {"configurable": {"thread_id": thread_id}}

                graph = build_fixture_graph(saver, call_counts, fail_node="risk")
                with self.assertRaises(RuntimeError):
                    await graph.ainvoke({}, config)

                graph = build_fixture_graph(saver, call_counts, fail_node=None)
                await graph.ainvoke(None, config)

        asyncio.run(run())

        # The completed parallel super-step is durable and does not rerun.
        self.assertEqual(call_counts["fundamentals"], 1)
        self.assertEqual(call_counts["technical"], 1)
        self.assertEqual(call_counts["news"], 1)
        self.assertEqual(call_counts["risk"], 2)
        self.assertEqual(call_counts["devil_advocate"], 1)
        self.assertEqual(call_counts["decision"], 1)


if __name__ == "__main__":
    unittest.main()
