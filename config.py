"""
config.py — Central configuration for the Anchor Investments dashboard.

Values are read, in priority order, from:
  1. Streamlit secrets (st.secrets)      — used on Streamlit Community Cloud
  2. Environment variables / .env file   — used for local dev
  3. Hard-coded defaults below

Streamlit Cloud's "Advanced settings -> Secrets" box only populates
st.secrets, not os.environ, so we must check both explicitly or admin
login / the database connection silently fall back to defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

try:
    import streamlit as st
    _HAS_SECRETS = True
except Exception:  # pragma: no cover
    _HAS_SECRETS = False


def _get(key: str, default: str = "") -> str:
    if _HAS_SECRETS:
        try:
            if key in st.secrets:
                return str(st.secrets[key])
        except Exception:
            pass
    return os.getenv(key, default)


# ── Portfolio identity ────────────────────────────────────────────────────────
PORTFOLIO_NAME = _get("PORTFOLIO_NAME", "Anchor Investments")
PORTFOLIO_DESCRIPTION = _get(
    "PORTFOLIO_DESCRIPTION",
    "A fictive model portfolio published alongside my Substack.",
)
SUBSTACK_URL = _get("SUBSTACK_URL", "https://yoursubstack.substack.com")

# Cash the portfolio was seeded with at inception. This is NOT a hard cap —
# unlike the old model, cash can be topped up (Deposit) or drawn down
# (Withdrawal) at any time from the Admin panel, exactly like a real
# brokerage account. It only sets the starting balance for day 1.
STARTING_CASH = float(_get("STARTING_CASH", "100000"))
BASE_CURRENCY = "EUR"

# ── Auth ──────────────────────────────────────────────────────────────────────
ADMIN_USERNAME = _get("ADMIN_USERNAME", "admin")
# bcrypt hash of the admin password — never store the plaintext password.
# Generate with:
#   python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
ADMIN_PASSWORD_HASH = _get("ADMIN_PASSWORD_HASH", "")

# ── Storage ───────────────────────────────────────────────────────────────────
# SQLAlchemy connection string.
#   - Local dev default: SQLite file under data/
#   - Production (Streamlit Community Cloud): set DATABASE_URL to a hosted
#     Postgres instance (e.g. Supabase free tier) so data survives restarts
#     and redeploys. Streamlit Cloud's own filesystem is wiped on every
#     redeploy/restart, so SQLite alone WILL lose your trade history there.
DATABASE_URL = _get("DATABASE_URL", "sqlite:///data/portfolio.db")

# ── Market data ──────────────────────────────────────────────────────────────
# Preferred provider: "openbb" | "yfinance"
DATA_PROVIDER = _get("DATA_PROVIDER", "yfinance")

# Cache TTL for price data (seconds). Kept fairly long by default because
# Yahoo's unofficial endpoint rate-limits aggressively under repeated calls.
PRICE_CACHE_TTL = int(_get("PRICE_CACHE_TTL", "900"))     # 15 min
HISTORY_CACHE_TTL = int(_get("HISTORY_CACHE_TTL", "3600"))  # 1 hr

# ── Display ───────────────────────────────────────────────────────────────────
CURRENCY_DISPLAY = "EUR"
DISCLAIMER = (
    "Model portfolio for informational and educational purposes only. "
    "This is not investment advice. Past performance is not indicative of future results."
)
