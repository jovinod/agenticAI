"""
Extended fundamentals for the Decision agent -- deliberately separate from
stock_data.py's fetch_stock_data(), which stays exactly as small as
Fundamentals/Technical/Risk need. This fetches the multi-year history and
balance-sheet/cash-flow figures those agents never needed: annual EPS,
annual free cash flow, ROE, and debt-to-equity.

Market-agnostic on purpose, unlike buynobuy's own version of this (which
hardcodes India's April-March fiscal year): yfinance reports each company's
OWN fiscal-year-end dates directly, so this uses those instead of assuming
a calendar. Works the same way for a US ticker (fiscal year ending
September) or an Indian one (fiscal year ending March) with no special-casing.
"""
import yfinance as yf
from tools.stock_data import resolve_symbol_candidates


def fetch_extended_fundamentals(ticker: str, market: str) -> dict:
    symbols_to_try = resolve_symbol_candidates(ticker, market)
    if not symbols_to_try:
        return {"ticker": ticker, "error": f"unknown market: {market}"}

    for symbol in symbols_to_try:
        t = yf.Ticker(symbol)
        info = t.info
        if not (info.get("currentPrice") or info.get("regularMarketPrice")):
            continue

        income_stmt = t.income_stmt
        cashflow = t.cashflow

        eps_history = _annual_series(income_stmt, "Diluted EPS")
        fcf_history = _annual_series(cashflow, "Free Cash Flow")
        monthly_prices = t.history(period="10y", interval="1mo")["Close"]
        if monthly_prices.index.tz is not None:
            monthly_prices.index = monthly_prices.index.tz_localize(None)

        return {
            "ticker": ticker,
            "resolved_symbol": symbol,
            "market": market,
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "return_on_equity": info.get("returnOnEquity"),
            # yfinance's own units -- a ratio expressed as e.g. 78.4, not 0.784.
            # Thresholds below are written in these same units deliberately,
            # to avoid a silent unit-conversion bug.
            "debt_to_equity": info.get("debtToEquity"),
            "eps_history": eps_history,       # {"2025-09-30": 7.46, ...}, most recent first
            "fcf_history": fcf_history,       # {"2025-09-30": 98767000000.0, ...}
            "monthly_prices": monthly_prices, # pandas Series, tz-naive, for compute_intrinsic_value
        }

    exchanges = "US markets" if market == "US" else "NSE or BSE"
    return {"ticker": ticker, "error": f"{ticker} not found on {exchanges}"}


def _annual_series(df, row_label: str) -> dict:
    """Pull one row out of yfinance's income_stmt/cashflow DataFrame into a
    plain {date_str: float} dict, most-recent-first, skipping NaNs."""
    if row_label not in df.index:
        return {}
    row = df.loc[row_label]
    return {
        str(date.date()): float(value)
        for date, value in row.items()
        if value == value  # NaN != NaN -- the standard float NaN check, no import needed
    }
