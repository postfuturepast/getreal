"""
generate_nsw_suburb_data.py
============================
Reads archive.zip (from nswpropertysalesdata.com), aggregates per suburb +
property type, and merges the result into suburb-data.json alongside the
existing VIC data.

This gives autocomplete and what-if cards accurate medians based on the full
146k-row dataset rather than the old 5-month cached weekly ZIPs.

USAGE
─────
python3 generate_nsw_suburb_data.py

OPTIONS
───────
  --zip    Path to archive.zip (default: archive.zip)
  --days   Rolling window in days (default: 390 = 13 months)

OUTPUT
──────
suburb-data.json updated: VIC suburbs (from VGV) + NSW suburbs (from archive.zip)
"""

import argparse
import csv
import io
import json
import zipfile
from collections import defaultdict
from datetime import date, timedelta

# ─────────────────────────────────────────────────────────────────────────────

OUTPUT_JSON   = "suburb-data.json"
RESIDENTIAL   = "Residence"
TOWNHOUSE_MIN = 150    # sqm — strata lots >= this → townhouse, else apartment
MIN_SALES     = 3      # skip suburb+type combos thinner than this
MAX_LAND_SQM  = 10_000 # cap to avoid rural/data-noise outliers

# ─────────────────────────────────────────────────────────────────────────────


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
    print(f"Opening {zip_path} ...")
    records = []
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
                if total_rows % 500_000 == 0:
                    print(f"  ... {total_rows:,} rows read, {len(records):,} kept")

                if row.get("Primary purpose", "").strip() != RESIDENTIAL:
                    continue

                contract_date_str = row.get("Contract date", "").strip()
                if not contract_date_str or len(contract_date_str) < 10:
                    continue
                try:
                    contract_date = date.fromisoformat(contract_date_str[:10])
                except ValueError:
                    continue
                if contract_date < cutoff_date:
                    continue

                try:
                    price = int(float(row.get("Purchase price", "0")))
                except (ValueError, TypeError):
                    continue
                if price < 50000:
                    continue

                suburb     = row.get("Property locality", "").strip().lower()
                area_raw   = row.get("Area", "0")
                area_type  = row.get("Area type", "M")
                strata_lot = row.get("Strata lot number", "").strip()
                land_sqm   = area_to_sqm(area_raw, area_type)
                prop_type  = infer_type(strata_lot, land_sqm)

                if suburb:
                    records.append({"suburb": suburb, "type": prop_type, "price": price})

    print(f"  Total rows read: {total_rows:,}")
    print(f"  Residential in window: {len(records):,}")
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip",  default="archive.zip")
    parser.add_argument("--days", type=int, default=390)
    args = parser.parse_args()

    import os
    if not os.path.exists(args.zip):
        print(f"ERROR: {args.zip} not found.")
        print("Download from https://nswpropertysalesdata.com/ and place in this folder.")
        return

    cutoff = date.today() - timedelta(days=args.days)
    print(f"Cutoff date: {cutoff} (last {args.days} days)\n")

    records = parse_csv(args.zip, cutoff)
    if not records:
        print("No records found.")
        return

    # ─── Aggregate per suburb + type ─────────────────────────────────────────

    by_suburb_type = defaultdict(list)
    for r in records:
        by_suburb_type[(r["suburb"], r["type"])].append(r["price"])

    suburbs_nsw = {}
    for (suburb, prop_type), prices in by_suburb_type.items():
        if len(prices) < MIN_SALES:
            continue
        if suburb not in suburbs_nsw:
            suburbs_nsw[suburb] = {"state": "NSW", "types": {}, "nearby": []}
        sorted_prices = sorted(prices)
        median = sorted_prices[len(sorted_prices) // 2]
        suburbs_nsw[suburb]["types"][prop_type] = {
            "median":      median,
            "annualSales": len(prices),
        }

    print(f"\nNSW suburbs with enough data: {len(suburbs_nsw):,}")

    # ─── Load existing VIC suburb-data.json ──────────────────────────────────

    try:
        with open(OUTPUT_JSON) as f:
            existing = json.load(f)
        # Keep only VIC suburbs from the existing file
        vic_suburbs = {k: v for k, v in existing.get("suburbs", {}).items()
                       if v.get("state") == "VIC"}
        print(f"Existing VIC suburbs loaded: {len(vic_suburbs):,}")
    except FileNotFoundError:
        print(f"Warning: {OUTPUT_JSON} not found — starting with NSW only")
        vic_suburbs = {}

    # ─── Merge and write ─────────────────────────────────────────────────────

    merged = {**vic_suburbs, **suburbs_nsw}

    output = {
        "generated":     str(date.today()),
        "source":        f"Victorian VGV + NSW nswpropertysalesdata.com (generated {date.today()})",
        "total_suburbs": len(merged),
        "suburbs":       merged,
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, separators=(",", ":"))

    print(f"\nWritten {OUTPUT_JSON}: {len(merged)} suburbs total")
    print(f"  VIC: {len(vic_suburbs)}  |  NSW: {len(suburbs_nsw)}")
    print("→ Deploy to Netlify")


if __name__ == "__main__":
    main()
