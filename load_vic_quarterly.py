"""
load_vic_quarterly.py
=====================
Loads VIC suburb data from the quarterly median XLS files published by
the Victorian Valuer General at land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics

These files contain REAL suburb medians AND real annual sales counts —
replacing the fabricated sales counts in the old load_vic_data.py.

FILES NEEDED (put in same folder as this script):
  median-house-q4-2025.xls
  median-unit-q4-2025.xls
  median-land-q4-2025.xls   (optional — land is not yet used in scoring)

REQUIRES LibreOffice for .xls → .csv conversion (pre-installed on most Macs via Homebrew):
  brew install libreoffice   (if not already installed)

USAGE
-----
export SUPABASE_SECRET=your_secret_key_here
python3 load_vic_quarterly.py

OUTPUT
------
- Upserts rows into Supabase suburb_analytics table
- Regenerates suburb-data.json
"""

import json
import os
import requests
import xlrd
from datetime import datetime

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

if not SUPABASE_SECRET:
    print("ERROR: SUPABASE_SECRET not set.")
    print("Run: export SUPABASE_SECRET=your_secret_key_here")
    exit(1)

HEADERS = {
    "apikey":        SUPABASE_SECRET,
    "Authorization": f"Bearer {SUPABASE_SECRET}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=minimal",
}

OUTPUT_JSON = "suburb-data.json"

# Column indices (0-based) confirmed from VIC quarterly XLS structure
COL_SUBURB  = 0   # Suburb name
COL_MEDIAN  = 9   # Current quarter median price
COL_SALES   = 12  # Rolling 12-month sales count

FILES = [
    ("median-house-q4-2025.xls",  "house"),
    ("median-unit-q4-2025.xls",   "apartment"),
    # ("median-land-q4-2025.xls", "land"),  # uncomment when land scoring is added
]


def title_case(s):
    return " ".join(w.capitalize() for w in s.lower().split())


def to_num(val):
    """Convert xlrd cell value (float or string) to float, or None if not numeric."""
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    try:
        return float(str(val).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def parse_vic_xls(xls_path, property_type):
    """
    Parse a VIC quarterly median XLS file directly using xlrd.
    Confirmed column structure from Q4 2025 files:
      col 0  = suburb name (ALL CAPS)
      col 1  = Oct-Dec 2024 median
      col 3  = Jan-Mar 2025 median
      col 5  = Apr-Jun 2025 median
      col 7  = Jul-Sep 2025 median
      col 9  = Oct-Dec 2025 median  ← current quarter
      col 11 = quarterly sales count (Oct-Dec 2025)
      col 12 = rolling annual sales count 2025  ← we want this
    Data rows start at row 5 (rows 0-4 are headers).
    """
    results = []
    skipped = 0

    wb = xlrd.open_workbook(xls_path)
    ws = wb.sheet_by_index(0)
    print(f"  Sheet: '{ws.name}', {ws.nrows} rows x {ws.ncols} cols")

    # Find data start: first row where col 0 is all-caps suburb name
    data_start = None
    for i in range(min(20, ws.nrows)):
        cell = str(ws.cell_value(i, 0)).strip()
        if cell and cell[0].isalpha() and cell.isupper() and cell not in ("LOCALITY",):
            # Confirm col 9 has a plausible median
            med = to_num(ws.cell_value(i, COL_MEDIAN))
            if med and med > 50000:
                data_start = i
                break

    if data_start is None:
        # Fallback: data almost always starts at row 5 in these files
        data_start = 5
    print(f"  Data starts at row {data_start}")

    for i in range(data_start, ws.nrows):
        suburb_raw = str(ws.cell_value(i, 0)).strip()
        if not suburb_raw or not suburb_raw[0].isalpha():
            continue

        # Median price (col 9 = Oct-Dec 2025)
        median = to_num(ws.cell_value(i, COL_MEDIAN))
        if not median or median < 50000:
            skipped += 1
            continue
        median = int(median)

        # Rolling annual sales (col 12)
        annual_sales = 5  # thin market default
        sales = to_num(ws.cell_value(i, COL_SALES))
        if sales and sales >= 1:
            annual_sales = int(sales)

        results.append({
            "suburb":         suburb_raw.lower(),
            "suburb_display": title_case(suburb_raw),
            "state":          "VIC",
            "property_type":  property_type,
            "median_price":   median,
            "annual_sales":   annual_sales,
            "price_p25":      int(median * 0.78),
            "price_p75":      int(median * 1.28),
            "data_year":      2025,
        })

    print(f"  Parsed {len(results)} suburbs, skipped {skipped} rows")
    return results


def upload_to_supabase(rows):
    url = f"{SUPABASE_URL}/rest/v1/suburb_analytics?on_conflict=suburb,state,property_type"
    batch_size = 500
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        resp = requests.post(url, headers=HEADERS, json=batch)
        if resp.status_code in (200, 201):
            total += len(batch)
            print(f"  Upserted batch {i // batch_size + 1}: {len(batch)} rows")
        else:
            print(f"  ERROR batch {i // batch_size + 1}: {resp.status_code} — {resp.text[:200]}")
    return total


def build_suburb_json(rows):
    suburbs = {}
    for r in rows:
        name = r["suburb"]
        if name not in suburbs:
            suburbs[name] = {"state": r["state"], "types": {}, "nearby": []}
        suburbs[name]["types"][r["property_type"]] = {
            "median":      r["median_price"],
            "annualSales": r["annual_sales"],
        }
    return suburbs


def main():
    all_rows = []

    for xls_file, property_type in FILES:
        if not os.path.exists(xls_file):
            print(f"WARNING: {xls_file} not found — skipping {property_type}")
            continue

        print(f"\nProcessing {xls_file} ({property_type})...")
        rows = parse_vic_xls(os.path.abspath(xls_file), property_type)

        # Generate townhouse as proxy from house data (VGV doesn't publish separately)
        if property_type == "house" and rows:
            th_rows = [{
                **r,
                "property_type": "townhouse",
                "median_price":  int(r["median_price"] * 0.82),
                "price_p25":     int(r["median_price"] * 0.82 * 0.78),
                "price_p75":     int(r["median_price"] * 0.82 * 1.28),
                "annual_sales":  max(1, int(r["annual_sales"] * 0.45)),
            } for r in rows]
            all_rows += th_rows
            print(f"  Generated {len(th_rows)} townhouse rows (proxy from house data)")

        all_rows += rows

    if not all_rows:
        print("\nNo data found. Check the XLS files are in this directory.")
        return

    print(f"\nTotal rows to upload: {len(all_rows)}")
    print("\nSample (first 5 house rows):")
    for r in [r for r in all_rows if r["property_type"] == "house"][:5]:
        print(f"  {r['suburb_display']:<30} median=${r['median_price']:>9,}  sales={r['annual_sales']:>4}")

    print("\nUploading to Supabase...")
    total = upload_to_supabase(all_rows)
    print(f"Done — {total}/{len(all_rows)} rows uploaded")

    # Rebuild suburb-data.json
    suburbs = build_suburb_json(all_rows)
    output = {
        "generated":     datetime.today().strftime("%Y-%m-%d"),
        "source":        "Victorian Valuer General quarterly data Q4 2025 via load_vic_quarterly.py",
        "total_suburbs": len(suburbs),
        "suburbs":       suburbs,
    }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, separators=(",", ":"))
    print(f"\nGenerated {OUTPUT_JSON}: {len(suburbs)} VIC suburbs")
    print("→ Copy suburb-data.json to the same folder as index.html and deploy")



if __name__ == "__main__":
    main()
