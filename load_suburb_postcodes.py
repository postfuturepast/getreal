#!/usr/bin/env python3
"""
load_suburb_postcodes.py — Load Australian suburb→postcode→metro/regional data into Supabase.

Usage:
    export SUPABASE_SECRET=<secret>
    python3 load_suburb_postcodes.py

Data source:
    Matthew Proctor's Australian Postcodes dataset (free, MIT licence):
    https://github.com/matthewproctor/australianpostcodes

    Joined against the existing postcode_locations Supabase table (loaded from ABS ASGS)
    to derive location_type (metro / regional).

What it loads:
    ~16,000 suburb/locality rows into suburb_postcodes table.
    Each row: suburb name, state, postcode, location_type.
    Suburb names are title-cased. Postcode left-padded to 4 chars.
"""

from __future__ import annotations

import os
import sys
import csv
import io
import requests
from supabase import create_client

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET")

# Free, well-maintained, MIT licence
SOURCE_CSV_URL = (
    "https://raw.githubusercontent.com/matthewproctor/"
    "australianpostcodes/master/australian_postcodes.csv"
)

# Only load delivery area postcodes with gazetted status
VALID_TYPES    = {"Delivery Area"}
VALID_STATUSES = {"Gazetted"}

# Normalise state codes (the dataset uses full names for some territories)
STATE_MAP = {
    "NSW": "NSW", "VIC": "VIC", "QLD": "QLD", "WA": "WA",
    "SA": "SA", "TAS": "TAS", "ACT": "ACT", "NT": "NT",
    # Handle any full-name variants
    "New South Wales": "NSW", "Victoria": "VIC", "Queensland": "QLD",
    "Western Australia": "WA", "South Australia": "SA", "Tasmania": "TAS",
    "Australian Capital Territory": "ACT", "Northern Territory": "NT",
}


def download_csv() -> str:
    print(f"Downloading suburb data from GitHub ...")
    resp = requests.get(SOURCE_CSV_URL, timeout=60)
    resp.raise_for_status()
    print(f"  Downloaded {len(resp.content):,} bytes")
    return resp.text


def load_postcode_locations(sb) -> dict[str, str]:
    """Fetch all postcodes from postcode_locations → {postcode: location_type}."""
    print("Fetching postcode → metro/regional mapping from Supabase ...")
    rows = []
    page_size = 1000
    offset = 0
    while True:
        result = (
            sb.table("postcode_locations")
            .select("postcode,location_type")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        rows.extend(result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    mapping = {r["postcode"]: r["location_type"] for r in rows}
    print(f"  Loaded {len(mapping):,} postcode mappings")
    return mapping


def parse_suburbs(csv_text: str, postcode_map: dict[str, str]) -> list[dict]:
    """Parse the CSV and return rows ready for upsert."""
    reader = csv.DictReader(io.StringIO(csv_text))

    seen      = set()   # deduplicate on (suburb, state, postcode)
    rows      = []
    skipped   = 0
    no_metro  = 0
    type_counts   = {}
    status_counts = {}

    for row in reader:
        ptype  = row.get("type", "").strip()
        status = row.get("status", "").strip()
        type_counts[ptype]     = type_counts.get(ptype, 0) + 1
        status_counts[status]  = status_counts.get(status, 0) + 1

        # Skip clearly non-residential entries
        ptype_lower = ptype.lower()
        if any(x in ptype_lower for x in ["po box", "p.o.", "locked bag", "cms", "gpo"]):
            skipped += 1
            continue

        suburb    = row.get("locality", "").strip().title()
        state_raw = row.get("state", "").strip().upper()
        state     = STATE_MAP.get(state_raw) or STATE_MAP.get(row.get("state", "").strip())
        postcode  = row.get("postcode", "").strip().zfill(4)

        if not suburb or not state or not postcode:
            skipped += 1
            continue

        # Skip numeric-only or clearly invalid suburbs
        if suburb.replace(" ", "").isdigit():
            skipped += 1
            continue

        key = (suburb.lower(), state, postcode)
        if key in seen:
            continue
        seen.add(key)

        location_type = postcode_map.get(postcode)
        if location_type is None:
            no_metro += 1

        rows.append({
            "suburb":        suburb,
            "state":         state,
            "postcode":      postcode,
            "location_type": location_type,
        })

    print(f"\nUnique 'type' values in CSV:")
    for k, v in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {v:>6,}  {repr(k)}")
    print(f"\nUnique 'status' values in CSV:")
    for k, v in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {v:>6,}  {repr(k)}")

    print(f"\nParsed {len(rows):,} suburb rows")
    print(f"  Skipped (PO box / invalid): {skipped:,}")
    print(f"  No metro/regional match:    {no_metro:,} (stored with null location_type)")
    return rows


def upsert_rows(sb, rows: list[dict]) -> None:
    BATCH = 500
    total = len(rows)
    upserted = 0
    for start in range(0, total, BATCH):
        batch = rows[start : start + BATCH]
        sb.table("suburb_postcodes").upsert(
            batch,
            on_conflict="suburb,state,postcode",
        ).execute()
        upserted += len(batch)
        print(f"  Upserted {upserted:,} / {total:,}", end="\r")
    print(f"\n  Done — {upserted:,} rows upserted")


def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET environment variable not set.")
        print("Run:  export SUPABASE_SECRET=<your-secret-key>")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_SECRET)

    csv_text     = download_csv()
    postcode_map = load_postcode_locations(sb)
    rows         = parse_suburbs(csv_text, postcode_map)
    upsert_rows(sb, rows)

    result = sb.table("suburb_postcodes").select("id", count="exact").execute()
    print(f"\n✓ suburb_postcodes now has {result.count:,} rows")

    # Spot-check a few suburbs
    print("\nSpot-check:")
    for suburb, state in [("Sydney", "NSW"), ("Melbourne", "VIC"), ("Dubbo", "NSW"), ("Richmond", "VIC")]:
        r = (
            sb.table("suburb_postcodes")
            .select("suburb,postcode,state,location_type")
            .eq("suburb", suburb)
            .eq("state", state)
            .limit(1)
            .execute()
        )
        if r.data:
            x = r.data[0]
            print(f"  {x['suburb']}, {x['state']} {x['postcode']} → {x['location_type']}")
        else:
            print(f"  {suburb}, {state} → NOT FOUND")


if __name__ == "__main__":
    main()
