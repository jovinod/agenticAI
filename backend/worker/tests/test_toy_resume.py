import asyncio
import unittest

from langgraph.checkpoint.memory import InMemorySaver

from thread import resolve_resume_input
from toy_graph import build_toy_graph


class TestToyResumeSemantics(unittest.TestCase):
    def test_a_crash_in_c_resumes_without_rerunning_a_and_b(self) -> None:
        """InMemorySaver proves invocation semantics -- it cannot survive
        process termination, so it is not evidence of restart recovery."""
        calls = {"a": 0, "b": 0, "c": 0}
        checkpointer = InMemorySaver()
        graph = build_toy_graph(checkpointer, calls)
        config = {"configurable": {"thread_id": "job-1:AAPL"}}

        with self.assertRaises(RuntimeError):
            asyncio.run(graph.ainvoke({"value": 0}, config))

        self.assertEqual(calls, {"a": 1, "b": 1, "c": 1})

        # Resuming with None, not the original input, is what makes this
        # a resume rather than a second independent run.
        asyncio.run(graph.ainvoke(None, config))

        self.assertEqual(calls, {"a": 1, "b": 1, "c": 2})

    def test_repeating_the_original_input_reruns_earlier_work(self) -> None:
        """The negative case the chapter warns about: passing the
        original state again, instead of None, changes the behavior."""
        calls = {"a": 0, "b": 0, "c": 0}
        checkpointer = InMemorySaver()
        graph = build_toy_graph(checkpointer, calls)
        config = {"configurable": {"thread_id": "job-2:MSFT"}}

        with self.assertRaises(RuntimeError):
            asyncio.run(graph.ainvoke({"value": 0}, config))

        asyncio.run(graph.ainvoke({"value": 0}, config))

        self.assertEqual(calls["a"], 2)
        self.assertEqual(calls["b"], 2)

    def test_resolve_resume_input_picks_fresh_for_an_unseen_thread(self) -> None:
        checkpointer = InMemorySaver()

        resume_input, config = asyncio.run(
            resolve_resume_input(checkpointer, "job-3:AAPL", {"value": 0})
        )

        self.assertEqual(resume_input, {"value": 0})

    def test_resolve_resume_input_picks_none_for_an_existing_thread(self) -> None:
        calls = {"a": 0, "b": 0, "c": 0}
        checkpointer = InMemorySaver()
        graph = build_toy_graph(checkpointer, calls, fail_on_first_c=False)
        config = {"configurable": {"thread_id": "job-4:AAPL"}}
        asyncio.run(graph.ainvoke({"value": 0}, config))

        resume_input, _ = asyncio.run(
            resolve_resume_input(checkpointer, "job-4:AAPL", {"value": 0})
        )

        self.assertIsNone(resume_input)


if __name__ == "__main__":
    unittest.main()
