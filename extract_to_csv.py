#!/usr/bin/env python3
"""
Handwritten Table → CSV Extractor
Uses Claude Vision API to read handwritten appointment/payment tables
and convert them to a structured CSV matching the Alkas Threading project format.

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

# ── Configuration ────────────────────────────────────────────────────────────
IMAGES_DIR = Path("/Users/raj/Desktop/Handwriting/Pre-Processing/Original_Images")
OUTPUT_CSV  = Path("/Users/raj/Desktop/Handwriting/extracted_finance.csv")

# ── Month name → number ───────────────────────────────────────────────────────
MONTH_MAP = {
    "jan": 1,  "feb": 2,  "mar": 3,  "apr": 4,
    "may": 5,  "jun": 6,  "jul": 7,  "aug": 8,
    "sep": 9,  "oct": 10, "nov": 11, "dec": 12,
}

def filename_to_year_month(filename: str) -> tuple[int, int]:
    """
    Parse month and year from filename.
    Examples:  Jan_25.jpg → (2025, 1)
               Apr25_1.jpg → (2025, 4)
               Sept25_2.jpg → (2025, 9)
    """
    name = Path(filename).stem.lower()          # e.g. "apr25_1"
    # find 3-4 letter month prefix
    for abbr, num in MONTH_MAP.items():
        if name.startswith(abbr):
            return 2025, num
    raise ValueError(f"Cannot parse month from filename: {filename}")


def image_to_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


EXTRACTION_PROMPT = """You are extracting data from a handwritten business ledger page for a threading/waxing salon.

The page is divided into a LEFT half and a RIGHT half. Each half is a table with these columns (though handwriting may make labels hard to read):
  • Row number (#)
  • Client / Service Name  (the person's name)
  • Cash amount  (blank if they didn't pay cash)
  • Beni / Venmo amount  (blank if not used)
  • Zel / Zelle amount   (blank if not used)

A client may have amounts in more than one payment column (split payment).

Your job: extract EVERY row that has a name AND at least one non-zero payment amount.

Return a JSON array. Each element represents ONE payment entry:
{
  "name":         "<client name as written, best guess>",
  "cash":         <number or 0>,
  "venmo":        <number or 0>,
  "zelle":        <number or 0>
}

Rules:
- If a cell is blank, crossed out, or illegible, use 0 for that amount.
- If the name is completely illegible, skip that row entirely.
- Do NOT include the header row, total rows, or summary rows.
- Strip any stray punctuation from names.
- Numbers may use shorthand: "100" means 100, ".5" means 0.5, "1/2" means 0.5.
- If a number has a line through it (crossed out), use 0.
- Return ONLY the JSON array, no other text.

Example output:
[
  {"name": "Alice Smith", "cash": 25, "venmo": 0, "zelle": 0},
  {"name": "Bob Jones",   "cash": 0,  "venmo": 15, "zelle": 10}
]
"""


def extract_rows_from_image(client: anthropic.Anthropic, image_path: Path) -> list[dict]:
    """Send image to Claude and get back structured payment rows."""
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

    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)

    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON parse error for {image_path.name}: {e}")
        print(f"  Raw response snippet: {raw[:300]}")
        rows = []

    return rows


def rows_to_csv_records(rows: list[dict], year: int, month: int) -> list[dict]:
    """
    Convert extracted rows into finance_payments.csv-compatible records.
    Split payments (cash + venmo, etc.) become separate CSV rows.
    Date: first of the month at midnight.
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
                })

    return records


def main():
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    image_files = sorted(IMAGES_DIR.glob("*.jpg")) + sorted(IMAGES_DIR.glob("*.png"))
    if not image_files:
        print(f"No images found in {IMAGES_DIR}")
        sys.exit(1)

    print(f"Found {len(image_files)} images to process.\n")

    all_records: list[dict] = []

    for img_path in image_files:
        try:
            year, month = filename_to_year_month(img_path.name)
        except ValueError as e:
            print(f"  Skipping {img_path.name}: {e}")
            continue

        print(f"Processing {img_path.name}  ({year}-{month:02d}) …", end=" ", flush=True)

        rows = extract_rows_from_image(client, img_path)
        records = rows_to_csv_records(rows, year, month)
        all_records.extend(records)

        print(f"→ {len(records)} payment entries extracted")

    # Write output CSV
    fieldnames = ["Date", "Client Name", "Amount", "Payment Type", "Service Type"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\n✅  Done! {len(all_records)} total records written to:\n   {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
