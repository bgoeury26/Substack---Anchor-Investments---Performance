# 📊 Anchor Investments — Portfolio Dashboard v2

A rebuild of the original allocation-based dashboard as a **real transactional
cash-management system**: every Buy debits cash, every Sell credits it,
Deposits and Withdrawals move cash directly — the same mental model as a
brokerage account or the Yahoo Finance portfolio view. Prices are pulled
live from Yahoo Finance.

- **Cash ledger:** append-only transaction log; cash balance and positions are
  both *derived* from it, so they can never drift apart.
- **Persistent storage:** SQLite (local dev) or Postgres (production —
  SQLAlchemy, same code either way).
- **Market data:** yfinance (default) or OpenBB, batched into one request per
  refresh, with automatic fallback to the last known-good price if Yahoo
  rate-limits the request.
- **Admin auth:** bcrypt-hashed password + short lockout after repeated
  failed logins.
- **Charts:** Plotly (portfolio value, cash-vs-invested, drawdown, allocation,
  contribution).

---

## What changed vs. the original app

The original app modeled a **fixed €100,000 split across static
allocations** — "Allocation tab" showed Base Capital / Allocated /
Unallocated Cash, but there was no actual Buy or Sell action anywhere, and
the "Changes" tab was permanently empty ("No position updates logged yet").
It also called Yahoo Finance once per ticker per page load, which is exactly
what triggered the "Too Many Requests. Rate limited." error visible on the
live site.

This version:

1. **Replaces the allocation model with a real trade ledger.** Admin → Trade
   (Buy/Sell) logs an actual transaction; cash balance updates immediately.
   Admin → Deposit/Withdraw moves cash directly, same as topping up a
   brokerage account.
2. **Fixes the rate-limiting failure mode.** All holdings' prices are fetched
   in a single batched call instead of one call per ticker, and a
   last-known-good price is cached and used as a fallback (flagged as
   "stale" in the UI) instead of showing a blank value.
3. **Makes the Changes tab a real audit trail** — every trade, deposit, and
   withdrawal, not a feature that was never wired up.
4. **Adds Postgres support** so Streamlit Community Cloud's ephemeral
   filesystem doesn't silently erase your trade history on redeploy (see
   Deployment below — this needs a few minutes of manual setup on your side,
   I can't create the database account for you).

---

## Folder Structure

```
anchor-investments/
├── app.py                 # Streamlit entry point
├── config.py               # Config (Streamlit secrets → env → defaults)
├── db.py                    # SQLAlchemy persistence layer (SQLite/Postgres)
├── auth.py                  # Admin authentication (bcrypt + lockout)
├── data_loader.py           # Market data (batched, cached, fallback-safe)
├── portfolio_engine.py      # Cash/position ledger math, performance
├── charts.py                # Plotly chart builders
├── migrate_legacy.py        # One-off: import the OLD allocation-based DB
├── requirements.txt
├── runtime.txt
├── .env.example
├── .streamlit/secrets.toml.example
├── .gitignore
└── data/                    # local SQLite file lives here (gitignored)
```

---

## Quick Start (local)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Generate your admin password hash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"

cp .env.example .env
nano .env   # paste the hash into ADMIN_PASSWORD_HASH, set your details

streamlit run app.py
```

Open http://localhost:8501. Click **Admin Login** top-right, then use the
**Admin** tab to log your first Deposit and Buy trades.

### Bringing over your existing holdings

Your current live site's data (9 holdings, €85,000 allocated) can be
converted into opening Buy transactions instead of starting from zero. I
copied the SQLite file out of your GitHub repo — it ships in this package at
`legacy_data/legacy_portfolio.db`. Run:

```bash
python migrate_legacy.py legacy_data/legacy_portfolio.db
```

This creates one BUY transaction per active holding (skipping the CASH row,
which just folds into the starting cash balance) at its recorded entry
price. NBIS, GDX and EIMI.L were labelled EUR in the old data but are quoted
in USD, so they are booked as USD with the entry price converted at that
day's USD/EUR close. The one holding with no recorded entry price (AMZN) is
skipped and reported rather than guessed: enter it yourself from the Admin
Trade form, with currency USD. Review the Changes tab afterwards to confirm
it landed correctly.

---

## Admin Workflow

1. **Admin Login** (top-right) with your username/password.
2. **Trade (Buy/Sell):** enter a ticker, click "Fetch live price" to
   auto-fill the current price (override it if you want to book at a
   different price), enter quantity, submit. A Buy is blocked if it would
   overdraw cash; a Sell is blocked if you don't hold enough units.
3. **Deposit / Withdraw:** add or remove cash directly — e.g. to model
   topping up the portfolio, or to correct the opening balance.
4. **Ledger & Corrections:** every transaction ever logged, including voided
   ones. Mistakes are corrected by **voiding** a transaction (soft delete)
   rather than deleting it outright, so the audit trail in the public
   Changes tab never silently loses a row.

---

## Persistent Storage Design

`transactions` is the single source of truth. Cash balance and open
positions are computed from it on every page load — see
`portfolio_engine.py`:

```
cash_balance = starting_cash + Σ cash_amount_eur over all non-voided rows

BUY  qty @ price   → cash_amount_eur = -(qty * price_eur + fees)
SELL qty @ price   → cash_amount_eur = +(qty * price_eur - fees)
DEPOSIT / WITHDRAWAL → cash_amount_eur = ± amount
```

Positions use **average-cost accounting**: each Buy blends into the
position's running average cost; each Sell realizes P&L against that
average and reduces the cost basis proportionally.

### Why SQLite locally but Postgres in production?

Streamlit Community Cloud's filesystem is **ephemeral** — it resets on every
redeploy or restart. A SQLite file committed to Git only gives you a fixed
seed state, not a database that survives you logging trades through the
Admin tab. Local development doesn't have that problem, so SQLite (zero
setup, single file) is the default there; production needs a database that
lives outside the container.

### Setting up free Postgres (Supabase) — you do this part

I can't create an account on your behalf, but it's about five minutes:

1. Go to [supabase.com](https://supabase.com) → **New project** (free tier).
2. Once it's provisioned, go to **Project Settings → Database → Connection
   string**, and copy the URI (it looks like
   `postgresql://postgres:[YOUR-PASSWORD]@db.xxxx.supabase.co:5432/postgres`).
3. Change the scheme from `postgresql://` to `postgresql+psycopg2://` and use
   that as `DATABASE_URL`.
4. Locally: put it in `.env`. On Streamlit Community Cloud: paste it into
   **App settings → Secrets** (see `.streamlit/secrets.toml.example`).
5. Run the app once — `db.init_db()` creates the tables automatically on
   first connection. Then run `migrate_legacy.py` against the same
   `DATABASE_URL` (or just re-log your trades from the Admin tab) to
   populate it.

Free tier covers this comfortably — a portfolio's trade ledger is a handful
of KB even after years of trading; Supabase's free plan gives 500MB.

---

## Deployment (Streamlit Community Cloud)

1. Push this project to GitHub (replacing or alongside the current repo —
   your call).
2. [share.streamlit.io](https://share.streamlit.io) → New app → select the
   repo, branch, and `app.py`.
3. **Advanced settings → Secrets** — paste the contents of
   `.streamlit/secrets.toml.example` with your real values, **including
   `DATABASE_URL` pointed at Postgres** (skipping this means your trade
   history disappears on the next redeploy).
4. Deploy. First load creates the tables; log in as Admin and either replay
   `migrate_legacy.py` against the Postgres URL or re-enter your trades.

---

## Known limitation (flagged, not hidden)

Performance/Sharpe/volatility/drawdown are computed on **total portfolio
value**, not a time-weighted return. A Deposit or Withdrawal shows up as a
jump in portfolio value rather than being excluded from the return
calculation. For a portfolio that rarely moves cash in or out after
inception, this is what the original app did too (return vs. a fixed base
capital) and is easy to reason about. If deposits/withdrawals become
frequent, this should be upgraded to a proper time-weighted return
calculation.

---

## Disclaimer

> Model portfolio for informational and educational purposes only.
> This is not investment advice. Past performance is not indicative of future results.
