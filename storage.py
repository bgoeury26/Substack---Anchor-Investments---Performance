"""
storage.py — SQLite persistence layer.
"""

import sqlite3
import os
import json
from datetime import datetime, date
from typing import Optional
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("DB_PATH", "data/portfolio.db")


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS holdings (
            ticker          TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            eur_allocation  REAL NOT NULL DEFAULT 0,
            asset_class     TEXT DEFAULT 'Equity',
            currency        TEXT DEFAULT 'EUR',
            region          TEXT DEFAULT 'Global',
            effective_date  TEXT DEFAULT (date('now')),
            active          INTEGER DEFAULT 1,
            notes           TEXT DEFAULT '',
            entry_price_eur REAL DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS rebalances (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date      TEXT NOT NULL,
            description     TEXT DEFAULT '',
            snapshot_json   TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    # Migration: add entry_price_eur if missing
    cols = [r[1] for r in cur.execute("PRAGMA table_info(holdings)").fetchall()]
    if "entry_price_eur" not in cols:
        cur.execute("ALTER TABLE holdings ADD COLUMN entry_price_eur REAL DEFAULT NULL")
    conn.commit()
    conn.close()


def seed_database():
    conn = get_conn()
    cur = conn.cursor()
    count = cur.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
    if count > 0:
        print("[storage] Database already populated — skipping seed.")
        conn.close()
        return
    seed = [
        ("IWDA.AS", "iShares Core MSCI World ETF",  35000, "ETF",    "USD", "Global",  "2026-04-15", 1, "", None),
        ("EIMI.AS", "iShares Core MSCI EM IMI ETF",  15000, "ETF",    "USD", "EM",      "2026-04-15", 1, "", None),
        ("IUSN.AS", "iShares MSCI World Small Cap ETF", 10000, "ETF", "USD", "Global",  "2026-04-15", 1, "", None),
        ("ASML.AS", "ASML Holding",                  12000, "Equity", "EUR", "Europe",  "2026-04-15", 1, "", None),
        ("XGIU.AS", "Xtrackers Global Infl Bond ETF",10000, "Bond ETF","EUR","Global",  "2026-04-15", 1, "", None),
        ("AAPL",    "Apple Inc.",                     8000, "Equity", "USD", "US",      "2026-04-15", 1, "", None),
        ("BTC-EUR", "Bitcoin",                        5000, "Crypto", "EUR", "Global",  "2026-04-15", 1, "", None),
        ("CASH",    "EUR Cash / Money Market",        5000, "Cash",   "EUR", "Global",  "2026-04-15", 1, "", None),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO holdings VALUES (?,?,?,?,?,?,?,?,?,?)", seed
    )
    cur.execute("INSERT OR IGNORE INTO meta(key,value) VALUES ('inception_date','2026-04-15')")
    conn.commit()
    conn.close()
    print("[storage] Seed data inserted.")


def get_holdings(active_only: bool = True) -> pd.DataFrame:
    conn = get_conn()
    query = "SELECT * FROM holdings"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY eur_allocation DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def upsert_holding(
    ticker: str,
    name: str,
    eur_allocation: float,
    asset_class: str = "Equity",
    currency: str = "EUR",
    region: str = "Global",
    effective_date: str = None,
    active: bool = True,
    notes: str = "",
    entry_price_eur: float = None,
) -> None:
    if effective_date is None:
        effective_date = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO holdings
            (ticker, name, eur_allocation, asset_class, currency, region,
             effective_date, active, notes, entry_price_eur,
         __import__('datetime').datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(ticker) DO UPDATE SET
            name            = excluded.name,
            eur_allocation  = excluded.eur_allocation,
            asset_class     = excluded.asset_class,
            currency        = excluded.currency,
            region          = excluded.region,
            effective_date  = excluded.effective_date,
            active          = excluded.active,
            notes           = excluded.notes,
            entry_price_eur = CASE
                WHEN excluded.entry_price_eur IS NOT NULL
                THEN excluded.entry_price_eur
                ELSE holdings.entry_price_eur
            END
    """, (
        ticker.upper(), name, eur_allocation, asset_class, currency,
        region, effective_date, int(active), notes, entry_price_eur
    ))
    conn.commit()
    conn.close()


def delete_holding(ticker: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM holdings WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    conn.close()


def deactivate_holding(ticker: str) -> None:
    conn = get_conn()
    conn.execute("UPDATE holdings SET active = 0 WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    conn.close()


def get_meta(key: str, default: str = "") -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else default


def set_meta(key: str, value: str) -> None:
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))
    conn.commit()
    conn.close()


def create_rebalance(event_date: str, description: str, snapshot: dict) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO rebalances(event_date,description,snapshot_json) VALUES(?,?,?)",
        (event_date, description, json.dumps(snapshot))
    )
    conn.commit()
    conn.close()


def get_rebalances() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM rebalances ORDER BY event_date DESC", conn)
    conn.close()
    return df


# ── Compatibility aliases & missing functions added 2026-04-16 ───────────────

def save_holding(ticker: str, name: str, eur_allocation: float,
                 asset_class: str = "", currency: str = "EUR",
                 region: str = "", effective_date: str = "",
                 active: int = 1, notes: str = "",
                 entry_price_eur: float = None) -> None:
    """Upsert a holding — alias used by app.py admin form."""
    conn = get_conn()
    _now = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute("""
        INSERT INTO holdings
            (ticker, name, eur_allocation, asset_class, currency, region,
             effective_date, active, notes, entry_price_eur, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(ticker) DO UPDATE SET
            name            = excluded.name,
            eur_allocation  = excluded.eur_allocation,
            asset_class     = excluded.asset_class,
            currency        = excluded.currency,
            region          = excluded.region,
            effective_date  = excluded.effective_date,
            active          = excluded.active,
            notes           = excluded.notes,
            entry_price_eur = COALESCE(excluded.entry_price_eur, holdings.entry_price_eur),
            updated_at      = excluded.updated_at
    """, (ticker.upper(), name, eur_allocation, asset_class, currency,
          region, effective_date, int(active), notes, entry_price_eur,
          _now, _now))
    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES('last_updated',?)",
        (datetime.utcnow().isoformat(timespec="seconds"),)
    )
    conn.commit()
    conn.close()


def delete_holding(ticker: str) -> None:
    """Permanently delete a holding from the database."""
    conn = get_conn()
    conn.execute("DELETE FROM holdings WHERE ticker = ?", (ticker.upper(),))
    conn.commit()
    conn.close()


def create_rebalance_snapshot(description: str = "") -> int:
    """Save a snapshot of current holdings as a rebalance event. Returns event id."""
    conn = get_conn()
    holdings = pd.read_sql_query(
        "SELECT * FROM holdings WHERE active = 1", conn
    ).to_dict(orient="records")
    event_date = datetime.utcnow().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO rebalances(event_date, description, snapshot_json) VALUES(?,?,?)",
        (event_date, description, json.dumps(holdings))
    )
    event_id = cur.lastrowid
    conn.commit()
    conn.close()
    return event_id


def get_rebalance_events() -> pd.DataFrame:
    """Return all rebalance events ordered by date descending."""
    conn = get_conn()
    # COALESCE handles both old DBs (no created_at) and new ones
    df = pd.read_sql_query(
        "SELECT id, event_date, description, COALESCE(created_at, event_date) AS created_at FROM rebalances ORDER BY event_date DESC",
        conn
    )
    conn.close()
    return df


def get_rebalance_items(event_id: int) -> pd.DataFrame:
    """Return the holdings snapshot for a given rebalance event."""
    conn = get_conn()
    row = conn.execute(
        "SELECT snapshot_json FROM rebalances WHERE id = ?", (event_id,)
    ).fetchone()
    conn.close()
    if not row or not row[0]:
        return pd.DataFrame()
    return pd.DataFrame(json.loads(row[0]))


# ── Position Updates ─────────────────────────────────────────────────────────

def init_position_updates_table():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS position_updates (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker               TEXT NOT NULL,
            update_date          TEXT NOT NULL,
            previous_allocation  REAL NOT NULL,
            new_allocation       REAL NOT NULL,
            direction            TEXT NOT NULL,
            note                 TEXT DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()


def log_position_update(ticker: str, previous_allocation: float,
                         new_allocation: float, note: str = "") -> None:
    if new_allocation > previous_allocation:
        direction = "Increased"
    elif new_allocation < previous_allocation:
        direction = "Reduced"
    else:
        direction = "Unchanged"
    conn = get_conn()
    conn.execute("""
        INSERT INTO position_updates
            (ticker, update_date, previous_allocation, new_allocation, direction, note)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (ticker.upper(), date.today().isoformat(),
          previous_allocation, new_allocation, direction, note))
    conn.commit()
    conn.close()


def get_position_updates() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM position_updates ORDER BY update_date DESC, id DESC", conn
    )
    conn.close()
    return df
