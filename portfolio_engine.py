"""
portfolio_engine.py — Turns the transaction ledger into everything the UI
needs: cash balance, open positions (average-cost basis), realized and
unrealized P&L, and a daily portfolio-value time series.

This is the actual "cash management" system the dashboard is built on:

    cash_balance  = starting_cash + Σ cash_amount_eur (all non-voided tx)

    BUY  ticker qty @ price  →  cash_amount_eur = -(qty * price_eur + fees)
    SELL ticker qty @ price  →  cash_amount_eur = +(qty * price_eur - fees)
    DEPOSIT / WITHDRAWAL     →  cash_amount_eur = ± amount

Positions are tracked with the average-cost method: every BUY blends into
the position's average cost; every SELL realizes P&L against that average
and reduces the cost basis proportionally. This mirrors how a standard
brokerage / Yahoo Finance portfolio view computes cost basis and P&L.

Known simplification (flagged, not hidden): the performance time series
and Sharpe/volatility/drawdown stats are computed on total portfolio value
including the effect of deposits and withdrawals — they are NOT a
time-weighted return. A deposit will show up as a jump in portfolio value,
not as a return. For a single-owner model portfolio that rarely if ever
withdraws capital, this matches what the original app did (return vs. a
fixed base capital) and is easy to reason about. If deposits/withdrawals
become frequent, this should be upgraded to a true time-weighted return.
"""

from datetime import date, timedelta
import numpy as np
import pandas as pd

from config import STARTING_CASH
from data_loader import get_price_history, get_spot_prices, get_fx_rate, get_fx_history

EPS = 1e-6


# ── Cash ─────────────────────────────────────────────────────────────────────

def compute_cash_balance(tx_df: pd.DataFrame, starting_cash: float = None) -> float:
    starting_cash = STARTING_CASH if starting_cash is None else starting_cash
    if tx_df.empty:
        return round(starting_cash, 2)
    return round(starting_cash + tx_df["cash_amount_eur"].sum(), 2)


# ── Positions (average-cost method) ─────────────────────────────────────────

def compute_positions(tx_df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns one row per ticker ever traded:
      ticker, name, asset_class, currency, quantity, avg_cost_eur,
      cost_basis_eur, realized_pnl_eur, first_trade_date, last_trade_date
    `quantity` is 0 for fully closed positions (kept for realized P&L history).
    """
    cols = ["ticker", "name", "asset_class", "currency", "quantity",
            "avg_cost_eur", "cost_basis_eur", "realized_pnl_eur",
            "first_trade_date", "last_trade_date"]
    if tx_df.empty:
        return pd.DataFrame(columns=cols)

    trades = tx_df[tx_df["tx_type"].isin(["BUY", "SELL"])].sort_values(["tx_date", "id"])
    state = {}

    for _, r in trades.iterrows():
        t = r["ticker"]
        if t not in state:
            state[t] = {
                "ticker": t, "name": r["name"], "asset_class": r["asset_class"],
                "currency": r["currency"], "quantity": 0.0, "cost_basis_eur": 0.0,
                "realized_pnl_eur": 0.0,
                "first_trade_date": r["tx_date"], "last_trade_date": r["tx_date"],
            }
        s = state[t]
        s["name"] = r["name"] or s["name"]
        s["asset_class"] = r["asset_class"] or s["asset_class"]
        s["currency"] = r["currency"] or s["currency"]
        s["last_trade_date"] = r["tx_date"]

        qty = float(r["quantity"] or 0.0)
        px_eur = float(r["price_eur"] or 0.0)

        if r["tx_type"] == "BUY":
            s["quantity"] += qty
            s["cost_basis_eur"] += qty * px_eur
        elif r["tx_type"] == "SELL":
            sell_qty = min(qty, s["quantity"]) if s["quantity"] > 0 else 0.0
            avg_cost = (s["cost_basis_eur"] / s["quantity"]) if s["quantity"] > EPS else 0.0
            s["realized_pnl_eur"] += sell_qty * (px_eur - avg_cost)
            s["cost_basis_eur"] -= sell_qty * avg_cost
            s["quantity"] -= sell_qty
            if s["quantity"] < EPS:
                s["quantity"] = 0.0
                s["cost_basis_eur"] = 0.0

    rows = []
    for s in state.values():
        avg_cost = (s["cost_basis_eur"] / s["quantity"]) if s["quantity"] > EPS else 0.0
        rows.append({
            "ticker": s["ticker"], "name": s["name"], "asset_class": s["asset_class"],
            "currency": s["currency"], "quantity": round(s["quantity"], 6),
            "avg_cost_eur": round(avg_cost, 4),
            "cost_basis_eur": round(s["cost_basis_eur"], 2),
            "realized_pnl_eur": round(s["realized_pnl_eur"], 2),
            "first_trade_date": s["first_trade_date"], "last_trade_date": s["last_trade_date"],
        })
    return pd.DataFrame(rows, columns=cols)


def enrich_positions(positions_df: pd.DataFrame, open_only: bool = True) -> pd.DataFrame:
    """Add live spot price, market value, and unrealized P&L to positions."""
    df = positions_df.copy()
    if open_only:
        df = df[df["quantity"] > EPS].reset_index(drop=True)
    if df.empty:
        for c in ["spot_local", "spot_eur", "market_value_eur", "unrealized_pnl_eur",
                   "unrealized_pnl_pct", "price_stale"]:
            df[c] = pd.Series(dtype=float)
        return df

    tickers = tuple(df["ticker"].tolist())
    spot_map = get_spot_prices(tickers)

    spot_locals, spot_eurs, mvs, upnl, upnl_pct, stale_flags = [], [], [], [], [], []
    for _, row in df.iterrows():
        info = spot_map.get(row["ticker"], {})
        spot_local = info.get("price")
        stale = info.get("stale", False)
        if spot_local is None:
            spot_locals.append(None); spot_eurs.append(None)
            mvs.append(None); upnl.append(None); upnl_pct.append(None)
            stale_flags.append(True)
            continue
        currency = row["currency"] or "EUR"
        fx = get_fx_rate(currency, "EUR") if currency != "EUR" else 1.0
        spot_eur = spot_local * (fx or 1.0)
        mv = row["quantity"] * spot_eur
        cost = row["cost_basis_eur"]
        gain = mv - cost
        gain_pct = (gain / cost * 100) if cost > EPS else 0.0

        spot_locals.append(round(spot_local, 4))
        spot_eurs.append(round(spot_eur, 4))
        mvs.append(round(mv, 2))
        upnl.append(round(gain, 2))
        upnl_pct.append(round(gain_pct, 2))
        stale_flags.append(stale)

    df["spot_local"] = spot_locals
    df["spot_eur"] = spot_eurs
    df["market_value_eur"] = mvs
    df["unrealized_pnl_eur"] = upnl
    df["unrealized_pnl_pct"] = upnl_pct
    df["price_stale"] = stale_flags
    return df


def total_realized_pnl(tx_df: pd.DataFrame) -> float:
    positions = compute_positions(tx_df)
    if positions.empty:
        return 0.0
    return round(positions["realized_pnl_eur"].sum(), 2)


# ── Daily portfolio value time series ───────────────────────────────────────

def _daily_cash_series(tx_df: pd.DataFrame, starting_cash: float,
                        start: str, end: str) -> pd.Series:
    idx = pd.date_range(start=start, end=end, freq="D")
    s = pd.Series(0.0, index=idx)
    if not tx_df.empty:
        by_date = tx_df.groupby("tx_date")["cash_amount_eur"].sum()
        for d, v in by_date.items():
            d_ts = pd.Timestamp(d)
            if d_ts in s.index:
                s.loc[d_ts] += v
            elif d_ts < s.index[0]:
                s.iloc[0] += v  # trades before window start still affect opening cash
    return starting_cash + s.cumsum()


def _daily_qty_series(ticker_trades: pd.DataFrame, start: str, end: str) -> pd.Series:
    idx = pd.date_range(start=start, end=end, freq="D")
    s = pd.Series(0.0, index=idx)
    for _, r in ticker_trades.iterrows():
        d_ts = pd.Timestamp(r["tx_date"])
        qty = float(r["quantity"] or 0.0)
        delta = qty if r["tx_type"] == "BUY" else -qty
        if d_ts in s.index:
            s.loc[d_ts] += delta
        elif d_ts < s.index[0]:
            s.iloc[0] += delta
    return s.cumsum().clip(lower=0)


def build_daily_portfolio_value(tx_df: pd.DataFrame, starting_cash: float,
                                 inception_date: str, end_date: str = None) -> pd.DataFrame:
    """
    Returns [date, cash_eur, invested_eur, portfolio_value_eur, cumulative_return_pct]
    for every calendar day from inception to end_date (defaults to today).
    """
    end_date = end_date or date.today().isoformat()
    out_cols = ["date", "cash_eur", "invested_eur", "portfolio_value_eur", "cumulative_return_pct"]

    if pd.Timestamp(inception_date) > pd.Timestamp(end_date):
        return pd.DataFrame(columns=out_cols)

    cash_s = _daily_cash_series(tx_df, starting_cash, inception_date, end_date)

    trades = tx_df[tx_df["tx_type"].isin(["BUY", "SELL"])]
    invested_s = pd.Series(0.0, index=cash_s.index)

    for ticker, grp in trades.groupby("ticker"):
        first_date = grp["tx_date"].min()
        currency = (grp.iloc[0]["currency"] or "EUR")
        price_df = get_price_history(ticker, first_date, end_date)
        if price_df.empty:
            continue
        price_s = price_df.set_index(pd.to_datetime(price_df["date"]))["close"].astype(float)
        price_s = price_s[~price_s.index.duplicated(keep="last")].sort_index()

        if currency != "EUR":
            fx_df = get_fx_history(currency, "EUR", first_date, end_date)
            if fx_df.empty:
                continue
            fx_s = fx_df.set_index(pd.to_datetime(fx_df["date"]))["close"].astype(float)
            fx_s = fx_s[~fx_s.index.duplicated(keep="last")].sort_index()
            price_eur = price_s.reindex(cash_s.index).ffill() * fx_s.reindex(cash_s.index).ffill()
        else:
            price_eur = price_s.reindex(cash_s.index).ffill()

        price_eur = price_eur.bfill()  # cover the first day(s) before the first close is seen
        qty_s = _daily_qty_series(grp, inception_date, end_date)
        invested_s = invested_s.add(qty_s * price_eur.fillna(0), fill_value=0.0)

    portfolio_value = cash_s + invested_s
    df = pd.DataFrame({
        "date": cash_s.index,
        "cash_eur": cash_s.round(2).values,
        "invested_eur": invested_s.round(2).values,
        "portfolio_value_eur": portfolio_value.round(2).values,
    })
    df["cumulative_return_pct"] = (
        (df["portfolio_value_eur"] - starting_cash) / starting_cash * 100
    ).round(4)
    return df


def compute_analytics(ts_df: pd.DataFrame) -> dict:
    if ts_df.empty or len(ts_df) < 2:
        return {}
    vals = ts_df.set_index("date")["portfolio_value_eur"].sort_index()
    daily_ret = vals.pct_change().dropna()
    starting = vals.iloc[0]
    cum_return = (vals.iloc[-1] - starting) / starting * 100 if starting else 0.0
    vol_ann = daily_ret.std() * np.sqrt(252) * 100 if len(daily_ret) else 0.0
    rolling_max = vals.cummax()
    drawdown = (vals - rolling_max) / rolling_max * 100
    max_dd = drawdown.min()
    sharpe = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
    n_days = (vals.index[-1] - vals.index[0]).days
    return {
        "portfolio_value": round(float(vals.iloc[-1]), 2),
        "cumulative_return_pct": round(float(cum_return), 2),
        "annualised_volatility_pct": round(float(vol_ann), 2),
        "max_drawdown_pct": round(float(max_dd), 2),
        "sharpe_ratio": round(float(sharpe), 2),
        "days_since_inception": int(n_days),
        "last_date": vals.index[-1].date().isoformat() if hasattr(vals.index[-1], "date") else str(vals.index[-1]),
    }


def compute_contributions(enriched_positions_df: pd.DataFrame) -> pd.DataFrame:
    """Total P&L (realized + unrealized) contribution per ticker, for the
    'top contributors' chart. Expects the output of enrich_positions(open_only=False)
    merged with realized P&L (see app.py)."""
    if enriched_positions_df.empty:
        return pd.DataFrame()
    df = enriched_positions_df.copy()
    df["unrealized_pnl_eur"] = df.get("unrealized_pnl_eur", 0.0).fillna(0.0)
    df["total_pnl_eur"] = df["realized_pnl_eur"].fillna(0.0) + df["unrealized_pnl_eur"]
    return df.sort_values("total_pnl_eur", ascending=False)
