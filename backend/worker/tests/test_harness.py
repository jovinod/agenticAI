import asyncio
import unittest
from unittest.mock import patch

from harness import run_agent
from tools import FETCH_STOCK_DATA_SCHEMA, TOOL_REGISTRY

FAKE_STOCK_DATA = {"ticker": "AAPL", "price": 305.93, "currency": "USD"}


def scripted_chat(responses):
    """Returns an async chat function that yields each response in order,
    repeating the last one if the harness calls more times than scripted."""
    calls = list(responses)

    async def chat(messages, tool_schemas):
        response = calls.pop(0) if calls else responses[-1]
        return response

    return chat


def assistant_message(content=None, tool_calls=None):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


class TestHarness(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch("tools.fetch_stock_data", return_value=FAKE_STOCK_DATA)
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_a_known_tool_with_valid_arguments_runs_and_its_result_is_appended(self):
        chat = scripted_chat(
            [
                {
                    "message": assistant_message(
                        tool_calls=[
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "fetch_stock_data",
                                    "arguments": {"ticker": "AAPL"},
                                },
                            }
                        ]
                    ),
                    "usage": {"total_tokens": 10},
                },
                {
                    "message": assistant_message(content="Apple is trading at USD 305.93."),
                    "usage": {"total_tokens": 5},
                },
            ]
        )

        result = asyncio.run(
            run_agent(
                chat,
                "system prompt",
                "What is Apple's current price?",
                [FETCH_STOCK_DATA_SCHEMA],
                TOOL_REGISTRY,
            )
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("305.93", result["answer"])

    def test_an_unknown_tool_name_runs_nothing_and_the_transcript_gets_an_error(self):
        captured_tool_messages = []

        chat_calls = [
            {
                "message": assistant_message(
                    tool_calls=[
                        {
                            "id": "call_1",
                            "function": {"name": "delete_database", "arguments": {}},
                        }
                    ]
                ),
                "usage": {},
            },
            {"message": assistant_message(content="done"), "usage": {}},
        ]

        async def chat(messages, tool_schemas):
            response = chat_calls.pop(0)
            if messages and messages[-1]["role"] == "tool":
                captured_tool_messages.append(messages[-1])
            return response

        result = asyncio.run(
            run_agent(chat, "system", "hello", [], TOOL_REGISTRY)
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(captured_tool_messages), 1)
        self.assertIn("unknown tool", captured_tool_messages[0]["content"])

    def test_one_assistant_message_with_two_tool_calls_keeps_two_matching_call_ids(self):
        chat = scripted_chat(
            [
                {
                    "message": assistant_message(
                        tool_calls=[
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "fetch_stock_data",
                                    "arguments": {"ticker": "AAPL"},
                                },
                            },
                            {
                                "id": "call_2",
                                "function": {
                                    "name": "fetch_stock_data",
                                    "arguments": {"ticker": "MSFT"},
                                },
                            },
                        ]
                    ),
                    "usage": {},
                },
                {"message": assistant_message(content="both fetched"), "usage": {}},
            ]
        )

        recorded_history = []
        original_chat = chat

        async def recording_chat(messages, tool_schemas):
            recorded_history.append(messages)
            return await original_chat(messages, tool_schemas)

        asyncio.run(
            run_agent(recording_chat, "system", "compare AAPL and MSFT", [], TOOL_REGISTRY)
        )

        final_messages = recorded_history[-1]
        tool_messages = [m for m in final_messages if m.get("role") == "tool"]
        self.assertEqual(
            {m["tool_call_id"] for m in tool_messages}, {"call_1", "call_2"}
        )

    def test_ordinary_content_with_no_tool_calls_is_terminal(self):
        chat = scripted_chat(
            [{"message": assistant_message(content="just an answer"), "usage": {}}]
        )

        result = asyncio.run(run_agent(chat, "system", "hi", [], TOOL_REGISTRY))

        self.assertEqual(result["status"], "success")

    def test_the_harness_stops_exactly_at_max_turns_when_every_response_calls_a_tool(self):
        def always_calls_a_tool(messages, tool_schemas):
            return {
                "message": assistant_message(
                    tool_calls=[
                        {
                            "id": "call_x",
                            "function": {
                                "name": "fetch_stock_data",
                                "arguments": {"ticker": "AAPL"},
                            },
                        }
                    ]
                ),
                "usage": {},
            }

        call_count = 0

        async def chat(messages, tool_schemas):
            nonlocal call_count
            call_count += 1
            return always_calls_a_tool(messages, tool_schemas)

        result = asyncio.run(
            run_agent(chat, "system", "hi", [], TOOL_REGISTRY, max_turns=3)
        )

        self.assertEqual(result["status"], "max_turns_exceeded")
        self.assertEqual(call_count, 3)
        self.assertEqual(len(result["partial_results"]), 3)

    def test_usage_across_three_model_calls_is_summed(self):
        chat = scripted_chat(
            [
                {
                    "message": assistant_message(
                        tool_calls=[
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "fetch_stock_data",
                                    "arguments": {"ticker": "AAPL"},
                                },
                            }
                        ]
                    ),
                    "usage": {"total_tokens": 10},
                },
                {
                    "message": assistant_message(
                        tool_calls=[
                            {
                                "id": "call_2",
                                "function": {
                                    "name": "fetch_stock_data",
                                    "arguments": {"ticker": "MSFT"},
                                },
                            }
                        ]
                    ),
                    "usage": {"total_tokens": 15},
                },
                {
                    "message": assistant_message(content="done"),
                    "usage": {"total_tokens": 7},
                },
            ]
        )

        result = asyncio.run(run_agent(chat, "system", "hi", [], TOOL_REGISTRY))

        self.assertEqual(result["usage"]["total_tokens"], 32)


if __name__ == "__main__":
    unittest.main()
