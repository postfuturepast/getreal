"""
test_raywhite.py
Quick proof-of-concept: can we scrape bedroom data from Ray White's sold listings?

Run: python3 test_raywhite.py
"""

import requests
from bs4 import BeautifulSoup
import json
import re

URL = "https://www.raywhite.com/listing?type=sold&address=Newtown%2C+NSW+2042&surrounding=0&category=any"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

def main():
    print(f"Fetching: {URL}\n")
    try:
        r = requests.get(URL, headers=HEADERS, timeout=15)
    except Exception as e:
        print(f"ERROR: {e}")
        return

    print(f"Status: {r.status_code}")
    print(f"Size: {len(r.content):,} bytes")
    print(f"Content-Type: {r.headers.get('Content-Type', 'unknown')}\n")

    if r.status_code != 200:
        print("Non-200 response. Bot blocked?")
        print(r.text[:500])
        return

    soup = BeautifulSoup(r.text, "html.parser")

    # Look for JSON-LD structured data (common in listing sites)
    json_lds = soup.find_all("script", type="application/ld+json")
    print(f"JSON-LD blocks found: {len(json_lds)}")
    for i, block in enumerate(json_lds[:3]):
        try:
            data = json.loads(block.string)
            print(f"\n--- JSON-LD {i+1} ---")
            print(json.dumps(data, indent=2)[:800])
        except:
            pass

    # Look for Next.js / __NEXT_DATA__ (many modern agency sites use Next.js)
    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data:
        print("\n✓ Found __NEXT_DATA__ (Next.js site)")
        try:
            data = json.loads(next_data.string)
            # Try to find listings in the data
            raw = json.dumps(data)
            if "bedroom" in raw.lower() or "beds" in raw.lower():
                print("✓ 'bedroom' data found in __NEXT_DATA__!")
            else:
                print("✗ No bedroom data visible in __NEXT_DATA__")
            print(f"Keys at root: {list(data.keys())}")
        except Exception as e:
            print(f"Could not parse: {e}")
    else:
        print("\n✗ No __NEXT_DATA__ found")

    # Look for listing cards in the HTML
    # Try common patterns
    cards = (
        soup.find_all(class_=re.compile(r'listing|property|card', re.I))
    )
    print(f"\nPotential listing elements found: {len(cards)}")

    # Look for bed/bath mentions
    text = r.text.lower()
    bed_count = text.count("bedroom") + text.count('"beds"') + text.count("bed:")
    bath_count = text.count("bathroom") + text.count('"baths"') + text.count("bath:")
    print(f"\n'bedroom' mentions in page: {bed_count}")
    print(f"'bathroom' mentions in page: {bath_count}")

    if bed_count > 0:
        print("\n✓ GOOD: Bedroom data appears to be in the page HTML/JS")
    else:
        print("\n✗ No bedroom data visible — likely client-rendered (JS required)")

    # Show first 1000 chars of body to help diagnose
    print("\n--- First 500 chars of body ---")
    print(r.text[:500])

if __name__ == "__main__":
    main()
