import sqlite3
import os
from datetime import datetime
from decimal import Decimal
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "fct.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            time TEXT NOT NULL,
            account TEXT,
            operation TEXT NOT NULL,
            currency TEXT NOT NULL,
            change TEXT NOT NULL,
            observation TEXT,
            eur_price REAL,
            eur_value REAL,
            classification TEXT,
            source TEXT DEFAULT 'csv',
            imported_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            currency TEXT NOT NULL,
            date TEXT NOT NULL,
            price_eur REAL NOT NULL,
            source TEXT DEFAULT 'coingecko',
            UNIQUE(currency, date)
        );

        CREATE TABLE IF NOT EXISTS fifo_lots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            currency TEXT NOT NULL,
            quantity REAL NOT NULL,
            cost_basis_eur REAL NOT NULL,
            price_per_unit_eur REAL NOT NULL,
            acquired_at TEXT NOT NULL,
            tx_id TEXT,
            is_income INTEGER DEFAULT 0,
            remaining_qty REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS disposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            currency TEXT NOT NULL,
            disposed_qty REAL NOT NULL,
            disposal_date TEXT NOT NULL,
            acquisition_cost_eur REAL NOT NULL,
            sale_value_eur REAL NOT NULL,
            gain_loss_eur REAL NOT NULL,
            acquisition_date TEXT NOT NULL,
            tx_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_tx_time ON transactions(time);
        CREATE INDEX IF NOT EXISTS idx_tx_currency ON transactions(currency);
        CREATE INDEX IF NOT EXISTS idx_tx_operation ON transactions(operation);
        CREATE INDEX IF NOT EXISTS idx_prices_currency_date ON prices(currency, date);
        CREATE INDEX IF NOT EXISTS idx_lots_currency ON fifo_lots(currency);
    """)

    # Default settings
    defaults = {
        "home_country": "Spain",
        "base_currency": "EUR",
        "cost_basis_method": "FIFO",
        "cost_tracking_method": "Universal",
        "gains_on_crypto_to_crypto": "Yes",
        "sidebar_layout": "False",
        "language": "es",
    }
    for key, value in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()


def import_transactions(records, source="csv"):
    conn = get_db()
    imported = 0
    duplicates = 0
    for rec in records:
        key = (rec["time"], rec["currency"], rec["operation"], rec["change"])
        cur = conn.execute(
            "SELECT id FROM transactions WHERE time=? AND currency=? AND operation=? AND change=?",
            key,
        )
        if cur.fetchone():
            duplicates += 1
            continue

        conn.execute(
            """INSERT INTO transactions
               (user_id, time, account, operation, currency, change, observation, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rec.get("user_id", ""),
                rec["time"].isoformat() if hasattr(rec["time"], "isoformat") else str(rec["time"]),
                rec.get("account", ""),
                rec["operation"],
                rec["currency"],
                rec["change"],
                rec.get("observation", ""),
                source,
            ),
        )
        imported += 1
    conn.commit()
    conn.close()
    return imported, duplicates


def get_settings():
    defaults = {
        "home_country": "Spain",
        "base_currency": "EUR",
        "cost_basis_method": "FIFO",
        "cost_tracking_method": "Universal",
        "gains_on_crypto_to_crypto": "Yes",
        "sidebar_layout": "False",
        "language": "es",
    }
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    settings = {row["key"]: row["value"] for row in rows}
    for key, value in defaults.items():
        settings.setdefault(key, value)
    return settings


def save_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()


def get_transaction_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) as cnt FROM transactions").fetchone()["cnt"]
    conn.close()
    return count


def get_transactions(limit=50, offset=0, currencies=None, operations=None, date_from=None, date_to=None, invert_currency=False, invert_operation=False, min_value=None):
    conn = get_db()
    query = "SELECT * FROM transactions WHERE 1=1"
    params = []

    if currencies:
        placeholders = ",".join(["?" for _ in currencies])
        op = "NOT IN" if invert_currency else "IN"
        query += f" AND currency {op} ({placeholders})"
        params.extend(currencies)
    if operations:
        placeholders = ",".join(["?" for _ in operations])
        op = "NOT IN" if invert_operation else "IN"
        query += f" AND operation {op} ({placeholders})"
        params.extend(operations)
    if date_from:
        query += " AND time >= ?"
        params.append(date_from)
    if date_to:
        query += " AND time <= ?"
        params.append(date_to)
    if min_value is not None:
        query += " AND ABS(CAST(change AS REAL)) >= ?"
        params.append(min_value)

    query += " ORDER BY time DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_total_transactions(currencies=None, operations=None, date_from=None, date_to=None, invert_currency=False, invert_operation=False, min_value=None):
    conn = get_db()
    query = "SELECT COUNT(*) as cnt FROM transactions WHERE 1=1"
    params = []
    if currencies:
        placeholders = ",".join(["?" for _ in currencies])
        op = "NOT IN" if invert_currency else "IN"
        query += f" AND currency {op} ({placeholders})"
        params.extend(currencies)
    if operations:
        placeholders = ",".join(["?" for _ in operations])
        op = "NOT IN" if invert_operation else "IN"
        query += f" AND operation {op} ({placeholders})"
        params.extend(operations)
    if date_from:
        query += " AND time >= ?"
        params.append(date_from)
    if date_to:
        query += " AND time <= ?"
        params.append(date_to)
    if min_value is not None:
        query += " AND ABS(CAST(change AS REAL)) >= ?"
        params.append(min_value)
    count = conn.execute(query, params).fetchone()["cnt"]
    conn.close()
    return count


def get_currencies():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT currency FROM transactions ORDER BY currency"
    ).fetchall()
    conn.close()
    return [r["currency"] for r in rows]


def get_operations():
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT operation FROM transactions ORDER BY operation"
    ).fetchall()
    conn.close()
    return [r["operation"] for r in rows]


def save_price(currency, date, price_eur, source="coingecko"):
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO prices (currency, date, price_eur, source)
           VALUES (?, ?, ?, ?)""",
        (currency, date, price_eur, source),
    )
    conn.commit()
    conn.close()


def get_price(currency, date):
    conn = get_db()
    row = conn.execute(
        "SELECT price_eur FROM prices WHERE currency=? AND date=? ORDER BY date DESC LIMIT 1",
        (currency, date),
    ).fetchone()
    conn.close()
    return row["price_eur"] if row else None


def get_transaction_eur_value(currency, amount, date_str):
    from web.engine import STABLECOINS, HISTORICAL_STABLECOIN_RATES
    if currency in STABLECOINS:
        date = date_str[:10] if len(date_str) > 10 else date_str
        year = int(date[:4])
        rate = HISTORICAL_STABLECOIN_RATES.get(year, HISTORICAL_STABLECOIN_RATES[2026]).get(currency, 0.92)
        return float(amount) * rate
    date = date_str[:10] if len(date_str) > 10 else date_str
    price = get_price(currency, date)
    if price:
        return float(amount) * price
    return 0.0


def get_yearly_prices(year):
    conn = get_db()
    rows = conn.execute(
        """SELECT currency, date, price_eur FROM prices
           WHERE date LIKE ? ORDER BY currency, date""",
        (f"{year}-%",),
    ).fetchall()
    conn.close()
    result = {}
    for r in rows:
        if r["currency"] not in result:
            result[r["currency"]] = {}
        result[r["currency"]][r["date"]] = r["price_eur"]
    return result


def clear_all_data():
    conn = get_db()
    conn.executescript("""
        DELETE FROM transactions;
        DELETE FROM fifo_lots;
        DELETE FROM disposals;
        DELETE FROM prices;
        DELETE FROM settings;
    """)
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at {DB_PATH}")
