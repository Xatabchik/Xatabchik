#!/usr/bin/env python3
"""Small helper to inspect the SQLite DB used by the bot.

Usage:
  python tools\inspect_db.py [--db path_to_db] [--payment PAYMENT_ID]

Prints recent transactions and pending_transactions and the row for the given payment_id if provided.
"""
import sqlite3
import argparse
from pathlib import Path
import json

parser = argparse.ArgumentParser()
parser.add_argument('--db', '-d', help='Path to DB file', default=None)
parser.add_argument('--payment', '-p', help='payment_id to inspect', default=None)
args = parser.parse_args()

# Discover DB similar to code logic
candidates = []
if args.db:
    candidates.append(Path(args.db))
candidates += [Path('/app/project/users.db'), Path('users-20251005-173430.db'), Path('users.db')]
DB = None
for c in candidates:
    if c and c.exists():
        DB = c
        break
if DB is None:
    print('DB not found. Checked:', [str(p) for p in candidates])
    raise SystemExit(1)

print('Using DB:', DB)
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('\nLast 50 transactions:')
cur.execute("SELECT transaction_id, payment_id, user_id, status, amount_rub, payment_method, created_date FROM transactions ORDER BY created_date DESC LIMIT 50")
rows = cur.fetchall()
if not rows:
    print('  (no transactions)')
else:
    for r in rows:
        print(' ', dict(r))

print('\nLast 20 pending_transactions:')
cur.execute("SELECT payment_id, user_id, amount_rub, status, metadata, rowid FROM pending_transactions ORDER BY rowid DESC LIMIT 20")
rows = cur.fetchall()
if not rows:
    print('  (no pending_transactions)')
else:
    for r in rows:
        meta = r['metadata']
        try:
            meta = json.loads(meta) if meta else None
        except Exception:
            pass
        print(' ', {'payment_id': r['payment_id'], 'user_id': r['user_id'], 'amount_rub': r['amount_rub'], 'status': r['status'], 'metadata': meta})

if args.payment:
    pay = args.payment
    print(f"\nTransactions with payment_id={pay}:")
    cur.execute("SELECT * FROM transactions WHERE payment_id = ?", (pay,))
    rows = cur.fetchall()
    if not rows:
        print('  (no transactions)')
    else:
        for r in rows:
            meta = r['metadata']
            try:
                meta = json.loads(meta) if meta else None
            except Exception:
                pass
            d = dict(r)
            d['metadata'] = meta
            print(' ', d)

    print(f"\nPending_transactions with payment_id={pay}:")
    cur.execute("SELECT * FROM pending_transactions WHERE payment_id = ?", (pay,))
    rows = cur.fetchall()
    if not rows:
        print('  (no pending_transactions)')
    else:
        for r in rows:
            meta = r['metadata']
            try:
                meta = json.loads(meta) if meta else None
            except Exception:
                pass
            d = dict(r)
            d['metadata'] = meta
            print(' ', d)

conn.close()
