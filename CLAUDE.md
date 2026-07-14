# GetReal — Project Context for Claude

## What this is
GetReal (get-real.co) is a brutalist dark web tool that helps Australians assess whether their property search budget is realistic. Users enter a suburb, property type, and budget and get a score (0–100%) representing what share of that market they can access.

## Core principle: precision and transparency
**This is non-negotiable.** Every score, label, and data point must be honest about what it is and how it was derived. When we are estimating, we say so. When data is unavailable, we say so. When methodology involves assumptions, we document them. Users are making major financial decisions — vague or misleading confidence is worse than an honest caveat.

## Data sources
- **NSW**: 146,285+ individual sale records from the NSW Valuer General (bulk PSI download). Real counts, real prices, updated periodically.
- **VIC**: Suburb-level median prices and annual sales counts from the Victorian Valuer General quarterly reports (land.vic.gov.au). No individual sale records are publicly available in VIC.
- **price_curves table** (Supabase): NSW-derived price distribution curves, used to score VIC suburbs. Structure: property_type × price_bracket × depth_tier → percentile lookup at 9 ratio thresholds (0.5x–1.5x median). Active markets = 30+ sales/year; thin = under 30. Curves derived from 140k+ NSW transactions.

## VIC scoring methodology
Because VIC doesn't publish individual sale records, VIC budget scores are *estimated* using NSW market distribution curves matched by:
1. Property type (house / apartment / townhouse)
2. Price bracket (5 brackets: under $500k to over $1.8M)
3. Market depth (active ≥30 sales/yr, thin <30 sales/yr)

The annual sales count in VIC data is the rolling 12-month figure from the Q4 2025 VGV report — i.e., calendar year 2025, not the trailing 12 months from today. Always say "in 2025 (VGV annual data)" not "in the last 12 months" for VIC.

## Key files
- `search.html` — single-file frontend (HTML/CSS/JS), the main tool
- `index.html` — landing page
- `faq.html` — methodology FAQ (link VIC methodology to #vic-methodology anchor)
- `manifesto.html` — data freedom manifesto
- `enrichment-dashboard.html` — live NSW enrichment coverage dashboard (also at get-real.co/enrichment-dashboard.html)
- `suburb-data.json` — generated VIC suburb data (run load_vic_quarterly.py to refresh)
- `load_vic_quarterly.py` — parses quarterly VIC XLS files → uploads to Supabase suburb_analytics + regenerates suburb-data.json
- `populate_price_curves.py` — derives NSW distribution curves → upserts into Supabase price_curves table
- `analyse_nsw_distribution.py` — Step 1 analysis: NSW price ratio distributions by type + bracket
- `analyse_nsw_depth.py` — Step 2 analysis: distribution by type + bracket + market depth tier
- `fetch_mcgrath.py` — harvests mcgrath.com.au sold listings (requires curl_cffi + mcgrath_urls.json seed file)
- `match_mcgrath_nsw.py` — matches McGrath sourced_sales_nsw records to property_sales by address, writes bedrooms/bathrooms
- `enrich_property_sales.py` — matches Ray White sourced_sales_nsw to property_sales (same pattern as McGrath script)

## Supabase
- URL: https://lkxzxeeeqfiymunpqvgt.supabase.co
- Publishable key: sb_publishable_1jyBD0hVdHX2ieqFIlC51A_A3ep39Bc (safe for frontend)
- Secret key: NEVER share in chat. Set as SUPABASE_SECRET env var for pipeline scripts.
- Tables: property_sales (NSW individual records), suburb_analytics (VIC + NSW aggregates), price_curves (NSW-derived distribution curves), sourced_sales_nsw/vic/qld/sa/wa/act/tas/nt (agency-sourced sold listings with bedrooms/bathrooms)
- **RLS:** Enabled on all tables (15 July 2026). Public read on property_sales, price_curves, suburb_analytics. Public insert on lead_captures. All sourced_sales_* and raywhite_listings are locked to service_role only. Secret key bypasses RLS — safe for pipeline scripts.

## Data pipeline runbook
See `RUNBOOK.md` for the full step-by-step pipeline — which scripts to run, in what order, for each data refresh. Update it whenever a new source or step is added. The goal is a single weekly automated run.

## Agency data research
See `TRIED-TOOL-01.md` for all data sources investigated, outcomes, and the Ray White API and McGrath scraping approaches. Includes address matching methodology, confidence tiers, coverage targets, and the deduplication check that must be run after every enrichment.

## NSW enrichment coverage (as of 15 July 2026)
- Ray White: 9,168 exact matches
- McGrath: 4,947 exact matches (after dedup cleanup of 233 ambiguous source_ids)
- Total: 14,115 / 146,330 = **9.6%** of NSW property_sales records enriched
- Houses: 12.9% · Units: 3.4%
- Next: add LJ Hooker, Raine & Horne, or other agencies to push coverage higher

## Deployment
- GitHub: https://github.com/postfuturepast/getreal
- Cloudflare Pages: get-real.co (auto-deploys from main branch)
- Push command: `git add -A && git commit -m "message" && git push`

## Data refresh process (when new VIC quarterly data is released)
1. Download new XLS files from land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics
2. Replace the XLS files in this folder
3. `export SUPABASE_SECRET=...` then `python3 load_vic_quarterly.py`
4. When new NSW DAT data is available, re-run `python3 populate_price_curves.py` to refresh curves
5. Commit and push suburb-data.json

## Backlog shortcut
If Tristan says "show me the backlog", read PLAN.md and summarise pending work grouped by: ready to build / blocked / waiting on Tristan.

## Pending work
- Task #51: Build Tool 03 — Deposit floor checker
- Task #52: Build Tool 04 — CGT impact calculator (new vs old rules)
- Task #53: SMS/push failure notifications for GitHub Actions (backlogged)
- NSW bedroom/bathroom enrichment — Ray White + McGrath done (9.6%). Next agencies: LJ Hooker, Raine & Horne, Belle Property, Harcourts. See TRIED-TOOL-01.md for approach per agency.
- Add dedup verification to `enrich_property_sales.py` (Ray White) — same logic as `match_mcgrath_nsw.py`
- Build `promote_probables.py` — bulk-promote reviewed probable matches to exact
