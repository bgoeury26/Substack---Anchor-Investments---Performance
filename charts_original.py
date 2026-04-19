"""
charts.py — Plotly chart builders for the portfolio dashboard.

All functions return go.Figure objects ready for st.plotly_chart().
Color palette aligns with a minimal investment research brand.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# ── Brand palette ─────────────────────────────────────────────────────────────
TEAL      = "#01696f"
TEAL_MUTED = "#4f98a3"
GOLD       = "#d19900"
WARM_RED   = "#a12c7b"
BEIGE_BG   = "#f7f6f2"
SURFACE    = "#f9f8f5"
TEXT_MAIN  = "#28251d"
TEXT_MUTED = "#7a7974"
BORDER     = "#d4d1ca"

ASSET_CLASS_COLORS = {
    "Equity":       "#01696f",
    "ETF":          "#4f98a3",
    "Bond ETF":     "#d19900",
    "Crypto":       "#da7101",
    "Cash":         "#bab9b4",
    "Real Estate":  "#a12c7b",
    "Commodity":    "#006494",
}


def _base_layout(fig: go.Figure, title: str = "", height: int = 420) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=TEXT_MAIN), x=0, xanchor="left"),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family="'Inter', 'Helvetica Neue', sans-serif", color=TEXT_MAIN, size=12),
        margin=dict(l=12, r=12, t=40 if title else 16, b=12),
        height=height,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=11, color=TEXT_MUTED),
        ),
        xaxis=dict(showgrid=False, zeroline=False, color=TEXT_MUTED, tickfont=dict(size=11)),
        yaxis=dict(gridcolor=BORDER, zeroline=False, color=TEXT_MUTED, tickfont=dict(size=11)),
    )
    return fig


# ── Portfolio value line chart ────────────────────────────────────────────────

def portfolio_line_chart(ts_df: pd.DataFrame, base_capital: float = 100_000) -> go.Figure:
    """Dual-axis chart: portfolio value (EUR) + cumulative return (%)."""
    if ts_df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data available", showarrow=False,
                           font=dict(size=14, color=TEXT_MUTED), xref="paper", yref="paper",
                           x=0.5, y=0.5)
        return _base_layout(fig, "Portfolio Value Over Time")

    fig = go.Figure()

    # Value line
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["portfolio_value"],
        mode="lines",
        name="Portfolio (EUR)",
        line=dict(color=TEAL, width=2.5),
        fill="tozeroy",
        fillcolor=f"rgba(1,105,111,0.08)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>€%{y:,.0f}<extra></extra>",
    ))

    # Base capital reference line
    fig.add_hline(
        y=base_capital,
        line_dash="dot",
        line_color=TEXT_MUTED,
        line_width=1,
        annotation_text="Base €100k",
        annotation_font_size=10,
        annotation_font_color=TEXT_MUTED,
    )

    fig = _base_layout(fig, "Portfolio Value (EUR)", height=380)
    fig.update_yaxes(tickprefix="€", tickformat=",.0f")
    fig.update_xaxes(showgrid=False)
    return fig


def return_line_chart(ts_df: pd.DataFrame) -> go.Figure:
    """Cumulative return % over time."""
    if ts_df.empty:
        return _base_layout(go.Figure(), "Cumulative Return (%)")

    positive = ts_df["cumulative_return_pct"] >= 0

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["cumulative_return_pct"],
        mode="lines",
        name="Cumulative Return",
        line=dict(color=TEAL, width=2),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y:+.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="solid", line_color=BORDER, line_width=1)

    fig = _base_layout(fig, "Cumulative Return (%)", height=280)
    fig.update_yaxes(ticksuffix="%")
    return fig


def drawdown_chart(ts_df: pd.DataFrame) -> go.Figure:
    """Drawdown from peak chart."""
    if ts_df.empty:
        return _base_layout(go.Figure(), "Drawdown from Peak")

    vals = ts_df.set_index("date")["portfolio_value"]
    rolling_max = vals.cummax()
    dd = (vals - rolling_max) / rolling_max * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        mode="lines",
        name="Drawdown",
        line=dict(color=WARM_RED, width=1.5),
        fill="tozeroy",
        fillcolor=f"rgba(161,44,123,0.10)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y:.2f}%<extra></extra>",
    ))
    fig = _base_layout(fig, "Drawdown from Peak (%)", height=220)
    fig.update_yaxes(ticksuffix="%")
    return fig


# ── Allocation charts ─────────────────────────────────────────────────────────

def allocation_pie(holdings_df: pd.DataFrame) -> go.Figure:
    """Donut chart of EUR allocation by ticker."""
    if holdings_df.empty:
        return _base_layout(go.Figure(), "Allocation")

    df = holdings_df.copy()
    colors = [ASSET_CLASS_COLORS.get(ac, TEAL_MUTED) for ac in df.get("asset_class", ["Equity"] * len(df))]

    fig = go.Figure(go.Pie(
        labels=df["ticker"],
        values=df["eur_allocation"],
        hole=0.52,
        texttemplate="%{label}<br>%{percent}",
        textfont=dict(size=11),
        marker=dict(colors=colors, line=dict(color=SURFACE, width=2)),
        hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>",
    ))
    fig = _base_layout(fig, "Allocation by Ticker", height=380)
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=40, b=0))
    return fig


def allocation_treemap(holdings_df: pd.DataFrame) -> go.Figure:
    """Treemap of allocation by asset class → ticker."""
    if holdings_df.empty:
        return _base_layout(go.Figure(), "Treemap")

    df = holdings_df.copy()
    df["asset_class"] = df.get("asset_class", pd.Series(["Equity"] * len(df)))

    fig = px.treemap(
        df,
        path=[px.Constant("Portfolio"), "asset_class", "ticker"],
        values="eur_allocation",
        color="asset_class",
        color_discrete_map=ASSET_CLASS_COLORS,
        custom_data=["name", "weight_pct"] if "weight_pct" in df.columns else ["name"],
    )
    fig.update_traces(
        texttemplate="<b>%{label}</b><br>€%{value:,.0f}",
        hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<extra></extra>",
        textfont_size=12,
    )
    fig = _base_layout(fig, "Allocation Treemap", height=400)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    return fig


# ── Contribution bar chart ────────────────────────────────────────────────────

def contribution_bar(contrib_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of contribution to total PnL (EUR)."""
    if contrib_df.empty:
        return _base_layout(go.Figure(), "Contribution to PnL")

    df = contrib_df.sort_values("contrib_eur")
    colors = [TEAL if v >= 0 else WARM_RED for v in df["contrib_eur"]]

    fig = go.Figure(go.Bar(
        x=df["contrib_eur"],
        y=df["ticker"],
        orientation="h",
        marker_color=colors,
        text=df["contrib_eur"].apply(lambda x: f"€{x:+,.0f}"),
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>%{x:+,.0f} EUR<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=BORDER, line_width=1)
    fig = _base_layout(fig, "Contribution to PnL (EUR, since inception)", height=max(280, len(df) * 36))
    fig.update_xaxes(tickprefix="€", tickformat=",.0f")
    return fig


# ── Asset class breakdown bar ─────────────────────────────────────────────────

def asset_class_bar(holdings_df: pd.DataFrame) -> go.Figure:
    if holdings_df.empty:
        return _base_layout(go.Figure(), "By Asset Class")

    df = (holdings_df.groupby("asset_class")["eur_allocation"]
          .sum().reset_index().sort_values("eur_allocation", ascending=False))
    colors = [ASSET_CLASS_COLORS.get(ac, TEAL_MUTED) for ac in df["asset_class"]]

    fig = go.Figure(go.Bar(
        x=df["asset_class"],
        y=df["eur_allocation"],
        marker_color=colors,
        text=df["eur_allocation"].apply(lambda v: f"€{v:,.0f}"),
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>€%{y:,.0f}<extra></extra>",
    ))
    fig = _base_layout(fig, "Allocation by Asset Class (EUR)", height=300)
    fig.update_yaxes(tickprefix="€", tickformat=",.0f")
    return fig
