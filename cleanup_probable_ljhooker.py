"""
cleanup_probable_ljhooker.py — Remove bad probable matches for LJ Hooker

Clears match_confidence='probable', enriched_source, enriched_source_id
from property_sales rows where enriched_source='ljhooker'.

Also clears match_confidence and matched_property_id from sourced_sales_nsw
where source='ljhooker' and match_confidence='probable'.

Safe to re-run.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 cleanup_probable_ljhooker.py
"""

import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")
if not SUPABASE_SECRET:
    print("ERROR: SUPABASE_SECRET not set.")
    sys.exit(1)


def headers():
    return {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }


def fetch_all(table, select, filters):
    records = []
    page_size = 1000
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}&{filters}&limit={page_size}&offset={offset}"
        r = requests.get(url, headers=headers(), timeout=30)
        if r.status_code != 200:
            print(f"ERROR {r.status_code}: {r.text[:200]}")
            break
        batch = r.json()
        if not batch:
            break
        records.extend(batch)
        offset += len(batch)
        if len(batch) < page_size:
            break
    return records


def patch_with_retry(url, payload, retries=3, backoff=0.5):
    for attempt in range(retries):
        try:
            r = requests.patch(url, headers=headers(), json=payload, timeout=15)
            if r.status_code in (200, 204):
                return True
        except Exception:
            pass
        time.sleep(backoff * (2 ** attempt))
    return False


def main():
    # ── 1. Clean property_sales ───────────────────────────────────────────────
    print("Loading property_sales rows with probable ljhooker matches...")
    ps_rows = fetch_all(
        "property_sales",
        "id",
        "enriched_source=eq.ljhooker&match_confidence=eq.probable",
    )
    print(f"  {len(ps_rows):,} rows to clean")

    def clean_ps(row):
        url = f"{SUPABASE_URL}/rest/v1/property_sales?id=eq.{row['id']}"
        return patch_with_retry(url, {
            "match_confidence":   None,
            "enriched_source":    None,
            "enriched_source_id": None,
        })

    ok = 0
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(clean_ps, row) for row in ps_rows]
        for f in as_completed(futures):
            if f.result():
                ok += 1
    print(f"  {ok:,} property_sales rows cleared")

    # ── 2. Clean sourced_sales_nsw ────────────────────────────────────────────
    print("\nLoading sourced_sales_nsw rows with probable ljhooker matches...")
    ss_rows = fetch_all(
        "sourced_sales_nsw",
        "source_id",
        "source=eq.ljhooker&match_confidence=eq.probable",
    )
    print(f"  {len(ss_rows):,} rows to clean")

    def clean_ss(row):
        url = f"{SUPABASE_URL}/rest/v1/sourced_sales_nsw?source_id=eq.{row['source_id']}&source=eq.ljhooker"
        return patch_with_retry(url, {
            "match_confidence":    None,
            "matched_property_id": None,
        })

    ok = 0
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = [pool.submit(clean_ss, row) for row in ss_rows]
        for f in as_completed(futures):
            if f.result():
                ok += 1
    print(f"  {ok:,} sourced_sales_nsw rows cleared")

    print("\nDone. Probable LJ Hooker matches removed.")


if __name__ == "__main__":
    main()
