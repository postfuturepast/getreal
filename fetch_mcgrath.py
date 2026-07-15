#!/usr/bin/env python3
"""
fetch_mcgrath.py — Harvest McGrath sold listings from mcgrath.com.au

Approach:
  1. Crawl all 8 sold-property sitemap pages → ~5,500 property URLs
  2. For each URL, fetch the page (server-side rendered — no JS needed)
  3. Parse title tag → full address (street, suburb, state, postcode)
  4. Parse page text → beds / bath / cars / sold price / sold date
  5. Upsert to sourced_sales_{state} in Supabase

Proxy note:
  Clears http(s)_proxy env vars within this process only.
  The corporate proxy (localhost:3128) doesn't exist on home networks —
  keeping it set just causes connection failures. Your shell profile is untouched.

Usage:
  export SUPABASE_SECRET=your_secret_key
  python3 fetch_mcgrath.py

SQL for tables not yet created (run once in Supabase SQL editor):
  CREATE TABLE IF NOT EXISTS sourced_sales_qld (LIKE sourced_sales_nsw INCLUDING ALL);
  CREATE TABLE IF NOT EXISTS sourced_sales_sa  (LIKE sourced_sales_nsw INCLUDING ALL);
  CREATE TABLE IF NOT EXISTS sourced_sales_wa  (LIKE sourced_sales_nsw INCLUDING ALL);
  CREATE TABLE IF NOT EXISTS sourced_sales_tas (LIKE sourced_sales_nsw INCLUDING ALL);
  CREATE TABLE IF NOT EXISTS sourced_sales_act (LIKE sourced_sales_nsw INCLUDING ALL);
  CREATE TABLE IF NOT EXISTS sourced_sales_nt  (LIKE sourced_sales_nsw INCLUDING ALL);
"""

import os
import re
import sys
import time
import json
import subprocess
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
from datetime import datetime, date

# ── Clear corporate proxy within this process (safe: does not touch shell profile) ──
for _k in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
    os.environ.pop(_k, None)

# ── Config ───────────────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET", "")

SITEMAP_BASE   = "https://www.mcgrath.com.au/sitemap/properties-sold-page-{n}.xml"
NUM_SITEMAPS   = 8
BATCH_SIZE     = 50
REQUEST_DELAY  = 0.5   # seconds between fetches per worker
NUM_WORKERS    = 3     # concurrent fetch threads
PROGRESS_FILE  = "mcgrath_progress.txt"  # resume checkpoint

STATE_TABLES = {
    "nsw": "sourced_sales_nsw",
    "vic": "sourced_sales_vic",
    "qld": "sourced_sales_qld",
    "sa":  "sourced_sales_sa",
    "wa":  "sourced_sales_wa",
    "tas": "sourced_sales_tas",
    "act": "sourced_sales_act",
    "nt":  "sourced_sales_nt",
}

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

_thread_local = threading.local()

def get_session():
    """One curl_cffi session per thread."""
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = cffi_requests.Session(impersonate="chrome120")
    return _thread_local.session


# ── Step 1: Collect all sold property URLs ────────────────────────────────────────────

def fetch_sitemap_page_text(n):
    """Fetch sitemap page n — tries local cache first, then curl, then requests."""
    cache_file = f".mcgrath_sitemap_{n}.xml"

    # 1. Local cache
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return f.read()

    url = SITEMAP_BASE.format(n=n)

    # 2. curl (different UA / connection handling, avoids session rate-limit)
    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "30",
             "-H", "User-Agent: Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
             url],
            capture_output=True, text=True, timeout=35
        )
        if result.returncode == 0 and "<loc>" in result.stdout:
            with open(cache_file, "w") as f:
                f.write(result.stdout)
            return result.stdout
    except Exception:
        pass

    # 3. curl_cffi fallback
    try:
        r = get_session().get(url, timeout=30)
        r.raise_for_status()
        with open(cache_file, "w") as f:
            f.write(r.text)
        return r.text
    except Exception as e:
        print(f"ERROR: {e}")
        return ""


def fetch_sitemap_urls():
    # Prefer pre-fetched URL seed file (generated via browser console JS snippet)
    seed_file = "mcgrath_urls.json"
    if os.path.exists(seed_file):
        with open(seed_file) as f:
            urls = json.load(f)
        print(f"Loaded {len(urls)} URLs from {seed_file}")
        return urls

    urls = []
    for n in range(1, NUM_SITEMAPS + 1):
        print(f"Sitemap page {n}/{NUM_SITEMAPS} ... ", end="", flush=True)
        text = fetch_sitemap_page_text(n)
        found = re.findall(r'https://www\.mcgrath\.com\.au/property/[^\s<]+', text)
        urls.extend(found)
        print(f"{len(found)} URLs (running total: {len(urls)})")
        time.sleep(2)
    return urls


def state_from_slug(url: str):
    """Quick state extraction from URL slug — avoids fetching the page first."""
    slug = url.split('/property/')[-1]
    m = re.search(r'-(nsw|vic|qld|sa|wa|act|tas|nt)-\d{4}-', slug, re.IGNORECASE)
    return m.group(1).lower() if m else None


def property_id_from_slug(url: str):
    slug = url.split('/property/')[-1]
    # ID is the last hyphen-separated token, e.g. 136P3112, G682671, 22P1229368
    m = re.search(r'-([A-Za-z]?\d*[Pp]\d+|[Gg]\d+)$', slug)
    return m.group(1).upper() if m else slug.split('-')[-1].upper()


# ── Step 2: Parse a property page ────────────────────────────────────────────────────

def parse_address_from_title(soup):
    """
    Page title: '40 Hersey Street, Blaxland, NSW 2774 | McGrath Estate Agents'
    Handles units: '6/171 Derby Street, Penrith, NSW 2750 | ...'
    """
    title_tag = soup.find('title')
    if not title_tag:
        return None
    raw = title_tag.get_text(strip=True).split('|')[0].strip()

    # Match: <street_part>, <suburb>, <STATE> <postcode>
    m = re.match(
        r'^(.+?),\s+(.+?),\s+([A-Z]{2,3})\s+(\d{4})$',
        raw
    )
    if not m:
        return None

    street_part = m.group(1).strip()   # e.g. "40 Hersey Street" or "6/171 Derby Street"
    suburb      = m.group(2).strip().upper()
    state       = m.group(3).lower()
    postcode    = m.group(4)

    # Split street into number + name
    sm = re.match(r'^(\S+)\s+(.+)$', street_part)
    if not sm:
        return None

    street_number = sm.group(1)   # "40", "6/171", "Lot 1302" (with space already handled)
    street_name   = sm.group(2)   # "Hersey Street"

    # Detect lot (land) — skip these
    if street_number.lower() == 'lot' or street_part.lower().startswith('lot '):
        return None

    return {
        "street_number": street_number,
        "street_name":   street_name,
        "suburb":        suburb,
        "state":         state,
        "postcode":      postcode,
    }


def parse_attributes(text: str):
    """
    Extract beds, baths, cars, sold_price, sold_date from page text.
    Returns (beds, baths, cars, sold_price, sold_date).
    """
    # Beds / Bath / Cars appear as "N\n...\nBeds" etc.
    def find_count(label):
        # Try with surrounding whitespace/newlines
        m = re.search(rf'(\d+)\s*\n\s*{label}', text)
        if m:
            return int(m.group(1))
        # Try inline "3 Beds"
        m = re.search(rf'(\d+)\s+{label}', text)
        return int(m.group(1)) if m else None

    beds  = find_count('Beds')
    baths = find_count('Bath')
    cars  = find_count('Cars')

    # Sold price: "$1,060,000" — take first dollar amount after "Sold"
    price = None
    sold_block = re.search(r'Sold[^\n]*\n+([\s\S]{0,200})', text)
    if sold_block:
        pm = re.search(r'\$([\d,]+)', sold_block.group(1))
        if pm:
            price = int(pm.group(1).replace(',', ''))
    # Fallback: first dollar amount anywhere
    if price is None:
        pm = re.search(r'\$([\d,]+)', text)
        if pm:
            price = int(pm.group(1).replace(',', ''))

    # Sold date: "Sold July 2026"
    sold_date = None
    dm = re.search(
        r'Sold\s+(January|February|March|April|May|June|July|August|'
        r'September|October|November|December)\s+(\d{4})',
        text, re.IGNORECASE
    )
    if dm:
        month_num = MONTH_MAP[dm.group(1).lower()]
        year      = int(dm.group(2))
        sold_date = date(year, month_num, 1).isoformat()

    return beds, baths, cars, price, sold_date


def fetch_property(url: str):
    """Fetch one property page and return a fully parsed dict, or None to skip."""
    time.sleep(REQUEST_DELAY)
    for attempt in range(4):
        try:
            r = get_session().get(url, timeout=30)
            if r.status_code == 429:
                wait = 30 * (2 ** attempt)
                print(f"    429 rate limited — waiting {wait}s", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            break
        except Exception as e:
            print(f"    FETCH ERROR {url}: {e}", flush=True)
            return None
    else:
        print(f"    Giving up after retries: {url}", flush=True)
        return None

    soup = BeautifulSoup(r.text, 'html.parser')
    addr = parse_address_from_title(soup)
    if not addr:
        return None   # lot, parse failure, etc.

    text = soup.get_text(separator='\n')
    beds, baths, cars, price, sold_date = parse_attributes(text)

    if not price:
        return None   # no sold price visible — skip

    # Determine coarse property type from street number
    property_type = "apartment" if '/' in addr['street_number'] else "house"

    return {
        "source":              "mcgrath",
        "source_id":           property_id_from_slug(url),
        "sourced_at":          datetime.utcnow().isoformat(),
        "street_number":       addr['street_number'],
        "street_name":         addr['street_name'],
        "suburb":              addr['suburb'],
        "state_code":          addr['state'].upper(),
        "postcode":            addr['postcode'],
        "bedrooms":            beds,
        "bathrooms":           baths,
        "car_spaces":          cars,
        "sold_price":          price,
        "sold_date":           sold_date,
        "property_type_code":  property_type,
        "_state":              addr['state'],   # internal routing key, stripped before upsert
    }


# ── Step 3: Upsert to Supabase ────────────────────────────────────────────────────────

def upsert_batch(table: str, rows: list) -> int:
    """Upsert rows to a Supabase table. Returns count upserted."""
    if not rows:
        return 0
    # Strip internal routing keys
    clean = [{k: v for k, v in row.items() if not k.startswith('_')} for row in rows]
    endpoint = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=source,source_id"
    headers = {
        "apikey":        SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=representation",
    }
    for attempt in range(3):
        try:
            r = requests.post(endpoint, json=clean, headers=headers, timeout=30)
            if r.status_code in (200, 201):
                return len(clean)
            print(f"    Upsert {table} HTTP {r.status_code}: {r.text[:200]}", flush=True)
        except Exception as e:
            print(f"    Upsert exception: {e}", flush=True)
        time.sleep(2 ** attempt)
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────────────

def load_progress():
    """Load set of already-processed property IDs from checkpoint file."""
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE) as f:
        return set(line.strip() for line in f if line.strip())

def save_progress(done_ids):
    with open(PROGRESS_FILE, 'w') as f:
        f.write('\n'.join(done_ids))


def main():
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SECRET not set.\nRun: export SUPABASE_SECRET=your_secret")
        sys.exit(1)

    print("=" * 60)
    print("fetch_mcgrath.py")
    print("=" * 60)

    # Resume: load already-processed IDs
    done_ids = load_progress()
    if done_ids:
        print(f"Resuming — {len(done_ids)} already done, skipping those.\n")

    # Collect all URLs
    all_urls = fetch_sitemap_urls()

    # Filter to known states, skip already done
    flat_urls = []
    skipped_state = 0
    skipped_done = 0
    for url in all_urls:
        state = state_from_slug(url)
        if not state or state not in STATE_TABLES:
            skipped_state += 1
            continue
        pid = property_id_from_slug(url)
        if pid in done_ids:
            skipped_done += 1
            continue
        flat_urls.append((state, url))

    urls_by_state = {}
    for state, url in flat_urls:
        urls_by_state.setdefault(state, 0)
        urls_by_state[state] += 1

    print(f"\nTotal to fetch: {len(flat_urls)} (skipped {skipped_done} already done, {skipped_state} unknown state)")
    print(f"By state: {urls_by_state}\n")

    # Shared state (protected by lock)
    lock = threading.Lock()
    pending = {}
    total_ok = 0
    total_skip = 0
    total_upserted = 0
    processed = 0
    start = time.time()

    def process_url(args):
        state, url = args
        row = fetch_property(url)
        return state, url, row

    with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = {executor.submit(process_url, item): item for item in flat_urls}
        for future in as_completed(futures):
            state, url, row = future.result()
            with lock:
                processed += 1
                if row:
                    total_ok += 1
                    pid = property_id_from_slug(url)
                    done_ids.add(pid)
                    pending.setdefault(state, []).append(row)

                    # Flush batch
                    if len(pending[state]) >= BATCH_SIZE:
                        batch = pending.pop(state)
                        n = upsert_batch(STATE_TABLES[state], batch)
                        total_upserted += n
                        save_progress(done_ids)
                        print(f"  Upserted {n} → {STATE_TABLES[state]} (total: {total_upserted})", flush=True)
                else:
                    total_skip += 1

                if processed % 100 == 0:
                    elapsed = time.time() - start
                    rate = processed / elapsed
                    remaining = (len(flat_urls) - processed) / rate
                    print(
                        f"[{processed}/{len(flat_urls)}] "
                        f"{total_ok} ok / {total_skip} skipped / {total_upserted} upserted "
                        f"— {remaining/60:.1f} min remaining",
                        flush=True
                    )

    # Flush remaining
    with lock:
        for state, rows in pending.items():
            if rows:
                n = upsert_batch(STATE_TABLES[state], rows)
                total_upserted += n
                print(f"  Final flush {n} → {STATE_TABLES[state]}")
        save_progress(done_ids)

    print("\n" + "=" * 60)
    print(f"Done. {total_ok} fetched, {total_skip} skipped, {total_upserted} upserted.")
    print(f"Elapsed: {(time.time() - start)/60:.1f} min")


if __name__ == "__main__":
    main()
