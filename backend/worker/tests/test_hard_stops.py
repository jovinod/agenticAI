import unittest

from hard_stops import check_hard_stop_rules


class TestCheckHardStopRules(unittest.TestCase):
    def test_roe_stop_triggers_exactly_at_the_boundary(self) -> None:
        just_below = check_hard_stop_rules({"roe": 0.0799})
        at_boundary = check_hard_stop_rules({"roe": 0.08})
        just_above = check_hard_stop_rules({"roe": 0.0801})

        self.assertTrue(any("equity" in s for s in just_below))
        self.assertFalse(any("equity" in s for s in at_boundary))
        self.assertFalse(any("equity" in s for s in just_above))

    def test_debt_to_equity_stop_triggers_exactly_at_the_boundary(self) -> None:
        at_boundary = check_hard_stop_rules({"debt_to_equity": 200})
        just_above = check_hard_stop_rules({"debt_to_equity": 200.01})

        self.assertFalse(any("leverage" in s for s in at_boundary))
        self.assertTrue(any("leverage" in s for s in just_above))

    def test_one_negative_recent_year_of_free_cash_flow_is_enough(self) -> None:
        stops = check_hard_stop_rules({"free_cash_flow_history": [-1.0, 5.0]})
        self.assertTrue(any("cash flow" in s for s in stops))

    def test_missing_data_does_not_trigger_a_stop(self) -> None:
        stops = check_hard_stop_rules({})
        self.assertEqual(stops, [])


if __name__ == "__main__":
    unittest.main()
