"""
data_loader.py — Market data abstraction layer.

Provider priority: OpenBB → yfinance fallback.
Switch provider via DATA_PROVIDER env var.

All public functions are cached with st.cache_data.
The cache is NOT the source of truth for holdings — it only avoids
hammering APIs on every Streamlit rerun.
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Optional
import streamlit as st

from config import DATA_PROVIDER, PRICE_CACHE_TTL, HISTORY_CACHE_TTL


# ── Provider detection ────────────────────────────────────────────────────────

def _use_openbb() -> bool:
    if DATA_PROVIDER != "openbb":
        return False
    try:
        from openbb import obb  # noqa: F401
        return True
    except ImportError:
        return False


# ── Spot price (single ticker) ────────────────────────────────────────────────

@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def get_spot_price(ticker: str) -> Optional[float]:
    """Return latest close price. Returns None on failure."""
    if ticker.upper() == "CASH":
        return 1.0

    if _use_openbb():
        return _openbb_spot(ticker)
    return _yfinance_spot(ticker)


def _openbb_spot(ticker: str) -> Optional[float]:
    try:
        from openbb import obb
        result = obb.equity.price.quote(symbol=ticker, provider="yfinance")
        return float(result.results[0].last_price)
    except Exception as e:
        st.warning(f"OpenBB spot price failed for {ticker}: {e}")
        return _yfinance_spot(ticker)


def _yfinance_spot(ticker: str) -> Optional[float]:
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as e:
        st.warning(f"yfinance spot price failed for {ticker}: {e}")
        return None


# ── Historical OHLCV ──────────────────────────────────────────────────────────

@st.cache_data(ttl=HISTORY_CACHE_TTL, show_spinner=False)
def get_price_history(
    ticker: str,
    start: str,
    end: Optional[str] = None,
) -> pd.DataFrame:
    """
    Return a DataFrame with columns [date, close] for the given ticker.
    Returns an empty DataFrame on failure.
    """
    if ticker.upper() == "CASH":
        # Cash is always priced at 1.0
        idx = pd.date_range(start=start, end=end or date.today().isoformat(), freq="B")
        return pd.DataFrame({"date": idx.date, "close": 1.0})

    if _use_openbb():
        return _openbb_history(ticker, start, end)
    return _yfinance_history(ticker, start, end)


def _openbb_history(ticker: str, start: str, end: Optional[str]) -> pd.DataFrame:
    try:
        from openbb import obb
        end = end or date.today().isoformat()
        result = obb.equity.price.historical(
            symbol=ticker, start_date=start, end_date=end, provider="yfinance"
        )
        df = result.to_df().reset_index()
        df = df.rename(columns={"date": "date", "close": "close"})
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df[["date", "close"]].dropna()
    except Exception as e:
        st.warning(f"OpenBB history failed for {ticker}: {e}. Falling back to yfinance.")
        return _yfinance_history(ticker, start, end)


def _yfinance_history(ticker: str, start: str, end: Optional[str]) -> pd.DataFrame:
    try:
        import yfinance as yf
        end = end or date.today().isoformat()
        t = yf.Ticker(ticker)
        hist = t.history(start=start, end=end)
        if hist.empty:
            return pd.DataFrame(columns=["date", "close"])
        hist = hist.reset_index()
        hist["date"] = pd.to_datetime(hist["Date"]).dt.date
        hist["close"] = hist["Close"].astype(float)
        return hist[["date", "close"]].dropna()
    except Exception as e:
        st.warning(f"yfinance history failed for {ticker}: {e}")
        return pd.DataFrame(columns=["date", "close"])


# ── FX: convert to EUR ────────────────────────────────────────────────────────

@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def get_fx_rate(from_currency: str, to_currency: str = "EUR") -> float:
    """
    Return the latest FX rate (from_currency → to_currency).
    Returns 1.0 if currencies are equal or on failure.
    """
    if from_currency.upper() == to_currency.upper():
        return 1.0
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    rate = _yfinance_spot(pair)
    return rate if rate else 1.0


@st.cache_data(ttl=HISTORY_CACHE_TTL, show_spinner=False)
def get_fx_history(
    from_currency: str,
    to_currency: str = "EUR",
    start: str = "2020-01-01",
    end: Optional[str] = None,
) -> pd.DataFrame:
    if from_currency.upper() == to_currency.upper():
        idx = pd.date_range(start=start, end=end or date.today().isoformat(), freq="B")
        return pd.DataFrame({"date": idx.date, "close": 1.0})
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    return _yfinance_history(pair, start, end)
