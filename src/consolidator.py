#!/usr/bin/env python
"""
Consolidador de exports de Binance
- Lee todos los exports (CSV original, export1 xlsx, export2 csv + zips)
- Normaliza columnas y formatos
- Elimina duplicados
- Genera un CSV unificado y una base de datos SQLite
"""

import os
import glob
import csv
import zipfile
import sqlite3
import warnings
from datetime import datetime

import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

XLSX_COLS = {"user_id": 2, "time": 3, "account": 5, "operation": 6, "currency": 8, "change": 9, "observation": 11}


def parse_time(time_str):
    if pd.isna(time_str):
        return None
    time_str = str(time_str).strip()
    for fmt in ("%y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    return None


def row_to_record(row, source="csv"):
    if source == "xlsx":
        return {
            "user_id": str(row[XLSX_COLS["user_id"]]).strip() if pd.notna(row[XLSX_COLS["user_id"]]) else "",
            "time": parse_time(row[XLSX_COLS["time"]]),
            "account": str(row[XLSX_COLS["account"]]).strip() if pd.notna(row[XLSX_COLS["account"]]) else "",
            "operation": str(row[XLSX_COLS["operation"]]).strip() if pd.notna(row[XLSX_COLS["operation"]]) else "",
            "currency": str(row[XLSX_COLS["currency"]]).strip() if pd.notna(row[XLSX_COLS["currency"]]) else "",
            "change": str(row[XLSX_COLS["change"]]).strip() if pd.notna(row[XLSX_COLS["change"]]) else "",
            "observation": str(row[XLSX_COLS["observation"]]).strip() if pd.notna(row[XLSX_COLS["observation"]]) else "",
        }
    return {
        "user_id": str(row.get("user_id", "")).strip(),
        "time": row["time"],
        "account": str(row.get("account", "")).strip() if pd.notna(row.get("account")) else "",
        "operation": str(row.get("operation", "")).strip() if pd.notna(row.get("operation")) else "",
        "currency": str(row.get("currency", "")).strip() if pd.notna(row.get("currency")) else "",
        "change": str(row.get("change", "")).strip() if pd.notna(row.get("change")) else "",
        "observation": str(row.get("observation", "")).strip() if pd.notna(row.get("observation")) else "",
    }


def col_map_from_headers(columns):
    m = {}
    for col in columns:
        cs = col.strip()
        if "ID de usuario" in cs:
            m[col] = "user_id"
        elif cs == "Tiempo":
            m[col] = "time"
        elif cs == "Cuenta":
            m[col] = "account"
        elif cs == "Operación":
            m[col] = "operation"
        elif cs == "Moneda":
            m[col] = "currency"
        elif cs == "Cambio":
            m[col] = "change"
        elif cs == "Observación":
            m[col] = "observation"
    return m


def load_csv_file(path):
    try:
        df = pd.read_csv(path, dtype=str)
    except Exception as e:
        print(f"  ERROR reading {path}: {e}")
        return []
    if df.empty:
        return []
    cm = col_map_from_headers(df.columns)
    if not cm:
        print(f"  WARNING: No recognized columns in {path}")
        return []
    df = df.rename(columns=cm)
    df["time"] = df["time"].apply(parse_time)
    df = df.dropna(subset=["time"])
    return [row_to_record(row, "csv") for _, row in df.iterrows()]


def load_xlsx_file(path):
    try:
        df = pd.read_excel(path, header=None)
    except Exception as e:
        print(f"  ERROR reading {path}: {e}")
        return []

    header_row = None
    for idx, row in df.iterrows():
        row_str = " ".join(str(v) for v in row if pd.notna(v))
        if "ID de usuario" in row_str and "Tiempo" in row_str:
            header_row = idx
            break

    if header_row is None:
        return []

    records = []
    for idx in range(header_row + 1, len(df)):
        row = df.iloc[idx]
        time_val = row[XLSX_COLS["time"]]
        if pd.isna(time_val):
            continue
        user_id = row[XLSX_COLS["user_id"]]
        if "No hay datos" in str(user_id):
            continue

        parsed_time = parse_time(time_val)
        if parsed_time is None:
            continue

        records.append(row_to_record(row, "xlsx"))

    return records


def load_zips(zip_dir):
    all_records = []
    for zf_path in sorted(glob.glob(os.path.join(zip_dir, "*.zip"))):
        try:
            with zipfile.ZipFile(zf_path) as zf:
                for name in zf.namelist():
                    if name.endswith(".csv"):
                        with zf.open(name) as f:
                            df = pd.read_csv(f, dtype=str)
                            if df.empty:
                                continue
                            cm = col_map_from_headers(df.columns)
                            if cm:
                                df = df.rename(columns=cm)
                                df["time"] = df["time"].apply(parse_time)
                                df = df.dropna(subset=["time"])
                                all_records.extend([row_to_record(row, "csv") for _, row in df.iterrows()])
        except Exception as e:
            print(f"  ERROR reading zip {zf_path}: {e}")
    return all_records


def dedup_key(r):
    return (r["time"], r["currency"], r["operation"], r["change"])


def enrich(existing, incoming):
    for k in ("account", "observation"):
        if not existing.get(k) and incoming.get(k):
            existing[k] = incoming[k]
    return existing


def consolidate(data_dir="data"):
    all_records = []
    source_counts = {}

    original_csvs = [f for f in glob.glob(os.path.join(data_dir, "*.csv")) if "Historial" in f]
    for path in original_csvs:
        records = load_csv_file(path)
        all_records.extend(records)
        source_counts[os.path.basename(path)] = len(records)

    xlsx_files = sorted(glob.glob(os.path.join(data_dir, "export1", "*.xlsx")))
    xlsx_total = 0
    for path in xlsx_files:
        records = load_xlsx_file(path)
        all_records.extend(records)
        xlsx_total += len(records)
    source_counts["export1_xlsx"] = xlsx_total

    export2_csvs = [f for f in glob.glob(os.path.join(data_dir, "export2", "*.csv")) if "Historial" in f]
    e2_csv_total = 0
    for path in export2_csvs:
        records = load_csv_file(path)
        all_records.extend(records)
        e2_csv_total += len(records)
    source_counts["export2_csv"] = e2_csv_total

    extracted_csvs = sorted(glob.glob(os.path.join(data_dir, "export2", "extracted", "*.csv")))
    ext_total = 0
    for path in extracted_csvs:
        records = load_csv_file(path)
        all_records.extend(records)
        ext_total += len(records)
    source_counts["export2_extracted"] = ext_total

    zip_records = load_zips(os.path.join(data_dir, "export2"))
    all_records.extend(zip_records)
    source_counts["export2_zips"] = len(zip_records)

    print("=== SOURCE SUMMARY ===")
    for src, cnt in source_counts.items():
        print(f"  {src}: {cnt}")

    print(f"\nTotal raw records: {len(all_records)}")

    seen = {}
    dups = 0
    for rec in all_records:
        key = dedup_key(rec)
        if key in seen:
            dups += 1
            seen[key] = enrich(seen[key], rec)
        else:
            seen[key] = rec

    unique = sorted(seen.values(), key=lambda r: r["time"])
    print(f"Unique records: {len(unique)}")
    print(f"Duplicates removed: {dups}")

    output_csv = os.path.join(data_dir, "transactions_unified.csv")
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["user_id", "time", "account", "operation", "currency", "change", "observation"])
        for rec in unique:
            writer.writerow([
                rec["user_id"],
                rec["time"].strftime("%y-%m-%d %H:%M:%S"),
                rec["account"],
                rec["operation"],
                rec["currency"],
                rec["change"],
                rec["observation"],
            ])
    print(f"Saved: {output_csv}")

    db_path = os.path.join(data_dir, "transactions.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, time TEXT, account TEXT,
        operation TEXT, currency TEXT, change TEXT, observation TEXT
    )""")
    cur.execute("CREATE INDEX idx_time ON transactions(time)")
    cur.execute("CREATE INDEX idx_currency ON transactions(currency)")
    cur.execute("CREATE INDEX idx_operation ON transactions(operation)")

    for rec in unique:
        cur.execute("INSERT INTO transactions VALUES (NULL,?,?,?,?,?,?,?)",
                    (rec["user_id"], rec["time"].isoformat(), rec["account"],
                     rec["operation"], rec["currency"], rec["change"], rec["observation"]))
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM transactions")
    total = cur.fetchone()[0]
    cur.execute("SELECT MIN(time), MAX(time) FROM transactions")
    dr = cur.fetchone()
    cur.execute("SELECT COUNT(DISTINCT currency) FROM transactions")
    ncur = cur.fetchone()[0]
    cur.execute("SELECT operation, COUNT(*) FROM transactions GROUP BY operation ORDER BY COUNT(*) DESC")
    ops = cur.fetchall()

    print(f"\nDatabase: {db_path}")
    print(f"Records: {total} | Range: {dr[0]} to {dr[1]} | Currencies: {ncur}")
    print(f"Operations:")
    for op, cnt in ops:
        print(f"  {op}: {cnt}")

    conn.close()
    return output_csv, db_path


if __name__ == "__main__":
    consolidate()
