"""
storage.py — persistence layer using Turso HTTP API (no libsql_experimental).
Uses httpx to call Turso REST endpoint. Falls back to local SQLite if no Turso creds.
"""

import os
import json
import sqlite3
import httpx
from datetime import datetime, date
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

TURSO_URL   = os.getenv("TURSO_URL", "")
TURSO_TOKEN = os.getenv("TURSO_TOKEN", "")
DB_PATH     = os.getenv("DB_PATH", "data/portfolio.db")

# Convert libsql:// or libsql+wss:// → https:// for the HTTP API
_TURSO_HTTP_URL = (TURSO_URL
    .replace("libsql+wss://", "https://")
    .replace("libsql://",     "https://"))
_USE_TURSO = bool(_TURSO_HTTP_URL and TURSO_TOKEN)


# ── Turso HTTP helpers ────────────────────────────────────────────────────────

def _cast(cell: dict):
    """Cast a Turso cell {type, value} to a Python native type."""
    t = cell.get("type", "text")
    v = cell.get("value")
    if v is None:
        return None
    if t == "integer":
        return int(v)
    if t == "float":
        return float(v)
    # text / blob — but COUNT(*) comes back as type "integer" from Turso;
    # guard against the API returning it as a string anyway
    try:
        # if it looks like a whole number, cast it
        if isinstance(v, str) and v.lstrip("-").isdigit():
            return int(v)
        return v
    except Exception:
        return v


def _turso_execute(sql: str, params: list = None):
    """Execute one SQL statement on Turso; returns (cols, rows)."""
    params = params or []
    typed = []
    for p in params:
        if p is None:
            typed.append({"type": "null",    "value": None})
        elif isinstance(p, bool):
            typed.append({"type": "integer", "value": int(p)})
        elif isinstance(p, int):
            typed.append({"type": "integer", "value": p})
        elif isinstance(p, float):
            typed.append({"type": "float",   "value": p})
        else:
            typed.append({"type": "text",    "value": str(p)})

    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": typed}},
            {"type": "close"}
        ]
    }
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type":  "application/json",
    }
    url  = _TURSO_HTTP_URL.rstrip("/") + "/v2/pipeline"
    resp = httpx.post(url, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    data   = resp.json()
    result = data["results"][0]
    if result["type"] == "error":
        raise RuntimeError(f"Turso error: {result['error']}")
    rs   = result.get("response", {}).get("result", {})
    cols = [c["name"] for c in rs.get("cols", [])]
    rows = [tuple(_cast(cell) for cell in row) for row in rs.get("rows", [])]
    return cols, rows


def _turso_executescript(sql_script: str):
    """Run multiple semicolon-separated statements on Turso."""
    statements = [s.strip() for s in sql_script.split(";") if s.strip()]
    requests   = [{"type": "execute", "stmt": {"sql": s, "args": []}} for s in statements]
    requests.append({"type": "close"})
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type":  "application/json",
    }
    url  = _TURSO_HTTP_URL.rstrip("/") + "/v2/pipeline"
    resp = httpx.post(url, json={"requests": requests}, headers=headers, timeout=15)
    resp.raise_for_status()


# ── Local SQLite helpers ──────────────────────────────────────────────────────

def _local_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


# ── Unified helpers ───────────────────────────────────────────────────────────

def _query(sql: str, params: tuple = ()) -> tuple:
    if _USE_TURSO:
        return _turso_execute(sql, list(params))
    conn = _local_conn()
    cur  = conn.execute(sql, params)
    cols = [d[0] for d in (cur.description or [])]
    rows = cur.fetchall()
    conn.close()
    return cols, rows


def _exec(sql: str, params: tuple = ()):
    if _USE_TURSO:
        _turso_execute(sql, list(params))
        return
    conn = _local_conn()
    conn.execute(sql, params)
    conn.commit()
    conn.close()


# ── Public API ────────────────────────────────────────────────────────────────

def init_db():
    script = """
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
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            event_date    TEXT NOT NULL,
            description   TEXT DEFAULT '',
            snapshot_json TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS position_updates (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker              TEXT NOT NULL,
            update_date         TEXT NOT NULL,
            previous_allocation REAL NOT NULL,
            new_allocation      REAL NOT NULL,
            direction           TEXT NOT NULL,
            note                TEXT DEFAULT ''
        )
    """
    if _USE_TURSO:
        _turso_executescript(script)
    else:
        conn = _local_conn()
        conn.executescript(script)
        conn.commit()
        conn.close()


def seed_database():
    _, rows = _query("SELECT COUNT(*) FROM holdings")
    count = int(rows[0][0]) if rows and rows[0][0] is not None else 0
    if count > 0:
        print("[storage] Database already populated — skipping seed.")
        return
    seed = [
        ("IWDA.AS", "iShares Core MSCI World ETF",      35000, "ETF",      "USD", "Global", "2026-04-15", 1, "", None),
        ("EMIM.AS", "iShares Core MSCI EM IMI ETF",     15000, "ETF",      "USD", "EM",     "2026-04-15", 1, "", None),
        ("IUSN.DE", "iShares MSCI World Small Cap ETF", 10000, "ETF",      "USD", "Global", "2026-04-15", 1, "", None),
        ("ASML.AS", "ASML Holding",                     12000, "Equity",   "EUR", "Europe", "2026-04-15", 1, "", None),
        ("XGIN.DE", "Xtrackers Global Infl Bond ETF",   10000, "Bond ETF", "EUR", "Global", "2026-04-15", 1, "", None),
        ("AAPL",    "Apple Inc.",                         8000, "Equity",   "USD", "US",     "2026-04-15", 1, "", None),
        ("BTC-EUR", "Bitcoin",                            5000, "Crypto",   "EUR", "Global", "2026-04-15", 1, "", None),
        ("CASH",    "EUR Cash / Money Market",            5000, "Cash",     "EUR", "Global", "2026-04-15", 1, "", None),
    ]
    for row in seed:
        _exec("INSERT OR IGNORE INTO holdings VALUES (?,?,?,?,?,?,?,?,?,?)", row)
    _exec("INSERT OR IGNORE INTO meta(key,value) VALUES (?,?)", ("inception_date", "2026-04-15"))
    print("[storage] Seed data inserted.")


def get_holdings(active_only: bool = True) -> pd.DataFrame:
    sql = "SELECT * FROM holdings"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY eur_allocation DESC"
    cols, rows = _query(sql)
    if not cols:
        cols = ["ticker","name","eur_allocation","asset_class","currency",
                "region","effective_date","active","notes","entry_price_eur"]
    return pd.DataFrame(rows, columns=cols)


def save_holding(ticker: str, name: str, eur_allocation: float,
                 asset_class: str = "", currency: str = "EUR",
                 region: str = "", effective_date: str = "",
                 active: int = 1, notes: str = "",
                 entry_price_eur: float = None) -> None:
    _now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    _exec("""
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
    _exec("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", ("last_updated", _now))


def delete_holding(ticker: str) -> None:
    _exec("DELETE FROM holdings WHERE ticker = ?", (ticker.upper(),))


def deactivate_holding(ticker: str) -> None:
    _exec("UPDATE holdings SET active = 0 WHERE ticker = ?", (ticker.upper(),))


def get_meta(key: str, default: str = "") -> str:
    _, rows = _query("SELECT value FROM meta WHERE key = ?", (key,))
    return str(rows[0][0]) if rows and rows[0][0] is not None else default


def set_meta(key: str, value: str) -> None:
    _exec("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))


def create_rebalance_snapshot(description: str = "") -> int:
    holdings   = get_holdings(active_only=True).to_dict(orient="records")
    event_date = datetime.utcnow().strftime("%Y-%m-%d")
    if _USE_TURSO:
        _turso_execute(
            "INSERT INTO rebalances(event_date, description, snapshot_json) VALUES(?,?,?)",
            [event_date, description, json.dumps(holdings)]
        )
        _, rows = _query("SELECT MAX(id) FROM rebalances")
        return int(rows[0][0]) if rows and rows[0][0] is not None else 0
    conn = _local_conn()
    cur  = conn.execute(
        "INSERT INTO rebalances(event_date, description, snapshot_json) VALUES(?,?,?)",
        (event_date, description, json.dumps(holdings))
    )
    conn.commit()
    rowid = cur.lastrowid
    conn.close()
    return rowid


def get_rebalance_events() -> pd.DataFrame:
    cols, rows = _query(
        "SELECT id, event_date, description FROM rebalances ORDER BY event_date DESC"
    )
    return pd.DataFrame(rows, columns=["id", "event_date", "description"])


def get_rebalance_items(event_id: int) -> pd.DataFrame:
    _, rows = _query("SELECT snapshot_json FROM rebalances WHERE id = ?", (event_id,))
    if not rows or not rows[0][0]:
        return pd.DataFrame()
    return pd.DataFrame(json.loads(rows[0][0]))


def init_position_updates_table():
    pass  # Created in init_db()


def log_position_update(ticker: str, previous_allocation: float,
                        new_allocation: float, note: str = "") -> None:
    direction = ("Increased" if new_allocation > previous_allocation
                 else "Reduced" if new_allocation < previous_allocation
                 else "Unchanged")
    _exec("""
        INSERT INTO position_updates
            (ticker, update_date, previous_allocation, new_allocation, direction, note)
        VALUES (?,?,?,?,?,?)
    """, (ticker.upper(), date.today().isoformat(),
          previous_allocation, new_allocation, direction, note))


def get_position_updates() -> pd.DataFrame:
    cols, rows = _query(
        "SELECT * FROM position_updates ORDER BY update_date DESC, id DESC"
    )
    if not cols:
        cols = ["id","ticker","update_date","previous_allocation",
                "new_allocation","direction","note"]
    return pd.DataFrame(rows, columns=cols)
