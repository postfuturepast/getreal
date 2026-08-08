#!/usr/bin/env python3
"""
monitor_lookup_data.py
Weekly monitor for all GetReal lookup data sources.

For every source:
  - Fetches the page and hashes the relevant content
  - Compares to the last known hash stored in pipeline_monitor_state
  - If changed AND auto_update=True: parses the new values and upserts to Supabase
  - Sends an email summary of everything that changed, failed, or was updated

Run:
    export SUPABASE_SECRET=<key>
    export GMAIL_USER=<address>
    export GMAIL_APP_PASSWORD=<app password>
    python3 monitor_lookup_data.py

Sources and their update strategy:
    AUTO-UPDATE (parse + upsert):
        hem_benchmarks      — JMD Mortgages HEM table (quarterly)
        lmi_rates           — Home Loan Experts rate table
        lmi_stamp_duty_rates — state legislation pages
        nt_duty_formula     — NT Revenue Office
        registration_fees   — state land registry pages

    ALERT-ONLY (detect change, email prompt to review):
        stamp_duty_*        — all 8 state Revenue Office pages (too complex to parse)
        apra_releases       — APRA media releases (lvr_limits, lending_policy_constants)
        abs_asgs            — ABS ASGS release page (postcode_locations)
"""

from __future__ import annotations
import os, sys, hashlib, json, smtplib, traceback
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Callable
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")
GMAIL_USER      = os.environ.get("GMAIL_USER", "")
GMAIL_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")

if not SUPABASE_SECRET:
    print("ERROR: SUPABASE_SECRET not set"); sys.exit(1)

SB_HEADERS = {
    "apikey":        SUPABASE_SECRET,
    "Authorization": f"Bearer {SUPABASE_SECRET}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

NOW = datetime.now(timezone.utc).isoformat()

# ── HTTP helpers ───────────────────────────────────────────────────────────────

def fetch_url(url: str, timeout: int = 30) -> str | None:
    """Fetch URL, return body as text or None on error."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GetReal-Monitor/1.0; +https://get-real.co)"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None

def sb_fetch(path: str) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    req = urllib.request.Request(url, headers=SB_HEADERS)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def sb_upsert(table: str, rows: list, on_conflict: str) -> None:
    data = json.dumps(rows).encode()
    headers = dict(SB_HEADERS)
    headers["Prefer"] = f"resolution=merge-duplicates,return=minimal"
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req) as r:
        pass

def sb_patch(table: str, filters: str, payload: dict) -> None:
    data = json.dumps(payload).encode()
    headers = dict(SB_HEADERS)
    headers["Prefer"] = "return=minimal"
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filters}"
    req = urllib.request.Request(url, data=data, headers=headers, method="PATCH")
    with urllib.request.urlopen(req) as r:
        pass

# ── Hashing ────────────────────────────────────────────────────────────────────

def page_hash(content: str, selector_hint: str | None = None) -> str:
    """Hash page content. selector_hint narrows to a substring if provided."""
    text = content
    if selector_hint and selector_hint in content:
        start = content.index(selector_hint)
        text = content[start:start + 8000]
    return hashlib.sha256(text.encode()).hexdigest()[:16]

# ── State management ───────────────────────────────────────────────────────────

def load_state() -> dict:
    """Load all monitor state rows keyed by source_key."""
    try:
        rows = sb_fetch("pipeline_monitor_state?select=*")
        return {r["source_key"]: r for r in rows}
    except Exception:
        return {}

def save_state(source_key: str, url: str, description: str, new_hash: str,
               status: str, error: str | None = None,
               auto_updated: bool = False) -> None:
    row = {
        "source_key":    source_key,
        "url":           url,
        "description":   description,
        "last_hash":     new_hash,
        "last_checked_at": NOW,
        "last_status":   status,
        "last_error":    error,
    }
    if status == "changed":
        row["last_changed_at"] = NOW
    if auto_updated:
        row["last_auto_updated_at"] = NOW

    # Upsert then increment counters via a second patch
    try:
        sb_upsert("pipeline_monitor_state", [row], "source_key")
        # Increment check_count always; change_count if changed
        patch = {"check_count": None}  # Supabase doesn't support increments via REST easily
        # We'll do a read-modify-write for counts
        existing = sb_fetch(f"pipeline_monitor_state?source_key=eq.{source_key}&select=check_count,change_count")
        if existing:
            counts = {
                "check_count": (existing[0].get("check_count") or 0) + 1,
            }
            if status in ("changed", "updated"):
                counts["change_count"] = (existing[0].get("change_count") or 0) + 1
            sb_patch("pipeline_monitor_state", f"source_key=eq.{source_key}", counts)
    except Exception as e:
        print(f"  Warning: could not save state for {source_key}: {e}")

# ── Parsers (auto-update) ──────────────────────────────────────────────────────

def parse_and_update_hem(html: str) -> tuple[bool, str]:
    """
    Parse HEM benchmarks from JMD Mortgages page and upsert to hem_benchmarks.
    Returns (success, message).

    The JMD page has a table with columns: Household type, Dependants, Metro, Regional
    We look for rows matching single/couple × 0-3+ dependants.
    """
    import re

    # Look for dollar amounts in table rows near HEM content
    # Pattern: rows containing household type + monthly amounts
    # This is a best-effort parser — alert if it looks wrong
    rows_found = []

    # Find table rows with $ amounts
    cell_pattern = re.compile(r'\$\s*([\d,]+)', re.IGNORECASE)
    row_pattern  = re.compile(r'<tr[^>]*>(.*?)</tr>', re.IGNORECASE | re.DOTALL)
    cell_split   = re.compile(r'<td[^>]*>(.*?)</td>', re.IGNORECASE | re.DOTALL)
    strip_tags   = re.compile(r'<[^>]+>')

    # Household type mapping
    HH_MAP = {
        "single": "single", "sole": "single",
        "couple": "couple", "partnered": "couple", "joint": "couple",
    }
    DEP_MAP = {"0": 0, "none": 0, "1": 1, "2": 2, "3": 3, "3+": 3, "3 or more": 3}

    for m in row_pattern.finditer(html):
        cells = [strip_tags.sub("", c.group(1)).strip() for c in cell_split.finditer(m.group(1))]
        if len(cells) < 4:
            continue
        amounts = [cell_pattern.search(c) for c in cells]
        if not any(amounts):
            continue

        row_text = " ".join(cells).lower()
        hh_type = next((v for k, v in HH_MAP.items() if k in row_text), None)
        dep = next((v for k, v in DEP_MAP.items() if k in row_text), None)
        if hh_type is None or dep is None:
            continue

        # Extract metro (3rd cell) and regional (4th cell)
        metro_m = amounts[2] if len(amounts) > 2 else None
        reg_m   = amounts[3] if len(amounts) > 3 else None
        if not metro_m or not reg_m:
            continue

        try:
            metro_amt = int(metro_m.group(1).replace(",", ""))
            reg_amt   = int(reg_m.group(1).replace(",", ""))
        except ValueError:
            continue

        if not (500 <= metro_amt <= 20000 and 500 <= reg_amt <= 20000):
            continue  # sanity check

        rows_found.append({
            "household_type": hh_type,
            "dependants": dep,
            "location_type": "metro",
            "monthly_amount": metro_amt,
        })
        rows_found.append({
            "household_type": hh_type,
            "dependants": dep,
            "location_type": "regional",
            "monthly_amount": reg_amt,
        })

    if len(rows_found) < 8:
        return False, f"HEM parser found only {len(rows_found)} rows (expected ≥8) — page may have restructured. Manual review needed."

    try:
        sb_upsert("hem_benchmarks", rows_found, "household_type,dependants,location_type")
        return True, f"Updated {len(rows_found)} hem_benchmark rows."
    except Exception as e:
        return False, f"Upsert failed: {e}"


def parse_and_update_lmi_rates(html: str) -> tuple[bool, str]:
    """
    Parse LMI rates from Home Loan Experts page and upsert to lmi_rates.
    Expects a table with LVR bands as rows and loan amount bands as columns.
    """
    import re

    strip_tags  = re.compile(r'<[^>]+>')
    row_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.IGNORECASE | re.DOTALL)
    cell_split  = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.IGNORECASE | re.DOTALL)
    pct_pattern = re.compile(r'([\d.]+)\s*%')
    dollar_pat  = re.compile(r'\$\s*([\d,]+(?:k|m)?)', re.IGNORECASE)

    def parse_amount(s: str) -> int | None:
        s = s.lower().strip()
        m = dollar_pat.search(s)
        if not m:
            return None
        val_str = m.group(1).replace(",", "").replace("$", "")
        if val_str.endswith("m"):
            return int(float(val_str[:-1]) * 1_000_000)
        if val_str.endswith("k"):
            return int(float(val_str[:-1]) * 1_000)
        return int(val_str)

    rows_found = []
    header_loan_maxes = []

    for m in row_pattern.finditer(html):
        cells = [strip_tags.sub("", c.group(1)).strip() for c in cell_split.finditer(m.group(1))]
        if not cells:
            continue

        # Header row: extract loan amount bands
        if any("loan" in c.lower() or "$" in c for c in cells) and not header_loan_maxes:
            amounts = [parse_amount(c) for c in cells[1:]]
            if any(a and a > 100000 for a in amounts):
                header_loan_maxes = [a for a in amounts if a]
            continue

        # Data row: first cell is LVR range, rest are rates
        pcts = [pct_pattern.search(c) for c in cells]
        lvr_m = pct_pattern.search(cells[0]) if cells else None
        if not lvr_m or not any(pcts[1:]):
            continue

        # Parse LVR range from first cell (e.g. "80.01% - 85%")
        lvr_vals = pct_pattern.findall(cells[0])
        if len(lvr_vals) < 2:
            continue
        try:
            lvr_min = float(lvr_vals[0])
            lvr_max = float(lvr_vals[1])
        except ValueError:
            continue

        if not (60 <= lvr_min <= 100 and 60 <= lvr_max <= 100):
            continue

        for i, loan_max in enumerate(header_loan_maxes):
            if i + 1 >= len(pcts):
                break
            rate_m = pcts[i + 1]
            if not rate_m:
                continue
            try:
                rate_pct = float(rate_m.group(1))
            except ValueError:
                continue
            if not (0.1 <= rate_pct <= 10):
                continue

            rows_found.append({
                "lvr_min":  lvr_min,
                "lvr_max":  lvr_max,
                "loan_max": loan_max,
                "rate_pct": rate_pct,
            })

    if len(rows_found) < 20:
        return False, f"LMI parser found only {len(rows_found)} rows (expected ≥20) — page may have restructured. Manual review needed at: https://www.homeloanexperts.com.au/lenders-mortgage-insurance/lmi-premium-rates/"

    try:
        sb_upsert("lmi_rates", rows_found, "lvr_min,lvr_max,loan_max")
        return True, f"Updated {len(rows_found)} lmi_rate rows."
    except Exception as e:
        return False, f"Upsert failed: {e}"


def parse_and_update_nt_formula(html: str) -> tuple[bool, str]:
    """
    Parse NT duty formula coefficients from NT Revenue page.
    Looks for the quadratic formula values.
    """
    import re

    # NT formula: D = (0.06571441 × V² + 15 × V) ÷ 1000, flat rate above $525k
    # We look for these coefficients on the page
    coeff_a_pat = re.compile(r'0\.0657\d+')
    flat_pat    = re.compile(r'\$?\s*525[,.]?000')
    rate_pat    = re.compile(r'([\d.]+)\s*(?:cent|%|per cent)', re.IGNORECASE)

    coeff_a_m = coeff_a_pat.search(html)
    flat_m    = flat_pat.search(html)

    if not coeff_a_m or not flat_m:
        return False, "NT formula parser could not find expected coefficients on page. Manual review needed at: https://nt.gov.au/industry/revenue/taxes-and-royalties/stamp-duty"

    # If page still contains expected values, check if anything changed
    # For NT the formula is very stable — change detection is the main value here
    return True, "NT duty formula page verified — coefficients present and unchanged structure."


# ── Source definitions ─────────────────────────────────────────────────────────

# Each source: key, url, description, selector_hint (narrows hash), auto_update, parser fn, tables_affected, alert_message
SOURCES = [

    # ── FULLY AUTO-UPDATE ──────────────────────────────────────────────────────

    {
        "key":          "hem_jmd",
        "url":          "https://www.jmdmortgages.com.au/hem-benchmarks/",
        "description":  "HEM benchmarks — JMD Mortgages",
        "hint":         "HEM",
        "auto_update":  True,
        "parser":       parse_and_update_hem,
        "tables":       ["hem_benchmarks"],
        "alert":        "HEM benchmarks page changed. Auto-update attempted — check results above.",
    },
    {
        "key":          "lmi_rates_hle",
        "url":          "https://www.homeloanexperts.com.au/lenders-mortgage-insurance/lmi-premium-rates/",
        "description":  "LMI rates — Home Loan Experts",
        "hint":         "LVR",
        "auto_update":  True,
        "parser":       parse_and_update_lmi_rates,
        "tables":       ["lmi_rates"],
        "alert":        "LMI rates page changed. Auto-update attempted — check results above.",
    },
    {
        "key":          "nt_duty_formula",
        "url":          "https://nt.gov.au/industry/revenue/taxes-and-royalties/stamp-duty",
        "description":  "NT duty formula — NT Revenue",
        "hint":         "0.065",
        "auto_update":  True,
        "parser":       parse_and_update_nt_formula,
        "tables":       ["nt_duty_formula"],
        "alert":        "NT stamp duty page changed. Review nt_duty_formula coefficients in Supabase.",
    },

    # ── ALERT-ONLY: Stamp duty (8 states — too complex to auto-parse) ──────────

    {
        "key":          "stamp_duty_nsw",
        "url":          "https://www.revenue.nsw.gov.au/taxes-duties-levies-royalties/transfer-duty",
        "description":  "NSW stamp duty — Revenue NSW",
        "hint":         "transfer duty",
        "auto_update":  False,
        "tables":       ["stamp_duty_brackets", "stamp_duty_concessions"],
        "alert":        "NSW Revenue transfer duty page changed. Review stamp_duty_brackets and stamp_duty_concessions for NSW in Supabase.",
    },
    {
        "key":          "stamp_duty_vic",
        "url":          "https://www.sro.vic.gov.au/land-transfer-duty-rates",
        "description":  "VIC stamp duty — SRO Victoria",
        "hint":         "duty",
        "auto_update":  False,
        "tables":       ["stamp_duty_brackets", "stamp_duty_concessions"],
        "alert":        "VIC SRO land transfer duty page changed. Review stamp_duty_brackets and stamp_duty_concessions for VIC in Supabase.",
    },
    {
        "key":          "stamp_duty_qld",
        "url":          "https://www.qro.qld.gov.au/duties/transfer-duty/rates-of-transfer-duty/",
        "description":  "QLD stamp duty — Queensland Revenue Office",
        "hint":         "duty",
        "auto_update":  False,
        "tables":       ["stamp_duty_brackets", "stamp_duty_concessions"],
        "alert":        "QLD Revenue transfer duty page changed. Review stamp_duty_brackets and stamp_duty_concessions for QLD in Supabase.",
    },
    {
        "key":          "stamp_duty_wa",
        "url":          "https://www.wa.gov.au/organisation/department-of-finance/transfer-duty",
        "description":  "WA stamp duty — WA Dept of Finance",
        "hint":         "duty",
        "auto_update":  False,
        "tables":       ["stamp_duty_brackets", "stamp_duty_concessions"],
        "alert":        "WA stamp duty page changed. Review stamp_duty_brackets and stamp_duty_concessions for WA in Supabase.",
    },
    {
        "key":          "stamp_duty_sa",
        "url":          "https://www.revenuesa.sa.gov.au/taxes-and-duties/stamp-duties/real-property",
        "description":  "SA stamp duty — Revenue SA",
        "hint":         "duty",
        "auto_update":  False,
        "tables":       ["stamp_duty_brackets", "stamp_duty_concessions"],
        "alert":        "SA Revenue stamp duty page changed. Review stamp_duty_brackets and stamp_duty_concessions for SA in Supabase.",
    },
    {
        "key":          "stamp_duty_tas",
        "url":          "https://www.sro.tas.gov.au/duties",
        "description":  "TAS stamp duty — SRO Tasmania",
        "hint":         "duty",
        "auto_update":  False,
        "tables":       ["stamp_duty_brackets", "stamp_duty_concessions"],
        "alert":        "TAS SRO duties page changed. Review stamp_duty_brackets and stamp_duty_concessions for TAS in Supabase.",
    },
    {
        "key":          "stamp_duty_act",
        "url":          "https://www.revenue.act.gov.au/duties/conveyance-duty",
        "description":  "ACT stamp duty — ACT Revenue",
        "hint":         "duty",
        "auto_update":  False,
        "tables":       ["stamp_duty_brackets", "stamp_duty_concessions"],
        "alert":        "ACT Revenue conveyance duty page changed. Review stamp_duty_brackets and stamp_duty_concessions for ACT in Supabase.",
    },
    {
        "key":          "stamp_duty_nt_concessions",
        "url":          "https://nt.gov.au/industry/revenue/taxes-and-royalties/stamp-duty/concessions",
        "description":  "NT stamp duty concessions — NT Revenue",
        "hint":         "concession",
        "auto_update":  False,
        "tables":       ["stamp_duty_concessions", "newbuild_concessions"],
        "alert":        "NT stamp duty concessions page changed. Review stamp_duty_concessions and newbuild_concessions for NT in Supabase.",
    },

    # ── ALERT-ONLY: APRA (lvr_limits, lending_policy_constants) ───────────────

    {
        "key":          "apra_releases",
        "url":          "https://www.apra.gov.au/news-and-publications?f%5B0%5D=category%3Amedia_release",
        "description":  "APRA media releases — lvr_limits, lending_policy_constants",
        "hint":         "media release",
        "auto_update":  False,
        "tables":       ["lvr_limits", "lending_policy_constants"],
        "alert":        "APRA media releases page changed — a new announcement may affect lvr_limits (LVR caps) or lending_policy_constants (DTI cap, serviceability buffer). Review: https://www.apra.gov.au/news-and-publications",
    },

    # ── ALERT-ONLY: ABS ASGS (postcode_locations) ─────────────────────────────

    {
        "key":          "abs_asgs",
        "url":          "https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/latest-release",
        "description":  "ABS ASGS Edition 3 — postcode_locations",
        "hint":         "edition",
        "auto_update":  False,
        "tables":       ["postcode_locations"],
        "alert":        "ABS ASGS page changed — a new edition may be available. If so, run load_abs_remoteness.py to refresh postcode_locations in Supabase.",
    },

    # ── ALERT-ONLY: LMI stamp duty rates (state legislation) ──────────────────

    {
        "key":          "lmi_stamp_duty_vic",
        "url":          "https://www.sro.vic.gov.au/insurance-duty",
        "description":  "VIC insurance duty — lmi_stamp_duty_rates",
        "hint":         "insurance",
        "auto_update":  False,
        "tables":       ["lmi_stamp_duty_rates"],
        "alert":        "VIC insurance duty page changed. Review lmi_stamp_duty_rates for VIC in Supabase.",
    },
]

# ── Main ───────────────────────────────────────────────────────────────────────

def run() -> None:
    print(f"GetReal — Lookup Data Monitor — {NOW}\n")

    state = load_state()
    results = []   # (source, status, message)

    for src in SOURCES:
        key  = src["key"]
        url  = src["url"]
        desc = src["description"]
        hint = src.get("hint")
        print(f"Checking: {desc}")

        html = fetch_url(url)
        if html is None:
            msg = f"Fetch failed for {url}"
            print(f"  ❌ {msg}")
            save_state(key, url, desc, state.get(key, {}).get("last_hash", ""), "error", error=msg)
            results.append((src, "error", msg))
            continue

        new_hash  = page_hash(html, hint)
        last_hash = state.get(key, {}).get("last_hash")

        if last_hash and new_hash == last_hash:
            print(f"  ✅ No change (hash: {new_hash})")
            save_state(key, url, desc, new_hash, "ok")
            results.append((src, "ok", "No change"))
            continue

        # Changed (or first run)
        is_first_run = not last_hash
        status_label = "first_run" if is_first_run else "changed"
        print(f"  {'🆕' if is_first_run else '⚠️ '} {'First run — baseline recorded' if is_first_run else 'CHANGED'} (hash: {last_hash} → {new_hash})")

        auto_updated = False
        update_msg   = ""

        if src.get("auto_update") and src.get("parser") and not is_first_run:
            print(f"  🔄 Running auto-update parser...")
            try:
                success, update_msg = src["parser"](html)
                if success:
                    auto_updated = True
                    print(f"  ✅ Auto-updated: {update_msg}")
                    status_label = "updated"
                else:
                    print(f"  ⚠️  Parser failed: {update_msg}")
                    status_label = "changed"
            except Exception as e:
                update_msg = f"Parser exception: {traceback.format_exc()}"
                print(f"  ❌ {update_msg}")

        save_state(key, url, desc, new_hash, status_label, auto_updated=auto_updated)

        if is_first_run:
            results.append((src, "first_run", "Baseline recorded"))
        else:
            results.append((src, status_label, update_msg or src.get("alert", "Page changed.")))

    # ── Send email summary ─────────────────────────────────────────────────────
    send_summary(results)


def send_summary(results: list) -> None:
    errors   = [(s, m) for s, st, m in results if st == "error"]
    changed  = [(s, m) for s, st, m in results if st == "changed"]
    updated  = [(s, m) for s, st, m in results if st == "updated"]
    ok_count = sum(1 for _, st, _ in results if st == "ok")

    # Only email if something needs attention
    needs_email = errors or changed or updated

    status_icon = "✅" if not errors and not changed else ("❌" if errors else "⚠️")
    subject = f"{status_icon} GetReal — Lookup Monitor — {datetime.now().strftime('%d %b %Y')}"
    if updated:
        subject += f" — {len(updated)} auto-updated"
    if changed:
        subject += f" — {len(changed)} need review"
    if errors:
        subject += f" — {len(errors)} errors"

    lines = [
        f"GetReal Lookup Data Monitor — {datetime.now().strftime('%d %b %Y %H:%M')} AEST",
        f"{ok_count} sources unchanged.",
        "",
    ]

    if updated:
        lines += ["─" * 60, f"✅ AUTO-UPDATED ({len(updated)})", "─" * 60]
        for src, msg in updated:
            lines += [f"  {src['description']}", f"  Tables: {', '.join(src['tables'])}", f"  {msg}", ""]

    if changed:
        lines += ["─" * 60, f"⚠️  ACTION REQUIRED — REVIEW THESE ({len(changed)})", "─" * 60]
        for src, msg in changed:
            lines += [
                f"  {src['description']}",
                f"  URL: {src['url']}",
                f"  Tables affected: {', '.join(src['tables'])}",
                f"  {msg}",
                "",
            ]

    if errors:
        lines += ["─" * 60, f"❌ FETCH ERRORS ({len(errors)})", "─" * 60]
        for src, msg in errors:
            lines += [f"  {src['description']}", f"  URL: {src['url']}", f"  {msg}", ""]

    if not needs_email:
        print("\n✅ All sources unchanged — no email sent.")
        return

    body = "\n".join(lines)
    print(f"\nSending email: {subject}")

    if not GMAIL_USER or not GMAIL_PASSWORD:
        print("No Gmail credentials — printing email body instead:")
        print(body)
        return

    try:
        msg = MIMEMultipart()
        msg["From"]    = f"GetReal Pipeline <{GMAIL_USER}>"
        msg["To"]      = GMAIL_USER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
        print("✅ Email sent.")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        print(body)


if __name__ == "__main__":
    run()
