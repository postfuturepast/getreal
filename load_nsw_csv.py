"""
load_nsw_csv.py
===============
Phase 2 data pipeline (v2) for GetReal.

Reads the cleaned CSV from nswpropertysalesdata.com (archive.zip),
filters to the last 13 months of residential sales, deduplicates,
infers property type, and loads into the Supabase property_sales table.

This replaces load_nsw_data.py and gives us a full 13-month window
instead of the partial 5-month window from the weekly DAT files.

SOURCE
──────
https://nswpropertysalesdata.com/data/archive.zip
  → nsw-property-sales-data-updated{date}.csv
  (updated daily, 6 years of NSW Valuer General PSI data)

CSV COLUMNS (header row)
─────────────────────────
Property ID, Sale counter, Download date / time, Property name,
Property unit number, Property house number, Property street name,
Property locality, Property post code, Area, Area type,
Contract date, Settlement date, Purchase price, Zoning,
Nature of property, Primary purpose, Strata lot number,
Dealing number, Property legal description

PREREQUISITES
─────────────
pip install requests   (standard library csv/zipfile used for parsing)

USAGE
─────
1. Download archive.zip from https://nswpropertysalesdata.com/
   and place it in this project folder.

2. Set SUPABASE_SECRET:
   export SUPABASE_SECRET=your_secret_key_here

3. Run:
   python3 load_nsw_csv.py

OPTIONS
───────
   --zip         Path to archive.zip (default: archive.zip)
   --days        Rolling window in days (default: 390 = 13 months)
   --dry-run     Parse and print stats without uploading
   --batch-size  Upload batch size (default: 500)
   --clear       DELETE all existing NSW rows before loading (fresh load)
"""

import argparse
import csv
import io
import json
import os
import zipfile
from collections import defaultdict
from datetime import date, timedelta

import requests

# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

RESIDENTIAL     = "Residence"
TOWNHOUSE_MIN   = 150   # sqm — strata lots >= this → townhouse, else apartment

# ─────────────────────────────────────────────────────────────────────────────


def title_case(s):
    return " ".join(w.capitalize() for w in s.lower().split()) if s else ""


MAX_LAND_SQM = 10_000  # cap at 1 hectare — anything larger is rural/data noise

def area_to_sqm(area_str, area_type):
    try:
        val = float(area_str)
    except (ValueError, TypeError):
        return 0
    sqm = int(val * 10000) if str(area_type).strip().upper() == "H" else int(val)
    return min(sqm, MAX_LAND_SQM)


def infer_type(strata_lot, land_sqm):
    if strata_lot and str(strata_lot).strip():
        return "townhouse" if land_sqm >= TOWNHOUSE_MIN else "apartment"
    return "house"


def parse_csv(zip_path, cutoff_date):
    """
    Read the archive.zip CSV, filter to residential sales after cutoff_date,
    deduplicate by (Property ID, Sale counter), and return list of dicts.
    """
    print(f"Opening {zip_path} ...")
    records   = {}   # key: (property_id, sale_counter) → dedup
    skipped   = 0
    total_rows = 0

    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            print("ERROR: no CSV found in ZIP")
            return []
        csv_name = csv_names[0]
        print(f"  Reading {csv_name} ...")

        with zf.open(csv_name) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8"))
            for row in reader:
                total_rows += 1
                if total_rows % 200000 == 0:
                    print(f"  ... {total_rows:,} rows read, {len(records):,} kept so far")

                # Filter: residential only
                if row.get("Primary purpose", "").strip() != RESIDENTIAL:
                    skipped += 1
                    continue

                # Filter: date window
                contract_date_str = row.get("Contract date", "").strip()
                if not contract_date_str or len(contract_date_str) < 10:
                    skipped += 1
                    continue
                try:
                    contract_date = date.fromisoformat(contract_date_str[:10])
                except ValueError:
                    skipped += 1
                    continue
                if contract_date < cutoff_date:
                    skipped += 1
                    continue

                # Filter: price
                try:
                    price = int(float(row.get("Purchase price", "0")))
                except (ValueError, TypeError):
                    skipped += 1
                    continue
                if price < 50000:
                    skipped += 1
                    continue

                # Dedup key: Property ID + Sale counter
                prop_id      = row.get("Property ID", "").strip()
                sale_counter = row.get("Sale counter", "").strip()
                dedup_key    = (prop_id, sale_counter)
                if dedup_key in records:
                    skipped += 1
                    continue

                # Build record
                suburb      = row.get("Property locality", "").strip().upper()
                postcode    = str(row.get("Property post code", "")).split(".")[0].strip()
                unit_num    = row.get("Property unit number", "").strip()
                house_num   = row.get("Property house number", "").strip()
                street_name = row.get("Property street name", "").strip()
                area_raw    = row.get("Area", "0")
                area_type   = row.get("Area type", "M")
                strata_lot  = row.get("Strata lot number", "").strip()
                land_sqm    = area_to_sqm(area_raw, area_type)
                prop_type   = infer_type(strata_lot, land_sqm)

                # Build address
                addr_parts = []
                if unit_num:
                    addr_parts.append(f"{unit_num}/")
                if house_num:
                    addr_parts.append(f"{house_num} ")
                if street_name:
                    addr_parts.append(title_case(street_name))
                address_full = "".join(addr_parts).strip()
                if address_full and suburb:
                    address_full = f"{address_full}, {title_case(suburb)} NSW {postcode}".strip()

                records[dedup_key] = {
                    "suburb":        suburb.lower(),
                    "state":         "NSW",
                    "postcode":      postcode,
                    "property_type": prop_type,
                    "sale_price":    price,
                    "sale_date":     contract_date.isoformat(),
                    "address_full":  address_full,
                    "street_number": (f"{unit_num}/" if unit_num else "") + house_num,
                    "street_name":   title_case(street_name),
                    "land_size_sqm": land_sqm if land_sqm > 0 else None,
                    "enriched":      False,
                }

    print(f"  Total rows read: {total_rows:,}")
    print(f"  Kept (residential, in window, unique): {len(records):,}")
    print(f"  Skipped: {skipped:,}")
    return list(records.values())


def print_summary(records):
    by_type   = defaultdict(int)
    by_suburb = defaultdict(int)
    for r in records:
        by_type[r["property_type"]]   += 1
        by_suburb[r["suburb"]]        += 1

    print(f"\n{'─'*50}")
    print(f"Total: {len(records):,}")
    print(f"\nBy type:")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t:<15} {n:>7,}")
    print(f"\nTop 20 suburbs:")
    for s, n in sorted(by_suburb.items(), key=lambda x: -x[1])[:20]:
        print(f"  {title_case(s):<30} {n:>5,}")
    print(f"{'─'*50}\n")


def clear_nsw_rows():
    """DELETE all NSW rows from property_sales before a fresh load."""
    if not SUPABASE_SECRET:
        print("SKIP: SUPABASE_SECRET not set")
        return
    url  = f"{SUPABASE_URL}/rest/v1/property_sales?state=eq.NSW"
    resp = requests.delete(url, headers={
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Prefer":        "return=minimal",
    }, timeout=60)
    if resp.status_code in (200, 204):
        print("Cleared existing NSW rows from property_sales")
    else:
        print(f"WARNING: clear failed {resp.status_code} — {resp.text[:200]}")


def upload(rows, batch_size=500, dry_run=False):
    if dry_run:
        print(f"\n[DRY RUN] Would upload {len(rows):,} rows to property_sales")
        return
    if not SUPABASE_SECRET:
        print("SKIP: SUPABASE_SECRET not set")
        return

    url     = f"{SUPABASE_URL}/rest/v1/property_sales"
    headers = {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }

    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        resp  = requests.post(url, headers=headers, json=batch, timeout=30)
        if resp.status_code in (200, 201):
            total += len(batch)
            print(f"  Batch {i//batch_size + 1}: {len(batch)} rows "
                  f"({total:,}/{len(rows):,} total)")
        else:
            print(f"  ERROR batch {i//batch_size + 1}: "
                  f"{resp.status_code} — {resp.text[:300]}")

    print(f"\nDone — {total:,}/{len(rows):,} rows uploaded")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip",        default="archive.zip")
    parser.add_argument("--days",       type=int, default=390)
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--clear",      action="store_true",
                        help="Delete all existing NSW rows before loading")
    args = parser.parse_args()

    if not os.path.exists(args.zip):
        print(f"ERROR: {args.zip} not found. Download from https://nswpropertysalesdata.com/")
        return

    cutoff = date.today() - timedelta(days=args.days)
    print(f"Cutoff date: {cutoff} (last {args.days} days)")

    records = parse_csv(args.zip, cutoff)
    if not records:
        print("No records found.")
        return

    print_summary(records)

    if args.clear and not args.dry_run:
        clear_nsw_rows()

    upload(records, batch_size=args.batch_size, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
