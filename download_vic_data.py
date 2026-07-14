#!/usr/bin/env python3
"""
download_vic_data.py
====================
Scrapes land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics
to find and download the latest VIC quarterly median price XLS files.

Downloads:
  median-house-qQ-YYYY.xls   → used by load_vic_quarterly.py
  median-unit-qQ-YYYY.xls    → used by load_vic_quarterly.py

Usage:
  python3 download_vic_data.py

Exits 0 if files were downloaded (or are already current).
Exits 1 if scraping fails or no files found.
Exits 2 if no new files (data already up to date) — allows GitHub Actions to skip commit.
"""

import os
import re
import sys
import json
import hashlib
import requests
from pathlib import Path

PAGE_URL  = "https://www.land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics"
BASE_URL  = "https://www.land.vic.gov.au"
STATE_FILE = ".vic_download_state.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GetReal-pipeline/1.0; +https://get-real.co)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def find_xls_links(html: str) -> list[str]:
    """Extract all .xls href values from the page HTML."""
    return re.findall(r'href=["\']([^"\']*\.xls[x]?)["\']', html, re.IGNORECASE)


def is_median_file(url: str) -> bool:
    lower = url.lower()
    return (("median-house" in lower or "median-unit" in lower) and ".xls" in lower)


def resolve(link: str) -> str:
    if link.startswith("http"):
        return link
    if link.startswith("//"):
        return "https:" + link
    if link.startswith("/"):
        return BASE_URL + link
    return BASE_URL + "/" + link


def file_md5(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def download_file(url: str, dest: str) -> int:
    r = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    return len(r.content)


def extract_quarter_label(filename: str) -> str:
    """Extract 'q4-2025' from 'median-house-q4-2025.xls'."""
    m = re.search(r"(q\d-\d{4})", filename, re.IGNORECASE)
    return m.group(1).lower() if m else "unknown"


def main():
    print(f"Fetching {PAGE_URL} ...")
    try:
        r = requests.get(PAGE_URL, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"ERROR: Could not fetch VIC stats page: {e}")
        sys.exit(1)

    raw_links = find_xls_links(r.text)
    median_links = [resolve(l) for l in raw_links if is_median_file(l)]

    # De-duplicate while preserving order
    seen = set()
    median_links = [l for l in median_links if not (l in seen or seen.add(l))]

    if not median_links:
        print("ERROR: No median-house or median-unit XLS links found on the page.")
        print("The page structure may have changed. Check manually:")
        print(f"  {PAGE_URL}")
        # Fallback: try predictable URL patterns for current quarter
        print("\nAttempting fallback URL patterns...")
        import datetime
        now = datetime.datetime.utcnow()
        year = now.year
        # Determine current quarter
        q = (now.month - 1) // 3  # 0-indexed
        # Previous quarter (most recently released)
        if q == 0:
            q, year = 4, year - 1
        quarter_label = f"q{q}-{year}"
        # VGV typically publishes about 2 months after quarter end
        upload_months = {1: "03", 2: "06", 3: "09", 4: "12"}
        upload_month = upload_months.get(q, "01")
        for ftype in ("house", "unit"):
            url = f"{BASE_URL}/sites/default/files/{year}-{upload_month}/median-{ftype}-{quarter_label}.xls"
            median_links.append(url)
            print(f"  Trying: {url}")

    print(f"\nCandidate XLS files ({len(median_links)}):")
    for url in median_links:
        print(f"  {url}")

    state = load_state()
    downloaded = []
    already_current = []

    for url in median_links:
        filename = url.split("/")[-1].split("?")[0]
        dest = filename

        print(f"\nProcessing {filename} ...")
        try:
            size = download_file(url, dest)
        except requests.RequestException as e:
            print(f"  SKIP: {e}")
            continue

        md5 = file_md5(dest)
        prev_md5 = state.get(filename)

        if prev_md5 == md5:
            print(f"  UNCHANGED ({size:,} bytes) — skipping")
            already_current.append(filename)
        else:
            print(f"  DOWNLOADED ({size:,} bytes) — new or updated")
            state[filename] = md5
            downloaded.append(filename)

    save_state(state)

    if not downloaded and not already_current:
        print("\nNo files could be downloaded. Exiting with error.")
        sys.exit(1)

    if not downloaded:
        print(f"\nAll {len(already_current)} file(s) are already current — no update needed.")
        sys.exit(2)  # Signal to GitHub Actions: no new data

    print(f"\nDownloaded {len(downloaded)} new/updated file(s): {', '.join(downloaded)}")

    # Print detected quarter for GitHub Actions output
    quarters = set(extract_quarter_label(f) for f in downloaded)
    print(f"Quarter(s): {', '.join(quarters)}")
    sys.exit(0)


if __name__ == "__main__":
    main()
