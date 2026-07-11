"""
load_domain_suburbs.py
======================
Fetches suburb performance data from Domain.com.au public suburb profile pages
and uploads to the suburb_stats table in Supabase.

Domain publishes bedroom-level median prices, annual sales counts, and
surrounding suburbs for every Australian suburb — for free, no API key needed.

This script replaces the static VIC suburb-data.json approach and adds QLD
(and any other state) with the same bedroom-level data quality.

PREREQUISITES
─────────────
pip3 install playwright beautifulsoup4 requests
python3 -m playwright install chromium

USAGE
─────
export SUPABASE_SECRET=your_secret_key_here

# Fetch QLD suburbs:
python3 load_domain_suburbs.py --state QLD

# Fetch VIC suburbs:
python3 load_domain_suburbs.py --state VIC

# Fetch multiple states:
python3 load_domain_suburbs.py --state QLD VIC

# Dry run (fetch + parse, no upload):
python3 load_domain_suburbs.py --state QLD --dry-run

# Resume from a specific suburb (after a crash):
python3 load_domain_suburbs.py --state QLD --resume-from "mackay"

OPTIONS
───────
  --state         State code(s) to process: QLD VIC SA WA TAS ACT NT
  --dry-run       Parse and print results without uploading
  --delay         Seconds between requests (default: 1.5)
  --resume-from   Suburb name to resume from (skips alphabetically prior suburbs)
  --postcodes     Path to postcodes CSV (default: downloads from GitHub)
  --min-sales     Skip rows where annual_sales < this (default: 3)

POSTCODE SOURCE
───────────────
Downloads from: https://raw.githubusercontent.com/matthewproctor/australianpostcodes/master/australian_postcodes.csv
Columns expected: postcode, locality, state, lat, long, dc, type, status

If the download fails, provide a local CSV with: postcode, locality, state
"""

import argparse
import csv
import io
import json
import os
import re
import time
from collections import defaultdict

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─────────────────────────────────────────────────────────────────────────────

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

POSTCODES_URL = (
    "https://raw.githubusercontent.com/matthewproctor/"
    "australianpostcodes/master/australian_postcodes.csv"
)

DOMAIN_BASE = "https://www.domain.com.au/suburb-profile"

# ─────────────────────────────────────────────────────────────────────────────


def load_postcodes(csv_path=None):
    """Return list of {suburb, state, postcode} dicts from CSV."""
    if csv_path and os.path.exists(csv_path):
        print(f"Loading postcodes from {csv_path} ...")
        with open(csv_path, encoding="utf-8") as f:
            content = f.read()
    else:
        print(f"Downloading postcode list from GitHub ...")
        resp = requests.get(POSTCODES_URL, timeout=30)
        resp.raise_for_status()
        content = resp.text

    reader = csv.DictReader(io.StringIO(content))
    rows = []
    seen = set()

    # Skip obviously non-residential locality suffixes
    SKIP_SUFFIXES = (
        " MC", " BC", " DC",           # mail/distribution centres
        " LPO", " GPO",                # post offices
        " MILPO", " BARRACKS",         # military
        " UNIVERSITY", " TAFE",        # education campuses
        " HOSPITAL", " AIRPORT",       # infrastructure
    )

    for row in reader:
        # Handle different column naming conventions
        suburb   = (row.get("locality") or row.get("suburb") or "").strip().upper()
        state    = (row.get("state") or "").strip().upper()
        postcode = str(row.get("postcode") or "").strip().split(".")[0]

        if not suburb or not state or not postcode:
            continue

        # Skip PO boxes and non-delivery types (column name varies by dataset)
        row_type = (row.get("type") or row.get("category") or "").strip().upper()
        if row_type in ("PO BOX", "GPO BOX", "LOCKED BAG", "POST OFFICE"):
            continue

        # Skip postcodes >= 9000 (Australia Post internal use / mail centres)
        try:
            if int(postcode) >= 9000:
                continue
        except ValueError:
            continue

        # Skip non-residential suffixes
        if any(suburb.endswith(sfx) for sfx in SKIP_SUFFIXES):
            continue

        key = (suburb, state, postcode)
        if key not in seen:
            seen.add(key)
            rows.append({"suburb": suburb, "state": state, "postcode": postcode})

    print(f"  Loaded {len(rows):,} suburb/postcode combinations")
    return rows


def suburb_to_slug(suburb):
    """'New Farm' → 'new-farm', 'St Lucia' → 'st-lucia'"""
    return re.sub(r'[^a-z0-9]+', '-', suburb.lower()).strip('-')


def parse_price(price_str):
    """'$1.45m' → 1450000, '$867.1k' → 867100, '$2.4m' → 2400000"""
    if not price_str or price_str.strip() in ('-', 'N/A', ''):
        return None
    s = price_str.strip().lower().replace('$', '').replace(',', '')
    try:
        if s.endswith('m'):
            return int(float(s[:-1]) * 1_000_000)
        elif s.endswith('k'):
            return int(float(s[:-1]) * 1_000)
        else:
            return int(float(s))
    except (ValueError, TypeError):
        return None


def parse_int(val):
    """'63' → 63, '-' → None"""
    if not val or val.strip() in ('-', 'N/A', ''):
        return None
    try:
        return int(val.strip().replace(',', ''))
    except (ValueError, TypeError):
        return None


def fetch_suburb(suburb, state, postcode, page):
    """
    Fetch Domain suburb profile page using a Playwright browser page and extract:
    - rows: [{property_type, bedrooms, median_price, annual_sales}, ...]
    - nearby: [suburb_name, ...]
    Returns (rows, nearby) or (None, None) on failure.
    """
    slug    = suburb_to_slug(suburb)
    state_l = state.lower()
    url     = f"{DOMAIN_BASE}/{slug}-{state_l}-{postcode}"

    try:
        response = page.goto(url, timeout=20000, wait_until="domcontentloaded")
        if response and response.status == 404:
            return None, None
        if response and response.status not in (200, 304):
            print(f"    HTTP {response.status}")
            return None, None
        # Wait for the market trends table to appear
        try:
            page.wait_for_selector("table", timeout=8000)
        except PWTimeout:
            return None, None
    except PWTimeout:
        print("    timeout")
        return None, None
    except Exception as e:
        print(f"    error: {e}")
        return None, None

    html = page.content()
    soup = BeautifulSoup(html, "html.parser")

    # ── Parse market trends table ─────────────────────────────────────────
    rows = []

    # Find the table containing "Median price" in its headers
    target_table = None
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any("median" in h for h in headers) and any("type" in h for h in headers):
            target_table = table
            break

    if target_table:
        # Map header positions
        ths = [th.get_text(strip=True).lower() for th in target_table.find_all("th")]
        def col(name):
            for i, h in enumerate(ths):
                if name in h:
                    return i
            return None

        idx_beds    = col("bed")
        idx_type    = col("type")
        idx_median  = col("median")
        idx_sold    = col("sold")

        for tr in target_table.find_all("tr")[1:]:  # skip header
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if not tds or len(tds) < 3:
                continue

            bedrooms     = parse_int(tds[idx_beds])   if idx_beds   is not None else None
            prop_type    = tds[idx_type].lower()       if idx_type   is not None else None
            median_price = parse_price(tds[idx_median]) if idx_median is not None else None
            annual_sales = parse_int(tds[idx_sold])   if idx_sold   is not None else None

            # Normalise property type
            if prop_type:
                if "house" in prop_type:
                    prop_type = "house"
                elif "unit" in prop_type or "apartment" in prop_type or "flat" in prop_type:
                    prop_type = "apartment"
                elif "town" in prop_type:
                    prop_type = "townhouse"

            if median_price and prop_type:
                rows.append({
                    "bedrooms":     bedrooms,
                    "property_type": prop_type,
                    "median_price": median_price,
                    "annual_sales": annual_sales,
                })

    # ── Parse surrounding suburbs ─────────────────────────────────────────
    nearby = []
    for heading in soup.find_all(["h3", "h4", "h5", "strong"]):
        if "surrounding" in heading.get_text(strip=True).lower():
            parent = heading.find_parent()
            if parent:
                for link in parent.find_all("a", href=True):
                    text = link.get_text(strip=True)
                    if text and len(text) > 1:
                        nearby.append(text.lower())
            break

    return rows or None, nearby


def upload_batch(records, dry_run=False):
    """Upload a list of suburb_stats rows to Supabase."""
    if dry_run:
        return True
    if not SUPABASE_SECRET:
        print("  SKIP upload: SUPABASE_SECRET not set")
        return False

    url = f"{SUPABASE_URL}/rest/v1/suburb_stats"
    headers = {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }
    resp = requests.post(url, headers=headers, json=records, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  Upload error {resp.status_code}: {resp.text[:200]}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state",       nargs="+", default=["QLD"],
                        help="State code(s): QLD VIC SA WA etc.")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--delay",       type=float, default=1.5,
                        help="Seconds between requests")
    parser.add_argument("--resume-from", default=None,
                        help="Suburb name to resume from")
    parser.add_argument("--postcodes",   default=None,
                        help="Path to local postcodes CSV")
    parser.add_argument("--min-sales",   type=int, default=3,
                        help="Skip rows with fewer annual sales than this")
    args = parser.parse_args()

    states = [s.upper() for s in args.state]
    print(f"States: {states}")
    print(f"Dry run: {args.dry_run}")
    print()

    # Load postcode list
    all_postcodes = load_postcodes(args.postcodes)
    suburbs = [r for r in all_postcodes if r["state"] in states]
    suburbs.sort(key=lambda r: (r["state"], r["suburb"]))
    print(f"Suburbs to process: {len(suburbs):,}\n")

    # Resume support
    if args.resume_from:
        resume = args.resume_from.upper()
        idx = next((i for i, r in enumerate(suburbs) if r["suburb"] >= resume), 0)
        suburbs = suburbs[idx:]
        print(f"Resuming from {suburbs[0]['suburb']} ({len(suburbs):,} remaining)\n")

    total_ok      = 0
    total_skipped = 0
    total_rows    = 0
    upload_buffer = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            locale="en-AU",
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # Warm up — visit listing page to pick up cookies
        print("Warming up browser (visiting domain.com.au) ...")
        page.goto("https://www.domain.com.au/suburb-profile/", wait_until="domcontentloaded")
        print("  Ready.\n")
        time.sleep(2)

        for i, sub in enumerate(suburbs, 1):
            suburb   = sub["suburb"]
            state    = sub["state"]
            postcode = sub["postcode"]

            print(f"[{i}/{len(suburbs)}] {suburb}, {state} {postcode} ...", end=" ", flush=True)

            rows, nearby = fetch_suburb(suburb, state, postcode, page)

            if not rows:
                print("no data")
                total_skipped += 1
                time.sleep(args.delay)
                continue

            # Filter thin rows
            rows = [r for r in rows if r["annual_sales"] is None
                    or r["annual_sales"] >= args.min_sales]

            if not rows:
                print("filtered (low sales)")
                total_skipped += 1
                time.sleep(args.delay)
                continue

            print(f"{len(rows)} rows, nearby: {nearby[:3]}")

            # Build Supabase records
            nearby_json = json.dumps(nearby) if nearby else None
            for row in rows:
                upload_buffer.append({
                    "suburb":        suburb.lower(),
                    "state":         state,
                    "postcode":      postcode,
                    "property_type": row["property_type"],
                    "bedrooms":      row["bedrooms"],
                    "median_price":  row["median_price"],
                    "annual_sales":  row["annual_sales"],
                    "nearby_suburbs": nearby_json,
                    "source":        "domain",
                })

            total_ok    += 1
            total_rows  += len(rows)

            # Upload in batches of 100
            if len(upload_buffer) >= 100:
                ok = upload_batch(upload_buffer, dry_run=args.dry_run)
                if ok and not args.dry_run:
                    print(f"  → Uploaded batch of {len(upload_buffer)}")
                upload_buffer = []

            time.sleep(args.delay)

    # Upload remaining
    if upload_buffer:
        upload_batch(upload_buffer, dry_run=args.dry_run)
        if not args.dry_run:
            print(f"  → Uploaded final batch of {len(upload_buffer)}")

    print(f"\n{'─'*50}")
    print(f"Done.")
    print(f"  Suburbs with data:  {total_ok:,}")
    print(f"  Suburbs skipped:    {total_skipped:,}")
    print(f"  Total rows written: {total_rows:,}")
    if args.dry_run:
        print("  [DRY RUN — nothing uploaded]")


if __name__ == "__main__":
    main()
