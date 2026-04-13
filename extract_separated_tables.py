#!/usr/bin/env python3
"""
Separated Tables → CSV Extractor
Uses Claude Vision API to read pre-split handwritten table halves
from Pre-Processing/Seperated Tables/ and produce a review CSV.

Each image is already ONE HALF of a ledger page (left or right side).
Output: handwriting_review.csv  (for manual review before importing to Alkas)
Backup: handwriting_review_raw.json  (raw per-image extraction results)

Output CSV columns:
    Date, Client Name, Amount, Payment Type, Service Type
"""

import anthropic
import base64
import csv
import json
import os
import re
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────
IMAGES_DIR   = Path("/Users/raj/Desktop/Handwriting/Pre-Processing/Seperated Tables")
REVIEW_CSV   = Path("/Users/raj/Desktop/Handwriting/handwriting_review.csv")
RAW_JSON     = Path("/Users/raj/Desktop/Handwriting/handwriting_review_raw.json")

# ── Month name → number ───────────────────────────────────────────────────────
MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

def filename_to_year_month(filename: str) -> tuple[int, int]:
    """
    Parse month and year from filename.
    Examples:
        Jan_25_1.jpg  → (2025, 1)
        Apr25_1_1.jpg → (2025, 4)
        Sept25_2_2.jpg → (2025, 9)
    """
    name = Path(filename).stem.lower()   # e.g. "apr25_1_1"
    for abbr, num in MONTH_MAP.items():
        if name.startswith(abbr):
            return 2025, num
    raise ValueError(f"Cannot parse month from filename: {filename}")


def image_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


EXTRACTION_PROMPT = """You are reading a single handwritten business ledger table for a threading/waxing salon.

This image contains ONE HALF (one side) of a ledger page — it is already cropped to show a single table.

The table has these columns (labels may be abbreviated or hard to read):
  • Row number or Date  (#, date, or row index)
  • Service / Client Name  (person's name)
  • Cash  (cash payment amount — blank if not used)
  • Bank / Beni / Venmo  (Venmo payment — blank if not used)
  • Zel / Zelle  (Zelle payment — blank if not used)

Note: some tables may only have Cash and one other column. Read what is actually there.

A client may have amounts in more than one payment column (split payment).

YOUR TASK: Extract EVERY row that has a name AND at least one non-zero payment amount.

Return a JSON array. Each element represents ONE payment row:
{
  "name":  "<client name as written, best guess>",
  "cash":  <number or 0>,
  "venmo": <number or 0>,
  "zelle": <number or 0>
}

Rules:
- If a cell is blank, crossed out, or illegible, use 0 for that amount.
- If the name is completely illegible, skip that row entirely.
- Do NOT include the header row, total rows, or summary rows at the bottom.
- Strip stray punctuation from names but keep parenthetical notes like "(2)".
- Numbers may use shorthand: ".5" means 0.5, "1/2" means 0.5, "100" means 100.
- If a number has a line through it (crossed out), treat it as 0.
- The "Bank" column is treated as Venmo. The "Zel" column is Zelle.
- Return ONLY the JSON array, no other text.

Example output:
[
  {"name": "Alice Smith",    "cash": 25, "venmo": 0,  "zelle": 0},
  {"name": "Bob Jones (2)",  "cash": 0,  "venmo": 15, "zelle": 10}
]
"""


def extract_rows_from_image(client: anthropic.Anthropic, image_path: Path) -> list[dict]:
    """Send one half-table image to Claude Vision and return structured rows."""
    b64 = image_to_b64(image_path)
    ext = image_path.suffix.lower().lstrip(".")
    media_type = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png"

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$",          "", raw, flags=re.MULTILINE)

    try:
        rows = json.loads(raw)
        if not isinstance(rows, list):
            rows = []
    except json.JSONDecodeError as e:
        print(f"\n  ⚠️  JSON parse error for {image_path.name}: {e}")
        print(f"  Raw snippet: {raw[:300]}")
        rows = []

    return rows


def rows_to_csv_records(rows: list[dict], year: int, month: int, source_file: str) -> list[dict]:
    """
    Convert extracted rows to finance_payments.csv-compatible dicts.
    Split payments produce multiple rows. Date = 1st of month.
    """
    date_str = f"{year}-{month:02d}-01T00:00:00"
    records = []

    for row in rows:
        name = str(row.get("name", "")).strip()
        if not name:
            continue

        payments = [
            (float(row.get("cash",  0) or 0), "Cash"),
            (float(row.get("venmo", 0) or 0), "Venmo"),
            (float(row.get("zelle", 0) or 0), "Zelle"),
        ]

        for amount, ptype in payments:
            if amount > 0:
                records.append({
                    "Date":         date_str,
                    "Client Name":  name,
                    "Amount":       round(amount, 2),
                    "Payment Type": ptype,
                    "Service Type": "",
                    "_source":      source_file,   # kept for debugging, stripped before CSV write
                })

    return records


def main():
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment

    image_files = sorted(
        list(IMAGES_DIR.glob("*.jpg")) + list(IMAGES_DIR.glob("*.png"))
    )
    if not image_files:
        print(f"No images found in {IMAGES_DIR}")
        sys.exit(1)

    print(f"Found {len(image_files)} images to process.\n")

    all_records: list[dict] = []
    raw_results: list[dict] = []   # backup: raw rows per image

    for i, img_path in enumerate(image_files, 1):
        try:
            year, month = filename_to_year_month(img_path.name)
        except ValueError as e:
            print(f"  [{i}/{len(image_files)}] Skipping {img_path.name}: {e}")
            continue

        print(f"  [{i:02d}/{len(image_files)}] {img_path.name}  ({year}-{month:02d}) … ", end="", flush=True)

        rows = extract_rows_from_image(client, img_path)
        records = rows_to_csv_records(rows, year, month, img_path.name)
        all_records.extend(records)

        raw_results.append({
            "file":  img_path.name,
            "year":  year,
            "month": month,
            "rows":  rows,
        })

        print(f"{len(records)} payment entries")

    # ── Save raw JSON backup ──────────────────────────────────────────────────
    with open(RAW_JSON, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, indent=2)
    print(f"\n📦 Raw JSON backup: {RAW_JSON}")

    # ── Write review CSV (strip internal _source key) ─────────────────────────
    fieldnames = ["Date", "Client Name", "Amount", "Payment Type", "Service Type"]
    with open(REVIEW_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in all_records:
            writer.writerow({k: rec[k] for k in fieldnames})

    print(f"📄 Review CSV:      {REVIEW_CSV}")
    print(f"\n✅ Done! {len(all_records)} total payment rows extracted from {len(image_files)} images.")
    print("\nPlease review handwriting_review.csv before importing to Alkas Threading.")


if __name__ == "__main__":
    main()
