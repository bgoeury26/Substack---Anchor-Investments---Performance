"""
config.py — Central configuration for the portfolio dashboard.
All environment-dependent values are read from .env or Streamlit secrets.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Portfolio identity ────────────────────────────────────────────────────────
PORTFOLIO_NAME = os.getenv("PORTFOLIO_NAME", "Model Portfolio")
PORTFOLIO_DESCRIPTION = os.getenv(
    "PORTFOLIO_DESCRIPTION",
    "A €100,000 model portfolio conceived to reflect the investment insights "
    "published as a companion to the Substack newsletter.",
)
SUBSTACK_URL = os.getenv("SUBSTACK_URL", "https://yoursubstack.substack.com")
BASE_CAPITAL = float(os.getenv("BASE_CAPITAL", "100000"))

# ── Auth ──────────────────────────────────────────────────────────────────────
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
# Store a bcrypt hash of your password in .env / Streamlit secrets.
# Generate with:  python -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

# ── Storage ───────────────────────────────────────────────────────────────────
# SQLite file path — committed to Git only for dev seed; excluded in prod.
DB_PATH = os.getenv("DB_PATH", "data/portfolio.db")

# ── Market data ──────────────────────────────────────────────────────────────
# Preferred provider: "openbb" | "yfinance"
DATA_PROVIDER = os.getenv("DATA_PROVIDER", "yfinance")

# Cache TTL for price data (seconds)
PRICE_CACHE_TTL = int(os.getenv("PRICE_CACHE_TTL", "900"))   # 15 min
HISTORY_CACHE_TTL = int(os.getenv("HISTORY_CACHE_TTL", "3600"))  # 1 hr

# ── Display ───────────────────────────────────────────────────────────────────
CURRENCY_DISPLAY = "EUR"
DISCLAIMER = (
    "⚠️  Model portfolio for informational and educational purposes only. "
    "This is not investment advice. Past performance is not indicative of future results."
)
