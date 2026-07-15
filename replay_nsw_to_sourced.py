"""
replay_nsw_to_sourced.py — Load raywhite NSW NDJSON into sourced_sales_nsw
===========================================================================
Reads raywhite_listings.ndjson, adds source='raywhite', deduplicates,
and upserts into the new sourced_sales_nsw table.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 replay_nsw_to_sourced.py
"""

import json
import os
import sys
import requests
import time

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")
SUPABASE_TABLE  = "sourced_sales_nsw"
INPUT_FILE      = "raywhite_listings.ndjson"
BATCH_SIZE      = 200

SUPABASE_HEADERS = {
    "apikey":        SUPABASE_SECRET,
    "Authorization": f"Bearer {SUPABASE_SECRET}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=minimal",
}

def upsert_batch(batch):
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}?on_conflict=source,source_id"
    r = requests.post(url, headers=SUPABASE_HEADERS, json=batch, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ERROR {r.status_code}: {r.text[:200]}")
        return False
    return True

def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        sys.exit(1)

    print(f"Loading {INPUT_FILE} → Supabase {SUPABASE_TABLE}")

    # Deduplicate by source_id
    seen = {}
    with open(INPUT_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            rec["source"] = "raywhite"  # add source column
            seen[rec["source_id"]] = rec

    records = list(seen.values())
    total = len(records)
    print(f"{total:,} unique records after dedup\n")

    ok = 0
    failed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        success = upsert_batch(batch)
        if success:
            ok += len(batch)
        else:
            failed += len(batch)

        if (i // BATCH_SIZE) % 20 == 0:
            pct = 100 * i // total
            print(f"  {pct}% — {ok:,} loaded, {failed:,} failed")

        time.sleep(0.1)

    print(f"\nDone! {ok:,} loaded, {failed:,} failed")

if __name__ == "__main__":
    main()
