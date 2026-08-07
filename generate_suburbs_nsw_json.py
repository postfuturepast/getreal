#!/usr/bin/env python3
"""
generate_suburbs_nsw_json.py
Reads _nsw_suburb_cache.json (raw sale records from build_suburbs.py)
and outputs suburbs-nsw.json in the same format as suburb-data.json.

Run from repo root. Requires _nsw_suburb_cache.json to exist.
GitHub Actions: run after build_suburbs.py (which creates the cache).
"""

import json, os, statistics
from datetime import datetime

CACHE   = os.path.join(os.path.dirname(__file__), "_nsw_suburb_cache.json")
OUT     = os.path.join(os.path.dirname(__file__), "suburbs-nsw.json")
MIN_SALES = 10   # minimum total sales to include a suburb

print(f"Loading {CACHE}...")
with open(CACHE) as f:
    records = json.load(f)
print(f"  {len(records):,} records")

# Group by suburb + property_type
from collections import defaultdict
groups = defaultdict(lambda: defaultdict(list))
for r in records:
    suburb = r["suburb"].strip().lower()
    ptype  = r.get("property_type", "").strip().lower()
    price  = r.get("sale_price")
    if suburb and ptype and price and price > 0:
        groups[suburb][ptype].append(price)

# The cache covers ~2 years of NSW data — halve counts for annual estimate
YEARS_COVERED = 2.0

suburbs_out = {}
for suburb, types_data in sorted(groups.items()):
    total_sales = sum(len(v) for v in types_data.values())
    if total_sales < MIN_SALES:
        continue

    types_out = {}
    for ptype, prices in types_data.items():
        if len(prices) < 3:
            continue
        prices_sorted = sorted(prices)
        n = len(prices_sorted)
        median = prices_sorted[n // 2] if n % 2 == 1 else (prices_sorted[n//2 - 1] + prices_sorted[n//2]) / 2
        annual_sales = max(1, round(n / YEARS_COVERED))
        types_out[ptype] = {
            "median": round(median),
            "annualSales": annual_sales
        }

    if not types_out:
        continue

    # Display name: title case, handle common NSW patterns
    display = suburb.replace("_", " ").title()

    suburbs_out[suburb] = {
        "state": "NSW",
        "display": display,
        "types": types_out,
        "nearby": []
    }

print(f"  {len(suburbs_out):,} NSW suburbs with {MIN_SALES}+ sales")

out = {
    "generated": datetime.utcnow().strftime("%Y-%m-%d"),
    "source": "NSW Valuer General individual sale records via build_suburbs.py cache",
    "total_suburbs": len(suburbs_out),
    "suburbs": suburbs_out
}

with open(OUT, "w") as f:
    json.dump(out, f, separators=(",", ":"))

size_kb = os.path.getsize(OUT) / 1024
print(f"Written: {OUT} ({size_kb:.0f} KB)")
