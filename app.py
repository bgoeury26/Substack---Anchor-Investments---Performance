"""
app.py — Main Streamlit entry point for the Portfolio Dashboard.

Run:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="Model Portfolio",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Local modules ─────────────────────────────────────────────────────────────
from config import (
    PORTFOLIO_NAME, PORTFOLIO_DESCRIPTION, SUBSTACK_URL,
    BASE_CAPITAL, DISCLAIMER, CURRENCY_DISPLAY
)
from storage import init_db, seed_database, get_holdings, get_meta, create_rebalance_snapshot
from data_loader import get_spot_price
from portfolio_engine import enrich_holdings, build_portfolio_timeseries, compute_analytics, compute_contributions
from charts import (
    portfolio_line_chart, return_line_chart, drawdown_chart,
    allocation_pie, allocation_treemap, contribution_bar, asset_class_bar
)
from auth import require_auth, is_authenticated, logout

# ── Initialise persistent storage on every startup ───────────────────────────
init_db()
seed_database()

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Fonts ─────────────────────────────────────────────── */
@import url('https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700&display=swap');

html, body, [class*="css"] {
    font-family: 'Satoshi', -apple-system, sans-serif !important;
}

/* ── Page background ────────────────────────────────────── */
.stApp {
    background-color: #0f1117 !important;
}

/* ── Hide Streamlit chrome ───────────────────────────────── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Tab bar ─────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    border-bottom: 1px solid #2a2d35;
    background: transparent;
    padding: 0;
    margin-bottom: 1.5rem;
}
.stTabs [data-baseweb="tab"] {
    font-size: 0.8125rem;
    font-weight: 500;
    letter-spacing: 0.02em;
    color: #6b7280;
    padding: 0.625rem 1.25rem;
    border-bottom: 2px solid transparent;
    background: transparent !important;
    border-radius: 0;
    transition: color 0.15s ease, border-color 0.15s ease;
}
.stTabs [aria-selected="true"] {
    color: #e2e8f0 !important;
    border-bottom: 2px solid #01696f !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #cbd5e1 !important;
}

/* ── KPI metric cards ────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #1a1d26;
    border: 1px solid #2a2d35;
    border-radius: 0.5rem;
    padding: 1rem 1.25rem;
    transition: border-color 0.15s ease;
}
[data-testid="metric-container"]:hover {
    border-color: #3a3d45;
}
[data-testid="metric-container"] label {
    font-size: 0.6875rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #6b7280 !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #e2e8f0 !important;
    font-variant-numeric: tabular-nums lining-nums;
    line-height: 1.2;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 0.75rem !important;
    font-weight: 500 !important;
}

/* ── Section headings ────────────────────────────────────── */
h1 {
    font-size: 1.375rem !important;
    font-weight: 700 !important;
    color: #e2e8f0 !important;
    letter-spacing: -0.01em;
    margin-bottom: 0.25rem !important;
}
h2 {
    font-size: 0.9375rem !important;
    font-weight: 600 !important;
    color: #cbd5e1 !important;
    margin-top: 1.5rem !important;
    margin-bottom: 0.75rem !important;
}
h3 {
    font-size: 0.8125rem !important;
    font-weight: 600 !important;
    color: #94a3b8 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

/* ── Data tables ─────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #2a2d35;
    border-radius: 0.5rem;
    overflow: hidden;
}
[data-testid="stDataFrame"] th {
    background: #1a1d26 !important;
    color: #6b7280 !important;
    font-size: 0.6875rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    padding: 0.625rem 0.75rem !important;
    border-bottom: 1px solid #2a2d35 !important;
}
[data-testid="stDataFrame"] td {
    font-size: 0.8125rem !important;
    color: #cbd5e1 !important;
    padding: 0.5rem 0.75rem !important;
    border-bottom: 1px solid #1e2028 !important;
    font-variant-numeric: tabular-nums lining-nums;
}
[data-testid="stDataFrame"] tr:hover td {
    background: #1e2130 !important;
}

/* ── Cards / containers ───────────────────────────────────── */
[data-testid="stExpander"] {
    background: #1a1d26;
    border: 1px solid #2a2d35 !important;
    border-radius: 0.5rem !important;
    margin-bottom: 0.375rem;
}
[data-testid="stExpander"]:hover {
    border-color: #3a3d45 !important;
}
[data-testid="stExpander"] summary {
    font-size: 0.8125rem !important;
    font-weight: 500 !important;
    color: #cbd5e1 !important;
    padding: 0.625rem 0.875rem !important;
}

/* ── Buttons ─────────────────────────────────────────────── */
.stButton > button {
    background: #01696f !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 0.375rem !important;
    font-size: 0.8125rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em;
    padding: 0.5rem 1rem !important;
    transition: background 0.15s ease !important;
}
.stButton > button:hover {
    background: #0c4e54 !important;
}
.stButton > button:active {
    background: #0f3638 !important;
}

/* ── Form inputs ─────────────────────────────────────────── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div,
.stTextArea > div > div > textarea,
.stDateInput > div > div > input {
    background: #1a1d26 !important;
    border: 1px solid #2a2d35 !important;
    border-radius: 0.375rem !important;
    color: #e2e8f0 !important;
    font-size: 0.8125rem !important;
    transition: border-color 0.15s ease !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #01696f !important;
    box-shadow: 0 0 0 2px rgba(1,105,111,0.2) !important;
}
.stTextInput label, .stNumberInput label,
.stSelectbox label, .stTextArea label,
.stDateInput label, .stCheckbox label {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.04em !important;
    color: #6b7280 !important;
    text-transform: uppercase !important;
}

/* ── Success / info / warning / error alerts ─────────────── */
[data-testid="stAlert"] {
    border-radius: 0.5rem !important;
    font-size: 0.8125rem !important;
    border-left-width: 3px !important;
}

/* ── Sidebar (admin panel) ───────────────────────────────── */
[data-testid="stSidebar"] {
    background: #13151e !important;
    border-right: 1px solid #2a2d35 !important;
}

/* ── Portfolio value chart ───────────────────────────────── */
[data-testid="stPlotlyChart"] {
    border: 1px solid #2a2d35;
    border-radius: 0.5rem;
    overflow: hidden;
}

/* ── Disclaimer banner ───────────────────────────────────── */
.disclaimer {
    background: #1a1d26;
    border: 1px solid #2a2d35;
    border-left: 3px solid #6b7280;
    border-radius: 0.375rem;
    padding: 0.625rem 1rem;
    font-size: 0.75rem;
    color: #6b7280;
    margin-top: 2rem;
    line-height: 1.5;
}

/* ── Info text / captions ────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] {
    font-size: 0.75rem !important;
    color: #6b7280 !important;
}

/* ── Dividers ────────────────────────────────────────────── */
hr {
    border-color: #2a2d35 !important;
    margin: 1.5rem 0 !important;
}

/* ── Logo / brand header ─────────────────────────────────── */
.brand-header {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 1.25rem 0 0.25rem;
}
.brand-name {
    font-size: 1.25rem;
    font-weight: 700;
    color: #e2e8f0;
    letter-spacing: -0.02em;
}
.brand-tagline {
    font-size: 0.75rem;
    color: #6b7280;
    margin-top: 0.125rem;
}
.brand-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #01696f;
    display: inline-block;
    margin-right: 2px;
    box-shadow: 0 0 6px rgba(1,105,111,0.6);
}

/* ── Last updated pill ───────────────────────────────────── */
.last-updated {
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    background: #1a1d26;
    border: 1px solid #2a2d35;
    border-radius: 9999px;
    padding: 0.25rem 0.75rem;
    font-size: 0.6875rem;
    color: #6b7280;
    margin-bottom: 1rem;
}
.last-updated::before {
    content: '';
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #01696f;
}

/* ── Number coloring ─────────────────────────────────────── */
.positive { color: #4ade80 !important; font-weight: 600; }
.negative { color: #f87171 !important; font-weight: 600; }
.neutral  { color: #94a3b8 !important; }

/* ── Plotly modebar ──────────────────────────────────────── */
.modebar-container { background: transparent !important; }
.modebar-btn path { fill: #6b7280 !important; }
.modebar-btn:hover path { fill: #e2e8f0 !important; }

</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kpi(label: str, value: str, css_class: str = "") -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value {css_class}">{value}</div>
    </div>"""

def _fmt_eur(v) -> str:
    if v is None: return "—"
    return f"€{v:,.0f}"

def _fmt_pct(v, decimals=2) -> str:
    if v is None: return "—"
    return f"{v:+.{decimals}f}%"

def _color_class(v) -> str:
    if v is None: return ""
    return "positive" if v >= 0 else "negative"


# ═════════════════════════════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════════════════════════════

col_title, col_admin = st.columns([8, 2])
with col_title:
    st.markdown(f"## 📊 {PORTFOLIO_NAME}")
    st.caption(PORTFOLIO_DESCRIPTION)

with col_admin:
    if is_authenticated():
        st.markdown(f"<span class='admin-badge'>⚙ Admin Mode</span>", unsafe_allow_html=True)
        if st.button("Log out", key="logout_top"):
            logout()
    else:
        if st.button("Admin Login", key="admin_login_btn"):
            st.session_state["show_login"] = True

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
# TAB LAYOUT
# ═════════════════════════════════════════════════════════════════════════════

tab_labels = ["📈 Overview", "🥧 Allocation", "📉 Performance", "📋 Holdings", "ℹ️ About"]
if is_authenticated():
    tab_labels.append("⚙️ Admin")

tabs = st.tabs(tab_labels)
tab_overview, tab_alloc, tab_perf, tab_holdings, tab_about = tabs[:5]
tab_admin = tabs[5] if is_authenticated() else None


# ── Load persistent data ──────────────────────────────────────────────────────
holdings_df_raw = get_holdings(active_only=True)
last_updated = get_meta("last_updated")
inception_date = get_meta("inception_date", "2024-01-15")

enriched = enrich_holdings(holdings_df_raw) if not holdings_df_raw.empty else pd.DataFrame()
ts_df = build_portfolio_timeseries(holdings_df_raw, inception_date) if not holdings_df_raw.empty else pd.DataFrame()
analytics = compute_analytics(ts_df) if not ts_df.empty else {}
contrib_df = compute_contributions(holdings_df_raw, inception_date) if not holdings_df_raw.empty else pd.DataFrame()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════

with tab_overview:
    if last_updated:
        st.caption(f"Last updated: {last_updated[:16].replace('T', ' ')} UTC")

    # KPI cards
    pv  = analytics.get("portfolio_value", BASE_CAPITAL)
    cr  = analytics.get("cumulative_return_pct")
    vol = analytics.get("annualised_volatility_pct")
    mdd = analytics.get("max_drawdown_pct")
    sr  = analytics.get("sharpe_ratio")
    n_holdings = len(holdings_df_raw)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: st.markdown(_kpi("Portfolio Value", _fmt_eur(pv)), unsafe_allow_html=True)
    with c2: st.markdown(_kpi("Cumulative Return", _fmt_pct(cr), _color_class(cr)), unsafe_allow_html=True)
    with c3: st.markdown(_kpi("Ann. Volatility", _fmt_pct(vol, 1) if vol else "—"), unsafe_allow_html=True)
    with c4: st.markdown(_kpi("Max Drawdown", _fmt_pct(mdd) if mdd else "—", "negative" if mdd and mdd < 0 else ""), unsafe_allow_html=True)
    with c5: st.markdown(_kpi("Sharpe Ratio", f"{sr:.2f}" if sr else "—"), unsafe_allow_html=True)
    with c6: st.markdown(_kpi("Holdings", str(n_holdings)), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Main chart
    if not ts_df.empty:
        st.plotly_chart(portfolio_line_chart(ts_df, BASE_CAPITAL), width="stretch")
    else:
        st.info("Price data is loading. Charts will appear once prices are fetched.")

    # Top contributors
    if not contrib_df.empty:
        st.markdown("<div class='section-header'>Top Contributors (Since Inception)</div>", unsafe_allow_html=True)
        st.plotly_chart(contribution_bar(contrib_df.head(10)), width="stretch")

    st.markdown(f"<div class='disclaimer'>{DISCLAIMER}</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — ALLOCATION
# ═════════════════════════════════════════════════════════════════════════════

with tab_alloc:
    if enriched.empty:
        st.info("No holdings found.")
    else:
        total_alloc = holdings_df_raw["eur_allocation"].sum()
        cash_buffer = BASE_CAPITAL - total_alloc

        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(_kpi("Base Capital", _fmt_eur(BASE_CAPITAL)), unsafe_allow_html=True)
        with c2: st.markdown(_kpi("Allocated", _fmt_eur(total_alloc)), unsafe_allow_html=True)
        with c3: st.markdown(_kpi("Unallocated Cash", _fmt_eur(cash_buffer)), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col_l, col_r = st.columns([1, 1])
        with col_l:
            st.plotly_chart(allocation_pie(enriched), width="stretch")
        with col_r:
            st.plotly_chart(allocation_treemap(enriched), width="stretch")

        st.plotly_chart(asset_class_bar(enriched), width="stretch")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — PERFORMANCE
# ═════════════════════════════════════════════════════════════════════════════

with tab_perf:
    if ts_df.empty:
        st.info("Insufficient price history to compute performance.")
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


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — HOLDINGS TABLE
# ═════════════════════════════════════════════════════════════════════════════

with tab_holdings:
    if enriched.empty:
        st.info("No holdings to display.")
    else:
        display_cols = {
            "ticker": "Ticker",
            "name": "Name",
            "asset_class": "Asset Class",
            "currency": "CCY",
            "eur_allocation": "Alloc (€)",
            "weight_pct": "Weight %",
            "latest_price_eur": "Price (EUR)",
            "current_value_eur": "Market Val (€)",
            "pnl_eur": "PnL (€)",
            "pnl_pct": "PnL %",
            "effective_date": "Since",
        }
        show_cols = [c for c in display_cols if c in enriched.columns]
        tbl = enriched[show_cols].copy()
        tbl.columns = [display_cols[c] for c in show_cols]

        # Style: colour PnL column
        def _style_pnl(val):
            if isinstance(val, (int, float)):
                return "color: #01696f; font-weight:500" if val >= 0 else "color: #a12c7b; font-weight:500"
            return ""

        styled = tbl.style.format({
            "Alloc (€)": "€{:,.0f}",
            "Weight %":  "{:.2f}%",
            "Price (EUR)": "€{:,.4f}",
            "Market Val (€)": "€{:,.0f}",
            "PnL (€)": lambda v: f"€{v:+,.0f}" if pd.notna(v) else "—",
            "PnL %": lambda v: f"{v:+.2f}%" if pd.notna(v) else "—",
        }).map(_style_pnl, subset=["PnL (€)", "PnL %"])

        st.dataframe(styled, width='stretch', hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — ABOUT
# ═════════════════════════════════════════════════════════════════════════════

with tab_about:
    st.markdown(f"""
### About This Portfolio

{PORTFOLIO_DESCRIPTION}

This is a **fictive model portfolio** built on a permanent base of **€{BASE_CAPITAL:,.0f}**.
It is not connected to any broker and does not represent real money.
The portfolio is manually maintained as a companion resource to
[the Substack publication]({SUBSTACK_URL}).

**Methodology**
- Allocations are expressed in euros, converted to weights by dividing by €100,000.
- Historical performance is calculated using daily close prices, with FX conversion to EUR where required.
- Data is sourced automatically via market data APIs (yfinance / OpenBB).

**Data & Pricing**
- Prices update automatically every 15 minutes while the app is open.
- Non-EUR assets are converted to EUR using live FX rates, clearly labelled in the holdings table.

**Inception Date:** {inception_date}

---

{DISCLAIMER}
    """)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 6 — ADMIN (authenticated only)
# ═════════════════════════════════════════════════════════════════════════════

# Login modal (shown when "Admin Login" clicked)
if not is_authenticated() and st.session_state.get("show_login"):
    with st.expander("🔐 Admin Login", expanded=True):
        from auth import login_form
        login_form()

if tab_admin is not None:
    with tab_admin:
        st.markdown("### ⚙️ Portfolio Management")
        st.caption("Changes save immediately to SQLite and persist across sessions.")

        # ── Add / Edit holding ────────────────────────────────────────────
        st.markdown("#### Add or Update Holding")

        from storage import save_holding, delete_holding, deactivate_holding

        with st.form("holding_form"):
            fc1, fc2, fc3 = st.columns(3)
            with fc1:
                f_ticker = st.text_input("Ticker *", help="e.g. AAPL, IWDA.AS, BTC-EUR").upper().strip()
                f_name   = st.text_input("Name *", help="Human-readable name")
                f_alloc  = st.number_input("EUR Allocation *", min_value=0.0, max_value=float(BASE_CAPITAL), step=500.0)
            with fc2:
                f_asset_class = st.selectbox("Asset Class", ["Equity", "ETF", "Bond ETF", "Crypto", "Cash", "Real Estate", "Commodity"])
                f_currency    = st.text_input("Currency", value="EUR", max_chars=3).upper()
                f_region      = st.text_input("Region", value="Global")
            with fc3:
                f_eff_date = st.date_input("Effective Date", value=date.today())
                f_active   = st.checkbox("Active", value=True)
                f_notes    = st.text_area("Notes / Thesis", height=70)

            st.markdown("**Optional: Override Entry Price (EUR)**")
            st.caption("Leave at 0.0 to auto-fetch the price on the effective date. Set manually if auto-fetch failed.")
            f_entry_price = st.number_input(
                "Entry Price (EUR per share/unit)",
                min_value=0.0, value=0.0, step=0.01, format="%.4f",
                help="The EUR price per unit at which this position was entered. Used to calculate P&L."
            )

            submitted = st.form_submit_button("💾 Save Holding", type="primary")

        if submitted:
            errors = []
            if not f_ticker: errors.append("Ticker is required.")
            if not f_name:   errors.append("Name is required.")
            if f_alloc <= 0: errors.append("EUR allocation must be greater than zero.")
            if len(f_currency) != 3: errors.append("Currency must be a 3-letter code.")

            # Validate total does not exceed BASE_CAPITAL
            existing = get_holdings(active_only=True)
            existing_excl = existing[existing["ticker"] != f_ticker]
            total_excl = existing_excl["eur_allocation"].sum()
            if total_excl + f_alloc > BASE_CAPITAL * 1.001:
                errors.append(
                    f"Total allocation ({_fmt_eur(total_excl + f_alloc)}) would exceed "
                    f"base capital ({_fmt_eur(BASE_CAPITAL)}). Reduce other positions first."
                )

            if errors:
                for e in errors:
                    st.error(e)
            else:
                from portfolio_engine import _get_closing_price_eur
                # Use manual entry price if provided, else auto-fetch
                if f_entry_price and f_entry_price > 0:
                    entry_px = f_entry_price
                else:
                    entry_px = _get_closing_price_eur(f_ticker, f_eff_date.isoformat(), f_currency)
                save_holding(
                    ticker=f_ticker, name=f_name, eur_allocation=f_alloc,
                    asset_class=f_asset_class, currency=f_currency, region=f_region,
                    effective_date=f_eff_date.isoformat(), active=f_active, notes=f_notes,
                    entry_price_eur=entry_px,
                )
                st.success(f"✅ {f_ticker} saved to database.")
                st.rerun()

        st.markdown("---")

        # ── Current holdings (admin view) ─────────────────────────────────
        st.markdown("#### Current Holdings")
        all_holdings = get_holdings(active_only=False)

        if all_holdings.empty:
            st.info("No holdings in database.")
        else:
            total_alloc = all_holdings[all_holdings["active"] == 1]["eur_allocation"].sum()
            remaining   = BASE_CAPITAL - total_alloc
            st.info(f"Total allocated: {_fmt_eur(total_alloc)} / {_fmt_eur(BASE_CAPITAL)}  |  Remaining: {_fmt_eur(remaining)}")

            for _, row in all_holdings.iterrows():
                with st.expander(
                    f"{'✅' if row['active'] else '❌'} {row['ticker']} — {row['name']} — {_fmt_eur(row['eur_allocation'])}",
                    expanded=False
                ):
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        st.write(f"**Asset Class:** {row.get('asset_class', '—')}")
                        st.write(f"**Currency:** {row.get('currency', '—')}")
                        st.write(f"**Region:** {row.get('region', '—')}")
                    with dc2:
                        st.write(f"**Effective Date:** {row.get('effective_date', '—')}")
                        st.write(f"**Notes:** {row.get('notes', '—')}")
                        st.write(f"**Active:** {bool(row['active'])}")

                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button(f"Deactivate {row['ticker']}", key=f"deact_{row['ticker']}"):
                            deactivate_holding(row["ticker"])
                            st.success(f"{row['ticker']} deactivated.")
                            st.rerun()
                    with btn_col2:
                        if st.button(f"🗑 Delete {row['ticker']}", key=f"del_{row['ticker']}"):
                            delete_holding(row["ticker"])
                            st.success(f"{row['ticker']} deleted.")
                            st.rerun()

        st.markdown("---")

        # ── Rebalance snapshot ────────────────────────────────────────────
        st.markdown("#### Create Rebalance Snapshot")
        st.caption("Saves a snapshot of current holdings for historical reference.")
        with st.form("rebalance_form"):
            rb_desc = st.text_input("Rebalance description", placeholder="Q1 2025 rebalance — added BTC position")
            rb_submit = st.form_submit_button("📸 Save Snapshot")
        if rb_submit:
            event_id = create_rebalance_snapshot(description=rb_desc)
            st.success(f"Snapshot saved (event #{event_id}).")

        # ── Rebalance history ─────────────────────────────────────────────
        from storage import get_rebalance_events, get_rebalance_items
        events_df = get_rebalance_events()
        if not events_df.empty:
            st.markdown("#### Rebalance History")
            for _, ev in events_df.iterrows():
                with st.expander(f"📅 {ev['event_date']} — {ev['description'] or 'No description'}", expanded=False):
                    items = get_rebalance_items(ev["id"])
                    if not items.empty:
                        st.dataframe(
                            items[["ticker", "name", "eur_allocation", "asset_class", "currency", "region"]],
                            hide_index=True, width="stretch"
                        )
