"""
find_historical_matches.py — Find out-of-window VG matches for unmatched agency records
========================================================================================
For every agency record in sourced_sales_nsw that has NO in-window match
(matched_property_id IS NULL), this script checks whether the same address
appears anywhere in property_sales (NSW) — regardless of date.

If a match is found, it writes:
  - outside_window_property_id: the matched property_sales.id
  - window_gap_days: signed int — (VG sale_date) minus (agency sold_date) in days.
      Positive = agency sold BEFORE the VG record (typical historical match).
      Negative = agency sold AFTER (unusual, possibly future listing).

If the same address appears multiple times in VG (same house sold in 2024 and 2025),
we store the match with the smallest absolute gap.

This script does NOT touch property_sales and does NOT write bedrooms/bathrooms.
It only records linkages so we can inspect the gap distribution and decide later
which matches are close enough to promote to full enrichment.

Supports all sources in sourced_sales_nsw. Add new agency names to SOURCES list.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 find_historical_matches.py

    # Single source only:
    python3 find_historical_matches.py --source mcgrath
"""

import requests
import os
import sys
import re
import time
import argparse
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

# All agency sources to process (extend as new agents are added)
SOURCES = ["raywhite", "mcgrath"]

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
            print(f"  ERROR {r.status_code}: {r.text[:200]}")
            break
        batch = r.json()
        if not batch:
            break
        records.extend(batch)
        offset += len(batch)
        if len(batch) < page_size:
            break
        if offset % 10000 == 0:
            print(f"    fetched {offset:,} rows...")
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


def patch_one_sourced(update):
    sid    = update.pop("source_id")
    source = update.pop("source")
    url = f"{SUPABASE_URL}/rest/v1/sourced_sales_nsw?source_id=eq.{sid}&source=eq.{source}"
    return patch_with_retry(url, update)


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
    """Split 'Hersey Street' → ('HERSEY', 'STREET'). Falls back to (full_name, '') if no match."""
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


def gap_days(vg_sale_date_str, agency_sold_date_str):
    """Signed gap in days: (VG date) - (agency date). Positive = agency sold before VG."""
    if not vg_sale_date_str or not agency_sold_date_str:
        return None
    try:
        vg   = date.fromisoformat(vg_sale_date_str[:10])
        ag   = date.fromisoformat(agency_sold_date_str[:10])
        return (vg - ag).days
    except Exception:
        return None


def build_vg_index(vg_records):
    """
    Build three indexes from VG records.
    Each key maps to a LIST of VG records (same address can appear multiple times
    if the property sold more than once in the dataset).
    """
    exact    = defaultdict(list)
    notype   = defaultdict(list)
    no_suburb = defaultdict(list)

    for rec in vg_records:
        raw_name = (rec.get("street_name") or "").strip()
        vg_name, vg_type = split_street_name_type(raw_name)
        street_number = (rec.get("street_number") or "").strip()
        suburb = rec.get("suburb", "")

        is_unit = "/" in street_number
        building_number = street_number.split("/")[1].strip() if is_unit else street_number

        if is_unit:
            exact[make_key(street_number, vg_name, vg_type, suburb)].append(rec)
            notype[make_key_no_type(street_number, vg_name, suburb)].append(rec)
        else:
            exact[make_key(building_number, vg_name, vg_type, suburb)].append(rec)
            notype[make_key_no_type(building_number, vg_name, suburb)].append(rec)
            nosub_key = make_key_no_type(building_number, vg_name, "")
            no_suburb[nosub_key].append(rec)

    return exact, notype, no_suburb


def find_best_vg_match(agency_rec, vg_exact, vg_notype, vg_no_suburb):
    """
    Try to find a VG record matching the agency address. Returns (vg_rec, gap) or (None, None).
    When multiple VG records match the same address (same house sold multiple times),
    returns the one with the smallest absolute gap.
    """
    num = (agency_rec.get("street_number") or "").strip()
    full_name = agency_rec.get("street_name") or ""
    ag_name, ag_type = split_street_name_type(full_name)
    suburb = agency_rec.get("suburb") or ""
    sold_date = agency_rec.get("sold_date") or ""
    is_unit = "/" in num
    building_number = num.split("/")[1].strip() if is_unit else num

    candidates = []

    if is_unit:
        candidates += vg_exact.get(make_key(num, ag_name, ag_type, suburb), [])
        if not candidates:
            candidates += vg_notype.get(make_key_no_type(num, ag_name, suburb), [])
    else:
        candidates += vg_exact.get(make_key(building_number, ag_name, ag_type, suburb), [])
        if not candidates:
            candidates += vg_notype.get(make_key_no_type(building_number, ag_name, suburb), [])
        if not candidates and re.search(r'\d[A-Z]$', building_number):
            stripped = re.sub(r'[A-Z]$', '', building_number)
            candidates += vg_exact.get(make_key(stripped, ag_name, ag_type, suburb), [])
        if not candidates:
            nosub = vg_no_suburb.get(make_key_no_type(building_number, ag_name, ""), [])
            if len(nosub) == 1:
                candidates = nosub

    if not candidates:
        return None, None

    # Pick the VG record with the smallest absolute gap
    best_rec, best_gap = None, None
    for vg_rec in candidates:
        g = gap_days(vg_rec.get("sale_date"), sold_date)
        if g is not None:
            if best_gap is None or abs(g) < abs(best_gap):
                best_rec, best_gap = vg_rec, g

    return best_rec, best_gap


def process_source(source, vg_exact, vg_notype, vg_no_suburb):
    print(f"\n── {source.upper()} ──────────────────────────────────────")

    # Load unmatched agency records for this source
    # (matched_property_id IS NULL = not already in-window matched)
    # (outside_window_property_id IS NULL = not already historically matched)
    print(f"  Loading unmatched {source} records...")
    agency_records = fetch_all(
        "sourced_sales_nsw",
        "source_id,source,street_number,street_name,suburb,sold_date",
        filters=f"source=eq.{source}&matched_property_id=is.null&outside_window_property_id=is.null",
    )
    print(f"  {len(agency_records):,} unmatched {source} records to check")

    if not agency_records:
        return 0, 0, []

    # Match
    matches = []
    no_match = 0
    gap_distribution = []

    for rec in agency_records:
        vg_rec, gap = find_best_vg_match(rec, vg_exact, vg_notype, vg_no_suburb)
        if vg_rec and gap is not None:
            matches.append({
                "source_id":                  rec["source_id"],
                "source":                     rec["source"],
                "outside_window_property_id": vg_rec["id"],
                "window_gap_days":            gap,
            })
            gap_distribution.append(gap)
        else:
            no_match += 1

    print(f"  Matched: {len(matches):,}  |  No match: {no_match:,}")

    # Write matches to sourced_sales_nsw (concurrent PATCHes)
    if not matches:
        return len(matches), no_match, gap_distribution

    print(f"  Writing {len(matches):,} matches to sourced_sales_nsw...")
    ok = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(patch_one_sourced, dict(m)) for m in matches]
        for f in as_completed(futures):
            if f.result():
                ok += 1

    print(f"  Written: {ok:,} / {len(matches):,}")
    return ok, no_match, gap_distribution


def print_gap_distribution(all_gaps):
    if not all_gaps:
        return

    print("\n── GAP DISTRIBUTION (agency sold_date vs VG sale_date) ───────────")
    print("  Positive = agency sold BEFORE VG record (typical historical match)")
    print("  Negative = agency sold AFTER VG record (unusual)\n")

    buckets = [
        ("Same sale / settlement lag  (0–90 days)",    0,    90),
        ("3–6 months",                                 91,   180),
        ("6–12 months",                                181,  365),
        ("1–2 years",                                  366,  730),
        ("2–5 years",                                  731,  1825),
        ("5+ years",                                   1826, 99999),
        ("After window (negative gap)",               -99999, -1),
    ]

    total = len(all_gaps)
    for label, lo, hi in buckets:
        count = sum(1 for g in all_gaps if lo <= g <= hi)
        pct = 100 * count / total if total else 0
        bar = "█" * int(pct / 2)
        print(f"  {label:<42} {count:>6,}  {pct:5.1f}%  {bar}")

    print(f"\n  Total matches: {total:,}")
    abs_gaps = [abs(g) for g in all_gaps]
    print(f"  Median abs gap: {sorted(abs_gaps)[len(abs_gaps)//2]:,} days")
    print(f"  Within 90 days:  {sum(1 for g in abs_gaps if g <= 90):,} ({100*sum(1 for g in abs_gaps if g <= 90)/total:.1f}%)")
    print(f"  Within 180 days: {sum(1 for g in abs_gaps if g <= 180):,} ({100*sum(1 for g in abs_gaps if g <= 180)/total:.1f}%)")
    print(f"  Within 365 days: {sum(1 for g in abs_gaps if g <= 365):,} ({100*sum(1 for g in abs_gaps if g <= 365)/total:.1f}%)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="Process one source only (e.g. mcgrath, raywhite)")
    args = parser.parse_args()

    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        sys.exit(1)

    sources = [args.source] if args.source else SOURCES

    # ── Load ALL VG property_sales for NSW ───────────────────────────────────
    print("Loading ALL NSW VG property_sales (no date filter)...")
    vg_records = fetch_all(
        "property_sales",
        "id,street_number,street_name,suburb,sale_date",
        filters="state=eq.NSW",
    )
    print(f"  {len(vg_records):,} VG records loaded")

    print("Building address indexes...")
    vg_exact, vg_notype, vg_no_suburb = build_vg_index(vg_records)
    print(f"  Exact index: {len(vg_exact):,} keys")

    # ── Process each source ───────────────────────────────────────────────────
    all_gaps = []
    total_matched = 0
    total_no_match = 0

    for source in sources:
        ok, no_match, gaps = process_source(source, vg_exact, vg_notype, vg_no_suburb)
        total_matched  += ok
        total_no_match += no_match
        all_gaps.extend(gaps)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"HISTORICAL MATCH COMPLETE")
    print(f"{'='*60}")
    print(f"Total historical matches written: {total_matched:,}")
    print(f"Total no match:                   {total_no_match:,}")

    print_gap_distribution(all_gaps)


if __name__ == "__main__":
    main()
