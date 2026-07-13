"""
generate_nsw_suburbs.py
=======================
Fetches all unique NSW suburb names from Supabase and writes them to
nsw-suburbs.json — a static file loaded by search.html for autocomplete.

Uses only the public anon key (safe to run, no secret key needed).

USAGE
-----
python3 generate_nsw_suburbs.py

OUTPUT
------
nsw-suburbs.json  — commit this and deploy alongside search.html
"""

import json, urllib.request, urllib.parse, sys

SUPABASE_URL = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
ANON_KEY     = "sb_publishable_1jyBD0hVdHX2ieqFIlC51A_A3ep39Bc"

HEADERS = {
    "apikey":        ANON_KEY,
    "Authorization": f"Bearer {ANON_KEY}",
}

def fetch(path):
    req = urllib.request.Request(SUPABASE_URL + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def title_case(s):
    return " ".join(w.capitalize() for w in s.lower().split())

print("Fetching NSW suburb names from Supabase...")
print("(Uses the public anon key — no secret key required)\n")

all_suburbs = set()
page_size   = 1000
offset      = 0

while True:
    path = (
        f"/rest/v1/property_sales"
        f"?select=suburb&state=eq.NSW"
        f"&order=suburb&limit={page_size}&offset={offset}"
    )
    try:
        rows = fetch(path)
    except Exception as e:
        print(f"Error at offset {offset}: {e}")
        sys.exit(1)

    if not rows:
        break

    for row in rows:
        s = (row.get("suburb") or "").strip()
        if s:
            all_suburbs.add(s)

    new_unique = len(all_suburbs)
    print(f"  Page {offset // page_size + 1:>3}: fetched {len(rows)} rows — {new_unique} unique suburbs so far")

    if len(rows) < page_size:
        break
    offset += page_size

suburbs_sorted = sorted(all_suburbs, key=lambda s: s.lower())
suburbs_display = [title_case(s) for s in suburbs_sorted]

print(f"\nTotal unique NSW suburbs: {len(suburbs_display)}")
print(f"Sample: {', '.join(suburbs_display[:8])}, ...")

output = {
    "generated":     __import__('datetime').date.today().isoformat(),
    "total_suburbs": len(suburbs_display),
    "suburbs":       suburbs_display,
}

with open("nsw-suburbs.json", "w") as f:
    json.dump(output, f, separators=(",", ":"))

print("\nWritten to nsw-suburbs.json")
print("→ Commit this file and deploy alongside search.html")
