"""
db.py — Persistence layer built on SQLAlchemy Core.

Works unchanged against SQLite (local dev, default) or Postgres
(production — e.g. a free Supabase project) purely by changing
DATABASE_URL. No dialect-specific SQL is used anywhere in this file,
so nothing else in the app needs to know which database is behind it.

Design
------
`transactions` is the single source of truth — an append-only ledger.
Every cash movement (deposit, withdrawal, buy, sell, dividend, fee) is one
row with a signed `cash_amount_eur`. Cash balance, open positions, and
realized/unrealized P&L are all *derived* from this table (see
portfolio_engine.py) rather than stored redundantly — so there is no way
for "cash balance" and "the trades that produced it" to drift out of sync.

Corrections are done by voiding a transaction (soft delete, `voided=1`)
rather than deleting it, so the audit trail in the Changes tab never loses
a row silently.
"""

import os
from datetime import datetime

import pandas as pd
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, Float, String, Text,
    select, insert, update,
)

from config import DATABASE_URL

# SQLite needs its parent directory to exist before the file is created.
if DATABASE_URL.startswith("sqlite:///"):
    _path = DATABASE_URL.replace("sqlite:///", "", 1)
    _dir = os.path.dirname(_path)
    if _dir:
        os.makedirs(_dir, exist_ok=True)

engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
metadata = MetaData()

meta_table = Table(
    "meta", metadata,
    Column("key", String(64), primary_key=True),
    Column("value", Text),
)

# tx_type ∈ {DEPOSIT, WITHDRAWAL, BUY, SELL, DIVIDEND, FEE}
transactions_table = Table(
    "transactions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("tx_date", String(10), nullable=False),          # YYYY-MM-DD
    Column("tx_type", String(16), nullable=False),
    Column("ticker", String(32)),
    Column("name", String(128)),
    Column("asset_class", String(32)),
    Column("currency", String(8)),
    Column("quantity", Float),
    Column("price_local", Float),
    Column("fx_rate", Float),
    Column("price_eur", Float),
    Column("cash_amount_eur", Float, nullable=False),        # signed
    Column("fees_eur", Float, default=0.0),
    Column("notes", Text),
    Column("created_at", String(20), nullable=False),
    Column("voided", Integer, default=0),
    Column("void_reason", Text),
)

price_cache_table = Table(
    "price_cache", metadata,
    Column("ticker", String(32), primary_key=True),
    Column("price", Float),
    Column("currency", String(8)),
    Column("fetched_at", String(20)),
)


def init_db() -> None:
    metadata.create_all(engine)


# ── meta key/value store ────────────────────────────────────────────────────

def get_meta(key: str, default: str = "") -> str:
    with engine.connect() as conn:
        row = conn.execute(
            select(meta_table.c.value).where(meta_table.c.key == key)
        ).fetchone()
    return row[0] if row else default


def set_meta(key: str, value: str) -> None:
    with engine.begin() as conn:
        exists = conn.execute(
            select(meta_table.c.key).where(meta_table.c.key == key)
        ).fetchone()
        if exists:
            conn.execute(
                update(meta_table).where(meta_table.c.key == key).values(value=value)
            )
        else:
            conn.execute(insert(meta_table).values(key=key, value=value))


def ensure_inception(starting_cash: float, inception_date: str) -> None:
    """Set inception_date/starting_cash in meta exactly once."""
    if not get_meta("inception_date"):
        set_meta("inception_date", inception_date)
    if not get_meta("starting_cash"):
        set_meta("starting_cash", str(starting_cash))


def _touch_last_updated() -> None:
    set_meta("last_updated", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))


# ── transactions (the ledger) ───────────────────────────────────────────────

def add_transaction(
    tx_date: str,
    tx_type: str,
    cash_amount_eur: float,
    ticker: str = None,
    name: str = None,
    asset_class: str = None,
    currency: str = None,
    quantity: float = None,
    price_local: float = None,
    fx_rate: float = None,
    price_eur: float = None,
    fees_eur: float = 0.0,
    notes: str = "",
) -> int:
    row = dict(
        tx_date=tx_date,
        tx_type=tx_type.upper(),
        ticker=(ticker.upper() if ticker else None),
        name=name,
        asset_class=asset_class,
        currency=(currency.upper() if currency else None),
        quantity=quantity,
        price_local=price_local,
        fx_rate=fx_rate,
        price_eur=price_eur,
        cash_amount_eur=round(float(cash_amount_eur), 2),
        fees_eur=round(float(fees_eur or 0.0), 2),
        notes=notes or "",
        created_at=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        voided=0,
    )
    with engine.begin() as conn:
        result = conn.execute(insert(transactions_table).values(**row))
        new_id = result.inserted_primary_key[0]
    _touch_last_updated()
    return new_id


def get_transactions(include_voided: bool = False) -> pd.DataFrame:
    query = select(transactions_table)
    if not include_voided:
        query = query.where(transactions_table.c.voided == 0)
    query = query.order_by(transactions_table.c.tx_date.asc(), transactions_table.c.id.asc())
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    if df.empty:
        df = pd.DataFrame(columns=[c.name for c in transactions_table.columns])
    return df


def void_transaction(tx_id: int, reason: str = "") -> None:
    with engine.begin() as conn:
        conn.execute(
            update(transactions_table)
            .where(transactions_table.c.id == tx_id)
            .values(voided=1, void_reason=reason)
        )
    _touch_last_updated()


# ── price cache (last-known-good fallback when Yahoo rate-limits us) ───────

def get_cached_price(ticker: str):
    with engine.connect() as conn:
        row = conn.execute(
            select(price_cache_table).where(price_cache_table.c.ticker == ticker.upper())
        ).fetchone()
    if not row:
        return None
    return {"price": row.price, "currency": row.currency, "fetched_at": row.fetched_at}


def set_cached_price(ticker: str, price: float, currency: str = "EUR") -> None:
    ticker = ticker.upper()
    fetched_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    with engine.begin() as conn:
        exists = conn.execute(
            select(price_cache_table.c.ticker).where(price_cache_table.c.ticker == ticker)
        ).fetchone()
        if exists:
            conn.execute(
                update(price_cache_table)
                .where(price_cache_table.c.ticker == ticker)
                .values(price=price, currency=currency, fetched_at=fetched_at)
            )
        else:
            conn.execute(
                insert(price_cache_table).values(
                    ticker=ticker, price=price, currency=currency, fetched_at=fetched_at
                )
            )
