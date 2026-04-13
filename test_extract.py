#!/usr/bin/env python3
"""
Quick test: run extraction on 2 images and print results without writing to CSV.
"""
import sys
sys.path.insert(0, "/Users/raj/Desktop/Handwriting")

from extract_to_csv import (
    extract_rows_from_image, rows_to_csv_records,
    filename_to_year_month, IMAGES_DIR
)
import anthropic
from pathlib import Path

client = anthropic.Anthropic()

test_images = ["Jan_25.jpg", "Apr25_1.jpg"]

for fname in test_images:
    img_path = IMAGES_DIR / fname
    year, month = filename_to_year_month(fname)
    print(f"\n{'='*60}")
    print(f"Image: {fname}  →  {year}-{month:02d}")
    print('='*60)

    rows = extract_rows_from_image(client, img_path)
    print(f"\nRaw rows extracted ({len(rows)} total):")
    for r in rows:
        print(f"  {r}")

    records = rows_to_csv_records(rows, year, month)
    print(f"\nCSV records ({len(records)} total):")
    for rec in records:
        print(f"  {rec['Date']} | {rec['Client Name']:<25} | ${rec['Amount']:>7.2f} | {rec['Payment Type']}")
