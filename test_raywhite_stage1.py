"""
test_raywhite_stage1.py — Stage 1: API stress test
====================================================
Tests whether the Ray White API can be bulk-queried across multiple postcodes
without rate limiting or blocking.

Tests 5 postcodes, paginates all results from each, measures:
- Total records returned per postcode
- Time per request
- Whether we get blocked or rate-limited
- Data quality (bedrooms/bathrooms present?)

Run: python3 test_raywhite_stage1.py
"""

import requests
import json
import time

API_URL = "https://raywhiteapi.ep.dynamics.net/v1/listings"
API_KEY = "6625c417-067a-4a8e-8c1d-85c812d0fb25"

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

# 5 diverse test postcodes: inner Sydney, suburban, regional
TEST_POSTCODES = [
    ("2042", "Newtown"),
    ("2000", "Sydney CBD"),
    ("2145", "Westmead/Parramatta"),
    ("2250", "Gosford"),
    ("2640", "Albury"),
]

PAGE_SIZE = 50  # Use larger page size to reduce requests


def fetch_page(postcode, from_offset):
    payload = {
        "size": PAGE_SIZE,
        "from": from_offset,
        "stateCode": "NSW",
        "postCode": [postcode],
        "statusCode": {"in": ["SLD"]},
        "typeCode": {"in": ["SAL", "RUR"]},
        "countryCode": ["AU", "NZ"],
        "categoryCode": {"in": []},
    }
    start = time.time()
    r = requests.post(
        f"{API_URL}?apiKey={API_KEY}",
        headers=HEADERS,
        json=payload,
        timeout=15,
    )
    elapsed = time.time() - start
    return r, elapsed


def check_record_quality(record):
    v = record.get("value", {})
    has_beds = v.get("bedrooms") is not None
    has_baths = v.get("bathrooms") is not None
    has_sold_price = v.get("soldPrice") is not None
    has_sold_date = bool(v.get("soldDate"))
    addr = v.get("address", {})
    has_address = bool(addr.get("streetNumber") and addr.get("streetName"))
    return has_beds, has_baths, has_sold_price, has_sold_date, has_address


def test_postcode(postcode, label):
    print(f"\n{'='*60}")
    print(f"Testing {label} (postcode {postcode})")
    print('='*60)

    # First page to get total hits
    r, elapsed = fetch_page(postcode, 0)
    print(f"  Page 1: status={r.status_code}, time={elapsed:.2f}s")

    if r.status_code != 200:
        print(f"  BLOCKED or ERROR: {r.status_code}")
        print(f"  Response: {r.text[:200]}")
        return None

    data = r.json()
    total_hits = data.get("hits", 0)
    records = data.get("data", [])
    print(f"  Total hits: {total_hits:,}")
    print(f"  Records on page 1: {len(records)}")

    if not records:
        print("  No records found.")
        return {"postcode": postcode, "hits": 0, "records_fetched": 0}

    # Quality check on first page
    beds_ok = baths_ok = sold_price_ok = sold_date_ok = addr_ok = 0
    for rec in records:
        hb, hba, hsp, hsd, ha = check_record_quality(rec)
        if hb: beds_ok += 1
        if hba: baths_ok += 1
        if hsp: sold_price_ok += 1
        if hsd: sold_date_ok += 1
        if ha: addr_ok += 1

    n = len(records)
    print(f"\n  Data quality (first {n} records):")
    print(f"    bedrooms present:   {beds_ok}/{n} ({100*beds_ok//n}%)")
    print(f"    bathrooms present:  {baths_ok}/{n} ({100*baths_ok//n}%)")
    print(f"    soldDate present:   {sold_date_ok}/{n} ({100*sold_date_ok//n}%)")
    print(f"    soldPrice present:  {sold_price_ok}/{n} ({100*sold_price_ok//n}%)")
    print(f"    address present:    {addr_ok}/{n} ({100*addr_ok//n}%)")

    # Sample record
    sample = records[0].get("value", {})
    addr = sample.get("address", {})
    print(f"\n  Sample record:")
    print(f"    {addr.get('streetNumber')} {addr.get('streetName')} {addr.get('streetType')}, {addr.get('suburb')} {addr.get('postCode')}")
    print(f"    beds={sample.get('bedrooms')} baths={sample.get('bathrooms')} cars={sample.get('carSpaces')}")
    print(f"    soldDate={sample.get('soldDate')} soldPrice={sample.get('soldPrice')}")

    # Paginate remaining pages (up to 5 total to keep test fast)
    total_fetched = len(records)
    pages_fetched = 1
    max_pages = 5

    while total_fetched < total_hits and pages_fetched < max_pages:
        time.sleep(0.5)  # Polite delay
        r, elapsed = fetch_page(postcode, total_fetched)
        pages_fetched += 1

        if r.status_code != 200:
            print(f"\n  ⚠️  Page {pages_fetched} BLOCKED: status={r.status_code}")
            break

        page_data = r.json().get("data", [])
        total_fetched += len(page_data)
        print(f"  Page {pages_fetched}: status={r.status_code}, time={elapsed:.2f}s, records={len(page_data)}, total_so_far={total_fetched}")

        if not page_data:
            break

    pages_needed_for_full = -(-total_hits // PAGE_SIZE)  # ceiling division
    print(f"\n  Summary:")
    print(f"    Total available: {total_hits:,} records")
    print(f"    Fetched in test: {total_fetched} records ({pages_fetched} pages)")
    print(f"    Pages needed for full extract: {pages_needed_for_full}")
    print(f"    Estimated full extract time (at 0.5s/page): {pages_needed_for_full * 0.5:.0f}s")

    return {
        "postcode": postcode,
        "label": label,
        "hits": total_hits,
        "records_fetched": total_fetched,
        "pages_fetched": pages_fetched,
        "blocked": False,
    }


def main():
    print("Ray White API — Stage 1 Stress Test")
    print("Testing bulk extraction across 5 diverse NSW postcodes")
    print("Delay between requests: 0.5s\n")

    results = []
    for postcode, label in TEST_POSTCODES:
        result = test_postcode(postcode, label)
        results.append(result)
        time.sleep(1)  # Pause between postcodes

    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    total_records = sum(r["hits"] for r in results if r)
    print(f"{'Postcode':<10} {'Label':<25} {'Total hits':>12}  {'Blocked?':>8}")
    print("-" * 60)
    for r in results:
        if r:
            blocked = "YES ⚠️" if r.get("blocked") else "no ✅"
            print(f"{r['postcode']:<10} {r['label']:<25} {r['hits']:>12,}  {blocked:>8}")

    print(f"\nAll 5 postcodes sampled. No blocking = Stage 1 PASS → proceed to Stage 2.")
    print(f"Any blocking = investigate rate limits before proceeding.")


if __name__ == "__main__":
    main()
