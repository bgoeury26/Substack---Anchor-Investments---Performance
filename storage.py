import sqlite3
import os
import bcrypt
from datetime import date

DB_PATH = os.path.join(os.path.dirname(__file__), "portfolio.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS holdings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker         TEXT NOT NULL,
            shares         REAL NOT NULL,
            purchase_price REAL NOT NULL,
            purchase_date  TEXT NOT NULL,
            inception_date TEXT NOT NULL DEFAULT '2026-04-15'
        );
        CREATE TABLE IF NOT EXISTS position_updates (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker       TEXT NOT NULL,
            shares       REAL NOT NULL,
            price        REAL NOT NULL,
            updated_date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cash (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()

def init_position_updates_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS position_updates (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker       TEXT NOT NULL,
            shares       REAL NOT NULL,
            price        REAL NOT NULL,
            updated_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def seed_database():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
    if count == 0:
        inception = "2026-04-15"
        holdings = [
            ("AAPL",  10, 195.00, "2026-04-15", inception),
            ("MSFT",   5, 415.00, "2026-04-15", inception),
            ("GOOGL",  8, 165.00, "2026-04-15", inception),
            ("AMZN",   6, 195.00, "2026-04-15", inception),
            ("NVDA",  15, 875.00, "2026-04-15", inception),
        ]
        conn.executemany(
            "INSERT INTO holdings (ticker, shares, purchase_price, purchase_date, inception_date) VALUES (?,?,?,?,?)",
            holdings
        )
        conn.commit()
    cash_count = conn.execute("SELECT COUNT(*) FROM cash").fetchone()[0]
    if cash_count == 0:
        conn.execute("INSERT INTO cash (amount) VALUES (0)")
        conn.commit()
    conn.close()

def create_user(username: str, password: str) -> bool:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        conn = get_conn()
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username: str, password: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT password FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if not row:
        return False
    return bcrypt.checkpw(password.encode(), row["password"].encode())

def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT id, username FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_holdings():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM holdings").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_holding(ticker: str, shares: float, purchase_price: float,
                purchase_date: str, inception_date: str = "2026-04-15"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO holdings (ticker, shares, purchase_price, purchase_date, inception_date) VALUES (?,?,?,?,?)",
        (ticker.upper(), shares, purchase_price, purchase_date, inception_date)
    )
    conn.commit()
    conn.close()

def update_holding(holding_id: int, shares: float, purchase_price: float, purchase_date: str):
    conn = get_conn()
    conn.execute(
        "UPDATE holdings SET shares=?, purchase_price=?, purchase_date=? WHERE id=?",
        (shares, purchase_price, purchase_date, holding_id)
    )
    conn.commit()
    conn.close()

def delete_holding(holding_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM holdings WHERE id=?", (holding_id,))
    conn.commit()
    conn.close()

def add_position_update(ticker: str, shares: float, price: float, updated_date: str = None):
    if updated_date is None:
        updated_date = str(date.today())
    conn = get_conn()
    conn.execute(
        "INSERT INTO position_updates (ticker, shares, price, updated_date) VALUES (?,?,?,?)",
        (ticker.upper(), shares, price, updated_date)
    )
    conn.commit()
    conn.close()

def get_position_updates(ticker: str = None):
    conn = get_conn()
    if ticker:
        rows = conn.execute(
            "SELECT * FROM position_updates WHERE ticker=? ORDER BY updated_date DESC",
            (ticker.upper(),)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM position_updates ORDER BY updated_date DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cash() -> float:
    conn = get_conn()
    row = conn.execute("SELECT amount FROM cash ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row["amount"] if row else 0.0

def set_cash(amount: float):
    conn = get_conn()
    row = conn.execute("SELECT id FROM cash LIMIT 1").fetchone()
    if row:
        conn.execute("UPDATE cash SET amount=? WHERE id=?", (amount, row["id"]))
    else:
        conn.execute("INSERT INTO cash (amount) VALUES (?)", (amount,))
    conn.commit()
    conn.close()

# ── Meta / Rebalance / Legacy aliases ────────────────────────────────────────

def get_meta():
    """Return portfolio-level metadata dict."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM portfolio_meta LIMIT 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}

def create_rebalance_snapshot(holdings: list):
    """Store a rebalance snapshot (no-op stub if table missing)."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rebalance_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot    TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (date('now'))
        )
    """)
    import json
    conn.execute(
        "INSERT INTO rebalance_snapshots (snapshot) VALUES (?)",
        (json.dumps(holdings),)
    )
    conn.commit()
    conn.close()

def log_position_update(ticker: str, shares: float, price: float, updated_date: str = None):
    """Alias for add_position_update for backward compatibility."""
    add_position_update(ticker, shares, price, updated_date)
