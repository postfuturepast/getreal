"""
cleanup_db.py
=============
Reduces Supabase database size by removing old/duplicate data.

Order of operations:
1. Delete old sourced_sales_* records (>2 years) — no FK dependencies, frees space fast
2. Null remaining FK references from sourced_sales_nsw → property_sales
3. Delete duplicate NSW property_sales records in daily batches

Run: export SUPABASE_SECRET=... && python3 cleanup_db.py
"""

import requests, os, time
from datetime import date, timedelta

key = os.environ.get("SUPABASE_SECRET", "")
if not key:
    print("ERROR: SUPABASE_SECRET not set")
    exit(1)

BASE = "https://lkxzxeeeqfiymunpqvgt.supabase.co/rest/v1"
HEADERS = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}
CUTOFF = (date.today() - timedelta(days=730)).isoformat()  # 2 years ago

def delete(table, params, label=""):
    url = f"{BASE}/{table}?{params}"
    r = requests.delete(url, headers=HEADERS, timeout=30)
    status = "OK" if r.status_code in (200, 204) else f"FAILED {r.status_code} {r.text[:80]}"
    print(f"  {label or table}: {status}")
    return r.status_code in (200, 204)

def patch(table, params, body, label=""):
    url = f"{BASE}/{table}?{params}"
    r = requests.patch(url, headers=HEADERS, json=body, timeout=30)
    status = "OK" if r.status_code in (200, 204) else f"FAILED {r.status_code} {r.text[:80]}"
    print(f"  {label}: {status}")

# ─── STEP 1: Delete old sourced_sales records (>2 years) ───────────────────
print(f"\n=== Step 1: Delete sourced_sales records older than {CUTOFF} ===")

sourced_tables = [
    ("sourced_sales_nsw", "sold_date"),
    ("sourced_sales_vic", "sold_date"),
    ("sourced_sales_qld", "sold_date"),
    ("sourced_sales_sa",  "sold_date"),
    ("sourced_sales_wa",  "sold_date"),
    ("sourced_sales_act", "sold_date"),
    ("sourced_sales_tas", "sold_date"),
    ("sourced_sales_nt",  "sold_date"),
]

for table, date_col in sourced_tables:
    delete(table, f"{date_col}=lt.{CUTOFF}", label=f"{table} (old records)")
    time.sleep(0.5)

# ─── STEP 2: Null remaining FK references ──────────────────────────────────
print(f"\n=== Step 2: Null FK references in sourced_sales_nsw ===")
for col in ["outside_window_property_id", "property_id", "matched_property_id"]:
    patch("sourced_sales_nsw", f"{col}=not.is.null", {col: None}, label=f"null {col}")
    time.sleep(0.5)

# ─── STEP 3: Delete NSW property_sales duplicates (daily batches) ───────────
print(f"\n=== Step 3: Delete NSW property_sales (daily batches from 2025-06-13) ===")
start = date(2025, 6, 13)   # resume from where previous script failed
end   = date(2027, 1, 1)

failed = []
while start < end:
    chunk_end = start + timedelta(days=1)
    ok = delete(
        "property_sales",
        f"state=eq.NSW&sale_date=gte.{start}&sale_date=lt.{chunk_end}",
        label=str(start)
    )
    if not ok:
        failed.append(str(start))
    start = chunk_end
    time.sleep(0.2)

print("\n=== Summary ===")
if failed:
    print(f"Failed dates: {failed}")
    print("Re-run script or delete these manually.")
else:
    print("All done! Now run:")
    print("  python3 load_nsw_csv.py --download --clear --batch-size 500")
