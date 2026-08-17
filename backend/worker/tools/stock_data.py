"""
Direct API call — no MCP, no LLM decision involved. Our own code always calls
this deterministically for any ticker request, so there's no benefit to routing
it through a tool-calling layer (see book/chapter-03-mcp-and-real-data.md).
"""
import yfinance as yf


def resolve_symbol_candidates(ticker: str, market: str) -> list[str]:
    """Which real exchange symbol(s) a ticker might resolve to in a given
    market -- shared by fetch_stock_data and technical_indicators.py, since
    both need the same US-vs-India resolution before calling yfinance."""
    if market == "US":
        return [ticker]
    elif market == "India":
        # NSE first, then BSE — picking the right *exchange within* the chosen
        # region is fine; mixing up US vs. India is what we're avoiding.
        return [f"{ticker}.NS", f"{ticker}.BO"]
    return []


def fetch_stock_data(ticker: str, market: str) -> dict:
    symbols_to_try = resolve_symbol_candidates(ticker, market)
    if not symbols_to_try:
        return {"ticker": ticker, "error": f"unknown market: {market}"}

    for symbol in symbols_to_try:
        info = yf.Ticker(symbol).info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price:
            return {
                "ticker": ticker,
                "resolved_symbol": symbol,
                "market": market,
                "price": price,
                "currency": info.get("currency"),
                "pe_ratio": info.get("trailingPE"),
                "market_cap": info.get("marketCap"),
                "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            }

    exchanges = "US markets" if market == "US" else "NSE or BSE"
    return {"ticker": ticker, "error": f"{ticker} not found on {exchanges}"}
