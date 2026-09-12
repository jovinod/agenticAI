import unittest

from valuation import compute_intrinsic_value

EPS_HISTORY = {"2022": 5.0, "2023": 6.0, "2024": 7.0}
MONTHLY_PRICES = {
    "2022-01": 90, "2022-06": 100, "2022-12": 110,
    "2023-01": 110, "2023-06": 120, "2023-12": 130,
    "2024-01": 130, "2024-06": 140, "2024-12": 150,
}


class TestComputeIntrinsicValue(unittest.TestCase):
    def test_calling_it_twice_with_the_same_captured_dataset_gives_the_same_result(
        self,
    ) -> None:
        first = compute_intrinsic_value(EPS_HISTORY, MONTHLY_PRICES, 120)
        second = compute_intrinsic_value(EPS_HISTORY, MONTHLY_PRICES, 120)

        self.assertEqual(first, second)
        self.assertIsNotNone(first["intrinsic_price"])

    def test_a_low_price_relative_to_intrinsic_value_is_a_buy(self) -> None:
        result = compute_intrinsic_value(EPS_HISTORY, MONTHLY_PRICES, 1)
        self.assertEqual(result["label"], "BUY")

    def test_a_high_price_relative_to_intrinsic_value_is_overpriced(self) -> None:
        result = compute_intrinsic_value(EPS_HISTORY, MONTHLY_PRICES, 10000)
        self.assertEqual(result["label"], "OVERPRICED")

    def test_missing_data_returns_unknown_without_raising(self) -> None:
        result = compute_intrinsic_value({}, None, None)
        self.assertEqual(result["label"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
