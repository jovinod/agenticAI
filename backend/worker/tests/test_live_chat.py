import asyncio
import os
import time
import unittest


@unittest.skipUnless(
    os.environ.get("APIM_BASE_URL") and os.environ.get("APIM_SUBSCRIPTION_KEY"),
    "no APIM_BASE_URL / APIM_SUBSCRIPTION_KEY exported -- skipping the live call",
)
class TestLiveChat(unittest.TestCase):
    def test_a_real_chat_call_returns_a_normalized_message_and_usage(self) -> None:
        from model_client import chat

        result = asyncio.run(
            chat(
                [{"role": "user", "content": "Say hello in exactly three words."}],
                [],
            )
        )

        self.assertEqual(result["message"]["role"], "assistant")
        self.assertIsInstance(result["message"]["content"], str)
        self.assertGreater(result["usage"]["total_tokens"], 0)

    def test_the_model_can_request_the_registered_tool(self) -> None:
        from model_client import chat

        tool_schema = {
            "type": "function",
            "function": {
                "name": "fetch_stock_data",
                "description": "Fetch current price and basic fundamentals for a US-listed ticker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                    },
                    "required": ["ticker"],
                },
            },
        }

        result = asyncio.run(
            chat(
                [
                    {
                        "role": "system",
                        "content": "You must use the fetch_stock_data tool to answer any price question. Never answer from memory.",
                    },
                    {
                        "role": "user",
                        "content": "What is Apple's (ticker AAPL) current price?",
                    },
                ],
                [tool_schema],
            )
        )

        message = result["message"]
        self.assertTrue(message.get("tool_calls"))
        call = message["tool_calls"][0]
        self.assertEqual(call["function"]["name"], "fetch_stock_data")
        self.assertIsInstance(call["function"]["arguments"], dict)
        self.assertEqual(call["function"]["arguments"]["ticker"], "AAPL")

    def test_two_real_calls_via_gather_take_about_one_call_not_the_sum(self) -> None:
        from model_client import chat

        async def one_call():
            return await chat(
                [{"role": "user", "content": "Reply with the single word: ok"}], []
            )

        async def run_both():
            start = time.monotonic()
            await asyncio.gather(one_call(), one_call())
            return time.monotonic() - start

        async def run_one():
            start = time.monotonic()
            await one_call()
            return time.monotonic() - start

        single = asyncio.run(run_one())
        both = asyncio.run(run_both())

        self.assertLess(both, single * 1.8)


if __name__ == "__main__":
    unittest.main()
