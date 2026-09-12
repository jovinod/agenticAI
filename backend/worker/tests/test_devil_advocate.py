import asyncio
import unittest

from devil_advocate import build_registry, dispatch, run_devil_advocate


class TestDevilAdvocateRegistry(unittest.TestCase):
    def test_only_search_web_is_callable(self) -> None:
        registry = build_registry(lambda query: [])

        self.assertEqual(set(registry.keys()), {"search_web"})

        result = asyncio.run(
            dispatch("delete_database", {}, registry)
        )
        self.assertIn("unknown tool", result["error"])

    def test_a_search_call_is_dispatched_and_a_final_answer_returned(self) -> None:
        def search_web(query: str) -> list[str]:
            return [f"counter-evidence for: {query}"]

        calls = [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "search_web",
                                "arguments": {"query": "AAPL fraud allegations"},
                            },
                        }
                    ],
                },
                "usage": {},
            },
            {
                "message": {
                    "role": "assistant",
                    "content": "Found no fraud allegations, but margins have been declining.",
                },
                "usage": {},
            },
        ]

        async def chat(messages, tools):
            return calls.pop(0)

        result = asyncio.run(
            run_devil_advocate(chat, {"fundamentals": "strong margins"}, search_web)
        )

        self.assertEqual(result["confidence"], "normal")
        self.assertIn("declining", result["dissent"])


if __name__ == "__main__":
    unittest.main()
