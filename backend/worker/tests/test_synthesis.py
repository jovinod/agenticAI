import asyncio
import unittest

from synthesis import run_synthesis


class TestRunSynthesis(unittest.TestCase):
    def test_mandatory_acquisition_sends_no_tool_schemas(self) -> None:
        captured_tools = []

        async def chat(messages, tools):
            captured_tools.append(tools)
            return {
                "message": {"role": "assistant", "content": "AAPL looks fine."},
                "usage": {"total_tokens": 42},
            }

        result = asyncio.run(
            run_synthesis(chat, "You are a fundamentals analyst.", "Summarize AAPL.")
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(captured_tools, [[]])


if __name__ == "__main__":
    unittest.main()
