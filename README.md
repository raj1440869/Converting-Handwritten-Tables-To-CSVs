# Converting Handwritten Payment Tables to CSV

A record of the full journey to digitize 11 months of handwritten salon payment ledgers — including two failed approaches and the final working solution using Claude Vision.

---

## The Problem

A threading salon tracked every client payment by hand in paper ledgers throughout 2025 (January – November). Each page was a table with columns for client name, cash, Venmo, and Zelle amounts. By year-end there were 56 scanned page-halves covering ~1,900+ individual payment records that needed to live in a finance management app.

The goal: read the handwritten tables, extract every row, and produce a clean CSV that the app could load.

---

## What Didn't Work

### Attempt 1 — Fine-tuning Microsoft's Azure OCR Model

The first instinct was to use a production OCR engine (Azure Cognitive Services / Document Intelligence) since it already knows how to read text. The plan was to hand-label a training set of 1,000+ data points — names, dates, and payment amounts — and fine-tune the model on the specific handwriting style.

**Why it failed:**

- Azure's form recognition model is designed for *printed* or *typed* forms. Fine-tuning it on cursive/casual handwriting requires enormous labeled datasets and the results on informal, mixed-language names (the ledger includes names like "Narm (2) FIF", "Ruby Catelina", "Anisa Bench", etc.) were poor.
- The model consistently misread numbers with dollar shorthand (e.g., `20` written with a loop being read as `20.0` or garbage), and multi-word names with parenthetical notes broke the bounding-box detection.
- Data labeling at the scale needed (every cell in 56 images) was a project in itself before any model training could begin.
- The fine-tuning pipeline required cloud credits, a labeled dataset in a specific JSON schema (COCO-style bounding boxes), multiple training iterations, and the model still couldn't generalize to new pages.

### Attempt 2 — Digit Segmentation + Fine-tuned MNIST

The second idea was to isolate the numeric columns (Cash, Venmo, Zelle) and treat them as a digit recognition problem using MNIST, since MNIST is the canonical handwritten digit dataset.

The pipeline was:

1. Detect table grid lines with morphological operations (OpenCV)
2. Crop each individual cell
3. Segment each digit within a cell
4. Classify each digit with a CNN fine-tuned on MNIST plus a "blank" class
5. Concatenate digits back into numbers

**Why it also failed:**

- Grid detection worked reasonably well (`Analyze.py` saved debug images to `_Debug_Grids/`), but digit *segmentation within a cell* broke on real handwriting. Digits that touch or overlap (common when writing quickly) couldn't be reliably separated.
- The fine-tuned MNIST model hit ~60% accuracy on the salon's actual handwriting — not even close to usable for financial data where a misread `1` as `7` is a significant error.
- Even perfect digit classification can't read *names* at all. The name column — the most important part for matching records to clients — required a completely different approach.
- A custom model for this (handling both names and numbers, in any handwriting) would effectively require building a full OCR system from scratch.

---

## What Actually Worked — Claude Vision

Rather than training a model, the solution was to use a vision-language model that already understands handwriting in context: **Claude Vision** (Anthropic's multimodal API).

### Pre-Processing Pipeline

Before sending images to Claude, the scans were processed into a cleaner form:

**Step 1 — Grayscale conversion** (`Pre-Processing/GrayScale.py`)

Converts color scans to grayscale to reduce noise and normalize contrast across different scan sessions.

**Step 2 — Table splitting** (`Pre-Processing/Split_Tables.py`)

Each original scan captured two table pages side-by-side. The script:
- Detects vertical grid lines using morphological erosion/dilation
- Finds the center "spine" divider
- Crops out the first-column row numbers (not useful for extraction)
- Saves a `_1.jpg` (left half) and `_2.jpg` (right half) for every scan

This produced 56 individual table images in `Pre-Processing/Seperated Tables/`.

**Step 3 — Cell extraction** (`Pre-Processing/Analyze.py`)

An optional step (used during the MNIST phase) that detects the full grid, skips header rows, and saves every individual cell as its own image. The `_Debug_Grids/` overlay images were useful for validating grid detection accuracy.

### Training Data Pipeline (for the failed fine-tuning attempts)

`Training_Data/Create_CSVs.py` — built the training CSVs by reading image filenames from the hand-labeled training folders. Name images were named `{client name}.jpg`; number images were named `{value}.jpg`. This generated `name_data.csv` and `number_data.csv` pairing each image file to its ground-truth label.

Over 1,000 data points were labeled by hand. The labels were ultimately not used because the model approaches they were intended for didn't work.

### Vision Extraction

`extract_separated_tables.py` — the working extraction script. For each of the 56 pre-processed images it:

1. Sends the image to Claude Vision with a structured prompt explaining the table layout (columns: name, cash, Venmo, Zelle)
2. Instructs the model to return a JSON array of every row with a non-zero payment
3. Parses the JSON response and expands split payments (a client who paid both cash and Venmo) into separate rows
4. Tags each record with year and month (inferred from the image filename)

Because the API rate limit meant processing all 56 images serially would be slow, 8 parallel Claude agents were run, each handling 6–10 images. The results were saved as batch JSON files.

`compile_csv.py` — merges all batch JSON files, sorts by (year, month, client name), deduplicates consecutive identical records (same name + amount + payment type within the same month that appeared twice due to overlapping page coverage), and writes the final CSV.

### Output Format

```
Date,Client Name,Amount,Payment Type,Service Type
2025-01-01T00:00:00,Ahmad Babar,20,Cash,
2025-01-01T00:00:00,Ahmad Babar,10,Venmo,
2025-03-01T00:00:00,Ruby Catelina,20,Venmo,
```

Dates are set to the 1st of the corresponding month since only month/year were available from the scans.

The final CSV was imported directly into the Alkas Threading finance management app.

---

## Results

| Month | Records |
|-------|---------|
| Jan 2025 | 66 |
| Feb 2025 | 140 |
| Mar 2025 | 139 |
| Apr 2025 | 195 |
| May 2025 | 303 |
| Jun 2025 | 262 |
| Jul 2025 | 217 |
| Aug 2025 | 95 |
| Sep 2025 | 218 |
| Oct 2025 | 159 |
| Nov 2025 | 130 |
| **Total** | **1,924** |

---

## Repository Contents

```
.
├── Pre-Processing/
│   ├── Analyze.py              # Grid detection + cell cropping (MNIST phase)
│   ├── GrayScale.py            # Grayscale conversion
│   └── Split_Tables.py         # Split dual-page scans into individual table halves
│
├── Training_Data/
│   └── Create_CSVs.py          # Build training label CSVs from image filenames
│
├── extract_to_csv.py           # Claude Vision extractor (original images version)
├── extract_separated_tables.py # Claude Vision extractor (pre-split images version)
├── compile_csv.py              # Merge batch JSONs → final CSV + Alkas import
└── test_extract.py             # Quick 2-image test run
```

> **Note:** Images, batch JSON files, and extracted CSVs are excluded from this repository because they contain real client payment records. Only the code is tracked.

---

## Dependencies

```
anthropic       # Claude Vision API
opencv-python   # Image processing (cv2)
numpy           # Grid line detection math
```

Install with:
```
pip install anthropic opencv-python numpy
```

To use `extract_separated_tables.py` or `extract_to_csv.py`, set your Anthropic API key:
```
export ANTHROPIC_API_KEY=your_key_here
```
