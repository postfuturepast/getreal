"""
match_raywhite_nsw.py — Stage 2: Address matching quality test
==============================================================
Matches Ray White sourced_sales_nsw records against NSW VG property_sales
to measure bedroom/bathroom enrichment coverage.

Results:
- Overall match rate
- Per-suburb match rate
- Sample of matched + unmatched records for manual inspection

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 match_raywhite_nsw.py
"""

import requests
import json
import os
import sys
import re
from collections import defaultdict

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

# VG data window
VG_DATE_MIN = "2025-06-13"
VG_DATE_MAX = "2026-05-28"

# Street type normalisation — abbreviation → full word
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
    "PKWY": "PARKWAY", "PWY": "PARKWAY", "RDGE": "RIDGE", "RDG": "RIDGE",
    "ROW": "ROW", "RUN": "RUN", "SQ": "SQUARE", "STRAND": "STRAND",
    "VALE": "VALE", "VIEW": "VIEW", "VISTA": "VISTA", "VW": "VIEW",
    "WHRF": "WHARF", "YARD": "YARD", "BEND": "BEND", "BVRD": "BOULEVARD",
    "BYPA": "BYPASS", "BYWAY": "BYWAY", "CHASE": "CHASE", "ALLY": "ALLEY",
    "ALY": "ALLEY", "ARC": "ARCADE", "APP": "APPROACH", "APPR": "APPROACH",
    "BA": "BANAN", "BANK": "BANK", "BASN": "BASIN", "BAY": "BAY",
    "BCH": "BEACH", "CAUS": "CAUSEWAY", "CTR": "CENTRE", "CH": "CHASE",
    "CIR": "CIRCLE", "CRCS": "CIRCUS", "CONN": "CONNECTOR",
    "CSWY": "CAUSEWAY", "COVE": "COVE", "DALE": "DALE", "DELL": "DELL",
    "DEVN": "DEVIATION", "DIP": "DIP", "DSTR": "DISTRIBUTOR",
    "DVWY": "DRIVEWAY", "EDGE": "EDGE", "ELB": "ELBOW", "END": "END",
    "ENT": "ENTRANCE", "ESMT": "EASEMENT", "EXP": "EXPRESSWAY",
    "FAWY": "FAIRWAY", "FIRE": "FIRETRAIL", "FLAT": "FLAT",
    "FOLW": "FOLLOW", "FORD": "FORD", "FORM": "FORMATION", "FWY": "FREEWAY",
    "GATE": "GATE", "GLADE": "GLADE", "GLEN": "GLEN", "GRA": "GRANGE",
    "GRN": "GREEN", "GRND": "GROUND", "GTE": "GATE", "HILL": "HILL",
    "INTG": "INTERCHANGE", "JCT": "JUNCTION", "KEY": "KEY",
    "LANE": "LANE", "LNWY": "LANEWAY", "LINE": "LINE", "MEWS": "MEWS",
    "MNDR": "MEANDER", "NOOK": "NOOK", "OTLK": "OUTLOOK", "PASS": "PASS",
    "PATH": "PATH", "PIAZ": "PIAZZA", "PKLD": "PARKLANDS",
    "PROM": "PROMENADE", "QUAD": "QUADRANT", "QUAY": "QUAY",
    "RAMP": "RAMP", "RCH": "REACH", "REEF": "REEF", "RES": "RESERVE",
    "REST": "REST", "RGWY": "RIDGEWAY", "RING": "RING", "RMBL": "RAMBLE",
    "RNDBT": "ROUNDABOUT", "ROAD": "ROAD", "ROTARY": "ROTARY",
    "RTE": "ROUTE", "SBWY": "SUBWAY", "SPUR": "SPUR", "TRFY": "TRAFFICWAY",
    "TURN": "TURN", "UPAS": "UNDERPASS", "VIAD": "VIADUCT",
}

def supabase_headers():
    return {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
    }

def fetch_all(table, select, filters="", order=""):
    """Paginate through all rows in a Supabase table."""
    records = []
    page_size = 1000
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
        if filters:
            url += f"&{filters}"
        if order:
            url += f"&order={order}"
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

def normalise_street_type(t):
    if not t:
        return ""
    t = t.upper().strip()
    return STREET_TYPES.get(t, t)

def normalise_street_name(name):
    if not name:
        return ""
    # uppercase, strip punctuation, collapse whitespace
    name = re.sub(r"[^A-Z0-9 ]", "", name.upper())
    return " ".join(name.split())

def make_key(street_number, street_name, street_type, suburb):
    """Normalised match key."""
    num = (street_number or "").strip().upper()
    name = normalise_street_name(street_name)
    stype = normalise_street_type(street_type)
    sub = (suburb or "").strip().upper()
    return f"{num}|{name}|{stype}|{sub}"

def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        sys.exit(1)

    # ── Load VG records ───────────────────────────────────────────────────────
    print("Loading NSW VG property_sales...")
    vg_records = fetch_all(
        "property_sales",
        "id,street_number,street_name,suburb,sale_date,sale_price,property_type",
        filters=f"sale_date=gte.{VG_DATE_MIN}&sale_date=lte.{VG_DATE_MAX}&state=eq.NSW",
    )
    print(f"  {len(vg_records):,} VG records loaded")

    # ── Load Ray White records ─────────────────────────────────────────────────
    print("\nLoading Ray White sourced_sales_nsw...")
    rw_records = fetch_all(
        "sourced_sales_nsw",
        "source_id,street_number,street_name,street_type,suburb,sold_date,sold_price,bedrooms,bathrooms,car_spaces",
        filters=f"sold_date=gte.{VG_DATE_MIN}&sold_date=lte.{VG_DATE_MAX}&source=eq.raywhite",
    )
    print(f"  {len(rw_records):,} Ray White records in VG window")

    # ── Build Ray White lookup ────────────────────────────────────────────────
    print("\nBuilding Ray White address index...")
    rw_index = {}
    for rec in rw_records:
        key = make_key(
            rec.get("street_number"),
            rec.get("street_name"),
            rec.get("street_type"),
            rec.get("suburb"),
        )
        if key not in rw_index:
            rw_index[key] = rec

    print(f"  {len(rw_index):,} unique addresses in Ray White")

    # ── Match VG records ──────────────────────────────────────────────────────
    print("\nMatching VG records against Ray White...")

    matched = 0
    unmatched = 0
    suburb_stats = defaultdict(lambda: {"total": 0, "matched": 0})
    sample_matched = []
    sample_unmatched = []

    for rec in vg_records:
        suburb = (rec.get("suburb") or "").strip().upper()
        suburb_stats[suburb]["total"] += 1

        # VG embeds street type in street_name (e.g. "Landon St")
        # Split last word as type, rest as name
        raw_name = (rec.get("street_name") or "").strip()
        parts = raw_name.split()
        if len(parts) >= 2 and parts[-1].upper() in STREET_TYPES:
            vg_street_name = " ".join(parts[:-1])
            vg_street_type = parts[-1]
        else:
            vg_street_name = raw_name
            vg_street_type = None

        # For unit addresses like "3/2", extract building number "2"
        street_number = (rec.get("street_number") or "").strip()
        if "/" in street_number:
            building_number = street_number.split("/")[-1].strip()
        else:
            building_number = street_number

        key = make_key(
            building_number,
            vg_street_name,
            vg_street_type,
            rec.get("suburb"),
        )

        rw = rw_index.get(key)

        # Fallback 1: try with full street_number if building_number didn't match
        if not rw and building_number != street_number:
            key2 = make_key(street_number, vg_street_name, vg_street_type, rec.get("suburb"))
            rw = rw_index.get(key2)

        # Fallback 2: try without street type (catches type mismatches)
        if not rw:
            key3 = make_key(building_number, vg_street_name, None, rec.get("suburb"))
            rw = rw_index.get(key3)

        # Fallback 3: try stripping trailing letter from street number (e.g. "44A" → "44")
        if not rw and re.search(r'\d[A-Z]$', building_number.upper()):
            stripped = re.sub(r'[A-Z]$', '', building_number.upper())
            key4 = make_key(stripped, vg_street_name, vg_street_type, rec.get("suburb"))
            rw = rw_index.get(key4)
        if rw:
            matched += 1
            suburb_stats[suburb]["matched"] += 1
            if len(sample_matched) < 10:
                sample_matched.append({
                    "vg":  f"{rec.get('street_number')} {rec.get('street_name')} {rec.get('street_type')}, {rec.get('suburb')}",
                    "rw":  f"{rw.get('street_number')} {rw.get('street_name')} {rw.get('street_type')}, {rw.get('suburb')}",
                    "beds": rw.get("bedrooms"),
                    "baths": rw.get("bathrooms"),
                })
        else:
            unmatched += 1
            if len(sample_unmatched) < 10:
                sample_unmatched.append(
                    f"{rec.get('street_number')} {rec.get('street_name')} {rec.get('street_type')}, {rec.get('suburb')}"
                )

    total = matched + unmatched
    pct = 100 * matched / total if total else 0

    # ── Results ───────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"VG records:          {total:,}")
    print(f"Ray White (window):  {len(rw_records):,}")
    print(f"Matched:             {matched:,} ({pct:.1f}%)")
    print(f"Unmatched:           {unmatched:,}")

    print(f"\n── Sample matched records ──")
    for s in sample_matched:
        print(f"  VG:  {s['vg']}")
        print(f"  RW:  {s['rw']}  beds={s['beds']} baths={s['baths']}")
        print()

    print(f"── Sample unmatched VG records ──")
    for s in sample_unmatched:
        print(f"  {s}")

    # ── Per-suburb breakdown (top 30 by volume) ───────────────────────────────
    print(f"\n── Top 30 suburbs by volume ──")
    top_suburbs = sorted(suburb_stats.items(), key=lambda x: -x[1]["total"])[:30]
    print(f"{'Suburb':<30} {'Total':>7} {'Matched':>8} {'Coverage':>9}")
    print("-" * 58)
    for suburb, stats in top_suburbs:
        t = stats["total"]
        m = stats["matched"]
        pct_s = 100 * m / t if t else 0
        print(f"{suburb:<30} {t:>7,} {m:>8,} {pct_s:>8.1f}%")

    # ── Save full results ─────────────────────────────────────────────────────
    output = {
        "summary": {
            "vg_total": total,
            "rw_in_window": len(rw_records),
            "matched": matched,
            "match_pct": round(pct, 2),
        },
        "suburb_stats": {
            k: v for k, v in sorted(suburb_stats.items(), key=lambda x: -x[1]["total"])
        }
    }
    with open("match_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results saved to match_results.json")


if __name__ == "__main__":
    main()
