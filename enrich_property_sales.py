"""
enrich_property_sales.py — Enrich property_sales with bedroom data from sourced_sales_nsw
===========================================================================================
Exact matches only — write bedrooms/bathrooms/car_spaces to property_sales,
mark match_confidence='exact' on both tables, cross-link the records.

Probable matching (same street/number, different suburb) has been removed —
it produced too many false positives across NSW where the same street name
and number exists in multiple suburbs.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 enrich_property_sales.py
"""

import requests
import json
import os
import sys
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

VG_DATE_MIN = "2025-06-13"
VG_DATE_MAX = "2026-05-28"
BATCH_SIZE  = 500

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
    "DALE": "DALE", "EDGE": "EDGE", "END": "END", "FLAT": "FLAT",
    "GATE": "GATE", "HILL": "HILL", "LINE": "LINE", "PASS": "PASS",
    "PATH": "PATH", "RAMP": "RAMP", "REST": "REST", "RING": "RING",
    "RUN": "RUN", "SPUR": "SPUR", "TURN": "TURN", "YARD": "YARD",
    "GRA": "GRANGE", "GRN": "GREEN", "NOOK": "NOOK", "GLEN": "GLEN",
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
    """PATCH with exponential backoff retry."""
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
    url = f"{SUPABASE_URL}/rest/v1/sourced_sales_nsw?source_id=eq.{sid}&source=eq.raywhite"
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
    print("Loading NSW VG property_sales...")
    vg_records = fetch_all(
        "property_sales",
        "id,street_number,street_name,suburb,sale_date",
        filters=f"sale_date=gte.{VG_DATE_MIN}&sale_date=lte.{VG_DATE_MAX}&state=eq.NSW&match_confidence=is.null",
    )
    print(f"  {len(vg_records):,} unmatched VG records")

    # ── Load Ray White records ────────────────────────────────────────────────
    print("\nLoading Ray White sourced_sales_nsw...")
    rw_records = fetch_all(
        "sourced_sales_nsw",
        "source_id,street_number,street_name,street_type,suburb,sold_date,bedrooms,bathrooms,car_spaces",
        filters=f"sold_date=gte.{VG_DATE_MIN}&sold_date=lte.{VG_DATE_MAX}&source=eq.raywhite&match_confidence=is.null",
    )
    print(f"  {len(rw_records):,} unmatched Ray White records")

    # ── Build Ray White indexes ───────────────────────────────────────────────
    print("\nBuilding indexes...")
    rw_exact  = {}
    rw_notype = {}

    for rec in rw_records:
        rw_num = (rec.get("street_number") or "").strip()

        exact_key = make_key(rw_num, rec.get("street_name"),
                             rec.get("street_type"), rec.get("suburb"))
        if exact_key not in rw_exact:
            rw_exact[exact_key] = rec

        notype_key = make_key_no_type(rw_num, rec.get("street_name"), rec.get("suburb"))
        if notype_key not in rw_notype:
            rw_notype[notype_key] = rec

    # ── Match ─────────────────────────────────────────────────────────────────
    print("\nMatching...")
    exact_ps_updates = []
    exact_rw_updates = []
    no_match         = 0

    for rec in vg_records:
        raw_name = (rec.get("street_name") or "").strip()
        parts = raw_name.split()
        if len(parts) >= 2 and parts[-1].upper() in STREET_TYPES:
            vg_name = " ".join(parts[:-1])
            vg_type = parts[-1]
        else:
            vg_name = raw_name
            vg_type = None

        street_number = (rec.get("street_number") or "").strip()
        is_unit = "/" in street_number
        if is_unit:
            building_number = street_number.split("/")[1].strip()
        else:
            building_number = street_number
        suburb = rec.get("suburb", "")
        pid    = rec["id"]
        rw     = None

        if is_unit:
            rw = rw_exact.get(make_key(street_number, vg_name, vg_type, suburb))
            if not rw:
                rw = rw_notype.get(make_key_no_type(street_number, vg_name, suburb))
        else:
            rw = rw_exact.get(make_key(building_number, vg_name, vg_type, suburb))
            if not rw:
                rw = rw_notype.get(make_key_no_type(building_number, vg_name, suburb))
            if not rw and re.search(r'\d[A-Z]$', building_number.upper()):
                stripped = re.sub(r'[A-Z]$', '', building_number.upper())
                rw = rw_exact.get(make_key(stripped, vg_name, vg_type, suburb))
                if not rw:
                    rw = rw_notype.get(make_key_no_type(stripped, vg_name, suburb))

        if rw:
            exact_ps_updates.append({
                "id":                 pid,
                "bedrooms":           rw.get("bedrooms"),
                "bathrooms":          rw.get("bathrooms"),
                "car_spaces":         rw.get("car_spaces"),
                "enriched":           "yes",
                "enriched_source":    "raywhite",
                "enriched_source_id": rw["source_id"],
                "match_confidence":   "exact",
            })
            exact_rw_updates.append({
                "source_id":           rw["source_id"],
                "matched_property_id": pid,
                "match_confidence":    "exact",
            })
        else:
            no_match += 1

    print(f"  Exact:    {len(exact_ps_updates):,}")
    print(f"  No match: {no_match:,}")

    # ── Batch write to Supabase ───────────────────────────────────────────────
    print("\nWriting exact matches to property_sales...")
    ok = batch_update_property_sales(exact_ps_updates)
    print(f"  {ok:,} property_sales rows updated")

    print("Writing exact matches to sourced_sales_nsw...")
    ok = batch_update_sourced_sales(exact_rw_updates)
    print(f"  {ok:,} sourced_sales_nsw rows updated")

    print(f"\n{'='*60}")
    print(f"ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Exact matches: {len(exact_ps_updates):,}")
    print(f"No match:      {no_match:,}")

if __name__ == "__main__":
    main()
