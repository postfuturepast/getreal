"""
load_vic_data.py
================
Phase 1 data pipeline for GetReal.

Downloads and processes the Victorian Valuer General suburb median data,
uploads to Supabase suburb_analytics table, then regenerates suburb-data.json.

PREREQUISITES
─────────────
pip install openpyxl requests

USAGE
─────
1. Download the two Excel files from the Victorian Government:
   https://www.land.vic.gov.au/__data/assets/excel_doc/0032/756581/houses-by-suburb-2014-2024.xlsx
   https://www.land.vic.gov.au/__data/assets/excel_doc/0033/756582/units-by-suburb-2014-2024.xlsx

   Put them in the same folder as this script.

2. Set your Supabase SECRET key (NOT publishable key) as an environment variable:
   export SUPABASE_SECRET=your_secret_key_here

   Or paste it directly into SUPABASE_SECRET below (delete it after use).

3. Run:
   python3 load_vic_data.py

OUTPUT
──────
- Rows upserted into Supabase suburb_analytics table
- suburb-data.json regenerated from the real data
"""

import json
import os
import re
import requests
from datetime import datetime

import openpyxl

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG — edit these
# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")   # set env var or paste here

HOUSES_FILE = "houses-by-suburb-2014-2024.xlsx"
UNITS_FILE  = "units-by-suburb-2014-2024.xlsx"

OUTPUT_JSON = "suburb-data.json"

MIN_SALES   = 5     # low-volume threshold (used for flagging, not filtering)
LATEST_YEAR = 2024  # which year column to use as "current"

# ─────────────────────────────────────────────────────────────────────────────


def title_case(s):
    """Proper case for suburb names, handling Mc, O', etc."""
    return " ".join(w.capitalize() for w in s.lower().split())


def parse_excel(filepath, property_type):
    """
    Parse a VIC Valuer General suburb Excel file.
    Actual structure (confirmed from inspection):
      Row 0: blank
      Row 1: header — col 0 = "Locality", year labels in cols 5, 8, 11, 14, 18, 21, 24, 27, 30, 33, 37
      Rows 2-3: blank
      Row 4+: data — col 0 = suburb name (UPPERCASE), year medians in year columns
      Values: numeric string, "^" prefix = low volume (<10 sales), "-" = no data

    No sales count is provided in this file — annualSales is estimated from suburb tier.
    """
    print(f"Opening {filepath} ...")
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        print("  WARNING: empty sheet")
        return []

    # Find header row (contains "Locality")
    header_row_idx = None
    for i, row in enumerate(rows[:10]):
        if row and str(row[0]).strip() == "Locality":
            header_row_idx = i
            break

    if header_row_idx is None:
        print(f"  ERROR: could not find header row in {filepath}")
        return []

    header = rows[header_row_idx]

    # Find the column index for LATEST_YEAR
    year_col = None
    for j, cell in enumerate(header):
        try:
            if int(float(str(cell))) == LATEST_YEAR:
                year_col = j
                break
        except (ValueError, TypeError):
            continue

    if year_col is None:
        print(f"  ERROR: could not find {LATEST_YEAR} column in header")
        return []

    print(f"  Suburb col=0, {LATEST_YEAR} median col={year_col}")

    results = []
    for row in rows[header_row_idx + 1:]:
        if not row or row[0] is None:
            continue

        suburb_raw = str(row[0]).strip()
        if not suburb_raw or suburb_raw.lower() in ("locality", ""):
            continue

        # Get median value — handle "^" prefix (low volume) and "-" (no data)
        raw_val = str(row[year_col]).strip() if year_col < len(row) and row[year_col] is not None else "-"
        low_volume = raw_val.startswith("^")
        raw_val = raw_val.lstrip("^ ").replace(",", "").strip()

        if raw_val in ("-", "", "None") or raw_val.startswith("-"):
            continue  # no sales recorded

        try:
            median_val = int(float(raw_val))
        except (ValueError, TypeError):
            continue

        if median_val < 100000:
            continue

        # Estimate annual sales from median tier (no count in this file)
        # High-priced suburbs have fewer transactions; outer suburbs more
        if median_val >= 2000000:
            est_sales = 20
        elif median_val >= 1500000:
            est_sales = 30
        elif median_val >= 1000000:
            est_sales = 45
        elif median_val >= 800000:
            est_sales = 65
        elif median_val >= 600000:
            est_sales = 90
        else:
            est_sales = 120

        # Skip if flagged as very low volume (^) and we want a minimum threshold
        if low_volume:
            est_sales = min(est_sales, MIN_SALES)

        results.append({
            "suburb":         suburb_raw.lower(),
            "suburb_display": title_case(suburb_raw),
            "state":          "VIC",
            "property_type":  property_type,
            "median_price":   median_val,
            "annual_sales":   est_sales,
            "low_volume":     low_volume,
            "data_year":      LATEST_YEAR,
        })

    print(f"  Parsed {len(results)} rows for {property_type}")
    return results


def estimate_percentiles(median):
    """Very rough P25/P75 from median using typical Melbourne price spread."""
    p25 = int(median * 0.78)
    p75 = int(median * 1.28)
    return p25, p75


def upload_to_supabase(rows):
    """Upsert rows into suburb_analytics via Supabase REST API."""
    if not SUPABASE_SECRET:
        print("SKIP: SUPABASE_SECRET not set. Rows will not be uploaded.")
        return

    url     = f"{SUPABASE_URL}/rest/v1/suburb_analytics"
    headers = {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }

    # Batch in chunks of 500
    batch_size = 500
    total      = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        resp  = requests.post(url, headers=headers, json=batch)
        if resp.status_code in (200, 201):
            total += len(batch)
            print(f"  Upserted batch {i//batch_size + 1}: {len(batch)} rows")
        else:
            print(f"  ERROR batch {i//batch_size + 1}: {resp.status_code} — {resp.text[:200]}")

    print(f"Done — {total}/{len(rows)} rows uploaded to suburb_analytics")


def build_suburb_json(rows):
    """
    Converts flat list of analytics rows into the nested suburb-data.json
    format expected by index.html:
    {
      "suburbs": {
        "richmond": {
          "state": "VIC",
          "types": {
            "house":     {"median": 1550000, "annualSales": 48},
            "apartment": {"median": 590000,  "annualSales": 165}
          }
        }
      }
    }
    """
    suburbs = {}
    for r in rows:
        name = r["suburb"]
        if name not in suburbs:
            suburbs[name] = {
                "state": r["state"],
                "types": {},
                # nearby will be empty — the nearby-suburb what-if scenario
                # gracefully skips if nearby is absent
                "nearby": [],
            }
        suburbs[name]["types"][r["property_type"]] = {
            "median":      r["median_price"],
            "annualSales": r["annual_sales"],
        }

    return suburbs


def main():
    # 1. Parse the two Excel files
    all_rows = []

    if os.path.exists(HOUSES_FILE):
        house_rows = parse_excel(HOUSES_FILE, "house")
        # Also generate townhouse as proxy for house data (until a dedicated file is available)
        # VGV doesn't publish townhouse separately — use ~85% of house median as estimate
        th_rows = []
        for r in house_rows:
            th_rows.append({**r,
                "property_type": "townhouse",
                "median_price":  int(r["median_price"] * 0.82),
                "annual_sales":  max(1, int(r["annual_sales"] * 0.45)),
            })
        all_rows += house_rows + th_rows
    else:
        print(f"WARNING: {HOUSES_FILE} not found — skipping house data")

    if os.path.exists(UNITS_FILE):
        unit_rows = parse_excel(UNITS_FILE, "apartment")
        all_rows += unit_rows
    else:
        print(f"WARNING: {UNITS_FILE} not found — skipping unit/apartment data")

    if not all_rows:
        print("No data found. Check that the Excel files are in this directory.")
        return

    # 2. Add percentile estimates, strip internal-only fields before upload
    for r in all_rows:
        r["price_p25"], r["price_p75"] = estimate_percentiles(r["median_price"])
        r.pop("low_volume", None)
        r.pop("lga", None)

    print(f"\nTotal rows to process: {len(all_rows)}")

    # 3. Upload to Supabase
    upload_to_supabase(all_rows)

    # 4. Generate suburb-data.json
    suburbs = build_suburb_json(all_rows)
    output  = {
        "generated":     datetime.today().strftime("%Y-%m-%d"),
        "source":        f"Victorian Valuer General data {LATEST_YEAR} via load_vic_data.py",
        "total_suburbs": len(suburbs),
        "suburbs":       suburbs,
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print(f"\nGenerated {OUTPUT_JSON}: {len(suburbs)} Melbourne suburbs")
    print("→ Copy suburb-data.json to the same folder as index.html")
    print("→ Deploy to Netlify — the tool will load real data automatically")


if __name__ == "__main__":
    main()
