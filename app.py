"""
app.py — Anchor Investments dashboard.

A transactional cash-management portfolio tracker: every Buy debits cash,
every Sell credits it, Deposits/Withdrawals move cash directly — the same
mental model as a real brokerage or the Yahoo Finance portfolio view.
Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Anchor Investments",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Local modules ─────────────────────────────────────────────────────────────
from config import (
    PORTFOLIO_NAME, PORTFOLIO_DESCRIPTION, SUBSTACK_URL,
    STARTING_CASH, DISCLAIMER,
)
import db
from data_loader import get_spot_price, get_fx_rate, drain_price_warnings
from portfolio_engine import (
    compute_cash_balance, compute_positions, enrich_positions,
    build_daily_portfolio_value, compute_analytics, compute_contributions,
)
from charts import (
    portfolio_line_chart, cash_vs_invested_chart, return_line_chart, drawdown_chart,
    allocation_pie, allocation_treemap, contribution_bar, asset_class_bar,
)
from auth import is_authenticated, logout

# ── Initialise persistent storage on every startup ───────────────────────────
db.init_db()
db.ensure_inception(STARTING_CASH, date.today().isoformat())

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&display=swap');

html, body, [class*="css"] { font-family: 'Satoshi', -apple-system, sans-serif !important; }
.stApp { background-color: #0f1117 !important; }
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

.stTabs [data-baseweb="tab-list"] { gap: 0; border-bottom: 1px solid #2a2d35; background: transparent; padding: 0; margin-bottom: 1.5rem; }
.stTabs [data-baseweb="tab"] { font-size: 0.8125rem; font-weight: 500; letter-spacing: 0.02em; color: #6b7280; padding: 0.625rem 1.25rem; border-bottom: 2px solid transparent; background: transparent !important; border-radius: 0; transition: color 0.15s ease, border-color 0.15s ease; }
.stTabs [aria-selected="true"] { color: #e2e8f0 !important; border-bottom: 2px solid #01696f !important; background: transparent !important; }
.stTabs [data-baseweb="tab"]:hover { color: #cbd5e1 !important; }

[data-testid="metric-container"] { background: #1a1d26; border: 1px solid #2a2d35; border-radius: 0.5rem; padding: 1rem 1.25rem; transition: border-color 0.15s ease; }
[data-testid="metric-container"]:hover { border-color: #3a3d45; }
[data-testid="metric-container"] label { font-size: 0.6875rem !important; font-weight: 600 !important; letter-spacing: 0.08em !important; text-transform: uppercase !important; color: #6b7280 !important; }
[data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700 !important; color: #e2e8f0 !important; font-variant-numeric: tabular-nums lining-nums; line-height: 1.2; }
[data-testid="metric-container"] [data-testid="stMetricDelta"] { font-size: 0.75rem !important; font-weight: 500 !important; }

h1 { font-size: 1.375rem !important; font-weight: 700 !important; color: #e2e8f0 !important; letter-spacing: -0.01em; margin-bottom: 0.25rem !important; }
h2 { font-size: 0.9375rem !important; font-weight: 600 !important; color: #cbd5e1 !important; margin-top: 1.5rem !important; margin-bottom: 0.75rem !important; }
h3 { font-size: 0.8125rem !important; font-weight: 600 !important; color: #94a3b8 !important; text-transform: uppercase; letter-spacing: 0.06em; }

[data-testid="stDataFrame"] { border: 1px solid #2a2d35; border-radius: 0.5rem; overflow: hidden; }
[data-testid="stDataFrame"] th { background: #1a1d26 !important; color: #6b7280 !important; font-size: 0.6875rem !important; font-weight: 600 !important; letter-spacing: 0.06em !important; text-transform: uppercase !important; padding: 0.625rem 0.75rem !important; border-bottom: 1px solid #2a2d35 !important; }
[data-testid="stDataFrame"] td { font-size: 0.8125rem !important; color: #cbd5e1 !important; padding: 0.5rem 0.75rem !important; border-bottom: 1px solid #1e2028 !important; font-variant-numeric: tabular-nums lining-nums; }
[data-testid="stDataFrame"] tr:hover td { background: #1e2130 !important; }

[data-testid="stExpander"] { background: #1a1d26; border: 1px solid #2a2d35 !important; border-radius: 0.5rem !important; margin-bottom: 0.375rem; }
[data-testid="stExpander"]:hover { border-color: #3a3d45 !important; }
[data-testid="stExpander"] summary { font-size: 0.8125rem !important; font-weight: 500 !important; color: #cbd5e1 !important; padding: 0.625rem 0.875rem !important; }

.stButton > button { background: #01696f !important; color: #ffffff !important; border: none !important; border-radius: 0.375rem !important; font-size: 0.8125rem !important; font-weight: 600 !important; letter-spacing: 0.01em; padding: 0.5rem 1rem !important; transition: background 0.15s ease !important; }
.stButton > button:hover { background: #0c4e54 !important; }
.stButton > button:active { background: #0f3638 !important; }

.stTextInput > div > div > input, .stNumberInput > div > div > input, .stSelectbox > div > div, .stTextArea > div > div > textarea, .stDateInput > div > div > input { background: #1a1d26 !important; border: 1px solid #2a2d35 !important; border-radius: 0.375rem !important; color: #e2e8f0 !important; font-size: 0.8125rem !important; transition: border-color 0.15s ease !important; }
.stTextInput > div > div > input:focus, .stNumberInput > div > div > input:focus, .stTextArea > div > div > textarea:focus { border-color: #01696f !important; box-shadow: 0 0 0 2px rgba(1,105,111,0.2) !important; }
.stTextInput label, .stNumberInput label, .stSelectbox label, .stTextArea label, .stDateInput label, .stCheckbox label { font-size: 0.75rem !important; font-weight: 600 !important; letter-spacing: 0.04em !important; color: #6b7280 !important; text-transform: uppercase !important; }

[data-testid="stAlert"] { border-radius: 0.5rem !important; font-size: 0.8125rem !important; border-left-width: 3px !important; }
[data-testid="stSidebar"] { background: #13151e !important; border-right: 1px solid #2a2d35 !important; }
[data-testid="stPlotlyChart"] { border: 1px solid #2a2d35; border-radius: 0.5rem; overflow: hidden; }

.disclaimer { background: #1a1d26; border: 1px solid #2a2d35; border-left: 3px solid #6b7280; border-radius: 0.375rem; padding: 0.625rem 1rem; font-size: 0.75rem; color: #6b7280; margin-top: 2rem; line-height: 1.5; }
.stCaption, [data-testid="stCaptionContainer"] { font-size: 0.75rem !important; color: #6b7280 !important; }
hr { border-color: #2a2d35 !important; margin: 1.5rem 0 !important; }

.brand-header { display: flex; align-items: center; gap: 0.625rem; padding: 1.25rem 0 0.25rem; }
.brand-name { font-size: 1.25rem; font-weight: 700; color: #e2e8f0; letter-spacing: -0.02em; }
.brand-tagline { font-size: 0.75rem; color: #6b7280; margin-top: 0.125rem; }

.last-updated { display: inline-flex; align-items: center; gap: 0.375rem; background: #1a1d26; border: 1px solid #2a2d35; border-radius: 9999px; padding: 0.25rem 0.75rem; font-size: 0.6875rem; color: #6b7280; margin-bottom: 1rem; }
.last-updated::before { content: ''; display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #01696f; }

.positive { color: #4ade80 !important; font-weight: 600; }
.negative { color: #f87171 !important; font-weight: 600; }
.neutral  { color: #94a3b8 !important; }

.admin-badge { display: inline-flex; align-items: center; background: rgba(1,105,111,0.15); border: 1px solid #01696f; color: #4f98a3; border-radius: 9999px; padding: 0.25rem 0.75rem; font-size: 0.75rem; font-weight: 600; margin-right: 0.5rem; }
.stale-badge { display: inline-block; background: rgba(217,153,0,0.15); border: 1px solid #d19900; color: #d19900; border-radius: 9999px; padding: 0.0625rem 0.5rem; font-size: 0.625rem; font-weight: 600; margin-left: 0.375rem; vertical-align: middle; }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem; margin-bottom: 0.5rem; }
.kpi-card { background: #1a1d26; border: 1px solid #2a2d35; border-radius: 0.5rem; padding: 1rem 1.25rem; transition: border-color 0.15s ease; }
.kpi-card:hover { border-color: #3a3d45; }
.kpi-label { font-size: 0.6875rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #6b7280; margin-bottom: 0.375rem; }
.kpi-value { font-size: 1.5rem; font-weight: 700; color: #e2e8f0; font-variant-numeric: tabular-nums lining-nums; line-height: 1.2; }

.tx-card { background: #1a1d26; border: 1px solid #2a2d35; border-radius: 0.5rem; padding: 0.875rem 1.125rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 1.5rem; flex-wrap: wrap; }
.tx-field-label { font-size: 0.6875rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.06em; }
.tx-field-value { font-size: 0.875rem; color: #cbd5e1; }
.tx-type-pill { display: inline-block; border-radius: 9999px; padding: 0.125rem 0.625rem; font-size: 0.6875rem; font-weight: 700; letter-spacing: 0.03em; }

.modebar-container { background: transparent !important; }
.modebar-btn path { fill: #6b7280 !important; }
.modebar-btn:hover path { fill: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, css_class: str = "") -> str:
    return f"""<div class="kpi-card"><div class="kpi-label">{label}</div><div class="kpi-value {css_class}">{value}</div></div>"""

def _kpi_grid(items) -> str:
    return "<div class='kpi-grid'>" + "".join(_kpi(*i) for i in items) + "</div>"

def _fmt_eur(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    return f"€{v:,.0f}"

def _fmt_eur4(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    return f"€{v:,.4f}"

def _fmt_pct(v, decimals=2) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)): return "—"
    return f"{v:+.{decimals}f}%"

def _color_class(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)): return ""
    return "positive" if v >= 0 else "negative"

TX_TYPE_STYLE = {
    "BUY":        ("#4ade80", "rgba(74,222,128,0.12)"),
    "SELL":       ("#f87171", "rgba(248,113,113,0.12)"),
    "DEPOSIT":    ("#4f98a3", "rgba(79,152,163,0.12)"),
    "WITHDRAWAL": ("#d19900", "rgba(209,153,0,0.12)"),
    "DIVIDEND":   ("#a78bfa", "rgba(167,139,250,0.12)"),
    "FEE":        ("#6b7280", "rgba(107,114,128,0.12)"),
}


# ═════════════════════════════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════════════════════════════

col_title, col_admin = st.columns([8, 2])
with col_title:
    st.markdown(f"## 📊 {PORTFOLIO_NAME}")
    st.caption(PORTFOLIO_DESCRIPTION)

with col_admin:
    if is_authenticated():
        st.markdown("<span class='admin-badge'>⚙ Admin Mode</span>", unsafe_allow_html=True)
        if st.button("Log out", key="logout_top"):
            logout()
    else:
        if st.button("Admin Login", key="admin_login_btn"):
            st.session_state["show_login"] = True

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
# LOAD & COMPUTE (once per rerun, shared across all tabs)
# ═════════════════════════════════════════════════════════════════════════════

tx_df = db.get_transactions(include_voided=False)
inception_date = db.get_meta("inception_date", date.today().isoformat())
starting_cash = float(db.get_meta("starting_cash", str(STARTING_CASH)))
last_updated = db.get_meta("last_updated")

cash_balance = compute_cash_balance(tx_df, starting_cash)
all_positions = compute_positions(tx_df)                       # every ticker ever traded
open_positions = enrich_positions(all_positions, open_only=True)
closed_positions = all_positions[all_positions["quantity"] <= 1e-6]

invested_value = float(open_positions["market_value_eur"].fillna(0).sum()) if not open_positions.empty else 0.0
portfolio_value = cash_balance + invested_value

ts_df = build_daily_portfolio_value(tx_df, starting_cash, inception_date)
analytics = compute_analytics(ts_df) if not ts_df.empty else {}

# Contribution chart covers every ticker ever traded (open + closed), so a
# fully-sold winner still shows up as a contributor to total P&L.
_unrealized_map = (
    open_positions.set_index("ticker")["unrealized_pnl_eur"] if not open_positions.empty else pd.Series(dtype=float)
)
contrib_df = all_positions.copy()
if not contrib_df.empty:
    contrib_df["unrealized_pnl_eur"] = contrib_df["ticker"].map(_unrealized_map).fillna(0.0)
contrib_df = compute_contributions(contrib_df) if not contrib_df.empty else pd.DataFrame()

price_warnings = drain_price_warnings()

n_open_holdings = int((open_positions["quantity"] > 1e-6).sum()) if not open_positions.empty else 0
total_realized = float(all_positions["realized_pnl_eur"].sum()) if not all_positions.empty else 0.0
total_unrealized = float(open_positions["unrealized_pnl_eur"].fillna(0).sum()) if not open_positions.empty else 0.0


# ═════════════════════════════════════════════════════════════════════════════
# TAB LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

tab_labels = ["📈 Overview", "🥧 Allocation", "📉 Performance", "📋 Holdings", "🔄 Changes", "ℹ️ About"]
if is_authenticated():
    tab_labels.append("⚙️ Admin")

tabs = st.tabs(tab_labels)
tab_overview, tab_alloc, tab_perf, tab_holdings, tab_changes, tab_about = tabs[:6]
tab_admin = tabs[6] if is_authenticated() else None

if price_warnings:
    for w in price_warnings:
        st.warning(w, icon="⚠️")


# ═════════════════════════════════════════════════════════════════════════════
# TAB — OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════

with tab_overview:
    if last_updated:
        st.markdown(f"<span class='last-updated'>Last updated: {last_updated[:16].replace('T', ' ')} UTC</span>", unsafe_allow_html=True)

    cr = analytics.get("cumulative_return_pct")
    vol = analytics.get("annualised_volatility_pct")
    mdd = analytics.get("max_drawdown_pct")
    sr = analytics.get("sharpe_ratio")

    st.markdown(_kpi_grid([
        ("Portfolio Value", _fmt_eur(portfolio_value)),
        ("Cash Balance", _fmt_eur(cash_balance)),
        ("Cumulative Return", _fmt_pct(cr), _color_class(cr)),
        ("Ann. Volatility", _fmt_pct(vol, 1) if vol is not None else "—"),
        ("Max Drawdown", _fmt_pct(mdd) if mdd is not None else "—", "negative" if mdd is not None and mdd < 0 else ""),
        ("Sharpe Ratio", f"{sr:.2f}" if sr is not None else "—"),
        ("Holdings", str(n_open_holdings)),
    ]), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not ts_df.empty:
        st.plotly_chart(portfolio_line_chart(ts_df, starting_cash), width="stretch")
        st.plotly_chart(cash_vs_invested_chart(ts_df), width="stretch")
    else:
        st.info("No trade history yet. Log your first Deposit / Buy from the Admin tab to start tracking performance.")

    if not contrib_df.empty:
        st.markdown("<div style='font-size:0.9375rem;font-weight:600;color:#cbd5e1;margin-top:1rem;'>Top Contributors (Realized + Unrealized)</div>", unsafe_allow_html=True)
        st.plotly_chart(contribution_bar(contrib_df.head(10)), width="stretch")

    st.markdown(f"<div class='disclaimer'>{DISCLAIMER}</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB — ALLOCATION
# ═════════════════════════════════════════════════════════════════════════════

with tab_alloc:
    st.markdown(_kpi_grid([
        ("Portfolio Value", _fmt_eur(portfolio_value)),
        ("Invested", _fmt_eur(invested_value)),
        ("Cash Balance", _fmt_eur(cash_balance)),
    ]), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if open_positions.empty and cash_balance <= 0:
        st.info("No holdings or cash yet.")
    else:
        col_l, col_r = st.columns([1, 1])
        with col_l:
            st.plotly_chart(allocation_pie(open_positions, cash_balance), width="stretch")
        with col_r:
            st.plotly_chart(allocation_treemap(open_positions, cash_balance), width="stretch")
        st.plotly_chart(asset_class_bar(open_positions, cash_balance), width="stretch")


# ═════════════════════════════════════════════════════════════════════════════
# TAB — PERFORMANCE
# ═════════════════════════════════════════════════════════════════════════════

with tab_perf:
    if ts_df.empty:
        st.info("Insufficient trade history to compute performance.")
    else:
        st.plotly_chart(return_line_chart(ts_df), width="stretch")
        st.plotly_chart(drawdown_chart(ts_df), width="stretch")

        st.markdown("### Analytics Summary")
        a_col1, a_col2 = st.columns(2)
        with a_col1:
            st.metric("Cumulative Return", _fmt_pct(analytics.get("cumulative_return_pct")))
            st.metric("Annualised Volatility", f"{analytics.get('annualised_volatility_pct', 0):.1f}%")
        with a_col2:
            st.metric("Max Drawdown", f"{analytics.get('max_drawdown_pct', 0):.2f}%")
            st.metric("Sharpe Ratio", f"{analytics.get('sharpe_ratio', 0):.2f}")

        st.markdown("### Realized vs. Unrealized P&L")
        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1: st.metric("Realized P&L", _fmt_eur(total_realized))
        with p_col2: st.metric("Unrealized P&L", _fmt_eur(total_unrealized))
        with p_col3: st.metric("Total P&L", _fmt_eur(total_realized + total_unrealized))

        st.caption(
            "Performance is measured on total portfolio value (cash + positions), not a "
            "time-weighted return — a Deposit/Withdrawal shows up as a jump in value rather than "
            "being excluded from return. Accurate for a portfolio that rarely moves cash in/out; "
            "see the About tab for details."
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB — HOLDINGS
# ═════════════════════════════════════════════════════════════════════════════

with tab_holdings:
    if open_positions.empty:
        st.info("No open positions.")
    else:
        df = open_positions.copy()
        df["weight_pct"] = (df["market_value_eur"] / portfolio_value * 100).round(2) if portfolio_value else 0.0

        display_cols = {
            "ticker": "Ticker", "name": "Name", "asset_class": "Asset Class", "currency": "CCY",
            "quantity": "Qty", "avg_cost_eur": "Avg Cost (€)", "spot_eur": "Price (EUR)",
            "market_value_eur": "Market Val (€)", "weight_pct": "Weight %",
            "unrealized_pnl_eur": "PnL (€)", "unrealized_pnl_pct": "PnL %",
            "first_trade_date": "Since",
        }
        show_cols = [c for c in display_cols if c in df.columns]
        tbl = df[show_cols].copy()
        tbl.columns = [display_cols[c] for c in show_cols]

        def _style_pnl(val):
            if isinstance(val, (int, float)) and pd.notna(val):
                return "color: #4ade80; font-weight:500" if val >= 0 else "color: #f87171; font-weight:500"
            return ""

        # Every formatter must tolerate NaN/None (a stale/failed price fetch
        # leaves these blank) — a bare "€{:,.4f}" format string raises on
        # None instead of falling back to a placeholder.
        styled = tbl.style.format({
            "Qty": lambda v: f"{v:,.4f}" if pd.notna(v) else "—",
            "Avg Cost (€)": lambda v: f"€{v:,.4f}" if pd.notna(v) else "—",
            "Price (EUR)": lambda v: f"€{v:,.4f}" if pd.notna(v) else "—",
            "Market Val (€)": lambda v: f"€{v:,.0f}" if pd.notna(v) else "—",
            "Weight %": lambda v: f"{v:.2f}%" if pd.notna(v) else "—",
            "PnL (€)": lambda v: f"€{v:+,.0f}" if pd.notna(v) else "—",
            "PnL %": lambda v: f"{v:+.2f}%" if pd.notna(v) else "—",
        }).map(_style_pnl, subset=["PnL (€)", "PnL %"])

        st.dataframe(styled, width="stretch", hide_index=True)

        stale = df[df.get("price_stale", False) == True]
        if not stale.empty:
            st.caption(f"⚠️ Prices for {', '.join(stale['ticker'])} are last-known cached values — Yahoo Finance did not respond on the latest refresh.")

    if not closed_positions.empty:
        with st.expander(f"Closed positions ({len(closed_positions)})", expanded=False):
            cdf = closed_positions[["ticker", "name", "asset_class", "realized_pnl_eur", "first_trade_date", "last_trade_date"]].copy()
            cdf.columns = ["Ticker", "Name", "Asset Class", "Realized P&L (€)", "First Trade", "Last Trade"]
            st.dataframe(cdf, width="stretch", hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB — ABOUT
# ═════════════════════════════════════════════════════════════════════════════

with tab_about:
    st.markdown(f"""
### About This Portfolio

This is a **model portfolio** started with **€{starting_cash:,.0f}** of cash, conceived to reflect
the investment insights shared through our Substack publication. Positions are opened and closed
through real Buy/Sell trades logged from the Admin panel — exactly like a brokerage account:
a **Buy debits cash** by the trade value, a **Sell credits cash** back. The portfolio is manually
managed as a companion resource to [the Substack publication]({SUBSTACK_URL}).

**Methodology**
- Every cash movement (Buy, Sell, Deposit, Withdrawal, Dividend, Fee) is one row in an append-only
  transaction ledger — cash balance and open positions are both derived from that ledger, so they
  can never drift out of sync with each other.
- Open positions use **average-cost** accounting: each Buy blends into the position's average cost;
  each Sell realizes P&L against that average.
- Historical performance replays the ledger day by day against historical closing prices, with FX
  conversion to EUR where required.
- Performance is measured on total portfolio value, not a time-weighted return — see the
  Performance tab for what that means in practice.

**Data & Pricing**
- Prices are sourced from Yahoo Finance (via `yfinance`), batched into a single request per refresh
  to minimize rate-limiting, and cached for {int(15)} minutes.
- If a live price fetch fails, the dashboard falls back to the last successfully fetched price for
  that ticker (flagged as stale in the Holdings tab) rather than showing a blank value.
- Non-EUR assets are converted to EUR using live FX rates.

**Inception Date:** {inception_date}

---

{DISCLAIMER}
    """)


# ═════════════════════════════════════════════════════════════════════════════
# LOGIN MODAL
# ═════════════════════════════════════════════════════════════════════════════

if not is_authenticated() and st.session_state.get("show_login"):
    with st.expander("🔐 Admin Login", expanded=True):
        from auth import login_form
        login_form()


# ═════════════════════════════════════════════════════════════════════════════
# TAB — ADMIN (authenticated only)
# ═════════════════════════════════════════════════════════════════════════════

if tab_admin is not None:
    with tab_admin:
        st.markdown("### ⚙️ Portfolio Management")
        st.caption("Every action here writes a new row to the transaction ledger and updates the cash balance immediately.")

        st.markdown(_kpi_grid([
            ("Cash Balance", _fmt_eur(cash_balance)),
            ("Invested Value", _fmt_eur(invested_value)),
            ("Portfolio Value", _fmt_eur(portfolio_value)),
        ]), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        admin_tabs = st.tabs(["💱 Trade (Buy/Sell)", "💵 Deposit / Withdraw", "🧾 Ledger & Corrections"])

        # ── Buy / Sell ──────────────────────────────────────────────────────
        with admin_tabs[0]:
            side = st.radio("Side", ["BUY", "SELL"], horizontal=True, key="trade_side")

            lookup_col1, lookup_col2, lookup_col3 = st.columns([2, 1, 1])
            with lookup_col1:
                t_ticker = st.text_input("Ticker", key="t_ticker", help="e.g. AAPL, IWDA.AS, BTC-EUR").upper().strip()
            with lookup_col2:
                t_currency = st.text_input("Currency", value="EUR", max_chars=3, key="t_currency").upper()
            with lookup_col3:
                st.markdown("<div style='height:1.6rem'></div>", unsafe_allow_html=True)
                if st.button("🔎 Fetch live price", key="fetch_price_btn") and t_ticker:
                    px = get_spot_price(t_ticker)
                    if px is None:
                        st.error(f"Could not fetch a live price for {t_ticker}. Enter it manually below.")
                    else:
                        st.session_state["fetched_price_local"] = px
                        fx = get_fx_rate(t_currency, "EUR") if t_currency != "EUR" else 1.0
                        st.session_state["fetched_price_eur"] = px * (fx or 1.0)
                        st.success(f"{t_ticker}: {px:,.4f} {t_currency} (≈ €{st.session_state['fetched_price_eur']:,.4f})")

            existing_qty = 0.0
            if side == "SELL" and not all_positions.empty and t_ticker:
                match = all_positions[all_positions["ticker"] == t_ticker]
                if not match.empty:
                    existing_qty = float(match.iloc[0]["quantity"])
            if side == "SELL" and t_ticker:
                st.caption(f"Current position: {existing_qty:,.4f} units")

            with st.form("trade_form"):
                fc1, fc2, fc3 = st.columns(3)
                with fc1:
                    f_name = st.text_input("Name", help="Human-readable name")
                    f_asset_class = st.selectbox("Asset Class", ["Equity", "ETF", "Bond ETF", "Crypto", "Cash", "Real Estate", "Commodity"])
                with fc2:
                    f_qty = st.number_input("Quantity *", min_value=0.0, step=1.0, format="%.6f")
                    default_price = st.session_state.get("fetched_price_eur", 0.0)
                    f_price_eur = st.number_input("Price (EUR per unit) *", min_value=0.0, value=float(default_price), step=0.01, format="%.4f",
                                                   help="Auto-filled by 'Fetch live price'. Override if needed.")
                with fc3:
                    f_date = st.date_input("Trade Date", value=date.today())
                    f_fees = st.number_input("Fees (EUR)", min_value=0.0, value=0.0, step=0.5)
                f_notes = st.text_area("Notes / Thesis", height=70)

                submitted = st.form_submit_button(f"💾 Log {side}", type="primary")

            if submitted:
                errors = []
                if not t_ticker: errors.append("Ticker is required.")
                if f_qty <= 0: errors.append("Quantity must be greater than zero.")
                if f_price_eur <= 0: errors.append("Price must be greater than zero.")
                if len(t_currency) != 3: errors.append("Currency must be a 3-letter code.")

                trade_value = f_qty * f_price_eur
                if side == "BUY":
                    total_cost = trade_value + f_fees
                    if total_cost > cash_balance + 0.01:
                        errors.append(f"Insufficient cash: trade costs {_fmt_eur(total_cost)} but cash balance is {_fmt_eur(cash_balance)}.")
                else:  # SELL
                    if f_qty > existing_qty + 1e-6:
                        errors.append(f"Cannot sell {f_qty:,.4f} units — only {existing_qty:,.4f} held.")

                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    fx_now = get_fx_rate(t_currency, "EUR") if t_currency != "EUR" else 1.0
                    price_local = f_price_eur / (fx_now or 1.0)
                    cash_amount = -(trade_value + f_fees) if side == "BUY" else (trade_value - f_fees)
                    db.add_transaction(
                        tx_date=f_date.isoformat(), tx_type=side, cash_amount_eur=cash_amount,
                        ticker=t_ticker, name=f_name or t_ticker, asset_class=f_asset_class,
                        currency=t_currency, quantity=f_qty, price_local=price_local,
                        fx_rate=fx_now, price_eur=f_price_eur, fees_eur=f_fees, notes=f_notes,
                    )
                    st.session_state.pop("fetched_price_eur", None)
                    st.session_state.pop("fetched_price_local", None)
                    st.success(f"✅ Logged {side} {f_qty:,.4f} {t_ticker} @ €{f_price_eur:,.4f}. Cash balance updated.")
                    st.rerun()

        # ── Deposit / Withdraw ─────────────────────────────────────────────
        with admin_tabs[1]:
            cw_side = st.radio("Type", ["DEPOSIT", "WITHDRAWAL"], horizontal=True, key="cw_side")
            with st.form("cash_form"):
                cw_amount = st.number_input("Amount (EUR) *", min_value=0.0, step=100.0)
                cw_date = st.date_input("Date", value=date.today(), key="cw_date")
                cw_notes = st.text_area("Notes", height=70, key="cw_notes")
                cw_submit = st.form_submit_button(f"💾 Log {cw_side.title()}", type="primary")
            if cw_submit:
                if cw_amount <= 0:
                    st.error("Amount must be greater than zero.")
                elif cw_side == "WITHDRAWAL" and cw_amount > cash_balance + 0.01:
                    st.error(f"Cannot withdraw {_fmt_eur(cw_amount)} — cash balance is only {_fmt_eur(cash_balance)}.")
                else:
                    signed = cw_amount if cw_side == "DEPOSIT" else -cw_amount
                    db.add_transaction(
                        tx_date=cw_date.isoformat(), tx_type=cw_side, cash_amount_eur=signed, notes=cw_notes,
                    )
                    st.success(f"✅ {cw_side.title()} of {_fmt_eur(cw_amount)} logged.")
                    st.rerun()

        # ── Ledger & corrections ────────────────────────────────────────────
        with admin_tabs[2]:
            st.caption("Corrections are done by voiding a row (soft delete) — the row stays visible here for audit purposes but no longer affects cash/positions.")
            full_ledger = db.get_transactions(include_voided=True)
            if full_ledger.empty:
                st.info("No transactions logged yet.")
            else:
                for _, row in full_ledger.sort_values(["tx_date", "id"], ascending=False).iterrows():
                    label = f"{row['tx_date']} — {row['tx_type']}"
                    if pd.notna(row["ticker"]) and row["ticker"]:
                        label += f" {row['quantity']:,.4f} {row['ticker']} @ €{row['price_eur']:,.4f}" if pd.notna(row["quantity"]) else f" {row['ticker']}"
                    label += f" — {_fmt_eur(row['cash_amount_eur'])}"
                    if row["voided"]:
                        label = f"❌ VOIDED — {label}"
                    with st.expander(label, expanded=False):
                        st.write(f"**Notes:** {row['notes'] or '—'}")
                        st.write(f"**Logged at:** {row['created_at']} UTC")
                        if row["voided"]:
                            st.write(f"**Void reason:** {row.get('void_reason') or '—'}")
                        else:
                            reason = st.text_input("Void reason (optional)", key=f"void_reason_{row['id']}")
                            if st.button(f"🗑 Void transaction #{row['id']}", key=f"void_{row['id']}"):
                                db.void_transaction(int(row["id"]), reason)
                                st.success(f"Transaction #{row['id']} voided.")
                                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# TAB — CHANGES (public trade blotter)
# ═════════════════════════════════════════════════════════════════════════════

with tab_changes:
    st.markdown("### 🔄 Portfolio Changes")
    st.caption("A full audit trail of every trade and cash movement since inception.")

    if tx_df.empty:
        st.info("No transactions logged yet.")
    else:
        for _, row in tx_df.sort_values(["tx_date", "id"], ascending=False).iterrows():
            color, bg = TX_TYPE_STYLE.get(row["tx_type"], ("#94a3b8", "rgba(148,163,184,0.12)"))
            qty_line = f"{row['quantity']:,.4f}" if pd.notna(row["quantity"]) else "—"
            price_line = f"€{row['price_eur']:,.4f}" if pd.notna(row["price_eur"]) else "—"
            st.markdown(f"""
            <div class="tx-card">
                <div style="min-width:90px;">
                    <div class="tx-field-label">Date</div>
                    <div class="tx-field-value">{row['tx_date']}</div>
                </div>
                <div style="min-width:100px;">
                    <div class="tx-field-label">Type</div>
                    <div><span class="tx-type-pill" style="color:{color};background:{bg};">{row['tx_type']}</span></div>
                </div>
                <div style="min-width:90px;">
                    <div class="tx-field-label">Ticker</div>
                    <div class="tx-field-value" style="color:#e2e8f0;font-weight:700;">{row['ticker'] if pd.notna(row['ticker']) and row['ticker'] else '—'}</div>
                </div>
                <div style="min-width:90px;">
                    <div class="tx-field-label">Qty</div>
                    <div class="tx-field-value">{qty_line}</div>
                </div>
                <div style="min-width:110px;">
                    <div class="tx-field-label">Price</div>
                    <div class="tx-field-value">{price_line}</div>
                </div>
                <div style="min-width:120px;">
                    <div class="tx-field-label">Cash Impact</div>
                    <div class="tx-field-value" style="color:{'#4ade80' if row['cash_amount_eur'] >= 0 else '#f87171'};font-weight:600;">
                        {'+' if row['cash_amount_eur'] >= 0 else ''}{_fmt_eur(row['cash_amount_eur'])}
                    </div>
                </div>
                <div style="flex:1;min-width:150px;">
                    <div class="tx-field-label">Note</div>
                    <div class="tx-field-value" style="color:#94a3b8;">{row['notes'] if row['notes'] else '—'}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
