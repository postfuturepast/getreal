"""
match_mcgrath_nsw.py — Enrich property_sales with bedroom data from McGrath sourced_sales_nsw
==============================================================================================
Matches McGrath sourced_sales records (source='mcgrath') to NSW VG property_sales records
by address, then writes bedrooms/bathrooms/car_spaces back to matched property_sales rows.

Exact matches only — write bedrooms/bathrooms/car_spaces to property_sales,
mark match_confidence='exact' on both tables, cross-link the records.

Probable matching (same street/number, different suburb) has been removed —
it produced too many false positives across NSW where the same street name
and number exists in multiple suburbs.

Key difference vs Ray White: McGrath street_name includes the street type
(e.g. "Hersey Street"), so we split it here. VG data also bundles type into street_name.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 match_mcgrath_nsw.py
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

# Wide window to capture McGrath's full historical coverage
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
    "DALE": "DALE", "EDGE": "EDGE", "END": "END", "FLAT": "FLAT",
    "GATE": "GATE", "HILL": "HILL", "LINE": "LINE", "PASS": "PASS",
    "PATH": "PATH", "RAMP": "RAMP", "REST": "REST", "RING": "RING",
    "RUN": "RUN", "SPUR": "SPUR", "TURN": "TURN", "YARD": "YARD",
    "GRA": "GRANGE", "GRN": "GREEN", "NOOK": "NOOK", "GLEN": "GLEN",
    # Full forms that also appear and should normalise to themselves
    "STREET": "STREET", "AVENUE": "AVENUE", "ROAD": "ROAD", "DRIVE": "DRIVE",
    "COURT": "COURT", "CLOSE": "CLOSE", "PLACE": "PLACE", "TERRACE": "TERRACE",
    "CRESCENT": "CRESCENT", "BOULEVARD": "BOULEVARD", "HIGHWAY": "HIGHWAY",
    "PARADE": "PARADE", "GROVE": "GROVE", "LANE": "LANE", "CIRCUIT": "CIRCUIT",
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
    url = f"{SUPABASE_URL}/rest/v1/sourced_sales_nsw?source_id=eq.{sid}&source=eq.mcgrath"
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
    """
    Split 'Hersey Street' → ('Hersey', 'STREET')
    Handles multi-word street types: 'Smith Parade' → ('Smith', 'PARADE')
    If last word not a known type, returns (full_name, '')
    """
    if not full_name:
        return "", ""
    parts = full_name.strip().upper().split()
    if len(parts) >= 2 and parts[-1] in STREET_TYPES:
        name = " ".join(parts[:-1])
        stype = STREET_TYPES[parts[-1]]
        return name, stype
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

    # ── Load McGrath records ──────────────────────────────────────────────────
    print("\nLoading McGrath sourced_sales_nsw (unmatched)...")
    mc_records = fetch_all(
        "sourced_sales_nsw",
        "source_id,street_number,street_name,suburb,sold_date,bedrooms,bathrooms,car_spaces",
        filters="source=eq.mcgrath&match_confidence=is.null",
    )
    print(f"  {len(mc_records):,} unmatched McGrath records")

    # ── Build McGrath indexes ─────────────────────────────────────────────────
    # McGrath street_name = "Hersey Street" (full name + type concatenated)
    # We split it to match VG's separate street_name + implied type pattern.
    print("\nBuilding indexes...")
    mc_exact  = {}
    mc_notype = {}

    for rec in mc_records:
        mc_num = (rec.get("street_number") or "").strip()
        mc_full_name = rec.get("street_name") or ""
        mc_name, mc_type = split_street_name_type(mc_full_name)
        suburb = rec.get("suburb") or ""

        exact_key = make_key(mc_num, mc_name, mc_type, suburb)
        if exact_key not in mc_exact:
            mc_exact[exact_key] = rec

        notype_key = make_key_no_type(mc_num, mc_name, suburb)
        if notype_key not in mc_notype:
            mc_notype[notype_key] = rec

    # ── Match ─────────────────────────────────────────────────────────────────
    print("\nMatching...")
    exact_ps_updates = []
    exact_mc_updates = []
    no_match         = 0

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
        mc     = None
        confidence = None

        if is_unit:
            # Units: try full unit/building key first, then no-type
            rw_unit_key = make_key(street_number, vg_name, vg_type, suburb)
            mc = mc_exact.get(rw_unit_key)
            if not mc:
                mc = mc_notype.get(make_key_no_type(street_number, vg_name, suburb))
            if mc:
                confidence = "exact"
        else:
            mc = mc_exact.get(make_key(building_number, vg_name, vg_type, suburb))

            if not mc:
                mc = mc_notype.get(make_key_no_type(building_number, vg_name, suburb))

            # Handle lot-suffix addresses like "14A" → try "14"
            if not mc and re.search(r'\d[A-Z]$', building_number.upper()):
                stripped = re.sub(r'[A-Z]$', '', building_number.upper())
                mc = mc_exact.get(make_key(stripped, vg_name, vg_type, suburb))

            if mc:
                confidence = "exact"

        if mc and confidence == "exact":
            exact_ps_updates.append({
                "id":                 pid,
                "bedrooms":           mc.get("bedrooms"),
                "bathrooms":          mc.get("bathrooms"),
                "car_spaces":         mc.get("car_spaces"),
                "enriched":           "yes",
                "enriched_source":    "mcgrath",
                "enriched_source_id": mc["source_id"],
                "match_confidence":   "exact",
            })
            exact_mc_updates.append({
                "source_id":           mc["source_id"],
                "matched_property_id": pid,
                "match_confidence":    "exact",
            })

        else:
            no_match += 1

    print(f"  Exact (raw): {len(exact_ps_updates):,}")
    print(f"  No match:    {no_match:,}")

    # ── Deduplication: remove ambiguous many-to-one and one-to-many ──────────
    # (1) Any McGrath source_id matched to more than one VG record → drop all
    #     (single sourced listing claiming to enrich multiple VG records = wrong)
    from collections import Counter
    mc_sid_counts = Counter(u["enriched_source_id"] for u in exact_ps_updates)
    ambiguous_sids = {sid for sid, n in mc_sid_counts.items() if n > 1}

    # (2) Any VG property_id matched by more than one McGrath record → drop all
    #     (shouldn't happen with single-entry index, but guard anyway)
    pid_counts = Counter(u["id"] for u in exact_ps_updates)
    ambiguous_pids = {pid for pid, n in pid_counts.items() if n > 1}

    if ambiguous_sids or ambiguous_pids:
        print(f"\n  ⚠ Deduplication:")
        print(f"    McGrath records matching >1 VG record (dropped): {len(ambiguous_sids):,}")
        print(f"    VG records matched by >1 McGrath record (dropped): {len(ambiguous_pids):,}")
        before = len(exact_ps_updates)
        exact_ps_updates = [
            u for u in exact_ps_updates
            if u["enriched_source_id"] not in ambiguous_sids
            and u["id"] not in ambiguous_pids
        ]
        exact_mc_updates = [
            u for u in exact_mc_updates
            if u["source_id"] not in ambiguous_sids
        ]
        print(f"    Exact matches after dedup: {before:,} → {len(exact_ps_updates):,}")

    print(f"\n  Exact (clean): {len(exact_ps_updates):,}")

    if not exact_ps_updates:
        print("\nNothing to write. Done.")
        return

    # ── Batch write to Supabase ───────────────────────────────────────────────
    print("\nWriting exact matches to property_sales...")
    ok = batch_update_property_sales(exact_ps_updates)
    print(f"  {ok:,} property_sales rows updated")

    print("Writing exact matches to sourced_sales_nsw...")
    ok = batch_update_sourced_sales(exact_mc_updates)
    print(f"  {ok:,} sourced_sales_nsw rows updated")

    print(f"\n{'='*60}")
    print(f"ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    print(f"Exact matches (clean): {len(exact_ps_updates):,}")
    print(f"No match:              {no_match:,}")
    if ambiguous_sids:
        print(f"Dropped (ambiguous):   {len(ambiguous_sids):,} McGrath records matched >1 VG row")


if __name__ == "__main__":
    main()
