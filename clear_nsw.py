import requests, os
from datetime import date, timedelta

key = os.environ.get("SUPABASE_SECRET", "")
if not key:
    print("ERROR: SUPABASE_SECRET not set")
    exit(1)

base = "https://lkxzxeeeqfiymunpqvgt.supabase.co/rest/v1"
headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# Step 1: Null out FK references in sourced_sales_nsw
print("Nulling FK references in sourced_sales_nsw...")
for col in ["outside_window_property_id", "property_id", "matched_property_id"]:
    url = f"{base}/sourced_sales_nsw?{col}=not.is.null"
    r = requests.patch(url, headers=headers, json={col: None}, timeout=30)
    if r.status_code in (200, 204):
        print(f"  Nulled {col}: OK")
    elif r.status_code == 400 and "does not exist" in r.text:
        print(f"  {col}: not found, skipping")
    else:
        print(f"  {col}: {r.status_code} {r.text[:100]}")

# Step 2: Delete NSW property_sales in weekly chunks
print("\nDeleting NSW property_sales (weekly batches)...")
start = date(2025, 6, 9)  # resume from where it failed
end_date = date(2027, 1, 1)

failed = []
while start < end_date:
    chunk_end = min(start + timedelta(days=1), end_date)
    url = f"{base}/property_sales?state=eq.NSW&sale_date=gte.{start}&sale_date=lt.{chunk_end}"
    r = requests.delete(url, headers=headers, timeout=30)
    if r.status_code in (200, 204):
        print(f"  {start} → {chunk_end}: OK")
    else:
        print(f"  {start} → {chunk_end}: FAILED {r.status_code} {r.text[:80]}")
        failed.append(start)
    start = chunk_end

if failed:
    print(f"\nFailed weeks: {failed}")
else:
    print("\nAll cleared. Now run: python3 load_nsw_csv.py --download --clear --batch-size 500")
