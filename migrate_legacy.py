"""
migrate_legacy.py — One-off migration from the old allocation-based SQLite
schema (ticker, eur_allocation, entry_price_eur, ...) into the new
transaction-ledger schema (db.py).

The old model had no concept of trades — a holding was just "€X allocated
to ticker Y". This script turns each active, non-CASH holding into an
opening BUY transaction of size €eur_allocation at its recorded
entry_price_eur.

A holding with no recorded entry price is never given a guessed one: it is
skipped and reported, to be entered by hand from the Admin Trade form.

The old CASH row and any unallocated portion of the €100,000 base capital
both fold naturally into the new model's cash balance — they don't need
their own transaction, they're just what's left of starting_cash after
the Buy transactions are replayed.

Usage:
    python migrate_legacy.py path/to/old/portfolio.db [--starting-cash 100000] [--force]

Run this ONCE, before you start using the Admin tab for real trades.
Safe to re-run with --force if you need to redo it (it will not
double-insert unless forced — it refuses to run against a ledger that
already has transactions).
"""

import sys
import sqlite3
import argparse
from datetime import date, timedelta

import db
from config import STARTING_CASH
from data_loader import get_fx_history, get_fx_rate

# The legacy rows for these tickers say currency=EUR, but Yahoo quotes them in
# USD and their recorded entry_price_eur is the raw USD close on that date. They
# are booked as USD, with the entry price converted at that day's USD/EUR close.
USD_QUOTED_AS_EUR = {"NBIS", "GDX", "EIMI.L", "AMZN"}


def _usd_eur_on(day: str):
    """USD/EUR close on `day`, or the next day with a quote. None if unavailable."""
    end = (date.fromisoformat(day) + timedelta(days=7)).isoformat()
    df = get_fx_history("USD", "EUR", day, end)
    if df.empty:
        return None
    return float(df.sort_values("date").iloc[0]["close"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("legacy_db_path")
    parser.add_argument("--starting-cash", type=float, default=STARTING_CASH)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    db.init_db()
    existing = db.get_transactions(include_voided=True)
    if not existing.empty and not args.force:
        print(f"Refusing to migrate: the ledger already has {len(existing)} transaction(s). "
              f"Pass --force to migrate anyway (this will add duplicate opening trades).")
        sys.exit(1)

    conn = sqlite3.connect(args.legacy_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM holdings WHERE active = 1 ORDER BY effective_date ASC").fetchall()
    conn.close()

    if not rows:
        print("No active holdings found in the legacy database — nothing to migrate.")
        sys.exit(0)

    inception = min(r["effective_date"] for r in rows) or date.today().isoformat()

    # Resolve every trade before writing any, so a failed FX lookup can't leave
    # a half-migrated ledger that the guard above would then refuse to redo.
    planned, skipped = [], []
    for r in rows:
        ticker = r["ticker"].upper()
        if ticker == "CASH":
            print(f"  · skipping {ticker} row (€{r['eur_allocation']:,.2f}) — folds into starting cash")
            continue

        alloc = float(r["eur_allocation"])
        day = r["effective_date"]
        currency = "USD" if ticker in USD_QUOTED_AS_EUR else (r["currency"] or "EUR")
        entry_px = r["entry_price_eur"]

        if not entry_px or entry_px <= 0:
            skipped.append(f"{ticker}: €{alloc:,.2f}, currency {currency}, legacy date {day}")
            continue

        if ticker in USD_QUOTED_AS_EUR:
            fx = _usd_eur_on(day)
            if not fx:
                print(f"Aborting, nothing was written: no USD/EUR rate available for {day} ({ticker}).")
                sys.exit(1)
            price_local, entry_px = entry_px, entry_px * fx
            source = f"recorded USD entry price, converted at {fx:.4f} USD/EUR"
        else:
            fx = get_fx_rate(currency, "EUR") if currency != "EUR" else 1.0
            price_local = entry_px / (fx or 1.0)
            source = "recorded entry price"

        planned.append(dict(
            tx_date=day, tx_type="BUY", cash_amount_eur=-alloc,
            ticker=ticker, name=r["name"], asset_class=r["asset_class"] or "Equity",
            currency=currency, quantity=alloc / entry_px, price_local=price_local,
            fx_rate=fx, price_eur=entry_px, fees_eur=0.0,
            notes=f"Migrated from legacy allocation model ({source}).",
        ))

    db.set_meta("starting_cash", str(args.starting_cash))
    db.set_meta("inception_date", inception)
    print(f"Starting cash: €{args.starting_cash:,.2f}    Inception date: {inception}\n")

    total_bought = 0.0
    for tx in planned:
        db.add_transaction(**tx)
        total_bought -= tx["cash_amount_eur"]
        print(f"  ✓ {tx['ticker']}: BUY {tx['quantity']:,.4f} units @ €{tx['price_eur']:,.4f}  "
              f"(€{-tx['cash_amount_eur']:,.2f}, {tx['notes']})")

    cash_after = args.starting_cash - total_bought
    print(f"\nMigrated. Cash balance after opening trades: €{cash_after:,.2f}")
    for line in skipped:
        print(f"  ⚠ NOT MIGRATED, no recorded entry price. Enter from the Admin Trade form — {line}")
    print("Review the Changes tab in the app to confirm everything landed correctly.")


if __name__ == "__main__":
    main()
