#!/usr/bin/env python3
"""
build_methodology_pages.py
Generates /methodology/{slug}.html — one deep-linkable page per topic.
Run from the repo root. Outputs to methodology/ directory.
"""

import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "methodology")
os.makedirs(OUT_DIR, exist_ok=True)

SHARED_STYLES = """
  <style>
    .meth-wrap { max-width:700px; margin:0 auto; padding:2rem var(--pad-page) 5rem; }
    .meth-eyebrow { font-family:var(--font-mono); font-size:0.65rem; color:var(--dim); letter-spacing:0.1em; text-transform:uppercase; margin-bottom:0.5rem; }
    .meth-title { font-size:clamp(1.6rem,6vw,2.4rem); font-weight:800; line-height:1.1; margin-bottom:0.5rem; }
    .meth-version { font-family:var(--font-mono); font-size:0.62rem; color:var(--dim); letter-spacing:0.06em; margin-bottom:1.5rem; }
    .meth-lead { font-size:0.88rem; color:var(--muted); font-family:var(--font-mono); line-height:1.7; margin-bottom:2rem; border-left:2px solid var(--border); padding:0.5rem 0.9rem; }
    .meth-body { font-size:0.88rem; color:var(--muted); line-height:1.8; display:flex; flex-direction:column; gap:1rem; }
    .meth-body p { margin:0; }
    .meth-body strong { color:var(--text); }
    .meth-body a { color:var(--dim); text-decoration:underline; text-underline-offset:2px; }
    .meth-body a:hover { color:var(--text); }
    .rule-box { background:rgba(0,221,56,0.04); border-left:3px solid #00b02c; padding:0.85rem 1rem; font-size:0.88rem; color:var(--text); line-height:1.65; font-weight:500; }
    .formula { background:var(--card); border:1px solid var(--border); border-left:3px solid #555; padding:1rem 1.15rem; font-family:var(--font-mono); font-size:0.75rem; color:var(--muted); line-height:1.8; overflow-x:auto; white-space:pre; }
    .formula .kw { color:var(--text); font-weight:700; }
    .formula .cm { color:#444; }
    .formula .hl { color:#f0a500; }
    .data-table { width:100%; border-collapse:collapse; font-family:var(--font-mono); font-size:0.73rem; }
    .data-table th { text-align:left; color:var(--dim); font-weight:400; letter-spacing:0.06em; text-transform:uppercase; font-size:0.62rem; padding:0.4rem 0.75rem 0.4rem 0; border-bottom:1px solid var(--border); }
    .data-table td { padding:0.5rem 0.75rem 0.5rem 0; color:var(--muted); border-bottom:1px solid #1f1f1f; vertical-align:top; }
    .data-table td:first-child { color:var(--text); font-weight:700; }
    .data-table tr:last-child td { border-bottom:none; }
    .example-box { background:var(--card); border:1px solid var(--border); padding:1rem 1.15rem; }
    .example-label { font-family:var(--font-mono); font-size:0.6rem; color:var(--dim); text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.6rem; }
    .example-body { font-family:var(--font-mono); font-size:0.75rem; color:var(--muted); line-height:1.75; }
    .example-body .hl { color:var(--text); font-weight:700; }
    .advisory { background:rgba(240,165,0,0.05); border-left:2px solid #f0a500; padding:0.7rem 0.9rem; font-family:var(--font-mono); font-size:0.72rem; color:var(--muted); line-height:1.65; }
    .advisory strong { color:var(--text); }
    .note-box { background:var(--card); border-left:2px solid var(--border); padding:0.65rem 0.9rem; font-family:var(--font-mono); font-size:0.7rem; color:var(--dim); line-height:1.65; }
    .note-box a { color:var(--dim); text-decoration:underline; }
    .source-link { display:inline-flex; align-items:center; gap:0.4rem; font-family:var(--font-mono); font-size:0.65rem; color:var(--dim); text-decoration:underline; text-underline-offset:2px; letter-spacing:0.04em; }
    .source-link:hover { color:var(--muted); }
    .subsection-title { font-size:0.9rem; font-weight:700; color:var(--text); margin-top:0.25rem; }
    .related-pages { border-top:1px solid var(--border); padding-top:1.5rem; margin-top:1rem; }
    .related-label { font-family:var(--font-mono); font-size:0.62rem; color:var(--dim); text-transform:uppercase; letter-spacing:0.1em; margin-bottom:0.75rem; }
    .related-list { display:flex; flex-wrap:wrap; gap:0.5rem; }
    .related-list a { font-family:var(--font-mono); font-size:0.7rem; color:var(--dim); text-decoration:none; border:1px solid var(--border); padding:0.3rem 0.7rem; }
    .related-list a:hover { color:var(--text); border-color:var(--muted); }
    .meth-footer { border-top:1px solid var(--border); padding-top:1.5rem; font-family:var(--font-mono); font-size:0.68rem; color:var(--dim); line-height:1.8; margin-top:2rem; }
  </style>
"""

def page(slug, title, description, version, body_html, related, faq_items=None, sources=None):
    canonical = f"https://get-real.co/methodology/{slug}"
    breadcrumb_json = f"""{{
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{"@type":"ListItem","position":1,"name":"GetReal","item":"https://get-real.co/"}},
        {{"@type":"ListItem","position":2,"name":"Methodology","item":"https://get-real.co/methodology"}},
        {{"@type":"ListItem","position":3,"name":"{title}","item":"{canonical}"}}
      ]
    }}"""

    article_json = f"""{{
      "@type": "Article",
      "@id": "{canonical}#article",
      "headline": "{title} — GetReal Methodology",
      "description": "{description}",
      "url": "{canonical}",
      "datePublished": "2025-01-01",
      "dateModified": "2026-08-07",
      "author": {{"@type":"Organization","name":"GetReal","url":"https://get-real.co"}},
      "publisher": {{"@type":"Organization","name":"GetReal","url":"https://get-real.co"}},
      "inLanguage": "en-AU",
      "isPartOf": {{"@type":"WebPage","url":"https://get-real.co/methodology"}}
    }}"""

    faq_json = ""
    if faq_items:
        items = ",\n          ".join([
            f'{{"@type":"Question","name":"{q}","acceptedAnswer":{{"@type":"Answer","text":"{a}"}}}}'
            for q, a in faq_items
        ])
        faq_json = f""",
    {{
      "@type": "FAQPage",
      "mainEntity": [
          {items}
      ]
    }}"""

    related_links = "\n".join([
        f'          <a href="{r_slug}">{r_label}</a>'
        for r_slug, r_label in related
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — GetReal Methodology</title>
  <meta name="description" content="{description}">
  <link rel="icon" href="../favicon.svg" type="image/svg+xml">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title} — GetReal Methodology">
  <meta property="og:description" content="{description}">
  <meta property="og:image" content="https://get-real.co/og-image.png">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="GetReal">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="https://get-real.co/og-image.png">
  <meta name="twitter:title" content="{title} — GetReal Methodology">
  <meta name="twitter:description" content="{description}">
  <meta name="article:published_time" content="2025-01-01">
  <meta name="article:modified_time" content="2026-08-07">
  <link rel="canonical" href="{canonical}">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@graph": [
      {article_json},
      {breadcrumb_json}{faq_json}
    ]
  }}
  </script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../styles.css">
{SHARED_STYLES}
</head>
<body>

<header class="site-header">
  <a class="brand" href="../index.html">
    <svg width="22" height="22" viewBox="0 0 26 26" fill="none">
      <circle cx="13" cy="13" r="11.5" stroke="#18181b" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="6.5" stroke="#18181b" stroke-width="1.5"/>
      <circle cx="13" cy="13" r="2.5" fill="#18181b"/>
    </svg>
    <span class="brand-name">GetReal</span>
  </a>
</header>

<div class="meth-wrap">

  <div style="margin-bottom:1.5rem;display:flex;gap:1.5rem;flex-wrap:wrap;">
    <a href="../index.html" style="font-family:var(--font-mono);font-size:0.68rem;color:var(--dim);text-decoration:underline;letter-spacing:0.06em;text-transform:uppercase;">← Home</a>
    <a href="../methodology.html" style="font-family:var(--font-mono);font-size:0.68rem;color:var(--dim);text-decoration:underline;letter-spacing:0.06em;text-transform:uppercase;">← All methodology</a>
  </div>

  <div class="meth-eyebrow">GetReal — Methodology</div>
  <h1 class="meth-title">{title}</h1>
  <div class="meth-version">{version}</div>

  <div class="meth-body">
{body_html}

    <div class="related-pages">
      <div class="related-label">Related methodology</div>
      <div class="related-list">
{related_links}
      </div>
    </div>
  </div>

  <div class="meth-footer">
    <p>GetReal is an informational tool. Nothing on this page is financial advice. Consult a licensed mortgage broker before making property decisions.</p>
    <p style="margin-top:0.5rem;">See something wrong? <a href="mailto:hello@get-real.co" style="color:var(--dim);text-decoration:underline;">hello@get-real.co</a></p>
  </div>

</div>
</body>
</html>"""


# ── PAGE DEFINITIONS ──────────────────────────────────────────────────────────

PAGES = []

# 1. BORROWING CAPACITY (synthesis page — ties together C1/C2/C3)
PAGES.append(page(
    slug="borrowing-capacity",
    title="Borrowing capacity",
    description="How Australian lenders calculate maximum borrowing capacity. Three ceilings: deposit (LVR), debt-to-income ratio, and serviceability stress test. GetReal calculates all three and shows which one limits you.",
    version="v1.0 — August 2026",
    faq_items=[
        ("How do Australian lenders calculate borrowing capacity?",
         "Australian lenders assess borrowing capacity against three separate limits — called ceilings — and apply whichever is lowest. Ceiling 1 is the deposit ceiling: how much you can borrow given your available savings after stamp duty, LMI, and fees. Ceiling 2 is the debt-to-income ceiling: total debt cannot exceed 6 times gross annual income. Ceiling 3 is the serviceability ceiling: your monthly net income minus all committed expenses must cover monthly repayments at your interest rate plus a 3% APRA buffer. GetReal calculates all three and shows which one is binding."),
        ("What is the maximum borrowing capacity in Australia?",
         "There is no single maximum — it depends on income, savings, debts, expenses, property type, and state. As a rough guide, a single borrower on $100,000 gross income with no debts and a 20% deposit might borrow up to $550,000–$650,000 under the serviceability ceiling (stress-tested at approximately 9.49%). GetReal calculates your specific ceilings based on your actual inputs."),
        ("Which ceiling limits most Australian borrowers?",
         "For most borrowers in capital cities, the serviceability ceiling (Ceiling 3) is the binding constraint — income relative to living costs and the stress-test rate is the most common limit. For first home buyers with small deposits, the deposit ceiling (Ceiling 1) often binds first. High-income borrowers with multiple existing debts may hit the debt-to-income ceiling (Ceiling 2)."),
    ],
    body_html="""    <div class="rule-box">
      Australian lenders assess borrowing capacity against three separate limits. GetReal calculates all three and shows which one limits you — because optimising for the wrong ceiling is a common and costly mistake.
    </div>

    <p>Most people think of borrowing capacity as a single number. It isn't. It's the lowest of three independent ceilings, each calculated differently and each affected by different inputs. Understanding which ceiling is binding tells you which lever actually matters.</p>

    <p class="subsection-title">Ceiling 1 — Deposit</p>
    <p>How much can you buy given your savings? After stamp duty, LMI (if LVR &gt; 80%), and transfer fees are deducted from your deposit, the remainder sets your maximum purchase price via the applicable LVR limit. This ceiling is entirely about savings — income doesn't help if you don't have the deposit.</p>
    <div class="formula"><span class="kw">Available deposit</span> = savings − stamp_duty − fees − lmi_stamp_duty
<span class="kw">Max price</span>      = available_deposit ÷ (1 − max_LVR)
<span class="cm">// Solved iteratively — stamp duty and LMI are both price-dependent</span></div>
    <p>→ See <a href="lvr">LVR limits</a>, <a href="lmi">LMI calculation</a>, <a href="stamp-duty">Stamp duty</a></p>

    <p class="subsection-title">Ceiling 2 — Debt-to-income ratio</p>
    <p>Total debt across all loans cannot exceed 6 times gross annual income. Credit card limits count in full regardless of balance. HECS/HELP is excluded since 30 September 2025. This ceiling is income-driven — adding a co-borrower's income can significantly increase it.</p>
    <div class="formula"><span class="kw">Max total debt</span>   = gross_annual_income × 6
<span class="kw">Max new mortgage</span> = max_total_debt − existing_debts − credit_card_limits</div>
    <p>→ See <a href="debt-to-income">Debt-to-income ratio</a></p>

    <p class="subsection-title">Ceiling 3 — Serviceability</p>
    <p>The largest loan where monthly repayments at the stress-test rate (your rate + 3%) can be covered by your monthly income surplus after living costs and committed expenses. This is the most complex ceiling and the most common binding constraint for mid-to-high income earners in capital cities.</p>
    <div class="formula"><span class="kw">Monthly surplus</span>  = net_income − HEM − debts − hecs_repayment
<span class="kw">Max loan</span>        = annuity_solve(surplus, stress_rate, 360_months)</div>
    <p>→ See <a href="serviceability">Serviceability</a>, <a href="living-expenses">Living expenses (HEM)</a>, <a href="hecs-help">HECS/HELP</a></p>

    <p class="subsection-title">Which ceiling binds?</p>
    <table class="data-table">
      <thead><tr><th>Situation</th><th>Most likely binding ceiling</th></tr></thead>
      <tbody>
        <tr><td>First home buyer, small deposit</td><td>Ceiling 1 — Deposit</td></tr>
        <tr><td>Mid-income, no prior debt</td><td>Ceiling 3 — Serviceability</td></tr>
        <tr><td>High-income, multiple debts</td><td>Ceiling 2 — DTI</td></tr>
        <tr><td>Investor adding second property</td><td>Ceiling 2 — DTI or C3</td></tr>
      </tbody>
    </table>

    <div class="example-box">
      <div class="example-label">Worked example — single borrower, $120,000 income, $150,000 savings, NSW house</div>
      <div class="example-body">
C1 Deposit ceiling:
  Savings: $150,000 | Stamp duty (est. $800k): ~$31,090
  Available deposit: ~$118,910 at 90% LVR → max price ~$1,189,000
  At 80% LVR (no LMI): max price ~$594,500

C2 DTI ceiling:
  Income: $120,000 × 6 = <span class="hl">$720,000</span> max debt (no existing debts)

C3 Serviceability ceiling:
  Net income: ~$6,650/month | HEM: $2,480 | Surplus: ~$4,170
  Stress rate: 9.49% | Max loan: <span class="hl">≈ $516,000</span>

<span class="hl">Binding ceiling: C3 — Serviceability at ~$516,000</span>
      </div>
    </div>

    <div class="advisory">
      <strong>Lender variation:</strong> Different lenders apply different HEM interpretations, expense floors, and appetite for high LVR. GetReal's ceilings are estimates based on mainstream lender practice.
    </div>""",
    related=[
        ("serviceability", "Serviceability"),
        ("debt-to-income", "Debt-to-income"),
        ("lvr", "LVR limits"),
        ("lmi", "LMI"),
        ("stamp-duty", "Stamp duty"),
        ("hecs-help", "HECS/HELP"),
        ("living-expenses", "Living expenses"),
        ("interest-rate-assumptions", "Interest rates"),
    ]
))

# 2. SERVICEABILITY
PAGES.append(page(
    slug="serviceability",
    title="Serviceability",
    description="How the APRA 3% serviceability buffer works in Australia. GetReal stress-tests mortgage repayments at your interest rate plus 3 percentage points. Formula, worked example, and lender variation explained.",
    version="v1.1 — updated September 2025 (HECS exclusion from DTI)",
    faq_items=[
        ("What is the serviceability buffer in Australia?",
         "The serviceability buffer is a 3 percentage point addition to a loan's interest rate, required by APRA's Prudential Practice Guide APG 223 (August 2022). Lenders must verify that a borrower can service monthly repayments at the actual interest rate plus 3%. For example, if the loan rate is 6.49%, lenders must test at 9.49%."),
        ("How does the serviceability test work?",
         "Lenders calculate your monthly net income, subtract a minimum living cost benchmark (HEM), and subtract all other committed monthly expenses including existing loan repayments, credit card costs, HECS withholding, rent, school fees, and private health. The remaining surplus must cover monthly mortgage repayments at the stress-test rate. The maximum loan is the one where repayments exactly equal the surplus."),
        ("Why does the serviceability buffer exist?",
         "APRA introduced the 3% buffer to ensure borrowers can still afford repayments if interest rates rise significantly. With a variable rate mortgage, your repayments increase when the RBA raises the cash rate. The buffer provides a cushion against rate rises of up to 3 percentage points from the date of application."),
    ],
    body_html="""    <div class="rule-box">
      Lenders must verify that a borrower can meet monthly repayments at the actual interest rate plus a 3 percentage point buffer (APRA APG 223, August 2022). The maximum loan is the one where monthly repayments at the stress-test rate exactly consume the available monthly surplus.
    </div>

    <p>Serviceability is the third and most nuanced of the three borrowing ceilings. It answers: given your income and all your committed expenses, what's the biggest loan you can actually repay — even if rates rise 3%?</p>

    <p class="subsection-title">The stress-test rate</p>
    <p>APRA requires all authorised deposit-taking institutions to assess applications at a minimum buffer of 3.0 percentage points above the loan rate. GetReal applies this to its current interest rate assumption.</p>

    <div class="formula"><span class="kw">Stress-test rate</span>    = interest_rate + <span class="hl">0.03</span>

<span class="kw">Monthly repayment</span>   = loan × r × (1 + r)^360 ÷ ((1 + r)^360 − 1)
<span class="cm">  where r = stress_test_rate ÷ 12
  and 360 = 30-year term in months</span></div>

    <p class="subsection-title">Monthly surplus</p>
    <div class="formula"><span class="kw">Monthly surplus</span> =
    take_home_pay_monthly
  − HEM_floor                   <span class="cm">// minimum living cost benchmark</span>
  − declared_living_expenses     <span class="cm">// if higher than HEM floor</span>
  − existing_loan_repayments
  − existing_mortgage_repayments
  − credit_card_monthly_cost     <span class="cm">// 3% of total limit</span>
  − rent                         <span class="cm">// if currently renting</span>
  − school_fees_monthly
  − private_health_monthly
  − hecs_monthly_repayment       <span class="cm">// estimated from income</span></div>

    <p class="subsection-title">Maximum serviceable loan</p>
    <p>Solved iteratively via binary search: the highest loan amount where monthly repayments at the stress rate do not exceed the monthly surplus.</p>

    <div class="example-box">
      <div class="example-label">Worked example — single borrower, $90,000 income, metro, HECS debt</div>
      <div class="example-body">
Take-home pay:        $5,200/month
HEM floor (metro):    $2,480/month
HECS repayment:       $520/month (est. at $90k income)
Car loan repayment:   $430/month
─────────────────────────────────────────────
Monthly surplus:      <span class="hl">$1,770/month</span>

Stress-test rate:     9.49% (6.49% + 3.0%)
Monthly stress rate:  0.7908%

Max loan:             <span class="hl">≈ $219,000</span>
      </div>
    </div>

    <div class="advisory">
      <strong>Lender variation:</strong> Individual lenders may apply higher buffers, stricter HEM interpretations, or additional expense categories. GetReal's estimate is indicative of mainstream lender practice.
    </div>

    <a class="source-link" href="https://www.apra.gov.au/sites/default/files/2022-08/Final%20-%20APG%20223%20-%20Residential%20Mortgage%20Lending%20-%20August%202022.pdf" target="_blank" rel="noopener">
      ↗ Source: APRA APG 223 — Residential Mortgage Lending (August 2022)
    </a>""",
    related=[
        ("borrowing-capacity", "Borrowing capacity"),
        ("debt-to-income", "Debt-to-income"),
        ("living-expenses", "Living expenses (HEM)"),
        ("hecs-help", "HECS/HELP"),
        ("interest-rate-assumptions", "Interest rates"),
    ]
))

# 3. DEBT-TO-INCOME
PAGES.append(page(
    slug="debt-to-income",
    title="Debt-to-income ratio",
    description="How the debt-to-income (DTI) ratio cap works for Australian mortgages. Total debt cannot exceed 6 times gross annual income. What counts, what's excluded, and how HECS changed in September 2025.",
    version="v1.1 — updated September 2025 (HECS excluded from DTI per APRA)",
    faq_items=[
        ("What is the debt-to-income ratio cap in Australia?",
         "APRA's macro-prudential guidance sets a practical DTI cap of 6 times gross annual income across all debts. Mainstream Australian lenders apply this as their ceiling. Total debt includes existing mortgage balances, credit card limits (treated as fully drawn regardless of actual balance), car loans, personal loans, and BNPL. HECS/HELP is excluded from DTI since 30 September 2025."),
        ("Does HECS count in the debt-to-income ratio?",
         "No. Since 30 September 2025, APRA directed lenders to exclude HECS/HELP balances from debt-to-income ratio calculations. HECS does not count toward the 6x DTI cap. However, HECS still reduces borrowing capacity by reducing net take-home pay through compulsory ATO repayment withholding, which affects the serviceability ceiling."),
        ("Do credit card limits affect borrowing capacity in Australia?",
         "Yes. Lenders count the full credit card limit — not the balance — as debt in the DTI calculation. A $20,000 credit card limit with a $0 balance still adds $20,000 to total debt. Reducing or closing credit cards before applying can meaningfully increase borrowing capacity. Additionally, a notional repayment of approximately 3% of the credit card limit per month is deducted from the monthly surplus in the serviceability calculation."),
    ],
    body_html="""    <div class="rule-box">
      Total debt across all loans cannot exceed 6 times gross annual income. GetReal uses 6× as its DTI ceiling — the dominant cap at mainstream Australian lenders as directed by APRA macro-prudential policy.
    </div>

    <p>APRA's macro-prudential framework directs lenders to limit high-DTI lending. While APRA does not set an absolute hard cap, mainstream lenders have adopted 6× gross income as their practical ceiling. GetReal applies 6× as the upper bound for Ceiling 2.</p>

    <div class="formula"><span class="kw">Max total debt</span>   = gross_annual_income × <span class="hl">6</span>

<span class="kw">Max new mortgage</span> = max_total_debt
    − existing_mortgage_balances
    − credit_card_limits        <span class="cm">// full limit, not balance</span>
    − car_loan_balances
    − personal_loan_balances
    <span class="cm">// HECS/HELP excluded since 30 Sep 2025</span></div>

    <p class="subsection-title">What counts as debt</p>
    <table class="data-table">
      <thead><tr><th>Debt type</th><th>How it's counted</th></tr></thead>
      <tbody>
        <tr><td>Existing mortgages</td><td>Outstanding balance</td></tr>
        <tr><td>Credit cards</td><td>Total approved limit — not the balance</td></tr>
        <tr><td>Car / personal loans</td><td>Outstanding balance</td></tr>
        <tr><td>HECS/HELP</td><td>Excluded since 30 September 2025</td></tr>
        <tr><td>BNPL (Afterpay etc.)</td><td>Outstanding balance if declared</td></tr>
      </tbody>
    </table>

    <div class="note-box">
      Credit card limits are counted in full regardless of actual balance. A $20,000 limit with a $0 balance still adds $20,000 to total debt. Reducing or closing cards before applying can materially increase borrowing capacity.
    </div>

    <div class="example-box">
      <div class="example-label">Worked example — couple, $180,000 combined income</div>
      <div class="example-body">
Gross income (couple):  $180,000/year
DTI cap (6×):           <span class="hl">$1,080,000</span> total debt

Existing car loan:      − $22,000
Credit card limit:      − $15,000
────────────────────────────────────────
Max new mortgage:       <span class="hl">$1,043,000</span>
      </div>
    </div>

    <a class="source-link" href="https://www.apra.gov.au" target="_blank" rel="noopener">
      ↗ Source: APRA macro-prudential policy framework
    </a>""",
    related=[
        ("borrowing-capacity", "Borrowing capacity"),
        ("serviceability", "Serviceability"),
        ("hecs-help", "HECS/HELP"),
    ]
))

# 4. LVR
PAGES.append(page(
    slug="lvr",
    title="LVR limits",
    description="Maximum loan-to-value ratio (LVR) limits for Australian mortgages by property type and buyer type. Owner-occupier houses: 95%. Apartments: 90%. Investors: 90% or 80%. LMI payable above 80%.",
    version="v1.0 — January 2025",
    faq_items=[
        ("What is LVR in Australian mortgages?",
         "LVR stands for loan-to-value ratio — the loan amount as a percentage of the property's purchase price. For example, a $720,000 loan on an $800,000 property has an LVR of 90%. Lenders cap LVR based on property type and whether the borrower will live in the property. LMI (lenders mortgage insurance) is payable when LVR exceeds 80%."),
        ("What is the maximum LVR for a home loan in Australia?",
         "Maximum LVR limits at mainstream lenders are: owner-occupier house or townhouse — 95%; owner-occupier apartment — 90%; investor house or townhouse — 90%; investor apartment — 80%. LMI is required above 80% LVR. The First Home Guarantee scheme allows eligible first home buyers to borrow at 95% LVR without paying LMI."),
        ("What LVR avoids LMI in Australia?",
         "An LVR of 80% or below avoids LMI entirely. This means a 20% deposit on the purchase price, before accounting for stamp duty and fees. For example, to avoid LMI on an $800,000 property, you need a $160,000 deposit plus stamp duty and fees — approximately $191,000 in NSW or $203,000 in VIC."),
    ],
    body_html="""    <div class="rule-box">
      LVR (loan-to-value ratio) is the loan as a percentage of the purchase price. Lenders cap LVR based on property type and whether the buyer will live there. LMI is payable when LVR exceeds 80%.
    </div>

    <p>LVR determines how much of a property's value a lender will fund. The higher the LVR, the more risk the lender takes on — so they charge LMI as protection above 80%, and cap the LVR outright at a maximum. GetReal applies these limits as Ceiling 1 (deposit ceiling).</p>

    <div class="formula"><span class="kw">LVR</span> = loan_amount ÷ purchase_price × 100

<span class="cm">// LMI applies when LVR > 80%
// Ceiling applied: effective LVR (incl. capitalised LMI) ≤ max_LVR</span></div>

    <table class="data-table">
      <thead><tr><th>Property type</th><th>Owner-occupier max LVR</th><th>Investor max LVR</th></tr></thead>
      <tbody>
        <tr><td>House</td><td>95%</td><td>90%</td></tr>
        <tr><td>Townhouse</td><td>95%</td><td>90%</td></tr>
        <tr><td>Apartment</td><td>90%</td><td>80%</td></tr>
      </tbody>
    </table>

    <p>These are practical market maximums at mainstream lenders. Individual lenders may apply stricter limits — particularly for apartments in high-density postcodes, small apartments under 50m², studio apartments, or properties in regional areas with limited comparable sales.</p>

    <p class="subsection-title">LMI capitalisation</p>
    <p>When LMI is added to the loan balance (capitalised), GetReal ensures the resulting LVR including LMI does not exceed the ceiling. A 95% ceiling means the total loan including capitalised LMI is at most 95% of the purchase price.</p>

    <div class="example-box">
      <div class="example-label">Example — 90% LVR with LMI capitalised</div>
      <div class="example-body">
Purchase price:        $700,000
Base deposit:          $70,000 (10%)
Base loan:             $630,000 (90% LVR)
LMI rate (90.01–95%):  2.77%
LMI premium:           $630,000 × 2.77% = $17,451
Total loan:            $647,451
Effective LVR:         $647,451 ÷ $700,000 = <span class="hl">92.5%</span>

<span class="cm">// LVR check: 92.5% ≤ 95% ceiling — viable for OO house ✓</span>
      </div>
    </div>

    <div class="advisory">
      <strong>First Home Guarantee:</strong> Eligible first home buyers can borrow up to 95% LVR without paying LMI, with the federal government guaranteeing the difference. GetReal does not currently model this scheme — if you're eligible, your ceiling may be higher.
    </div>

    <a class="source-link" href="https://www.housingaustralia.gov.au/support-buy-home/first-home-guarantee" target="_blank" rel="noopener">
      ↗ First Home Guarantee — Housing Australia
    </a>""",
    related=[
        ("borrowing-capacity", "Borrowing capacity"),
        ("lmi", "LMI calculation"),
        ("stamp-duty", "Stamp duty"),
    ]
))

# 5. LMI
PAGES.append(page(
    slug="lmi",
    title="Lenders mortgage insurance (LMI)",
    description="How LMI (lenders mortgage insurance) is calculated in Australia. Payable when LVR exceeds 80%. Rates by LVR band and loan size. LMI stamp duty by state. GetReal uses indicative Helia/QBE rates.",
    version="v1.0 — rates updated May 2026",
    faq_items=[
        ("What is LMI in Australia?",
         "LMI stands for lenders mortgage insurance. It is an insurance premium paid by the borrower that protects the lender (not the borrower) if the borrower defaults. LMI is payable when the loan-to-value ratio (LVR) exceeds 80%. The premium is a percentage of the loan amount that varies by LVR band and loan size, and is typically capitalised into the loan rather than paid upfront."),
        ("How much does LMI cost in Australia?",
         "LMI varies by LVR and loan size. As indicative figures: at 80.01–85% LVR, around 0.70–0.76% of the loan amount. At 85.01–90% LVR, around 1.43%. At 90.01–95% LVR, around 2.77–3.09%. On an $800,000 loan at 90% LVR, LMI might be approximately $11,440. Most borrowers capitalise LMI into the loan rather than paying it upfront."),
        ("Is LMI tax deductible in Australia?",
         "For investment properties, LMI is generally deductible over the life of the loan (not in the year paid). For owner-occupier properties, LMI is not tax deductible. GetReal does not model tax deductibility — consult a tax adviser."),
    ],
    body_html="""    <div class="rule-box">
      LMI is an insurance premium paid by the borrower that protects the lender if the borrower defaults. It is payable when LVR exceeds 80%. The premium varies by LVR band and loan size, and is typically capitalised into the loan.
    </div>

    <p>LMI is not optional at high LVR — it's a lender requirement. It protects the lender, not the borrower. The two main LMI providers in Australia are Helia (formerly Genworth) and QBE. GetReal uses indicative rates sourced from Home Loan Experts (May 2026).</p>

    <p class="subsection-title">LMI premium rates</p>
    <table class="data-table">
      <thead>
        <tr>
          <th>LVR band</th><th>Loan &lt;$300k</th><th>$300k–$500k</th><th>$500k–$750k</th><th>$750k–$1M</th><th>Over $1M</th>
        </tr>
      </thead>
      <tbody>
        <tr><td>80.01–85%</td><td>0.70%</td><td>0.70%</td><td>0.76%</td><td>0.76%</td><td>0.76%</td></tr>
        <tr><td>85.01–90%</td><td>1.43%</td><td>1.43%</td><td>1.43%</td><td>1.43%</td><td>1.43%</td></tr>
        <tr><td>90.01–95%</td><td>2.77%</td><td>2.77%</td><td>3.09%</td><td>3.09%</td><td>3.09%</td></tr>
      </tbody>
    </table>
    <p style="font-family:var(--font-mono);font-size:0.68rem;color:var(--dim);">Indicative only. Actual rates depend on lender and insurer.</p>

    <div class="formula"><span class="kw">LMI premium</span>    = loan_amount × lmi_rate_pct
<span class="kw">LMI stamp duty</span> = lmi_premium × state_lmi_sd_rate
<span class="kw">Total LMI cost</span> = lmi_premium + lmi_stamp_duty

<span class="cm">// When capitalised (most common):</span>
<span class="kw">Total loan</span>     = base_loan + lmi_premium
<span class="cm">// LMI stamp duty is paid upfront — not capitalised</span></div>

    <p class="subsection-title">LMI stamp duty by state</p>
    <p>Most states charge stamp duty on the LMI premium itself. This is a small additional upfront cost, not capitalised.</p>

    <div class="example-box">
      <div class="example-label">Worked example — $700,000 purchase, 10% deposit, NSW</div>
      <div class="example-body">
Purchase price:    $700,000
Deposit (10%):     $70,000
Base loan:         $630,000
LVR:               90.0%

LMI rate (85.01–90%, loan $500k–$750k): 1.43%
LMI premium:       $630,000 × 1.43% = <span class="hl">$9,009</span>
LMI stamp duty (NSW, 9%): $9,009 × 9% = $811

Total loan (capitalised LMI): <span class="hl">$639,009</span>
Effective LVR:     91.3%
      </div>
    </div>

    <div class="note-box">
      LMI can be avoided by: (1) reaching 20% deposit, (2) using a guarantor, or (3) qualifying for the First Home Guarantee (eligible FHBs only). GetReal does not currently model guarantor loans.
    </div>

    <a class="source-link" href="https://www.homeloanexperts.com.au/lenders-mortgage-insurance/lmi-rates/" target="_blank" rel="noopener">
      ↗ Source: Home Loan Experts — indicative LMI rates (May 2026)
    </a>""",
    related=[
        ("lvr", "LVR limits"),
        ("borrowing-capacity", "Borrowing capacity"),
        ("stamp-duty", "Stamp duty"),
    ]
))

# 6. STAMP DUTY
PAGES.append(page(
    slug="stamp-duty",
    title="Stamp duty",
    description="How stamp duty (transfer duty) is calculated across all 8 Australian states and territories. Progressive bracket formula, NT quadratic formula, VIC PPR rates, and first home buyer concessions for every state.",
    version="v1.0 — rates verified August 2026",
    faq_items=[
        ("How is stamp duty calculated in Australia?",
         "Stamp duty is calculated using a progressive bracket system — similar to income tax. You pay a base amount for your price bracket, plus a marginal rate on the portion above the bracket minimum. For example, in NSW at $800,000 the duty is $17,990 (base) plus 4.5% of the amount over $500,000. The Northern Territory uses a quadratic formula instead of brackets for purchases up to $525,000."),
        ("Which Australian state has the lowest stamp duty?",
         "Queensland and ACT generally have lower stamp duty than NSW and VIC at most price points. At $800,000: QLD $24,525, ACT $25,200, NSW $31,090, WA $28,453, TAS $30,247, SA $38,730, VIC $43,070. Rates change frequently — use GetReal's stamp duty calculator for current figures."),
        ("Do first home buyers get stamp duty concessions in Australia?",
         "Yes. Every state and territory offers some form of first home buyer stamp duty relief. NSW exempts FHBs below $800,000 and tapers to $1,000,000. VIC exempts below $600,000, tapers to $750,000. QLD exempts below $700,000, tapers to $800,000. WA exempts below $450,000, tapers to $600,000. ACT has an income-tested full exemption. SA offers no duty concession (grant only). TAS gives a 50% discount. NT gives an $18,601 rebate."),
    ],
    body_html="""    <div class="rule-box">
      Stamp duty (transfer duty) is a state and territory tax on property purchases. Every state uses a progressive bracket system. GetReal calculates it from bracket tables sourced directly from each state revenue office, stored in the <code>stamp_duty_brackets</code> Supabase table.
    </div>

    <p>Stamp duty is one of the largest upfront costs in a property purchase. It comes directly out of your savings before deposit — which is why it matters so much to the deposit ceiling. A $31,090 stamp duty bill on an $800,000 NSW purchase is $31,090 that can't become deposit.</p>

    <p class="subsection-title">General formula (all states except NT)</p>
    <div class="formula"><span class="kw">Duty</span> = base_amount_for_bracket
       + (purchase_price − bracket_min) × marginal_rate

<span class="cm">// VIC owner-occupier ≤$550k: PPR rate schedule applies (lower)
// VIC $960k–$2M: is_full_price=true (rate applies to full price, not margin)</span></div>

    <p class="subsection-title">NT — quadratic formula</p>
    <div class="formula"><span class="cm">// Where V = purchase_price ÷ 1000</span>
<span class="kw">Duty</span> = (0.06571441 × V² + 15 × V) ÷ 1000   <span class="cm">// up to $525,000</span>
<span class="kw">Duty</span> = purchase_price × <span class="hl">0.0545</span>             <span class="cm">// above $525,000</span></div>

    <p class="subsection-title">Stamp duty by state — standard, non-FHB, established property</p>
    <table class="data-table">
      <thead><tr><th>State</th><th>$500k</th><th>$800k</th><th>$1.0M</th><th>$1.5M</th></tr></thead>
      <tbody>
        <tr><td>NSW</td><td>$17,990</td><td>$31,090</td><td>$40,090</td><td>$68,215</td></tr>
        <tr><td>VIC (standard)</td><td>$21,970</td><td>$43,070</td><td>$55,000</td><td>$82,500</td></tr>
        <tr><td>VIC (owner-occ ≤$550k)</td><td>$5,765</td><td>$43,070</td><td>$55,000</td><td>$82,500</td></tr>
        <tr><td>QLD</td><td>$8,750</td><td>$24,525</td><td>$34,525</td><td>$59,525</td></tr>
        <tr><td>WA</td><td>$17,765</td><td>$28,453</td><td>$37,453</td><td>$63,453</td></tr>
        <tr><td>SA</td><td>$21,330</td><td>$38,730</td><td>$50,730</td><td>$81,730</td></tr>
        <tr><td>TAS</td><td>$18,247</td><td>$30,247</td><td>$38,247</td><td>$63,247</td></tr>
        <tr><td>ACT</td><td>$12,800</td><td>$25,200</td><td>$34,200</td><td>$60,200</td></tr>
        <tr><td>NT</td><td>$23,929</td><td>$38,422</td><td>$49,007</td><td>$82,543</td></tr>
      </tbody>
    </table>
    <p style="font-family:var(--font-mono);font-size:0.68rem;color:var(--dim);">Approximate figures. Use the <a href="../stamp-duty.html">stamp duty calculator</a> for precise results.</p>

    <p class="subsection-title">First home buyer concessions</p>
    <table class="data-table">
      <thead><tr><th>State</th><th>FHB exemption threshold</th><th>Taper / detail</th></tr></thead>
      <tbody>
        <tr><td>NSW</td><td>$800,000</td><td>Tapers to $1,000,000</td></tr>
        <tr><td>VIC</td><td>$600,000</td><td>Tapers to $750,000</td></tr>
        <tr><td>QLD</td><td>$700,000</td><td>Tapers to $800,000</td></tr>
        <tr><td>WA</td><td>$450,000</td><td>Tapers to $600,000</td></tr>
        <tr><td>SA</td><td>No duty concession</td><td>Grant only ($15,000)</td></tr>
        <tr><td>TAS</td><td>50% discount on established homes</td><td>No upper limit</td></tr>
        <tr><td>ACT</td><td>Full exemption</td><td>Income-tested (Home Buyer Concession Scheme)</td></tr>
        <tr><td>NT</td><td>$18,601 rebate</td><td>Phaseout starts $650k, ends $723k</td></tr>
      </tbody>
    </table>

    <a class="source-link" href="../stamp-duty.html">→ Use the stamp duty calculator</a>""",
    related=[
        ("borrowing-capacity", "Borrowing capacity"),
        ("lvr", "LVR limits"),
        ("lmi", "LMI"),
    ]
))

# 7. HECS/HELP
PAGES.append(page(
    slug="hecs-help",
    title="HECS/HELP and borrowing capacity",
    description="How HECS/HELP debt affects mortgage borrowing capacity in Australia. Since September 2025, HECS is excluded from the DTI ratio. But HECS still reduces serviceability by cutting net take-home pay.",
    version="v1.1 — updated September 2025 (APRA exclusion from DTI)",
    faq_items=[
        ("Does HECS debt affect borrowing capacity in Australia?",
         "Yes, but differently since 30 September 2025. HECS/HELP balances are now excluded from the debt-to-income ratio calculation — so HECS doesn't count toward the 6x DTI cap. However, HECS still reduces borrowing capacity through the serviceability ceiling: the ATO compulsorily withholds HECS repayments from salary above income thresholds, reducing the net take-home pay available to service a mortgage."),
        ("How much does HECS reduce borrowing capacity?",
         "The impact depends on income. At $80,000 gross income, HECS repayments are approximately 4% of income — about $3,200/year or $267/month withheld by the ATO. At $120,000, repayments are approximately 6.5% — about $7,800/year or $650/month. Dividing the monthly HECS repayment by the monthly serviceability rate gives the approximate reduction in borrowing capacity. At 9.49% stress rate and $650/month HECS, borrowing capacity is reduced by approximately $80,000–$90,000."),
        ("Should I pay off my HECS before applying for a mortgage?",
         "Usually not — HECS is excluded from the DTI cap since September 2025, and the serviceability impact is modest relative to the cash required to clear the debt. Paying $40,000 to clear a HECS debt might save $150–200/month in repayment withholding, which increases borrowing capacity by only around $18,000–$25,000. That $40,000 would add far more to your deposit ceiling if kept as savings."),
    ],
    body_html="""    <div class="rule-box">
      Since 30 September 2025, HECS/HELP balances are excluded from lenders' debt-to-income ratio calculations per APRA direction. HECS does not count toward the 6× DTI cap. However, HECS still reduces borrowing capacity by reducing net take-home pay through compulsory ATO repayment withholding.
    </div>

    <p>The September 2025 APRA change was significant — for borrowers with large HECS balances, it removed an artificial ceiling that bore no relationship to their actual repayment burden. But HECS still matters for serviceability (Ceiling 3).</p>

    <p class="subsection-title">How HECS affects serviceability</p>
    <p>The ATO withholds HECS repayments from salary above income thresholds at tax time. GetReal estimates monthly HECS withholding from gross income and deducts it from take-home pay in the serviceability calculation. If you enter actual take-home pay already net of HECS, GetReal does not double-count.</p>

    <p class="subsection-title">HECS compulsory repayment rates (2025–26)</p>
    <table class="data-table">
      <thead><tr><th>Repayment income threshold</th><th>Rate</th></tr></thead>
      <tbody>
        <tr><td>Below $54,435</td><td>Nil</td></tr>
        <tr><td>$54,435 – $62,738</td><td>1.0%</td></tr>
        <tr><td>$62,739 – $70,619</td><td>2.0%–2.5%</td></tr>
        <tr><td>$70,620 – $84,107</td><td>3.0%–4.0%</td></tr>
        <tr><td>$84,108 – $100,174</td><td>4.5%–5.5%</td></tr>
        <tr><td>$100,175 – $119,309</td><td>6.0%–7.0%</td></tr>
        <tr><td>$119,310 and above</td><td>7.5%–8.0%</td></tr>
      </tbody>
    </table>

    <div class="example-box">
      <div class="example-label">Impact of HECS on borrowing capacity — $100,000 income</div>
      <div class="example-body">
Gross income:           $100,000
HECS repayment rate:    5.5% (at $100k threshold)
Annual HECS withholding: $5,500
Monthly HECS:           $458/month

Without HECS (monthly surplus): $3,200
With HECS (monthly surplus):    <span class="hl">$2,742</span>

Reduction in max loan at 9.49% stress rate: <span class="hl">≈ $56,000</span>
      </div>
    </div>

    <div class="advisory">
      <strong>Should you pay off HECS?</strong> Rarely. Paying $40,000 to clear HECS might save ~$458/month — worth ~$56,000 in borrowing capacity. But that same $40,000 kept as deposit adds far more to your Ceiling 1. The serviceability saving rarely exceeds the deposit impact.
    </div>

    <a class="source-link" href="https://www.ato.gov.au/individuals-and-families/study-and-training-support-loans/ato-study-and-training-support-loans/help-debt-repayment" target="_blank" rel="noopener">
      ↗ Source: ATO — HELP debt repayment thresholds (2025–26)
    </a>""",
    related=[
        ("borrowing-capacity", "Borrowing capacity"),
        ("serviceability", "Serviceability"),
        ("debt-to-income", "Debt-to-income"),
    ]
))

# 8. LIVING EXPENSES / HEM
PAGES.append(page(
    slug="living-expenses",
    title="Living expenses — HEM",
    description="How the Household Expenditure Measure (HEM) is used in Australian mortgage serviceability assessments. HEM figures by household type, dependants, and metro vs regional. Why lenders apply HEM even if you spend less.",
    version="v1.0 — March 2026 (HEM figures current)",
    faq_items=[
        ("What is HEM in mortgage applications?",
         "HEM stands for Household Expenditure Measure, published quarterly by the Melbourne Institute. It is the minimum living cost benchmark that APRA-regulated lenders must apply when assessing serviceability — even if a borrower declares lower expenses. HEM covers basic living costs: food, utilities, transport, clothing, and everyday spending. It excludes rent, school fees, and private health insurance, which are added separately."),
        ("What is the HEM benchmark in Australia?",
         "HEM varies by household type, number of dependants, and location. Indicative metro figures (March 2026): single with no dependants $2,480/month, couple with no dependants $3,680/month, couple with 2 dependants $4,680/month. Regional figures are approximately 10–15% lower. Lenders are not required to publish their exact HEM figures — the Melbourne Institute licenses them."),
        ("Can I use lower expenses than HEM in my mortgage application?",
         "No. Lenders are required by APRA to use whichever is higher: HEM or your declared expenses. If your declared expenses are lower than HEM, the lender uses HEM anyway. This is a regulatory requirement introduced to prevent borrowers understating living costs to qualify for larger loans. If your actual expenses are higher than HEM, your stated expenses are used."),
    ],
    body_html="""    <div class="rule-box">
      HEM (Household Expenditure Measure) is a minimum living cost benchmark published by the Melbourne Institute. APRA requires all lenders to apply at least HEM when assessing serviceability — even if the borrower declares lower expenses. GetReal uses HEM as the floor.
    </div>

    <p>HEM exists because borrowers historically understated living costs on mortgage applications. APRA requires lenders to apply a regulatory minimum regardless of what's declared. The higher of HEM or declared expenses is used in GetReal's serviceability calculation.</p>

    <p>HEM covers basic living costs: food, utilities, transport, clothing, and everyday spending. It does not include rent, school fees, or private health — these are added separately.</p>

    <table class="data-table">
      <thead>
        <tr><th>Household type</th><th>Dependants</th><th>Metro / month</th><th>Regional / month</th></tr>
      </thead>
      <tbody>
        <tr><td>Single</td><td>0</td><td>$2,480</td><td>$2,150</td></tr>
        <tr><td>Single</td><td>1</td><td>$3,050</td><td>$2,700</td></tr>
        <tr><td>Single</td><td>2</td><td>$3,480</td><td>$3,100</td></tr>
        <tr><td>Single</td><td>3+</td><td>$3,950</td><td>$3,520</td></tr>
        <tr><td>Couple</td><td>0</td><td>$3,680</td><td>$3,200</td></tr>
        <tr><td>Couple</td><td>1</td><td>$4,200</td><td>$3,700</td></tr>
        <tr><td>Couple</td><td>2</td><td>$4,680</td><td>$4,150</td></tr>
        <tr><td>Couple</td><td>3+</td><td>$5,200</td><td>$4,650</td></tr>
      </tbody>
    </table>
    <p style="font-family:var(--font-mono);font-size:0.68rem;color:var(--dim);">Indicative figures based on JMD Mortgages HEM estimates (March 2026). Actual lender HEM benchmarks vary and are not publicly published.</p>

    <p class="subsection-title">Metro vs regional</p>
    <p>GetReal determines location type from the buyer's postcode, using ABS ASGS Edition 3 classifications. Metropolitan = all eight GCCSA capital cities (Sydney, Melbourne, Brisbane, Perth, Adelaide, Canberra, Darwin, Hobart). Regional = everything else.</p>

    <div class="note-box">
      HEM figures are not publicly published by the Melbourne Institute — lenders license them. GetReal uses indicative estimates from JMD Mortgages (March 2026). If a lender applies a stricter HEM, your actual serviceability ceiling will be lower than GetReal's estimate.
    </div>

    <a class="source-link" href="https://melbourneinstitute.unimelb.edu.au" target="_blank" rel="noopener">
      ↗ Source: Melbourne Institute — Household Expenditure Measure
    </a>""",
    related=[
        ("serviceability", "Serviceability"),
        ("borrowing-capacity", "Borrowing capacity"),
        ("interest-rate-assumptions", "Interest rates"),
    ]
))

# 9. INTEREST RATE ASSUMPTIONS
PAGES.append(page(
    slug="interest-rate-assumptions",
    title="Interest rate assumptions",
    description="What interest rate GetReal uses for borrowing capacity calculations. A representative variable rate based on the RBA cash rate plus lender margin, stress-tested at +3% per APRA requirements.",
    version="v1.0 — updated periodically from RBA (last reviewed August 2026)",
    faq_items=[
        ("What interest rate does GetReal use?",
         "GetReal uses a representative variable rate based on the RBA cash rate plus an average lender margin. As of August 2026, this is 6.49% per annum. The stress-test rate used in serviceability calculations is this rate plus the 3% APRA buffer — currently 9.49%. The rate is updated periodically, not in real-time."),
        ("What is the APRA serviceability buffer rate?",
         "APRA's Prudential Practice Guide APG 223 (August 2022) requires lenders to add a minimum 3 percentage point buffer to the interest rate when assessing serviceability. If the loan rate is 6.49%, the stress-test rate is 9.49%. This buffer has been set at 3% since October 2021."),
        ("Can I override the interest rate in GetReal?",
         "Yes. The buying ceiling calculator allows you to enter a custom interest rate — for example if you have a pre-approval from a lender at a specific rate. When overridden, the stress-test rate is still your entered rate plus 3% as required by APRA."),
    ],
    body_html="""    <div class="rule-box">
      GetReal uses a single representative variable rate based on the RBA cash rate plus average lender margin. This is not a real-time feed — it is updated periodically. The stress-test rate is this rate plus the 3% APRA buffer.
    </div>

    <p>All three serviceability ceilings are sensitive to the interest rate assumption. GetReal uses a market-average variable rate rather than any lender's advertised rate — the tool is designed to give a realistic estimate across lenders, not to reflect any specific product.</p>

    <table class="data-table">
      <thead><tr><th>Rate component</th><th>Current assumption</th></tr></thead>
      <tbody>
        <tr><td>Representative variable rate</td><td>6.49% p.a.</td></tr>
        <tr><td>APRA serviceability buffer</td><td>+ 3.00%</td></tr>
        <tr><td>Stress-test rate</td><td>9.49% p.a.</td></tr>
        <tr><td>Loan term assumed</td><td>30 years, principal and interest</td></tr>
      </tbody>
    </table>

    <p class="subsection-title">Rate override</p>
    <p>The buying ceiling calculator allows a custom rate override — for example, a pre-approval offer from a specific lender. When overridden, the stress-test rate is still entered_rate + 3%.</p>

    <p class="subsection-title">How we track the RBA rate</p>
    <p>GetReal's GitHub Actions pipeline fetches the RBA cash rate automatically from the RBA's F1 statistical table (series FIRMMCRTD). The representative mortgage rate is derived by adding an average lender margin to the cash rate and manually reviewed before each pipeline run.</p>

    <div class="note-box">
      Rate last reviewed: August 2026. RBA cash rate: 3.85% (as of August 2026). Representative variable rate: 6.49% (cash rate + ~2.64% average margin).
    </div>

    <div class="example-box">
      <div class="example-label">Effect of rate on borrowing capacity — $3,000/month surplus</div>
      <div class="example-body">
Stress rate 8.49% (rate 5.49%):   max loan ≈ <span class="hl">$404,000</span>
Stress rate 9.49% (rate 6.49%):   max loan ≈ <span class="hl">$370,000</span>
Stress rate 10.49% (rate 7.49%):  max loan ≈ <span class="hl">$340,000</span>

A 1% rise in the stress rate ≈ $30–35k reduction in borrowing capacity
per $1,000/month of available surplus.
      </div>
    </div>

    <a class="source-link" href="https://www.rba.gov.au/statistics/cash-rate/" target="_blank" rel="noopener">
      ↗ Source: RBA — Cash Rate Target
    </a>""",
    related=[
        ("serviceability", "Serviceability"),
        ("borrowing-capacity", "Borrowing capacity"),
    ]
))

# 10. PROPERTY REALISM SCORE
PAGES.append(page(
    slug="property-realism-score",
    title="Property realism score",
    description="How GetReal calculates the property realism score. A 0–100% estimate of what share of properties in a suburb sold within your criteria last year. Based on 146,000+ NSW Valuer General sale records.",
    version="v1.0 — January 2025",
    faq_items=[
        ("How is the GetReal property realism score calculated?",
         "The realism score estimates what percentage of properties in a suburb would match all of a buyer's criteria (suburb, property type, budget, bedrooms, bathrooms) based on actual sales from the last year. For NSW, the budget factor is calculated directly from 146,000+ individual Valuer General sale records — the exact count of sales at or below your budget. Each criterion is measured as a fraction of sales meeting it, then multiplied together. The result is scaled so that 25 or more matching sales per year = 100%."),
        ("What does a 50% realism score mean?",
         "A 50% realism score means that on current market data, roughly half of the sales that occurred in that suburb last year matched all of your criteria — suburb, property type, budget, bedrooms, and bathrooms. It does not mean 50% of properties are currently available. It's a signal of how frequently properties matching your full combination appear in the market."),
        ("Why does the realism score cap at 100%?",
         "GetReal defines 100% as 25 or more matching sales per year — a frequency roughly equivalent to fortnightly availability. Above this threshold, supply is considered plentiful and the score is capped. The cap prevents very active markets from showing artificially high numbers and keeps the score interpretable: 100% means regular opportunities, not unlimited supply."),
    ],
    body_html="""    <div class="rule-box">
      The realism score estimates what percentage of properties in a suburb would match all of a buyer's criteria based on actual sales from the last year. A score of 100% means 25 or more matching sales per year — roughly fortnightly availability.
    </div>

    <p>The score is not a count of available listings. It is a signal of how often properties matching your full combination of criteria appear in this market. A tight score on any single factor — especially budget — dominates the result.</p>

    <p class="subsection-title">Score calculation</p>
    <div class="formula"><span class="kw">raw_score</span>          = budget_pct × bedrooms_pct × bathrooms_pct

<span class="cm">// Each factor: fraction of sales meeting that criterion.
// Factors assumed independent (not correlated).</span>

<span class="kw">estimated_matches</span>  = raw_score × annual_sales_count

<span class="kw">display_score</span>      = min(estimated_matches ÷ <span class="hl">25</span>, 1.0) × 100
<span class="cm">// 25 matching sales/year = 100%</span></div>

    <p class="subsection-title">Budget factor — NSW</p>
    <p>For NSW, GetReal counts exactly how many of the last 13 months' sold properties fall at or below the budget from the Valuer General database. This is a direct calculation from individual records — no estimation.</p>

    <p class="subsection-title">Budget factor — VIC</p>
    <p>VIC uses estimated curves derived from NSW data. See <a href="vic-methodology">VIC suburb methodology</a>.</p>

    <p class="subsection-title">Bedroom and bathroom factors</p>
    <p>Where agency-sourced enrichment data is available (Ray White, McGrath, LJ Hooker), bedroom and bathroom distributions are calculated from actual sold records. For un-enriched properties, national distribution estimates are used as a fallback. Current NSW enrichment coverage: approximately 12% of records.</p>

    <p class="subsection-title">Score grade labels</p>
    <table class="data-table">
      <thead><tr><th>Grade</th><th>Score</th><th>What it means</th></tr></thead>
      <tbody>
        <tr><td>Highly Realistic</td><td>75–100%</td><td>Strong supply. Regular opportunities.</td></tr>
        <tr><td>Realistic</td><td>55–74%</td><td>Good supply. Patience needed.</td></tr>
        <tr><td>Competitive</td><td>35–54%</td><td>Limited supply. Act quickly or compromise.</td></tr>
        <tr><td>Tight</td><td>15–34%</td><td>Very limited. Consider relaxing one criterion.</td></tr>
        <tr><td>Very Difficult</td><td>5–14%</td><td>Rare supply. Most criteria are binding.</td></tr>
        <tr><td>Unrealistic</td><td>0–4%</td><td>This combination almost never appears.</td></tr>
      </tbody>
    </table>

    <a class="source-link" href="https://www.valuergeneral.nsw.gov.au/land_values/bulk_land_value_information" target="_blank" rel="noopener">
      ↗ Source: NSW Valuer General — Bulk Property Sales Information
    </a>""",
    related=[
        ("vic-methodology", "VIC suburb methodology"),
        ("data-sources", "Data sources"),
    ]
))

# 11. VIC METHODOLOGY
PAGES.append(page(
    slug="vic-methodology",
    title="VIC suburb methodology",
    description="How GetReal estimates property realism scores for Victorian suburbs. VIC does not publish individual sale records. GetReal uses NSW-derived price distribution curves matched by property type, price bracket, and market depth.",
    version="v1.0 — January 2025 (VIC data: Q4 2025 VGV report)",
    faq_items=[
        ("Why are VIC property scores estimated and not exact?",
         "Victoria does not publish individual property sale records. The Victorian Valuer General publishes quarterly suburb-level median prices and annual sales volumes, but not transaction-level data. Without individual records, it is impossible to directly measure what fraction of sales fall at or below a given budget. GetReal estimates this using price distribution curves derived from NSW's 146,000+ individual sale records, matched to VIC suburbs by property type, price bracket, and market depth."),
        ("How accurate are GetReal's VIC property realism scores?",
         "VIC scores are directionally useful but not precise. The estimation approach assumes VIC price distributions behave similarly to NSW markets with equivalent medians and volume. This is a reasonable assumption in most cases but will be less accurate in suburbs with unusual housing stock mix, strong recent price movements, or very thin markets. GetReal is transparent about this on every VIC result page."),
    ],
    body_html="""    <div class="rule-box">
      Victoria does not publish individual sale records. GetReal estimates VIC budget scores using NSW price distribution curves matched by property type, price bracket, and market depth. This is an estimation approach — not a direct count. GetReal is transparent about this on every VIC result.
    </div>

    <p>NSW has over 146,000 individual sale records, which allows direct measurement of the price distribution around the median — how many sales fall at 80%, 90%, 100%, 110% of median, and so on. This distribution shape is consistent across NSW with two meaningful variables: price bracket and market depth.</p>

    <p class="subsection-title">Price brackets</p>
    <table class="data-table">
      <thead><tr><th>Bracket</th><th>Median price range</th></tr></thead>
      <tbody>
        <tr><td>1</td><td>Under $500,000</td></tr>
        <tr><td>2</td><td>$500,000 – $800,000</td></tr>
        <tr><td>3</td><td>$800,000 – $1,200,000</td></tr>
        <tr><td>4</td><td>$1,200,000 – $1,800,000</td></tr>
        <tr><td>5</td><td>Over $1,800,000</td></tr>
      </tbody>
    </table>

    <p class="subsection-title">Market depth tiers</p>
    <p>Thin markets (under 30 sales/year) have tighter price distributions — buyers compete hard for limited stock. Active markets (30+ sales/year) have wider dispersion. Three depth tiers were tested; high-volume and medium-volume suburbs were statistically indistinguishable. GetReal uses two tiers: active (≥30 sales/year) and thin (&lt;30 sales/year).</p>

    <p class="subsection-title">Annual sales count — important note</p>
    <p>The annual sales count for VIC suburbs is the rolling 12-month figure from the Q4 2025 VGV report — meaning calendar year 2025, not the trailing 12 months from today. GetReal displays "in 2025 (VGV annual data)" not "in the last 12 months" for this reason.</p>

    <p class="subsection-title">Curve lookup</p>
    <div class="formula"><span class="cm">// VIC suburb: median $750k, 45 sales/year, property type: house</span>

<span class="kw">bracket</span>    = 2           <span class="cm">// $500k–$800k</span>
<span class="kw">depth_tier</span> = active      <span class="cm">// 45 ≥ 30</span>

<span class="kw">ratio</span>      = budget ÷ suburb_median
<span class="cm">// e.g. $650k ÷ $750k = 0.867</span>

<span class="kw">budget_pct</span> = interpolate(price_curves, type, bracket, depth_tier, ratio)
<span class="cm">// Curves store percentiles at 11 ratio thresholds:
// 0.5×, 0.6×, 0.7×, 0.8×, 0.9×, 1.0×, 1.1×, 1.2×, 1.3×, 1.4×, 1.5× median</span></div>

    <div class="advisory">
      <strong>Honest limitation:</strong> VIC scores are estimates calibrated to NSW market behaviour. Actual VIC distributions may differ — particularly in suburbs with unusual housing stock, strong recent price movements, or very thin markets. Treat VIC scores as directionally useful, not precise.
    </div>

    <a class="source-link" href="https://www.land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics" target="_blank" rel="noopener">
      ↗ Source: Victorian Valuer General — Quarterly Property Sales Statistics
    </a>""",
    related=[
        ("property-realism-score", "Property realism score"),
        ("data-sources", "Data sources"),
    ]
))

# 12. DATA SOURCES
PAGES.append(page(
    slug="data-sources",
    title="Data sources",
    description="Every data source used by GetReal. NSW Valuer General individual sale records (146,000+), Victorian VGV quarterly reports, stamp duty brackets from state revenue offices, RBA cash rate, ATO HECS schedules, HEM benchmarks.",
    version="v1.0 — August 2026",
    body_html="""    <div class="rule-box">
      GetReal is built on open government data. Every data source is documented here — what it is, what it's used for, how often it's updated, and under what licence.
    </div>

    <table class="data-table">
      <thead>
        <tr><th>Source</th><th>Used for</th><th>Update frequency</th><th>Licence</th></tr>
      </thead>
      <tbody>
        <tr>
          <td>NSW Valuer General — Bulk PSI</td>
          <td>NSW individual sale records (146,000+)</td>
          <td>Daily on VG site; weekly pipeline</td>
          <td>Open — CC BY</td>
        </tr>
        <tr>
          <td>Victorian Valuer General — Quarterly report</td>
          <td>VIC suburb medians + annual sales volumes</td>
          <td>Quarterly</td>
          <td>Open</td>
        </tr>
        <tr>
          <td>Ray White sold listings (API)</td>
          <td>NSW bedroom/bathroom enrichment</td>
          <td>Weekly pipeline</td>
          <td>Best-effort scraping</td>
        </tr>
        <tr>
          <td>McGrath sold listings (scrape)</td>
          <td>NSW bedroom/bathroom enrichment</td>
          <td>Weekly pipeline</td>
          <td>Best-effort scraping</td>
        </tr>
        <tr>
          <td>LJ Hooker sold listings (API)</td>
          <td>NSW bedroom/bathroom enrichment</td>
          <td>Weekly pipeline</td>
          <td>Best-effort scraping</td>
        </tr>
        <tr>
          <td>State revenue offices (all 8)</td>
          <td>Stamp duty brackets and FHB concessions</td>
          <td>On legislative change</td>
          <td>Public</td>
        </tr>
        <tr>
          <td>Melbourne Institute — HEM</td>
          <td>Living expense benchmarks (serviceability)</td>
          <td>Quarterly (licensed)</td>
          <td>Licensed — indicative figures used</td>
        </tr>
        <tr>
          <td>Home Loan Experts — LMI rates</td>
          <td>LMI premium estimation</td>
          <td>As published</td>
          <td>Indicative</td>
        </tr>
        <tr>
          <td>RBA — Cash Rate (F1 table, FIRMMCRTD)</td>
          <td>Interest rate assumption base</td>
          <td>Fetched automatically on each pipeline run</td>
          <td>Public</td>
        </tr>
        <tr>
          <td>ABS ASGS Edition 3</td>
          <td>Postcode metro/regional classification</td>
          <td>Static (2021 census)</td>
          <td>CC BY 4.0</td>
        </tr>
        <tr>
          <td>ATO — HECS repayment schedule</td>
          <td>Estimated HECS withholding from income</td>
          <td>Annual (July update)</td>
          <td>Public</td>
        </tr>
        <tr>
          <td>ATO — Income tax brackets + LITO</td>
          <td>Net income estimation from gross</td>
          <td>Annual (July update)</td>
          <td>Public</td>
        </tr>
      </tbody>
    </table>

    <p class="subsection-title">NSW enrichment coverage</p>
    <p>GetReal enriches NSW sale records with bedroom and bathroom data from agency-sourced sold listings. As of August 2026, approximately 12.1% of NSW records are enriched (17,709 of 146,330). Agencies: Ray White (10,955 records), McGrath (5,386), LJ Hooker (1,368). Un-enriched records use national distribution estimates as a fallback.</p>

    <a class="source-link" href="../enrichment-dashboard.html">→ View live NSW enrichment coverage stats</a>

    <p class="subsection-title">Open data advocacy</p>
    <p>GetReal believes property sales data should be freely available in all Australian states and territories. NSW leads with individual sale records. Victoria, Queensland, and others publish only aggregate data. See the <a href="../manifesto.html">data freedom manifesto</a> for the full argument.</p>

    <a class="source-link" href="https://www.valuergeneral.nsw.gov.au/land_values/bulk_land_value_information" target="_blank" rel="noopener">
      ↗ NSW Valuer General — Bulk Property Sales Information
    </a>""",
    related=[
        ("property-realism-score", "Property realism score"),
        ("vic-methodology", "VIC methodology"),
        ("borrowing-capacity", "Borrowing capacity"),
    ]
))


# ── WRITE FILES ───────────────────────────────────────────────────────────────

for p_html in PAGES:
    # Extract slug from canonical URL in content
    lines = p_html.split('\n')
    canonical_line = [l for l in lines if 'rel="canonical"' in l][0]
    slug = canonical_line.strip().split('/methodology/')[1].split('"')[0]
    path = os.path.join(OUT_DIR, f"{slug}.html")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(p_html)
    print(f"✓ methodology/{slug}.html")

print(f"\nDone — {len(PAGES)} pages written to methodology/")
