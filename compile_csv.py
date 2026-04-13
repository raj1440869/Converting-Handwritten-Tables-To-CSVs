#!/usr/bin/env python3
"""
Compile all extracted batch JSON files into a single finance_payments.csv
and import it into the Alkas Threading project.
"""

import csv
import json
import os
import sqlite3
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
HANDWRITING_DIR = Path("/Users/raj/Desktop/Handwriting")
ALKAS_DIR       = Path("/Users/raj/Desktop/Alkas Threading Summer 2025/Alkas-Threading-Summer-2025")

EXTRACTED_CSV   = HANDWRITING_DIR / "extracted_finance.csv"
TARGET_CSV      = ALKAS_DIR / "finance_payments.csv"
TARGET_DB       = ALKAS_DIR / "appointments.db"

BATCH_FILES = [
    HANDWRITING_DIR / "batch_jan_feb_mar.json",
    HANDWRITING_DIR / "batch_apr_may.json",
    HANDWRITING_DIR / "batch_jun_jul.json",
    HANDWRITING_DIR / "batch_aug_sept.json",
    HANDWRITING_DIR / "batch_oct_nov.json",
]

def load_all_batches() -> list[dict]:
    """Load and merge all batch JSON files."""
    all_records = []
    for batch_file in BATCH_FILES:
        if not batch_file.exists():
            print(f"  ⚠️  Missing batch file: {batch_file.name} — skipping")
            continue
        with open(batch_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  ✅ {batch_file.name}: {len(data)} records")
        all_records.extend(data)
    return all_records


def records_to_csv_rows(records: list[dict]) -> list[dict]:
    """Convert raw batch records to finance_payments.csv format."""
    rows = []
    for r in records:
        month  = int(r["month"])
        year   = int(r["year"])
        name   = str(r.get("name", "")).strip()
        amount = float(r.get("amount", 0) or 0)
        ptype  = str(r.get("payment_type", "Cash")).strip()

        if not name or amount <= 0:
            continue

        # Normalise payment type
        pt_lower = ptype.lower()
        if "cash" in pt_lower:
            ptype = "Cash"
        elif "venmo" in pt_lower or "beni" in pt_lower:
            ptype = "Venmo"
        elif "zelle" in pt_lower or "zel" in pt_lower:
            ptype = "Zelle"
        else:
            ptype = "Cash"

        date_str = f"{year}-{month:02d}-01T00:00:00"
        rows.append({
            "Date":         date_str,
            "Client Name":  name,
            "Amount":       round(amount, 2),
            "Payment Type": ptype,
            "Service Type": "",
        })
    return rows


def write_extracted_csv(rows: list[dict]):
    """Write the standalone extracted CSV for review."""
    fieldnames = ["Date", "Client Name", "Amount", "Payment Type", "Service Type"]
    with open(EXTRACTED_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n📄 Extracted CSV saved: {EXTRACTED_CSV}")
    print(f"   → {len(rows)} rows total")


def import_to_alkas(rows: list[dict]):
    """
    Merge extracted rows into the Alkas Threading finance_payments.csv
    and sync to the SQLite database.
    Existing rows are preserved; extracted rows are appended (no duplicates
    by exact Date+Name+Amount+PaymentType match).
    """
    # ── Load existing CSV data ──────────────────────────────────────────────
    existing = []
    existing_keys: set[tuple] = set()

    if TARGET_CSV.exists():
        with open(TARGET_CSV, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.append(row)
                key = (row["Date"], row["Client Name"],
                       row["Amount"], row["Payment Type"])
                existing_keys.add(key)
        print(f"\n📂 Existing finance_payments.csv: {len(existing)} rows")
    else:
        print("\n📂 finance_payments.csv not found — will create fresh")

    # ── Deduplicate new rows ────────────────────────────────────────────────
    new_rows = []
    skipped  = 0
    for row in rows:
        key = (row["Date"], row["Client Name"],
               str(row["Amount"]), row["Payment Type"])
        if key in existing_keys:
            skipped += 1
        else:
            new_rows.append(row)
            existing_keys.add(key)

    print(f"   → {len(new_rows)} new rows to add ({skipped} already existed)")

    # ── Write merged CSV ────────────────────────────────────────────────────
    merged = existing + new_rows
    fieldnames = ["Date", "Client Name", "Amount", "Payment Type", "Service Type"]
    with open(TARGET_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)

    print(f"✅ finance_payments.csv updated: {len(merged)} total rows")

    # ── Sync to SQLite ──────────────────────────────────────────────────────
    if TARGET_DB.exists():
        try:
            conn = sqlite3.connect(str(TARGET_DB), timeout=30)
            cursor = conn.cursor()

            # Make sure table exists
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS finance_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    payment_type TEXT NOT NULL DEFAULT 'Cash',
                    service_type TEXT DEFAULT ''
                )
            ''')

            # Insert only the new rows (avoid full replace to keep existing IDs)
            inserted = 0
            for row in new_rows:
                cursor.execute(
                    "INSERT INTO finance_payments (date, client_name, amount, payment_type, service_type) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (row["Date"], row["Client Name"], float(row["Amount"]),
                     row["Payment Type"], row.get("Service Type", ""))
                )
                inserted += 1

            conn.commit()
            conn.close()
            print(f"✅ SQLite DB updated: {inserted} rows inserted into finance_payments")
        except Exception as e:
            print(f"⚠️  DB update failed: {e} (CSV is still saved)")
    else:
        print("⚠️  appointments.db not found — skipping DB sync (CSV only)")


def main():
    print("=" * 60)
    print("Handwriting → Alkas Threading Import")
    print("=" * 60)

    print("\n[1] Loading batch files …")
    raw_records = load_all_batches()
    print(f"\n   Total raw records: {len(raw_records)}")

    print("\n[2] Converting to CSV format …")
    csv_rows = records_to_csv_rows(raw_records)

    print("\n[3] Writing extracted CSV …")
    write_extracted_csv(csv_rows)

    print("\n[4] Importing into Alkas Threading project …")
    import_to_alkas(csv_rows)

    print("\n🎉 Done!")


if __name__ == "__main__":
    main()
