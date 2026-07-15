"""
replay_to_supabase.py — Load raywhite_listings.ndjson into Supabase
====================================================================
Reads the local NDJSON backup and upserts all records to Supabase
in batches of 200. Safe to re-run — uses on_conflict=source_id.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 replay_to_supabase.py
"""

import json
import os
import sys
import requests
import time

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")
INPUT_FILE      = "raywhite_listings.ndjson"
BATCH_SIZE      = 200

SUPABASE_HEADERS = {
    "apikey":        SUPABASE_SECRET,
    "Authorization": f"Bearer {SUPABASE_SECRET}",
    "Content-Type":  "application/json",
    "Prefer":        "resolution=merge-duplicates,return=minimal",
}

def upsert_batch(batch):
    url = f"{SUPABASE_URL}/rest/v1/raywhite_listings?on_conflict=source_id"
    r = requests.post(url, headers=SUPABASE_HEADERS, json=batch, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ERROR {r.status_code}: {r.text[:200]}")
        return False
    return True

def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        print("Run: export SUPABASE_SECRET=your_secret_key_here")
        sys.exit(1)

    print(f"Loading {INPUT_FILE} → Supabase raywhite_listings")

    # Deduplicate by source_id (file was appended across multiple runs)
    seen = {}
    with open(INPUT_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            seen[rec["source_id"]] = rec

    lines = list(seen.values())
    total = len(lines)
    print(f"Raw lines → {total:,} unique records after dedup\n")

    ok = 0
    failed = 0

    for i in range(0, total, BATCH_SIZE):
        batch = lines[i:i + BATCH_SIZE]
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
