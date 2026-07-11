"""
load_nsw_data.py
================
Phase 2 data pipeline for GetReal.

Downloads NSW Valuer General bulk Property Sales Information (PSI) data,
parses the semicolon-delimited DAT format, infers property type from strata
flag + land size, and loads residential sales into the Supabase property_sales
table.

DATA SOURCE
───────────
NSW Valuer General — free, open-licence bulk PSI.
Annual ZIPs:   https://www.valuergeneral.nsw.gov.au/__psi/yearly/{year}.zip
Weekly ZIPs:   https://www.valuergeneral.nsw.gov.au/__psi/weekly/{YYYYMMDD}.zip

PREREQUISITES
─────────────
pip install requests

USAGE
─────
1. Set your Supabase SECRET key as an environment variable:
   export SUPABASE_SECRET=your_secret_key_here

2. Run (defaults to 2025 annual + 2026 weekly files):
   python3 load_nsw_data.py

   Or restrict to specific years (faster for testing):
   python3 load_nsw_data.py --years 2025
   python3 load_nsw_data.py --years 2025 2026_weekly

OPTIONS
───────
   --years          Which datasets to download (default: 2025 2026_weekly)
   --suburb-filter  Comma-separated list of suburbs to load (default: all NSW)
                    e.g. --suburb-filter "NEWTOWN,BONDI,SURRY HILLS,PARRAMATTA"
   --dry-run        Parse and print stats without uploading to Supabase
   --batch-size     Supabase upload batch size (default: 500)

DAT FILE FORMAT (2001 to current)
──────────────────────────────────
Each ZIP contains multiple .DAT files (one per council district).
Records are semicolon-delimited with a trailing semicolon:

  A record (header):   A;{district_code};{district_name};{file_date};
  B record (sale):     B;{district};{property_id};{sale_counter};{dealing};
                         {property_name};{unit_number};{house_number};
                         {street_name};{suburb};{postcode};{area};{area_type};
                         {contract_date};{settlement_date};{purchase_price};
                         {zones};{nature_of_property};{primary_purpose};
                         {strata_lot_number};{component_code};{sale_code};
                         {interest_of_sale};
  C record (total):    C;{total_records};

Key fields:
  [6]  unit_number        — blank for Torrens (house), set for strata
  [7]  house_number       — street number
  [8]  street_name
  [9]  suburb             — UPPERCASE
  [10] postcode
  [11] area               — land size (numeric)
  [12] area_type          — H=hectares, M=sqm
  [13] contract_date      — YYYYMMDD
  [15] purchase_price
  [17] zone_code          — R=Residential zone
  [18] primary_purpose    — 'RESIDENCE' = residential (we only load these)
  [19] strata_lot_number  — non-blank = strata title (unit/apartment/townhouse)

PROPERTY TYPE INFERENCE
───────────────────────
  strata_lot == blank AND land_area > 0 → house
  strata_lot == blank AND land_area == 0 → house (unknown land size)
  strata_lot != blank AND land_area >= 150 sqm  → townhouse
  strata_lot != blank AND land_area < 150 sqm   → apartment
  (townhouse threshold is approximate — strata townhouses are common in NSW)

OUTPUT
──────
- Rows upserted into Supabase property_sales table
- Console summary of records loaded by suburb/type
"""

import argparse
import io
import json
import os
import sys
import zipfile
from datetime import datetime, date, timedelta
from urllib.request import urlretrieve

import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

# Only residential properties (primary_purpose field, index [18])
RESIDENTIAL_CODE = "RESIDENCE"

# Property type inference threshold (strata lot + land size)
TOWNHOUSE_MIN_SQM = 150   # strata lots >= this → townhouse, else apartment

# Rolling window — only load sales within this many days
DAYS_WINDOW = 13 * 30     # ~13 months

# Download cache folder (re-use ZIPs between runs)
CACHE_DIR = ".nsw_psi_cache"

BASE_URL_ANNUAL = "https://www.valuergeneral.nsw.gov.au/__psi/yearly/{year}.zip"
BASE_URL_WEEKLY = "https://www.valuergeneral.nsw.gov.au/__psi/weekly/{date}.zip"

# Weekly dates to download for 2026 (Jan–May, the weeks published on the site)
WEEKLY_2026 = [
    "20260105", "20260112", "20260119", "20260126",
    "20260202", "20260209", "20260216", "20260223",
    "20260302", "20260309", "20260316", "20260323", "20260330",
    "20260406", "20260413", "20260420", "20260427",
    "20260504", "20260511", "20260518", "20260525",
]

# ─────────────────────────────────────────────────────────────────────────────


def title_case(s):
    return " ".join(w.capitalize() for w in s.lower().split())


def parse_date(s):
    """Parse YYYYMMDD string to date, return None if invalid."""
    s = s.strip()
    if not s or len(s) != 8:
        return None
    try:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def area_to_sqm(area_str, area_type):
    """Convert area to sqm. area_type: H=hectares, M=sqm."""
    try:
        val = float(area_str.strip())
    except (ValueError, TypeError):
        return 0
    if area_type and area_type.strip().upper() == "H":
        return int(val * 10000)
    return int(val)


def infer_property_type(strata_lot, land_sqm):
    """Infer property type from strata lot number and land size."""
    if strata_lot and strata_lot.strip():
        # Strata title — unit, apartment, or strata townhouse
        if land_sqm >= TOWNHOUSE_MIN_SQM:
            return "townhouse"
        return "apartment"
    # Torrens title — house (or large rural block, but nature filter handles that)
    return "house"


def parse_dat_file(content_bytes, cutoff_date=None, suburb_filter=None):
    """
    Parse a single NSW PSI .DAT file (bytes).
    Returns list of dicts ready for Supabase.
    """
    records = []
    try:
        text = content_bytes.decode("latin-1")
    except Exception:
        return records

    for line in text.splitlines():
        if not line.startswith("B;"):
            continue

        parts = line.split(";")
        # B records should have at least 22 fields
        if len(parts) < 22:
            continue

        # Unpack key fields (1-indexed in docs = 0-indexed after split)
        # [0]=B [1]=district [2]=property_id [3]=sale_counter [4]=dealing
        # [5]=property_name [6]=unit_number [7]=house_number [8]=street_name
        # [9]=suburb [10]=postcode [11]=area [12]=area_type [13]=contract_date
        # [14]=settlement_date [15]=purchase_price [16]=zones
        # [17]=nature_of_property [18]=primary_purpose [19]=strata_lot_number
        # [20]=component_code [21]=sale_code [22]=interest_of_sale

        primary_purpose = parts[18].strip().upper() if len(parts) > 18 else ""
        if primary_purpose != RESIDENTIAL_CODE:
            continue

        suburb_raw = parts[9].strip().upper() if len(parts) > 9 else ""
        if not suburb_raw:
            continue

        if suburb_filter and suburb_raw not in suburb_filter:
            continue

        contract_date = parse_date(parts[13]) if len(parts) > 13 else None
        if contract_date is None:
            continue

        if cutoff_date and contract_date < cutoff_date:
            continue

        price_str = parts[15].strip() if len(parts) > 15 else ""
        try:
            price = int(price_str)
        except (ValueError, TypeError):
            continue

        if price < 50000:
            continue  # skip clearly bad/nominal transfers

        postcode    = parts[10].strip() if len(parts) > 10 else ""
        area_raw    = parts[11].strip() if len(parts) > 11 else "0"
        area_type   = parts[12].strip() if len(parts) > 12 else "M"
        land_sqm    = area_to_sqm(area_raw, area_type)
        strata_lot  = parts[19].strip() if len(parts) > 19 else ""
        unit_number = parts[6].strip()  if len(parts) > 6  else ""
        house_num   = parts[7].strip()  if len(parts) > 7  else ""
        street_name = parts[8].strip()  if len(parts) > 8  else ""

        prop_type = infer_property_type(strata_lot, land_sqm)

        # Build address
        address_parts = []
        if unit_number:
            address_parts.append(f"{unit_number}/")
        if house_num:
            address_parts.append(house_num + " ")
        if street_name:
            address_parts.append(title_case(street_name))
        address_full = "".join(address_parts).strip()
        if address_full and suburb_raw:
            address_full = f"{address_full}, {title_case(suburb_raw)} NSW {postcode}".strip()

        records.append({
            "suburb":        suburb_raw.lower(),
            "state":         "NSW",
            "postcode":      postcode,
            "property_type": prop_type,
            "sale_price":    price,
            "sale_date":     contract_date.isoformat(),
            "address_full":  address_full,
            "street_number": (unit_number + "/" if unit_number else "") + house_num,
            "street_name":   title_case(street_name),
            "land_size_sqm": land_sqm if land_sqm > 0 else None,
            "enriched":      False,
        })

    return records


def download_zip(url, cache_path):
    """Download ZIP to cache_path if not already cached. Returns bytes."""
    if os.path.exists(cache_path):
        print(f"  (cached) {os.path.basename(cache_path)}")
        with open(cache_path, "rb") as f:
            return f.read()

    print(f"  Downloading {url} ...")
    try:
        resp = requests.get(url, timeout=120, stream=True)
        if resp.status_code == 404:
            print(f"  SKIP: 404 — {url}")
            return None
        resp.raise_for_status()
        data = resp.content
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "wb") as f:
            f.write(data)
        return data
    except Exception as e:
        print(f"  ERROR downloading {url}: {e}")
        return None


def process_zip(zip_bytes, cutoff_date, suburb_filter, label):
    """Parse all .DAT files inside a ZIP. Returns list of record dicts."""
    all_records = []
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            dat_files = [n for n in zf.namelist() if n.upper().endswith(".DAT")]
            print(f"  {label}: {len(dat_files)} DAT files in ZIP")
            for name in dat_files:
                with zf.open(name) as f:
                    records = parse_dat_file(f.read(), cutoff_date, suburb_filter)
                    all_records.extend(records)
    except zipfile.BadZipFile as e:
        print(f"  ERROR: bad ZIP for {label}: {e}")
    return all_records


def upload_to_supabase(rows, batch_size=500, dry_run=False):
    """Upsert rows into property_sales via Supabase REST API."""
    if dry_run:
        print(f"\n[DRY RUN] Would upload {len(rows)} rows to property_sales")
        return

    if not SUPABASE_SECRET:
        print("SKIP: SUPABASE_SECRET not set.")
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
            print(f"  Uploaded batch {i // batch_size + 1}: {len(batch)} rows "
                  f"({total}/{len(rows)} total)")
        else:
            print(f"  ERROR batch {i // batch_size + 1}: "
                  f"{resp.status_code} — {resp.text[:300]}")

    print(f"\nDone — {total}/{len(rows)} rows uploaded to property_sales")


def print_summary(records):
    """Print breakdown by property type and top 20 suburbs."""
    by_type = {}
    by_suburb = {}
    for r in records:
        pt = r["property_type"]
        sb = r["suburb"]
        by_type[pt]     = by_type.get(pt, 0) + 1
        by_suburb[sb]   = by_suburb.get(sb, 0) + 1

    print(f"\n{'─'*50}")
    print(f"Total records:  {len(records):,}")
    print(f"\nBy property type:")
    for pt, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {pt:<15} {n:>6,}")

    print(f"\nTop 20 suburbs:")
    for sb, n in sorted(by_suburb.items(), key=lambda x: -x[1])[:20]:
        print(f"  {title_case(sb):<30} {n:>5,}")
    print(f"{'─'*50}\n")


def main():
    parser = argparse.ArgumentParser(description="Load NSW property sales into Supabase")
    parser.add_argument("--years", nargs="+", default=["2025", "2026_weekly"],
                        help="Which datasets: e.g. 2025 2026_weekly")
    parser.add_argument("--suburb-filter", default=None,
                        help="Comma-separated suburbs to load (UPPERCASE), e.g. NEWTOWN,BONDI")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse but don't upload")
    parser.add_argument("--batch-size", type=int, default=500,
                        help="Supabase upload batch size")
    args = parser.parse_args()

    suburb_filter = None
    if args.suburb_filter:
        suburb_filter = {s.strip().upper() for s in args.suburb_filter.split(",")}
        print(f"Suburb filter: {suburb_filter}")

    # Only load sales within the rolling window
    cutoff_date = date.today() - timedelta(days=DAYS_WINDOW)
    print(f"Cutoff date:   {cutoff_date} (last {DAYS_WINDOW // 30} months)")

    os.makedirs(CACHE_DIR, exist_ok=True)
    all_records = []

    for dataset in args.years:
        if dataset == "2026_weekly":
            print(f"\n── 2026 Weekly files ({len(WEEKLY_2026)} weeks) ──")
            for week_date in WEEKLY_2026:
                url  = BASE_URL_WEEKLY.format(date=week_date)
                path = os.path.join(CACHE_DIR, f"weekly_{week_date}.zip")
                data = download_zip(url, path)
                if data:
                    records = process_zip(data, cutoff_date, suburb_filter, week_date)
                    all_records.extend(records)
                    print(f"    → {len(records):,} residential records")
        else:
            # Annual file
            print(f"\n── Annual {dataset} ──")
            url  = BASE_URL_ANNUAL.format(year=dataset)
            path = os.path.join(CACHE_DIR, f"annual_{dataset}.zip")
            data = download_zip(url, path)
            if data:
                records = process_zip(data, cutoff_date, suburb_filter, dataset)
                all_records.extend(records)
                print(f"  → {len(records):,} residential records")

    if not all_records:
        print("\nNo records found. Check downloads or suburb filter.")
        return

    print_summary(all_records)

    # Deduplicate within this batch (same address + date + price)
    seen    = set()
    deduped = []
    for r in all_records:
        key = (r["address_full"], r["sale_date"], r["sale_price"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    print(f"After dedup: {len(deduped):,} records")

    upload_to_supabase(deduped, batch_size=args.batch_size, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
