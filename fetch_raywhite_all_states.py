"""
fetch_raywhite_all_states.py — Ray White extraction for QLD, WA, SA, ACT, TAS, NT
==================================================================================
Runs sequentially through all remaining states after NSW and VIC are done.
Each state has its own state file for resume support.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 fetch_raywhite_all_states.py

To run a single state only:
    python3 fetch_raywhite_all_states.py QLD
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

# State → (supabase_table, postcode_range)
STATES = {
    "QLD": ("sourced_sales_qld", range(4000, 5000)),
    "SA":  ("sourced_sales_sa",  range(5000, 6000)),
    "WA":  ("sourced_sales_wa",  range(6000, 7000)),
    "TAS": ("sourced_sales_tas", range(7000, 8000)),
    "NT":  ("sourced_sales_nt",  range(800,  900)),   # NT uses 0800-0899
    "ACT": ("sourced_sales_act", range(2600, 2620)),  # ACT postcodes
}

API_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def supabase_headers():
    return {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }

def load_state(state_code):
    path = f".raywhite_{state_code.lower()}_state.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f), path
    return {"completed_postcodes": [], "total_records": 0}, path

def save_state(state, path):
    # Atomic write — avoids corrupt state file if process is killed mid-write
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)

def fetch_page(state_code, postcode, from_offset, retries=3, backoff=2):
    """Fetch one page with retry on transient network errors."""
    payload = {
        "size": PAGE_SIZE,
        "from": from_offset,
        "stateCode": state_code,
        "postCode": [postcode],
        "statusCode": {"in": ["SLD"]},
        "typeCode": {"in": ["SAL", "RUR"]},
        "countryCode": ["AU", "NZ"],
        "categoryCode": {"in": []},
    }
    for attempt in range(retries):
        try:
            return requests.post(
                f"{API_URL}?apiKey={API_KEY}",
                headers=API_HEADERS,
                json=payload,
                timeout=20,
            )
        except Exception:
            if attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
            else:
                raise

def extract_record(item, source="raywhite"):
    v = item.get("value", {})
    addr = v.get("address", {})
    cats = v.get("categories", [])
    return {
        "source":             source,
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

def upsert_to_supabase(records, table, retries=3, backoff=2):
    """Upsert with exponential backoff retry. Returns True on success.
    On persistent failure, logs a warning but does NOT crash — data is safe in NDJSON."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=source,source_id"
    for attempt in range(retries):
        try:
            r = requests.post(url, headers=supabase_headers(), json=records, timeout=30)
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

def process_postcode(state_code, postcode, table, outfile):
    try:
        r = fetch_page(state_code, postcode, 0)
    except Exception as e:
        print(f"  ERROR fetching page 1: {e}")
        return 0

    if r.status_code == 429:
        print(f"  Rate limited — sleeping 60s then skipping postcode")
        time.sleep(60)
        return 0

    if r.status_code != 200:
        return 0

    try:
        data = r.json()
    except Exception:
        print(f"  Bad JSON response — skipping postcode")
        return 0

    total_hits = data.get("hits", 0)
    if total_hits == 0:
        return 0

    all_records = [extract_record(item) for item in data.get("data", [])]
    fetched = len(all_records)

    while fetched < total_hits:
        time.sleep(DELAY)
        try:
            r = fetch_page(state_code, postcode, fetched)
        except Exception as e:
            print(f"  ERROR at offset {fetched}: {e}")
            break

        if r.status_code == 429:
            print(f"  Rate limited at offset {fetched} — sleeping 60s then stopping postcode")
            time.sleep(60)
            break

        if r.status_code != 200:
            break

        try:
            page_data = r.json().get("data", [])
        except Exception:
            print(f"  Bad JSON at offset {fetched} — stopping postcode")
            break

        if not page_data:
            break

        prev_fetched = fetched
        all_records.extend([extract_record(item) for item in page_data])
        fetched += len(page_data)

        # Safety: if pagination isn't advancing, bail out
        if fetched == prev_fetched:
            print(f"  Pagination stalled at offset {fetched} — stopping postcode")
            break

    if not all_records:
        return 0

    # Deduplicate by source_id
    seen = {}
    for rec in all_records:
        seen[rec["source_id"]] = rec
    all_records = list(seen.values())

    for rec in all_records:
        outfile.write(json.dumps(rec) + "\n")
    outfile.flush()

    for i in range(0, len(all_records), 200):
        batch = all_records[i:i + 200]
        if not upsert_to_supabase(batch, table):
            print(f"  ⚠️  Supabase upsert failed at {i} — saved to NDJSON")

    return len(all_records)


def run_state(state_code):
    table, postcode_range = STATES[state_code]
    state, state_path = load_state(state_code)
    completed = set(state["completed_postcodes"])
    total_records = state["total_records"]
    output_file = f"raywhite_{state_code.lower()}_listings.ndjson"

    postcodes = [str(p).zfill(4) for p in postcode_range]
    remaining = [p for p in postcodes if p not in completed]

    print(f"\n{'='*60}")
    print(f"Ray White {state_code} — {len(remaining)} postcodes remaining")
    print(f"Table: {table} | Output: {output_file}")
    print(f"{'='*60}\n")

    with open(output_file, "a") as outfile:
        for i, postcode in enumerate(remaining):
            count = process_postcode(state_code, postcode, table, outfile)
            total_records += count

            if count > 0:
                print(f"  [{i+1}/{len(remaining)}] {postcode}: {count:,}  (total: {total_records:,})")
            else:
                print(f"  [{i+1}/{len(remaining)}] {postcode}: 0")

            completed.add(postcode)
            state["completed_postcodes"] = list(completed)
            state["total_records"] = total_records
            save_state(state, state_path)
            time.sleep(DELAY)

    print(f"\n{state_code} done! {total_records:,} total records → {table}")
    return total_records


def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        sys.exit(1)

    # Allow single state via CLI arg
    if len(sys.argv) > 1:
        state_code = sys.argv[1].upper()
        if state_code not in STATES:
            print(f"Unknown state: {state_code}. Options: {', '.join(STATES.keys())}")
            sys.exit(1)
        run_state(state_code)
        return

    # Otherwise run all states in order
    print(f"Ray White — All States Extraction")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"States: {', '.join(STATES.keys())}")

    for state_code in STATES:
        run_state(state_code)

    print(f"\nAll states done!")


if __name__ == "__main__":
    main()
