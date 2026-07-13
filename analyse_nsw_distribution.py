"""
analyse_nsw_distribution.py
===========================
Step 1: Understand the shape of NSW property price distributions.

For each sale in property_sales, we calculate:
    price_ratio = sale_price / suburb_median

Then we look at how those ratios distribute across property types
and median price brackets.

USAGE
-----
export SUPABASE_SECRET=your_secret_key_here
python3 analyse_nsw_distribution.py

OUTPUT
------
Prints a summary table showing, for each property type + price bracket:
- Number of suburbs and sales
- What % of sales fall at various ratios of the suburb median
  (0.5x, 0.6x, 0.7x, 0.8x, 0.9x, 1.0x, 1.1x, 1.2x, 1.5x)
"""

import os
import requests
from collections import defaultdict

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

if not SUPABASE_SECRET:
    print("ERROR: SUPABASE_SECRET environment variable not set.")
    print("Run: export SUPABASE_SECRET=your_secret_key_here")
    exit(1)

HEADERS = {
    "apikey":        SUPABASE_SECRET,
    "Authorization": f"Bearer {SUPABASE_SECRET}",
    "Content-Type":  "application/json",
}

PRICE_BRACKETS = [
    (0,        500_000,  "Under $500k"),
    (500_000,  800_000,  "$500k-$800k"),
    (800_000,  1_200_000,"$800k-$1.2M"),
    (1_200_000,1_800_000,"$1.2M-$1.8M"),
    (1_800_000,float('inf'),"Over $1.8M"),
]

RATIO_THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5]

def fetch_all(table, select, filters=""):
    """Fetch all rows with pagination."""
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

# ── Step 1: Fetch all NSW sales ───────────────────────────────────────────────
print("Fetching NSW property sales...")
sales = fetch_all(
    "property_sales",
    "suburb,property_type,sale_price",
    "&state=eq.NSW&sale_price=gt.50000"
)
print(f"  Got {len(sales)} sales")

# ── Step 2: Calculate suburb medians from the sales data itself ───────────────
print("\nCalculating suburb medians from sales data...")
from collections import defaultdict

suburb_prices = defaultdict(list)
for sale in sales:
    suburb = (sale.get("suburb") or "").lower().strip()
    ptype  = sale.get("property_type") or ""
    price  = sale.get("sale_price") or 0
    if suburb and ptype and price > 0:
        suburb_prices[(suburb, ptype)].append(price)

medians = {}
for (suburb, ptype), prices in suburb_prices.items():
    prices.sort()
    n = len(prices)
    if n >= 5:  # only use suburbs with at least 5 sales
        medians[(suburb, ptype)] = prices[n // 2]

print(f"  Calculated medians for {len(medians)} suburb/type combinations")

# ── Step 3: Calculate price ratios ───────────────────────────────────────────
print("\nCalculating price ratios...")

# Group: property_type -> price_bracket -> list of ratios
groups = defaultdict(lambda: defaultdict(list))
skipped = 0

for sale in sales:
    suburb = (sale.get("suburb") or "").lower().strip()
    ptype  = sale.get("property_type") or ""
    price  = sale.get("sale_price") or 0

    median = medians.get((suburb, ptype))
    if not median or median <= 0:
        skipped += 1
        continue

    ratio = price / median

    # Only keep ratios in a sensible range (0.2x to 3x)
    if ratio < 0.2 or ratio > 3.0:
        skipped += 1
        continue

    # Find price bracket based on median
    bracket_label = None
    for lo, hi, label in PRICE_BRACKETS:
        if lo <= median < hi:
            bracket_label = label
            break
    if not bracket_label:
        continue

    groups[ptype][bracket_label].append(ratio)

print(f"  Skipped {skipped} sales (no matching median or outlier ratio)")

# ── Step 4: Print distribution table ─────────────────────────────────────────
print("\n" + "="*80)
print("NSW PRICE RATIO DISTRIBUTIONS")
print("Showing: % of sales at or below each ratio of suburb median")
print("="*80)

for ptype in sorted(groups.keys()):
    print(f"\n── {ptype.upper()} ──")
    header = f"{'Bracket':<18} {'Sales':>6}  " + "  ".join(f"<={r:.1f}x" for r in RATIO_THRESHOLDS)
    print(header)
    print("-" * len(header))

    for _, _, label in PRICE_BRACKETS:
        ratios = groups[ptype].get(label)
        if not ratios or len(ratios) < 10:
            continue
        ratios_sorted = sorted(ratios)
        n = len(ratios_sorted)
        pcts = []
        for t in RATIO_THRESHOLDS:
            count_below = sum(1 for r in ratios_sorted if r <= t)
            pcts.append(f"{count_below/n*100:>6.1f}%")
        print(f"{label:<18} {n:>6}  {'  '.join(pcts)}")

print("\n" + "="*80)
print("SUMMARY: Median ratio stats by property type")
print("="*80)
for ptype in sorted(groups.keys()):
    all_ratios = []
    for bracket_ratios in groups[ptype].values():
        all_ratios.extend(bracket_ratios)
    if not all_ratios:
        continue
    all_ratios.sort()
    n = len(all_ratios)
    p25 = all_ratios[int(n*0.25)]
    p50 = all_ratios[int(n*0.50)]
    p75 = all_ratios[int(n*0.75)]
    print(f"{ptype:<12}: n={n:>6}  P25={p25:.3f}x  P50={p50:.3f}x  P75={p75:.3f}x")

print("\nDone. Paste the output above back to Claude for analysis.")
