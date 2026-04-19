"""
storage.py — persistence layer using Turso (libSQL) for cloud deployments,
falling back to local SQLite for development if TURSO_URL is not set.
"""

import os
import json
import libsql_experimental as libsql
from datetime import datetime, date
from typing import Optional
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

TURSO_URL   = os.getenv("TURSO_URL", "")
TURSO_TOKEN = os.getenv("TURSO_TOKEN", "")
DB_PATH     = os.getenv("DB_PATH", "data/portfolio.db")


def get_conn():
    if TURSO_URL and TURSO_TOKEN:
        conn = libsql.connect(database=TURSO_URL, auth_token=TURSO_TOKEN)
    else:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = libsql.connect(DB_PATH)
    return conn


def _exec(conn, sql: str, params: tuple = ()):
    conn.execute(sql, params)
    conn.commit()


def init_db():
    conn = get_conn()
    conn.executescript("""
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
        CREATE TABLE IF NOT EXISTS position_updates (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker               TEXT NOT NULL,
            update_date          TEXT NOT NULL,
            previous_allocation  REAL NOT NULL,
            new_allocation       REAL NOT NULL,
            direction            TEXT NOT NULL,
            note                 TEXT DEFAULT ''
        );
    """)
    conn.commit()


def seed_database():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
    if count > 0:
        print("[storage] Database already populated — skipping seed.")
        return
    seed = [
        ("IWDA.AS", "iShares Core MSCI World ETF",     35000, "ETF",     "USD", "Global", "2026-04-15", 1, "", None),
        ("EIMI.AS", "iShares Core MSCI EM IMI ETF",    15000, "ETF",     "USD", "EM",     "2026-04-15", 1, "", None),
        ("IUSN.AS", "iShares MSCI World Small Cap ETF",10000, "ETF",     "USD", "Global", "2026-04-15", 1, "", None),
        ("ASML.AS", "ASML Holding",                    12000, "Equity",  "EUR", "Europe", "2026-04-15", 1, "", None),
        ("XGIU.AS", "Xtrackers Global Infl Bond ETF",  10000, "Bond ETF","EUR", "Global", "2026-04-15", 1, "", None),
        ("AAPL",    "Apple Inc.",                       8000, "Equity",  "USD", "US",     "2026-04-15", 1, "", None),
        ("BTC-EUR", "Bitcoin",                          5000, "Crypto",  "EUR", "Global", "2026-04-15", 1, "", None),
        ("CASH",    "EUR Cash / Money Market",          5000, "Cash",    "EUR", "Global", "2026-04-15", 1, "", None),
    ]
    for row in seed:
        conn.execute("INSERT OR IGNORE INTO holdings VALUES (?,?,?,?,?,?,?,?,?,?)", row)
    conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES ('inception_date','2026-04-15')")
    conn.commit()
    print("[storage] Seed data inserted.")


def get_holdings(active_only: bool = True) -> pd.DataFrame:
    conn = get_conn()
    query = "SELECT * FROM holdings"
    if active_only:
        query += " WHERE active = 1"
    query += " ORDER BY eur_allocation DESC"
    rows = conn.execute(query).fetchall()
    cols = ["ticker","name","eur_allocation","asset_class","currency",
            "region","effective_date","active","notes","entry_price_eur"]
    return pd.DataFrame(rows, columns=cols)


def save_holding(ticker: str, name: str, eur_allocation: float,
                 asset_class: str = "", currency: str = "EUR",
                 region: str = "", effective_date: str = "",
                 active: int = 1, notes: str = "",
                 entry_price_eur: float = None) -> None:
    conn = get_conn()
    _now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute("""
        INSERT INTO holdings
            (ticker, name, eur_allocation, asset_class, currency, region,
             effective_date, active, notes, entry_price_eur)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(ticker) DO UPDATE SET
            name            = excluded.name,
            eur_allocation  = excluded.eur_allocation,
            asset_class     = excluded.asset_class,
            currency        = excluded.currency,
            region          = excluded.region,
            effective_date  = excluded.effective_date,
            active          = excluded.active,
            notes           = excluded.notes,
            entry_price_eur = COALESCE(excluded.entry_price_eur, holdings.entry_price_eur)
    """, (ticker.upper(), name, eur_allocation, asset_class, currency,
          region, effective_date, int(active), notes, entry_price_eur))
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('last_updated',?)", (_now,))
    conn.commit()


def delete_holding(ticker: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM holdings WHERE ticker = ?", (ticker.upper(),))
    conn.commit()


def deactivate_holding(ticker: str) -> None:
    conn = get_conn()
    conn.execute("UPDATE holdings SET active = 0 WHERE ticker = ?", (ticker.upper(),))
    conn.commit()


def get_meta(key: str, default: str = "") -> str:
    conn = get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(key: str, value: str) -> None:
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))
    conn.commit()


def create_rebalance_snapshot(description: str = "") -> int:
    conn = get_conn()
    holdings = get_holdings(active_only=True).to_dict(orient="records")
    event_date = datetime.utcnow().strftime("%Y-%m-%d")
    cur = conn.execute(
        "INSERT INTO rebalances(event_date, description, snapshot_json) VALUES(?,?,?)",
        (event_date, description, json.dumps(holdings))
    )
    conn.commit()
    return cur.lastrowid


def get_rebalance_events() -> pd.DataFrame:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, event_date, description FROM rebalances ORDER BY event_date DESC"
    ).fetchall()
    return pd.DataFrame(rows, columns=["id","event_date","description"])


def get_rebalance_items(event_id: int) -> pd.DataFrame:
    conn = get_conn()
    row = conn.execute(
        "SELECT snapshot_json FROM rebalances WHERE id = ?", (event_id,)
    ).fetchone()
    if not row or not row[0]:
        return pd.DataFrame()
    return pd.DataFrame(json.loads(row[0]))


def init_position_updates_table():
    pass  # Table created in init_db()


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


def get_position_updates() -> pd.DataFrame:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM position_updates ORDER BY update_date DESC, id DESC"
    ).fetchall()
    cols = ["id","ticker","update_date","previous_allocation",
            "new_allocation","direction","note"]
    return pd.DataFrame(rows, columns=cols)
