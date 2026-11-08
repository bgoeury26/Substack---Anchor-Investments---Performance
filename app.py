"""
app.py — Anchor Investments dashboard.

A transactional cash-management portfolio tracker: every Buy debits cash,
every Sell credits it, Deposits/Withdrawals move cash directly — the same
mental model as a real brokerage or the Yahoo Finance portfolio view.
Run:  streamlit run app.py
"""

from datetime import date
from pathlib import Path

import streamlit as st
import pandas as pd

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Anchor Investments",
    page_icon=str(Path(__file__).parent / "assets" / "favicon.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Local modules ─────────────────────────────────────────────────────────────
from config import (
    PORTFOLIO_NAME, PORTFOLIO_DESCRIPTION, SUBSTACK_URL,
    STARTING_CASH, DISCLAIMER, PRICE_CACHE_TTL,
)
import db
from data_loader import get_spot_price, get_fx_rate, drain_price_warnings
from portfolio_engine import (
    compute_cash_balance, compute_positions, enrich_positions,
    build_daily_portfolio_value, compute_analytics, compute_contributions,
)
from charts import (
    portfolio_line_chart, cash_vs_invested_chart, return_line_chart, drawdown_chart,
    allocation_donut, holdings_bar, contribution_bar,
)
from auth import is_authenticated, logout, login_form
import theme
from theme import fmt_eur as _fmt_eur, fmt_pct as _fmt_pct, kpi_strip, section, empty_state

# ── Initialise persistent storage on every startup ───────────────────────────
db.init_db()
db.ensure_inception(STARTING_CASH, date.today().isoformat())

st.markdown(theme.CSS, unsafe_allow_html=True)


def _chart(fig) -> None:
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


# ═════════════════════════════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════════════════════════════

col_brand, col_link, col_admin = st.columns([7, 2, 1.3], vertical_alignment="center")
with col_brand:
    st.html(theme.brand(PORTFOLIO_NAME))
with col_link:
    if "yoursubstack" not in SUBSTACK_URL:
        st.html(f'<div class="aw-toplink"><a href="{SUBSTACK_URL}" target="_blank" rel="noopener">Read the Substack</a></div>')
with col_admin:
    if is_authenticated():
        st.html('<span class="aw-admin-flag">Admin mode</span>')
        if st.button("Log out", key="logout_top", type="tertiary"):
            logout()
    else:
        if st.button("Admin login", key="admin_login_btn", type="tertiary"):
            st.session_state["show_login"] = not st.session_state.get("show_login", False)

if not is_authenticated() and st.session_state.get("show_login"):
    with st.container(key="login_panel"):
        login_form()

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

cr = analytics.get("cumulative_return_pct")
vol = analytics.get("annualised_volatility_pct")
mdd = analytics.get("max_drawdown_pct")
sr = analytics.get("sharpe_ratio")
_vol_text = f"{vol:.1f}%" if vol is not None else "—"
_sharpe_text = f"{sr:.2f}" if sr is not None else "—"
_mdd_class = "aw-neg" if mdd is not None and mdd < 0 else ""


# ═════════════════════════════════════════════════════════════════════════════
# TAB LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

for w in price_warnings:
    st.warning(w)

tab_labels = ["Overview", "Allocation", "Performance", "Holdings", "Changes", "About"]
if is_authenticated():
    tab_labels.append("Admin")

tabs = st.tabs(tab_labels)
tab_overview, tab_alloc, tab_perf, tab_holdings, tab_changes, tab_about = tabs[:6]
tab_admin = tabs[6] if is_authenticated() else None


# ═════════════════════════════════════════════════════════════════════════════
# TAB — OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════

with tab_overview:
    st.html(
        theme.hero(portfolio_value, cr, inception_date, PORTFOLIO_DESCRIPTION)
        + kpi_strip([
            ("Cash", _fmt_eur(cash_balance)),
            ("Invested", _fmt_eur(invested_value)),
            ("Annual volatility", _vol_text),
            ("Max drawdown", _fmt_pct(mdd), _mdd_class),
            ("Sharpe ratio", _sharpe_text),
            ("Holdings", str(n_open_holdings)),
        ], lift=True)
    )

    if not ts_df.empty:
        _updated = f"Ledger updated {theme.fmt_date(last_updated)}" if last_updated else "Daily, in EUR"
        st.html(section("Portfolio value", _updated))
        _chart(portfolio_line_chart(ts_df, starting_cash))

        left, right = st.columns([3, 2], gap="large")
        with left:
            st.html(section("Cash and invested capital", "How much is at sea, how much is in harbour"))
            _chart(cash_vs_invested_chart(ts_df))
        with right:
            if not contrib_df.empty:
                st.html(section("Top contributors", "Realized + unrealized"))
                _chart(contribution_bar(contrib_df.head(10)))
    else:
        st.html(empty_state("Still at anchor", "Log a first deposit or buy from the Admin tab to start tracking performance."))


# ═════════════════════════════════════════════════════════════════════════════
# TAB — ALLOCATION
# ═════════════════════════════════════════════════════════════════════════════

with tab_alloc:
    st.html(kpi_strip([
        ("Portfolio value", _fmt_eur(portfolio_value)),
        ("Invested", _fmt_eur(invested_value)),
        ("Cash", _fmt_eur(cash_balance)),
        ("Cash weight", f"{cash_balance / portfolio_value * 100:.1f}%" if portfolio_value else "—"),
    ]))

    if open_positions.empty and cash_balance <= 0:
        st.html(empty_state("Nothing on board yet", "Holdings and cash will appear here once they are logged."))
    else:
        col_l, col_r = st.columns([2, 3], gap="large")
        with col_l:
            st.html(section("By asset class", "Share of portfolio"))
            _chart(allocation_donut(open_positions, cash_balance))
        with col_r:
            st.html(section("By holding", "Market value in EUR"))
            _chart(holdings_bar(open_positions, cash_balance, portfolio_value))


# ═════════════════════════════════════════════════════════════════════════════
# TAB — PERFORMANCE
# ═════════════════════════════════════════════════════════════════════════════

with tab_perf:
    if ts_df.empty:
        st.html(empty_state("No wake to measure yet", "Performance needs at least two days of trade history."))
    else:
        st.html(kpi_strip([
            ("Cumulative return", _fmt_pct(cr), theme.tone(cr)),
            ("Annual volatility", _vol_text),
            ("Max drawdown", _fmt_pct(mdd), _mdd_class),
            ("Sharpe ratio", _sharpe_text),
        ]))

        st.html(section("Cumulative return", "Against starting cash"))
        _chart(return_line_chart(ts_df))
        st.html(section("Drawdown", "Distance below the previous peak"))
        _chart(drawdown_chart(ts_df))

        st.html(section("Realized and unrealized P&amp;L"))
        st.html(kpi_strip([
            ("Realized", theme.fmt_signed_eur(total_realized), theme.tone(total_realized)),
            ("Unrealized", theme.fmt_signed_eur(total_unrealized), theme.tone(total_unrealized)),
            ("Total", theme.fmt_signed_eur(total_realized + total_unrealized), theme.tone(total_realized + total_unrealized)),
        ]))

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
        st.html(empty_state("No open positions", "Positions will be listed here once a buy is logged."))
    else:
        df = open_positions.copy()
        df["weight_pct"] = (df["market_value_eur"] / portfolio_value * 100).round(2) if portfolio_value else 0.0
        st.html(section("Holdings", f"{n_open_holdings} open positions, valued in EUR", flush=True))
        st.html(theme.holdings_table(df))

        stale = df[df["price_stale"] == True]
        if not stale.empty:
            st.caption(f"Prices for {', '.join(stale['ticker'])} are last-known cached values. Yahoo Finance did not respond on the latest refresh.")

    if not closed_positions.empty:
        with st.expander(f"Closed positions ({len(closed_positions)})", expanded=False):
            st.html(theme.closed_table(closed_positions))


# ═════════════════════════════════════════════════════════════════════════════
# TAB — ABOUT
# ═════════════════════════════════════════════════════════════════════════════

with tab_about:
    st.html(section("About this portfolio", flush=True))
    about_text, about_facts = st.columns([3, 2], gap="large")
    with about_text:
        with st.container(key="about_prose"):
            st.markdown(f"""
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

**Data & pricing**
- Prices are sourced from Yahoo Finance (via `yfinance`), batched into a single request per refresh
  to minimize rate-limiting, and cached for {PRICE_CACHE_TTL // 60} minutes.
- If a live price fetch fails, the dashboard falls back to the last successfully fetched price for
  that ticker (flagged as stale in the Holdings tab) rather than showing a blank value.
- Non-EUR assets are converted to EUR using live FX rates.
""")
    with about_facts:
        st.html(theme.fact_sheet([
            ("Inception", theme.fmt_date(inception_date)),
            ("Starting capital", _fmt_eur(starting_cash)),
            ("Base currency", "EUR"),
            ("Cost method", "Average cost"),
            ("Price source", "Yahoo Finance"),
            ("Price refresh", f"Every {PRICE_CACHE_TTL // 60} minutes"),
        ]))


# ═════════════════════════════════════════════════════════════════════════════
# TAB — ADMIN (authenticated only)
# ═════════════════════════════════════════════════════════════════════════════

if tab_admin is not None:
    with tab_admin:
        st.html(section("Portfolio management", "Every action writes a new ledger row and updates cash immediately", flush=True))

        st.html(kpi_strip([
            ("Cash", _fmt_eur(cash_balance)),
            ("Invested", _fmt_eur(invested_value)),
            ("Portfolio value", _fmt_eur(portfolio_value)),
        ]))

        admin_tabs = st.tabs(["Trade", "Deposit / withdraw", "Ledger and corrections"])

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
                if st.button("Fetch live price", key="fetch_price_btn") and t_ticker:
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

                submitted = st.form_submit_button(f"Log {side.lower()}", type="primary")

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
                    st.success(f"Logged {side} {f_qty:,.4f} {t_ticker} @ €{f_price_eur:,.4f}. Cash balance updated.")
                    st.rerun()

        # ── Deposit / Withdraw ─────────────────────────────────────────────
        with admin_tabs[1]:
            cw_side = st.radio("Type", ["DEPOSIT", "WITHDRAWAL"], horizontal=True, key="cw_side")
            with st.form("cash_form"):
                cw_amount = st.number_input("Amount (EUR) *", min_value=0.0, step=100.0)
                cw_date = st.date_input("Date", value=date.today(), key="cw_date")
                cw_notes = st.text_area("Notes", height=70, key="cw_notes")
                cw_submit = st.form_submit_button(f"Log {cw_side.lower()}", type="primary")
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
                    st.success(f"{cw_side.title()} of {_fmt_eur(cw_amount)} logged.")
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
                        label = f"VOIDED — {label}"
                    with st.expander(label, expanded=False):
                        st.write(f"**Notes:** {row['notes'] or '—'}")
                        st.write(f"**Logged at:** {row['created_at']} UTC")
                        if row["voided"]:
                            st.write(f"**Void reason:** {row.get('void_reason') or '—'}")
                        else:
                            reason = st.text_input("Void reason (optional)", key=f"void_reason_{row['id']}")
                            if st.button(f"Void transaction #{row['id']}", key=f"void_{row['id']}"):
                                db.void_transaction(int(row["id"]), reason)
                                st.success(f"Transaction #{row['id']} voided.")
                                st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# TAB — CHANGES (public trade blotter)
# ═════════════════════════════════════════════════════════════════════════════

with tab_changes:
    st.html(section("Logbook", "Every trade and cash movement since inception", flush=True))

    if tx_df.empty:
        st.html(empty_state("The log is blank", "No transactions have been recorded yet."))
    else:
        st.html(theme.logbook(tx_df))


st.html(theme.footer(DISCLAIMER))
