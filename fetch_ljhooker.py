#!/usr/bin/env python3
"""
fetch_ljhooker.py — Harvest LJ Hooker sold listings → Supabase sourced_sales_nsw

Approach:
  1. Load NSW office IDs from ljhooker_nsw_offices.json (run discover_ljhooker_offices.py first)
  2. For each office, paginate through all sold listings (limit=100 per page)
  3. Parse address, bedrooms, bathrooms, parking, price, category
  4. Upsert to sourced_sales_nsw with source='ljhooker'

Property type mapping (→ property_type_code):
  House → house
  Unit / Apartment / Studio / Flat → unit
  Townhouse / Terrace → townhouse
  Villa / Duplex → unit  (closest match)
  Block / Land → skip

Price parsing:
  "Sold For $920,000" → 920000
  "SOLD" → None (undisclosed)

Usage:
  export SUPABASE_SECRET=your_secret_key
  python3 fetch_ljhooker.py

Deduplication note:
  source_id = linkUrl path slug (globally unique per listing)
  Upsert on (source, source_id) — safe to re-run.

Proxy note:
  Clears http(s)_proxy env vars within this process only.
  The corporate proxy (localhost:3128) doesn't exist on home networks.
  Your shell profile is untouched.
"""

import os
import re
import sys
import time
import json
import requests
from datetime import datetime

# ── Clear corporate proxy (safe: does not touch shell profile) ────────────────
for _k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
    os.environ.pop(_k, None)

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET", "")
if not SUPABASE_KEY:
    print("ERROR: SUPABASE_SECRET env var not set.")
    sys.exit(1)

LJH_BASE_URL = "https://api01.ljx.com.au/website/search-v1"
OFFICES_FILE  = "ljhooker_offices.json"
TARGET_STATE  = "NSW"   # change to "VIC" etc. when harvesting other states
SOURCE_NAME  = "ljhooker"
PAGE_SIZE    = 100
MAX_PAGES    = 50          # safety cap: 5,000 listings per office max
REQUEST_DELAY = 0.3        # seconds between API calls
UPSERT_BATCH  = 200        # records per Supabase upsert

LJH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://blacktown.ljhooker.com.au/",
}

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates",
}

SESSION = requests.Session()
SESSION.headers.update(LJH_HEADERS)

# ── Street type vocabulary (for splitting name from type) ─────────────────────
STREET_TYPE_WORDS = {
    "STREET", "AVENUE", "ROAD", "DRIVE", "COURT", "CLOSE", "PLACE",
    "TERRACE", "CRESCENT", "BOULEVARD", "HIGHWAY", "PARADE", "GROVE",
    "LANE", "CIRCUIT", "ESPLANADE", "BROADWAY", "PARKWAY", "RIDGE",
    "MEWS", "ROW", "SQUARE", "QUAY", "CHASE", "VALE", "VIEW", "BEND",
    "COVE", "DALE", "EDGE", "END", "GATE", "HILL", "LINE", "PASS",
    "PATH", "RING", "RUN", "TURN", "WALK", "WAY", "LOOP", "LINK",
    "RISE", "TRACK", "PARK", "NOOK", "GLEN", "GREEN", "GRANGE",
    "FREEWAY", "BYPASS", "POINT", "MOUNT", "CROSS", "GARDENS", "HEIGHTS",
}

# ── Category normalisation ─────────────────────────────────────────────────────
CATEGORY_MAP = {
    "house":       "house",
    "acreage":     "house",
    "rural":       "house",
    "unit":        "unit",
    "apartment":   "unit",
    "studio":      "unit",
    "flat":        "unit",
    "townhouse":   "townhouse",
    "villa":       "unit",
    "duplex":      "unit",
    "semi":        "unit",
    "terrace":     "townhouse",
    "block":       None,    # vacant land — skip
    "land":        None,
}

def normalise_category(raw: str):
    return CATEGORY_MAP.get(raw.strip().lower(), "unit")


def parse_price(price_display):
    """Extract integer sale price from 'Sold For $920,000', or None."""
    m = re.search(r'\$([0-9,]+)', price_display or "")
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def split_street(name_and_type: str):
    """
    Split 'Mantaka Street' → ('MANTAKA', 'STREET')
    Split 'Carmelita Circuit' → ('CARMELITA', 'CIRCUIT')
    Split 'Unknown Name' → ('UNKNOWN NAME', None)
    """
    parts = name_and_type.strip().upper().split()
    if not parts:
        return ("", None)
    if len(parts) >= 2 and parts[-1] in STREET_TYPE_WORDS:
        return (" ".join(parts[:-1]), parts[-1])
    return (" ".join(parts), None)


def parse_address(address1: str) -> dict:
    """
    Parse LJH address1 into components.
    Examples:
      "33/25 Mantaka Street"  → unit_part="33", street_number="25", street_name="MANTAKA", street_type="STREET"
      "41 Carmelita Circuit"  → street_number="41", street_name="CARMELITA", street_type="CIRCUIT"
      "6/8-10 Lancaster St"   → unit_part="6", street_number="8-10", street_name="LANCASTER", street_type="ST"
    """
    raw = address1.strip()

    # Check for unit/lot prefix: digits/digits
    unit_number = None
    unit_match = re.match(r'^(\d+)[/\\](.+)$', raw)
    if unit_match:
        unit_number = unit_match.group(1)
        raw = unit_match.group(2).strip()

    # Extract leading street number (digits, optional hyphen range, optional letter suffix)
    street_number = None
    name_type_str = raw
    num_match = re.match(r'^([\d][\d\-]*[A-Za-z]?)\s+(.+)$', raw)
    if num_match:
        street_number = num_match.group(1)
        name_type_str = num_match.group(2).strip()

    street_name, street_type = split_street(name_type_str)

    # For units: store combined street_number as "unit/building" (matches Ray White convention)
    if unit_number and street_number:
        combined_number = f"{unit_number}/{street_number}"
    elif street_number:
        combined_number = street_number
    else:
        combined_number = None

    return {
        "street_number": combined_number,
        "street_name":   street_name,
        "street_type":   street_type,
    }


def extract_source_id(link_url: str) -> str:
    """Use the slug at end of the property URL as stable unique ID."""
    return link_url.rstrip("/").split("/")[-1]


def fetch_office_page(office_id, page, retries=3, backoff=2):
    """Fetch one page of sold listings for a given office, with retry."""
    params = {
        "searchOrigin":      "residential-au",
        "searchProfile":     "sold",
        "officeId":          office_id,
        "orderBy":           "date-desc",
        "surroundingSuburbs": "false",
        "page":              page,
        "limit":             PAGE_SIZE,
    }
    last_exc = None
    for attempt in range(retries):
        try:
            r = SESSION.get(LJH_BASE_URL, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_exc = e
            wait = backoff * (2 ** attempt)
            print(f"    ⚠ Page {page} attempt {attempt+1} failed: {e} — retrying in {wait}s")
            time.sleep(wait)
    raise last_exc


def build_record(prop):
    """Convert a LJH property dict to our sourced_sales schema."""
    addr = prop.get("address", {})
    state = addr.get("state", "").upper()
    if state != "NSW":
        return None  # skip non-NSW

    category = normalise_category(prop.get("category", ""))
    if category is None:
        return None  # skip vacant land

    link_url = prop.get("linkUrl", "")
    source_id = extract_source_id(link_url)
    if not source_id:
        return None

    parsed = parse_address(addr.get("address1", ""))
    suburb  = addr.get("suburb", "").strip().upper()
    postcode = addr.get("postcode", "").strip()
    price   = parse_price(prop.get("priceDisplay", ""))

    def to_int(val):
        try:
            return int(val) if val is not None else None
        except (ValueError, TypeError):
            return None

    return {
        "source":             SOURCE_NAME,
        "source_id":          source_id,
        "sourced_at":         datetime.utcnow().isoformat(),
        "street_number":      parsed["street_number"],
        "street_name":        parsed["street_name"],
        "street_type":        parsed["street_type"],
        "suburb":             suburb,
        "state_code":         "NSW",
        "postcode":           postcode,
        "bedrooms":           to_int(prop.get("bedrooms")),
        "bathrooms":          to_int(prop.get("bathrooms")),
        "car_spaces":         to_int(prop.get("parking")),
        "property_type_code": category,
        "sold_price":         price,
        "sold_date":          None,   # LJH API doesn't expose sale date
    }


def upsert_records(records: list) -> int:
    """Batch-upsert records to sourced_sales_nsw. Returns count upserted."""
    if not records:
        return 0
    url = f"{SUPABASE_URL}/rest/v1/sourced_sales_nsw?on_conflict=source,source_id"
    total = 0
    for i in range(0, len(records), UPSERT_BATCH):
        batch = records[i:i + UPSERT_BATCH]
        r = requests.post(url, headers=SB_HEADERS, json=batch, timeout=30)
        if r.status_code not in (200, 201):
            print(f"    ⚠ Upsert error {r.status_code}: {r.text[:200]}")
        else:
            total += len(batch)
    return total


def harvest_office(office):
    """Fetch all pages for one office. Returns (fetched, upserted)."""
    office_id   = office["officeId"]
    office_name = office.get("name", f"Office {office_id}")

    try:
        first = fetch_office_page(office_id, 1)
    except Exception as e:
        print(f"  ✗ {office_name} (ID {office_id}): fetch error — {e}")
        return 0, 0

    total_props = first.get("totalProperties", 0)
    total_pages = min(first.get("pages", 1), MAX_PAGES)

    if total_props == 0:
        print(f"  — {office_name} (ID {office_id}): no sold listings")
        return 0, 0

    print(f"  → {office_name} (ID {office_id}): {total_props} sold, {total_pages} pages")

    all_pages = {1: first}

    for page in range(2, total_pages + 1):
        try:
            time.sleep(REQUEST_DELAY)
            all_pages[page] = fetch_office_page(office_id, page)
        except Exception as e:
            print(f"    ⚠ Page {page} error: {e}")
            break

    all_records = []
    for _, data in sorted(all_pages.items()):
        for prop in data.get("properties", []):
            rec = build_record(prop)
            if rec:
                all_records.append(rec)

    upserted = upsert_records(all_records)
    print(f"    ✓ {len(all_records)} records built, {upserted} upserted")
    return len(all_records), upserted


def load_offices():
    """Load office list from discover script output, filtered to TARGET_STATE."""
    # Check for full national file first, then fall back to legacy NSW-only file
    load_from = OFFICES_FILE if os.path.exists(OFFICES_FILE) else "ljhooker_nsw_offices.json"
    if os.path.exists(load_from):
        with open(load_from) as f:
            all_offices = json.load(f)
        offices = [o for o in all_offices if o.get("state", "").upper() == TARGET_STATE]
        print(f"Loaded {len(offices)} {TARGET_STATE} offices from {load_from} ({len(all_offices)} total)")
        return offices

    seed = [
        {"officeId": 234, "name": "LJ Hooker Blacktown", "suburb": "Blacktown", "state": "NSW"},
    ]
    print(f"WARNING: {OFFICES_FILE} not found. Using seed list ({len(seed)} offices).")
    print("Run discover_ljhooker_offices.py first to find all office IDs.\n")
    return seed


def main():
    print("=" * 60)
    print("fetch_ljhooker.py — LJ Hooker NSW sold listings harvest")
    print("=" * 60)

    offices = load_offices()
    if not offices:
        print("No offices to process.")
        sys.exit(1)

    total_fetched  = 0
    total_upserted = 0

    print(f"\nProcessing {len(offices)} NSW offices...\n")
    for i, office in enumerate(offices, 1):
        print(f"[{i}/{len(offices)}] ", end="")
        fetched, upserted = harvest_office(office)
        total_fetched  += fetched
        total_upserted += upserted
        time.sleep(REQUEST_DELAY)

    print(f"\n{'=' * 60}")
    print(f"Complete: {total_fetched} records built, {total_upserted} upserted")
    print(f"Source: '{SOURCE_NAME}'")
    print(f"\nNext: run match_ljhooker_nsw.py to match against property_sales")


if __name__ == "__main__":
    main()
