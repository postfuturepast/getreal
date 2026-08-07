"""
match_nsw_enrichment.py — Consolidated NSW enrichment matching
==============================================================
Matches ALL sourced_sales_nsw records (all agencies) against NSW VG
property_sales records by address, writes bedrooms/bathrooms/car_spaces
back to matched property_sales rows.

Replaces:
  match_raywhite_nsw.py
  match_mcgrath_nsw.py
  match_ljhooker_nsw.py
  match_harcourts_nsw.py

Only processes unmatched records on both sides (match_confidence IS NULL),
so incremental weekly runs are safe — already-matched rows are skipped.

Address normalisation per source:
  raywhite  — separate street_name + street_type columns
  mcgrath   — street_name includes type ("Hersey Street") → auto-split
  ljhooker  — separate street_name + street_type columns
  harcourts — polluted street_name; parse address from source_id URL slug
  (others)  — separate columns; fall back to auto-split if no street_type

Match confidence tiers:
  exact     — address match + sold_date within DATE_WINDOW_DAYS (or no sold_date)
  historical — address match + sold_date within HISTORICAL_WINDOW_DAYS

Date disambiguation:
  When one address has multiple VG candidates (property sold multiple times),
  use sold_date to pick the closest sale. Sources with no sold_date (LJH)
  are skipped for multi-candidate addresses.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 match_nsw_enrichment.py

Options:
    --source    Only process records from a specific source (e.g. raywhite)
    --dry-run   Print match stats without writing to Supabase
    --workers   Parallel write workers (default: 20)
"""

import argparse
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

# ── Config ─────────────────────────────────────────────────────────────────────

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

DATE_WINDOW_DAYS      = 180   # sold_date within this → exact match
HISTORICAL_WINDOW_DAYS = 730  # sold_date within this → historical match

# ── Street type normalisation ───────────────────────────────────────────────────

STREET_TYPES = {
    # Abbreviations → canonical full form
    "ST": "STREET", "AVE": "AVENUE", "AV": "AVENUE", "RD": "ROAD",
    "DR": "DRIVE", "DV": "DRIVE", "CT": "COURT", "CRT": "COURT",
    "CL": "CLOSE", "PL": "PLACE", "TCE": "TERRACE", "TER": "TERRACE",
    "CRES": "CRESCENT", "CR": "CRESCENT", "BLVD": "BOULEVARD",
    "HWY": "HIGHWAY", "PDE": "PARADE", "GR": "GROVE", "LN": "LANE",
    "WAY": "WAY", "ESP": "ESPLANADE", "CCT": "CIRCUIT", "CIR": "CIRCUIT",
    "BDWY": "BROADWAY", "BVD": "BOULEVARD", "GLN": "GLEN",
    "RISE": "RISE", "LOOP": "LOOP", "LINK": "LINK", "WALK": "WALK",
    "TRCE": "TRACE", "TRAK": "TRACK", "TRK": "TRACK", "PARK": "PARK",
    "PKWY": "PARKWAY", "PWY": "PARKWAY", "RDG": "RIDGE", "RDGE": "RIDGE",
    "MEWS": "MEWS", "ROW": "ROW", "SQ": "SQUARE", "QUAY": "QUAY",
    "CHASE": "CHASE", "VALE": "VALE", "VIEW": "VIEW", "VW": "VIEW",
    "BEND": "BEND", "COVE": "COVE", "DALE": "DALE", "EDGE": "EDGE",
    "END": "END", "GATE": "GATE", "GTE": "GATE", "HILL": "HILL",
    "LINE": "LINE", "PASS": "PASS", "PATH": "PATH", "RAMP": "RAMP",
    "REST": "REST", "RING": "RING", "RUN": "RUN", "SPUR": "SPUR",
    "TURN": "TURN", "YARD": "YARD", "GRA": "GRANGE", "GRN": "GREEN",
    "NOOK": "NOOK", "GLEN": "GLEN", "ALLY": "ALLEY", "ALY": "ALLEY",
    "ARC": "ARCADE", "APP": "APPROACH", "APPR": "APPROACH",
    "BCH": "BEACH", "CAUS": "CAUSEWAY", "CTR": "CENTRE",
    "CRCS": "CIRCUS", "CONN": "CONNECTOR", "CSWY": "CAUSEWAY",
    "DELL": "DELL", "DEVN": "DEVIATION", "DIP": "DIP",
    "DVWY": "DRIVEWAY", "ELB": "ELBOW", "ENT": "ENTRANCE",
    "EXP": "EXPRESSWAY", "FAWY": "FAIRWAY", "FIRE": "FIRETRAIL",
    "FLAT": "FLAT", "FOLW": "FOLLOW", "FORD": "FORD", "FWY": "FREEWAY",
    "BYPA": "BYPASS", "BYWAY": "BYWAY", "GLADE": "GLADE",
    "GRND": "GROUND", "INTG": "INTERCHANGE", "JCT": "JUNCTION",
    "LANE": "LANE", "LNWY": "LANEWAY", "MNDR": "MEANDER",
    "OTLK": "OUTLOOK", "PIAZ": "PIAZZA", "PKLD": "PARKLANDS",
    "PROM": "PROMENADE", "QUAD": "QUADRANT", "RAMP": "RAMP",
    "RCH": "REACH", "RES": "RESERVE", "RGWY": "RIDGEWAY",
    "RMBL": "RAMBLE", "RNDBT": "ROUNDABOUT", "ROTARY": "ROTARY",
    "RTE": "ROUTE", "SBWY": "SUBWAY", "TRFY": "TRAFFICWAY",
    "UPAS": "UNDERPASS", "VIAD": "VIADUCT", "BANK": "BANK",
    "BAY": "BAY", "FORM": "FORMATION", "STRAND": "STRAND",
    "VISTA": "VISTA", "WHRF": "WHARF",
    # Full forms already canonical
    "STREET": "STREET", "AVENUE": "AVENUE", "ROAD": "ROAD",
    "DRIVE": "DRIVE", "COURT": "COURT", "CLOSE": "CLOSE",
    "PLACE": "PLACE", "TERRACE": "TERRACE", "CRESCENT": "CRESCENT",
    "BOULEVARD": "BOULEVARD", "HIGHWAY": "HIGHWAY", "PARADE": "PARADE",
    "GROVE": "GROVE", "CIRCUIT": "CIRCUIT", "ESPLANADE": "ESPLANADE",
    "BROADWAY": "BROADWAY", "PARKWAY": "PARKWAY", "RIDGE": "RIDGE",
    "SQUARE": "SQUARE", "TRACK": "TRACK", "GRANGE": "GRANGE",
    "GREEN": "GREEN", "FREEWAY": "FREEWAY", "BYPASS": "BYPASS",
    "HEIGHTS": "HEIGHTS", "GARDENS": "GARDENS", "ALLEY": "ALLEY",
    "ARCADE": "ARCADE", "APPROACH": "APPROACH", "BEACH": "BEACH",
    "CAUSEWAY": "CAUSEWAY", "CENTRE": "CENTRE", "CIRCLE": "CIRCLE",
}


# ── Supabase helpers ────────────────────────────────────────────────────────────

def sb_headers(prefer="return=minimal"):
    h = {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def fetch_all(table, select, filters=""):
    records   = []
    page_size = 1000
    offset    = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}"
        if filters:
            url += f"&{filters}"
        url += f"&limit={page_size}&offset={offset}"
        r = requests.get(url, headers=sb_headers(prefer=""), timeout=30)
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
        if offset % 50_000 == 0:
            print(f"    fetched {offset:,} rows...")
    return records


def patch_with_retry(url, payload, retries=3, backoff=0.5):
    for attempt in range(retries):
        try:
            r = requests.patch(url, headers=sb_headers(), json=payload, timeout=15)
            if r.status_code in (200, 204):
                return True
        except Exception:
            pass
        time.sleep(backoff * (2 ** attempt))
    return False


def batch_patch(updates_fn_pairs, workers=20):
    """Run a list of (url, payload) patch calls in parallel. Returns success count."""
    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(patch_with_retry, url, payload): (url, payload)
                   for url, payload in updates_fn_pairs}
        for f in as_completed(futures):
            if f.result():
                ok += 1
    return ok


# ── Address normalisation ───────────────────────────────────────────────────────

def norm_name(name):
    if not name:
        return ""
    return " ".join(re.sub(r"[^A-Z0-9 ]", "", name.upper()).split())


def norm_type(t):
    if not t:
        return ""
    return STREET_TYPES.get(t.upper().strip(), t.upper().strip())


def split_name_type(full_name):
    """Split VG-style 'HERSEY STREET' → ('HERSEY', 'STREET')."""
    if not full_name:
        return "", ""
    parts = full_name.strip().upper().split()
    if len(parts) >= 2 and parts[-1] in STREET_TYPES:
        return " ".join(parts[:-1]), STREET_TYPES[parts[-1]]
    return full_name.strip().upper(), ""


def make_key(number, name, stype, suburb):
    return f"{(number or '').strip().upper()}|{norm_name(name)}|{norm_type(stype)}|{(suburb or '').strip().upper()}"


def make_key_notype(number, name, suburb):
    return f"{(number or '').strip().upper()}|{norm_name(name)}|{(suburb or '').strip().upper()}"


def parse_harcourts_address(source_id, suburb, state_code, postcode):
    """
    Parse street number/name/type from a Harcourts source_id URL slug.

    Format: 1p{office_id}-{number}-{street_slug}-{suburb_slug}-{state}-{postcode}
    Example: 1p6684-35-kundabung-road-kundabung-nsw-2441
      → ('35', 'KUNDABUNG', 'ROAD')

    Returns (street_number, street_name, street_type) or (None, None, None).
    """
    try:
        s = re.sub(r'^1p\d+-', '', source_id)

        suburb_slug = (suburb or "").lower().strip().replace(" ", "-")
        state_slug  = (state_code or "").lower().strip()
        suffix      = f"-{suburb_slug}-{state_slug}-{postcode}"

        if s.endswith(suffix):
            street_part = s[:-len(suffix)]
        else:
            sfx2 = f"-{state_slug}-{postcode}"
            idx  = s.rfind(sfx2)
            if idx == -1:
                return None, None, None
            street_part = s[:idx]
            sfx3 = f"-{suburb_slug}"
            if street_part.endswith(sfx3):
                street_part = street_part[:-len(sfx3)]

        parts = street_part.split("-")
        if len(parts) < 2:
            return None, None, None

        number = parts[0].upper()
        if not re.match(r'^\d', number):
            return None, None, None

        # Unit format: "2-14" → "2/14"
        if len(parts) >= 3 and re.match(r'^\d+[a-z]?$', parts[1]):
            number = f"{parts[0]}/{parts[1]}".upper()
            rest   = parts[2:]
        else:
            rest = parts[1:]

        if not rest:
            return number, "", ""

        if rest[-1].upper() in STREET_TYPES:
            stype = STREET_TYPES[rest[-1].upper()]
            name  = " ".join(p.upper() for p in rest[:-1])
        else:
            stype = ""
            name  = " ".join(p.upper() for p in rest)

        return number, name, stype

    except Exception:
        return None, None, None


def normalize_sourced(rec):
    """
    Return (street_number, street_name, street_type, suburb, sold_date) for
    any sourced_sales_nsw record, applying per-source parsing logic.
    """
    source = (rec.get("source") or "").lower()

    suburb    = (rec.get("suburb") or "").strip()
    sold_date = rec.get("sold_date")

    if source == "harcourts":
        num, name, stype = parse_harcourts_address(
            rec.get("source_id", ""),
            suburb,
            rec.get("state_code", ""),
            rec.get("postcode", ""),
        )
        return num, name, stype, suburb, sold_date

    if source == "mcgrath":
        # McGrath bundles street type into street_name ("Hersey Street")
        raw_name = (rec.get("street_name") or "").strip()
        name, stype = split_name_type(raw_name)
        num = (rec.get("street_number") or "").strip()
        return num, name, stype, suburb, sold_date

    # raywhite, ljhooker, and any future agency: separate columns
    num   = (rec.get("street_number") or "").strip()
    name  = (rec.get("street_name") or "").strip()
    stype = (rec.get("street_type") or "").strip()
    # Fall back: if no street_type, try splitting street_name
    if not stype and name:
        name, stype = split_name_type(name)
    return num, name, stype, suburb, sold_date


# ── Date helpers ────────────────────────────────────────────────────────────────

def date_delta(d1, d2):
    """Absolute day difference between two YYYY-MM-DD strings; 9999 on error."""
    try:
        return abs((datetime.strptime(d1[:10], "%Y-%m-%d") -
                    datetime.strptime(d2[:10], "%Y-%m-%d")).days)
    except Exception:
        return 9999


def completeness(rec):
    return sum(1 for f in ("bedrooms", "bathrooms", "car_spaces")
               if rec.get(f) is not None)


# ── Main ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source",   default=None,
                        help="Only match records from this source (e.g. raywhite)")
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--workers",  type=int, default=20)
    args = parser.parse_args()

    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        sys.exit(1)

    # ── 1. Load unmatched VG records ──────────────────────────────────────────
    print("Loading NSW property_sales (unmatched)...")
    vg_records = fetch_all(
        "property_sales",
        "id,street_number,street_name,suburb,sale_date",
        filters="state=eq.NSW&match_confidence=is.null",
    )
    print(f"  {len(vg_records):,} unmatched VG records")

    if not vg_records:
        print("Nothing to enrich.")
        return

    # ── 2. Build VG address index ─────────────────────────────────────────────
    # VG street_name includes type (e.g. "HERSEY STREET") → split it.
    # One VG key can have multiple records (property sold multiple times in window).
    print("\nBuilding VG address index...")
    vg_exact  = defaultdict(list)
    vg_notype = defaultdict(list)

    for rec in vg_records:
        raw   = (rec.get("street_name") or "").strip()
        name, stype = split_name_type(raw)
        snum  = (rec.get("street_number") or "").strip()
        is_unit = "/" in snum
        build = snum.split("/")[1].strip() if is_unit else snum
        sub   = rec.get("suburb", "")

        lookup_num = snum if is_unit else build

        vg_exact [make_key      (lookup_num, name, stype, sub)].append(rec)
        vg_notype[make_key_notype(lookup_num, name, sub)      ].append(rec)

        # Also index stripped lot-suffix (e.g. "14A" → also index as "14")
        if not is_unit and re.search(r'\d[A-Z]$', build.upper()):
            stripped = re.sub(r'[A-Z]$', '', build.upper())
            vg_exact [make_key      (stripped, name, stype, sub)].append(rec)
            vg_notype[make_key_notype(stripped, name, sub)      ].append(rec)

    print(f"  {len(vg_exact):,} unique exact keys | {len(vg_notype):,} no-type keys")

    # ── 3. Load unmatched sourced_sales_nsw ───────────────────────────────────
    src_filter = "match_confidence=is.null"
    if args.source:
        src_filter += f"&source=eq.{args.source}"

    label = args.source or "all sources"
    print(f"\nLoading sourced_sales_nsw ({label}, unmatched)...")
    sourced = fetch_all(
        "sourced_sales_nsw",
        "source_id,source,street_number,street_name,street_type,suburb,"
        "state_code,postcode,sold_date,bedrooms,bathrooms,car_spaces",
        filters=src_filter,
    )
    print(f"  {len(sourced):,} unmatched sourced records")

    # ── 4. Match ──────────────────────────────────────────────────────────────
    print("\nMatching sourced records against VG index...")

    # vg_pid → {"sourced": rec, "delta": int, "confidence": str}
    # Only the best sourced record per VG property_id is kept.
    vg_best     = {}
    matched     = 0
    no_match    = 0
    ambiguous   = 0
    unparseable = 0

    for src in sourced:
        num, name, stype, suburb, sold_date = normalize_sourced(src)

        if not num or not name:
            unparseable += 1
            continue

        # Handle unit addresses: if sourced has "3/12", also try building-number "12"
        is_unit = "/" in num
        build   = num.split("/")[1].strip() if is_unit else num

        # Candidate lookup (exact type → no-type fallback)
        candidates = (
            vg_exact .get(make_key      (num, name, stype, suburb)) or
            vg_notype.get(make_key_notype(num, name, suburb))
        )

        # If unit, also try building-number only
        if not candidates and is_unit:
            candidates = (
                vg_exact .get(make_key      (build, name, stype, suburb)) or
                vg_notype.get(make_key_notype(build, name, suburb))
            )

        if not candidates:
            # Try stripping trailing letter from number (e.g. "44A" → "44")
            if re.search(r'\d[A-Z]$', build.upper()):
                stripped = re.sub(r'[A-Z]$', '', build.upper())
                candidates = (
                    vg_exact .get(make_key      (stripped, name, stype, suburb)) or
                    vg_notype.get(make_key_notype(stripped, name, suburb))
                )

        if not candidates:
            no_match += 1
            continue

        # Resolve to a single VG record
        if len(candidates) == 1:
            vg = candidates[0]
            delta = date_delta(sold_date, vg.get("sale_date", "")) if sold_date else 0
        else:
            if not sold_date:
                ambiguous += 1
                continue
            vg    = min(candidates, key=lambda v: date_delta(sold_date, v.get("sale_date", "")))
            delta = date_delta(sold_date, vg.get("sale_date", ""))
            if delta > HISTORICAL_WINDOW_DAYS:
                ambiguous += 1
                continue

        if delta <= DATE_WINDOW_DAYS:
            confidence = "exact"
        else:
            confidence = "historical"

        pid = vg["id"]

        # Dedup: if this VG record already has a claim, keep the better one
        if pid in vg_best:
            existing = vg_best[pid]
            if (delta < existing["delta"] or
                    (delta == existing["delta"] and completeness(src) > completeness(existing["sourced"]))):
                vg_best[pid] = {"sourced": src, "vg": vg, "delta": delta, "confidence": confidence}
        else:
            vg_best[pid] = {"sourced": src, "vg": vg, "delta": delta, "confidence": confidence}
            matched += 1

    print(f"  Matched:     {len(vg_best):,}")
    print(f"  No match:    {no_match:,}")
    print(f"  Ambiguous:   {ambiguous:,}  (multi-candidate, no date to disambiguate)")
    print(f"  Unparseable: {unparseable:,}  (address could not be parsed)")

    by_source = defaultdict(lambda: {"exact": 0, "historical": 0})
    for pid, m in vg_best.items():
        by_source[m["sourced"].get("source", "unknown")][m["confidence"]] += 1
    print("\n  Breakdown by source:")
    for src_name, counts in sorted(by_source.items()):
        print(f"    {src_name:<15} exact={counts['exact']:,}  historical={counts['historical']:,}")

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
        return

    if not vg_best:
        print("\nNothing to write.")
        return

    # ── 5. Write to property_sales ────────────────────────────────────────────
    print(f"\nWriting {len(vg_best):,} matches to property_sales...")

    ps_calls = []
    for pid, m in vg_best.items():
        src = m["sourced"]
        payload = {
            "bedrooms":           src.get("bedrooms"),
            "bathrooms":          src.get("bathrooms"),
            "car_spaces":         src.get("car_spaces"),
            "enriched":           "yes",
            "enriched_source":    src.get("source"),
            "enriched_source_id": src["source_id"],
            "match_confidence":   m["confidence"],
        }
        url = f"{SUPABASE_URL}/rest/v1/property_sales?id=eq.{pid}"
        ps_calls.append((url, payload))

    ok = batch_patch(ps_calls, workers=args.workers)
    print(f"  {ok:,} / {len(ps_calls):,} property_sales rows updated")

    # ── 6. Write to sourced_sales_nsw ─────────────────────────────────────────
    print(f"Writing {len(vg_best):,} matches to sourced_sales_nsw...")

    src_calls = []
    for pid, m in vg_best.items():
        src = m["sourced"]
        payload = {
            "matched_property_id": pid,
            "match_confidence":    m["confidence"],
        }
        source    = src.get("source", "")
        source_id = src["source_id"]
        url = (f"{SUPABASE_URL}/rest/v1/sourced_sales_nsw"
               f"?source_id=eq.{source_id}&source=eq.{source}")
        src_calls.append((url, payload))

    ok = batch_patch(src_calls, workers=args.workers)
    print(f"  {ok:,} / {len(src_calls):,} sourced_sales_nsw rows updated")

    print(f"\n{'='*60}")
    print(f"ENRICHMENT COMPLETE")
    print(f"{'='*60}")
    exact_total      = sum(1 for m in vg_best.values() if m["confidence"] == "exact")
    historical_total = sum(1 for m in vg_best.values() if m["confidence"] == "historical")
    print(f"Exact matches:     {exact_total:,}")
    print(f"Historical:        {historical_total:,}")
    print(f"No match:          {no_match:,}")
    print(f"Ambiguous:         {ambiguous:,}")
    print(f"Unparseable:       {unparseable:,}")
    print()


if __name__ == "__main__":
    main()
