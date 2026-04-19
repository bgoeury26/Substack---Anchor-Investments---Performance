"""
charts.py — Plotly chart builders for the portfolio dashboard.

All functions return go.Figure objects ready for st.plotly_chart().
Dark theme aligned with a minimal investment research brand.
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# ── Brand palette ──────────────────────────────────────────────────────────────
TEAL        = "#01696f"
TEAL_MUTED  = "#4f98a3"
GOLD        = "#d19900"
WARM_RED    = "#a12c7b"

# ── Dark theme surfaces ────────────────────────────────────────────────────────
CHART_BG    = "#0f1117"
CHART_PAPER = "#0f1117"
CHART_GRID  = "#1e2130"
CHART_LINE  = "#2a2d35"
CHART_TEXT  = "#94a3b8"
CHART_TEXT_DIM = "#4b5563"

ASSET_CLASS_COLORS = {
    "Equity":       "#01696f",
    "ETF":          "#4f98a3",
    "Bond ETF":     "#d19900",
    "Crypto":       "#da7101",
    "Cash":         "#6b7280",
    "Real Estate":  "#a12c7b",
    "Commodity":    "#006494",
}


def _base_layout(fig: go.Figure, title: str = "", height: int = 420) -> go.Figure:
    fig.update_layout(
        title=dict(
            text=title,
            font=dict(size=13, color=CHART_TEXT, family="Satoshi, sans-serif"),
            x=0, xanchor="left",
        ),
        paper_bgcolor=CHART_PAPER,
        plot_bgcolor=CHART_BG,
        font=dict(family="Satoshi, sans-serif", color=CHART_TEXT, size=12),
        margin=dict(l=12, r=12, t=44 if title else 16, b=12),
        height=height,
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=11, color=CHART_TEXT),
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
        ),
        yaxis=dict(
            gridcolor=CHART_GRID,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
        ),
    )
    return fig


# ── Portfolio value line chart ─────────────────────────────────────────────────

def portfolio_line_chart(ts_df: pd.DataFrame, base_capital: float = 100_000) -> go.Figure:
    """Area line chart: portfolio value (EUR) with time-range selector."""
    if ts_df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available", showarrow=False,
            font=dict(size=14, color=CHART_TEXT),
            xref="paper", yref="paper", x=0.5, y=0.5,
        )
        return _base_layout(fig, "Portfolio Value Over Time")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["portfolio_value"],
        mode="lines",
        name="Portfolio (EUR)",
        line=dict(color=TEAL, width=2.5),
        fill="tozeroy",
        fillcolor="rgba(1,105,111,0.10)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>€%{y:,.0f}<extra></extra>",
    ))

    fig.add_hline(
        y=base_capital,
        line_dash="dot",
        line_color=CHART_TEXT_DIM,
        line_width=1,
        annotation_text="Base €100k",
        annotation_font_size=10,
        annotation_font_color=CHART_TEXT_DIM,
    )

    fig = _base_layout(fig, "Portfolio Value (EUR)", height=380)

    fig.update_layout(
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
            type="date",
            rangeslider=dict(visible=False),
            rangeselector=dict(
                bgcolor="#1a1d26",
                activecolor=TEAL,
                bordercolor=CHART_LINE,
                borderwidth=1,
                font=dict(color=CHART_TEXT, size=11),
                buttons=[
                    dict(count=7,  label="1W",  step="day",   stepmode="backward"),
                    dict(count=1,  label="1M",  step="month", stepmode="backward"),
                    dict(count=1,  label="MTD", step="month", stepmode="todate"),
                    dict(count=3,  label="3M",  step="month", stepmode="backward"),
                    dict(count=6,  label="6M",  step="month", stepmode="backward"),
                    dict(count=1,  label="YTD", step="year",  stepmode="todate"),
                    dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
                    dict(step="all", label="All"),
                ],
            ),
        ),
        yaxis=dict(
            gridcolor=CHART_GRID,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
            tickprefix="€",
            tickformat=",.0f",
        ),
    )
    return fig


def return_line_chart(ts_df: pd.DataFrame) -> go.Figure:
    """Cumulative return % over time."""
    if ts_df.empty:
        return _base_layout(go.Figure(), "Cumulative Return (%)")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["cumulative_return_pct"],
        mode="lines",
        name="Cumulative Return",
        line=dict(color=TEAL, width=2),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y:+.2f}%<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="solid", line_color=CHART_LINE, line_width=1)

    fig = _base_layout(fig, "Cumulative Return (%)", height=280)
    fig.update_layout(
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
            type="date",
            rangeslider=dict(visible=False),
            rangeselector=dict(
                bgcolor="#1a1d26",
                activecolor=TEAL,
                bordercolor=CHART_LINE,
                borderwidth=1,
                font=dict(color=CHART_TEXT, size=11),
                buttons=[
                    dict(count=7,  label="1W",  step="day",   stepmode="backward"),
                    dict(count=1,  label="1M",  step="month", stepmode="backward"),
                    dict(count=1,  label="MTD", step="month", stepmode="todate"),
                    dict(count=3,  label="3M",  step="month", stepmode="backward"),
                    dict(count=6,  label="6M",  step="month", stepmode="backward"),
                    dict(count=1,  label="YTD", step="year",  stepmode="todate"),
                    dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
                    dict(step="all", label="All"),
                ],
            ),
        ),
        yaxis=dict(
            gridcolor=CHART_GRID,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
            ticksuffix="%",
        ),
    )
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
        fillcolor="rgba(161,44,123,0.12)",
        hovertemplate="<b>%{x|%d %b %Y}</b><br>%{y:.2f}%<extra></extra>",
    ))
    fig = _base_layout(fig, "Drawdown from Peak (%)", height=220)
    fig.update_layout(
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
            type="date",
            rangeslider=dict(visible=False),
            rangeselector=dict(
                bgcolor="#1a1d26",
                activecolor=TEAL,
                bordercolor=CHART_LINE,
                borderwidth=1,
                font=dict(color=CHART_TEXT, size=11),
                buttons=[
                    dict(count=7,  label="1W",  step="day",   stepmode="backward"),
                    dict(count=1,  label="1M",  step="month", stepmode="backward"),
                    dict(count=1,  label="MTD", step="month", stepmode="todate"),
                    dict(count=3,  label="3M",  step="month", stepmode="backward"),
                    dict(count=6,  label="6M",  step="month", stepmode="backward"),
                    dict(count=1,  label="YTD", step="year",  stepmode="todate"),
                    dict(count=1,  label="1Y",  step="year",  stepmode="backward"),
                    dict(step="all", label="All"),
                ],
            ),
        ),
        yaxis=dict(
            gridcolor=CHART_GRID,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
            ticksuffix="%",
        ),
    )
    return fig


# ── Allocation charts ──────────────────────────────────────────────────────────

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
        textfont=dict(size=11, color="#e2e8f0"),
        marker=dict(colors=colors, line=dict(color=CHART_BG, width=2)),
        hovertemplate="<b>%{label}</b><br>€%{value:,.0f}<br>%{percent}<extra></extra>",
    ))
    fig = _base_layout(fig, "Allocation by Ticker", height=380)
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=40, b=0),
    )
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
        textfont_color="#e2e8f0",
    )
    fig = _base_layout(fig, "Allocation Treemap", height=400)
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    return fig


# ── Contribution bar chart ─────────────────────────────────────────────────────

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
        textfont=dict(color=CHART_TEXT, size=11),
        hovertemplate="<b>%{y}</b><br>%{x:+,.0f} EUR<extra></extra>",
    ))
    fig.add_vline(x=0, line_color=CHART_LINE, line_width=1)
    fig = _base_layout(
        fig,
        "Contribution to PnL (EUR, since inception)",
        height=max(280, len(df) * 36),
    )
    fig.update_layout(
        xaxis=dict(
            showgrid=True,
            gridcolor=CHART_GRID,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
            tickprefix="€",
            tickformat=",.0f",
        ),
    )
    return fig


# ── Asset class breakdown bar ──────────────────────────────────────────────────

def asset_class_bar(holdings_df: pd.DataFrame) -> go.Figure:
    if holdings_df.empty:
        return _base_layout(go.Figure(), "By Asset Class")

    df = (
        holdings_df.groupby("asset_class")["eur_allocation"]
        .sum().reset_index().sort_values("eur_allocation", ascending=False)
    )
    colors = [ASSET_CLASS_COLORS.get(ac, TEAL_MUTED) for ac in df["asset_class"]]

    fig = go.Figure(go.Bar(
        x=df["asset_class"],
        y=df["eur_allocation"],
        marker_color=colors,
        text=df["eur_allocation"].apply(lambda v: f"€{v:,.0f}"),
        textposition="outside",
        textfont=dict(color=CHART_TEXT, size=11),
        hovertemplate="<b>%{x}</b><br>€%{y:,.0f}<extra></extra>",
    ))
    fig = _base_layout(fig, "Allocation by Asset Class (EUR)", height=300)
    fig.update_layout(
        yaxis=dict(
            gridcolor=CHART_GRID,
            zeroline=False,
            color=CHART_TEXT,
            tickfont=dict(size=11, color=CHART_TEXT),
            linecolor=CHART_LINE,
            tickprefix="€",
            tickformat=",.0f",
        ),
    )
    return fig
