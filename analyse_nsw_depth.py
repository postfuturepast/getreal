"""
analyse_nsw_depth.py
====================
Step 2: Do curves differ between high-volume (inner city) and
low-volume (thin/regional) suburbs within the same price bracket?

We split suburbs by annual sales count as a proxy for market depth:
  Deep:   100+ sales/year  (inner city, high density)
  Medium: 30-99 sales/year (middle ring)
  Thin:   <30  sales/year  (outer, regional, small markets)

Then compare the distribution curves within each price bracket.
If curves are similar across depth tiers, price bracket alone is enough.
If they differ meaningfully, we need the extra dimension.

USAGE
-----
export SUPABASE_SECRET=your_secret_key_here
python3 analyse_nsw_depth.py
"""

import os
import requests
from collections import defaultdict

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

if not SUPABASE_SECRET:
    print("ERROR: SUPABASE_SECRET not set.")
    exit(1)

HEADERS = {
    "apikey":        SUPABASE_SECRET,
    "Authorization": f"Bearer {SUPABASE_SECRET}",
    "Content-Type":  "application/json",
}

PRICE_BRACKETS = [
    (0,         500_000,   "Under $500k"),
    (500_000,   800_000,   "$500k-$800k"),
    (800_000,   1_200_000, "$800k-$1.2M"),
    (1_200_000, 1_800_000, "$1.2M-$1.8M"),
    (1_800_000, float('inf'), "Over $1.8M"),
]

DEPTH_TIERS = [
    (100, float('inf'), "Deep   (100+ sales/yr)"),
    (30,  99,           "Medium (30-99 sales/yr)"),
    (0,   29,           "Thin   (<30 sales/yr)  "),
]

RATIO_THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5]

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

# ── Fetch sales ───────────────────────────────────────────────────────────────
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

# ── Calculate price ratios, grouped by type + price bracket + depth ───────────
print("\nGrouping by property type, price bracket, and market depth...")

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

    bracket_label = None
    for lo, hi, label in PRICE_BRACKETS:
        if lo <= median < hi:
            bracket_label = label
            break
    if not bracket_label:
        continue

    depth_label = None
    for lo, hi, label in DEPTH_TIERS:
        if lo <= annual_sales <= hi:
            depth_label = label
            break
    if not depth_label:
        continue

    groups[ptype][bracket_label][depth_label].append(ratio)

print(f"  Skipped {skipped} sales\n")

# ── Print results — focus on houses first, then apartments ───────────────────
print("=" * 90)
print("CURVE COMPARISON BY MARKET DEPTH — within each price bracket")
print("Question: do inner-city (deep) suburbs curve differently to thin/regional ones?")
print("=" * 90)

for ptype in ["house", "apartment", "townhouse"]:
    if ptype not in groups:
        continue
    print(f"\n{'━'*90}")
    print(f"  {ptype.upper()}")
    print(f"{'━'*90}")

    for _, _, bracket_label in PRICE_BRACKETS:
        depth_data = groups[ptype].get(bracket_label)
        if not depth_data:
            continue

        print(f"\n  {bracket_label}")
        header = f"    {'Depth tier':<26} {'Sales':>6}  " + "  ".join(f"≤{r:.1f}x" for r in RATIO_THRESHOLDS)
        print(header)
        print("    " + "-" * (len(header) - 4))

        for lo, hi, depth_label in DEPTH_TIERS:
            ratios = depth_data.get(depth_label)
            if not ratios or len(ratios) < 10:
                print(f"    {depth_label:<26} {'<10':>6}  (not enough data)")
                continue
            n = len(ratios)
            pcts = []
            for t in RATIO_THRESHOLDS:
                count = sum(1 for r in ratios if r <= t)
                pcts.append(f"{count/n*100:>5.1f}%")
            print(f"    {depth_label:<26} {n:>6}  {'  '.join(pcts)}")

print("\n" + "=" * 90)
print("KEY QUESTION: Within each bracket, are the rows above similar or different?")
print("If similar → price bracket alone is sufficient. If different → depth matters.")
print("=" * 90)
print("\nDone. Paste output back to Claude.")
