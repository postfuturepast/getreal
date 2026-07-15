#!/usr/bin/env python3
"""
discover_ljhooker_offices.py — Discover LJ Hooker office IDs for NSW

The LJ Hooker sold search API requires a numeric officeId, but this ID is
not exposed in any public endpoint. This script brute-forces the range
1–3000, calling search-v1 with limit=1 for each ID, and records which IDs
return NSW properties.

Output: ljhooker_nsw_offices.json — list of {officeId, name, suburb, state}

Usage:
    python3 discover_ljhooker_offices.py

Runtime: ~10–15 minutes (3000 calls at 0.25s delay)
"""

import os
import re
import time
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Clear corporate proxy (safe: does not touch shell profile) ────────────────
for _k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
    os.environ.pop(_k, None)

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL    = "https://api01.ljx.com.au/website/search-v1"
ID_RANGE    = range(1, 3001)          # try 1–3000
MAX_WORKERS = 8                        # concurrent threads
DELAY_PER_WORKER = 0.25               # seconds between calls per worker
OUTPUT_FILE = "ljhooker_offices.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://blacktown.ljhooker.com.au/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def probe_office(office_id: int):
    """
    Call search-v1 for a single officeId with limit=1.
    Returns a dict with office info for any office that has sold listings, else None.
    """
    params = {
        "searchOrigin": "residential-au",
        "searchProfile": "sold",
        "officeId": office_id,
        "orderBy": "date-desc",
        "surroundingSuburbs": "false",
        "page": 1,
        "limit": 1,
    }
    for attempt in range(3):
        try:
            r = SESSION.get(BASE_URL, params=params, timeout=15)
            if r.status_code == 200:
                break
            if r.status_code == 400:
                return None  # invalid ID, don't retry
            time.sleep(2 ** attempt)
        except Exception:
            time.sleep(2 ** attempt)
    else:
        return None
    try:
        data = r.json()
        props = data.get("properties", [])
        if not props:
            return None

        # Get office name from offices array if present
        offices = data.get("offices", [])
        office_name = offices[0].get("name", f"Office {office_id}") if offices else f"Office {office_id}"
        first = props[0]["address"]
        state = first.get("state", "").upper()
        return {
            "officeId": office_id,
            "name": office_name,
            "suburb": first.get("suburb", ""),
            "state": state,
            "total_sold": data.get("totalProperties", 0),
        }
    except Exception:
        return None


def main():
    print(f"Probing office IDs 1–{max(ID_RANGE)} for NSW offices...")
    print(f"Workers: {MAX_WORKERS}, estimated time: ~{(max(ID_RANGE) * DELAY_PER_WORKER / MAX_WORKERS / 60):.0f} min\n")

    found = []
    done = 0
    total = len(ID_RANGE)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(probe_office, oid): oid for oid in ID_RANGE}
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                found.append(result)
                print(f"  ✓ ID {result['officeId']:4d} → {result['name']} ({result['suburb']}, {result['state']}, {result['total_sold']} sold)")
            if done % 100 == 0:
                print(f"  [{done}/{total}] checked, {len(found)} NSW offices found so far...")
            time.sleep(DELAY_PER_WORKER / MAX_WORKERS)

    found.sort(key=lambda x: x["officeId"])

    with open(OUTPUT_FILE, "w") as f:
        json.dump(found, f, indent=2)

    by_state = {}
    for o in found:
        by_state.setdefault(o["state"], []).append(o)

    print(f"\nDone. Found {len(found)} offices across {len(by_state)} states.")
    print(f"Saved to {OUTPUT_FILE}\n")
    for state in sorted(by_state):
        print(f"  {state}: {len(by_state[state])} offices")
    print()
    for o in found:
        print(f"  {o['officeId']:4d}  {o['state']:<4s}  {o['name']:<50s}  {o['suburb']}")


if __name__ == "__main__":
    main()
