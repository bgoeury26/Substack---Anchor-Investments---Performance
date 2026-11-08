"""
data_loader.py — Market data abstraction layer.

Provider priority: OpenBB → yfinance fallback. Switch via DATA_PROVIDER.

Yahoo Finance has no supported public API — yfinance talks to an internal,
unofficial endpoint that rate-limits hard under repeated calls (this is the
exact failure the original app hit live: "Too Many Requests"). Two things
here specifically defend against that:

1. Batching — get_spot_prices() fetches every ticker the portfolio holds in
   ONE network call via yf.download(), instead of one call per ticker. Most
   rate-limit trips come from N sequential single-ticker calls on every
   rerun; this cuts that to 1.
2. Fallback-to-last-known-good — every successful fetch is written to the
   price_cache table (db.py). If a live fetch then fails or gets rate
   limited, callers get the last cached price back (flagged as stale)
   instead of a blank "None" cell, so the dashboard degrades gracefully
   instead of breaking.
"""

import time
import random
from datetime import date, timedelta
from typing import Optional, Iterable

import pandas as pd
import numpy as np
import streamlit as st

from config import DATA_PROVIDER, PRICE_CACHE_TTL, HISTORY_CACHE_TTL
import db


# ── Provider detection ────────────────────────────────────────────────────────

def _use_openbb() -> bool:
    if DATA_PROVIDER != "openbb":
        return False
    try:
        from openbb import obb  # noqa: F401
        return True
    except ImportError:
        return False


def _retry(fn, attempts: int = 3, base_delay: float = 0.6):
    """Retry a zero-arg callable with exponential backoff + jitter.
    Returns (result, error) — error is None on success."""
    last_err = None
    for i in range(attempts):
        try:
            return fn(), None
        except Exception as e:  # noqa: BLE001
            last_err = e
            if i < attempts - 1:
                time.sleep(base_delay * (2 ** i) + random.uniform(0, 0.3))
    return None, last_err


# ── Spot prices (batched) ───────────────────────────────────────────────────

@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def get_spot_prices(tickers: tuple) -> dict:
    """
    Return {ticker: {"price": float|None, "stale": bool, "fetched_at": str|None}}
    for every ticker in `tickers`. CASH is always 1.0. One batched network
    call handles every non-cash ticker; failures fall back to the cache.
    """
    tickers = tuple(sorted(set(t.upper() for t in tickers if t)))
    out = {}
    real_tickers = [t for t in tickers if t != "CASH"]

    fresh = {}
    if real_tickers:
        if _use_openbb():
            fresh = _openbb_spot_batch(real_tickers)
        else:
            fresh = _yfinance_spot_batch(real_tickers)

    for t in tickers:
        if t == "CASH":
            out[t] = {"price": 1.0, "stale": False, "fetched_at": None}
            continue
        price = fresh.get(t)
        if price is not None and price > 0:
            db.set_cached_price(t, price)
            out[t] = {"price": price, "stale": False, "fetched_at": "live"}
        else:
            cached = db.get_cached_price(t)
            if cached and cached["price"]:
                out[t] = {"price": cached["price"], "stale": True, "fetched_at": cached["fetched_at"]}
            else:
                out[t] = {"price": None, "stale": True, "fetched_at": None}
    return out


def get_spot_price(ticker: str) -> Optional[float]:
    """Convenience single-ticker wrapper around get_spot_prices()."""
    result = get_spot_prices((ticker,))
    return result.get(ticker.upper(), {}).get("price")


def _yfinance_spot_batch(tickers: list) -> dict:
    def _fetch():
        import yfinance as yf
        data = yf.download(
            tickers=tickers, period="5d", group_by="ticker",
            progress=False, threads=True, auto_adjust=False,
        )
        result = {}
        if len(tickers) == 1:
            t = tickers[0]
            if not data.empty and "Close" in data:
                closes = data["Close"].dropna()
                if not closes.empty:
                    result[t] = float(closes.iloc[-1])
        else:
            for t in tickers:
                try:
                    closes = data[t]["Close"].dropna()
                    if not closes.empty:
                        result[t] = float(closes.iloc[-1])
                except Exception:
                    continue
        return result

    result, err = _retry(_fetch)
    if err is not None:
        st.session_state.setdefault("_price_warnings", []).append(
            f"Live price fetch failed ({err.__class__.__name__}); showing last known prices where available."
        )
        return {}
    return result or {}


def _openbb_spot_batch(tickers: list) -> dict:
    try:
        from openbb import obb
        out = {}
        for t in tickers:
            try:
                res = obb.equity.price.quote(symbol=t, provider="yfinance")
                out[t] = float(res.results[0].last_price)
            except Exception:
                continue
        if out:
            return out
    except Exception:
        pass
    return _yfinance_spot_batch(tickers)


# ── Historical OHLCV ──────────────────────────────────────────────────────────

@st.cache_data(ttl=HISTORY_CACHE_TTL, show_spinner=False)
def get_price_history(ticker: str, start: str, end: Optional[str] = None) -> pd.DataFrame:
    """Return DataFrame [date, close] for `ticker`. Empty DataFrame on failure."""
    ticker = ticker.upper()
    if ticker == "CASH":
        idx = pd.date_range(start=start, end=end or date.today().isoformat(), freq="B")
        return pd.DataFrame({"date": idx.date, "close": 1.0})

    if _use_openbb():
        df = _openbb_history(ticker, start, end)
        if not df.empty:
            return df
    return _yfinance_history(ticker, start, end)


def _openbb_history(ticker: str, start: str, end: Optional[str]) -> pd.DataFrame:
    try:
        from openbb import obb
        end = end or date.today().isoformat()
        result = obb.equity.price.historical(
            symbol=ticker, start_date=start, end_date=end, provider="yfinance"
        )
        df = result.to_df().reset_index()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df[["date", "close"]].dropna()
    except Exception:
        return pd.DataFrame(columns=["date", "close"])


def _yfinance_history(ticker: str, start: str, end: Optional[str]) -> pd.DataFrame:
    def _fetch():
        import yfinance as yf
        end_ = end or date.today().isoformat()
        t = yf.Ticker(ticker)
        hist = t.history(start=start, end=end_)
        if hist.empty:
            return pd.DataFrame(columns=["date", "close"])
        hist = hist.reset_index()
        hist["date"] = pd.to_datetime(hist["Date"]).dt.date
        hist["close"] = hist["Close"].astype(float)
        return hist[["date", "close"]].dropna()

    result, err = _retry(_fetch, attempts=2)
    if err is not None or result is None:
        return pd.DataFrame(columns=["date", "close"])
    return result


# ── FX: convert to EUR ────────────────────────────────────────────────────────

@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def get_fx_rate(from_currency: str, to_currency: str = "EUR") -> float:
    if from_currency.upper() == to_currency.upper():
        return 1.0
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    prices = _yfinance_spot_batch([pair])
    rate = prices.get(pair)
    if rate:
        return rate
    cached = db.get_cached_price(pair)
    return cached["price"] if cached and cached["price"] else 1.0


@st.cache_data(ttl=HISTORY_CACHE_TTL, show_spinner=False)
def get_fx_history(from_currency: str, to_currency: str = "EUR",
                    start: str = "2020-01-01", end: Optional[str] = None) -> pd.DataFrame:
    if from_currency.upper() == to_currency.upper():
        idx = pd.date_range(start=start, end=end or date.today().isoformat(), freq="B")
        return pd.DataFrame({"date": idx.date, "close": 1.0})
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    return _yfinance_history(pair, start, end)


def drain_price_warnings() -> list:
    """Pop and return any warnings accumulated during this rerun's fetches."""
    warnings = st.session_state.get("_price_warnings", [])
    st.session_state["_price_warnings"] = []
    return warnings
