import os
import unittest
import uuid


@unittest.skipUnless(
    os.environ.get("DATABASE_URL"), "no DATABASE_URL exported -- skipping the live call"
)
class TestProfileStore(unittest.TestCase):
    def test_researching_the_same_ticker_and_market_twice_gives_a_count_of_two(
        self,
    ) -> None:
        import profile_store

        ticker = f"TST{uuid.uuid4().hex[:6].upper()}"

        first = profile_store.record_research(ticker, "US", sector="Technology")
        second = profile_store.record_research(ticker, "US")

        self.assertEqual(second.research_count, 2)
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.sector, "Technology")

    def test_the_same_ticker_in_a_different_market_is_a_separate_identity(
        self,
    ) -> None:
        import profile_store

        ticker = f"TST{uuid.uuid4().hex[:6].upper()}"

        us_profile = profile_store.record_research(ticker, "US")
        india_profile = profile_store.record_research(ticker, "India")

        self.assertNotEqual(us_profile.id, india_profile.id)
        self.assertEqual(us_profile.research_count, 1)
        self.assertEqual(india_profile.research_count, 1)


if __name__ == "__main__":
    unittest.main()
