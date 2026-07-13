"""
populate_price_curves.py
========================
Derives price distribution curves from NSW sale records and upserts
them into the Supabase price_curves table.

Methodology:
  - Fetch all NSW individual sales from property_sales
  - Calculate suburb medians directly from the data (grouped by suburb + type)
  - For each sale, compute price_ratio = sale_price / suburb_median
  - Group by property_type + price_bracket + depth_tier
    - depth_tier = 'active' if suburb has 30+ sales/yr, else 'thin'
    - price_bracket based on the suburb median
  - Compute the cumulative % at each ratio threshold (0.5x to 1.5x)
  - Upsert results into price_curves table

USAGE
-----
export SUPABASE_SECRET=your_secret_key_here
python3 populate_price_curves.py

Run again whenever new NSW data is loaded into property_sales.
"""

import os
import requests
from collections import defaultdict

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

if not SUPABASE_SECRET:
    print("ERROR: SUPABASE_SECRET not set.")
    print("Run: export SUPABASE_SECRET=your_secret_key_here")
    exit(1)

HEADERS = {
    "apikey":        SUPABASE_SECRET,
    "Authorization": f"Bearer {SUPABASE_SECRET}",
    "Content-Type":  "application/json",
}

PRICE_BRACKETS = [
    (0,           500_000,       "under_500k"),
    (500_000,     800_000,       "500k_800k"),
    (800_000,     1_200_000,     "800k_1200k"),
    (1_200_000,   1_800_000,     "1200k_1800k"),
    (1_800_000,   float("inf"), "over_1800k"),
]

RATIO_THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5]
RATIO_COLS       = ["pct_at_05x", "pct_at_06x", "pct_at_07x", "pct_at_08x",
                    "pct_at_09x", "pct_at_10x", "pct_at_11x", "pct_at_12x", "pct_at_15x"]

ACTIVE_THRESHOLD = 30   # sales/year — below this = 'thin'


def fetch_all(table, select, filters=""):
    rows = []
    page_size = 1000
    offset = 0
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}{filters}&limit={page_size}"
    while True:
        resp = requests.get(
            url + f"&offset={offset}",
            headers={**HEADERS, "Range-Unit": "items", "Range": f"{offset}-{offset+page_size-1}"}
        )
        batch = resp.json()
        if not batch:
            break
        rows += batch
        if len(batch) < page_size:
            break
        offset += page_size
        if offset % 10000 == 0:
            print(f"  Fetched {offset} rows...")
    return rows


# ── Fetch all NSW sales ───────────────────────────────────────────────────────
print("Fetching NSW property sales...")
sales = fetch_all(
    "property_sales",
    "suburb,property_type,sale_price",
    "&state=eq.NSW&sale_price=gt.50000"
)
print(f"  Got {len(sales)} sales")

# ── Calculate suburb medians and annual volumes ───────────────────────────────
print("\nCalculating suburb medians and volumes...")
suburb_prices = defaultdict(list)
for sale in sales:
    suburb = (sale.get("suburb") or "").lower().strip()
    ptype  = sale.get("property_type") or ""
    price  = sale.get("sale_price") or 0
    if suburb and ptype and price > 0:
        suburb_prices[(suburb, ptype)].append(price)

suburb_stats = {}  # (suburb, ptype) -> (median, annual_sales)
for (suburb, ptype), prices in suburb_prices.items():
    prices.sort()
    n = len(prices)
    if n >= 5:
        median = prices[n // 2]
        suburb_stats[(suburb, ptype)] = (median, n)

print(f"  {len(suburb_stats)} suburb/type combinations")

# ── Calculate ratios, group by type + bracket + depth ────────────────────────
print("\nGrouping ratios...")
# groups[ptype][bracket][depth] = [ratios]
groups = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
skipped = 0

for sale in sales:
    suburb = (sale.get("suburb") or "").lower().strip()
    ptype  = sale.get("property_type") or ""
    price  = sale.get("sale_price") or 0

    stats = suburb_stats.get((suburb, ptype))
    if not stats:
        skipped += 1
        continue

    median, annual_sales = stats
    if median <= 0:
        skipped += 1
        continue

    ratio = price / median
    if ratio < 0.2 or ratio > 3.0:
        skipped += 1
        continue

    bracket = None
    for lo, hi, label in PRICE_BRACKETS:
        if lo <= median < hi:
            bracket = label
            break
    if not bracket:
        continue

    depth = "active" if annual_sales >= ACTIVE_THRESHOLD else "thin"
    groups[ptype][bracket][depth].append(ratio)

print(f"  Skipped {skipped} sales")

# ── Compute curve rows ────────────────────────────────────────────────────────
print("\nComputing curves...")
rows_to_upsert = []

for ptype in ["house", "apartment", "townhouse"]:
    if ptype not in groups:
        continue
    for _, _, bracket in PRICE_BRACKETS:
        depth_data = groups[ptype].get(bracket)
        if not depth_data:
            continue
        for depth in ["active", "thin"]:
            ratios = depth_data.get(depth)
            if not ratios or len(ratios) < 20:
                print(f"  SKIP {ptype} / {bracket} / {depth}: only {len(ratios) if ratios else 0} sales")
                continue
            n = len(ratios)
            row = {
                "property_type": ptype,
                "price_bracket": bracket,
                "depth_tier":    depth,
                "sample_size":   n,
            }
            for col, threshold in zip(RATIO_COLS, RATIO_THRESHOLDS):
                count = sum(1 for r in ratios if r <= threshold)
                row[col] = round(count / n * 100, 2)

            rows_to_upsert.append(row)
            print(f"  {ptype:<12} {bracket:<14} {depth:<8} n={n:>6}  "
                  f"≤0.8x={row['pct_at_08x']}%  ≤1.0x={row['pct_at_10x']}%  ≤1.2x={row['pct_at_12x']}%")

# ── Upsert into Supabase ──────────────────────────────────────────────────────
print(f"\nUpserting {len(rows_to_upsert)} rows into price_curves...")
url = f"{SUPABASE_URL}/rest/v1/price_curves"
upsert_headers = {
    **HEADERS,
    "Prefer": "resolution=merge-duplicates,return=minimal",
}
resp = requests.post(url, headers=upsert_headers, json=rows_to_upsert)
if resp.status_code in (200, 201):
    print(f"Done — {len(rows_to_upsert)} rows upserted successfully.")
else:
    print(f"ERROR: {resp.status_code} — {resp.text[:300]}")

print("\nSummary of rows inserted:")
for r in rows_to_upsert:
    print(f"  {r['property_type']:<12} {r['price_bracket']:<14} {r['depth_tier']:<8} "
          f"sample={r['sample_size']:>6}  ≤1.0x={r['pct_at_10x']}%")
