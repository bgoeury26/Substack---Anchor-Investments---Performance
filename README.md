# 📊 Portfolio Dashboard

A production-ready **Streamlit** web application for a fictive model portfolio,
built as a public companion to a Substack publication.

- **Fixed base capital:** EUR 100,000
- **Persistent storage:** SQLite (local) → PostgreSQL-ready
- **Market data:** yfinance (default) or OpenBB
- **Admin auth:** bcrypt-hashed password, env-variable secrets
- **Charts:** Plotly (line, donut, treemap, drawdown, contribution bar)

---

## Folder Structure

```
portfolio_dashboard/
├── app.py                    # Streamlit entry point
├── config.py                 # Env-based configuration
├── storage.py                # SQLite CRUD + schema + seed data
├── auth.py                   # Admin authentication (bcrypt)
├── data_loader.py            # Market data abstraction (yfinance / OpenBB)
├── portfolio_engine.py       # Portfolio calculations & analytics
├── charts.py                 # Plotly chart builders
├── requirements.txt
├── .env.example              # Copy to .env and fill in
├── .gitignore
├── data/
│   └── portfolio.db          # SQLite file (auto-created on first run)
└── .github/
    └── workflows/
        └── lint.yml          # GitHub Actions CI
```

---

## Quick Start (macOS Terminal + nano)

### 1. Clone or create the repo

```bash
# If starting fresh:
mkdir portfolio_dashboard
cd portfolio_dashboard
git init
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Generate your admin password hash

```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"
```

Copy the output (the `$2b$12$...` string).

### 5. Create your `.env` file

```bash
cp .env.example .env
nano .env
```

Fill in at minimum:
- `ADMIN_USERNAME` — your chosen username
- `ADMIN_PASSWORD_HASH` — the bcrypt hash from step 4
- `PORTFOLIO_NAME` — your portfolio name
- `SUBSTACK_URL` — your Substack link

### 6. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Admin Workflow

1. Open the app and click **Admin Login** in the top-right.
2. Enter your username and password from `.env`.
3. The **⚙️ Admin** tab appears.
4. Add, edit, or deactivate holdings — every save writes **immediately to SQLite**.
5. Holdings persist across browser refreshes, app restarts, and redeployments.

### Adding a holding (example)

| Field | Example |
|---|---|
| Ticker | `IWDA.AS` |
| Name | `iShares Core MSCI World ETF` |
| EUR Allocation | `35000` |
| Asset Class | `ETF` |
| Currency | `USD` |
| Region | `Global` |
| Effective Date | `2024-01-15` |

---

## Persistent Storage Design

### Why SQLite?

SQLite is a single-file database — perfect for:
- Local development and self-hosted deployment
- Git-friendly (the `.db` file can be committed for dev seeds or excluded for prod)
- Zero configuration — no server needed
- Easy migration to PostgreSQL later (see below)

### Schema

```sql
-- holdings: source of truth for current positions
CREATE TABLE holdings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker          TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    eur_allocation  REAL NOT NULL DEFAULT 0,
    asset_class     TEXT DEFAULT 'Equity',
    currency        TEXT DEFAULT 'EUR',
    region          TEXT DEFAULT 'Global',
    effective_date  TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1,
    notes           TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

-- rebalance_events: snapshot headers
CREATE TABLE rebalance_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date  TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

-- rebalance_items: holdings at each snapshot
CREATE TABLE rebalance_items (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id       INTEGER NOT NULL REFERENCES rebalance_events(id),
    ticker         TEXT NOT NULL,
    name           TEXT NOT NULL,
    eur_allocation REAL NOT NULL,
    asset_class    TEXT,
    currency       TEXT,
    region         TEXT
);

-- portfolio_meta: key/value store (last_updated, inception_date, …)
CREATE TABLE portfolio_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### Migration to PostgreSQL

Replace the `_connect()` function in `storage.py` with a `psycopg2` or
`SQLAlchemy` connection. All public functions (`get_holdings`, `save_holding`,
etc.) remain unchanged — only the driver changes.

---

## SQLite and Git

| Scenario | Commit `data/portfolio.db`? |
|---|---|
| Local dev / fresh machine | ✅ Yes — brings seed data |
| Streamlit Community Cloud | ❌ No — use persistent volume or external DB |
| Self-hosted (VPS/Docker) | ❌ No — keep on server volume, back up separately |

For Streamlit Community Cloud, the filesystem resets on each deploy.
Options:
1. Use an external database (PlanetScale, Supabase, Railway PostgreSQL).
2. Store a base JSON/CSV snapshot in the repo and sync to a cloud DB on startup.
3. Self-host on a VPS where the filesystem persists.

---

## GitHub Workflow

### Initial push

```bash
cd portfolio_dashboard
git init
git add .
git commit -m "feat: initial portfolio dashboard"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/portfolio-dashboard.git
git push -u origin main
```

### Daily workflow

```bash
# Edit code in nano
nano app.py

# Stage, commit, push
git add .
git commit -m "feat: add ASML position"
git push
```

### After changing holdings via Admin UI

The SQLite `.db` file updates automatically. If you want to track it:
```bash
git add data/portfolio.db
git commit -m "data: rebalance Q2 2025"
git push
```

---

## Deployment

### Streamlit Community Cloud (recommended for public Substack companion)

1. Push your repo to GitHub (public or private).
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app.
3. Select your repo, branch `main`, and main file `app.py`.
4. In **Advanced settings → Secrets**, add all keys from `.env.example`.
5. ⚠️ Community Cloud has **ephemeral storage** — the SQLite file resets on redeploy.
   Solution: commit a seed `data/portfolio.db` for demo data, or switch to an
   external PostgreSQL (e.g. Supabase free tier).

### Self-hosted on a VPS (persistent storage ✅)

```bash
# On your server
git clone https://github.com/YOUR_USERNAME/portfolio-dashboard.git
cd portfolio-dashboard
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && nano .env

# Run with nohup or as a systemd service
nohup streamlit run app.py --server.port 8501 --server.headless true &

# Update after git push:
git pull && streamlit run app.py
```

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `ADMIN_USERNAME` | ✅ | `admin` | Admin login username |
| `ADMIN_PASSWORD_HASH` | ✅ | — | bcrypt hash of admin password |
| `PORTFOLIO_NAME` | — | `Model Portfolio` | Displayed in header |
| `PORTFOLIO_DESCRIPTION` | — | Built-in text | Displayed in About tab |
| `SUBSTACK_URL` | — | — | Link to your Substack |
| `BASE_CAPITAL` | — | `100000` | Fixed model portfolio size (EUR) |
| `DB_PATH` | — | `data/portfolio.db` | SQLite file path |
| `DATA_PROVIDER` | — | `yfinance` | `yfinance` or `openbb` |
| `PRICE_CACHE_TTL` | — | `900` | Price cache duration (seconds) |

---

## Notes on OpenBB

To use OpenBB as the data provider:
```bash
pip install openbb
```
Then set `DATA_PROVIDER=openbb` in `.env`.

OpenBB is used as the first-attempt provider; the app falls back to yfinance
automatically if OpenBB fails. This makes the data layer resilient and easy to
extend with other providers later.

---

## Disclaimer

> Model portfolio for informational and educational purposes only.
> This is not investment advice. Past performance is not indicative of future results.
