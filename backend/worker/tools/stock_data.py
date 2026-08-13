"""
Direct API call — no MCP, no LLM decision involved. Our own code always calls
this deterministically for any ticker request, so there's no benefit to routing
it through a tool-calling layer (see tutor/references/concepts.md).
"""
import yfinance as yf


def fetch_stock_data(ticker: str, market: str) -> dict:
    if market == "US":
        symbols_to_try = [ticker]
    elif market == "India":
        # NSE first, then BSE — picking the right *exchange within* the chosen
        # region is fine; mixing up US vs. India is what we're avoiding.
        symbols_to_try = [f"{ticker}.NS", f"{ticker}.BO"]
    else:
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
