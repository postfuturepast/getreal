#!/usr/bin/env python3
"""
fetch_barryplant.py — Barry Plant sold listings via public JSON API
====================================================================
Uses the undocumented barryplant.com.au properties API (same one the
Next.js SSR page hits — no auth, no browser required).

Bonus: soldDetails_price is present in the JSON even when
soldDetails_price_display=false (website shows "undisclosed").

Usage:
    export SUPABASE_SECRET=your_secret_key
    python3 fetch_barryplant.py
    python3 fetch_barryplant.py --state VIC
    python3 fetch_barryplant.py --resume
    python3 fetch_barryplant.py --since 40   # only listings sold in last 40 days
"""

import argparse
import json
import os
import re
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# ── Config ────────────────────────────────────────────────────────────────────
SUPABASE_URL  = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_KEY  = os.environ.get("SUPABASE_SECRET", "")
SOURCE        = "barryplant"
UPSERT_BATCH  = 200
STATE_FILE    = ".barryplant_state.json"
NDJSON_FILE   = "barryplant_listings.ndjson"
PER_PAGE      = 100
DELAY         = 0.3   # seconds between requests

BASE_API   = (
    "https://www.barryplant.com.au/api/properties/"
    f"?light=1&listing_type=sale&order_by=-soldDetails_date"
    f"&per_page={PER_PAGE}&status=sold"
)
DETAIL_URL = "https://www.barryplant.com.au/api/properties/{id}/"

CATEGORY_MAP = {
    "apartment":  "apartment",
    "unit":       "apartment",
    "flat":       "apartment",
    "studio":     "apartment",
    "house":      "house",
    "townhouse":  "townhouse",
    "villa":      "townhouse",
    "duplex":     "townhouse",
    # Non-residential → None (skip)
    "land":              None,
    "land/development":  None,
    "acreage":           None,
    "acreagesemi-rural": None,
    "rural":             None,
    "viticulture":       None,
    "retail":            None,
    "commercial":        None,
    "medical/consulting": None,
    "industrial":        None,
}
DETAIL_WORKERS = 10

STATE_TABLES = {
    "NSW": "sourced_sales_nsw",
    "VIC": "sourced_sales_vic",
    "QLD": "sourced_sales_qld",
    "SA":  "sourced_sales_sa",
    "WA":  "sourced_sales_wa",
    "TAS": "sourced_sales_tas",
    "NT":  "sourced_sales_nt",
    "ACT": "sourced_sales_act",
}

STREET_TYPES = {
    "STREET","AVENUE","ROAD","DRIVE","COURT","CLOSE","PLACE","TERRACE",
    "CRESCENT","BOULEVARD","HIGHWAY","PARADE","GROVE","LANE","CIRCUIT",
    "ESPLANADE","BROADWAY","PARKWAY","RIDGE","MEWS","ROW","SQUARE","QUAY",
    "CHASE","VALE","VIEW","BEND","COVE","DALE","EDGE","END","GATE","HILL",
    "LINE","PASS","PATH","RING","RUN","TURN","WALK","WAY","LOOP","LINK",
    "RISE","TRACK","PARK","NOOK","GLEN","GREEN","GRANGE","FREEWAY",
    "BYPASS","POINT","MOUNT","CROSS","GARDENS","HEIGHTS","APPROACH",
}

# ── Supabase helpers ──────────────────────────────────────────────────────────
def sb_headers():
    return {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }

def upsert_to_supabase(records):
    if not records:
        return 0
    by_table = {}
    for rec in records:
        tbl = STATE_TABLES.get(rec["state_code"])
        if tbl:
            by_table.setdefault(tbl, []).append(rec)
    total = 0
    for tbl, recs in by_table.items():
        url = f"{SUPABASE_URL}/rest/v1/{tbl}?on_conflict=source,source_id"
        for i in range(0, len(recs), UPSERT_BATCH):
            batch = recs[i:i + UPSERT_BATCH]
            try:
                r = requests.post(url, headers=sb_headers(), json=batch, timeout=30)
                if r.status_code in (200, 201, 204):
                    total += len(batch)
                else:
                    print(f"  ⚠ Supabase {r.status_code}: {r.text[:120]}")
            except Exception as e:
                print(f"  ⚠ Supabase error: {e}")
    return total

# ── Detail API: get property category ────────────────────────────────────────
def fetch_category(django_id):
    """GET /api/properties/{id}/ → property_type_code string or None."""
    try:
        r = requests.get(
            DETAIL_URL.format(id=django_id),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if r.status_code == 200:
            raw = (r.json().get("category") or "").lower().strip()
            if raw in CATEGORY_MAP:
                return CATEGORY_MAP[raw]   # may be None for non-residential
            return "house"                 # unknown residential type → default
    except Exception:
        pass
    return None


# ── Address parsing ───────────────────────────────────────────────────────────
def parse_street(street_str):
    """Parse '39 Zeta Crescent' or '2/3 Heather Grove' into components."""
    s = street_str.strip()
    unit_number = None

    # Unit prefix: "2/3 Heather Grove"
    unit_match = re.match(r'^(\d+)[/\\](.+)$', s)
    if unit_match:
        unit_number = unit_match.group(1)
        s = unit_match.group(2).strip()

    # Street number
    num_match = re.match(r'^([\d][\d\-]*[A-Za-z]?)\s+(.+)$', s)
    if num_match:
        street_number = num_match.group(1)
        rest = num_match.group(2).strip()
    else:
        street_number = None
        rest = s

    words = rest.upper().split()
    if len(words) >= 2 and words[-1] in STREET_TYPES:
        street_name = " ".join(words[:-1])
        street_type = words[-1]
    else:
        street_name = " ".join(words)
        street_type = None

    combined = f"{unit_number}/{street_number}" if unit_number and street_number else street_number
    return combined, street_name, street_type

# ── Record parsing ────────────────────────────────────────────────────────────
def parse_listing(item, state_filter=None, property_type_code=None):
    state_code = (item.get("address_state") or "").upper()
    if not state_code or state_code not in STATE_TABLES:
        return None
    if state_filter and state_code != state_filter:
        return None

    source_id = item.get("uniqueID") or str(item.get("id", ""))
    if not source_id:
        return None

    street_raw = item.get("address_street_display") or ""
    street_number, street_name, street_type = parse_street(street_raw)

    # Sold date (ISO → YYYY-MM-DD)
    sold_date = None
    sd = item.get("soldDetails_date")
    if sd:
        try:
            sold_date = sd[:10]
        except Exception:
            pass

    # Sold price — present in API even when not publicly displayed on site
    sold_price = item.get("soldDetails_price")
    if sold_price is not None:
        try:
            sold_price = int(sold_price)
            if sold_price < 50_000 or sold_price > 50_000_000:
                sold_price = None
        except (ValueError, TypeError):
            sold_price = None

    bedrooms   = item.get("bedrooms")   or None
    bathrooms  = item.get("bathrooms")  or None
    car_spaces = item.get("total_parking") or item.get("parking") or None

    # Zero-value bedrooms/bathrooms are unreliable — treat as None
    if bedrooms  == 0: bedrooms  = None
    if bathrooms == 0: bathrooms = None
    if car_spaces == 0: car_spaces = None

    return {
        "source":        SOURCE,
        "source_id":     source_id,
        "street_number": street_number,
        "street_name":   street_name,
        "street_type":   street_type,
        "suburb":        (item.get("address_suburb") or "").upper(),
        "state_code":    state_code,
        "postcode":      item.get("address_postcode") or "",
        "bedrooms":      bedrooms,
        "bathrooms":     bathrooms,
        "car_spaces":    car_spaces,
        "property_type_code": property_type_code,
        "sold_price":    sold_price,
        "sold_date":     sold_date,
    }

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Barry Plant sold listings scraper")
    parser.add_argument("--state",  default=None, help="Filter by state (e.g. VIC)")
    parser.add_argument("--resume", action="store_true", help="Resume from saved state")
    parser.add_argument("--since",  type=int, default=0,
                        help="Only fetch listings sold in the last N days (0 = all)")
    args = parser.parse_args()

    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SECRET not set.")
        sys.exit(1)

    state_filter = args.state.upper() if args.state else None

    cutoff = None
    if args.since > 0:
        cutoff = (datetime.now() - timedelta(days=args.since)).strftime('%Y-%m-%d')
        print(f"Since filter: last {args.since} days (cutoff: {cutoff})")

    # Resume state
    seen_ids   = set()
    start_page = 1
    if args.resume and os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            saved = json.load(f)
        seen_ids   = set(saved.get("seen_ids", []))
        start_page = saved.get("next_page", 1)
        print(f"Resuming from page {start_page}, {len(seen_ids):,} seen IDs")

    print("Barry Plant — Sold Listings Scraper (API mode, no browser)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"State filter: {state_filter or 'all'} | Per page: {PER_PAGE}")
    print(f"NDJSON: {NDJSON_FILE}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.barryplant.com.au/for-sale/our-sold-properties/",
    })

    # Build start URL
    url = BASE_API
    if start_page > 1:
        url += f"&page={start_page}"

    total_new = 0
    total_ups = 0
    page_num  = start_page

    while url:
        try:
            r = session.get(url, timeout=30)
            if r.status_code != 200:
                print(f"  HTTP {r.status_code} on page {page_num} — stopping")
                break
            data = r.json()
        except Exception as e:
            print(f"  Error on page {page_num}: {e} — retrying in 5s")
            time.sleep(5)
            try:
                r = session.get(url, timeout=30)
                data = r.json()
            except Exception as e2:
                print(f"  Retry failed: {e2} — stopping")
                break

        results = data.get("results", [])
        if not results:
            print("  No results — done.")
            break

        # If --since is set, stop when entire page is older than cutoff
        # (API is sorted newest-first so once we're past the cutoff we're done)
        if cutoff:
            page_dates = [
                item.get("soldDetails_date", "")[:10]
                for item in results if item.get("soldDetails_date")
            ]
            if page_dates and all(d < cutoff for d in page_dates):
                print(f"  Page {page_num}: all listings before {cutoff} — stopping")
                break

        # Filter to new items only, and respect --since cutoff
        new_items = [
            item for item in results
            if (item.get("uniqueID") or str(item.get("id", ""))) not in seen_ids
            and (not cutoff or (item.get("soldDetails_date", "")[:10] or "9999") >= cutoff)
        ]

        # Fetch categories from detail API concurrently (one call per new item)
        category_map = {}
        if new_items:
            with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as ex:
                futs = {ex.submit(fetch_category, item.get("id")): item for item in new_items}
                for f in as_completed(futs):
                    item = futs[f]
                    uid  = item.get("uniqueID") or str(item.get("id", ""))
                    category_map[uid] = f.result()

        # Parse records with real category
        records = []
        for item in new_items:
            source_id = item.get("uniqueID") or str(item.get("id", ""))
            ptype = category_map.get(source_id)
            rec = parse_listing(item, state_filter, property_type_code=ptype)
            if rec:
                records.append(rec)
                seen_ids.add(source_id)

        # Write + upsert
        if records:
            with open(NDJSON_FILE, "a") as f:
                for rec in records:
                    f.write(json.dumps(rec) + "\n")
            ups = upsert_to_supabase(records)
            total_new += len(records)
            total_ups += ups

        count = data.get("count", "?")
        print(f"  Page {page_num:4d} — {len(records):3d} new (total: {total_new:,} / {count})")

        # Save resume state
        next_url = data.get("next")
        with open(STATE_FILE, "w") as f:
            json.dump({"seen_ids": list(seen_ids), "next_page": page_num + 1}, f)

        url = next_url
        page_num += 1
        time.sleep(DELAY)

    print(f"\nDone: {total_new:,} new records | {total_ups:,} upserted")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
