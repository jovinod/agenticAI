import unittest
from unittest.mock import MagicMock, patch

from market_data import fetch_stock_data


class TestFetchStockData(unittest.TestCase):
    @patch("market_data.yfinance.Ticker")
    def test_returns_structured_fields_for_a_known_ticker(self, mock_ticker) -> None:
        mock_ticker.return_value.info = {
            "currentPrice": 150.0,
            "currency": "USD",
            "trailingPE": 25.0,
            "fiftyTwoWeekHigh": 200.0,
            "fiftyTwoWeekLow": 100.0,
        }

        data = fetch_stock_data("AAPL")

        self.assertEqual(data["ticker"], "AAPL")
        self.assertEqual(data["price"], 150.0)
        self.assertNotIn("error", data)

    @patch("market_data.yfinance.Ticker")
    def test_missing_price_is_reported_as_ticker_not_found(self, mock_ticker) -> None:
        mock_ticker.return_value.info = {}

        data = fetch_stock_data("NOPE")

        self.assertEqual(data["error"], "ticker not found")

    @patch("market_data.yfinance.Ticker")
    def test_provider_exception_is_kept_distinct_from_not_found(
        self, mock_ticker
    ) -> None:
        mock_ticker.side_effect = RuntimeError("network down")

        data = fetch_stock_data("AAPL")

        self.assertIn("provider unavailable", data["error"])


if __name__ == "__main__":
    unittest.main()
