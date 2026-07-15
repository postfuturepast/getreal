"""
fetch_raywhite_vic.py — Ray White VIC extraction
=================================================
Same as fetch_raywhite.py but for Victoria (postcodes 3000-3999).
Writes to Supabase sourced_sales_vic table.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 fetch_raywhite_vic.py

Output:
    - Supabase: sourced_sales_vic table
    - Local: raywhite_vic_listings.ndjson (one record per line)
"""

import requests
import json
import time
import os
import sys
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

API_URL   = "https://raywhiteapi.ep.dynamics.net/v1/listings"
API_KEY   = "6625c417-067a-4a8e-8c1d-85c812d0fb25"
PAGE_SIZE = 50
DELAY     = 0.5

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")
SUPABASE_TABLE  = "sourced_sales_vic"

STATE_CODE  = "VIC"
POSTCODES   = [str(p) for p in range(3000, 4000)]

STATE_FILE  = ".raywhite_vic_state.json"
OUTPUT_FILE = "raywhite_vic_listings.ndjson"

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
    # Atomic write — avoids corrupt state file if process is killed mid-write
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)

# ── Ray White API ─────────────────────────────────────────────────────────────

def fetch_page(postcode, from_offset, retries=3, backoff=2):
    """Fetch one page with retry on transient network errors."""
    payload = {
        "size": PAGE_SIZE,
        "from": from_offset,
        "stateCode": STATE_CODE,
        "postCode": [postcode],
        "statusCode": {"in": ["SLD"]},
        "typeCode": {"in": ["SAL", "RUR"]},
        "countryCode": ["AU", "NZ"],
        "categoryCode": {"in": []},
    }
    for attempt in range(retries):
        try:
            r = requests.post(
                f"{API_URL}?apiKey={API_KEY}",
                headers=API_HEADERS,
                json=payload,
                timeout=20,
            )
            return r
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
            else:
                raise

def extract_record(item):
    v = item.get("value", {})
    addr = v.get("address", {})
    cats = v.get("categories", [])
    return {
        "source":             "raywhite",
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

def upsert_to_supabase(records, retries=3, backoff=2):
    """Upsert with exponential backoff retry. Returns True on success.
    On network/DNS failure, logs a warning but does NOT crash — data is safe in NDJSON."""
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?on_conflict=source,source_id"
    for attempt in range(retries):
        try:
            r = requests.post(url, headers=SUPABASE_HEADERS, json=records, timeout=30)
            if r.status_code in (200, 201):
                return True
            print(f"    Supabase error {r.status_code}: {r.text[:200]}")
        except requests.exceptions.ConnectionError as e:
            print(f"    Supabase unreachable (attempt {attempt+1}/{retries}): {e}")
        except Exception as e:
            print(f"    Supabase error (attempt {attempt+1}/{retries}): {e}")
        if attempt < retries - 1:
            time.sleep(backoff * (2 ** attempt))
    print(f"    ⚠️  Supabase upsert failed after {retries} attempts — data saved to NDJSON, replay later")
    return False

# ── Main ──────────────────────────────────────────────────────────────────────

def process_postcode(postcode, outfile, state):
    try:
        r = fetch_page(postcode, 0)
    except Exception as e:
        print(f"  ERROR fetching page 1: {e}")
        return 0

    if r.status_code == 429:
        print(f"  Rate limited — sleeping 60s then skipping postcode")
        time.sleep(60)
        return 0

    if r.status_code != 200:
        print(f"  HTTP {r.status_code} — skipping")
        return 0

    try:
        data = r.json()
    except Exception:
        print(f"  Bad JSON response — skipping postcode")
        return 0

    total_hits = data.get("hits", 0)
    if total_hits == 0:
        return 0

    all_records = []
    page_records = [extract_record(item) for item in data.get("data", [])]
    all_records.extend(page_records)

    fetched = len(page_records)
    while fetched < total_hits:
        time.sleep(DELAY)
        try:
            r = fetch_page(postcode, fetched)
        except Exception as e:
            print(f"  ERROR at offset {fetched}: {e}")
            break

        if r.status_code == 429:
            print(f"  Rate limited at offset {fetched} — sleeping 60s then stopping postcode")
            time.sleep(60)
            break

        if r.status_code != 200:
            print(f"  HTTP {r.status_code} at offset {fetched} — stopping postcode")
            break

        try:
            page_data = r.json().get("data", [])
        except Exception:
            print(f"  Bad JSON at offset {fetched} — stopping postcode")
            break

        if not page_data:
            break

        page_records = [extract_record(item) for item in page_data]
        all_records.extend(page_records)
        prev_fetched = fetched
        fetched += len(page_data)

        # Safety: if pagination isn't advancing, bail out
        if fetched == prev_fetched:
            print(f"  Pagination stalled at offset {fetched} — stopping postcode")
            break

    if not all_records:
        return 0

    # Deduplicate by source_id within this postcode's results
    seen = {}
    for rec in all_records:
        seen[rec["source_id"]] = rec
    all_records = list(seen.values())

    for rec in all_records:
        outfile.write(json.dumps(rec) + "\n")
    outfile.flush()

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

    remaining = [p for p in POSTCODES if p not in completed]

    print(f"Ray White VIC Full Extraction")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Postcodes: {len(remaining)} remaining of {len(POSTCODES)} total")
    print(f"Records so far: {total_records:,}")
    print(f"Output: {OUTPUT_FILE} + Supabase {SUPABASE_TABLE}\n")

    with open(OUTPUT_FILE, "a") as outfile:
        for i, postcode in enumerate(remaining):
            count = process_postcode(postcode, outfile, state)

            if count > 0:
                total_records += count
                print(f"  [{i+1}/{len(remaining)}] {postcode}: {count:,} records  (total: {total_records:,})")
            else:
                print(f"  [{i+1}/{len(remaining)}] {postcode}: 0")

            completed.add(postcode)
            state["completed_postcodes"] = list(completed)
            state["total_records"] = total_records
            save_state(state)

            time.sleep(DELAY)

    print(f"\nDone! {total_records:,} total records")
    print(f"Local backup: {OUTPUT_FILE}")
    print(f"Supabase table: {SUPABASE_TABLE}")


if __name__ == "__main__":
    main()
