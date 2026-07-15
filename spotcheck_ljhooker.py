"""
spotcheck_ljhooker.py — Spot-check LJ Hooker exact matches

Pulls 30 random property_sales rows enriched by LJ Hooker and fetches
the matching sourced_sales_nsw record to compare addresses side by side.

Usage:
    export SUPABASE_SECRET=your_secret_key_here
    python3 spotcheck_ljhooker.py
"""

import os, sys, requests, random

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")
if not SUPABASE_SECRET:
    print("ERROR: SUPABASE_SECRET not set.")
    sys.exit(1)

def headers():
    return {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
        "Content-Type":  "application/json",
    }

# Pull LJ Hooker exact matches from property_sales
url = (
    f"{SUPABASE_URL}/rest/v1/property_sales"
    f"?select=id,street_number,street_name,suburb,sale_date,bedrooms,bathrooms,car_spaces,enriched_source_id"
    f"&enriched_source=eq.ljhooker&match_confidence=eq.exact&limit=1000"
)
r = requests.get(url, headers=headers(), timeout=30)
ps_rows = r.json()
print(f"Total LJ Hooker exact matches in property_sales: {len(ps_rows)}")

# Sample 30
sample = random.sample(ps_rows, min(30, len(ps_rows)))

# Fetch matching sourced_sales records
source_ids = [row["enriched_source_id"] for row in sample]
ss_map = {}
for sid in source_ids:
    url2 = (
        f"{SUPABASE_URL}/rest/v1/sourced_sales_nsw"
        f"?select=source_id,street_number,street_name,street_type,suburb,bedrooms,bathrooms,car_spaces,sold_price"
        f"&source_id=eq.{sid}&source=eq.ljhooker"
    )
    r2 = requests.get(url2, headers=headers(), timeout=15)
    rows = r2.json()
    if rows:
        ss_map[sid] = rows[0]

# Print comparison
print(f"\n{'─'*80}")
print(f"{'VG ADDRESS':<40} {'LJH ADDRESS':<40} BEDS BATH CARS")
print(f"{'─'*80}")

ok = bad = 0
for row in sample:
    sid = row["enriched_source_id"]
    ss  = ss_map.get(sid)
    if not ss:
        continue

    vg_addr  = f"{row['street_number']} {row['street_name']}, {row['suburb']}".title()
    ljh_addr = f"{ss['street_number']} {ss['street_name']} {ss.get('street_type','')}, {ss['suburb']}".title()

    beds = ss.get("bedrooms", "?")
    bath = ss.get("bathrooms", "?")
    cars = ss.get("car_spaces", "?")

    # Flag if suburb doesn't match (rough check)
    vg_sub  = (row.get("suburb") or "").upper().strip()
    ljh_sub = (ss.get("suburb") or "").upper().strip()
    flag = " ⚠" if vg_sub != ljh_sub else ""

    print(f"{vg_addr:<40} {ljh_addr:<40} {str(beds):>4} {str(bath):>4} {str(cars):>4}{flag}")
    if flag:
        bad += 1
    else:
        ok += 1

print(f"{'─'*80}")
print(f"\n{ok} suburb match, {bad} suburb mismatch ⚠")
