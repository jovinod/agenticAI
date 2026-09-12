import unittest

from risk_rules import flag_risk_factors


class TestFlagRiskFactors(unittest.TestCase):
    def test_price_near_the_52_week_low_is_flagged(self) -> None:
        flags = flag_risk_factors(
            {"price": 105, "fifty_two_week_low": 100, "fifty_two_week_high": 200}
        )
        self.assertIn("near_52_week_low", flags)

    def test_negative_pe_ratio_is_flagged_unprofitable(self) -> None:
        flags = flag_risk_factors({"pe_ratio": -5})
        self.assertIn("unprofitable", flags)

    def test_high_pe_ratio_is_flagged(self) -> None:
        flags = flag_risk_factors({"pe_ratio": 50})
        self.assertIn("high_pe_ratio", flags)

    def test_missing_pe_ratio_raises_no_exception(self) -> None:
        flags = flag_risk_factors({"price": 100})
        self.assertEqual(flags, [])

    def test_equal_high_and_low_does_not_divide_by_zero(self) -> None:
        flags = flag_risk_factors(
            {"price": 100, "fifty_two_week_low": 100, "fifty_two_week_high": 100}
        )
        self.assertEqual(flags, [])


if __name__ == "__main__":
    unittest.main()
