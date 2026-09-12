import json
import unittest

from decision import make_decision

LOW_ROE_DATA = {"roe": 0.02}


class TestMakeDecision(unittest.TestCase):
    def test_malformed_json_falls_back_to_hold_with_no_score(self) -> None:
        decision = make_decision("this is not json", {})

        self.assertEqual(decision["recommendation"], "HOLD")
        self.assertIsNone(decision["overall_score"])
        self.assertIn("synthesis error", decision["summary"])

    def test_a_buy_recommendation_survives_alongside_a_triggered_hard_stop(self) -> None:
        # Documented gap, not a bug this test papers over: current code
        # does not enforce that a hard stop rules out BUY.
        raw = json.dumps(
            {"recommendation": "BUY", "overall_score": 8.5, "summary": "Looks strong."}
        )

        decision = make_decision(raw, LOW_ROE_DATA)

        self.assertEqual(decision["recommendation"], "BUY")
        self.assertTrue(decision["hard_stops_triggered"])

    def test_deterministic_fields_always_come_from_python_not_the_model(self) -> None:
        raw = json.dumps(
            {
                "recommendation": "WAIT",
                "overall_score": 5,
                "summary": "ok",
                # A model attempting to supply its own valuation is ignored.
                "intrinsic_value": {"label": "BUY"},
                "hard_stops_triggered": [],
            }
        )

        decision = make_decision(raw, LOW_ROE_DATA)

        self.assertTrue(decision["hard_stops_triggered"])
        self.assertEqual(decision["intrinsic_value"]["label"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
