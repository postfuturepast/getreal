#!/usr/bin/env python3
"""
build-data.py — Property Search Realism Checker data pipeline
==============================================================

Downloads free government property sales data for NSW and VIC,
processes it into suburb-level statistics, and outputs suburb-data.json
for use with index.html.

Data sources (both free, open-licence):
  NSW: NSW Valuer General bulk PSI (CC BY-NC-ND 4.0)
       https://www.valuergeneral.nsw.gov.au/design/bulk_psi_content/bulk_psi
  VIC: Valuer-General Victoria Property Sales Report (CC BY 4.0)
       https://discover.data.vic.gov.au/dataset/victorian-property-sales-report-median-house-by-suburb-time-series

Requirements:
  pip install openpyxl

Usage:
  python3 build-data.py            # builds suburb-data.json
  python3 build-data.py --year 2024  # use a specific NSW year (default: 2025)
"""

import json, zipfile, io, os, sys, statistics, argparse
from datetime import datetime
from collections import defaultdict
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────

DEFAULT_NSW_YEAR = 2025

VIC_HOUSES_URL = (
    "https://www.land.vic.gov.au/__data/assets/excel_doc"
    "/0032/756581/houses-by-suburb-2014-2024.xlsx"
)
# Note: VIC releases an updated file each year. If this URL breaks,
# check: https://discover.data.vic.gov.au/dataset/victorian-property-sales-report-median-house-by-suburb-time-series

NSW_ANNUAL_URL = "https://www.valuergeneral.nsw.gov.au/__psi/yearly/{year}.zip"

# Minimum sales required to include a suburb (avoid noise from tiny suburbs)
MIN_SALES = 5

# ── NSW property type codes (field 18 in PSI records) ────────────────────────
NSW_TYPE_MAP = {
    "RESIDENCE":    "house",
    "UNIT":         "apartment",   # includes strata townhouses
    "VACANT LAND":  None,
    "COMMERCIAL":   None,
    "INDUSTRIAL":   None,
    "RURAL":        None,
    "RETAIL":       None,
    "PRIMARY PRODUCTION": None,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def download(url: str, label: str) -> bytes:
    print(f"  Downloading {label}...", end=" ", flush=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "PropertyRealism-DataBuilder/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
        print(f"done ({len(data) // 1024:,} KB)")
        return data
    except urllib.error.HTTPError as e:
        print(f"FAILED — HTTP {e.code}: {e.reason}")
        raise
    except Exception as e:
        print(f"FAILED — {e}")
        raise


# ── NSW Parser ────────────────────────────────────────────────────────────────

def parse_nsw_zip(data: bytes) -> dict:
    """
    Parse an NSW Valuer General annual PSI ZIP file.

    Record format (semicolon-delimited, starts with 'B;'):
      [0]  Record type (B)
      [1]  District code
      [2]  Property ID
      [3]  Sequence number
      [4]  Timestamp
      [5]  Building name
      [6]  Unit number
      [7]  Street number
      [8]  Street name
      [9]  Suburb        ← we want this
      [10] Postcode
      [11] Area
      [12] Area type
      [13] Contract date
      [14] Settlement date
      [15] Purchase price  ← we want this
      [16] Zone code
      [17] Nature (R=Residential, V=Vacant, 3=Strata unit)
      [18] Primary purpose  ← we want this (RESIDENCE / UNIT / etc.)
      ...

    Returns { suburb_lower: { prop_type: [price, ...] } }
    """
    print("  Parsing NSW records...", end=" ", flush=True)
    raw = defaultdict(lambda: defaultdict(list))
    record_count = 0

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        dat_files = [n for n in zf.namelist() if n.upper().endswith(".DAT")]
        for name in dat_files:
            with zf.open(name) as f:
                for line_bytes in f:
                    line = line_bytes.decode("utf-8", errors="ignore").strip()
                    if not line.startswith("B;"):
                        continue
                    parts = line.split(";")
                    if len(parts) < 19:
                        continue

                    suburb_raw  = parts[9].strip()
                    price_str   = parts[15].strip()
                    nature      = parts[17].strip().upper()
                    purpose_raw = parts[18].strip().upper()

                    # Only residential transactions
                    if nature not in ("R", "3"):
                        continue

                    prop_type = NSW_TYPE_MAP.get(purpose_raw)
                    if prop_type is None:
                        continue

                    if not suburb_raw:
                        continue

                    try:
                        price = int(price_str)
                        if price < 50_000 or price > 100_000_000:
                            continue  # exclude obviously bad/commercial values
                    except (ValueError, TypeError):
                        continue

                    suburb_key = suburb_raw.lower()
                    raw[suburb_key][prop_type].append(price)
                    record_count += 1

    print(f"done ({record_count:,} records across {len(raw):,} suburbs)")
    return dict(raw)


def aggregate_nsw(raw: dict) -> dict:
    """
    Convert raw price lists to { suburb: { type: { median, annualSales } } }
    """
    result = {}
    for suburb, types in raw.items():
        entry = {}
        for ptype, prices in types.items():
            if len(prices) < MIN_SALES:
                continue
            sorted_prices = sorted(prices)
            entry[ptype] = {
                "median":      int(statistics.median(sorted_prices)),
                "annualSales": len(sorted_prices),
            }
        if entry:
            result[suburb] = entry
    return result


# ── VIC Parser ────────────────────────────────────────────────────────────────

def parse_vic_houses(data: bytes) -> dict:
    """
    Parse the VIC 'houses by suburb' Excel file.

    Expected structure (wide format):
      Col 0: Municipality
      Col 1: Suburb
      Col 2: 2014 Number of Sales
      Col 3: 2014 Median
      Col 4: 2015 Number of Sales
      Col 5: 2015 Median
      ...   (pairs for each year)
      Col N-1: 2024 Number of Sales
      Col N:   2024 Median

    Returns { suburb_lower: { "house": { median, annualSales } } }
    """
    try:
        import openpyxl
    except ImportError:
        print("  ✗ openpyxl not installed. Run: pip install openpyxl")
        return {}

    print("  Parsing VIC Excel...", end=" ", flush=True)

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    results = {}

    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue

        # Find header row (contains "suburb" somewhere)
        header_idx = None
        for i, row in enumerate(rows[:15]):
            if any(str(c).lower().strip() == "suburb" for c in row if c is not None):
                header_idx = i
                break

        if header_idx is None:
            continue  # skip sheets without a recognisable header

        headers = [str(h).lower().strip() if h is not None else "" for h in rows[header_idx]]

        # Find suburb column
        suburb_col = next((i for i, h in enumerate(headers) if h == "suburb"), None)
        if suburb_col is None:
            continue

        # Find all "number of sales" and "median" column indices
        sales_cols  = [i for i, h in enumerate(headers) if "number" in h or "sales" in h]
        median_cols = [i for i, h in enumerate(headers) if "median" in h]

        if not sales_cols or not median_cols:
            # Try: sometimes columns are labelled by year only — look for numeric year headers
            # and assume alternating sales/median pairs after the suburb column
            data_cols = [i for i, h in enumerate(headers)
                         if h and i > suburb_col and (h.isdigit() or "price" in h or "sale" in h)]
            if len(data_cols) >= 2:
                sales_cols  = data_cols[0::2]
                median_cols = data_cols[1::2]
            else:
                continue

        # Use the LAST (most recent) sales/median columns
        sales_col  = sales_cols[-1]
        median_col = median_cols[-1]

        for row in rows[header_idx + 1:]:
            if not row or row[suburb_col] is None:
                continue

            suburb = str(row[suburb_col]).strip()
            if not suburb or suburb.lower() in (
                "suburb", "total", "metropolitan", "country", "victoria", "lga"
            ):
                continue

            # Skip rows that look like LGA subtotals (all-caps municipality names in suburb col)
            if suburb.isupper() and len(suburb) > 3:
                continue

            try:
                sales  = int(float(str(row[sales_col])))  if row[sales_col]  else 0
                median = int(float(str(row[median_col]))) if row[median_col] else 0
            except (ValueError, TypeError):
                continue

            if sales < MIN_SALES or median < 50_000:
                continue

            key = suburb.lower()
            # Use most recent sheet's data if suburb appears multiple times
            if key not in results or results[key]["house"]["annualSales"] < sales:
                results[key] = {
                    "house": {"median": median, "annualSales": sales}
                }

    wb.close()
    print(f"done ({len(results):,} suburbs)")
    return results


# ── Merge & Output ────────────────────────────────────────────────────────────

def merge_states(nsw: dict, vic: dict) -> dict:
    """
    Merge NSW and VIC suburb data.
    NSW data wins where both states have a suburb with the same name.
    """
    merged = {}

    for suburb, types in nsw.items():
        merged[suburb] = {"state": "NSW", "types": types}

    for suburb, types in vic.items():
        if suburb in merged:
            # Same name exists in NSW — add any VIC-only property types
            for t, v in types.items():
                if t not in merged[suburb]["types"]:
                    merged[suburb]["types"][t] = v
        else:
            merged[suburb] = {"state": "VIC", "types": types}

    return merged


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build suburb-data.json from government property data")
    parser.add_argument("--year", type=int, default=DEFAULT_NSW_YEAR,
                        help=f"NSW annual file year (default: {DEFAULT_NSW_YEAR})")
    parser.add_argument("--skip-nsw", action="store_true", help="Skip NSW download (VIC only)")
    parser.add_argument("--skip-vic", action="store_true", help="Skip VIC download (NSW only)")
    args = parser.parse_args()

    print("=" * 58)
    print("  Property Search Realism Checker — Data Builder")
    print("=" * 58)
    print()

    all_nsw = {}
    all_vic = {}

    # ── NSW ──────────────────────────────────────────────────────
    if not args.skip_nsw:
        print(f"[NSW] Annual data — {args.year}")
        url = NSW_ANNUAL_URL.format(year=args.year)
        try:
            raw_bytes = download(url, f"NSW {args.year}.zip")
            raw_dict  = parse_nsw_zip(raw_bytes)
            all_nsw   = aggregate_nsw(raw_dict)
            print(f"  → {len(all_nsw):,} NSW suburbs processed\n")
        except Exception as e:
            print(f"  ✗ NSW skipped due to error: {e}\n")
    else:
        print("[NSW] Skipped\n")

    # ── VIC ──────────────────────────────────────────────────────
    if not args.skip_vic:
        print("[VIC] Houses by suburb (2014–2024)")
        try:
            vic_bytes = download(VIC_HOUSES_URL, "VIC Excel")
            all_vic   = parse_vic_houses(vic_bytes)
            print(f"  → {len(all_vic):,} VIC suburbs processed\n")
        except Exception as e:
            print(f"  ✗ VIC skipped due to error: {e}\n")
    else:
        print("[VIC] Skipped\n")

    # ── Merge ─────────────────────────────────────────────────────
    if not all_nsw and not all_vic:
        print("ERROR: No data collected. Check your internet connection and try again.")
        sys.exit(1)

    merged = merge_states(all_nsw, all_vic)

    nsw_count = sum(1 for v in merged.values() if v["state"] == "NSW")
    vic_count = sum(1 for v in merged.values() if v["state"] == "VIC")

    output = {
        "generated":     datetime.now().strftime("%Y-%m-%d"),
        "nsw_year":      args.year,
        "total_suburbs": len(merged),
        "nsw_suburbs":   nsw_count,
        "vic_suburbs":   vic_count,
        "suburbs":       merged,
    }

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suburb-data.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, separators=(",", ":"))

    size_kb = os.path.getsize(out_path) // 1024
    print("=" * 58)
    print(f"  ✅  Written: suburb-data.json")
    print(f"      {len(merged):,} suburbs  ({nsw_count:,} NSW · {vic_count:,} VIC)")
    print(f"      File size: {size_kb:,} KB")
    print()
    print("  Next step: open a terminal in this folder and run:")
    print("      python3 -m http.server 8000")
    print("  Then open:  http://localhost:8000")
    print("=" * 58)


if __name__ == "__main__":
    main()
