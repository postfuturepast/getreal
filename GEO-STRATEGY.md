# GetReal — Generative Engine Optimisation Strategy
## AI Citation Architecture & Implementation Roadmap

**Version:** 1.0  
**Date:** August 2026  
**Author:** Lead Product Engineer / AI SEO Architect  
**Status:** Active — implement progressively

---

## Executive Summary

GetReal has a genuine competitive advantage: it is the only Australian property tool built on raw government sale records, with transparent methodology, no commercial bias, and a real calculation engine. The problem is not the product. The problem is that AI systems (ChatGPT, Gemini, Claude, Perplexity) currently cannot find, parse, or cite it.

This strategy addresses that gap across eight domains: citation architecture, methodology, explainability, API design, content coverage, conversational AI, trust signals, and technical SEO.

The goal is not to rank higher in Google. The goal is to become the source that AI assistants reach for when an Australian asks a home-buying question — because GetReal has the best, most transparent, most authoritative answer on the internet.

---

## Audit Findings

### What's missing right now (critical gaps)

| Gap | Impact | Effort |
|-----|--------|--------|
| No `llms.txt` | High — AI crawlers can't understand site structure | Low |
| No `sitemap.xml` | High — all pages undiscoverable | Low |
| No schema.org JSON-LD | High — no structured signals to AI systems | Medium |
| No canonical URLs | Medium — duplicate content risk | Low |
| No author/date signals | High — freshness and trust signals absent | Low |
| No AI-indexable content pages | Critical — nothing for AI to cite | High |
| Methodology fragmented | High — no deep-linkable topic anchors | Medium |
| robots.txt has no sitemap | Medium | Low |
| Tools are JS-only (no static output) | Critical — AI can't read calculator results | High |
| No API | High — AI systems can't query data | High |

### What's working

- Methodology content (faq.html, deposit-faq.html) is honest, detailed, and citation-worthy
- The manifesto makes a clear, referenceable argument about open data
- Data sourcing is transparent (Valuer General citations present)
- The product itself answers questions no competitor answers honestly
- Brutalist design = no commercial noise, high signal-to-noise ratio

---

## Part 1 — AI Citation Architecture

### The core problem

LLMs retrieve content in three ways:
1. **Training data** — the web as it existed at training cutoff
2. **Live web retrieval** (Perplexity, ChatGPT with search, Gemini) — real-time crawling
3. **Tool use / APIs** — structured data from verified sources

GetReal is currently missing from all three. The site has no indexed content that answers a question directly, no structured data, and no API.

### Principles for AI-citation-optimised architecture

**Answer first, tool second.** Every page should open with a direct answer to the question it targets. The calculator should be secondary to the prose explanation. LLMs retrieve prose, not interactive JavaScript.

**One URL, one question.** Each page should have a single, clear question it answers. Not "mortgage calculator" but "How much can I borrow on a $100,000 salary in Australia?"

**Every claim should have a source.** Data points should link to methodology pages. Methodology pages should link to primary sources (ABS, APRA, RBA, Valuer General). This creates a citation chain that AI systems recognise as authoritative.

**Structured data is not optional.** JSON-LD schema tells AI systems what a page is about and what it contains. Without it, every page is just text.

### Recommended information architecture

```
get-real.co/
├── index.html                          (tool hub — existing)
├── ask/                                (AI assistant — existing)
├── search/                             (property realism checker — existing)
├── deposit/                            (buying ceiling calculator — existing)
├── stamp-duty/                         (stamp duty calculator — existing)
│
├── methodology/                        (NEW — methodology hub)
│   ├── index                           (overview, links to all topics)
│   ├── borrowing-capacity              (how borrowing capacity is calculated)
│   ├── deposit-calculation             (LVR, LMI, stamp duty netting)
│   ├── stamp-duty                      (all 8 states, formulas, concessions)
│   ├── serviceability                  (buffer, HEM, stress test)
│   ├── debt-to-income                  (DTI cap, what counts)
│   ├── hecs-help                       (how HECS affects borrowing)
│   ├── living-expenses                 (HEM benchmarks, methodology)
│   ├── lmi                             (how LMI is calculated)
│   ├── lvr                             (LVR limits by property type)
│   ├── interest-rate-assumptions       (which rate we use and why)
│   ├── property-realism-score          (how the search score is calculated)
│   ├── vic-methodology                 (VIC-specific curve estimation)
│   └── data-sources                    (all data sources, licenses, dates)
│
├── guides/                             (NEW — answer-first content pages)
│   ├── australia/                      (national guides)
│   ├── nsw/                            (state guides)
│   ├── vic/
│   ├── qld/
│   └── ...
│
├── suburb/                             (NEW — suburb-specific pages, generated)
│   ├── nsw/
│   │   ├── parramatta/
│   │   └── ...
│   └── vic/
│
├── faq/                                (existing faq.html → becomes /faq/)
├── manifesto/                          (existing manifesto.html)
├── enrichment-dashboard/               (existing)
│
├── sitemap.xml                         (NEW)
├── robots.txt                          (update)
└── llms.txt                            (NEW)
```

### Internal linking strategy

Every page should link to:
1. Its relevant methodology page(s)
2. Its relevant calculator(s)
3. 2–3 related guide pages
4. The data sources page

Every methodology page should link to:
1. The calculator that uses it
2. Related methodology topics
3. Primary source (government website)
4. Changelog/version history

Every guide page should link to:
1. The calculator to run the calculation
2. The methodology explaining the result
3. 3–5 related questions

### Schema.org structured data

Implement JSON-LD on every page:

| Page type | Schema |
|-----------|--------|
| Homepage | `WebSite`, `Organization`, `SiteLinksSearchBox` |
| Calculators | `HowTo`, `WebApplication`, `FinancialProduct` |
| FAQ pages | `FAQPage` with `Question`/`Answer` pairs |
| Methodology pages | `Article` with `author`, `datePublished`, `dateModified`, `citation` |
| Guide pages | `Article`, `FAQPage`, `BreadcrumbList` |
| Suburb pages | `Article`, `Dataset`, `BreadcrumbList` |
| Global | `BreadcrumbList` on every page |

### Canonical URLs

Every page needs a canonical URL. The current site has none. Pattern:
```html
<link rel="canonical" href="https://get-real.co/deposit/" />
```

The site currently has redirect inconsistencies (deposit.html → /deposit). Canonicals should point to the clean URL (no .html extension).

### Metadata improvements

Current meta descriptions are functional but not answer-first. Compare:

**Current:** "Find your real property buying ceiling — deposit, debt-to-income, and serviceability."

**Better:** "Calculate your maximum property budget in Australia. GetReal accounts for stamp duty, LMI, your debt-to-income ratio, and serviceability buffer — and shows which of the three limits you've hit."

Every page needs:
- `<meta name="description">` — answer-first, 140–160 characters
- `<meta property="og:image">` — currently missing on most pages
- `<meta name="article:published_time">` on methodology/guide pages
- `<meta name="article:modified_time">` on methodology/guide pages
- `<link rel="canonical">`

### Trust signals for AI citation

AI systems weight content by trust. Things that increase citation probability:

1. **Author attribution** — even "GetReal Editorial Team" is better than nothing. Add a byline to methodology pages.
2. **Publication and update dates** — AI systems treat recent content as more authoritative. Every methodology page needs a visible "Last updated: Month Year" date.
3. **Primary source citations** — link directly to ABS, APRA, RBA, and state Valuer General sites.
4. **Version history** — a simple changelog on methodology pages signals active maintenance.
5. **Methodology version numbers** — e.g., "Serviceability calculation v1.3 — updated June 2026 to reflect APRA July 2025 HECS ruling."
6. **Data freshness indicators** — "NSW data: updated daily. VIC data: last updated Q4 2025."

---

## Part 2 — Methodology

### Current state

Methodology content exists in two places:
- `faq.html` — covers property realism score methodology
- `deposit-faq.html` — covers deposit, LVR, LMI, stamp duty, serviceability

Problems:
- Fragmented — no single methodology hub
- No deep-linkable anchors for individual topics
- No version numbers or update dates
- No changelog
- Not linked from calculators in a structured way
- No schema.org markup

### Recommended methodology architecture

Create `/methodology/` as a hub with individual topic pages. Each page should:

1. **State the rule clearly** — e.g., "In Australia, lenders apply a serviceability buffer of 3% above your interest rate (APRA floor as of July 2025)."
2. **Explain why** — the regulatory or practical reason
3. **Show the formula** — explicit calculation
4. **Give a worked example** — concrete numbers
5. **Link to the primary source** — APRA, RBA, ATO, state revenue office
6. **Show the version history** — date and what changed

### Priority methodology pages to build

| Page | URL | Priority |
|------|-----|----------|
| Borrowing Capacity | /methodology/borrowing-capacity | P0 |
| Serviceability Buffer | /methodology/serviceability | P0 |
| Debt-to-Income Ratio | /methodology/debt-to-income | P0 |
| Stamp Duty — All States | /methodology/stamp-duty | P0 |
| Deposit Calculation | /methodology/deposit-calculation | P0 |
| HECS/HELP & Borrowing | /methodology/hecs-help | P0 |
| LVR Limits | /methodology/lvr | P1 |
| LMI Calculation | /methodology/lmi | P1 |
| Interest Rate Assumptions | /methodology/interest-rate-assumptions | P1 |
| Living Expenses (HEM) | /methodology/living-expenses | P1 |
| Property Realism Score | /methodology/property-realism-score | P1 |
| VIC Estimation Methodology | /methodology/vic-methodology | P1 |
| Data Sources & Licences | /methodology/data-sources | P1 |

### Methodology page template

```
[METHODOLOGY LABEL] [VERSION] [LAST UPDATED DATE]

# [Topic]

## The rule

[One clear sentence stating the rule, regulation, or standard.]

## How GetReal applies it

[2–3 sentences explaining the implementation.]

## Formula

[Explicit mathematical expression]

## Worked example

[Concrete numbers through the formula]

## Assumptions

[Any simplifications or limitations]

## Primary source

[Link to APRA, ATO, RBA, or state authority]

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 1.1 | Jul 2025 | HECS excluded from DTI per APRA ruling |
| 1.0 | Jan 2025 | Initial |
```

---

## Part 3 — Explainability

### The problem

GetReal's calculators currently produce a number. They don't explain what drove that number or what the user can change to improve it. This is a missed opportunity for both UX and AI citability.

An AI assistant that can explain *why* a result is what it is is infinitely more useful than one that just produces a number — and far more likely to be cited.

### Recommended output structure for all calculators

**Before (current):**
```
Maximum borrowing: $920,000
```

**After (target):**
```
Maximum borrowing: $920,000

This is your Ceiling 3 (serviceability) limit — your income 
after living costs can support a $920,000 loan.

What's holding you back:
  • HECS repayments reduce your net income by ~$7,200/year
  • HEM floor for a couple with 1 dependant: $4,680/month
  • Serviceability buffer adds 3% to the stress-test rate (9.49%)
  • Existing car loan ($350/month) counts against your surplus

Your three ceilings:
  Deposit:          $980,000  ← not your limit
  Debt-to-income:   $1,140,000 ← not your limit  
  Serviceability:   $920,000  ← THIS IS YOUR LIMIT

To increase your ceiling, the highest-impact lever is:
  Closing your credit card ($12,000 limit) would add ~$45,000 
  to your borrowing capacity.

[Methodology: how we calculate serviceability →]
```

### Explainability for the property realism score

**Before:**
```
Realism score: 34% — Tight
```

**After:**
```
Realism score: 34% — Tight

Out of 127 houses sold in Reservoir last year, 
approximately 43 were within your $850,000 budget.
Of those, roughly 15 had 3+ bedrooms.

What's holding you back:
  Budget coverage:    67% of Reservoir houses  
  3+ bedrooms:        51% of those  
  Combined:           34%

The biggest constraint is your budget. Raising it by $50,000 
would likely lift your score to ~45% (Competitive).

[How the realism score is calculated →]
```

### Implementation approach

Every result component should expose:
- The binding constraint (which ceiling/factor is limiting)
- The formula applied
- The key input values
- The highest-leverage change the user can make
- A link to the relevant methodology page

This makes every result shareable, explainable, and citable by AI systems — because the explanation is in the HTML, not just the number.

---

## Part 4 — AI-Friendly API

### Purpose

A public API serves two purposes simultaneously:
1. Developers and other applications can integrate GetReal's calculations
2. AI systems (which increasingly call APIs as tools) can query GetReal directly

### Recommended endpoints

**Base URL:** `https://api.get-real.co/v1/`

```
GET  /v1/methodology                    List all methodology topics + links
GET  /v1/methodology/{topic}            Fetch a specific methodology page

POST /v1/borrowing-capacity             Calculate max borrowing
POST /v1/deposit                        Calculate deposit ceiling
POST /v1/stamp-duty                     Calculate stamp duty
POST /v1/serviceability                 Calculate serviceability
POST /v1/lmi                            Calculate LMI premium
POST /v1/property-affordability         Check suburb budget realism
POST /v1/monthly-repayments             Calculate P&I repayments

GET  /v1/suburbs                        List available suburbs (+ state filter)
GET  /v1/suburbs/{state}/{suburb}       Get suburb market data
GET  /v1/rate                           Current interest rate assumption + source
```

### Request/response design principles

- JSON in, JSON out
- Every response includes a `methodology_url` field pointing to the relevant methodology page
- Every response includes a `disclaimer` field
- Every response includes a `data_as_of` field
- Versioned (`/v1/`) from day one
- Rate limited: 100 requests/day on free tier, unlimited on API key
- Error responses are human-readable

### Example: POST /v1/borrowing-capacity

**Request:**
```json
{
  "borrowers": [
    {
      "gross_annual_income": 120000,
      "take_home_fortnightly": 3800,
      "hecs_debt": 45000
    }
  ],
  "dependants": 1,
  "existing_debts": [
    { "type": "car_loan", "monthly_repayment": 450, "outstanding_balance": 18000 }
  ],
  "credit_card_limit": 10000,
  "state": "NSW",
  "property_type": "house",
  "owner_occupier": true,
  "interest_rate_override": null
}
```

**Response:**
```json
{
  "ceiling_1_deposit": null,
  "ceiling_2_dti": 1080000,
  "ceiling_3_serviceability": 890000,
  "binding_ceiling": "serviceability",
  "maximum_borrowing": 890000,
  "stress_rate_applied": 9.49,
  "monthly_repayment_at_stress_rate": 7240,
  "monthly_surplus_income": 7240,
  "hem_applied": 3980,
  "factors": {
    "hecs_monthly_reduction": 600,
    "credit_card_monthly_cost": 250,
    "existing_debt_monthly": 450
  },
  "explanation": "Your serviceability ceiling of $890,000 is driven by your monthly net income surplus of $7,240 after HEM living costs, existing debt repayments, and HECS withholding. Your credit card limit ($10,000) is treated as fully drawn and reduces available surplus.",
  "highest_impact_lever": "Closing your credit card limit would increase your maximum borrowing by approximately $43,000.",
  "methodology_url": "https://get-real.co/methodology/borrowing-capacity",
  "disclaimer": "This is an estimate only. Lender policies vary. Consult a licensed mortgage broker.",
  "data_as_of": "2026-08-01",
  "api_version": "1.0"
}
```

### Documentation

Host API docs at `https://get-real.co/api/` as a static HTML page. Include:
- Authentication (API key via `X-API-Key` header)
- Rate limiting policy
- All endpoints with full request/response examples
- Error codes
- Changelog
- Terms of use

Make the documentation page itself AI-readable (prose explanations, not just code blocks).

### Implementation path

Phase 1: Deploy calculation functions from engine.js as serverless functions (Cloudflare Workers or Supabase Edge Functions)  
Phase 2: Add suburb data endpoints from existing Supabase tables  
Phase 3: Rate limiting + API key management  
Phase 4: Public docs page  
Phase 5: Register in API directories (RapidAPI, Postman, etc.)

---

## Part 5 — Topic Coverage

### Strategy

The guiding principle: every question an Australian has ever asked ChatGPT about buying a home should have a GetReal page that is the best answer on the internet — backed by real data, transparent methodology, and a live calculator.

These are not traditional blog posts. They are **answer pages**: static HTML with:
1. A direct answer to the question in the first paragraph
2. A worked example with real numbers
3. A link to the relevant calculator
4. A methodology citation
5. FAQPage schema for AI retrieval
6. Related questions

### Content map — 500+ pages

**Category 1: Affordability by price point (40 pages)**

| Question | URL |
|----------|-----|
| Can I afford a $500,000 property? | /guides/can-i-afford/500000 |
| Can I afford a $600,000 property? | /guides/can-i-afford/600000 |
| Can I afford a $700,000 property? | /guides/can-i-afford/700000 |
| Can I afford a $750,000 property? | /guides/can-i-afford/750000 |
| Can I afford an $800,000 property? | /guides/can-i-afford/800000 |
| Can I afford a $900,000 property? | /guides/can-i-afford/900000 |
| Can I afford a $1,000,000 property? | /guides/can-i-afford/1000000 |
| Can I afford a $1,200,000 property? | /guides/can-i-afford/1200000 |
| Can I afford a $1,500,000 property? | /guides/can-i-afford/1500000 |
| Can I afford a $2,000,000 property? | /guides/can-i-afford/2000000 |
*(continue at $50k intervals from $400k to $2.5M)*

**Category 2: Income-based borrowing (30 pages)**

| Question | URL |
|----------|-----|
| How much can I borrow on $60,000 salary? | /guides/borrow/salary-60000 |
| How much can I borrow on $80,000 salary? | /guides/borrow/salary-80000 |
| How much can I borrow on $100,000 salary? | /guides/borrow/salary-100000 |
| How much can I borrow on $120,000 salary? | /guides/borrow/salary-120000 |
| How much can I borrow on $150,000 salary? | /guides/borrow/salary-150000 |
| How much income do I need to buy a $600,000 house? | /guides/income-needed/600000 |
| How much income do I need to buy a $800,000 house? | /guides/income-needed/800000 |
| How much income do I need to buy a $1,000,000 house? | /guides/income-needed/1000000 |
| How much income do I need to buy a $1,500,000 house? | /guides/income-needed/1500000 |
| Combined income borrowing capacity | /guides/borrow/combined-income |
*(continue at $10k intervals $50k–$250k)*

**Category 3: Deposit scenarios (20 pages)**

| Question | URL |
|----------|-----|
| Can I buy with a 5% deposit in Australia? | /guides/deposit/5-percent |
| Can I buy with a 10% deposit? | /guides/deposit/10-percent |
| Can I buy with a 20% deposit? | /guides/deposit/20-percent |
| What deposit do I need for a $600,000 house? | /guides/deposit/needed-for-600000 |
| What deposit do I need for an $800,000 house? | /guides/deposit/needed-for-800000 |
| What deposit do I need for a $1,000,000 house? | /guides/deposit/needed-for-1000000 |
| Using the First Home Guarantee (5% deposit) | /guides/deposit/first-home-guarantee |
| How does LMI affect my deposit? | /guides/deposit/lmi-impact |
| How much deposit to avoid LMI? | /guides/deposit/avoid-lmi |
| Gifted deposit — does it count? | /guides/deposit/gifted-deposit |

**Category 4: Occupation-based borrowing (25 pages)**

| Question | URL |
|----------|-----|
| Teacher borrowing capacity | /guides/occupation/teacher |
| Nurse borrowing capacity | /guides/occupation/nurse |
| Doctor borrowing capacity | /guides/occupation/doctor |
| Police officer borrowing capacity | /guides/occupation/police-officer |
| Tradesperson borrowing capacity | /guides/occupation/tradesperson |
| Public servant borrowing capacity | /guides/occupation/public-servant |
| Self-employed borrowing capacity | /guides/occupation/self-employed |
| Casual worker borrowing capacity | /guides/occupation/casual-worker |
| Part-time worker borrowing capacity | /guides/occupation/part-time |
| Contractor borrowing capacity | /guides/occupation/contractor |
*(continue: lawyer, accountant, pharmacist, engineer, social worker, etc.)*

**Category 5: Life situation (25 pages)**

| Question | URL |
|----------|-----|
| Buying with HECS debt | /guides/situation/hecs-debt |
| How much does HECS reduce borrowing? | /guides/situation/hecs-borrowing-impact |
| Buying after divorce | /guides/situation/buying-after-divorce |
| Buying as a single parent | /guides/situation/single-parent |
| Buying with a partner | /guides/situation/buying-with-partner |
| Buying investment property while renting | /guides/situation/investment-while-renting |
| First home buyer guide | /guides/situation/first-home-buyer |
| Second property guide | /guides/situation/second-property |
| Buying with parents (guarantor) | /guides/situation/guarantor-loan |
| Buying off the plan | /guides/situation/off-the-plan |

**Category 6: Stamp duty guides (30 pages)**

| Question | URL |
|----------|-----|
| Stamp duty in NSW | /guides/stamp-duty/nsw |
| Stamp duty in VIC | /guides/stamp-duty/vic |
| Stamp duty in QLD | /guides/stamp-duty/qld |
| Stamp duty in WA | /guides/stamp-duty/wa |
| Stamp duty in SA | /guides/stamp-duty/sa |
| Stamp duty in TAS | /guides/stamp-duty/tas |
| Stamp duty in ACT | /guides/stamp-duty/act |
| Stamp duty in NT | /guides/stamp-duty/nt |
| First home buyer stamp duty concessions | /guides/stamp-duty/first-home-buyer |
| Stamp duty on a $500,000 property | /guides/stamp-duty/on-500000 |
| Stamp duty on a $600,000 property | /guides/stamp-duty/on-600000 |
| Stamp duty on a $800,000 property | /guides/stamp-duty/on-800000 |
| Stamp duty on a $1,000,000 property | /guides/stamp-duty/on-1000000 |
| Stamp duty on investment properties | /guides/stamp-duty/investment-property |
*(continue at price points $400k–$2M)*

**Category 7: City and region guides (30 pages)**

| Question | URL |
|----------|-----|
| Buying in Sydney | /guides/location/sydney |
| Buying in Melbourne | /guides/location/melbourne |
| Buying in Brisbane | /guides/location/brisbane |
| Buying in Perth | /guides/location/perth |
| Buying in Adelaide | /guides/location/adelaide |
| Buying in Canberra | /guides/location/canberra |
| Buying in the inner west (Sydney) | /guides/location/sydney-inner-west |
| Buying in the eastern suburbs (Sydney) | /guides/location/sydney-eastern-suburbs |
| Buying in western Sydney | /guides/location/sydney-western |
| Buying in Melbourne's inner north | /guides/location/melbourne-inner-north |
| Buying in regional NSW | /guides/location/regional-nsw |
| Buying in regional VIC | /guides/location/regional-vic |

**Category 8: Suburb-specific pages (NSW — ~300 pages)**

For every NSW suburb with 30+ sales/year, generate a static page:

| Page | URL |
|------|-----|
| Parramatta property market | /suburb/nsw/parramatta |
| Blacktown property market | /suburb/nsw/blacktown |
| Liverpool property market | /suburb/nsw/liverpool |
| Bondi property market | /suburb/nsw/bondi |
*(continue for all active NSW suburbs)*

Each page includes:
- Median price (current)
- Sales volume (last 13 months)
- Price distribution chart (what % of sales fall at each price bracket)
- Bedroom/bathroom distribution
- "What can $X buy in [suburb]?" sections at 3–4 price points
- Link to run the full property realism check
- Last updated date and data source citation

**Category 9: Concept explainers (30 pages)**

| Question | URL |
|----------|-----|
| What is LVR? | /guides/concepts/lvr |
| What is LMI? | /guides/concepts/lmi |
| What is DTI? | /guides/concepts/dti |
| What is a serviceability buffer? | /guides/concepts/serviceability-buffer |
| What is HEM? | /guides/concepts/hem |
| What is APRA? | /guides/concepts/apra |
| What is a comparison rate? | /guides/concepts/comparison-rate |
| What is stamp duty? | /guides/concepts/stamp-duty |
| What is conveyancing? | /guides/concepts/conveyancing |
| What is an offset account? | /guides/concepts/offset-account |
| What is principal and interest? | /guides/concepts/principal-and-interest |
| What is a fixed rate mortgage? | /guides/concepts/fixed-rate |
| What is a variable rate mortgage? | /guides/concepts/variable-rate |
| What is genuine savings? | /guides/concepts/genuine-savings |
| What is negative gearing? | /guides/concepts/negative-gearing |

**Category 10: Comparison and scenario pages (30 pages)**

| Question | URL |
|----------|-----|
| House vs apartment: what can I borrow? | /guides/compare/house-vs-apartment |
| Investing vs owner-occupying | /guides/compare/invest-vs-owner-occupy |
| 5% vs 20% deposit — real cost comparison | /guides/compare/5-vs-20-percent-deposit |
| Fixed vs variable: which rate assumption? | /guides/compare/fixed-vs-variable |
| Buying with one income vs two | /guides/compare/single-vs-dual-income |
| Closing your credit card before applying | /guides/compare/close-credit-card |

**Total content target: ~550 pages**

### Content generation strategy

Suburb pages (~300) and price-point pages (~80) can be programmatically generated from existing Supabase data. The template is static HTML with data injected at build time (or on-demand from Cloudflare Workers). 

Priority order:
1. P0: Concept explainers (high citation value, low data dependency)
2. P0: Life situation guides (high search intent, evergreen)
3. P0: Methodology pages (trust foundation)
4. P1: Stamp duty guides (high volume, state-by-state)
5. P1: Income/affordability guides (high LLM query volume)
6. P2: Suburb pages (data-generated, high volume)

---

## Part 6 — Conversational AI (ask.html)

### Current state

The AI assistant at /ask exists but is minimal — no metadata, a bare page, and no visible guidance on what it can do. It likely uses basic prompt-to-response without structured coaching.

### Target behaviour: home-buying coach

The AI should behave like a knowledgeable, unbiased mortgage broker who explains trade-offs clearly. It should:

**Ask clarifying questions** — before answering "can I afford a $900k house", ask:
- Are you buying alone or with a partner?
- Do you have savings for a deposit?
- Do you have any existing debt?
- Is this your first property?
- What state are you buying in?

**Explain trade-offs** — not just "yes" or "no", but "yes if X, no if Y, and here's the lever":
> "On your income, you could borrow up to $850,000, but your HECS debt is reducing that by about $60,000. If you pay $20,000 off your HECS, your borrowing capacity barely moves — it's not worth it. The bigger lever is your credit card limit."

**Show confidence levels** — when estimating, say so:
> "Based on a $110,000 income and standard HEM for a single buyer in metro Sydney, my estimate is $750,000–$820,000. This is an estimate — actual lender assessment will vary."

**Link to methodology** — every factual claim should reference its source:
> "The 3% serviceability buffer is set by APRA. [How we calculate this →]"

**Link to calculators** — convert conversation to action:
> "Want the exact number? Enter your full details in the buying ceiling calculator — it covers all three ceilings."

**Suggest next steps** — don't just answer:
> "Based on what you've told me, your binding constraint is your deposit — not your income. The next step is to find out if the First Home Guarantee could work for you."

### System prompt design principles

The AI assistant's system prompt should:
1. Ground responses in GetReal methodology
2. Cite specific methodology pages
3. Always hedge with "consult a mortgage broker" for complex situations
4. Never invent data — use GetReal's real data sources
5. Maintain a clear "three ceilings" framework for borrowing conversations
6. Use real suburb data when discussing specific locations
7. Treat every conversation as an opportunity to educate, not just answer

### Structured conversation flows

Design explicit flows for the 10 most common entry questions:
1. "How much can I borrow?"
2. "Can I afford X suburb?"
3. "How much deposit do I need?"
4. "How does HECS affect my borrowing?"
5. "What is stamp duty in [state]?"
6. "Can I buy with a 5% deposit?"
7. "What's my buying limit?"
8. "How much do I need to save?"
9. "Should I fix or go variable?"
10. "Is [suburb] realistic on my budget?"

For each flow, define: opening clarifying questions, the calculation to run, the explanation template, and the recommended next step.

---

## Part 7 — Trust & Authority

### Why AI systems cite some sources and not others

AI assistants are essentially doing reputation assessment at scale. They weight sources by:
1. **Uniqueness of data** — does this source have data no one else has?
2. **Primary source status** — does this cite governments and regulators directly?
3. **Transparency of methodology** — is the calculation explained?
4. **Currency** — is the content recent and actively maintained?
5. **Inbound links from trusted sources** — are credible sites linking here?
6. **Structured data** — is the content machine-readable?

GetReal has genuine advantages on points 1, 2, and 3. Points 4, 5, and 6 need work.

### Recommended trust-building initiatives

**Original datasets and research:**
- Publish an annual "Australian Property Affordability Report" as a citable PDF
- Publish quarterly suburb affordability rankings by state
- Publish a "Stamp Duty Burden Index" — stamp duty as a percentage of median income by state and suburb
- Make datasets downloadable in CSV format under Creative Commons licence
- Create an open "Australian Borrowing Capacity Dataset" — anonymised inputs and outputs

**Methodology as a product:**
- Version control the methodology (GitHub-linked changelog)
- Publish "GetReal Methodology Notes" as a citable document with DOI
- Have methodology reviewed by an independent financial professional (with byline)

**Public data advocacy:**
- Expand the manifesto into a research paper: "The Case for Open Property Data in Australia"
- Publish state-by-state open data scorecards
- Partner with university housing research centres (AHURI, Grattan) — not for money, for citation

**Content that earns citations:**
- "When did HECS stop counting in mortgage applications?" — definitive answer page
- "What is the current APRA serviceability buffer?" — updated automatically, linked to RBA
- "What are stamp duty rates across Australia in 2026?" — comprehensive, authoritative
- "How much have property prices changed in [suburb] over 10 years?" — data-driven

**Media and community:**
- When journalists write about housing affordability, GetReal should be the tool they link to
- Engage with Reddit communities (r/AusFinance, r/AusPropertyChat) — not spam, but genuine useful tools
- Share suburb data insights that are genuinely newsworthy

---

## Part 8 — Technical Audit

### Critical issues

| Issue | Impact | Fix |
|-------|--------|-----|
| No sitemap.xml | High | Create sitemap.xml, link from robots.txt |
| No llms.txt | High | Create llms.txt describing the site for AI crawlers |
| No schema.org | High | Add JSON-LD to all pages |
| No canonical URLs | Medium | Add `<link rel="canonical">` to all pages |
| No og:image | Medium | Create default og:image, add to all pages |
| robots.txt has no sitemap reference | Medium | Update robots.txt |
| JS-only calculator output | Critical | Add static HTML output for key results |

### Performance

- Google Fonts are render-blocking. Consider self-hosting or using `font-display: swap`
- `suburb-data.json` is large (~780 VIC suburbs) — consider lazy-loading
- No HTTP/2 push or preloading of critical resources

### Crawlability

- JavaScript-heavy calculators mean bots see only the initial form state, not any output
- No `<noscript>` fallback content
- All tool output is ephemeral — no shareable URLs with state

**Recommendation:** Every calculator result should be representable as a URL with state parameters, e.g.:
`/deposit/result?state=NSW&savings=150000&fhb=true&property_type=house`

This makes results shareable, crawlable, and referenceable.

### Structured data opportunities

- `WebSite` + `SiteLinksSearchBox` on homepage
- `FAQPage` on faq.html (many existing Q&A pairs)
- `HowTo` on deposit.html and stamp-duty.html
- `Dataset` on enrichment-dashboard.html
- `Article` + `dateModified` on all methodology pages

### Sitemap improvements

Current sitemap: doesn't exist (returns homepage).

Required sitemap structure:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://get-real.co/</loc>
    <lastmod>2026-08-01</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <!-- all pages with changefreq and lastmod -->
</urlset>
```

When guide pages are built, use a sitemap index to manage multiple sitemaps.

### Internal linking improvements

Current: sparse, mostly header links back to homepage.

Required linking pattern:
- Every calculator → its methodology page
- Every methodology page → the calculator and related methodology
- Every guide page → calculator + methodology + 3 related guides
- Every suburb page → property realism tool pre-filled with that suburb

---

## Prioritised Roadmap

### Quick wins — implement now (1–2 weeks)

| # | Action | Impact | Effort | Owner |
|---|--------|--------|--------|-------|
| Q1 | Create `llms.txt` | High | 1hr | Engineer |
| Q2 | Create `sitemap.xml` | High | 2hr | Engineer |
| Q3 | Update `robots.txt` to reference sitemap | Low | 15min | Engineer |
| Q4 | Add JSON-LD schema to index.html (WebSite + Org) | High | 2hr | Engineer |
| Q5 | Add FAQPage schema to faq.html | High | 3hr | Engineer |
| Q6 | Add HowTo schema to deposit.html | Medium | 3hr | Engineer |
| Q7 | Add Article schema to deposit-faq.html | Medium | 1hr | Engineer |
| Q8 | Add canonical URLs to all pages | Medium | 2hr | Engineer |
| Q9 | Add publication/modified dates to faq.html and deposit-faq.html | Medium | 1hr | Engineer |
| Q10 | Add author byline to methodology pages | Low | 30min | Engineer |
| Q11 | Add `og:image` to all pages | Medium | 2hr | Engineer |
| Q12 | Add `<meta name="article:modified_time">` to FAQ/methodology pages | Medium | 1hr | Engineer |

**Total quick wins: ~20 hours of engineering**

### Medium term — 1–3 months

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| M1 | Build /methodology/ hub with 5 P0 topic pages | High | 3 days |
| M2 | Build 10 concept explainer pages (/guides/concepts/) | High | 3 days |
| M3 | Build 8 stamp duty guides (one per state) | High | 2 days |
| M4 | Build 10 income/affordability guides | High | 3 days |
| M5 | Build 10 life situation guides | High | 3 days |
| M6 | Add shareable/stateful URLs to calculators | Medium | 3 days |
| M7 | Add explainability output to deposit calculator | High | 3 days |
| M8 | Add explainability output to search tool | High | 3 days |
| M9 | Build API v1 — stamp duty + borrowing capacity endpoints | High | 1 week |
| M10 | Build API docs page | Medium | 2 days |
| M11 | Improve ask.html — structured conversation flows | Medium | 3 days |
| M12 | NSW suburb pages (top 50 by volume) | High | 3 days |

### Long term — 6–18 months

| # | Action | Impact | Effort |
|---|--------|--------|--------|
| L1 | Full guide content library (500+ pages) | Critical | 2 months |
| L2 | All NSW suburb pages (~300) | High | 2 weeks |
| L3 | All VIC suburb pages (~780) | High | 2 weeks |
| L4 | Full API v1 with all endpoints | High | 1 month |
| L5 | Annual affordability report (PDF + landing page) | High | 1 week |
| L6 | Quarterly suburb rankings + data downloads | High | 1 week |
| L7 | Partner with AHURI / Grattan / journalism | High | Ongoing |
| L8 | Self-updating rate/buffer pages (live from RBA) | Medium | 1 week |
| L9 | Historical price data pages (10-year suburb trends) | High | 2 weeks |
| L10 | Expand AI assistant with GetReal data grounding | High | 1 month |

### Impact vs effort matrix

```
HIGH IMPACT
│
│  [Q4 Schema]    [M1 Methodology]  [L1 Guide Library]
│  [Q1 llms.txt]  [M9 API]          [L5 Annual Report]
│  [Q2 Sitemap]   [M12 Suburb pages]
│                 [M7 Explainability]
│
│  [Q5 FAQ Schema][M3 Stamp duty]   [L7 Media/Uni]
│  [Q6 HowTo]     [M4 Income guides]
│
LOW ──────────────────────────────────────── HIGH EFFORT
│
│  [Q3 robots.txt][M6 Stateful URLs]
│  [Q8 Canonicals][M11 Ask flows]
│
LOW IMPACT
```

---

## Appendix A — `llms.txt` specification

The `llms.txt` standard (llmstxt.org) provides AI crawlers with a structured overview of a site's content and purpose. It is the `robots.txt` for LLMs.

See implementation in the quick wins below.

## Appendix B — Schema.org reference

Recommended schema types for GetReal:
- `WebSite` — homepage
- `Organization` — homepage, all pages
- `WebApplication` — calculator pages
- `FinancialProduct` — calculators (type: LoanOrCredit adjacent)
- `HowTo` — step-by-step calculators
- `FAQPage` — FAQ and guide pages
- `Article` — methodology and guide pages
- `Dataset` — enrichment dashboard, suburb data
- `BreadcrumbList` — all non-homepage pages

## Appendix C — llms.txt content

See `llms.txt` file in repository root.
