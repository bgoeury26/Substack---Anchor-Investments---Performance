"""
charts.py — Plotly chart builders for the Anchor Investments dashboard.

Charts sit directly on the chart-paper background; section titles are rendered
by theme.section(), so figures carry no title of their own. The categorical
asset-class palette was validated against the paper surface for colour-vision
separation and contrast, and hues stay fixed per asset class.
"""

import plotly.graph_objects as go
import pandas as pd

# ── Palette ──────────────────────────────────────────────────────────────────
NAVY     = "#14304F"
SEA      = "#24708C"
PORT     = "#B0413A"
BRASS    = "#B08A3E"
SAND     = "#A79F8C"
INK      = "#14263C"
INK_SOFT = "#5F6D82"
GRID     = "#E6DFD0"
AXIS     = "#CFC6B3"
PAPER    = "#F6F2E9"
FONT     = "'Source Sans 3', 'Source Sans', sans-serif"

ASSET_CLASS_COLORS = {
    "Equity":      "#2B6CB0",
    "Crypto":      "#C07E12",
    "ETF":         "#159A9C",
    "Bond ETF":    "#8A5FC0",
    "Commodity":   "#7E8F1E",
    "Real Estate": "#C2527A",
    "Cash":        SAND,
}
_FALLBACK_CLASS = "#7C8CA0"

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


def _base_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    tick = dict(size=13, color=INK_SOFT, family=FONT)
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK_SOFT, size=13),
        margin=dict(l=4, r=8, t=8, b=8),
        hoverlabel=dict(bgcolor=NAVY, bordercolor=NAVY, font=dict(family=FONT, color="#F6F2E9", size=14), align="left"),
        legend=dict(orientation="h", x=1, xanchor="right", y=1.0, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)", font=dict(size=13, color=INK_SOFT)),
        xaxis=dict(showgrid=False, zeroline=False, tickfont=tick, linecolor=AXIS, ticks="", automargin=True),
        yaxis=dict(gridcolor=GRID, gridwidth=1, zeroline=False, tickfont=tick, showline=False, ticks="", automargin=True),
    )
    return fig


def _date_xaxis(fig: go.Figure) -> go.Figure:
    """Date axis with a shared crosshair and range buttons above the plot."""
    fig.update_layout(
        hovermode="x",
        margin=dict(l=4, r=8, t=46, b=8),
        xaxis=dict(
            type="date", rangeslider=dict(visible=False),
            showspikes=True, spikemode="across", spikesnap="cursor", spikecolor=AXIS, spikethickness=1, spikedash="solid",
            rangeselector=dict(
                x=0, xanchor="left", y=1.02, yanchor="bottom",
                bgcolor="rgba(0,0,0,0)", activecolor="#DCE4EB", borderwidth=0,
                font=dict(color=INK, size=13, family=FONT), buttons=_RANGE_BUTTONS,
            ),
        ),
    )
    return fig


def _empty(height: int = 300) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text="No data available", showarrow=False,
                       font=dict(size=14, color=INK_SOFT), xref="paper", yref="paper", x=0.5, y=0.5)
    fig = _base_layout(fig, height)
    fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig


def _value_range(series: pd.Series, extra: float = None) -> list:
    """Y-range hugging the data, so a line chart shows movement rather than a €0 floor."""
    low, high = float(series.min()), float(series.max())
    if extra is not None:
        low, high = min(low, extra), max(high, extra)
    pad = max((high - low) * 0.12, abs(high) * 0.005, 1.0)
    return [low - pad, high + pad]


# ── Portfolio value ──────────────────────────────────────────────────────────

def portfolio_line_chart(ts_df: pd.DataFrame, starting_cash: float) -> go.Figure:
    if ts_df.empty:
        return _empty()

    y_range = _value_range(ts_df["portfolio_value_eur"], starting_cash)
    fig = go.Figure(go.Scatter(
        x=ts_df["date"], y=ts_df["portfolio_value_eur"], mode="lines", name="Portfolio",
        line=dict(color=NAVY, width=2),
        fill="tozeroy",
        fillgradient=dict(type="vertical", start=y_range[0], stop=y_range[1],
                          colorscale=[(0, "rgba(36,112,140,0)"), (1, "rgba(36,112,140,0.26)")]),
        hovertemplate="%{x|%d %b %Y}<br><b>€%{y:,.0f}</b><extra></extra>",
    ))
    fig.add_hline(y=starting_cash, line_dash="dot", line_color=BRASS, line_width=1.25,
                  annotation_text=f"Starting cash €{starting_cash:,.0f}", annotation_position="bottom right",
                  annotation_font=dict(size=13, color=INK_SOFT, family=FONT))
    fig = _date_xaxis(_base_layout(fig, 400))
    fig.update_layout(showlegend=False, yaxis=dict(range=y_range, tickprefix="€", tickformat=",.0f"))
    return fig


def cash_vs_invested_chart(ts_df: pd.DataFrame) -> go.Figure:
    """Stacked area: invested (market) value and cash balance over time."""
    if ts_df.empty:
        return _empty()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["invested_eur"], mode="lines", name="Invested", stackgroup="one",
        line=dict(width=1.5, color=NAVY), fillcolor="rgba(20,48,79,0.82)",
        hovertemplate="Invested <b>€%{y:,.0f}</b><extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=ts_df["date"], y=ts_df["cash_eur"], mode="lines", name="Cash", stackgroup="one",
        line=dict(width=1.5, color=SAND), fillcolor="rgba(167,159,140,0.5)",
        hovertemplate="Cash <b>€%{y:,.0f}</b><extra></extra>",
    ))
    fig = _base_layout(fig, 340)
    fig.update_layout(hovermode="x unified", margin=dict(l=4, r=8, t=34, b=8),
                      xaxis=dict(type="date", hoverformat="%d %b %Y"),
                      yaxis=dict(tickprefix="€", tickformat=",.0f"))
    return fig


def return_line_chart(ts_df: pd.DataFrame) -> go.Figure:
    if ts_df.empty:
        return _empty(320)
    fig = go.Figure(go.Scatter(
        x=ts_df["date"], y=ts_df["cumulative_return_pct"], mode="lines", name="Cumulative return",
        line=dict(color=NAVY, width=2),
        hovertemplate="%{x|%d %b %Y}<br><b>%{y:+.2f}%</b><extra></extra>",
    ))
    fig.add_hline(y=0, line_color=AXIS, line_width=1)
    fig = _date_xaxis(_base_layout(fig, 320))
    fig.update_layout(showlegend=False, yaxis=dict(ticksuffix="%"))
    return fig


def drawdown_chart(ts_df: pd.DataFrame) -> go.Figure:
    if ts_df.empty:
        return _empty(260)
    vals = ts_df.set_index("date")["portfolio_value_eur"]
    rolling_max = vals.cummax()
    dd = (vals - rolling_max) / rolling_max * 100

    fig = go.Figure(go.Scatter(
        x=dd.index, y=dd.values, mode="lines", name="Drawdown",
        line=dict(color=PORT, width=1.75), fill="tozeroy", fillcolor="rgba(176,65,58,0.12)",
        hovertemplate="%{x|%d %b %Y}<br><b>%{y:.2f}%</b><extra></extra>",
    ))
    fig = _date_xaxis(_base_layout(fig, 260))
    fig.update_layout(showlegend=False, yaxis=dict(ticksuffix="%"))
    return fig


# ── Allocation ───────────────────────────────────────────────────────────────

def allocation_donut(positions_df: pd.DataFrame, cash_eur: float = 0.0) -> go.Figure:
    """Donut of current market value by asset class, with total in the centre."""
    if positions_df.empty and cash_eur <= 0:
        return _empty()

    totals = {}
    if not positions_df.empty:
        totals = positions_df.groupby("asset_class")["market_value_eur"].sum().to_dict()
    if cash_eur > 0:
        totals["Cash"] = totals.get("Cash", 0.0) + cash_eur
    items = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    labels = [k for k, _ in items]
    values = [v for _, v in items]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.68, sort=False, direction="clockwise",
        textinfo="percent", textposition="outside", texttemplate="%{percent:.1%}",
        textfont=dict(size=14, color=INK, family=FONT),
        marker=dict(colors=[ASSET_CLASS_COLORS.get(k, _FALLBACK_CLASS) for k in labels], line=dict(color=PAPER, width=3)),
        hovertemplate="%{label}<br><b>€%{value:,.0f}</b> · %{percent:.1%}<extra></extra>",
    ))
    fig.add_annotation(text=f"<span style='font-size:13px;color:{INK_SOFT}'>Total</span><br>€{sum(values):,.0f}",
                       showarrow=False, x=0.5, y=0.5, font=dict(family="Newsreader, Georgia, serif", size=25, color=INK))
    fig = _base_layout(fig, 400)
    fig.update_layout(margin=dict(l=20, r=20, t=24, b=12),
                      legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.04, yanchor="top"))
    return fig


def holdings_bar(positions_df: pd.DataFrame, cash_eur: float, portfolio_value: float) -> go.Figure:
    """Holdings by market value, largest first, coloured by asset class."""
    if positions_df.empty and cash_eur <= 0:
        return _empty()

    df = pd.DataFrame(columns=["ticker", "asset_class", "market_value_eur"])
    if not positions_df.empty:
        df = positions_df[["ticker", "asset_class", "market_value_eur"]].copy()
    if cash_eur > 0:
        df = pd.concat([df, pd.DataFrame([{"ticker": "Cash", "asset_class": "Cash", "market_value_eur": cash_eur}])], ignore_index=True)
    df["market_value_eur"] = df["market_value_eur"].fillna(0.0).astype(float)
    df = df.sort_values("market_value_eur")
    total = portfolio_value or 1.0

    fig = go.Figure()
    for asset_class, grp in df.groupby("asset_class", sort=False):
        fig.add_trace(go.Bar(
            x=grp["market_value_eur"], y=grp["ticker"], orientation="h", name=asset_class,
            marker=dict(color=ASSET_CLASS_COLORS.get(asset_class, _FALLBACK_CLASS), cornerradius=3),
            text=[f"€{v:,.0f}  ·  {v / total * 100:.1f}%" for v in grp["market_value_eur"]],
            textposition="outside", cliponaxis=False, textfont=dict(color=INK, size=13, family=FONT),
            hovertemplate="%{y}<br><b>€%{x:,.0f}</b><extra></extra>",
        ))
    fig = _base_layout(fig, max(360, len(df) * 44))
    fig.update_layout(
        bargap=0.42, margin=dict(l=4, r=118, t=34, b=8),
        xaxis=dict(visible=False),
        yaxis=dict(type="category", categoryorder="array", categoryarray=list(df["ticker"]), showgrid=False,
                   tickfont=dict(size=14, color=INK, family=FONT), ticksuffix="  "),
    )
    return fig


# ── Contribution ─────────────────────────────────────────────────────────────

def contribution_bar(contrib_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar of total (realized + unrealized) P&L by ticker."""
    if contrib_df.empty:
        return _empty()

    df = contrib_df.sort_values("total_pnl_eur")
    fig = go.Figure(go.Bar(
        x=df["total_pnl_eur"], y=df["ticker"], orientation="h",
        marker=dict(color=[SEA if v >= 0 else PORT for v in df["total_pnl_eur"]], cornerradius=3),
        text=[f"{'−' if v < 0 else '+'}€{abs(v):,.0f}" for v in df["total_pnl_eur"]],
        textposition="outside", cliponaxis=False, textfont=dict(color=INK, size=13, family=FONT),
        hovertemplate="%{y}<br><b>%{x:+,.0f} EUR</b><extra></extra>",
    ))
    fig.add_vline(x=0, line_color=AXIS, line_width=1)
    low, high = min(df["total_pnl_eur"].min(), 0.0), max(df["total_pnl_eur"].max(), 0.0)
    span = (high - low) or 1.0
    fig = _base_layout(fig, max(340, len(df) * 40))
    fig.update_layout(
        showlegend=False, bargap=0.42, margin=dict(l=4, r=8, t=34, b=8),
        xaxis=dict(visible=False, range=[low - span * 0.2 if low < 0 else 0, high + span * 0.24]),
        yaxis=dict(type="category", showgrid=False, tickfont=dict(size=14, color=INK, family=FONT), ticksuffix="  "),
    )
    return fig
