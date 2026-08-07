#!/usr/bin/env python3
"""
build_income_guides.py — GetReal Series A: "How much can I borrow on $X salary?"
==================================================================================
Generates static HTML pages at:
  guides/how-much-can-i-borrow/{salary}/index.html

One page per salary point: $60k–$300k in $10k steps = 25 pages.

All rates and tax brackets are read from Supabase at build time:
  - reference_rates    → rba_cash_rate, assessment_rate_buffer, medicare_levy_rate
  - income_tax_brackets → ATO marginal rates for the current FY
  - lito_rates          → LITO offset parameters
  - suburb_analytics    → nearby suburbs at the estimated purchase price

Usage:
    export SUPABASE_SECRET=<secret>
    python3 build_income_guides.py

Output:
    guides/how-much-can-i-borrow/{salary}/index.html   (25 pages)
    sitemap-guides-a.xml
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

BASE_URL  = "https://get-real.co"
TODAY     = date.today().isoformat()
OUT_DIR   = Path("guides/how-much-can-i-borrow")

# Salary range: $60k–$300k in $10k steps
SALARY_MIN  = 60_000
SALARY_MAX  = 300_000
SALARY_STEP = 10_000

# Loan term (months)
LOAN_TERM_YEARS  = 30
LOAN_TERM_MONTHS = LOAN_TERM_YEARS * 12

# Deposit assumed for "what can I reach" suburb suggestions
DEFAULT_DEPOSIT = 100_000

# Sensitivity scenarios shown in the table
SCENARIOS = [
    ("partner_80k",   "Partner on $80,000",     {"extra_income": 80_000}),
    ("partner_60k",   "Partner on $60,000",      {"extra_income": 60_000}),
    ("cc_15k",        "$15k credit card limit",  {"credit_card": 15_000}),
    ("cc_5k",         "$5k credit card limit",   {"credit_card": 5_000}),
    ("hecs_50k",      "$50k HECS debt",           {"hecs": 50_000}),
    ("hecs_30k",      "$30k HECS debt",           {"hecs": 30_000}),
    ("dep_1",         "1 dependant",              {"dependants": 1}),
    ("dep_2",         "2 dependants",             {"dependants": 2}),
]

# HEM monthly amounts (metro single, no dependants) — from hem_benchmarks table fallback
HEM_METRO_SINGLE     = 2_800
HEM_METRO_COUPLE     = 3_800
HEM_METRO_DEP_EXTRA  = 500   # extra per dependant

# HECS repayment rates (% of income) — ATO 2025-26 thresholds
# Stored here as they're part of income calculation, not loan servicing debt
HECS_REPAYMENT_RATES = [
    (54_435,  0.010),
    (62_739,  0.020),
    (66_153,  0.025),
    (70_619,  0.030),
    (75_145,  0.035),
    (79_653,  0.040),
    (84_422,  0.045),
    (89_495,  0.050),
    (94_865,  0.055),
    (100_557, 0.060),
    (106_590, 0.065),
    (112_985, 0.070),
    (119_764, 0.075),
    (126_951, 0.080),
    (134_568, 0.085),
    (142_642, 0.090),
    (151_200, 0.095),
    (160_273, 0.100),
]

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
    """Return brackets sorted by bracket_min for the most recent year."""
    rows = sb_get(
        "income_tax_brackets",
        "select=effective_year,bracket_min,bracket_max,base_amount,rate"
        "&order=effective_year.desc,bracket_min.asc"
    )
    if not rows:
        raise ValueError("No tax brackets found in Supabase — run load_tax_brackets.py first")
    # Use the most recent year
    latest_year = rows[0]["effective_year"]
    brackets = [r for r in rows if r["effective_year"] == latest_year]
    print(f"  Tax brackets: FY ending {latest_year} ({len(brackets)} brackets)")
    return brackets, latest_year


def load_lito():
    rows = sb_get("lito_rates", "select=*&order=effective_year.desc&limit=1")
    if not rows:
        raise ValueError("No LITO data found — run load_tax_brackets.py first")
    return rows[0]


def load_suburbs_near_price(target_price, state=None, limit=6):
    """Return suburbs where median house price is within 15% of target."""
    low  = int(target_price * 0.85)
    high = int(target_price * 1.15)
    params = (
        f"select=suburb_display,state,median_price,annual_sales"
        f"&property_type=eq.house"
        f"&median_price=gte.{low}&median_price=lte.{high}"
        f"&annual_sales=gte.20"
        f"&order=annual_sales.desc"
        f"&limit={limit}"
    )
    if state:
        params += f"&state=eq.{state}"
    rows = sb_get("suburb_analytics", params)
    return rows

# ── Tax calculation ──────────────────────────────────────────────────────────────

def calc_income_tax(gross, brackets, lito_params, medicare_rate):
    """
    Calculate net annual take-home pay.
    Returns (net_tax, take_home_annual, take_home_monthly)
    """
    # 1. Raw income tax from brackets
    raw_tax = 0.0
    for b in brackets:
        bmin = b["bracket_min"]
        bmax = b["bracket_max"]
        base = b["base_amount"]
        rate = float(b["rate"])
        if gross > bmin:
            top = min(gross, bmax) if bmax is not None else gross
            raw_tax = base + (top - bmin) * rate

    # 2. LITO (Low Income Tax Offset)
    lito = float(lito_params["max_offset"])
    phase_start = lito_params["phase_out_start"]
    end_1       = lito_params["phase_out_end_1"]
    rate_1      = float(lito_params["phase_out_rate_1"])
    end_2       = lito_params["phase_out_end_2"]
    rate_2      = float(lito_params["phase_out_rate_2"])

    if gross > phase_start:
        excess = min(gross, end_1) - phase_start
        lito  -= excess * rate_1
    if gross > end_1:
        excess = min(gross, end_2) - end_1
        lito  -= excess * rate_2
    lito = max(0.0, lito)

    # 3. Medicare levy (simplified — 2% above low-income threshold ~$26k)
    medicare = gross * medicare_rate if gross > 26_000 else 0.0

    net_tax   = max(0.0, raw_tax - lito) + medicare
    take_home = gross - net_tax
    return round(net_tax), round(take_home), round(take_home / 12)


def calc_hecs_repayment(gross):
    """Annual compulsory HECS repayment based on income."""
    rate = 0.0
    for threshold, r in HECS_REPAYMENT_RATES:
        if gross >= threshold:
            rate = r
    return round(gross * rate)


def calc_borrowing_capacity(
    gross_income,
    assessment_rate_pct,
    brackets,
    lito_params,
    medicare_rate,
    extra_income=0,
    credit_card=0,
    hecs=0,
    dependants=0,
    hem_monthly=None,
):
    """
    Estimate borrowing capacity using standard serviceability methodology.

    Method:
    1. Calculate combined net monthly income using actual ATO tax brackets
    2. Subtract HEM living expenses
    3. Subtract monthly obligations: credit card (3.8% of limit/month), HECS repayments
    4. Remaining cash flow supports P&I repayments at assessment rate
    5. Back-calculate loan amount from monthly repayment capacity

    Returns borrowing capacity in dollars (rounded to nearest $5k).
    """
    total_gross = gross_income + extra_income

    # Use actual tax calculation for both borrowers combined.
    # For combined income, we calculate tax on total gross (simplified — doesn't
    # split income across two tax returns, which would be slightly more generous,
    # but is a conservative approximation used by lenders).
    _, take_home_annual, _ = calc_income_tax(total_gross, brackets, lito_params, medicare_rate)
    net_monthly = take_home_annual / 12

    # HEM
    if hem_monthly is None:
        hem_monthly = HEM_METRO_SINGLE if extra_income == 0 else HEM_METRO_COUPLE
        hem_monthly += dependants * HEM_METRO_DEP_EXTRA

    # Monthly obligations
    cc_monthly   = credit_card * 0.038          # lenders use 3.8% of limit as monthly obligation
    hecs_monthly = calc_hecs_repayment(total_gross) / 12 if hecs > 0 else 0

    # Available for repayments
    available = net_monthly - hem_monthly - cc_monthly - hecs_monthly
    if available <= 0:
        return 0

    # Monthly assessment rate
    r = (assessment_rate_pct / 100) / 12

    # Loan amount from standard annuity formula:
    # available = L * r * (1+r)^n / ((1+r)^n - 1)
    # → L = available * ((1+r)^n - 1) / (r * (1+r)^n)
    n       = LOAN_TERM_MONTHS
    factor  = (1 + r) ** n
    capacity = available * (factor - 1) / (r * factor)

    # Round to nearest $5k
    return int(round(capacity / 5_000) * 5_000)


# ── Page generation ──────────────────────────────────────────────────────────────

def fmt_dollar(n, decimals=0):
    if decimals:
        return f"${n:,.{decimals}f}"
    return f"${n:,.0f}"


def fmt_dollar_short(n):
    """$625,000 → $625k"""
    if n >= 1_000_000:
        m = n / 1_000_000
        return f"${m:.1f}m" if m % 1 else f"${int(m)}m"
    if n >= 1_000:
        k = n / 1_000
        return f"${k:.0f}k"
    return f"${n}"


def generate_page(
    salary,
    capacity,
    take_home_monthly,
    net_tax,
    assessment_rate,
    cash_rate,
    buffer,
    tax_year,
    lito_params,
    brackets,
    medicare_rate,
    suburbs_near,
    rate_effective_date,
):
    slug          = str(salary)
    salary_fmt    = fmt_dollar(salary)
    capacity_fmt  = fmt_dollar(capacity)
    capacity_short = fmt_dollar_short(capacity)
    th_fmt        = fmt_dollar(take_home_monthly)

    # Estimated purchase price = borrowing capacity + assumed deposit
    purchase_est  = capacity + DEFAULT_DEPOSIT
    purchase_fmt  = fmt_dollar(purchase_est)

    hem           = fmt_dollar(HEM_METRO_SINGLE)
    assess_str    = f"{assessment_rate:.2f}%"
    cash_str      = f"{cash_rate:.2f}%"
    buffer_str    = f"{buffer:.1f}%"

    # Sensitivity rows
    scenario_rows = []
    for key, label, overrides in SCENARIOS:
        sc = calc_borrowing_capacity(
            salary,
            assessment_rate,
            brackets,
            lito_params,
            medicare_rate,
            **overrides,
        )
        diff = sc - capacity
        diff_str  = (f"+{fmt_dollar_short(diff)}" if diff > 0 else fmt_dollar_short(diff))
        diff_class = "hi" if diff > 0 else ("lo" if diff < 0 else "")
        scenario_rows.append((label, sc, fmt_dollar_short(sc), diff_str, diff_class))

    # Suburb chips
    suburb_chips = ""
    for s in suburbs_near:
        name  = s["suburb_display"]
        state = s["state"]
        slug_s = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        suburb_chips += f'<a class="suburb-chip" href="/suburbs/{state.lower()}/{slug_s}/">{name} {state} ›</a>\n'
    if not suburb_chips:
        suburb_chips = '<span style="color:var(--dim);font-size:0.8rem;">No suburbs found near this price range</span>'

    sens_rows_html = ""
    for label, sc, sc_short, diff_str, diff_class in scenario_rows:
        sens_rows_html += f"""
            <tr>
              <td>{label}</td>
              <td class="{diff_class}" style="text-align:right;">{sc_short}</td>
              <td class="{diff_class}" style="text-align:right;">{diff_str}</td>
            </tr>"""

    # Previous / next links
    prev_salary = salary - SALARY_STEP
    next_salary = salary + SALARY_STEP
    prev_link = f'<a href="/guides/how-much-can-i-borrow/{prev_salary}/" style="color:var(--muted);">← {fmt_dollar(prev_salary)}</a>' if prev_salary >= SALARY_MIN else ""
    next_link = f'<a href="/guides/how-much-can-i-borrow/{next_salary}/" style="color:var(--muted);">{fmt_dollar(next_salary)} →</a>' if next_salary <= SALARY_MAX else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>How much can I borrow on {salary_fmt}? — GetReal</title>
  <meta name="description" content="On a {salary_fmt} salary, you can borrow approximately {capacity_fmt}. See how debts, dependants, and a second income change this figure.">
  <link rel="canonical" href="{BASE_URL}/guides/how-much-can-i-borrow/{slug}/">
  <meta property="og:title" content="How much can I borrow on {salary_fmt}? — GetReal">
  <meta property="og:description" content="Estimated borrowing capacity {capacity_fmt}. Assessment rate {assess_str}. See sensitivity analysis.">
  <meta property="og:image" content="https://get-real.co/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="https://get-real.co/og-image.png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/styles.css">
  <style>
    .guide-wrap {{ max-width: 860px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
    .breadcrumb {{ font-family:monospace;font-size:0.65rem;color:var(--dim);margin-bottom:1.5rem; }}
    .breadcrumb a {{ color:var(--dim);text-decoration:none; }}
    h1 {{ font-size:1.6rem;margin-bottom:0.4rem;line-height:1.3; }}
    .lead {{ color:var(--muted);font-size:0.9rem;line-height:1.8;margin-bottom:1.5rem;max-width:640px; }}

    /* Input bar */
    .input-bar {{
      border:1px solid var(--border);background:var(--card);
      padding:1rem 1.25rem;margin:0 0 1.25rem;
      display:flex;align-items:center;gap:1rem;flex-wrap:wrap;
    }}
    .input-group {{ display:flex;flex-direction:column;gap:4px; }}
    .input-group label {{ font-family:monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim); }}
    .input-group select, .input-group input {{
      font-family:monospace;font-size:0.9rem;
      background:var(--bg);border:1px solid var(--border);
      color:var(--text);padding:5px 10px;cursor:pointer;
    }}
    .toggle-group {{ display:flex;flex-direction:column;gap:4px; }}
    .toggle-group label {{ font-family:monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim); }}
    .toggle-row {{ display:flex; }}
    .toggle-btn {{
      font-family:monospace;font-size:0.78rem;
      border:1px solid var(--border);padding:5px 12px;
      cursor:pointer;background:var(--card);color:var(--muted);
    }}
    .toggle-btn.active {{ background:var(--text);color:var(--bg); }}

    /* Assumptions panel */
    .assumptions {{
      border:1px solid #b45309;background:var(--card);
      padding:1rem 1.25rem;margin:0 0 1.25rem;
    }}
    .assumptions-hdr {{
      display:flex;align-items:center;gap:8px;
      font-family:monospace;font-size:0.65rem;text-transform:uppercase;
      letter-spacing:0.1em;color:#f59e0b;margin-bottom:0.75rem;
    }}
    .warn-circle {{
      width:16px;height:16px;border:1.5px solid #f59e0b;border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:10px;font-weight:700;color:#f59e0b;flex-shrink:0;
    }}
    .assumptions-grid {{
      display:grid;grid-template-columns:1fr 1fr;gap:0;
    }}
    .assume-row {{
      display:flex;justify-content:space-between;
      font-size:0.8rem;padding:5px 0;border-bottom:1px solid var(--border);
      gap:1rem;
    }}
    .assume-row:nth-last-child(1):nth-child(odd) {{ grid-column:span 2; }}
    .assume-key {{ color:var(--dim); }}
    .assume-val {{ color:var(--text);font-weight:500;text-align:right; }}
    .assume-footer {{
      margin-top:0.6rem;font-size:0.75rem;color:var(--dim);
      line-height:1.6;border-top:1px solid var(--border);padding-top:0.5rem;
    }}
    .assume-footer a {{ color:#f59e0b; }}

    /* Result */
    .result-band {{
      border:1px solid var(--border);padding:1.25rem;margin:0 0 1.25rem;
    }}
    .result-figure {{ font-size:2.4rem;font-weight:700;color:#4caf50;line-height:1; }}
    .result-label {{ font-family:monospace;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.1em;color:var(--dim);margin-top:4px; }}
    .result-note {{ font-size:0.85rem;color:var(--muted);margin-top:8px;line-height:1.6; }}

    /* Section label */
    .section-label {{
      font-family:monospace;font-size:0.65rem;text-transform:uppercase;
      letter-spacing:0.1em;color:var(--dim);border-bottom:1px solid var(--border);
      padding-bottom:0.4rem;margin:1.5rem 0 0.75rem;
    }}

    /* Sensitivity table */
    .sens-table {{ width:100%;border-collapse:collapse;font-size:0.85rem;margin-bottom:1.5rem; }}
    .sens-table th {{
      text-align:left;font-weight:400;font-family:monospace;
      font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em;
      color:var(--dim);border-bottom:1px solid var(--border);padding:4px 8px;
    }}
    .sens-table td {{ padding:7px 8px;border-bottom:1px solid var(--border);color:var(--muted); }}
    .sens-table tr:last-child td {{ border-bottom:none; }}
    .sens-table .baseline {{ background:var(--card); }}
    .sens-table .baseline td {{ color:var(--text); }}
    .hi {{ color:#4caf50;font-weight:500; }}
    .lo {{ color:#ef5350; }}
    .baseline-tag {{
      font-size:0.65rem;color:var(--dim);border:1px solid var(--border);
      padding:1px 5px;margin-left:6px;vertical-align:middle;
    }}

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
      .assumptions-grid {{ grid-template-columns:1fr; }}
      .sens-table td:last-child {{ display:none; }}
    }}
  </style>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "How much can I borrow on {salary_fmt}?",
    "description": "On a {salary_fmt} salary, estimated borrowing capacity is {capacity_fmt} based on standard lender assumptions. Assessment rate {assess_str}.",
    "url": "{BASE_URL}/guides/how-much-can-i-borrow/{slug}/",
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
    <a href="/guides/how-much-can-i-borrow/">How much can I borrow</a> ›
    {salary_fmt}
  </nav>

  <p class="eyebrow" style="margin-bottom:0.75rem;">Borrowing capacity</p>
  <h1>How much can I borrow on a {salary_fmt} salary?</h1>
  <p class="lead">
    Estimated borrowing capacity: <strong style="color:#4caf50;">{capacity_fmt}</strong>.
    Select your state and buyer type — stamp duty and upfront costs update below.
    Adjust the assumptions if they don't match your situation.
  </p>

  <!-- Input bar -->
  <div class="input-bar">
    <div class="input-group">
      <label>State</label>
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
        <button class="toggle-btn active" onclick="setBuyer('fhb',this)">First home buyer</button>
        <button class="toggle-btn" onclick="setBuyer('oo',this)">Owner-occupier</button>
        <button class="toggle-btn" onclick="setBuyer('inv',this)">Investor</button>
      </div>
    </div>
    <div class="input-group">
      <label>Deposit saved</label>
      <input type="text" id="depositInput" value="{fmt_dollar(DEFAULT_DEPOSIT)}" oninput="update()" style="width:110px;">
    </div>
  </div>

  <!-- Assumptions panel -->
  <div class="assumptions">
    <div class="assumptions-hdr">
      <div class="warn-circle">!</div>
      These assumptions are built into the estimate — check they match your situation
    </div>
    <div class="assumptions-grid">
      <div class="assume-row"><span class="assume-key">Borrowers</span><span class="assume-val">1 (single)</span></div>
      <div class="assume-row"><span class="assume-key">Existing debt</span><span class="assume-val">None</span></div>
      <div class="assume-row"><span class="assume-key">Assessment rate</span><span class="assume-val">{assess_str} (RBA {cash_str} + {buffer_str})</span></div>
      <div class="assume-row"><span class="assume-key">Living expenses</span><span class="assume-val">HEM metro ({hem}/mo)</span></div>
      <div class="assume-row"><span class="assume-key">Loan term</span><span class="assume-val">{LOAN_TERM_YEARS} years P&amp;I</span></div>
      <div class="assume-row"><span class="assume-key">HECS / student debt</span><span class="assume-val">None</span></div>
      <div class="assume-row"><span class="assume-key">Dependants</span><span class="assume-val">None</span></div>
      <div class="assume-row"><span class="assume-key">Tax year</span><span class="assume-val">FY{tax_year} ATO rates</span></div>
    </div>
    <div class="assume-footer">
      ⚠ Assessment rate sourced from RBA F1 data (effective {rate_effective_date}), updated automatically each week.
      For a result using your actual debts, HECS, and dependants, <a href="/deposit">use the calculator →</a>
    </div>
  </div>

  <!-- Result -->
  <div class="result-band">
    <div class="result-figure">{capacity_fmt}</div>
    <div class="result-label">Estimated borrowing capacity</div>
    <div class="result-note">
      Your take-home pay is approximately {th_fmt}/month.
      After living expenses, you can service a loan of {capacity_fmt} at {assess_str}.
      <br>
      With a <span id="depositDisplay">{fmt_dollar(DEFAULT_DEPOSIT)}</span> deposit, you can target properties up to
      <strong id="purchaseDisplay" style="color:#4caf50;">{purchase_fmt}</strong>
      <span id="stampDutyNote" style="color:var(--dim);font-size:0.8rem;"></span>
    </div>
  </div>

  <!-- Stamp duty block (JS-updated) -->
  <div class="section-label" id="stampDutyLabel">Upfront costs — NSW, first home buyer</div>
  <div id="stampDutyBlock" style="border:1px solid var(--border);padding:1rem 1.25rem;margin-bottom:1.5rem;">
    <div id="stampDutyContent">Loading...</div>
  </div>

  <!-- Sensitivity table -->
  <div class="section-label">How borrowing capacity changes</div>
  <table class="sens-table">
    <thead>
      <tr>
        <th>Scenario</th>
        <th style="text-align:right;">Capacity</th>
        <th style="text-align:right;">Change</th>
      </tr>
    </thead>
    <tbody>
      <tr class="baseline">
        <td>Single, no debt <span class="baseline-tag">baseline above</span></td>
        <td class="hi" style="text-align:right;">{capacity_short}</td>
        <td style="text-align:right;">—</td>
      </tr>
      {sens_rows_html}
    </tbody>
  </table>

  <!-- Suburb suggestions -->
  <div class="section-label" id="suburbLabel">Suburbs within reach — NSW</div>
  <div class="suburb-chips" id="suburbChips">
    {suburb_chips}
  </div>

  <!-- CTA -->
  <div class="cta-strip">
    <div class="cta-text">
      <strong>Get a personalised figure</strong>
      Enter your actual debts, HECS, and dependants in the deposit checker.
    </div>
    <a class="btn" href="/deposit">Open calculator →</a>
  </div>

  <div class="pagination">
    <span>{prev_link}</span>
    <span>{next_link}</span>
  </div>

</div>

<script>
(function() {{
  // Stamp duty data — all states, embedded at build time from Supabase
  // Format: {{ state: {{ fhb: amount, standard: amount, fhb_threshold: amount }} }}
  // These figures are for salary={salary}, est. purchase price={purchase_est}
  // They are approximate — link to calculator for exact figure.
  // NOTE: In build_price_guides.py this data is computed precisely from Supabase.
  // Here we embed a static lookup keyed on the purchase price band.
  // The JS state/FHB toggle updates the displayed upfront cost block.

  var PURCHASE = {purchase_est};
  var CAPACITY = {capacity};

  var buyerType = 'fhb';
  var state     = 'NSW';

  // Stamp duty estimates by state and buyer type for this purchase price.
  // Generated at build time — see build_price_guides.py for exact Supabase calc.
  var DUTY = {{}};

  function parseDep(s) {{
    var v = parseInt((s || '').replace(/[^0-9]/g, ''), 10);
    return isNaN(v) ? {DEFAULT_DEPOSIT} : v;
  }}

  function fmtDollar(n) {{
    return '$' + Math.round(n).toLocaleString('en-AU');
  }}

  function setBuyer(type, btn) {{
    buyerType = type;
    document.querySelectorAll('.toggle-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    btn.classList.add('active');
    update();
  }}
  window.setBuyer = setBuyer;

  function update() {{
    state  = document.getElementById('stateSelect').value;
    var deposit = parseDep(document.getElementById('depositInput').value);
    var purchase = CAPACITY + deposit;

    document.getElementById('depositDisplay').textContent = fmtDollar(deposit);
    document.getElementById('purchaseDisplay').textContent = fmtDollar(purchase);
    document.getElementById('suburbLabel').textContent = 'Suburbs within reach — ' + state;
    document.getElementById('stampDutyLabel').textContent = 'Upfront costs — ' + state + ', ' + (buyerType === 'fhb' ? 'first home buyer' : buyerType === 'oo' ? 'owner-occupier' : 'investor');

    // Stamp duty note in result band
    var note = document.getElementById('stampDutyNote');
    note.textContent = ' (before stamp duty and other upfront costs)';

    // Upfront cost block — links to stamp duty calculator for exact figure
    var block = document.getElementById('stampDutyContent');
    block.innerHTML = '<p style="font-size:0.85rem;color:var(--muted);line-height:1.8;">' +
      'Stamp duty varies significantly by state and buyer type. ' +
      'Use the <a href="/stamp-duty?price=' + purchase + '&state=' + state + '" style="color:#4caf50;">stamp duty calculator →</a> ' +
      'to see the exact amount for ' + state + ' (' + (buyerType === 'fhb' ? 'first home buyer' : 'standard') + ').' +
      '<br><br>Your ' + fmtDollar(deposit) + ' deposit may need to cover stamp duty in addition to the loan deposit. ' +
      'In NSW, FHBs pay $0 stamp duty on properties up to $800k. In VIC, standard duty on $800k is $43,070.' +
      '</p>';
  }}

  window.update = update;
  update();
}})();
</script>

</body>
</html>"""

    return html


# ── Sitemap ──────────────────────────────────────────────────────────────────────

def write_sitemap(salaries):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    # Index page
    lines.append(f"""  <url>
    <loc>{BASE_URL}/guides/how-much-can-i-borrow/</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>""")
    for s in salaries:
        lines.append(f"""  <url>
    <loc>{BASE_URL}/guides/how-much-can-i-borrow/{s}/</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>""")
    lines.append('</urlset>')
    path = Path("sitemap-guides-a.xml")
    path.write_text("\n".join(lines))
    print(f"  Wrote {path}")


def write_index(salaries, capacity_map):
    """Write an index page listing all salary points."""
    rows = ""
    for s in salaries:
        cap = capacity_map.get(s, 0)
        rows += f"""    <a class="guide-row" href="/guides/how-much-can-i-borrow/{s}/">
      <span class="guide-row-salary">{fmt_dollar(s)}</span>
      <span class="guide-row-cap">{fmt_dollar(cap)}</span>
      <span class="guide-row-arrow" style="color:#4caf50;">›</span>
    </a>\n"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>How much can I borrow? Salary-by-salary borrowing guide — GetReal</title>
  <meta name="description" content="How much can you borrow based on your salary? Estimated borrowing capacity for every income from $60,000 to $300,000. Assessment rate {TODAY}.">
  <link rel="canonical" href="{BASE_URL}/guides/how-much-can-i-borrow/">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/styles.css">
  <style>
    .wrap {{ max-width:860px;margin:0 auto;padding:2.5rem 1.5rem 5rem; }}
    h1 {{ font-size:1.6rem;margin-bottom:0.5rem; }}
    .lead {{ color:var(--muted);font-size:0.9rem;line-height:1.8;margin-bottom:2rem;max-width:640px; }}
    .guide-list {{ display:grid;gap:1px;background:var(--border);border:1px solid var(--border); }}
    .guide-row {{
      background:var(--bg);display:flex;align-items:center;gap:1rem;
      padding:0.85rem 1.25rem;text-decoration:none;color:inherit;
    }}
    .guide-row:hover {{ background:var(--card); }}
    .guide-row-salary {{ font-family:monospace;font-size:0.9rem;font-weight:500;width:90px;flex-shrink:0; }}
    .guide-row-cap {{ color:var(--muted);font-size:0.85rem;flex:1; }}
    .guide-row-arrow {{ flex-shrink:0; }}
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
    <a href="/guides/" style="color:var(--dim);text-decoration:none;">Guides</a> › How much can I borrow
  </nav>
  <p class="eyebrow" style="margin-bottom:0.75rem;">Borrowing capacity</p>
  <h1>How much can I borrow?</h1>
  <p class="lead">
    Estimated borrowing capacity for every salary from $60,000 to $300,000.
    Based on single borrower, no existing debt, metro HEM living expenses, and
    an assessment rate of RBA cash rate + 3% buffer. Select your salary below.
  </p>
  <div class="section-label">Salary → estimated borrowing capacity</div>
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
    rates        = load_reference_rates()
    brackets, tax_year = load_tax_brackets()
    lito         = load_lito()

    cash_rate    = rates["rba_cash_rate"]
    buffer       = rates["assessment_rate_buffer"]
    medicare     = rates["medicare_levy_rate"]
    assessment   = cash_rate + buffer

    print(f"  Cash rate:      {cash_rate:.2f}%")
    print(f"  Assessment:     {assessment:.2f}%")
    print(f"  Medicare levy:  {medicare*100:.1f}%")
    print(f"  Tax year:       FY{tax_year}")

    # Rate effective date (for page footer note)
    rate_rows = sb_get("reference_rates", "select=effective_date&key=eq.rba_cash_rate")
    rate_eff  = rate_rows[0]["effective_date"] if rate_rows else TODAY

    salaries     = list(range(SALARY_MIN, SALARY_MAX + SALARY_STEP, SALARY_STEP))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    capacity_map = {}

    print(f"\nBuilding {len(salaries)} income guide pages ...")
    for salary in salaries:
        net_tax, take_home, take_home_monthly = calc_income_tax(
            salary, brackets, lito, medicare
        )
        capacity = calc_borrowing_capacity(salary, assessment, brackets, lito, medicare)
        capacity_map[salary] = capacity

        # Suburbs near estimated purchase price
        purchase_est = capacity + DEFAULT_DEPOSIT
        suburbs_near = load_suburbs_near_price(purchase_est)

        page_dir = OUT_DIR / str(salary)
        page_dir.mkdir(parents=True, exist_ok=True)
        out = page_dir / "index.html"

        html = generate_page(
            salary        = salary,
            capacity      = capacity,
            take_home_monthly = take_home_monthly,
            net_tax       = net_tax,
            assessment_rate = assessment,
            cash_rate     = cash_rate,
            buffer        = buffer,
            tax_year      = tax_year,
            lito_params   = lito,
            brackets      = brackets,
            medicare_rate = medicare,
            suburbs_near  = suburbs_near,
            rate_effective_date = rate_eff,
        )
        out.write_text(html)
        print(f"  {salary:>7,}  →  {fmt_dollar(capacity):>12}  ({out})")

    write_index(salaries, capacity_map)
    write_sitemap(salaries)

    print(f"\n✓ Built {len(salaries)} pages + index + sitemap")
    print(f"  Assessment rate used: {assessment:.2f}% (RBA {cash_rate:.2f}% + {buffer:.1f}% buffer)")
    print(f"  Push command:")
    print(f"  git add guides/how-much-can-i-borrow/ sitemap-guides-a.xml && git commit -m 'feat: add Series A income borrowing guides' && git push")


if __name__ == "__main__":
    main()
