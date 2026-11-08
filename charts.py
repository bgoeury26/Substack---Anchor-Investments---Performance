"""
charts.py — Plotly chart builders for the Anchor Investments dashboard.
Same dark, minimal brand as the original app; field names updated for the
transaction-based data model (portfolio_value_eur, cash_eur, invested_eur,
market_value_eur, unrealized_pnl_eur, total_pnl_eur, ...).
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# ── Brand palette ────────────────────────────────────────────────────────────
TEAL        = "#01696f"
TEAL_MUTED  = "#4f98a3"
GOLD        = "#d19900"
WARM_RED    = "#a12c7b"
CASH_COLOR  = "#6b7280"

CHART_BG       = "#0f1117"
CHART_PAPER    = "#0f1117"
CHART_GRID     = "#1e2130"
CHART_LINE     = "#2a2d35"
CHART_TEXT     = "#94a3b8"
CHART_TEXT_DIM = "#4b5563"

ASSET_CLASS_COLORS = {
    "Equity":      "#01696f",
    "ETF":         "#4f98a3",
    "Bond ETF":    "#d19900",
    "Crypto":      "#da7101",
    "Cash":        "#6b7280",
    "Real Estate": "#a12c7b",
    "Commodity":   "#006494",
}

_RANGE_BUTTONS = [
    dict(count=7,  label="1W",  step="day",   stepmode="backward"),
    dict(count=1,  label="1M",  step="month", stepmode="backward"),
    dict(count=1,  label="MTD", step="month", stepmode="todate"),
    dict(count=3,  label="3M",  step="month", stepmode="backward"),
    dict(count=6,  label="6M",  step="month", stepmode="backward"),
    dict(count=1,  label="YTD", step="year",  stepmode="todate"),
    dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
    dict(step="all", label="All"),
]


def _base_layout(fig: go.Figure, title: str = "", height: int = 420) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=CHART_TEXT, family="Satoshi, sans-serif"), x=0, xanchor="left"),
        paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG,
        font=dict(family="Satoshi, sans-serif", color=CHART_TEXT, size=12),
        margin=dict(l=12, r=12, t=44 if title else 16, b=12),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(size=11, color=CHART_TEXT)),
        xaxis=dict(showgrid=False, zeroline=False, color=CHART_TEXT, tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE),
        yaxis=dict(gridcolor=CHART_GRID, zeroline=False, color=CHART_TEXT, tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE),
    )
    return fig


def _date_xaxis(fig: go.Figure) -> go.Figure:
    fig.update_layout(xaxis=dict(
        showgrid=False, zeroline=False, color=CHART_TEXT,
        tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE,
        type="date", rangeslider=dict(visible=False),
        rangeselector=dict(
            bgcolor="#1a1d26", activecolor=TEAL, bordercolor=CHART_LINE, borderwidth=1,
            font=dict(color=CHART_TEXT, size=11), buttons=_RANGE_BUTTONS,
        ),
    ))
    return fig


def _empty(title: str, height: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text="No data available", showarrow=False,
                        font=dict(size=14, color=CHART_TEXT), xref="paper", yref="paper", x=0.5, y=0.5)
    return _base_layout(fig, title, height)


# ── Portfolio value ──────────────────────────────────────────────────────────

def portfolio_line_chart(ts_df: pd.DataFrame, starting_cash: float) -> go.Figure:
    if ts_df.empty:
        return _empty("Portfolio Value Over Time")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["portfolio_value_eur"], mode="lines", name="Portfolio (EUR)",
        line=dict(color=TEAL, width=2.5), fill="tozeroy", fillcolor="rgba(1,105,111,0.10)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>€%{y:,.0f}<extra></extra>",
    ))
    fig.add_hline(y=starting_cash, line_dash="dot", line_color=CHART_TEXT_DIM, line_width=1,
                  annotation_text=f"Starting cash €{starting_cash:,.0f}",
                  annotation_font_size=10, annotation_font_color=CHART_TEXT_DIM)

    fig = _base_layout(fig, "Portfolio Value (EUR)", height=380)
    fig = _date_xaxis(fig)
    fig.update_layout(yaxis=dict(gridcolor=CHART_GRID, zeroline=False, color=CHART_TEXT,
                                  tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE,
                                  tickprefix="€", tickformat=",.0f"))
    return fig


def cash_vs_invested_chart(ts_df: pd.DataFrame) -> go.Figure:
    """Stacked area: cash balance vs. invested (market) value over time —
    the direct visual of the buy/sell cash-management system."""
    if ts_df.empty:
        return _empty("Cash vs. Invested")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["invested_eur"], mode="lines", name="Invested",
        stackgroup="one", line=dict(width=0.5, color=TEAL), fillcolor="rgba(1,105,111,0.55)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Invested: €%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["cash_eur"], mode="lines", name="Cash",
        stackgroup="one", line=dict(width=0.5, color=CASH_COLOR), fillcolor="rgba(107,114,128,0.45)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Cash: €%{y:,.0f}<extra></extra>",
    ))
    fig = _base_layout(fig, "Cash vs. Invested (EUR)", height=320)
    fig = _date_xaxis(fig)
    fig.update_layout(yaxis=dict(gridcolor=CHART_GRID, zeroline=False, color=CHART_TEXT,
                                  tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE,
                                  tickprefix="€", tickformat=",.0f"))
    return fig


def return_line_chart(ts_df: pd.DataFrame) -> go.Figure:
    if ts_df.empty:
        return _empty("Cumulative Return (%)", 280)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["cumulative_return_pct"], mode="lines", name="Cumulative Return",
        line=dict(color=TEAL, width=2),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y:+.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="solid", line_color=CHART_LINE, line_width=1)
    fig = _base_layout(fig, "Cumulative Return (%)", height=280)
    fig = _date_xaxis(fig)
    fig.update_layout(yaxis=dict(gridcolor=CHART_GRID, zeroline=False, color=CHART_TEXT,
                                  tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE, ticksuffix="%"))
    return fig


def drawdown_chart(ts_df: pd.DataFrame) -> go.Figure:
    if ts_df.empty:
        return _empty("Drawdown from Peak", 220)
    vals = ts_df.set_index("date")["portfolio_value_eur"]
    rolling_max = vals.cummax()
    dd = (vals - rolling_max) / rolling_max * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values, mode="lines", name="Drawdown",
        line=dict(color=WARM_RED, width=1.5), fill="tozeroy", fillcolor="rgba(161,44,123,0.12)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y:.2f}%<extra></extra>",
    ))
    fig = _base_layout(fig, "Drawdown from Peak (%)", height=220)
    fig = _date_xaxis(fig)
    fig.update_layout(yaxis=dict(gridcolor=CHART_GRID, zeroline=False, color=CHART_TEXT,
                                  tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE, ticksuffix="%"))
    return fig


# ── Allocation ───────────────────────────────────────────────────────────────

def allocation_pie(positions_df: pd.DataFrame, cash_eur: float = 0.0) -> go.Figure:
    """Donut of current market value by ticker, plus a Cash slice."""
    if positions_df.empty and cash_eur <= 0:
        return _empty("Allocation")

    labels = list(positions_df["ticker"]) if not positions_df.empty else []
    values = list(positions_df["market_value_eur"].fillna(0)) if not positions_df.empty else []
    colors = [ASSET_CLASS_COLORS.get(ac, TEAL_MUTED) for ac in positions_df.get("asset_class", [])] if not positions_df.empty else []

    if cash_eur > 0:
        labels.append("CASH")
        values.append(cash_eur)
        colors.append(ASSET_CLASS_COLORS["Cash"])

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.52,
        texttemplate="%{label}<br>%{percent}", textfont=dict(size=11, color="#e2e8f0"),
        marker=dict(colors=colors, line=dict(color=CHART_BG, width=2)),
        hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>",
    ))
    fig = _base_layout(fig, "Allocation by Ticker", height=380)
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def allocation_treemap(positions_df: pd.DataFrame, cash_eur: float = 0.0) -> go.Figure:
    if positions_df.empty and cash_eur <= 0:
        return _empty("Treemap")

    df = positions_df.copy()
    if not df.empty:
        df = df.rename(columns={"market_value_eur": "value"})[["ticker", "name", "asset_class", "value"]]
    else:
        df = pd.DataFrame(columns=["ticker", "name", "asset_class", "value"])

    if cash_eur > 0:
        df = pd.concat([df, pd.DataFrame([{
            "ticker": "CASH", "name": "Cash", "asset_class": "Cash", "value": cash_eur
        }])], ignore_index=True)

    fig = px.treemap(
        df, path=[px.Constant("Portfolio"), "asset_class", "ticker"], values="value",
        color="asset_class", color_discrete_map=ASSET_CLASS_COLORS, custom_data=["name"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>€%{value:,.0f}",
        hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<extra></extra>",
        textfont_size=12, textfont_color="#e2e8f0",
    )
    fig = _base_layout(fig, "Allocation Treemap", height=400)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    return fig


def asset_class_bar(positions_df: pd.DataFrame, cash_eur: float = 0.0) -> go.Figure:
    if positions_df.empty and cash_eur <= 0:
        return _empty("By Asset Class", 300)

    rows = []
    if not positions_df.empty:
        g = positions_df.groupby("asset_class")["market_value_eur"].sum().reset_index()
        rows = g.to_dict("records")
    if cash_eur > 0:
        rows.append({"asset_class": "Cash", "market_value_eur": cash_eur})

    df = pd.DataFrame(rows).sort_values("market_value_eur", ascending=False)
    colors = [ASSET_CLASS_COLORS.get(ac, TEAL_MUTED) for ac in df["asset_class"]]

    fig = go.Figure(go.Bar(
        x=df["asset_class"], y=df["market_value_eur"], marker_color=colors,
        text=df["market_value_eur"].apply(lambda v: f"€{v:,.0f}"), textposition="outside",
        textfont=dict(color=CHART_TEXT, size=11),
        hovertemplate="<b>%{x}</b><br>€%{y:,.0f}<extra></extra>",
    ))
    fig = _base_layout(fig, "Allocation by Asset Class (EUR)", height=300)
    fig.update_layout(yaxis=dict(gridcolor=CHART_GRID, zeroline=False, color=CHART_TEXT,
                                  tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE,
                                  tickprefix="€", tickformat=",.0f"))
    return fig


# ── Contribution ─────────────────────────────────────────────────────────────

def contribution_bar(contrib_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar of total (realized + unrealized) P&L by ticker."""
    if contrib_df.empty:
        return _empty("Contribution to P&L")

    df = contrib_df.sort_values("total_pnl_eur")
    colors = [TEAL if v >= 0 else WARM_RED for v in df["total_pnl_eur"]]

    fig = go.Figure(go.Bar(
        x=df["total_pnl_eur"], y=df["ticker"], orientation="h", marker_color=colors,
        text=df["total_pnl_eur"].apply(lambda x: f"€{x:+,.0f}"), textposition="outside",
        textfont=dict(color=CHART_TEXT, size=11),
        hovertemplate="<b>%{y}</b><br>%{x:+,.0f} EUR<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=CHART_LINE, line_width=1)
    fig = _base_layout(fig, "Contribution to P&L (EUR, realized + unrealized)", height=max(280, len(df) * 36))
    fig.update_layout(xaxis=dict(showgrid=True, gridcolor=CHART_GRID, zeroline=False, color=CHART_TEXT,
                                  tickfont=dict(size=11, color=CHART_TEXT), linecolor=CHART_LINE,
                                  tickprefix="€", tickformat=",.0f"))
    return fig
