"""
fetch_raywhite.py — Full Ray White NSW extraction
==================================================
Loops all NSW postcodes (2000-2999), paginates all sold listings,
upserts to Supabase raywhite_listings table, and saves a local
NDJSON backup file.

Resume-friendly: tracks completed postcodes in .raywhite_state.json
so a restart picks up where it left off.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 fetch_raywhite.py

Output:
    - Supabase: raywhite_listings table
    - Local: raywhite_listings.ndjson (one record per line)
"""

import requests
import json
import time
import os
import sys
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

API_URL  = "https://raywhiteapi.ep.dynamics.net/v1/listings"
API_KEY  = "6625c417-067a-4a8e-8c1d-85c812d0fb25"
PAGE_SIZE = 50
DELAY     = 0.5  # seconds between requests

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

STATE_FILE  = ".raywhite_state.json"
OUTPUT_FILE = "raywhite_listings.ndjson"

API_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

SUPABASE_HEADERS = {
    "apikey":        SUPABASE_SECRET,
    "Authorization": f"Bearer {SUPABASE_SECRET}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=minimal",
}

# ── State (resume support) ────────────────────────────────────────────────────

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"completed_postcodes": [], "total_records": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

# ── Ray White API ─────────────────────────────────────────────────────────────

def fetch_page(postcode, from_offset):
    payload = {
        "size": PAGE_SIZE,
        "from": from_offset,
        "stateCode": "NSW",
        "postCode": [postcode],
        "statusCode": {"in": ["SLD"]},
        "typeCode": {"in": ["SAL", "RUR"]},
        "countryCode": ["AU", "NZ"],
        "categoryCode": {"in": []},
    }
    r = requests.post(
        f"{API_URL}?apiKey={API_KEY}",
        headers=API_HEADERS,
        json=payload,
        timeout=20,
    )
    return r

def extract_record(item):
    v = item.get("value", {})
    addr = v.get("address", {})
    cats = v.get("categories", [])
    return {
        "source_id":          v.get("sourceId") or str(v.get("id")),
        "street_number":      addr.get("streetNumber"),
        "street_name":        addr.get("streetName"),
        "street_type":        addr.get("streetType"),
        "suburb":             addr.get("suburb"),
        "state_code":         addr.get("stateCode"),
        "postcode":           addr.get("postCode"),
        "bedrooms":           v.get("bedrooms"),
        "bathrooms":          v.get("bathrooms"),
        "car_spaces":         v.get("carSpaces"),
        "property_type_code": cats[0]["code"] if cats else None,
        "sold_date":          v.get("soldDate"),
        "sold_price":         v.get("soldPrice"),
    }

# ── Supabase ──────────────────────────────────────────────────────────────────

def upsert_to_supabase(records):
    url = f"{SUPABASE_URL}/rest/v1/raywhite_listings?on_conflict=source_id"
    r = requests.post(url, headers=SUPABASE_HEADERS, json=records, timeout=30)
    if r.status_code not in (200, 201):
        print(f"    Supabase error {r.status_code}: {r.text[:200]}")
    return r.status_code in (200, 201)

# ── Main ──────────────────────────────────────────────────────────────────────

def process_postcode(postcode, outfile, state):
    # First page — get total hits
    try:
        r = fetch_page(postcode, 0)
    except Exception as e:
        print(f"  ERROR fetching page 1: {e}")
        return 0

    if r.status_code != 200:
        print(f"  HTTP {r.status_code} — skipping")
        return 0

    data = r.json()
    total_hits = data.get("hits", 0)
    if total_hits == 0:
        return 0

    all_records = []
    page_records = [extract_record(item) for item in data.get("data", [])]
    all_records.extend(page_records)

    # Remaining pages
    fetched = len(page_records)
    while fetched < total_hits:
        time.sleep(DELAY)
        try:
            r = fetch_page(postcode, fetched)
        except Exception as e:
            print(f"  ERROR at offset {fetched}: {e}")
            break

        if r.status_code != 200:
            print(f"  HTTP {r.status_code} at offset {fetched} — stopping postcode")
            break

        page_data = r.json().get("data", [])
        if not page_data:
            break

        page_records = [extract_record(item) for item in page_data]
        all_records.extend(page_records)
        fetched += len(page_data)

    if not all_records:
        return 0

    # Write to NDJSON
    for rec in all_records:
        outfile.write(json.dumps(rec) + "\n")
    outfile.flush()

    # Upsert to Supabase in batches of 200
    batch_size = 200
    for i in range(0, len(all_records), batch_size):
        batch = all_records[i:i + batch_size]
        ok = upsert_to_supabase(batch)
        if not ok:
            print(f"  ⚠️  Supabase upsert failed for batch at {i} — data saved to NDJSON")

    return len(all_records)


def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        print("Run: export SUPABASE_SECRET=your_secret_key_here")
        sys.exit(1)

    state = load_state()
    completed = set(state["completed_postcodes"])
    total_records = state["total_records"]

    postcodes = [str(p) for p in range(2000, 3000)]
    remaining = [p for p in postcodes if p not in completed]

    print(f"Ray White NSW Full Extraction")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Postcodes: {len(remaining)} remaining of {len(postcodes)} total")
    print(f"Records so far: {total_records:,}")
    print(f"Output: {OUTPUT_FILE} + Supabase raywhite_listings\n")

    with open(OUTPUT_FILE, "a") as outfile:
        for i, postcode in enumerate(remaining):
            count = process_postcode(postcode, outfile, state)

            if count > 0:
                total_records += count
                print(f"  [{i+1}/{len(remaining)}] {postcode}: {count:,} records  (total: {total_records:,})")
            else:
                # Print a dot for empty postcodes to show progress without spam
                print(f"  [{i+1}/{len(remaining)}] {postcode}: 0")

            completed.add(postcode)
            state["completed_postcodes"] = list(completed)
            state["total_records"] = total_records
            save_state(state)

            time.sleep(DELAY)

    print(f"\nDone! {total_records:,} total records")
    print(f"Local backup: {OUTPUT_FILE}")
    print(f"Supabase table: raywhite_listings")


if __name__ == "__main__":
    main()
