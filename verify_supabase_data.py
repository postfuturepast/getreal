#!/usr/bin/env python3
"""
verify_supabase_data.py
Smoke-tests all Supabase lookup tables used by GetReal.
Run: SUPABASE_SECRET=<key> python3 verify_supabase_data.py
"""

import os, sys, json
import urllib.request

SUPABASE_URL = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
ANON_KEY = "sb_publishable_1jyBD0hVdHX2ieqFIlC51A_A3ep39Bc"

SECRET = os.environ.get("SUPABASE_SECRET")
if not SECRET:
    print("ERROR: SUPABASE_SECRET env var not set.")
    sys.exit(1)

HEADERS = {
    "apikey": SECRET,
    "Authorization": f"Bearer {SECRET}",
    "Content-Type": "application/json",
}

ANON_HEADERS = {
    "apikey": ANON_KEY,
    "Authorization": f"Bearer {ANON_KEY}",
    "Content-Type": "application/json",
}

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

errors = 0

def fetch(path):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def anon_fetch(table):
    """Fetch a single row via the anon key — tests frontend read access.
    Returns (ok, error_msg). Fails if HTTP error OR if RLS blocks and returns empty array."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?limit=1"
    req = urllib.request.Request(url, headers=ANON_HEADERS)
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            if isinstance(data, list) and len(data) == 0:
                return False, "RLS blocked — returned empty array (GRANT exists but no policy)"
            return True, None
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code} — missing GRANT"
    except Exception as e:
        return False, str(e)

def check(condition, msg):
    global errors
    icon = PASS if condition else FAIL
    print(f"  {icon} {msg}")
    if not condition:
        errors += 1

def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ── 1. lending_policy_constants ───────────────────────────────
section("lending_policy_constants")
try:
    rows = fetch("lending_policy_constants?select=key,value")
    kv = {r["key"]: r["value"] for r in rows}
    print(f"  Rows: {len(rows)}")
    for key in ["dti_multiplier", "stress_rate_buffer_pct", "cc_repayment_rate", "loan_term_months"]:
        present = key in kv
        check(present, f"key '{key}' present" + (f" = {kv[key]}" if present else ""))
    # Sanity-check values
    if "dti_multiplier" in kv:
        check(4 <= float(kv["dti_multiplier"]) <= 10, f"dti_multiplier in reasonable range (4–10)")
    if "stress_rate_buffer_pct" in kv:
        check(1 <= float(kv["stress_rate_buffer_pct"]) <= 5, f"stress_rate_buffer_pct in reasonable range (1–5%)")
    if "cc_repayment_rate" in kv:
        check(0.01 <= float(kv["cc_repayment_rate"]) <= 0.05, f"cc_repayment_rate in reasonable range (1–5%)")
    if "loan_term_months" in kv:
        check(float(kv["loan_term_months"]) in [300, 360], f"loan_term_months is 300 or 360")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── 2. lvr_limits ─────────────────────────────────────────────
section("lvr_limits")
try:
    rows = fetch("lvr_limits?select=property_type,is_owner_occupier,max_lvr")
    print(f"  Rows: {len(rows)}")
    combos = {(r["property_type"], r["is_owner_occupier"]): float(r["max_lvr"]) for r in rows}
    expected = [
        ("apartment", True,  0.90),
        ("apartment", False, 0.80),
        ("standard",  True,  0.95),
        ("standard",  False, 0.90),
    ]
    for pt, oo, expected_lvr in expected:
        key = (pt, oo)
        present = key in combos
        check(present, f"({pt}, oo={oo}) present" + (f" → max_lvr={combos[key]}" if present else ""))
        if present:
            check(combos[key] == expected_lvr, f"  max_lvr {combos[key]} matches expected {expected_lvr}")
    # Confirm max_lvr is stored as decimal (0.x), not percentage (xx)
    for r in rows:
        check(0 < float(r["max_lvr"]) <= 1, f"max_lvr={r['max_lvr']} is decimal (not percentage)")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── 3. benchmark_rates ────────────────────────────────────────
section("benchmark_rates")
try:
    # Filter to the rows fetchLendingData() uses: pi repayment, new loans, no LVR/size filter
    rows = fetch(
        "benchmark_rates?select=purpose,rate_pct,reference_month"
        "&repayment_type=eq.pi&loan_status=eq.new"
        "&rate_type=is.null&lvr_band=is.null&loan_size_band=is.null"
        "&order=reference_month.desc&limit=4"
    )
    print(f"  Rows returned: {len(rows)}")
    # Most recent row per purpose
    by_purpose = {}
    for r in rows:
        if r["purpose"] not in by_purpose:
            by_purpose[r["purpose"]] = r
    for pt in ["oo", "investor"]:
        present = pt in by_purpose
        check(present, f"purpose '{pt}' present" + (f" → rate_pct={by_purpose[pt]['rate_pct']}%, month={by_purpose[pt]['reference_month']}" if present else ""))
        if present:
            check(3 <= float(by_purpose[pt]["rate_pct"]) <= 15, f"rate_pct {by_purpose[pt]['rate_pct']} in plausible range (3–15%)")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── 4. stamp_duty_brackets ────────────────────────────────────
section("stamp_duty_brackets")
try:
    rows = fetch("stamp_duty_brackets?select=state,bracket_set&order=state.asc")
    states_found = sorted(set(r["state"].strip() for r in rows))
    print(f"  Rows: {len(rows)}  States: {', '.join(states_found)}")
    expected_states = ["ACT", "NSW", "QLD", "SA", "TAS", "VIC", "WA"]
    for s in expected_states:
        check(s in states_found, f"State '{s}' has brackets")
    # NT uses formula, not brackets — warn if missing rather than fail
    if "NT" not in states_found:
        print(f"  {WARN} NT not in stamp_duty_brackets (expected — NT uses nt_duty_formula)")
    # VIC should have both bracket_sets
    vic_sets = set(r["bracket_set"] for r in rows if r["state"].strip() == "VIC")
    check("standard" in vic_sets, "VIC has 'standard' bracket_set")
    check("vic_ppr" in vic_sets, "VIC has 'vic_ppr' bracket_set")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── 5. stamp_duty_concessions ─────────────────────────────────
section("stamp_duty_concessions")
try:
    rows = fetch("stamp_duty_concessions?select=state,concession_key")
    print(f"  Rows: {len(rows)}")
    check(len(rows) > 0, "Table has rows")
    states_found = set(r["state"] for r in rows)
    # At minimum NSW and VIC should have concessions
    for s in ["NSW", "VIC"]:
        check(s in states_found, f"State '{s}' has concessions")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── 6. nt_duty_formula ────────────────────────────────────────
section("nt_duty_formula")
try:
    rows = fetch("nt_duty_formula?select=formula_threshold,coeff_a,coeff_b,divisor,flat_rate_above")
    print(f"  Rows: {len(rows)}")
    check(len(rows) == 1, "Exactly 1 row")
    if rows:
        r = rows[0]
        check(r["formula_threshold"] == 525000, f"formula_threshold = {r['formula_threshold']} (expected 525000)")
        check(r["divisor"] is not None, f"divisor present = {r['divisor']}")
        check(r["flat_rate_above"] is not None, f"flat_rate_above present = {r['flat_rate_above']}")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── 7. registration_fees ──────────────────────────────────────
section("registration_fees")
try:
    rows = fetch("registration_fees?select=state,fee_type,amount")
    print(f"  Rows: {len(rows)}")
    by_state = {}
    for r in rows:
        by_state.setdefault(r["state"].strip(), set()).add(r["fee_type"])
    expected_states = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
    for s in expected_states:
        has_transfer  = s in by_state and "transfer"  in by_state[s]
        has_mortgage  = s in by_state and "mortgage"  in by_state[s]
        check(has_transfer,  f"{s} has 'transfer' fee")
        check(has_mortgage,  f"{s} has 'mortgage' fee")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── 8. lmi_rates ──────────────────────────────────────────────
section("lmi_rates")
try:
    rows = fetch("lmi_rates?select=lvr_min,lvr_max,loan_max,rate_pct")
    print(f"  Rows: {len(rows)} (expected 75 = 15 LVR bands × 5 loan bands)")
    check(len(rows) == 75, f"Row count = {len(rows)}")
    # Check LVR values are stored as percentages (80, 90), not decimals (0.8, 0.9)
    bad_lvr = [r for r in rows if not (0 < float(r["lvr_min"]) <= 100) or not (0 < float(r["lvr_max"]) <= 100)]
    check(len(bad_lvr) == 0, f"All LVR values are in percentage range (0–100)")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── 9. hem_benchmarks ─────────────────────────────────────────
section("hem_benchmarks")
try:
    rows = fetch("hem_benchmarks?select=household_type,dependants,location_type,monthly_amount")
    print(f"  Rows: {len(rows)} (expected 14)")
    check(len(rows) == 14, f"Row count = {len(rows)}")
    types_found = set(r["household_type"] for r in rows)
    for ht in ["single", "couple"]:
        check(ht in types_found, f"household_type '{ht}' present")
    locs_found = set(r["location_type"] for r in rows)
    for lt in ["metro", "regional"]:
        check(lt in locs_found, f"location_type '{lt}' present")
    # Sanity: all monthly amounts > 0
    bad_hem = [r for r in rows if float(r["monthly_amount"]) <= 0]
    check(len(bad_hem) == 0, "All monthly_amount values > 0")
except Exception as e:
    print(f"  {FAIL} Fetch failed: {e}"); errors += 1


# ── Frontend (anon key) read access ──────────────────────────
# All tables read by deposit.html / ask.js must be accessible via the anon key.
# If any fail here, run: GRANT SELECT ON public.<table> TO anon, authenticated;
section("Frontend anon key access (deposit.html / ask.js)")
FRONTEND_TABLES = [
    "lending_policy_constants",
    "lvr_limits",
    "benchmark_rates",
    "stamp_duty_brackets",
    "stamp_duty_concessions",
    "nt_duty_formula",
    "registration_fees",
    "lmi_rates",
    "lmi_stamp_duty_rates",
    "hem_benchmarks",
    "postcode_locations",
]
for table in FRONTEND_TABLES:
    ok, err = anon_fetch(table)
    check(ok, f"{table} readable by anon key" + (f" — {err}" if err else ""))


# ── Summary ───────────────────────────────────────────────────
print(f"\n{'═'*60}")
if errors == 0:
    print(f"  {PASS} All checks passed.")
else:
    print(f"  {FAIL} {errors} check(s) failed — see above.")
print(f"{'═'*60}\n")
sys.exit(0 if errors == 0 else 1)
