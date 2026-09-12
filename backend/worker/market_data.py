from typing import Any

import yfinance


def fetch_stock_data(ticker: str) -> dict[str, Any]:
    """Fetch structured market data for one US-listed ticker.

    Returns only the fields the application understands -- never a raw
    provider object. yfinance is unofficial and has no service-level
    agreement, so "ticker not found" and "provider unavailable" are kept
    distinct.
    """
    try:
        info = yfinance.Ticker(ticker).info
    except Exception as exc:  # provider unavailable
        return {"ticker": ticker, "error": f"provider unavailable: {exc}"}

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if not price:
        return {"ticker": ticker, "error": "ticker not found"}

    return {
        "ticker": ticker,
        "price": price,
        "currency": info.get("currency"),
        "pe_ratio": info.get("trailingPE"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
    }
