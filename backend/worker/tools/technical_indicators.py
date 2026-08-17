"""
Direct API call — same category as tools/stock_data.py's fetch_stock_data,
no MCP, no LLM decision involved. Computes real technical indicators from
yfinance's historical price data (a time series, not the snapshot
fetch_stock_data uses) -- a genuinely different data shape, hence its own tool.
"""
import yfinance as yf
from tools.stock_data import resolve_symbol_candidates


def _simple_moving_average(closes, window: int):
    if len(closes) < window:
        return None
    value = closes.rolling(window=window).mean().iloc[-1]
    return round(value, 2) if value == value else None  # NaN check


def _rsi(closes, period: int = 14):
    """Relative Strength Index -- 0-100, how aggressively a stock has been
    bought vs. sold over `period` days. >70 is commonly read as
    "possibly overbought," <30 as "possibly oversold." Not a prediction,
    just a measure of recent momentum."""
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)
    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()
    last_avg_loss = avg_loss.iloc[-1]
    if last_avg_loss == 0:
        return 100.0  # no losses in the window -- maximally "overbought" by definition
    rs = avg_gain.iloc[-1] / last_avg_loss
    value = 100 - (100 / (1 + rs))
    return round(value, 2) if value == value else None


def fetch_technical_indicators(ticker: str, market: str) -> dict:
    symbols_to_try = resolve_symbol_candidates(ticker, market)
    if not symbols_to_try:
        return {"ticker": ticker, "error": f"unknown market: {market}"}

    for symbol in symbols_to_try:
        history = yf.Ticker(symbol).history(period="6mo")
        if not history.empty:
            closes = history["Close"]
            return {
                "ticker": ticker,
                "resolved_symbol": symbol,
                "market": market,
                "current_price": round(closes.iloc[-1], 2),
                "sma_20": _simple_moving_average(closes, 20),
                "sma_50": _simple_moving_average(closes, 50),
                "rsi_14": _rsi(closes, 14),
            }

    exchanges = "US markets" if market == "US" else "NSE or BSE"
    return {"ticker": ticker, "error": f"{ticker} not found on {exchanges}"}
