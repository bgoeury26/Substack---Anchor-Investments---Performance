"""
migrate_legacy.py — One-off migration from the old allocation-based SQLite
schema (ticker, eur_allocation, entry_price_eur, ...) into the new
transaction-ledger schema (db.py).

The old model had no concept of trades — a holding was just "€X allocated
to ticker Y". This script turns each active, non-CASH holding into an
opening BUY transaction of size €eur_allocation at its recorded
entry_price_eur (or, if that's missing, the historical closing price on
its effective_date, fetched from Yahoo Finance).

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
from datetime import date

import db
from config import STARTING_CASH
from data_loader import get_price_history, get_fx_rate


def _closing_price_eur(ticker: str, currency: str, effective_date: str):
    df = get_price_history(ticker, effective_date, None)
    if df.empty:
        return None
    df = df.sort_values("date")
    close_local = float(df.iloc[0]["close"])
    if currency and currency.upper() != "EUR":
        fx = get_fx_rate(currency, "EUR")
        return close_local * (fx or 1.0)
    return close_local


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
    db.set_meta("starting_cash", str(args.starting_cash))
    db.set_meta("inception_date", inception)

    total_bought = 0.0
    print(f"Starting cash: €{args.starting_cash:,.2f}    Inception date: {inception}\n")

    for r in rows:
        ticker = r["ticker"].upper()
        if ticker == "CASH":
            print(f"  · skipping {ticker} row (€{r['eur_allocation']:,.2f}) — folds into starting cash")
            continue

        alloc = float(r["eur_allocation"])
        currency = r["currency"] or "EUR"
        entry_px = r["entry_price_eur"]
        source = "recorded entry price"

        if not entry_px or entry_px <= 0:
            entry_px = _closing_price_eur(ticker, currency, r["effective_date"])
            source = "fetched historical close"

        if not entry_px or entry_px <= 0:
            print(f"  ⚠ {ticker}: no entry price available (recorded or fetched) — SKIPPED. "
                  f"Add this position manually from the Admin tab.")
            continue

        qty = alloc / entry_px
        fx_now = get_fx_rate(currency, "EUR") if currency != "EUR" else 1.0
        price_local = entry_px / (fx_now or 1.0)

        db.add_transaction(
            tx_date=r["effective_date"], tx_type="BUY", cash_amount_eur=-alloc,
            ticker=ticker, name=r["name"], asset_class=r["asset_class"] or "Equity",
            currency=currency, quantity=qty, price_local=price_local,
            fx_rate=fx_now, price_eur=entry_px, fees_eur=0.0,
            notes=f"Migrated from legacy allocation model ({source}).",
        )
        total_bought += alloc
        print(f"  ✓ {ticker}: BUY {qty:,.4f} units @ €{entry_px:,.4f}  (€{alloc:,.2f}, {source})")

    cash_after = args.starting_cash - total_bought
    print(f"\nMigrated. Cash balance after opening trades: €{cash_after:,.2f}")
    print("Review the Changes tab in the app to confirm everything landed correctly.")


if __name__ == "__main__":
    main()
