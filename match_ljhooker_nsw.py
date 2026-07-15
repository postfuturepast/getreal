"""
match_ljhooker_nsw.py — Enrich property_sales with bedroom data from LJ Hooker
===============================================================================
Matches LJ Hooker sourced_sales records (source='ljhooker') to NSW VG
property_sales records by address, then writes bedrooms/bathrooms/car_spaces
back to matched property_sales rows.

Exact matches only — write bedrooms/bathrooms/car_spaces to property_sales,
mark match_confidence='exact' on both tables, cross-link the records.

Probable matching (same street/number, different suburb) has been removed —
it produced too many false positives across NSW where the same street name
and number exists in multiple suburbs.

Key difference vs McGrath: LJ Hooker stores street_name and street_type as
separate columns (like Ray White), so no splitting is needed on sourced records.
LJ Hooker does not provide sold_date, so no date-window filter is applied.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 match_ljhooker_nsw.py
"""

import requests
import json
import os
import sys
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

# VG date window — wide to capture all LJ Hooker historical coverage
VG_DATE_MIN = "2022-01-01"
VG_DATE_MAX = "2026-12-31"

STREET_TYPES = {
    "ST": "STREET", "AVE": "AVENUE", "AV": "AVENUE", "RD": "ROAD",
    "DR": "DRIVE", "DV": "DRIVE", "CT": "COURT", "CRT": "COURT",
    "CL": "CLOSE", "PL": "PLACE", "TCE": "TERRACE", "TER": "TERRACE",
    "CRES": "CRESCENT", "CR": "CRESCENT", "BLVD": "BOULEVARD",
    "HWY": "HIGHWAY", "PDE": "PARADE", "GR": "GROVE", "LN": "LANE",
    "WAY": "WAY", "ESP": "ESPLANADE", "CCT": "CIRCUIT", "CIR": "CIRCUIT",
    "BDWY": "BROADWAY", "BVD": "BOULEVARD", "GLN": "GLEN",
    "RISE": "RISE", "LOOP": "LOOP", "LINK": "LINK", "WALK": "WALK",
    "TRCE": "TRACE", "TRAK": "TRACK", "TRK": "TRACK", "PARK": "PARK",
    "PKWY": "PARKWAY", "PWY": "PARKWAY", "RDG": "RIDGE", "MEWS": "MEWS",
    "ROW": "ROW", "SQ": "SQUARE", "QUAY": "QUAY", "CHASE": "CHASE",
    "VALE": "VALE", "VIEW": "VIEW", "BEND": "BEND", "COVE": "COVE",
    "DALE": "DALE", "EDGE": "EDGE", "END": "END", "GATE": "GATE",
    "HILL": "HILL", "LINE": "LINE", "PASS": "PASS", "PATH": "PATH",
    "RAMP": "RAMP", "REST": "REST", "RING": "RING", "RUN": "RUN",
    "SPUR": "SPUR", "TURN": "TURN", "YARD": "YARD", "GRA": "GRANGE",
    "GRN": "GREEN", "NOOK": "NOOK", "GLEN": "GLEN",
    # Full forms
    "STREET": "STREET", "AVENUE": "AVENUE", "ROAD": "ROAD",
    "DRIVE": "DRIVE", "COURT": "COURT", "CLOSE": "CLOSE",
    "PLACE": "PLACE", "TERRACE": "TERRACE", "CRESCENT": "CRESCENT",
    "BOULEVARD": "BOULEVARD", "HIGHWAY": "HIGHWAY", "PARADE": "PARADE",
    "GROVE": "GROVE", "LANE": "LANE", "CIRCUIT": "CIRCUIT",
    "ESPLANADE": "ESPLANADE", "BROADWAY": "BROADWAY", "PARKWAY": "PARKWAY",
    "RIDGE": "RIDGE", "SQUARE": "SQUARE", "CHASE": "CHASE", "TRACK": "TRACK",
    "GRANGE": "GRANGE", "GREEN": "GREEN",
}


def supabase_headers():
    return {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
        "Prefer":        "return=minimal",
    }


def fetch_all(table, select, filters=""):
    records = []
    page_size = 1000
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
        if filters:
            url += f"&{filters}"
        url += f"&limit={page_size}&offset={offset}"
        r = requests.get(url, headers=supabase_headers(), timeout=30)
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
        if offset % 10000 == 0:
            print(f"  fetched {offset:,} rows...")
    return records


def patch_with_retry(url, payload, retries=3, backoff=0.5):
    for attempt in range(retries):
        try:
            r = requests.patch(url, headers=supabase_headers(), json=payload, timeout=15)
            if r.status_code in (200, 204):
                return True
        except Exception:
            pass
        time.sleep(backoff * (2 ** attempt))
    return False


def patch_one_property(update):
    pid = update.pop("id")
    url = f"{SUPABASE_URL}/rest/v1/property_sales?id=eq.{pid}"
    return patch_with_retry(url, update)


def patch_one_sourced(update):
    sid = update.pop("source_id")
    url = f"{SUPABASE_URL}/rest/v1/sourced_sales_nsw?source_id=eq.{sid}&source=eq.ljhooker"
    return patch_with_retry(url, update)


def batch_update_property_sales(updates):
    if not updates:
        return 0
    ok = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(patch_one_property, dict(u)) for u in updates]
        for f in as_completed(futures):
            if f.result():
                ok += 1
    return ok


def batch_update_sourced_sales(updates):
    if not updates:
        return 0
    ok = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(patch_one_sourced, dict(u)) for u in updates]
        for f in as_completed(futures):
            if f.result():
                ok += 1
    return ok


def normalise_street_type(t):
    if not t:
        return ""
    return STREET_TYPES.get(t.upper().strip(), t.upper().strip())


def normalise_street_name(name):
    if not name:
        return ""
    name = re.sub(r"[^A-Z0-9 ]", "", name.upper())
    return " ".join(name.split())


def split_street_name_type(full_name):
    """Split VG 'HERSEY STREET' → ('HERSEY', 'STREET'). Used for VG records only."""
    if not full_name:
        return "", ""
    parts = full_name.strip().upper().split()
    if len(parts) >= 2 and parts[-1] in STREET_TYPES:
        return " ".join(parts[:-1]), STREET_TYPES[parts[-1]]
    return full_name.upper(), ""


def make_key(street_number, street_name, street_type, suburb):
    num   = (street_number or "").strip().upper()
    name  = normalise_street_name(street_name)
    stype = normalise_street_type(street_type)
    sub   = (suburb or "").strip().upper()
    return f"{num}|{name}|{stype}|{sub}"


def make_key_no_type(street_number, street_name, suburb):
    num  = (street_number or "").strip().upper()
    name = normalise_street_name(street_name)
    sub  = (suburb or "").strip().upper()
    return f"{num}|{name}|{sub}"


def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        sys.exit(1)

    # ── Load VG records ───────────────────────────────────────────────────────
    print("Loading NSW VG property_sales (unmatched)...")
    vg_records = fetch_all(
        "property_sales",
        "id,street_number,street_name,suburb,sale_date",
        filters=(
            f"sale_date=gte.{VG_DATE_MIN}&sale_date=lte.{VG_DATE_MAX}"
            "&state=eq.NSW&match_confidence=is.null"
        ),
    )
    print(f"  {len(vg_records):,} unmatched VG records")

    # ── Load LJ Hooker records ────────────────────────────────────────────────
    print("\nLoading LJ Hooker sourced_sales_nsw (unmatched)...")
    ljh_records = fetch_all(
        "sourced_sales_nsw",
        "source_id,street_number,street_name,street_type,suburb,bedrooms,bathrooms,car_spaces",
        filters="source=eq.ljhooker&match_confidence=is.null",
    )
    print(f"  {len(ljh_records):,} unmatched LJ Hooker records")

    # ── Build LJ Hooker indexes ───────────────────────────────────────────────
    # LJ Hooker already has street_name and street_type as separate columns.
    print("\nBuilding indexes...")
    ljh_exact  = {}
    ljh_notype = {}

    for rec in ljh_records:
        ljh_num  = (rec.get("street_number") or "").strip()
        ljh_name = rec.get("street_name") or ""
        ljh_type = rec.get("street_type") or ""
        suburb   = rec.get("suburb") or ""

        exact_key = make_key(ljh_num, ljh_name, ljh_type, suburb)
        if exact_key not in ljh_exact:
            ljh_exact[exact_key] = rec

        notype_key = make_key_no_type(ljh_num, ljh_name, suburb)
        if notype_key not in ljh_notype:
            ljh_notype[notype_key] = rec

    print(f"  {len(ljh_exact):,} unique LJ Hooker addresses indexed")

    # ── Match ─────────────────────────────────────────────────────────────────
    print("\nMatching...")
    exact_ps_updates  = []
    exact_ljh_updates = []
    no_match          = 0

    for rec in vg_records:
        # VG street_name includes type (e.g. "HERSEY STREET") — split it
        raw_name = (rec.get("street_name") or "").strip()
        vg_name, vg_type = split_street_name_type(raw_name)

        street_number = (rec.get("street_number") or "").strip()
        is_unit = "/" in street_number
        if is_unit:
            building_number = street_number.split("/")[1].strip()
        else:
            building_number = street_number

        suburb = rec.get("suburb", "")
        pid    = rec["id"]
        ljh    = None
        confidence = None

        if is_unit:
            # Units: try full "unit/building" key first
            ljh = ljh_exact.get(make_key(street_number, vg_name, vg_type, suburb))
            if not ljh:
                ljh = ljh_notype.get(make_key_no_type(street_number, vg_name, suburb))
            if ljh:
                confidence = "exact"
        else:
            ljh = ljh_exact.get(make_key(building_number, vg_name, vg_type, suburb))

            if not ljh:
                ljh = ljh_notype.get(make_key_no_type(building_number, vg_name, suburb))

            # Handle lot-suffix addresses like "14A" → try "14"
            if not ljh and re.search(r'\d[A-Z]$', building_number.upper()):
                stripped = re.sub(r'[A-Z]$', '', building_number.upper())
                ljh = ljh_exact.get(make_key(stripped, vg_name, vg_type, suburb))
                if not ljh:
                    ljh = ljh_notype.get(make_key_no_type(stripped, vg_name, suburb))

            if ljh:
                confidence = "exact"

        if ljh and confidence == "exact":
            exact_ps_updates.append({
                "id":                 pid,
                "bedrooms":           ljh.get("bedrooms"),
                "bathrooms":          ljh.get("bathrooms"),
                "car_spaces":         ljh.get("car_spaces"),
                "enriched":           "yes",
                "enriched_source":    "ljhooker",
                "enriched_source_id": ljh["source_id"],
                "match_confidence":   "exact",
            })
            exact_ljh_updates.append({
                "source_id":           ljh["source_id"],
                "matched_property_id": pid,
                "match_confidence":    "exact",
            })

        else:
            no_match += 1

    print(f"  Exact (raw): {len(exact_ps_updates):,}")
    print(f"  No match:    {no_match:,}")

    # ── Deduplication ─────────────────────────────────────────────────────────
    ljh_sid_counts = Counter(u["enriched_source_id"] for u in exact_ps_updates)
    ambiguous_sids = {sid for sid, n in ljh_sid_counts.items() if n > 1}

    pid_counts     = Counter(u["id"] for u in exact_ps_updates)
    ambiguous_pids = {pid for pid, n in pid_counts.items() if n > 1}

    if ambiguous_sids or ambiguous_pids:
        print(f"\n  ⚠ Deduplication:")
        print(f"    LJH records matching >1 VG record (dropped): {len(ambiguous_sids):,}")
        print(f"    VG records matched by >1 LJH record (dropped): {len(ambiguous_pids):,}")
        before = len(exact_ps_updates)
        exact_ps_updates = [
            u for u in exact_ps_updates
            if u["enriched_source_id"] not in ambiguous_sids
            and u["id"] not in ambiguous_pids
        ]
        exact_ljh_updates = [
            u for u in exact_ljh_updates
            if u["source_id"] not in ambiguous_sids
        ]
        print(f"    Exact matches after dedup: {before:,} → {len(exact_ps_updates):,}")

    print(f"\n  Exact (clean): {len(exact_ps_updates):,}")

    if not exact_ps_updates:
        print("\nNothing to write. Done.")
        return

    # ── Write to Supabase ─────────────────────────────────────────────────────
    print("\nWriting exact matches to property_sales...")
    ok = batch_update_property_sales(exact_ps_updates)
    print(f"  {ok:,} property_sales rows updated")

    print("Writing exact matches to sourced_sales_nsw...")
    ok = batch_update_sourced_sales(exact_ljh_updates)
    print(f"  {ok:,} sourced_sales_nsw rows updated")

    print(f"\n{'='*60}")
    print(f"ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Exact matches (clean): {len(exact_ps_updates):,}")
    print(f"No match:              {no_match:,}")
    if ambiguous_sids:
        print(f"Dropped (ambiguous):   {len(ambiguous_sids):,} LJH records matched >1 VG row")


if __name__ == "__main__":
    main()
