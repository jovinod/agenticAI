from typing import Any

import yfinance


def fetch_extended_data(ticker: str) -> dict[str, Any]:
    """Real fundamentals beyond price/P/E, for the hard-stop rules and
    intrinsic-value calculation: return on equity, debt-to-equity, free
    cash flow history, EPS history, and monthly prices. Any missing
    piece stays None/empty rather than failing the whole fetch -- the
    downstream rules already treat missing data as "unknown," not
    "failed."
    """
    try:
        stock = yfinance.Ticker(ticker)
        info = stock.info
    except Exception:
        return {
            "roe": None,
            "debt_to_equity": None,
            "free_cash_flow_history": [],
            "eps_history": {},
            "monthly_prices": {},
            "current_price": None,
        }

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    roe = info.get("returnOnEquity")
    debt_to_equity = info.get("debtToEquity")

    free_cash_flow_history: list[float] = []
    try:
        cashflow = stock.cashflow
        if cashflow is not None and "Free Cash Flow" in cashflow.index:
            free_cash_flow_history = [
                float(v) for v in cashflow.loc["Free Cash Flow"].dropna().tolist()
            ]
    except Exception:
        pass

    eps_history: dict[str, float] = {}
    try:
        income_stmt = stock.income_stmt
        eps_row = "Diluted EPS" if "Diluted EPS" in income_stmt.index else None
        if eps_row:
            for column, value in income_stmt.loc[eps_row].items():
                if value == value:  # filters NaN
                    eps_history[str(column.year)] = float(value)
    except Exception:
        pass

    monthly_prices: dict[str, float] = {}
    try:
        history = stock.history(period="5y", interval="1mo")
        for index, row in history.iterrows():
            monthly_prices[f"{index.year}-{index.month:02d}"] = float(row["Close"])
    except Exception:
        pass

    return {
        "roe": roe,
        "debt_to_equity": debt_to_equity,
        "free_cash_flow_history": free_cash_flow_history,
        "eps_history": eps_history,
        "monthly_prices": monthly_prices,
        "current_price": current_price,
    }
