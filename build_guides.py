#!/usr/bin/env python3
"""
GetReal — Guide page builder.

Fetches stamp duty data from Supabase, calculates duty at key price points,
and generates static HTML pages for:
  - 6 concept pages at /guides/{slug}
  - 8 stamp duty state pages at /guides/stamp-duty/{state-lower}

Run: python3 build_guides.py

Pages auto-update whenever this script runs — stamp duty figures always come
from Supabase (the single source of truth), not from hardcoded data here.
"""

import json
import math
import os
import re
from datetime import date
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from guides_data import CONCEPT_PAGES, STAMP_DUTY_EDITORIAL

# ─── Config ──────────────────────────────────────────────────────────────────

SB_URL = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SB_KEY = "sb_publishable_1jyBD0hVdHX2ieqFIlC51A_A3ep39Bc"
HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"}

BASE_URL = "https://get-real.co"
TODAY = date.today().isoformat()

# Price points to calculate stamp duty at (in dollars)
PRICE_POINTS = [400_000, 500_000, 600_000, 700_000, 750_000, 800_000,
                900_000, 1_000_000, 1_200_000, 1_500_000, 2_000_000]


# ─── Supabase fetchers ────────────────────────────────────────────────────────

def fetch_table(table, select="*", filters=None):
    """Fetch all rows from a Supabase table with optional filters."""
    params = {"select": select}
    if filters:
        params.update(filters)
    r = requests.get(f"{SB_URL}/rest/v1/{table}", headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


def load_stamp_duty_data():
    """Return brackets, concessions, and NT formula.

    Tries Supabase first. Falls back to _supabase_cache.json if the
    network is unavailable (e.g. running in a sandboxed environment).
    """
    cache_path = Path(__file__).parent / "_supabase_cache.json"

    raw_brackets = raw_concessions = raw_nt = None

    if REQUESTS_AVAILABLE:
        try:
            raw_brackets = fetch_table("stamp_duty_brackets", select="*",
                                        filters={"order": "state,bracket_set,bracket_min"})
            raw_concessions = fetch_table("stamp_duty_concessions")
            raw_nt = fetch_table("nt_duty_formula")
            print("   (data source: Supabase live)")
        except Exception as e:
            print(f"   ⚠️  Supabase unavailable ({e.__class__.__name__}), falling back to cache")

    if raw_brackets is None:
        if not cache_path.exists():
            raise FileNotFoundError(f"No Supabase connection and no cache at {cache_path}")
        cache = json.loads(cache_path.read_text())
        raw_brackets = cache["stamp_duty_brackets"]
        raw_concessions = cache["stamp_duty_concessions"]
        raw_nt = cache["nt_duty_formula"]
        print("   (data source: _supabase_cache.json)")

    # Group brackets: { state → { bracket_set → [bracket, …] } }
    # Strip trailing spaces from state codes (DB artifact for SA, WA, NT)
    brackets = {}
    for b in raw_brackets:
        state = b["state"].strip()
        bset = b["bracket_set"]
        brackets.setdefault(state, {}).setdefault(bset, []).append(b)

    # Index concessions: { state → { concession_key → value } }
    concessions = {}
    for c in raw_concessions:
        state = c["state"].strip()
        concessions.setdefault(state, {})[c["concession_key"]] = float(c["value"])

    nt_formula = raw_nt[0] if raw_nt else None

    return brackets, concessions, nt_formula


# ─── Stamp duty calculator ────────────────────────────────────────────────────

def calc_duty_brackets(price, bracket_list):
    """Progressive bracket calculation. Returns duty in dollars."""
    duty = 0.0
    for b in bracket_list:
        bmin = float(b["bracket_min"])
        bmax = float(b["bracket_max"]) if b["bracket_max"] else math.inf
        rate = float(b["rate"])
        base = float(b["base_amount"])
        is_full = b.get("is_full_price", False)

        if price < bmin:
            break
        if is_full:
            # Flat rate on full price (e.g. VIC $960k–$2M band)
            if bmin <= price <= bmax:
                duty = price * rate
                break
        else:
            # Standard progressive: base + rate × (price – bracket_min)
            top = min(price, bmax)
            duty = base + rate * (top - bmin)

    return duty


def calc_nt_duty(price, formula):
    """NT quadratic formula. Returns duty in dollars."""
    threshold = float(formula["formula_threshold"])
    flat_rate = float(formula["flat_rate_above"])
    coeff_a = float(formula["coeff_a"])
    coeff_b = float(formula["coeff_b"])
    divisor = float(formula["divisor"])

    if price > threshold:
        return price * flat_rate

    V = price / divisor
    return (coeff_a * V * V + coeff_b * V) / 1000.0 * divisor


def calc_stamp_duty(price, state, is_fhb, is_oo, brackets, concessions, nt_formula):
    """
    Calculate stamp duty for a given price, state, and buyer type.
    Returns (duty_dollars, concession_applied, concession_label).
    """
    conc = concessions.get(state, {})
    state_brackets = brackets.get(state, {})

    # ─── NT ───────────────────────────────────────────────────────────────────
    if state == "NT":
        if nt_formula is None:
            return None, False, ""
        base_duty = calc_nt_duty(price, nt_formula)
        if is_fhb:
            rebate = float(conc.get("fhb_max_discount", 18601))
            phaseout_start = float(conc.get("fhb_phaseout_start", 500_000))
            phaseout_end = float(conc.get("fhb_price_cap", 650_000))  # end of phaseout, not an offset
            if price <= phaseout_start:
                base_duty = max(0, base_duty - rebate)
                return base_duty, True, f"${rebate:,.0f} FHB rebate"
            elif price < phaseout_end:
                taper = 1 - (price - phaseout_start) / (phaseout_end - phaseout_start)
                taper_rebate = rebate * taper
                base_duty = max(0, base_duty - taper_rebate)
                return base_duty, True, f"partial FHB rebate"
        return base_duty, False, ""

    # ─── VIC — dual bracket sets ───────────────────────────────────────────
    if state == "VIC":
        ppr_cap = float(conc.get("ppr_price_cap", 550_000))
        use_ppr = is_oo and price <= ppr_cap

        bset_name = "vic_ppr" if use_ppr else "standard"
        blist = state_brackets.get(bset_name, state_brackets.get("standard", []))
        base_duty = calc_duty_brackets(price, blist)

        # FHB concessions
        if is_fhb:
            exempt_thresh = float(conc.get("fhb_exempt_threshold", 600_000))
            taper_top = float(conc.get("fhb_taper_top", 750_000))
            if price <= exempt_thresh:
                return 0.0, True, "FHB full exemption"
            elif price < taper_top:
                taper = 1 - (price - exempt_thresh) / (taper_top - exempt_thresh)
                return max(0, base_duty * (1 - taper)), True, "FHB partial concession"

        return base_duty, False, ""

    # ─── All other states (standard bracket tables) ───────────────────────
    blist = state_brackets.get("standard", [])
    base_duty = calc_duty_brackets(price, blist)

    if is_fhb:
        exempt_thresh = conc.get("fhb_exempt_threshold")
        taper_top = conc.get("fhb_taper_top")
        discount_pct = conc.get("fhb_discount_pct")
        price_cap = conc.get("fhb_price_cap")

        # SA has no FHB concession
        if state == "SA":
            return base_duty, False, ""

        # NSW: full exemption under $800k, taper to $1M
        if exempt_thresh and price <= exempt_thresh:
            return 0.0, True, "FHB full exemption"

        if exempt_thresh and taper_top and price < taper_top:
            taper = 1 - (price - exempt_thresh) / (taper_top - exempt_thresh)
            return max(0, base_duty * (1 - taper)), True, "FHB partial concession"

        # WA / TAS: percentage discount below a price cap
        if discount_pct and price_cap and price <= price_cap:
            pct = float(discount_pct) / 100.0
            return max(0, base_duty * (1 - pct)), True, f"{discount_pct:.0f}% FHB concession"

        # Percentage discount with no price cap
        if discount_pct and not price_cap:
            pct = float(discount_pct) / 100.0
            return max(0, base_duty * (1 - pct)), True, f"{discount_pct:.0f}% FHB concession"

    return base_duty, False, ""


def build_duty_table(state, brackets, concessions, nt_formula):
    """
    Build a list of dicts with duty at each price point for a state.
    Returns: [{price, standard_duty, oo_fhb_duty, investor_duty}, …]
    """
    rows = []
    for price in PRICE_POINTS:
        std, _, _ = calc_stamp_duty(price, state, False, True, brackets, concessions, nt_formula)
        fhb, conc_applied, conc_label = calc_stamp_duty(price, state, True, True, brackets, concessions, nt_formula)
        inv, _, _ = calc_stamp_duty(price, state, False, False, brackets, concessions, nt_formula)
        rows.append({
            "price": price,
            "standard_duty": std,
            "fhb_duty": fhb,
            "fhb_concession": conc_label if conc_applied else "",
            "investor_duty": inv,
        })
    return rows


# ─── HTML helpers ─────────────────────────────────────────────────────────────

def fmt_dollar(val):
    if val is None:
        return "N/A"
    if val == 0:
        return "$0"
    return f"${val:,.0f}"


def breadcrumb_json(crumbs):
    """Generate BreadcrumbList JSON-LD."""
    items = [
        {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
        for i, (name, url) in enumerate(crumbs)
    ]
    return json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}, indent=2)


def faq_json(faqs):
    """Generate FAQPage JSON-LD."""
    return json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": faq["q"],
             "acceptedAnswer": {"@type": "Answer", "text": faq["a"]}}
            for faq in faqs
        ]
    }, indent=2)


NAV_HTML = """<header class="site-header">
  <a class="brand" href="/">
    <svg width="22" height="22" viewBox="0 0 26 26" fill="none">
      <circle cx="13" cy="13" r="11.5" stroke="#18181b" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="6.5" stroke="#18181b" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="2.5" fill="#18181b"/>
    </svg>
    <span class="brand-name">GetReal</span>
  </a>
  <nav class="site-nav-links">
    <a href="/deposit">Borrowing ceiling</a>
    <a href="/stamp-duty">Stamp duty</a>
    <a href="/guides/">Guides</a>
    <a href="/methodology">Methodology</a>
  </nav>
</header>"""

FOOTER_HTML = """<footer class="site-footer">
  <p>GetReal is a free tool. Data from NSW and Victorian Valuer Generals. Not financial advice.</p>
  <p><a href="/methodology">Methodology</a> · <a href="/faq">FAQ</a> · <a href="/manifesto">Manifesto</a></p>
</footer>"""

STYLES = """<link rel="stylesheet" href="/styles.css">
<style>
  .guide-container { max-width: 800px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
  .guide-answer { border-left: 4px solid var(--green); padding: 1.25rem 1.5rem; margin: 2rem 0; background: rgba(0,255,127,0.04); }
  .guide-answer p { margin: 0; font-size: 1.05rem; line-height: 1.7; }
  .guide-section { margin: 2.5rem 0; }
  .guide-section h2 { font-size: 1.25rem; letter-spacing: 0.02em; margin-bottom: 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
  .worked-example { background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 1.25rem 1.5rem; }
  .worked-example-label { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 1rem; }
  .example-row { display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid var(--border); font-size: 0.95rem; }
  .example-row:last-child { border-bottom: none; }
  .example-val { color: var(--green); font-variant-numeric: tabular-nums; }
  .key-factors { list-style: none; padding: 0; margin: 0; }
  .key-factors li { padding: 0.6rem 0 0.6rem 1.5rem; border-bottom: 1px solid var(--border); font-size: 0.95rem; line-height: 1.6; position: relative; }
  .key-factors li::before { content: "→"; position: absolute; left: 0; color: var(--green); }
  .key-factors li:last-child { border-bottom: none; }
  .faq-item { margin: 1.5rem 0; }
  .faq-q { font-weight: 600; margin-bottom: 0.5rem; }
  .faq-a { color: var(--muted); line-height: 1.7; font-size: 0.95rem; }
  .cta-block { border: 1px solid var(--green); padding: 1.5rem; text-align: center; margin: 3rem 0; }
  .cta-block p { margin: 0 0 1rem; color: var(--muted); }
  .duty-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
  .duty-table th { text-align: left; padding: 0.6rem 0.8rem; background: var(--surface); border-bottom: 2px solid var(--border); font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }
  .duty-table td { padding: 0.55rem 0.8rem; border-bottom: 1px solid var(--border); font-variant-numeric: tabular-nums; }
  .duty-table tr:last-child td { border-bottom: none; }
  .duty-table .price-col { font-weight: 600; }
  .duty-table .fhb-col { color: var(--green); }
  .concession-note { font-size: 0.75rem; color: var(--muted); display: block; }
  .key-notes { list-style: none; padding: 0; margin: 0; }
  .key-notes li { padding: 0.5rem 0 0.5rem 1.5rem; border-bottom: 1px solid var(--border); font-size: 0.95rem; line-height: 1.6; position: relative; }
  .key-notes li::before { content: "▸"; position: absolute; left: 0; color: var(--muted); }
  .key-notes li:last-child { border-bottom: none; }
  .breadcrumb { font-size: 0.8rem; color: var(--muted); margin-bottom: 2rem; }
  .breadcrumb a { color: var(--muted); text-decoration: none; }
  .breadcrumb a:hover { color: var(--fg); }
  .breadcrumb span { margin: 0 0.4em; }
  .authority-link { font-size: 0.85rem; color: var(--muted); margin-top: 1rem; }
  .authority-link a { color: var(--green); }
</style>"""


# ─── Page builders ────────────────────────────────────────────────────────────

def build_concept_page(page):
    slug = page["slug"]
    title = page["title"]
    meta_desc = page["meta_description"]
    answer = page["answer"]
    how_it_affects = page["how_it_affects"]
    worked = page["worked_example"]
    key_factors = page["key_factors"]
    faqs = page["faqs"]
    calc_url = page["calculator_url"]
    calc_label = page["calculator_label"]
    meth_anchor = page["methodology_anchor"]

    canonical = f"{BASE_URL}/guides/{slug}"
    crumbs = [
        ("Home", BASE_URL + "/"),
        ("Guides", BASE_URL + "/guides"),
        (title, canonical),
    ]

    schema_article = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": meta_desc,
        "url": canonical,
        "datePublished": "2026-08-07",
        "dateModified": TODAY,
        "author": {"@type": "Organization", "name": "GetReal"},
        "publisher": {"@type": "Organization", "name": "GetReal", "url": BASE_URL},
    }, indent=2)

    worked_rows = "".join(
        f'<div class="example-row"><span>{label}</span><span class="example-val">{val}</span></div>'
        for label, val in worked["lines"]
    )

    faq_html = "".join(
        f'<div class="faq-item"><p class="faq-q">{faq["q"]}</p><p class="faq-a">{faq["a"]}</p></div>'
        for faq in faqs
    )

    kf_html = "".join(f"<li>{kf}</li>" for kf in key_factors)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | GetReal</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="article:published_time" content="2026-08-07">
  <meta property="article:modified_time" content="{TODAY}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{meta_desc}">
  {STYLES}
  <script type="application/ld+json">{schema_article}</script>
  <script type="application/ld+json">{faq_json(faqs)}</script>
  <script type="application/ld+json">{breadcrumb_json(crumbs)}</script>
</head>
<body>
  {NAV_HTML}

  <main class="guide-container">
    <div class="breadcrumb">
      <a href="/">Home</a><span>›</span>
      <a href="/guides">Guides</a><span>›</span>
      {title}
    </div>

    <h1>{title}</h1>

    <div class="guide-answer">
      <p>{answer}</p>
    </div>

    <div class="guide-section">
      <h2>How it affects your borrowing</h2>
      <p>{how_it_affects}</p>
    </div>

    <div class="guide-section">
      <h2>Worked example</h2>
      <div class="worked-example">
        <div class="worked-example-label">{worked["label"]}</div>
        {worked_rows}
      </div>
    </div>

    <div class="guide-section">
      <h2>Key factors</h2>
      <ul class="key-factors">{kf_html}</ul>
    </div>

    <div class="cta-block">
      <p>See how this affects your specific situation</p>
      <a href="{calc_url}" class="btn">{calc_label}</a>
    </div>

    <div class="guide-section">
      <h2>Frequently asked questions</h2>
      {faq_html}
    </div>

    <div class="guide-section">
      <p style="font-size:0.85rem;color:var(--muted);">
        This page is part of GetReal's <a href="/methodology#{meth_anchor}">methodology documentation</a>.
        Figures are updated when underlying data in our Supabase database changes.
        This is not financial advice.
      </p>
    </div>
  </main>

  {FOOTER_HTML}
</body>
</html>"""


def build_stamp_duty_page(state_code, editorial, duty_rows):
    slug = editorial["slug"]
    title = editorial["title"]
    meta_desc = editorial["meta_description"]
    answer = editorial["answer"]
    key_notes = editorial["key_notes"]
    faqs = editorial["faqs"]
    authority = editorial["authority"]
    authority_url = editorial["authority_url"]
    state_name = title.split(" — ")[0].replace("Stamp duty in ", "").replace("Stamp duty in the ", "The ")

    canonical = f"{BASE_URL}/guides/{slug}"
    crumbs = [
        ("Home", BASE_URL + "/"),
        ("Stamp duty calculator", BASE_URL + "/stamp-duty"),
        (title, canonical),
    ]

    schema_article = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": meta_desc,
        "url": canonical,
        "datePublished": "2026-08-07",
        "dateModified": TODAY,
        "author": {"@type": "Organization", "name": "GetReal"},
        "publisher": {"@type": "Organization", "name": "GetReal", "url": BASE_URL},
        "about": {"@type": "Thing", "name": f"Stamp duty in {state_code}"},
        "citation": [{"@type": "WebSite", "name": authority, "url": authority_url}],
    }, indent=2)

    faq_html = "".join(
        f'<div class="faq-item"><p class="faq-q">{faq["q"]}</p><p class="faq-a">{faq["a"]}</p></div>'
        for faq in faqs
    )

    kn_html = "".join(f"<li>{kn}</li>" for kn in key_notes)

    # Duty table rows
    table_rows_html = ""
    for row in duty_rows:
        price = row["price"]
        std = row["standard_duty"]
        fhb = row["fhb_duty"]
        conc = row["fhb_concession"]
        inv = row["investor_duty"]

        # If investor == standard, don't show a separate column (most states)
        fhb_cell = fmt_dollar(fhb)
        if conc:
            fhb_cell += f'<span class="concession-note">{conc}</span>'

        table_rows_html += f"""<tr>
          <td class="price-col">{fmt_dollar(price)}</td>
          <td>{fmt_dollar(std)}</td>
          <td class="fhb-col">{fhb_cell}</td>
          <td>{fmt_dollar(inv)}</td>
        </tr>"""

    # Show investor column note
    investor_col_note = ""
    if state_code in ("VIC",):
        investor_col_note = "(standard rate applies to investors when price > $550,000)"
    elif state_code in ("NSW", "WA", "SA", "TAS", "QLD", "ACT", "NT"):
        investor_col_note = "(same rate as owner-occupier in this state)"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | GetReal</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="article:published_time" content="2026-08-07">
  <meta property="article:modified_time" content="{TODAY}">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{meta_desc}">
  {STYLES}
  <script type="application/ld+json">{schema_article}</script>
  <script type="application/ld+json">{faq_json(faqs)}</script>
  <script type="application/ld+json">{breadcrumb_json(crumbs)}</script>
</head>
<body>
  {NAV_HTML}

  <main class="guide-container">
    <div class="breadcrumb">
      <a href="/">Home</a><span>›</span>
      <a href="/stamp-duty">Stamp duty calculator</a><span>›</span>
      {state_name} rates
    </div>

    <h1>{title}</h1>
    <p style="font-size:0.85rem;color:var(--muted);margin-bottom:2rem;">
      Rates calculated from <a href="{authority_url}" target="_blank" rel="noopener">{authority}</a> data,
      stored in GetReal's Supabase database. Updated when official rates change. Last built: {TODAY}.
    </p>

    <div class="guide-answer">
      <p>{answer}</p>
    </div>

    <div class="guide-section">
      <h2>Key points</h2>
      <ul class="key-notes">{kn_html}</ul>
    </div>

    <div class="guide-section">
      <h2>Stamp duty by purchase price — {state_code} 2026</h2>
      <div style="overflow-x:auto;">
        <table class="duty-table">
          <thead>
            <tr>
              <th>Purchase price</th>
              <th>Standard duty</th>
              <th>FHB duty</th>
              <th>Investor duty <span style="font-weight:normal;text-transform:none;letter-spacing:0;">{investor_col_note}</span></th>
            </tr>
          </thead>
          <tbody>{table_rows_html}</tbody>
        </table>
      </div>
      <p class="authority-link">
        Source: <a href="{authority_url}" target="_blank" rel="noopener">{authority}</a>.
        FHB = first home buyer purchasing owner-occupied principal place of residence.
        Standard = all other buyers. These are indicative figures — confirm with your conveyancer.
      </p>
    </div>

    <div class="cta-block">
      <p>Calculate stamp duty for your exact purchase price and situation</p>
      <a href="/stamp-duty" class="btn">Open stamp duty calculator</a>
    </div>

    <div class="guide-section">
      <h2>Frequently asked questions</h2>
      {faq_html}
    </div>

    <div class="guide-section">
      <p style="font-size:0.85rem;color:var(--muted);">
        Stamp duty rates are sourced from official government data and stored in GetReal's database.
        This page is rebuilt whenever rates change. See <a href="/methodology#stamp-duty">methodology</a>
        for calculation details. This is not financial advice — confirm with your conveyancer or the
        relevant state revenue authority.
      </p>
    </div>
  </main>

  {FOOTER_HTML}
</body>
</html>"""


# ─── Sitemap updater ──────────────────────────────────────────────────────────

def update_sitemap(new_urls, sitemap_path):
    """Add new URL entries to sitemap.xml if not already present."""
    text = Path(sitemap_path).read_text()

    entries_added = 0
    for url in new_urls:
        if url in text:
            continue
        new_entry = f"""
  <url>
    <loc>{url}</loc>
    <lastmod>{TODAY}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>"""
        text = text.replace("</urlset>", new_entry + "\n</urlset>")
        entries_added += 1

    Path(sitemap_path).write_text(text)
    return entries_added


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    script_dir = Path(__file__).parent
    guides_dir = script_dir / "guides"
    stamp_dir = guides_dir / "stamp-duty"
    sitemap_path = script_dir / "sitemap.xml"

    print("📡 Fetching stamp duty data from Supabase...")
    brackets, concessions, nt_formula = load_stamp_duty_data()
    print(f"   {sum(len(v) for s in brackets.values() for v in s.values())} bracket rows")
    print(f"   {sum(len(v) for v in concessions.values())} concession rows")
    print(f"   NT formula: {'found' if nt_formula else 'NOT FOUND'}")

    guides_dir.mkdir(exist_ok=True)
    stamp_dir.mkdir(exist_ok=True)

    new_sitemap_urls = []

    # ─── Concept pages ─────────────────────────────────────────────────────
    print("\n📄 Building concept pages...")
    for page in CONCEPT_PAGES:
        slug = page["slug"]
        html = build_concept_page(page)
        out = guides_dir / f"{slug}.html"
        out.write_text(html, encoding="utf-8")
        url = f"{BASE_URL}/guides/{slug}"
        new_sitemap_urls.append(url)
        print(f"   ✓ {out.relative_to(script_dir)}")

    # ─── Stamp duty pages ───────────────────────────────────────────────────
    print("\n📄 Building stamp duty pages...")
    for state_code, editorial in STAMP_DUTY_EDITORIAL.items():
        duty_rows = build_duty_table(state_code, brackets, concessions, nt_formula)
        html = build_stamp_duty_page(state_code, editorial, duty_rows)
        slug_parts = editorial["slug"].split("/")  # "stamp-duty/nsw"
        out = stamp_dir / f"{slug_parts[-1]}.html"
        out.write_text(html, encoding="utf-8")
        url = f"{BASE_URL}/guides/{editorial['slug']}"
        new_sitemap_urls.append(url)
        print(f"   ✓ {out.relative_to(script_dir)}")

        # Quick sanity check — print duty at $800k
        row_800 = next((r for r in duty_rows if r["price"] == 800_000), None)
        if row_800:
            print(f"      $800k → standard {fmt_dollar(row_800['standard_duty'])} | FHB {fmt_dollar(row_800['fhb_duty'])}")

    # ─── Sitemap ────────────────────────────────────────────────────────────
    if sitemap_path.exists():
        added = update_sitemap(new_sitemap_urls, sitemap_path)
        print(f"\n🗺  Sitemap updated: {added} new URLs added")
    else:
        print(f"\n⚠️  sitemap.xml not found at {sitemap_path} — skipping update")

    print(f"\n✅ Done — {len(CONCEPT_PAGES)} concept pages, {len(STAMP_DUTY_EDITORIAL)} stamp duty pages")
    print(f"   Output: {guides_dir}")
    print(f"\n   Git commands for Tristan:")
    print(f"   git add guides/ sitemap.xml guides_data.py build_guides.py")
    print(f"   git commit -m \"Add GEO guide pages — {len(CONCEPT_PAGES)} concept + {len(STAMP_DUTY_EDITORIAL)} stamp duty by state\"")
    print(f"   git push")


if __name__ == "__main__":
    main()
