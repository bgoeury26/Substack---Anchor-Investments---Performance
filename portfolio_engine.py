"""
portfolio_engine.py — Portfolio calculations.
PnL uses stored entry_price_eur (NAV-style closing price on effective_date).
"""

import pandas as pd
import numpy as np
from datetime import date
from config import BASE_CAPITAL
from data_loader import get_price_history, get_spot_price, get_fx_rate


def _to_date_index(s: pd.Series) -> pd.Series:
    """Normalize any Series index to pandas DatetimeIndex strings (YYYY-MM-DD)."""
    idx = pd.to_datetime(s.index, errors="coerce")
    s = s.copy()
    s.index = idx
    return s.loc[~s.index.isna()]


def _get_closing_price_eur(ticker: str, effective_date: str, currency: str):
    try:
        end_dt = (pd.Timestamp(effective_date) + pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        df = get_price_history(ticker, effective_date, end_dt)
        if df.empty:
            return None
        df = df.sort_values("date")
        close_local = float(df.iloc[0]["close"])
        if currency != "EUR":
            fx = get_fx_rate(currency, "EUR")
            if fx is None:
                return None
            return close_local * fx
        return close_local
    except Exception:
        return None


def enrich_holdings(holdings_df: pd.DataFrame) -> pd.DataFrame:
    if holdings_df.empty:
        return holdings_df
    df = holdings_df.copy()
    df["weight_pct"] = (df["eur_allocation"] / BASE_CAPITAL * 100).round(2)
    df["total_weight_pct"] = df["weight_pct"].sum()

    prices_eur, current_vals, pnl_eur, pnl_pct = [], [], [], []

    for _, row in df.iterrows():
        ticker   = row["ticker"]
        currency = (row.get("currency") or "EUR")
        alloc    = float(row["eur_allocation"])
        entry_px = row.get("entry_price_eur")
        try:
            entry_px = float(entry_px) if entry_px and str(entry_px) not in ("", "None", "nan") else None
        except (TypeError, ValueError):
            entry_px = None

        spot_local = get_spot_price(ticker)

        if spot_local is None:
            prices_eur.append(None)
            current_vals.append(None)
            pnl_eur.append(None)
            pnl_pct.append(None)
            continue

        fx       = get_fx_rate(currency, "EUR") if currency != "EUR" else 1.0
        spot_eur = spot_local * (fx or 1.0)

        if entry_px and entry_px > 0:
            units       = alloc / entry_px
            current_val = units * spot_eur
            gain        = current_val - alloc
            gain_pct    = (gain / alloc * 100) if alloc else 0.0
        else:
            current_val = alloc
            gain        = 0.0
            gain_pct    = 0.0

        prices_eur.append(round(spot_eur, 4))
        current_vals.append(round(current_val, 2))
        pnl_eur.append(round(gain, 2))
        pnl_pct.append(round(gain_pct, 2))

    df["latest_price_eur"]  = prices_eur
    df["current_value_eur"] = current_vals
    df["pnl_eur"]           = pnl_eur
    df["pnl_pct"]           = pnl_pct
    return df


def build_portfolio_timeseries(
    holdings_df: pd.DataFrame,
    inception_date: str,
) -> pd.DataFrame:
    if holdings_df.empty:
        return pd.DataFrame(columns=["date", "portfolio_value", "cumulative_return_pct"])

    end = date.today().isoformat()
    weight_series = []

    for _, row in holdings_df.iterrows():
        ticker    = row["ticker"]
        alloc     = float(row["eur_allocation"])
        currency  = (row.get("currency") or "EUR")
        effective = row.get("effective_date") or inception_date
        entry_px  = row.get("entry_price_eur")
        try:
            entry_px = float(entry_px) if entry_px and str(entry_px) not in ("", "None", "nan") else None
        except (TypeError, ValueError):
            entry_px = None

        price_df = get_price_history(ticker, effective, end)

        if price_df.empty or len(price_df) < 2:
            # Flat line: hold allocation value constant from inception to today
            date_range = pd.date_range(start=inception_date, end=end, freq="B")
            flat = pd.Series(alloc, index=date_range, dtype=float)
            weight_series.append(flat)
            continue

        price_s = price_df.set_index("date")["close"].astype(float)

        if currency != "EUR":
            from data_loader import get_fx_history
            fx_df = get_fx_history(currency, "EUR", effective, end)
            if fx_df.empty:
                date_range = pd.date_range(start=inception_date, end=end, freq="B")
                flat = pd.Series(alloc, index=date_range, dtype=float)
                weight_series.append(flat)
                continue
            fx_s      = fx_df.set_index("date")["close"].astype(float)
            # Normalize both to DatetimeIndex before multiply
            price_s   = _to_date_index(price_s)
            fx_s      = _to_date_index(fx_s)
            price_eur = price_s.multiply(fx_s, fill_value=np.nan).dropna()
        else:
            price_eur = _to_date_index(price_s)

        price_eur = price_eur.sort_index()
        if price_eur.empty:
            continue

        base_price = entry_px if (entry_px and entry_px > 0) else float(price_eur.iloc[0])
        if base_price == 0:
            continue

        indexed = (price_eur / base_price) * alloc
        weight_series.append(indexed)

    if not weight_series:
        return pd.DataFrame(columns=["date", "portfolio_value", "cumulative_return_pct"])

    # All series now have DatetimeIndex — safe to concat and sort
    combined        = pd.concat(weight_series, axis=1).sort_index()
    combined        = combined.ffill().dropna(how="all")
    portfolio_value = combined.sum(axis=1)

    total_alloc = holdings_df["eur_allocation"].astype(float).sum()
    unallocated = BASE_CAPITAL - total_alloc
    if unallocated > 0:
        portfolio_value = portfolio_value + unallocated

    df_out = portfolio_value.reset_index()
    df_out.columns = ["date", "portfolio_value"]
    df_out["portfolio_value"]       = df_out["portfolio_value"].round(2)
    df_out["cumulative_return_pct"] = (
        (df_out["portfolio_value"] - BASE_CAPITAL) / BASE_CAPITAL * 100
    ).round(4)
    df_out["date"] = pd.to_datetime(df_out["date"])
    return df_out


def compute_analytics(portfolio_ts: pd.DataFrame) -> dict:
    if portfolio_ts.empty or len(portfolio_ts) < 2:
        return {}
    vals      = portfolio_ts.set_index("date")["portfolio_value"].sort_index()
    daily_ret = vals.pct_change().dropna()
    cum_return = (vals.iloc[-1] - BASE_CAPITAL) / BASE_CAPITAL * 100
    vol_ann    = daily_ret.std() * np.sqrt(252) * 100
    rolling_max = vals.cummax()
    drawdown   = (vals - rolling_max) / rolling_max * 100
    max_dd     = drawdown.min()
    sharpe     = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)) if daily_ret.std() > 0 else 0
    n_days     = (vals.index[-1] - vals.index[0]).days
    return {
        "portfolio_value":           round(float(vals.iloc[-1]), 2),
        "cumulative_return_pct":     round(float(cum_return), 2),
        "annualised_volatility_pct": round(float(vol_ann), 2),
        "max_drawdown_pct":          round(float(max_dd), 2),
        "sharpe_ratio":              round(float(sharpe), 2),
        "days_since_inception":      int(n_days),
        "last_date":                 vals.index[-1].date().isoformat(),
    }


def compute_contributions(
    holdings_df: pd.DataFrame,
    inception_date: str,
) -> pd.DataFrame:
    if holdings_df.empty:
        return pd.DataFrame()

    end  = date.today().isoformat()
    rows = []

    for _, holding in holdings_df.iterrows():
        ticker    = holding["ticker"]
        alloc     = float(holding["eur_allocation"])
        currency  = (holding.get("currency") or "EUR")
        effective = holding.get("effective_date") or inception_date
        entry_px  = holding.get("entry_price_eur")
        try:
            entry_px = float(entry_px) if entry_px and str(entry_px) not in ("", "None", "nan") else None
        except (TypeError, ValueError):
            entry_px = None

        price_df = get_price_history(ticker, effective, end)

        if price_df.empty or len(price_df) < 2:
            rows.append({
                "ticker": ticker, "name": holding["name"],
                "asset_class": holding.get("asset_class", ""),
                "eur_allocation": alloc,
                "return_pct": 0.0, "contrib_eur": 0.0, "contrib_pct": 0.0,
            })
            continue

        price_s = price_df.set_index("date")["close"].astype(float)

        if currency != "EUR":
            from data_loader import get_fx_history
            fx_df = get_fx_history(currency, "EUR", effective, end)
            if fx_df.empty:
                rows.append({
                    "ticker": ticker, "name": holding["name"],
                    "asset_class": holding.get("asset_class", ""),
                    "eur_allocation": alloc,
                    "return_pct": 0.0, "contrib_eur": 0.0, "contrib_pct": 0.0,
                })
                continue
            fx_s      = fx_df.set_index("date")["close"].astype(float)
            price_s   = _to_date_index(price_s)
            fx_s      = _to_date_index(fx_s)
            price_eur = price_s.multiply(fx_s, fill_value=np.nan).dropna()
        else:
            price_eur = _to_date_index(price_s)

        price_eur = price_eur.sort_index()
        if price_eur.empty:
            continue

        base    = entry_px if (entry_px and entry_px > 0) else float(price_eur.iloc[0])
        if base == 0:
            continue
        current     = float(price_eur.iloc[-1])
        ret         = (current - base) / base
        contrib_eur = alloc * ret
        contrib_pct = contrib_eur / BASE_CAPITAL * 100

        rows.append({
            "ticker":         ticker,
            "name":           holding["name"],
            "asset_class":    holding.get("asset_class", ""),
            "eur_allocation": alloc,
            "return_pct":     round(ret * 100, 2),
            "contrib_eur":    round(contrib_eur, 2),
            "contrib_pct":    round(contrib_pct, 4),
        })

    return pd.DataFrame(rows).sort_values("contrib_eur", ascending=False)
