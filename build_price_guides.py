#!/usr/bin/env python3
"""
build_price_guides.py — GetReal Series B: "Can I afford a $Y property?"
=========================================================================
Generates static HTML pages at:
  guides/can-i-afford/{price}/index.html

One page per price point: $300k–$3M in $50k steps = 55 pages.

All stamp duty, rates, and tax data are read from Supabase at build time:
  - stamp_duty_brackets    → state/bracket/rate data for all 8 states
  - stamp_duty_concessions → FHB thresholds, taper rates, discount %
  - nt_duty_formula        → NT's unique quadratic formula
  - lmi_rates              → LVR-based LMI premium rates
  - lmi_stamp_duty_rates   → state stamp duty on LMI premium
  - reference_rates        → RBA cash rate + assessment buffer
  - income_tax_brackets    → ATO marginal rates (for income-required calc)
  - lito_rates             → LITO offset parameters
  - suburb_analytics       → example suburbs near this price point

Usage:
    export SUPABASE_SECRET=<secret>
    python3 build_price_guides.py

Output:
    guides/can-i-afford/{price}/index.html   (55 pages)
    guides/can-i-afford/index.html
    sitemap-guides-b.xml
"""

import json
import math
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests

# ── Config ──────────────────────────────────────────────────────────────────────

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET", "")

BASE_URL   = "https://get-real.co"
TODAY      = date.today().isoformat()
OUT_DIR    = Path("guides/can-i-afford")

PRICE_MIN  = 300_000
PRICE_MAX  = 3_000_000
PRICE_STEP = 50_000

LOAN_TERM_YEARS  = 30
LOAN_TERM_MONTHS = LOAN_TERM_YEARS * 12

STATES = ["NSW", "VIC", "QLD", "WA", "SA", "ACT", "TAS", "NT"]

# HEM metro single (used for income-required calc)
HEM_METRO_SINGLE = 2_800

# ── Supabase helpers ─────────────────────────────────────────────────────────────

def sb_get(table, params=""):
    headers = {
        "apikey":        SUPABASE_SECRET,
        "Authorization": f"Bearer {SUPABASE_SECRET}",
    }
    url = f"{SUPABASE_URL}/rest/v1/{table}?{params}"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def load_reference_rates():
    rows = sb_get("reference_rates", "select=key,value,effective_date")
    return {r["key"]: float(r["value"]) for r in rows}


def load_tax_brackets():
    rows = sb_get(
        "income_tax_brackets",
        "select=effective_year,bracket_min,bracket_max,base_amount,rate"
        "&order=effective_year.desc,bracket_min.asc"
    )
    latest_year = rows[0]["effective_year"]
    return [r for r in rows if r["effective_year"] == latest_year], latest_year


def load_lito():
    rows = sb_get("lito_rates", "select=*&order=effective_year.desc&limit=1")
    return rows[0]


def load_stamp_duty_data():
    brackets    = sb_get("stamp_duty_brackets",    "select=*&order=state,bracket_set,bracket_min")
    concessions = sb_get("stamp_duty_concessions", "select=*")
    nt_formula  = sb_get("nt_duty_formula",        "select=*&limit=1")
    return brackets, concessions, nt_formula[0] if nt_formula else None


def load_lmi_data():
    rates     = sb_get("lmi_rates",           "select=*&order=lvr_min,loan_max")
    sd_rates  = sb_get("lmi_stamp_duty_rates","select=state,rate_pct")
    return rates, {r["state"]: float(r["rate_pct"]) / 100 for r in sd_rates}


def load_suburbs_near_price(target_price, limit=8):
    low  = int(target_price * 0.88)
    high = int(target_price * 1.12)
    params = (
        f"select=suburb_display,state,median_price,annual_sales,property_type"
        f"&median_price=gte.{low}&median_price=lte.{high}"
        f"&annual_sales=gte.20"
        f"&order=annual_sales.desc"
        f"&limit={limit}"
    )
    return sb_get("suburb_analytics", params)


# ── Tax calculation (same as build_income_guides.py) ────────────────────────────

def calc_income_tax(gross, brackets, lito_params, medicare_rate):
    raw_tax = 0.0
    for b in brackets:
        bmin = b["bracket_min"]
        bmax = b["bracket_max"]
        base = b["base_amount"]
        rate = float(b["rate"])
        if gross > bmin:
            top = min(gross, bmax) if bmax is not None else gross
            raw_tax = base + (top - bmin) * rate

    lito = float(lito_params["max_offset"])
    if gross > lito_params["phase_out_start"]:
        excess = min(gross, lito_params["phase_out_end_1"]) - lito_params["phase_out_start"]
        lito  -= excess * float(lito_params["phase_out_rate_1"])
    if gross > lito_params["phase_out_end_1"]:
        excess = min(gross, lito_params["phase_out_end_2"]) - lito_params["phase_out_end_1"]
        lito  -= excess * float(lito_params["phase_out_rate_2"])
    lito = max(0.0, lito)

    medicare = gross * medicare_rate if gross > 26_000 else 0.0
    net_tax  = max(0.0, raw_tax - lito) + medicare
    return round(net_tax), round(gross - net_tax), round((gross - net_tax) / 12)


def income_required_for_loan(loan_amount, assessment_rate_pct, brackets, lito_params, medicare_rate):
    """
    Binary-search for the gross income required to service `loan_amount`
    at `assessment_rate_pct` with standard HEM and no debt.
    Returns gross annual income (rounded to nearest $1k).
    """
    r = (assessment_rate_pct / 100) / 12
    n = LOAN_TERM_MONTHS
    factor = (1 + r) ** n
    monthly_repayment = loan_amount * r * factor / (factor - 1)
    # Required monthly cash flow after HEM
    required_available = monthly_repayment + HEM_METRO_SINGLE

    # Binary search gross income
    lo, hi = 30_000, 1_000_000
    for _ in range(50):
        mid = (lo + hi) / 2
        _, take_home, _ = calc_income_tax(mid, brackets, lito_params, medicare_rate)
        if take_home / 12 >= required_available:
            hi = mid
        else:
            lo = mid
    return int(round(hi / 1_000) * 1_000)


# ── Stamp duty calculation ───────────────────────────────────────────────────────

def calc_stamp_duty(price, state, bracket_set, brackets_data, concessions_data, nt_formula):
    """
    Calculate stamp duty for a given price, state, and bracket set.
    bracket_set: 'standard' or 'vic_ppr'
    Returns duty in dollars.
    """
    if state == "NT" and nt_formula:
        # NT uses a quadratic formula for prices below threshold
        threshold = float(nt_formula["formula_threshold"])
        if price <= threshold:
            coeff_a  = float(nt_formula["coeff_a"])
            coeff_b  = float(nt_formula["coeff_b"])
            divisor  = float(nt_formula["divisor"])
            V        = price / divisor
            duty     = coeff_a * V * V + coeff_b * V
        else:
            flat_rate = float(nt_formula["flat_rate_above"])
            duty      = price * flat_rate
        return round(duty)

    # Standard bracket calculation for all other states
    state_brackets = [
        b for b in brackets_data
        if b["state"] == state and b["bracket_set"] == bracket_set
    ]
    if not state_brackets:
        # Fallback to 'standard' if requested bracket_set not found
        state_brackets = [b for b in brackets_data if b["state"] == state and b["bracket_set"] == "standard"]

    duty = 0.0
    for b in sorted(state_brackets, key=lambda x: x["bracket_min"]):
        bmin  = float(b["bracket_min"])
        bmax  = float(b["bracket_max"]) if b["bracket_max"] is not None else float("inf")
        base  = float(b["base_amount"])
        rate  = float(b["rate"])
        is_full = b.get("is_full_price", False)

        if price < bmin:
            break
        if bmin <= price <= bmax:
            if is_full:
                # VIC full-price flat rate band — rate applies to entire price
                duty = base + price * rate
            else:
                duty = base + (price - bmin) * rate
            break

    return round(duty)


def calc_fhb_duty(price, state, brackets_data, concessions_data, nt_formula):
    """
    Calculate stamp duty for a first home buyer, applying relevant concessions.
    Returns (fhb_duty, saving, note).
    """
    # Get concessions for this state
    concs = {c["concession_key"]: c["value"] for c in concessions_data if c["state"] == state}

    standard_duty = calc_stamp_duty(price, state, "standard", brackets_data, concessions_data, nt_formula)

    # ── NSW ───────────────────────────────────────────────────────────────────
    if state == "NSW":
        exempt_threshold = float(concs.get("fhb_exempt_threshold", 800_000))
        taper_top        = float(concs.get("fhb_taper_top",       1_000_000))
        if price <= exempt_threshold:
            return 0, standard_duty, f"FHB exemption — properties up to ${exempt_threshold:,.0f}"
        elif price <= taper_top:
            # Tapered concession — linear reduction
            taper_ratio = (taper_top - price) / (taper_top - exempt_threshold)
            fhb_duty    = round(standard_duty * (1 - taper_ratio))
            saving      = standard_duty - fhb_duty
            return fhb_duty, saving, f"FHB partial concession (tapers $800k–$1M)"
        else:
            return standard_duty, 0, "No FHB concession above $1M"

    # ── VIC ───────────────────────────────────────────────────────────────────
    elif state == "VIC":
        # VIC PPR rate applies for owner-occupiers; FHB waiver under $600k
        ppr_cap   = float(concs.get("ppr_price_cap",       600_000))
        fhb_cap   = float(concs.get("fhb_exempt_threshold", 600_000))
        ppr_duty  = calc_stamp_duty(price, state, "vic_ppr", brackets_data, concessions_data, nt_formula)
        if price <= fhb_cap:
            return 0, standard_duty, f"FHB waiver — properties up to ${fhb_cap:,.0f}"
        else:
            return ppr_duty, standard_duty - ppr_duty, "PPR rate — no FHB waiver above $600k"

    # ── QLD ───────────────────────────────────────────────────────────────────
    elif state == "QLD":
        fhb_cap   = float(concs.get("fhb_exempt_threshold", 500_000))
        taper_top = float(concs.get("fhb_taper_top",        550_000))
        if price <= fhb_cap:
            return 0, standard_duty, f"FHB exemption — under ${fhb_cap:,.0f}"
        elif price <= taper_top:
            taper_ratio = (taper_top - price) / (taper_top - fhb_cap)
            fhb_duty    = round(standard_duty * (1 - taper_ratio))
            return fhb_duty, standard_duty - fhb_duty, "FHB partial concession"
        else:
            return standard_duty, 0, "No FHB concession above $550k"

    # ── WA ────────────────────────────────────────────────────────────────────
    elif state == "WA":
        fhb_cap   = float(concs.get("fhb_exempt_threshold", 430_000))
        taper_top = float(concs.get("fhb_taper_top",        530_000))
        if price <= fhb_cap:
            return 0, standard_duty, f"FHB exemption — under ${fhb_cap:,.0f}"
        elif price <= taper_top:
            taper_ratio = (taper_top - price) / (taper_top - fhb_cap)
            fhb_duty    = round(standard_duty * (1 - taper_ratio))
            return fhb_duty, standard_duty - fhb_duty, "FHB partial concession"
        else:
            return standard_duty, 0, "No FHB concession above $530k"

    # ── SA ────────────────────────────────────────────────────────────────────
    elif state == "SA":
        return standard_duty, 0, "SA has no FHB stamp duty concession"

    # ── ACT ───────────────────────────────────────────────────────────────────
    elif state == "ACT":
        fhb_cap = float(concs.get("fhb_price_cap", 1_000_000))
        if price <= fhb_cap:
            return 0, standard_duty, "Home Buyer Concession Scheme (income-tested)"
        else:
            return standard_duty, 0, "Exceeds HBCS price cap"

    # ── TAS ───────────────────────────────────────────────────────────────────
    elif state == "TAS":
        fhb_cap     = float(concs.get("fhb_price_cap", 600_000))
        discount    = float(concs.get("fhb_discount_pct", 50)) / 100
        if price <= fhb_cap:
            fhb_duty = round(standard_duty * (1 - discount))
            return fhb_duty, standard_duty - fhb_duty, f"FHB 50% concession — under ${fhb_cap:,.0f}"
        else:
            return standard_duty, 0, "No FHB concession above $600k"

    # ── NT ────────────────────────────────────────────────────────────────────
    elif state == "NT":
        max_rebate    = float(concs.get("fhb_max_discount",    18_601))
        phaseout_start= float(concs.get("fhb_phaseout_start", 500_000))
        taper_top     = float(concs.get("fhb_taper_top",      650_000))
        if price <= phaseout_start:
            rebate = min(max_rebate, standard_duty)
            return max(0, standard_duty - rebate), rebate, f"FHB rebate up to ${max_rebate:,.0f}"
        elif price <= taper_top:
            taper_ratio = (taper_top - price) / (taper_top - phaseout_start)
            rebate      = round(max_rebate * taper_ratio)
            fhb_duty    = max(0, standard_duty - rebate)
            return fhb_duty, rebate, "FHB partial rebate"
        else:
            return standard_duty, 0, "No FHB rebate above $650k"

    return standard_duty, 0, ""


# ── LMI calculation ─────────────────────────────────────────────────────────────

def calc_lmi(loan_amount, property_value, state, lmi_rates_data, lmi_sd_rates):
    """
    Calculate LMI premium + stamp duty on LMI for a given LVR and loan.
    Returns (lmi_premium, lmi_stamp_duty, total_lmi_cost).
    LMI is only applicable when LVR > 80%.
    """
    lvr = loan_amount / property_value * 100
    if lvr <= 80:
        return 0, 0, 0

    # Find matching LMI rate
    rate_pct = None
    for row in lmi_rates_data:
        if (float(row["lvr_min"]) <= lvr <= float(row["lvr_max"]) and
                (row["loan_max"] is None or loan_amount <= float(row["loan_max"]))):
            rate_pct = float(row["rate_pct"])
            break

    if rate_pct is None:
        # Use highest bracket if not found
        rate_pct = max(float(r["rate_pct"]) for r in lmi_rates_data)

    premium  = round(loan_amount * rate_pct / 100)
    sd_rate  = lmi_sd_rates.get(state, 0.1)   # default 10% if unknown
    sd_on_lmi = round(premium * sd_rate)
    return premium, sd_on_lmi, premium + sd_on_lmi


# ── Deposit tiers ────────────────────────────────────────────────────────────────

def deposit_tiers(price, state, brackets_data, concessions_data, nt_formula, lmi_rates_data, lmi_sd_rates):
    """
    Calculate deposit, loan, and LMI for 20%, 10%, and 5% deposit tiers.
    Returns list of dicts.
    """
    tiers = []
    for pct in [0.20, 0.10, 0.05]:
        deposit = round(price * pct)
        loan    = price - deposit
        lvr     = loan / price * 100
        lmi_premium, lmi_sd, lmi_total = calc_lmi(loan, price, state, lmi_rates_data, lmi_sd_rates)
        tiers.append({
            "pct":        pct,
            "pct_label":  f"{int(pct*100)}%",
            "deposit":    deposit,
            "loan":       loan,
            "lvr":        lvr,
            "lmi_total":  lmi_total,
            "no_lmi":     lmi_total == 0,
            "fhlds":      pct == 0.05,   # flag for FHLDS note
        })
    return tiers


# ── Format helpers ───────────────────────────────────────────────────────────────

def fmt(n):
    return f"${n:,.0f}"


def fmt_short(n):
    if n >= 1_000_000:
        m = n / 1_000_000
        return f"${m:.1f}m" if m % 1 else f"${int(m)}m"
    if n >= 1_000:
        return f"${int(n/1_000)}k"
    return f"${n}"


# ── Build all stamp duty data for JS embedding ───────────────────────────────────

def build_duty_json(price, brackets_data, concessions_data, nt_formula):
    """
    Build a JSON dict of stamp duty for all states and buyer types.
    Embedded in the page for JS state/FHB switching.
    """
    result = {}
    for state in STATES:
        std  = calc_stamp_duty(price, state, "standard", brackets_data, concessions_data, nt_formula)
        fhb_duty, saving, fhb_note = calc_fhb_duty(price, state, brackets_data, concessions_data, nt_formula)

        # Investor = standard rate always
        result[state] = {
            "standard":  std,
            "fhb":       fhb_duty,
            "fhb_saving": saving,
            "fhb_note":  fhb_note,
            "investor":  std,
        }
    return result


# ── Page generation ──────────────────────────────────────────────────────────────

def generate_page(
    price,
    assessment_rate,
    cash_rate,
    buffer,
    tax_year,
    brackets,
    lito_params,
    medicare_rate,
    rate_eff,
    brackets_data,
    concessions_data,
    nt_formula,
    lmi_rates_data,
    lmi_sd_rates,
    suburbs_near,
):
    price_fmt   = fmt(price)
    price_short = fmt_short(price)
    assess_str  = f"{assessment_rate:.2f}%"
    cash_str    = f"{cash_rate:.2f}%"
    buffer_str  = f"{buffer:.1f}%"

    # Income required for 20% deposit loan
    loan_20pct    = price - round(price * 0.20)
    income_single = income_required_for_loan(loan_20pct, assessment_rate, brackets, lito_params, medicare_rate)
    income_each   = income_required_for_loan(loan_20pct // 2, assessment_rate, brackets, lito_params, medicare_rate)

    # Default NSW / FHB deposit tiers
    nsw_tiers = deposit_tiers(price, "NSW", brackets_data, concessions_data, nt_formula, lmi_rates_data, lmi_sd_rates)

    # Stamp duty JSON for all states — embedded for JS switching
    duty_json = build_duty_json(price, brackets_data, concessions_data, nt_formula)

    # Suburb chips
    suburb_chips_html = ""
    for s in suburbs_near:
        name   = s["suburb_display"]
        state  = s["state"]
        ptype  = s["property_type"]
        slug_s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        suburb_chips_html += f'<a class="suburb-chip" href="/suburbs/{state.lower()}/{slug_s}/">{name} {state} ›</a>\n'
    if not suburb_chips_html:
        suburb_chips_html = '<span style="color:var(--dim);font-size:0.8rem;">No suburbs found near this price range</span>'

    # Deposit tier cards HTML (default NSW, updated by JS)
    tier_cards_html = ""
    for t in nsw_tiers:
        featured = ' featured' if t["pct"] == 0.20 else ''
        lmi_line = ""
        if t["lmi_total"] > 0:
            lmi_line = f'<div class="dep-warn">+ {fmt(t["lmi_total"])} LMI est.</div>'
        elif t["fhlds"]:
            lmi_line = '<div class="dep-good">No LMI (FHLDS guarantee)</div>'
        else:
            lmi_line = '<div class="dep-good">No LMI required</div>'
        tier_cards_html += f"""
      <div class="deposit-card{featured}">
        <div class="dep-label">{t["pct_label"]} deposit</div>
        <div class="dep-amount">{fmt(t["deposit"])}</div>
        <div class="dep-note">Loan: {fmt(t["loan"])}</div>
        {lmi_line}
      </div>"""

    prev_price = price - PRICE_STEP
    next_price = price + PRICE_STEP
    prev_link = f'<a href="/guides/can-i-afford/{prev_price}/" style="color:var(--muted);">← {fmt(prev_price)}</a>' if prev_price >= PRICE_MIN else ""
    next_link = f'<a href="/guides/can-i-afford/{next_price}/" style="color:var(--muted);">{fmt(next_price)} →</a>' if next_price <= PRICE_MAX else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Can I afford a {price_fmt} property? — GetReal</title>
  <meta name="description" content="To buy a {price_fmt} property you need a deposit of {fmt(round(price*0.2))} (20%) and an income of approximately {fmt(income_single)}. Stamp duty by state, LMI costs, and example suburbs.">
  <link rel="canonical" href="{BASE_URL}/guides/can-i-afford/{price}/">
  <meta property="og:title" content="Can I afford a {price_fmt} property? — GetReal">
  <meta property="og:description" content="Deposit {fmt(round(price*0.2))}, income required {fmt(income_single)}, stamp duty varies by state. See full breakdown.">
  <meta property="og:image" content="https://get-real.co/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="https://get-real.co/og-image.png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/styles.css">
  <style>
    .guide-wrap {{ max-width:860px;margin:0 auto;padding:2.5rem 1.5rem 5rem; }}
    .breadcrumb {{ font-family:monospace;font-size:0.65rem;color:var(--dim);margin-bottom:1.5rem; }}
    .breadcrumb a {{ color:var(--dim);text-decoration:none; }}
    h1 {{ font-size:1.6rem;margin-bottom:0.4rem;line-height:1.3; }}
    .lead {{ color:var(--muted);font-size:0.9rem;line-height:1.8;margin-bottom:1.5rem;max-width:640px; }}

    .input-bar {{
      border:1px solid var(--border);background:var(--card);
      padding:1rem 1.25rem;margin:0 0 1rem;
      display:flex;align-items:center;gap:1rem;flex-wrap:wrap;
    }}
    .input-group {{ display:flex;flex-direction:column;gap:4px; }}
    .input-group label {{ font-family:monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim); }}
    .input-group select {{
      font-family:monospace;font-size:0.9rem;
      background:var(--bg);border:1px solid var(--border);
      color:var(--text);padding:5px 10px;cursor:pointer;
    }}
    .toggle-group {{ display:flex;flex-direction:column;gap:4px; }}
    .toggle-group label {{ font-family:monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim); }}
    .toggle-row {{ display:flex; }}
    .toggle-btn {{
      font-family:monospace;font-size:0.78rem;
      border:1px solid var(--border);border-left:none;
      padding:5px 12px;cursor:pointer;background:var(--card);color:var(--muted);
    }}
    .toggle-btn:first-child {{ border-left:1px solid var(--border); }}
    .toggle-btn.active {{ background:var(--text);color:var(--bg); }}

    /* Assumptions */
    .assumptions {{
      border:1px solid #b45309;background:var(--card);
      padding:1rem 1.25rem;margin:0 0 1rem;
    }}
    .assumptions-hdr {{
      display:flex;align-items:center;gap:8px;
      font-family:monospace;font-size:0.65rem;text-transform:uppercase;
      letter-spacing:0.1em;color:#f59e0b;margin-bottom:0.6rem;
    }}
    .warn-circle {{
      width:16px;height:16px;border:1.5px solid #f59e0b;border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:10px;font-weight:700;color:#f59e0b;flex-shrink:0;
    }}
    .assume-grid {{ display:flex;flex-direction:column; }}
    .assume-row {{
      display:flex;justify-content:space-between;font-size:0.8rem;
      padding:5px 0;border-bottom:1px solid var(--border);gap:2rem;
    }}
    .assume-key {{ color:var(--dim); }}
    .assume-val {{ color:var(--text);font-weight:500;text-align:right; }}
    .assume-footer {{
      margin-top:0.6rem;font-size:0.75rem;color:var(--dim);
      line-height:1.6;border-top:1px solid var(--border);padding-top:0.5rem;
    }}
    .assume-footer a {{ color:#f59e0b; }}

    /* Stamp duty block */
    .duty-block {{
      border:1px solid var(--border);padding:1.25rem;margin:0 0 1rem;
    }}
    .duty-headline {{ display:flex;align-items:baseline;gap:1.5rem;flex-wrap:wrap; }}
    .duty-figure {{ font-size:2rem;font-weight:700;color:#4caf50;line-height:1; }}
    .duty-figure.high {{ color:#ef5350; }}
    .duty-figure.mid {{ color:#f59e0b; }}
    .duty-label {{ font-family:monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim);margin-top:3px; }}
    .duty-saving {{ font-size:1rem;color:#4caf50; }}
    .duty-note {{ font-size:0.82rem;color:var(--muted);margin-top:8px;line-height:1.6; }}

    /* Compare table */
    details {{ margin-bottom:1rem; }}
    details summary {{ font-size:0.8rem;color:var(--dim);cursor:pointer;padding:4px 0; }}
    .compare-table {{ width:100%;border-collapse:collapse;font-size:0.83rem;margin-top:8px; }}
    .compare-table th {{
      text-align:left;font-weight:400;font-family:monospace;font-size:0.65rem;
      text-transform:uppercase;letter-spacing:0.08em;color:var(--dim);
      border-bottom:1px solid var(--border);padding:3px 8px;
    }}
    .compare-table td {{ padding:6px 8px;border-bottom:1px solid var(--border);color:var(--muted); }}
    .compare-table tr:last-child td {{ border-bottom:none; }}
    .compare-table .selected td {{ background:var(--card);color:var(--text);font-weight:500; }}
    .sc {{ color:var(--dim);font-size:0.75rem; }}
    .hi {{ color:#4caf50; }}
    .lo {{ color:#ef5350; }}
    .mid {{ color:#f59e0b; }}

    /* Section label */
    .section-label {{
      font-family:monospace;font-size:0.65rem;text-transform:uppercase;
      letter-spacing:0.1em;color:var(--dim);border-bottom:1px solid var(--border);
      padding-bottom:0.4rem;margin:1.5rem 0 0.75rem;
    }}

    /* Deposit cards */
    .three-grid {{ display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:1rem; }}
    .deposit-card {{ border:1px solid var(--border);padding:0.85rem 1rem; }}
    .deposit-card.featured {{ border-color:#4caf50; }}
    .dep-label {{ font-family:monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--dim);margin-bottom:4px; }}
    .dep-amount {{ font-size:1.1rem;font-weight:500;color:var(--text); }}
    .dep-note {{ font-size:0.8rem;color:var(--muted);margin-top:3px; }}
    .dep-good {{ font-size:0.8rem;color:#4caf50;margin-top:3px; }}
    .dep-warn {{ font-size:0.8rem;color:#f59e0b;margin-top:3px; }}

    /* Income grid */
    .two-grid {{ display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:1rem; }}
    .income-card {{ border:1px solid var(--border);padding:0.85rem 1rem; }}
    .inc-label {{ font-family:monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;color:var(--dim);margin-bottom:4px; }}
    .inc-val {{ font-size:1.1rem;font-weight:500;color:var(--text); }}
    .inc-sub {{ font-size:0.8rem;color:var(--muted);margin-top:3px; }}

    /* Suburb chips */
    .suburb-chips {{ display:flex;flex-wrap:wrap;gap:6px;margin-bottom:1.5rem; }}
    .suburb-chip {{
      font-size:0.8rem;border:1px solid var(--border);
      padding:4px 10px;color:#4caf50;text-decoration:none;
    }}
    .suburb-chip:hover {{ border-color:#4caf50; }}

    /* CTA */
    .cta-strip {{
      border:1px solid var(--border);padding:1rem 1.25rem;
      display:flex;align-items:center;justify-content:space-between;
      gap:1rem;flex-wrap:wrap;margin-top:1.5rem;
    }}
    .cta-text {{ font-size:0.85rem;color:var(--muted); }}
    .cta-text strong {{ color:var(--text);display:block;margin-bottom:2px; }}

    /* Pagination */
    .pagination {{
      display:flex;justify-content:space-between;
      margin-top:2rem;padding-top:1rem;border-top:1px solid var(--border);
      font-size:0.85rem;
    }}

    @media(max-width:600px) {{
      .three-grid {{ grid-template-columns:1fr; }}
      .two-grid {{ grid-template-columns:1fr; }}
      .assume-grid {{ grid-template-columns:1fr; }}
    }}
  </style>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Can I afford a {price_fmt} property?",
    "description": "Deposit, income, stamp duty, and LMI costs for a {price_fmt} property purchase in Australia.",
    "url": "{BASE_URL}/guides/can-i-afford/{price}/",
    "publisher": {{"@type": "Organization", "name": "GetReal", "url": "https://get-real.co"}},
    "dateModified": "{TODAY}"
  }}
  </script>
</head>
<body>

<header class="site-header">
  <a class="brand" href="/">
    <svg width="22" height="22" viewBox="0 0 26 26" fill="none">
      <circle cx="13" cy="13" r="11.5" stroke="#18181b" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="6.5" stroke="#18181b" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="2.5" fill="#18181b"/>
    </svg>
    <span class="brand-name">GetReal</span>
  </a>
</header>

<div class="guide-wrap">

  <nav class="breadcrumb">
    <a href="/">Home</a> ›
    <a href="/guides/">Guides</a> ›
    <a href="/guides/can-i-afford/">Can I afford</a> ›
    {price_fmt}
  </nav>

  <p class="eyebrow" style="margin-bottom:0.75rem;">Affordability</p>
  <h1>What do you need to buy a {price_fmt} property?</h1>
  <p class="lead">
    Deposit, stamp duty, LMI, and the income needed to service the loan.
    Select your state and buyer type — stamp duty updates instantly.
  </p>

  <!-- Input bar -->
  <div class="input-bar">
    <div class="input-group">
      <label>Your state</label>
      <select id="stateSelect" onchange="update()">
        <option value="NSW">NSW</option>
        <option value="VIC">VIC</option>
        <option value="QLD">QLD</option>
        <option value="WA">WA</option>
        <option value="SA">SA</option>
        <option value="ACT">ACT</option>
        <option value="TAS">TAS</option>
        <option value="NT">NT</option>
      </select>
    </div>
    <div class="toggle-group">
      <label>Buyer type</label>
      <div class="toggle-row">
        <button class="toggle-btn active" onclick="setBuyer('fhb',this)">First home</button>
        <button class="toggle-btn" onclick="setBuyer('oo',this)">Next home</button>
        <button class="toggle-btn" onclick="setBuyer('inv',this)">Investment</button>
      </div>
    </div>
  </div>

  <!-- Assumptions panel -->
  <div class="assumptions">
    <div class="assumptions-hdr">
      <div class="warn-circle">!</div>
      Income figures assume: single borrower, no existing debt, metro HEM
    </div>
    <div class="assume-grid">
      <div class="assume-row"><span class="assume-key">Assessment rate</span><span class="assume-val">{assess_str} (RBA {cash_str} + {buffer_str})</span></div>
      <div class="assume-row"><span class="assume-key">Loan term</span><span class="assume-val">{LOAN_TERM_YEARS} years P&amp;I</span></div>
      <div class="assume-row"><span class="assume-key">Living expenses</span><span class="assume-val">HEM metro (${HEM_METRO_SINGLE:,}/mo)</span></div>
      <div class="assume-row"><span class="assume-key">Existing debt</span><span class="assume-val">None</span></div>
    </div>
    <div class="assume-footer">
      ⚠ Assessment rate sourced from RBA F1 data (effective {rate_eff}), updated automatically each week.
      Stamp duty figures are sourced from state revenue offices — accurate as at {TODAY}.
      For a personalised affordability check, <a href="/search">use the search tool →</a>
    </div>
  </div>

  <!-- Stamp duty — state-specific headline -->
  <div class="section-label" id="dutyLabel">Stamp duty — NSW, first home buyer</div>
  <div class="duty-block" id="dutyBlock">
    <div id="dutyContent"></div>
  </div>

  <details>
    <summary>Compare all states →</summary>
    <table class="compare-table" id="compareTable">
      <thead>
        <tr>
          <th>State</th>
          <th>Buyer type</th>
          <th style="text-align:right;">Duty payable</th>
          <th style="text-align:right;">FHB saving</th>
        </tr>
      </thead>
      <tbody id="compareBody"></tbody>
    </table>
  </details>

  <!-- Deposit tiers -->
  <div class="section-label">Deposit options — {price_fmt}</div>
  <div class="three-grid" id="depositGrid">
    {tier_cards_html}
  </div>

  <!-- Income required -->
  <div class="section-label">Minimum income to service the loan (20% deposit)</div>
  <div class="two-grid">
    <div class="income-card">
      <div class="inc-label">Single borrower</div>
      <div class="inc-val">{fmt(income_single)}</div>
      <div class="inc-sub">gross annual, no existing debt</div>
    </div>
    <div class="income-card">
      <div class="inc-label">Two borrowers</div>
      <div class="inc-val">{fmt(income_each)} each</div>
      <div class="inc-sub">or any split totalling {fmt(income_single)}</div>
    </div>
  </div>

  <!-- Suburb chips -->
  <div class="section-label" id="suburbLabel">What does {price_fmt} get you?</div>
  <div class="suburb-chips">
    {suburb_chips_html}
  </div>

  <!-- CTA -->
  <div class="cta-strip">
    <div class="cta-text">
      <strong>Check if this is realistic for a specific suburb</strong>
      See what share of the market your budget can reach.
    </div>
    <a class="btn" href="/search">Search now →</a>
  </div>

  <div class="pagination">
    <span>{prev_link}</span>
    <span>{next_link}</span>
  </div>

</div>

<script>
(function() {{
  var PRICE = {price};
  var DUTY  = {json.dumps(duty_json, separators=(',',':'))};
  var STATES_ORDER = {json.dumps(STATES)};

  var buyerType = 'fhb';
  var state     = 'NSW';

  function fmtDollar(n) {{
    if (n === 0) return '$0';
    return '$' + Math.round(n).toLocaleString('en-AU');
  }}

  function dutyClass(n) {{
    if (n === 0) return 'hi';
    if (n > 40000) return 'lo';
    if (n > 20000) return 'mid';
    return '';
  }}

  function setBuyer(type, btn) {{
    buyerType = type;
    document.querySelectorAll('.toggle-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    update();
  }}
  window.setBuyer = setBuyer;

  function getDuty() {{
    var d = DUTY[state];
    if (!d) return {{duty: 0, saving: 0, note: ''}};
    if (buyerType === 'fhb') return {{duty: d.fhb, saving: d.fhb_saving, note: d.fhb_note}};
    if (buyerType === 'inv') return {{duty: d.investor, saving: 0, note: 'Investor — standard rate'}};
    return {{duty: d.standard, saving: 0, note: 'Owner-occupier — standard rate'}};
  }}

  function update() {{
    state = document.getElementById('stateSelect').value;
    var buyerLabel = buyerType === 'fhb' ? 'first home' : buyerType === 'oo' ? 'next home' : 'investment';

    document.getElementById('dutyLabel').textContent = 'Stamp duty — ' + state + ', ' + buyerLabel;
    document.getElementById('suburbLabel').textContent = 'What does {price_fmt} get you?';

    var d = getDuty();
    var dc = dutyClass(d.duty);

    var savingHtml = d.saving > 0
      ? '<span style="font-size:0.9rem;color:#4caf50;margin-left:1rem;">saving ' + fmtDollar(d.saving) + '</span>'
      : '';

    var strikeHtml = '';
    if (buyerType === 'fhb' && d.saving > 0) {{
      var std = DUTY[state].standard;
      strikeHtml = '<div style="margin-top:4px;"><span style="font-size:0.85rem;color:var(--dim);">Standard rate: </span>'
        + '<span style="font-size:0.85rem;color:var(--muted);text-decoration:line-through;">' + fmtDollar(std) + '</span></div>';
    }}

    document.getElementById('dutyContent').innerHTML =
      '<div class="duty-headline">'
      + '<div><div class="duty-figure ' + dc + '">' + fmtDollar(d.duty) + '</div>'
      + '<div class="duty-label">Stamp duty payable</div></div>'
      + savingHtml
      + '</div>'
      + strikeHtml
      + '<div class="duty-note">' + (d.note || '') + '</div>';

    // Compare table
    var tbody = document.getElementById('compareBody');
    tbody.innerHTML = '';
    STATES_ORDER.forEach(function(st) {{
      var sd   = DUTY[st];
      var duty = buyerType === 'fhb' ? sd.fhb : sd.standard;
      var sav  = buyerType === 'fhb' ? sd.fhb_saving : 0;
      var tr   = document.createElement('tr');
      if (st === state) tr.className = 'selected';
      var savCell = sav > 0
        ? '<td class="hi" style="text-align:right;">−' + fmtDollar(sav) + '</td>'
        : '<td style="text-align:right;color:var(--dim);">—</td>';
      tr.innerHTML = '<td><span class="sc">' + st + '</span></td>'
        + '<td style="color:var(--muted);">' + buyerLabel + '</td>'
        + '<td class="' + dutyClass(duty) + '" style="text-align:right;">' + fmtDollar(duty) + '</td>'
        + savCell;
      tbody.appendChild(tr);
    }});
  }}

  window.update = update;
  update();
}})();
</script>

</body>
</html>"""

    return html


# ── Sitemap ──────────────────────────────────────────────────────────────────────

def write_sitemap(prices):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines.append(f"""  <url>
    <loc>{BASE_URL}/guides/can-i-afford/</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>""")
    for p in prices:
        lines.append(f"""  <url>
    <loc>{BASE_URL}/guides/can-i-afford/{p}/</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""")
    lines.append('</urlset>')
    path = Path("sitemap-guides-b.xml")
    path.write_text("\n".join(lines))
    print(f"  Wrote {path}")


def write_index(prices):
    rows = ""
    for p in prices:
        rows += f"""    <a class="guide-row" href="/guides/can-i-afford/{p}/">
      <span class="guide-row-price">{fmt(p)}</span>
      <span class="guide-row-arrow" style="color:#4caf50;">›</span>
    </a>\n"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Can I afford it? Property affordability guides — GetReal</title>
  <meta name="description" content="Deposit, stamp duty, LMI, and income required for every property price from $300,000 to $3,000,000. Updated weekly.">
  <link rel="canonical" href="{BASE_URL}/guides/can-i-afford/">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/styles.css">
  <style>
    .wrap {{ max-width:860px;margin:0 auto;padding:2.5rem 1.5rem 5rem; }}
    h1 {{ font-size:1.6rem;margin-bottom:0.5rem; }}
    .lead {{ color:var(--muted);font-size:0.9rem;line-height:1.8;margin-bottom:2rem;max-width:640px; }}
    .guide-list {{ display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:1px;background:var(--border);border:1px solid var(--border); }}
    .guide-row {{
      background:var(--bg);display:flex;align-items:center;justify-content:space-between;
      padding:0.75rem 1rem;text-decoration:none;color:inherit;
    }}
    .guide-row:hover {{ background:var(--card); }}
    .guide-row-price {{ font-family:monospace;font-size:0.85rem;font-weight:500; }}
    .section-label {{
      font-family:monospace;font-size:0.65rem;text-transform:uppercase;
      letter-spacing:0.1em;color:var(--dim);border-bottom:1px solid var(--border);
      padding-bottom:0.4rem;margin:0 0 0.75rem;
    }}
  </style>
</head>
<body>
<header class="site-header">
  <a class="brand" href="/">
    <svg width="22" height="22" viewBox="0 0 26 26" fill="none">
      <circle cx="13" cy="13" r="11.5" stroke="#18181b" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="6.5" stroke="#18181b" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="2.5" fill="#18181b"/>
    </svg>
    <span class="brand-name">GetReal</span>
  </a>
</header>
<div class="wrap">
  <nav style="font-family:monospace;font-size:0.65rem;color:var(--dim);margin-bottom:1.5rem;">
    <a href="/" style="color:var(--dim);text-decoration:none;">Home</a> ›
    <a href="/guides/" style="color:var(--dim);text-decoration:none;">Guides</a> › Can I afford
  </nav>
  <p class="eyebrow" style="margin-bottom:0.75rem;">Affordability</p>
  <h1>Can I afford it?</h1>
  <p class="lead">
    Deposit required, stamp duty by state, LMI costs, and minimum income — for every price point from $300k to $3M.
    Select a price to see the full breakdown.
  </p>
  <div class="section-label">Select a price point</div>
  <div class="guide-list">
{rows}
  </div>
</div>
</body>
</html>"""

    out = OUT_DIR / "index.html"
    out.write_text(html)
    print(f"  Wrote {out}")


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET not set.")
        sys.exit(1)

    print("Loading reference data from Supabase ...")
    rates    = load_reference_rates()
    brackets, tax_year = load_tax_brackets()
    lito     = load_lito()

    cash_rate  = rates["rba_cash_rate"]
    buffer     = rates["assessment_rate_buffer"]
    medicare   = rates["medicare_levy_rate"]
    assessment = cash_rate + buffer

    rate_rows = sb_get("reference_rates", "select=effective_date&key=eq.rba_cash_rate")
    rate_eff  = rate_rows[0]["effective_date"] if rate_rows else TODAY

    print("Loading stamp duty data ...")
    brackets_data, concessions_data, nt_formula = load_stamp_duty_data()
    print(f"  {len(brackets_data)} duty brackets, {len(concessions_data)} concession rows")

    print("Loading LMI data ...")
    lmi_rates_data, lmi_sd_rates = load_lmi_data()
    print(f"  {len(lmi_rates_data)} LMI rate rows")

    prices = list(range(PRICE_MIN, PRICE_MAX + PRICE_STEP, PRICE_STEP))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\nBuilding {len(prices)} price guide pages ...")
    for price in prices:
        suburbs_near = load_suburbs_near_price(price)
        page_dir     = OUT_DIR / str(price)
        page_dir.mkdir(parents=True, exist_ok=True)
        out = page_dir / "index.html"

        html = generate_page(
            price            = price,
            assessment_rate  = assessment,
            cash_rate        = cash_rate,
            buffer           = buffer,
            tax_year         = tax_year,
            brackets         = brackets,
            lito_params      = lito,
            medicare_rate    = medicare,
            rate_eff         = rate_eff,
            brackets_data    = brackets_data,
            concessions_data = concessions_data,
            nt_formula       = nt_formula,
            lmi_rates_data   = lmi_rates_data,
            lmi_sd_rates     = lmi_sd_rates,
            suburbs_near     = suburbs_near,
        )
        out.write_text(html)
        # Spot-check: show NSW FHB duty and income required
        nsw_fhb, saving, _ = calc_fhb_duty(price, "NSW", brackets_data, concessions_data, nt_formula)
        loan_20 = price - round(price * 0.20)
        inc_req = income_required_for_loan(loan_20, assessment, brackets, lito, medicare)
        print(f"  {fmt(price):>12}  NSW FHB duty: {fmt(nsw_fhb):>10}  Income reqd: {fmt(inc_req):>10}  ({out})")

    write_index(prices)
    write_sitemap(prices)

    print(f"\n✓ Built {len(prices)} pages + index + sitemap")
    print(f"  Assessment rate: {assessment:.2f}% (RBA {cash_rate:.2f}% + {buffer:.1f}% buffer)")
    print(f"\n  Push command:")
    print(f"  git add guides/can-i-afford/ sitemap-guides-b.xml && git commit -m 'feat: add Series B price affordability guides' && git push")


if __name__ == "__main__":
    main()
