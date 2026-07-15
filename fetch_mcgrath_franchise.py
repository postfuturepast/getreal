"""
fetch_mcgrath_franchise.py — McGrath franchise WordPress/EPL scraper
=====================================================================
Scrapes sold property listings from McGrath franchise offices that run
WordPress + Easy Property Listings (EPL) plugin. These sites serve
server-rendered HTML — no JavaScript execution needed.

Key advantage over Ray White: EPL captures unit-level addresses
(e.g. "2/17 Wood Crescent"), solving the apartment matching gap.

Sites covered:
    NSW: mcgrathnr, mcgrathwnwhh, mcgrathillawarra, mcgrathcw, mcgrathlbm
    QLD: mcgrathch, mcgrathsc, mcgrathmb
    TAS: mcgrathhl

Records upserted to sourced_sales_{state} in Supabase.
Unique constraint on (source, source_id) — safe to re-run.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 fetch_mcgrath_franchise.py [--domain mcgrathnr.com.au]

    Optionally pass a single domain to scrape just that site.

Output:
    - Supabase: sourced_sales_nsw / sourced_sales_qld / sourced_sales_tas
    - Local: mcgrath_franchise_listings.ndjson (append mode, resume-safe)

Required tables (run once if not yet created):
    CREATE TABLE sourced_sales_qld (LIKE sourced_sales_nsw INCLUDING ALL);
    ALTER TABLE sourced_sales_qld ADD CONSTRAINT sourced_sales_qld_source_source_id_key UNIQUE (source, source_id);
    GRANT SELECT, INSERT, UPDATE ON sourced_sales_qld TO service_role;
    GRANT USAGE, SELECT ON SEQUENCE sourced_sales_qld_id_seq TO service_role;
    -- repeat for sourced_sales_tas
"""

import os
import re
import sys
import time
import json
import logging
import requests
from datetime import datetime
from urllib.parse import urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: pip install beautifulsoup4")
    sys.exit(1)

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

OUTPUT_FILE = "mcgrath_franchise_listings.ndjson"
DELAY       = 1.5    # seconds between page requests (be polite)
SITE_DELAY  = 3.0    # seconds between sites
BATCH_SIZE  = 100    # Supabase upsert batch size

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

# All confirmed McGrath WordPress/EPL franchise sites.
# Add new entries here as more franchise sites are discovered.
FRANCHISE_SITES = [
    # ── NSW ──────────────────────────────────────────────────────────────────
    {
        "domain": "mcgrathnr.com.au",
        "source": "mcgrath_northern_rivers",
        "state":  "nsw",
        "note":   "Ballina, Byron Bay, Lennox Head, Alstonville",
    },
    {
        "domain": "mcgrathwnwhh.com.au",
        "source": "mcgrath_west_hills",
        "state":  "nsw",
        "note":   "Parramatta, Blacktown, Castle Hill, Kellyville, Epping",
    },
    {
        "domain": "mcgrathillawarra.com.au",
        "source": "mcgrath_illawarra",
        "state":  "nsw",
        "note":   "Wollongong region",
    },
    {
        "domain": "mcgrathcw.com.au",
        "source": "mcgrath_central_west",
        "state":  "nsw",
        "note":   "Orange, Bathurst",
    },
    {
        "domain": "mcgrathlbm.com.au",
        "source": "mcgrath_lower_blue_mtns",
        "state":  "nsw",
        "note":   "Lower Blue Mountains",
    },
    # ── QLD ──────────────────────────────────────────────────────────────────
    {
        "domain": "mcgrathch.com.au",
        "source": "mcgrath_coast_hinterland",
        "state":  "qld",
        "note":   "Caloundra, Beerwah, Glass House Mountains",
    },
    {
        "domain": "mcgrathsc.com.au",
        "source": "mcgrath_sunshine_coast",
        "state":  "qld",
        "note":   "Sunshine Coast",
    },
    {
        "domain": "mcgrathmb.com.au",
        "source": "mcgrath_north_lakes",
        "state":  "qld",
        "note":   "North Lakes, Moreton Bay",
    },
    # ── TAS ──────────────────────────────────────────────────────────────────
    {
        "domain": "mcgrathhl.com.au",
        "source": "mcgrath_launceston",
        "state":  "tas",
        "note":   "Launceston to Hobart",
    },
]

# ── Address parsing ───────────────────────────────────────────────────────────

STREET_TYPES = {
    "road", "rd", "street", "st", "avenue", "ave", "drive", "dr",
    "place", "pl", "way", "close", "cl", "court", "ct", "crescent",
    "cres", "lane", "ln", "highway", "hwy", "boulevard", "blvd",
    "circuit", "cct", "parade", "pde", "terrace", "tce", "grove",
    "gr", "rise", "vale", "hill", "point", "track", "trail",
    "access", "loop", "pass", "row", "walk", "esplanade", "esp",
    "parkway", "pkwy", "vista", "link", "mews", "gardens", "grange",
    "views", "outlook", "haven", "bay", "beach", "ridge", "creek",
    "falls", "park", "green", "square", "plaza", "promenade", "quay",
    "run", "ramble", "approach", "bypass", "chase", "end", "entry",
    "gate", "glade", "hollow", "junction", "key", "lookout", "manor",
    "nook", "path", "reach", "retreat", "return", "service", "side",
    "slope", "spur", "steps", "summit", "turn",
}

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def parse_sold_date(text):
    """Parse 'Sold on 14 Jul 2026' or '14 Jul 2026' → '2026-07-14'."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})", text)
    if m:
        day, mon, year = m.groups()
        month = MONTHS.get(mon.lower())
        if month:
            return f"{year}-{month:02d}-{int(day):02d}"
    return None


def parse_price(text):
    """Parse 'Sold $1,300,000' → 1300000. Returns None if no dollar amount."""
    m = re.search(r"\$([\d,]+)", text)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


def parse_address(raw):
    """
    Parse EPL address like:
        '7 Bannockburn Court Cumbalum NSW 2478'
        '2/17 Wood Crescent Baringa QLD 4551'
        '44/99 Birtinya Boulevard Birtinya QLD 4575'
        '51/40 Applegum Crescent North Kellyville NSW 2155'
        'Lot 2/2643 Old Gympie Road Beerwah QLD 4519'

    Returns dict with: street_number, street_name, suburb, state_code, postcode
    """
    raw = raw.strip()

    # Must end with STATE POSTCODE (2-3 uppercase letters, 4 digits)
    m = re.match(r"^(.+?)\s+([A-Z]{2,3})\s+(\d{4})$", raw)
    if not m:
        return None

    body, state, postcode = m.groups()
    parts = body.split()

    if len(parts) < 3:
        return None

    # Find the last word that is a known street type
    street_end = None
    for i in range(len(parts) - 1, 0, -1):
        if parts[i].lower().rstrip(".") in STREET_TYPES:
            street_end = i
            break

    if street_end is not None and street_end < len(parts) - 1:
        street = " ".join(parts[: street_end + 1])
        suburb = " ".join(parts[street_end + 1 :])
    else:
        # Fallback: last word is suburb
        suburb = parts[-1]
        street = " ".join(parts[:-1])

    # Split street into number + name
    # Street numbers: "7", "2/17", "44/99", "13B", "Lot 2/2643", "175B"
    street_parts = street.split(" ", 1)
    street_number = street_parts[0]

    # Absorb "Lot N/M" style
    if street_number.lower() == "lot" and len(street_parts) > 1:
        rest = street_parts[1].split(" ", 1)
        street_number = "Lot " + rest[0]
        street_name = rest[1] if len(rest) > 1 else ""
    else:
        street_name = street_parts[1] if len(street_parts) > 1 else ""

    return {
        "street_number": street_number,
        "street_name":   street_name,
        "suburb":        suburb,
        "state_code":    state,
        "postcode":      postcode,
    }


# ── EPL HTML parsing ──────────────────────────────────────────────────────────

def extract_feature_count(article, feature_keyword):
    """
    Extract a numeric count for a bed/bath/car feature from an EPL article.
    Tries multiple class patterns used by different EPL theme configurations.
    """
    # Pattern 1: <div/li class="...bed..."><span>3</span>
    candidates = article.find_all(
        class_=lambda c: c and feature_keyword in " ".join(c).lower()
    )
    for el in candidates:
        # Avoid grabbing the label text; find the numeric span
        nums = re.findall(r"\b(\d+)\b", el.get_text(" "))
        if nums:
            val = int(nums[0])
            # Sanity: beds/baths/cars should be 0-20 range
            if 0 < val <= 20:
                return val

    # Pattern 2: look for data-epl-* attributes
    el = article.find(attrs={"data-epl-" + feature_keyword: True})
    if el:
        nums = re.findall(r"\b(\d+)\b", el.get_text())
        if nums:
            return int(nums[0])

    return None


def parse_article(article, domain):
    """
    Parse a single EPL property card (<article> element).
    Returns a dict of fields, or None if the card lacks an address.
    """
    # ── Address ───────────────────────────────────────────────────────────────
    h3 = article.find("h3")
    if not h3:
        return None

    link_el = h3.find("a")
    address_raw = (link_el or h3).get_text(separator=" ", strip=True)
    address_raw = re.sub(r"\s+", " ", address_raw)  # normalise any double spaces
    if not address_raw:
        return None

    # source_id: URL path slug, unique within this domain
    source_url = ""
    source_id = address_raw  # fallback
    if link_el and link_el.get("href"):
        source_url = link_el["href"]
        parsed = urlparse(source_url)
        source_id = parsed.path.strip("/")  # e.g. "property/7-bannockburn-court-..."

    addr = parse_address(address_raw)
    if not addr:
        log.debug(f"Could not parse address: {address_raw!r}")
        return None

    # ── Price ─────────────────────────────────────────────────────────────────
    sold_price = None
    # EPL sticker price (on image overlay or summary)
    for class_hint in ["price", "sticker"]:
        price_el = article.find(
            class_=lambda c: c and class_hint in " ".join(c).lower() if c else False
        )
        if price_el:
            sold_price = parse_price(price_el.get_text())
            if sold_price:
                break

    # Fallback: scan full article text for "$NNN,NNN"
    if sold_price is None:
        sold_price = parse_price(article.get_text(" "))

    # ── Beds / Baths / Cars ───────────────────────────────────────────────────
    bedrooms  = extract_feature_count(article, "bed")
    bathrooms = extract_feature_count(article, "bath")
    car_spaces = extract_feature_count(article, "car")

    # ── Sold date ─────────────────────────────────────────────────────────────
    sold_date = None
    # Look for EPL date element
    date_el = article.find(
        class_=lambda c: c and "date" in " ".join(c).lower() if c else False
    )
    if date_el:
        sold_date = parse_sold_date(date_el.get_text())

    # Fallback: scan article text for "Sold on DD Mon YYYY"
    if not sold_date:
        m = re.search(r"Sold on\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", article.get_text())
        if m:
            sold_date = parse_sold_date(m.group())

    return {
        "source_id":     source_id,
        "source_url":    source_url,
        "address":       address_raw,
        "street_number": addr["street_number"],
        "street_name":   addr["street_name"],
        "suburb":        addr["suburb"],
        "state_code":    addr["state_code"],
        "postcode":      addr["postcode"],
        "sold_price":    sold_price,
        "bedrooms":      bedrooms,
        "bathrooms":     bathrooms,
        "car_spaces":    car_spaces,
        "sold_date":     sold_date,
    }


def scrape_page(url, domain):
    """
    Fetch one /sold/page/N/ page and extract all property listings.
    Returns:
        list of dicts  — on success (may be empty if page has no listings)
        None           — on HTTP 404 (signals end of pagination)
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        log.warning(f"Request failed {url}: {e}")
        return []

    if r.status_code == 404:
        return None  # End of pages

    if r.status_code != 200:
        log.warning(f"HTTP {r.status_code} for {url}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    # DEBUG — remove after confirming structure
    all_h3 = soup.find_all("h3")
    log.info(f"  DEBUG: {len(all_h3)} h3 tags found, page size {len(r.text)} bytes")
    for h in all_h3[:5]:
        log.info(f"    h3: {h.get_text(strip=True)[:80]!r}")

    # Strategy: find every h3 whose text ends with a STATE+POSTCODE pattern.
    # EPL uses h3 for listing titles on archive pages. Navigate up to the
    # nearest block container (article, div, li) to get the full card context.
    ADDRESS_RE = re.compile(r"[A-Z]{2,3}\s*\d{4}$")

    containers = []
    seen_ids = set()
    for h3 in soup.find_all("h3"):
        text = h3.get_text(separator=" ", strip=True)
        if not ADDRESS_RE.search(text):
            continue
        # Walk up to find the nearest block-level ancestor that wraps the full card
        el = h3
        for _ in range(6):  # look up to 6 levels up
            parent = el.parent
            if parent is None:
                break
            tag = parent.name
            if tag in ("article", "li", "div", "section"):
                # Use the element id to avoid duplicates
                el_id = id(parent)
                if el_id not in seen_ids:
                    seen_ids.add(el_id)
                    containers.append(parent)
                break
            el = parent

    if not containers:
        log.debug(f"No property cards found on {url} (page may be empty or structure changed)")
        return []

    listings = []
    for container in containers:
        try:
            rec = parse_article(container, domain)
            if rec:
                listings.append(rec)
        except Exception as e:
            log.debug(f"Parse error on {url}: {e}")

    return listings


# ── Supabase ──────────────────────────────────────────────────────────────────

def supabase_headers():
    return {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
        "Prefer":        "resolution=merge-duplicates,return=minimal",
    }


def upsert_batch(records, state, source):
    """Upsert a list of records to sourced_sales_{state}. Returns True on success."""
    table = f"sourced_sales_{state}"
    url   = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict=source,source_id"
    now   = datetime.utcnow().isoformat() + "Z"

    rows = [
        {
            "source":        source,
            "source_id":     r["source_id"],
            "sourced_at":    now,
            "source_url":    r.get("source_url"),
            "street_number": r.get("street_number"),
            "street_name":   r.get("street_name"),
            "suburb":        r.get("suburb"),
            "state_code":    r.get("state_code"),
            "postcode":      r.get("postcode"),
            "bedrooms":      r.get("bedrooms"),
            "bathrooms":     r.get("bathrooms"),
            "car_spaces":    r.get("car_spaces"),
            "sold_price":    r.get("sold_price"),
            "sold_date":     r.get("sold_date"),
        }
        for r in records
    ]

    for attempt in range(3):
        try:
            resp = requests.post(
                url, headers=supabase_headers(), json=rows, timeout=30
            )
            if resp.status_code in (200, 201):
                return True
            log.warning(
                f"Supabase {table} error {resp.status_code}: {resp.text[:200]}"
            )
        except requests.RequestException as e:
            log.warning(f"Supabase connection error (attempt {attempt+1}): {e}")
        time.sleep(2 ** attempt)

    return False


# ── Site scraper ──────────────────────────────────────────────────────────────

def scrape_site(site, outfile):
    """
    Scrape all sold pages from one franchise site.
    Streams records to local NDJSON backup and upserts to Supabase.
    Returns count of scraped records.
    """
    domain = site["domain"]
    source = site["source"]
    state  = site["state"]

    log.info(f"━━ {domain} → sourced_sales_{state} ({site['note']}) ━━")

    total = 0
    page  = 1

    while True:
        url = (
            f"https://{domain}/sold/"
            if page == 1
            else f"https://{domain}/sold/page/{page}/"
        )

        log.info(f"  p{page} {url}")
        listings = scrape_page(url, domain)

        if listings is None:
            log.info(f"  → 404, no more pages")
            break

        if not listings:
            log.info(f"  → 0 listings, stopping")
            break

        # Write to local backup
        for rec in listings:
            rec["_source"] = source
            rec["_state"]  = state
            outfile.write(json.dumps(rec) + "\n")

        # Upsert to Supabase in batches
        for i in range(0, len(listings), BATCH_SIZE):
            batch = listings[i : i + BATCH_SIZE]
            ok = upsert_batch(batch, state, source)
            status = "✓" if ok else "✗"
            log.info(f"    upsert {len(batch)} records → Supabase {status}")

        total += len(listings)
        log.info(f"  → {len(listings)} listings (running total: {total})")

        page += 1
        time.sleep(DELAY)

    log.info(f"  {domain}: {total} total records")
    return total


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not SUPABASE_SECRET:
        log.error(
            "SUPABASE_SECRET environment variable not set.\n"
            "Run: export SUPABASE_SECRET=your_key_here"
        )
        sys.exit(1)

    # Optional: single-domain mode
    filter_domain = None
    if len(sys.argv) >= 3 and sys.argv[1] == "--domain":
        filter_domain = sys.argv[2]
        log.info(f"Single-domain mode: {filter_domain}")

    sites = FRANCHISE_SITES
    if filter_domain:
        sites = [s for s in sites if s["domain"] == filter_domain]
        if not sites:
            log.error(f"Domain {filter_domain!r} not found in FRANCHISE_SITES")
            sys.exit(1)

    log.info(f"Scraping {len(sites)} franchise site(s) → {OUTPUT_FILE}")

    grand_total = 0
    with open(OUTPUT_FILE, "a") as outfile:
        for i, site in enumerate(sites):
            count = scrape_site(site, outfile)
            grand_total += count
            if i < len(sites) - 1:
                time.sleep(SITE_DELAY)

    log.info(f"═══ Done. Grand total: {grand_total} records scraped ═══")


if __name__ == "__main__":
    print("DEBUG: script entry point reached", flush=True)
    print(f"DEBUG: SUPABASE_SECRET set = {bool(SUPABASE_SECRET)}", flush=True)
    print(f"DEBUG: argv = {sys.argv}", flush=True)
    main()
