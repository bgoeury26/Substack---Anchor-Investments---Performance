"""
theme.py — Visual identity for the Anchor Investments dashboard.

Chart-room look: chart-paper background, deep navy, brass accents, the Anchor
Investments logo and a sailboat photograph (both in assets/). Holds the global
CSS, the artwork helpers and the HTML components. Colours used by Plotly live
in charts.py.

Every value that can originate from the ledger is escaped before rendering,
because notes and names are free text typed in the Admin forms.
"""

import base64
import re
from functools import lru_cache
from html import escape
from pathlib import Path

import pandas as pd

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500&family=Source+Sans+3:wght@400;500;600;700&display=swap');

:root {
  --paper: #F6F2E9; --surface: #FFFDF8; --ink: #14263C; --ink-2: #46566B; --ink-3: #5F6D82;
  --rule: #DDD5C4; --rule-soft: #EAE4D6; --navy: #0F2540; --brass: #B08A3E; --brass-lt: #D9BC7E;
  --sea: #24708C; --pos: #1F7A5C; --neg: #B0413A; --amber: #8A6414;
  --serif: 'Newsreader', Georgia, 'Times New Roman', serif;
  --sans: 'Source Sans 3', 'Source Sans', -apple-system, sans-serif;
}

/* Page: chart paper with a faint graticule */
[data-testid="stApp"] {
  background-color: var(--paper);
  background-image: linear-gradient(rgba(20,38,60,.03) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(20,38,60,.03) 1px, transparent 1px);
  background-size: 96px 96px;
}
[data-testid="stHeader"], #MainMenu, footer, .stDeployButton { display: none !important; }
.block-container { width: 100%; max-width: 1240px !important; margin: 0 auto; padding: 1.25rem 2rem 2.5rem !important; }
[data-testid="stHtml"] { font-family: var(--sans); color: var(--ink); }
hr { border-color: var(--rule) !important; }

/* Navigation */
.stTabs [data-baseweb="tab-list"] { gap: 1.75rem; }
.stTabs [data-baseweb="tab"] { padding: .7rem 0; background: transparent !important; }
.stTabs [data-baseweb="tab"] p { font-size: .98rem; font-weight: 500; color: var(--ink-3); transition: color .18s ease; }
.stTabs [data-baseweb="tab"]:hover p, .stTabs [aria-selected="true"] p { color: var(--ink); }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--brass) !important; height: 2px; }
.stTabs [data-baseweb="tab-border"] { background-color: var(--rule) !important; }

/* Controls */
.stButton > button, .stFormSubmitButton > button { transition: transform .12s ease, background-color .18s ease, border-color .18s ease; }
.stButton > button:active, .stFormSubmitButton > button:active { transform: translateY(1px); }
[data-testid="stExpander"] details { background: var(--surface); }
.st-key-login_panel { max-width: 380px; margin-left: auto; background: var(--surface); border: 1px solid var(--rule); border-radius: 10px; padding: 1.1rem 1.25rem; box-shadow: 0 16px 32px -22px rgba(15,37,64,.45); }
.st-key-about_prose p, .st-key-about_prose li { max-width: 65ch; line-height: 1.6; color: var(--ink-2); }
.st-key-about_prose strong { color: var(--ink); }

/* Brand bar */
.st-key-admin_login_btn, .st-key-logout_top { display: flex; justify-content: flex-end; }
.aw-brand { display: flex; align-items: center; gap: .9rem; }
.aw-logo { flex: none; display: block; height: 54px; width: auto; }
.aw-brand-sub { font-size: .86rem; color: var(--ink-3); border-left: 1px solid var(--rule); padding-left: .9rem; line-height: 1.5; white-space: nowrap; }
.aw-mark { display: block; height: auto; opacity: .55; }
.aw-toplink { text-align: right; font-size: .95rem; }
.aw-toplink a { color: var(--ink-2); text-decoration: none; border-bottom: 1px solid var(--brass-lt); padding-bottom: 1px; transition: color .18s ease, border-color .18s ease; }
.aw-toplink a:hover { color: var(--ink); border-color: var(--brass); }
.aw-admin-flag { display: block; text-align: right; font-size: .85rem; font-weight: 600; color: var(--sea); }

/* Hero */
.aw-hero { position: relative; overflow: hidden; border-radius: 14px; color: #F4EFE3; padding: 2.6rem 3rem 7.25rem; min-height: 25rem;
  background: linear-gradient(180deg, #0B1E35 0%, #15324F 100%); }
.aw-hero-photo { position: absolute; top: 0; right: 0; bottom: 0; width: 64%; height: 100%; object-fit: cover; object-position: 50% 69%; pointer-events: none;
  -webkit-mask-image: linear-gradient(90deg, transparent 8%, rgba(0,0,0,.03) 16%, rgba(0,0,0,.12) 24%, rgba(0,0,0,.3) 32%, rgba(0,0,0,.58) 41%, rgba(0,0,0,.84) 50%, #000 60%); mask-image: linear-gradient(90deg, transparent 8%, rgba(0,0,0,.03) 16%, rgba(0,0,0,.12) 24%, rgba(0,0,0,.3) 32%, rgba(0,0,0,.58) 41%, rgba(0,0,0,.84) 50%, #000 60%); }
.aw-hero-copy { position: relative; z-index: 4; max-width: min(34rem, 44%); }
.aw-eyebrow { font-size: .9rem; font-weight: 500; color: #C9D3DE; }
.aw-hero-value { font-family: var(--serif); font-size: clamp(3rem, 7vw, 4.9rem); font-weight: 400; letter-spacing: -.025em; line-height: 1.04; margin: .2rem 0 .5rem; font-variant-numeric: lining-nums tabular-nums; }
.aw-hero-meta { font-size: 1.02rem; color: #C9D3DE; }
.aw-hero-meta b { font-weight: 600; }
.aw-up { color: #93DDC2; } .aw-down { color: #F4AEA6; }
.aw-lede { font-family: var(--serif); font-size: 1.1rem; line-height: 1.45; color: #DCE3EA; margin: 1rem 0 0; max-width: 31rem; text-wrap: pretty; }

/* Figures strip */
.aw-strip { display: grid; grid-template-columns: repeat(auto-fit, minmax(128px, 1fr)); background: var(--surface); border: 1px solid var(--rule); border-radius: 10px; }
.aw-strip.lift { position: relative; z-index: 5; margin: -2.4rem 1.75rem 0; box-shadow: 0 18px 34px -24px rgba(15,37,64,.55); }
.aw-stat { padding: .95rem 1.2rem 1rem; border-left: 1px solid var(--rule-soft); }
.aw-stat:first-child { border-left: 0; }
.aw-stat-label { font-size: .86rem; color: var(--ink-3); }
.aw-stat-value { font-size: 1.42rem; font-weight: 600; letter-spacing: -.01em; color: var(--ink); font-variant-numeric: lining-nums tabular-nums; margin-top: .1rem; }
.aw-pos { color: var(--pos) !important; } .aw-neg { color: var(--neg) !important; }

/* Section headings */
.aw-section { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; flex-wrap: wrap; border-top: 1px solid var(--rule); padding-top: .85rem; margin-top: .9rem; }
.aw-section.flush { border-top: 0; padding-top: 0; margin-top: .15rem; }
.aw-section h3 { all: unset; font-family: var(--serif); font-size: 1.42rem; font-weight: 500; letter-spacing: -.012em; color: var(--ink); }
.aw-section span { font-size: .92rem; color: var(--ink-3); }

/* Ledger tables */
.aw-scroll { overflow-x: auto; }
.aw-table { width: 100%; border-collapse: collapse; font-size: .97rem; font-variant-numeric: lining-nums tabular-nums; color: var(--ink); }
.aw-table th { font-size: .86rem; font-weight: 500; color: var(--ink-3); text-align: right; padding: .45rem .7rem .55rem; border-bottom: 1px solid var(--ink); white-space: nowrap; }
.aw-table td { padding: .68rem .7rem; text-align: right; border-bottom: 1px solid var(--rule-soft); white-space: nowrap; }
.aw-table tbody tr { transition: background-color .15s ease; }
.aw-table tbody tr:hover { background: rgba(176,138,62,.08); }
.aw-table .l { text-align: left; }
.aw-table th:first-child, .aw-table td:first-child { padding-left: .2rem; }
.aw-table tfoot td { border-top: 1px solid var(--ink); border-bottom: 0; font-weight: 600; }
.aw-table .wrap { white-space: normal; min-width: 15rem; color: var(--ink-2); font-size: .92rem; line-height: 1.35; text-wrap: pretty; }
.aw-tk { font-weight: 600; } .aw-nm { display: block; font-size: .86rem; color: var(--ink-3); }
.aw-w { display: inline-flex; align-items: center; gap: .55rem; }
.aw-w i { display: block; width: 58px; height: 4px; background: var(--rule-soft); border-radius: 2px; overflow: hidden; }
.aw-w i b { display: block; height: 100%; background: var(--navy); border-radius: 2px; }
.aw-tag { display: inline-block; font-size: .8rem; font-weight: 600; padding: .08rem .42rem; border-radius: 3px; }
.aw-tag.BUY { color: #15365A; background: #DFE7EF; } .aw-tag.SELL { color: #8E2F29; background: #F6E1DD; }
.aw-tag.DEPOSIT { color: #155A72; background: #DCEDF2; } .aw-tag.WITHDRAWAL { color: var(--amber); background: #F4EAD2; }
.aw-tag.DIVIDEND { color: #1B6A50; background: #DDF0E8; } .aw-tag.FEE { color: var(--ink-2); background: #EAE6DC; }
.aw-stale { font-size: .78rem; font-weight: 600; color: var(--amber); margin-left: .35rem; }

/* Fact sheet, empty state, footer */
.aw-facts { background: var(--surface); border: 1px solid var(--rule); border-radius: 10px; padding: 1.35rem 1.5rem .75rem; }
.aw-facts img { display: block; margin: 0 auto .85rem; }
.aw-fact { display: flex; justify-content: space-between; gap: 1rem; padding: .55rem 0; border-top: 1px solid var(--rule-soft); font-size: .95rem; }
.aw-fact span { color: var(--ink-3); } .aw-fact b { font-weight: 600; text-align: right; }
.aw-empty { text-align: center; padding: 2.5rem 1rem; color: var(--ink-2); }
.aw-empty .aw-mark { margin: 0 auto; }
.aw-empty b { display: block; font-family: var(--serif); font-size: 1.3rem; font-weight: 500; color: var(--ink); margin: .5rem 0 .2rem; }
.aw-footer { margin-top: 1.75rem; color: var(--ink-3); font-size: .86rem; line-height: 1.5; }
.aw-footer img.line { display: block; width: 100%; height: 14px; margin-bottom: .85rem; }
.aw-footer-row { display: flex; gap: .7rem; align-items: flex-start; }
.aw-footer-row img { flex: none; margin-top: .1rem; }
.aw-footer p { margin: 0; max-width: 90ch; }

@media (max-width: 720px) {
  .block-container { padding: .85rem 1rem 2rem !important; }
  .aw-hero { padding: 1.75rem 1.4rem 14rem; min-height: 0; }
  .aw-hero-copy { max-width: none; }
  .aw-hero-photo { top: auto; left: 0; width: 100%; height: 270px; object-position: 100% 50%;
    -webkit-mask-image: linear-gradient(180deg, transparent 14%, rgba(0,0,0,.25) 26%, rgba(0,0,0,.7) 40%, #000 54%); mask-image: linear-gradient(180deg, transparent 14%, rgba(0,0,0,.25) 26%, rgba(0,0,0,.7) 40%, #000 54%); }
  .aw-brand-sub { display: none; }
  .aw-strip { grid-template-columns: repeat(2, 1fr); }
  .aw-strip.lift { margin: -1.75rem .6rem 0; }
  .aw-stat:nth-child(odd) { border-left: 0; }
  .aw-stat:nth-child(n+3) { border-top: 1px solid var(--rule-soft); }
  .aw-toplink { text-align: left; }
  .aw-admin-flag { text-align: left; }
  .st-key-admin_login_btn, .st-key-logout_top { justify-content: flex-start; }
  .st-key-login_panel { margin-left: 0; }
  .stTabs [data-baseweb="tab-list"] { gap: 1.1rem; }
}
</style>
"""

# ── Artwork ──────────────────────────────────────────────────────────────────


def _img(svg: str) -> str:
    """Return artwork as a data-URI <img>, because st.html strips inline <svg>."""
    head = svg.split(">", 1)[0]
    attrs = ""
    for name in ("class", "width", "height"):
        m = re.search(rf'\b{name}="([^"]*)"', head)
        if m:
            attrs += f' {name}="{m.group(1)}"'
    label = re.search(r'aria-label="([^"]*)"', head)
    encoded = base64.b64encode(svg.replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1).encode()).decode()
    return f'<img{attrs} alt="{label.group(1) if label else ""}" src="data:image/svg+xml;base64,{encoded}">'


@lru_cache(maxsize=None)
def _asset(name: str) -> str:
    """Return a file from assets/ as a data URI (st.html has no static file route)."""
    mime = "image/jpeg" if name.endswith(".jpg") else "image/png"
    data = (Path(__file__).parent / "assets" / name).read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def anchor_mark(size: int = 44) -> str:
    """The anchor from the Anchor Investments logo, as a quiet ornament."""
    return f'<img class="aw-mark" width="{size}" alt="" src="{_asset("logo_mark.png")}">'


def _compass_rose(size: int = 112) -> str:
    major = "".join(
        f'<g transform="rotate({a})"><path d="M0-44L7-7L0 0Z" fill="#0F2540"/><path d="M0-44L-7-7L0 0Z" fill="#B08A3E"/></g>'
        for a in (0, 90, 180, 270))
    minor = "".join(
        f'<g transform="rotate({a})"><path d="M0-29L5-5L0 0Z" fill="#7C8CA0"/><path d="M0-29L-5-5L0 0Z" fill="#D9BC7E"/></g>'
        for a in (45, 135, 225, 315))
    return _img(f'<svg width="{size}" height="{size}" viewBox="-54 -54 108 108" role="img" aria-label="Compass rose">'
            '<circle r="50" fill="none" stroke="#DDD5C4"/><circle r="36" fill="none" stroke="#EAE4D6"/>'
            f'{minor}{major}<circle r="3" fill="#FFFDF8" stroke="#0F2540"/></svg>')


# ── Formatting ───────────────────────────────────────────────────────────────


def _missing(v) -> bool:
    return v is None or pd.isna(v)


def fmt_eur(v, decimals: int = 0) -> str:
    if _missing(v):
        return "—"
    return f"{'−' if v < 0 else ''}€{abs(v):,.{decimals}f}"


def fmt_signed_eur(v) -> str:
    if _missing(v):
        return "—"
    return f"{'−' if v < 0 else '+'}€{abs(v):,.0f}"


def fmt_pct(v, decimals: int = 2) -> str:
    if _missing(v):
        return "—"
    return f"{'−' if v < 0 else '+'}{abs(v):.{decimals}f}%"


def fmt_date(v) -> str:
    if _missing(v) or v == "":
        return "—"
    ts = pd.Timestamp(v)
    return f"{ts.day} {ts:%b %Y}"


def tone(v) -> str:
    if _missing(v):
        return ""
    return "aw-pos" if v >= 0 else "aw-neg"


def _text(v, fallback: str = "—") -> str:
    return escape(str(v)) if not _missing(v) and v != "" else fallback


# ── Components ───────────────────────────────────────────────────────────────


def brand(name: str) -> str:
    return (f'<div class="aw-brand"><img class="aw-logo" alt="{escape(name, quote=True)}" src="{_asset("logo_lockup.png")}">'
            '<div class="aw-brand-sub">Model portfolio</div></div>')


def hero(value: float, cum_return, inception: str, description: str) -> str:
    if _missing(cum_return):
        meta = f"Tracking since {fmt_date(inception)}"
    else:
        cls = "aw-up" if cum_return >= 0 else "aw-down"
        meta = f'<b class="{cls}">{fmt_pct(cum_return)}</b> since inception on {fmt_date(inception)}'
    return (
        f'<section class="aw-hero"><img class="aw-hero-photo" alt="A sailboat on open water at dusk" src="{_asset("hero_sailboat.jpg")}">'
        f'<div class="aw-hero-copy"><div class="aw-eyebrow">Portfolio value</div>'
        f'<div class="aw-hero-value">{fmt_eur(value)}</div><div class="aw-hero-meta">{meta}</div>'
        f'<p class="aw-lede">{escape(description)}</p></div></section>'
    )


def kpi_strip(items, lift: bool = False) -> str:
    """items: (label, value) or (label, value, css_class)."""
    cells = "".join(
        f'<div class="aw-stat"><div class="aw-stat-label">{i[0]}</div>'
        f'<div class="aw-stat-value {i[2] if len(i) > 2 else ""}">{i[1]}</div></div>'
        for i in items)
    return f'<div class="aw-strip{" lift" if lift else ""}">{cells}</div>'


def section(title: str, note: str = "", flush: bool = False) -> str:
    aside = f"<span>{note}</span>" if note else ""
    return f'<div class="aw-section{" flush" if flush else ""}"><h3>{title}</h3>{aside}</div>'


def empty_state(title: str, body: str) -> str:
    return f'<div class="aw-empty">{anchor_mark(40)}<b>{title}</b>{body}</div>'


def holdings_table(df: pd.DataFrame) -> str:
    """df: open positions with a weight_pct column."""
    df = df.sort_values("market_value_eur", ascending=False, na_position="last")
    top = df["weight_pct"].max()
    top = top if not _missing(top) and top > 0 else 1.0
    rows = []
    for _, r in df.iterrows():
        bar = 0 if _missing(r["weight_pct"]) else r["weight_pct"] / top * 100
        weight = "—" if _missing(r["weight_pct"]) else f'{r["weight_pct"]:.1f}%'
        stale = '<span class="aw-stale" title="Last known price. Yahoo Finance did not respond on the latest refresh.">Stale</span>' if r.get("price_stale") else ""
        pnl = r["unrealized_pnl_eur"]
        qty = "—" if _missing(r["quantity"]) else f'{r["quantity"]:,.4f}'
        rows.append(
            f'<tr><td class="l"><span class="aw-tk">{_text(r["ticker"])}</span><span class="aw-nm">{_text(r["name"])}</span></td>'
            f'<td class="l">{_text(r["asset_class"])}</td><td class="l">{_text(r["currency"])}</td><td>{qty}</td>'
            f'<td>{fmt_eur(r["avg_cost_eur"], 2)}</td><td>{fmt_eur(r["spot_eur"], 2)}{stale}</td><td>{fmt_eur(r["market_value_eur"])}</td>'
            f'<td><span class="aw-w"><i><b style="width:{bar:.0f}%"></b></i>{weight}</span></td>'
            f'<td class="{tone(pnl)}">{fmt_signed_eur(pnl)}</td><td class="{tone(pnl)}">{fmt_pct(r["unrealized_pnl_pct"])}</td>'
            f'<td>{fmt_date(r["first_trade_date"])}</td></tr>'
        )
    cost = df["cost_basis_eur"].sum()
    value = df["market_value_eur"].sum()
    gain = df["unrealized_pnl_eur"].sum()
    gain_pct = gain / cost * 100 if cost > 0 else None
    return (
        '<div class="aw-scroll"><table class="aw-table"><thead><tr><th class="l">Holding</th><th class="l">Class</th><th class="l">CCY</th>'
        '<th>Quantity</th><th>Avg cost</th><th>Price</th><th>Value</th><th>Weight</th><th>P&amp;L</th><th>P&amp;L %</th><th>Since</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody><tfoot><tr><td class="l" colspan="6">Total invested</td><td>{fmt_eur(value)}</td><td></td>'
        f'<td class="{tone(gain)}">{fmt_signed_eur(gain)}</td><td class="{tone(gain)}">{fmt_pct(gain_pct)}</td><td></td></tr></tfoot></table></div>'
    )


def closed_table(df: pd.DataFrame) -> str:
    rows = "".join(
        f'<tr><td class="l"><span class="aw-tk">{_text(r["ticker"])}</span><span class="aw-nm">{_text(r["name"])}</span></td>'
        f'<td class="l">{_text(r["asset_class"])}</td><td class="{tone(r["realized_pnl_eur"])}">{fmt_signed_eur(r["realized_pnl_eur"])}</td>'
        f'<td>{fmt_date(r["first_trade_date"])}</td><td>{fmt_date(r["last_trade_date"])}</td></tr>'
        for _, r in df.iterrows())
    return ('<div class="aw-scroll"><table class="aw-table"><thead><tr><th class="l">Holding</th><th class="l">Class</th>'
            f'<th>Realized P&amp;L</th><th>First trade</th><th>Last trade</th></tr></thead><tbody>{rows}</tbody></table></div>')


def logbook(tx_df: pd.DataFrame) -> str:
    rows = []
    for _, r in tx_df.sort_values(["tx_date", "id"], ascending=False).iterrows():
        tx_type = str(r["tx_type"])
        qty = "—" if _missing(r["quantity"]) else f'{r["quantity"]:,.4f}'
        has_ticker = not _missing(r["ticker"]) and r["ticker"] != ""
        name = f'<span class="aw-nm">{_text(r["name"])}</span>' if has_ticker and not _missing(r["name"]) else ""
        instrument = f'<span class="aw-tk">{_text(r["ticker"])}</span>{name}' if has_ticker else "—"
        cash = r["cash_amount_eur"]
        rows.append(
            f'<tr><td class="l">{fmt_date(r["tx_date"])}</td><td class="l"><span class="aw-tag {escape(tx_type)}">{escape(tx_type.title())}</span></td>'
            f'<td class="l">{instrument}</td><td>{qty}</td><td>{fmt_eur(r["price_eur"], 2)}</td>'
            f'<td class="{tone(cash)}">{fmt_signed_eur(cash)}</td><td class="l wrap">{_text(r["notes"])}</td></tr>'
        )
    return ('<div class="aw-scroll"><table class="aw-table"><thead><tr><th class="l">Date</th><th class="l">Entry</th><th class="l">Holding</th>'
            f'<th>Quantity</th><th>Price</th><th>Cash impact</th><th class="l">Note</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def fact_sheet(facts) -> str:
    rows = "".join(f'<div class="aw-fact"><span>{escape(k)}</span><b>{escape(v)}</b></div>' for k, v in facts)
    return f'<div class="aw-facts">{_compass_rose()}{rows}</div>'


def footer(disclaimer: str) -> str:
    line = _img('<svg class="line" viewBox="0 0 1200 14" preserveAspectRatio="none" aria-hidden="true"><path fill="none" stroke="#DDD5C4" '
            'vector-effect="non-scaling-stroke" d="M0 7' + "".join(f"q25 -9 50 0t50 0" for _ in range(12)) + '"/></svg>')
    return (f'<div class="aw-footer">{line}<div class="aw-footer-row">{anchor_mark(20)}'
            f'<p>{escape(disclaimer)}</p></div></div>')
