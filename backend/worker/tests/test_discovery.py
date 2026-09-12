import tempfile
import unittest
from pathlib import Path

from discovery import discover_skills


class TestDiscovery(unittest.TestCase):
    def test_a_reviewed_skill_folder_appears_in_deterministic_order(self) -> None:
        tool_schemas, tool_registry = discover_skills()

        self.assertEqual([s["function"]["name"] for s in tool_schemas], [
            "assess_news_sentiment"
        ])
        self.assertIn("assess_news_sentiment", tool_registry)
        instructions = tool_registry["assess_news_sentiment"]()
        self.assertIn("Fraud allegations", instructions)

    def test_a_folder_without_skill_md_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skills_dir = Path(tmp)
            (skills_dir / "not_a_skill").mkdir()
            (skills_dir / "not_a_skill" / "notes.txt").write_text("just a file")

            tool_schemas, tool_registry = discover_skills(skills_dir)

            self.assertEqual(tool_schemas, [])
            self.assertEqual(tool_registry, {})


if __name__ == "__main__":
    unittest.main()
