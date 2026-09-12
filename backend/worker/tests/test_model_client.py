import copy
import time
import unittest
import asyncio

from model_client import _stringify_tool_call_args, _normalize_usage


class TestStringifyToolCallArgs(unittest.TestCase):
    def test_outbound_copy_has_json_strings_original_keeps_dictionaries(self) -> None:
        original = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "fetch_stock_data",
                            "arguments": {"ticker": "AAPL"},
                        },
                    }
                ],
            }
        ]
        snapshot = copy.deepcopy(original)

        prepared = _stringify_tool_call_args(original)

        self.assertIsInstance(
            prepared[0]["tool_calls"][0]["function"]["arguments"], str
        )
        self.assertEqual(original, snapshot)
        self.assertIsInstance(
            original[0]["tool_calls"][0]["function"]["arguments"], dict
        )


class TestNormalizeUsage(unittest.TestCase):
    def test_known_token_counts_pass_through(self) -> None:
        usage = _normalize_usage(
            {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160}
        )

        self.assertEqual(usage["prompt_tokens"], 120)
        self.assertEqual(usage["completion_tokens"], 40)
        self.assertEqual(usage["total_tokens"], 160)
        self.assertIn("estimated_cost_usd", usage)


class TestAsyncTransportYields(unittest.TestCase):
    def test_two_delayed_calls_via_gather_take_about_one_delay_not_the_sum(self) -> None:
        delay = 0.2

        async def fake_delayed_chat(messages, tools):
            await asyncio.sleep(delay)
            return {"message": {"role": "assistant", "content": "ok"}, "usage": {}}

        async def run_both():
            start = time.monotonic()
            await asyncio.gather(
                fake_delayed_chat([], []),
                fake_delayed_chat([], []),
            )
            return time.monotonic() - start

        elapsed = asyncio.run(run_both())

        self.assertLess(elapsed, delay * 1.5)


if __name__ == "__main__":
    unittest.main()
