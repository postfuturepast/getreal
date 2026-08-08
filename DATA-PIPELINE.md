# GetReal — Data Pipeline Reference

Complete map of every data source, script, workflow, Supabase table, and propagation path. The authoritative reference for understanding how data moves through the system.

Last updated: 2026-08-08

---

## Architecture summary

```
Source (web/API/download)
  → Fetch script (Python, run by GitHub Actions)
    → Supabase (service_role write)
      → Frontend calculators (anon read, live)
      → API endpoints (anon read, live) [planned]
      → Static page builders (GitHub Actions → commit → Cloudflare Pages)
```

Everything flows through Supabase as the single source of truth. Calculators read it live. Static page builds read it at build time and bake results into HTML.

---

## GitHub Actions Workflows

Nine workflow files. One is superseded (vic-sourced-sales.yml — safe to delete).

### Schedule overview

| Day | Time (AEST) | Workflow | What it does |
|-----|-------------|----------|--------------|
| Sunday | 2:00am | refresh-nsw-data.yml | Download + load NSW VG data |
| Sunday | 2:00am | sourced-sales-refresh.yml | All agency scrapers (non-RW) |
| Sunday | 3:00am | refresh-lookup-data.yml | RBA rates + verify all lookup tables |
| Sunday | 4:00am | nsw-enrichment.yml | Match sourced sales to property_sales |
| Sunday | 6:00am (UTC 20:00) | build-suburb-pages.yml | Rebuild all static pages → commit → deploy |
| Monday | 3:00am | raywhite-incremental.yml | Ray White incremental fetch, all states |
| Monday | 4:00am | monitor-lookup-sources.yml | Check all lookup sources for changes; auto-update where possible |
| Monday | 2:00am (UTC) | refresh-vic-data.yml | Check for new VGV quarterly data |

---

### 1. `refresh-nsw-data.yml`
**Schedule:** Sunday 2am AEST (16:00 UTC) · **Timeout:** 30 min

Downloads and replaces NSW Valuer General data in `property_sales`.

```
load_nsw_csv.py --download --clear --batch-size 500
```
- Source: nswpropertysalesdata.com (James Elks' cleaned VG bulk PSI download)
- Table: `property_sales` (~146k rows, rolling ~12 months)
- **Notification:** None ← gap, see Known Issues

---

### 2. `refresh-vic-data.yml`
**Schedule:** Monday 2:00am UTC (weekly check) · **Timeout:** 15 min

Smart quarterly refresh. Checks every week but only processes and commits when new VGV data is released (exit code 2 = no new data, skips gracefully).

```
download_vic_data.py   → exits 0 (new data) or 2 (already current)
load_vic_quarterly.py  → updates suburb_analytics + regenerates suburb-data.json
git add suburb-data.json && git commit && git push
```
- Source: land.vic.gov.au quarterly XLS files (downloaded automatically)
- Tables: `suburb_analytics`
- Static file: `suburb-data.json` (committed to repo → Cloudflare auto-deploys)
- Commit message includes quarter label (e.g. "data: auto-refresh VIC data to Q2-2026")
- **Notification:** None ← gap

---

### 3. `sourced-sales-refresh.yml`
**Schedule:** Sunday 2am AEST (16:00 UTC) · **Timeout:** 360 min

Runs all non-Ray White agency scrapers. Each scraper runs `continue-on-error: true` so one failure doesn't block others. State files cached between runs for resumability.

**Agencies covered:**

| Agency | Geography | Script |
|--------|-----------|--------|
| Nelson Alexander | VIC only | fetch_nelsonalexander.py |
| Jellis Craig | VIC only | fetch_jelliscraig.py |
| Barry Plant | All states (incremental, --since 21d) | fetch_barryplant.py |
| Harcourts | All states | fetch_harcourts.py |
| LJ Hooker | All states | fetch_ljhooker_all_states.py |
| McGrath | All states | fetch_mcgrath.py |
| McGrath Franchise | All states | fetch_mcgrath_franchise.py |

- Tables: `sourced_sales_nsw`, `sourced_sales_vic`, `sourced_sales_qld`, `sourced_sales_sa`, `sourced_sales_wa`, `sourced_sales_tas`, `sourced_sales_act`, `sourced_sales_nt`
- NDJSON artifacts uploaded for each run (14-day retention) — local backup if Supabase upserts fail
- **Notification:** GitHub issue updated (label: `pipeline-report`) after every run. GitHub emails you when the issue is updated. No extra credentials needed.

Can be triggered manually for a single agency:
```
workflow_dispatch → scraper: nelsonalexander | barryplant | jelliscraig | harcourts | ljhooker | mcgrath | mcgrath_franchise
```

---

### 4. `refresh-lookup-data.yml`
**Schedule:** Sunday 3am AEST (17:00 UTC) · **Timeout:** 15 min

Refreshes RBA benchmark rates and verifies all lookup tables have data.

```
fetch_rba_rates.py          → updates benchmark_rates table
verify_supabase_data.py     → checks all lookup tables are non-empty
```

Tables verified: `lending_policy_constants`, `lvr_limits`, `benchmark_rates`, `stamp_duty_brackets`, `stamp_duty_concessions`, `nt_duty_formula`, `registration_fees`, `lmi_rates`, `hem_benchmarks`

**Notification:** Email via Gmail SMTP (GMAIL_USER + GMAIL_APP_PASSWORD secrets). Sends on success and failure. Subject line includes ✅ or ❌.

---

### 5. `nsw-enrichment.yml`
**Schedule:** Sunday 4am AEST (18:00 UTC) · **Timeout:** 60 min

Runs after NSW data refresh. Matches records in `sourced_sales_nsw` (all agencies) to `property_sales` by address, writes bedrooms/bathrooms/car_spaces.

```
match_nsw_enrichment.py
```
- Writes exact matches to `property_sales` (match_confidence='exact')
- Promotes records outside date window but ≤730 days to 'historical'
- **Notification:** None ← gap

---

### 6. `build-suburb-pages.yml`
**Schedule:** Sunday 6am AEST (20:00 UTC) · **Timeout:** 30 min

Builds all static page sets after the data refresh chain is complete, then commits and pushes once (single Cloudflare deployment).

```
fetch_rba_cash_rate.py                              → updates benchmark_rates
build_suburbs.py + generate_suburbs_nsw_json.py    → suburbs/ HTML + suburbs-nsw.json
build_income_guides.py                              → guides/how-much-can-i-borrow/
build_price_guides.py                               → guides/can-i-afford/

git add suburbs/ sitemap-suburbs.xml suburbs-nsw.json guides/how-much-can-i-borrow/ sitemap-guides-a.xml guides/can-i-afford/ sitemap-guides-b.xml
git commit + git push → Cloudflare Pages auto-deploys
```

**Notification:** None (GitHub Actions email on failure if you watch the repo, but no explicit step)

---

### 7. `raywhite-incremental.yml`
**Schedule:** Monday 3am AEST (17:00 UTC) · **Timeout:** 180 min

Runs the day after the main Sunday pipeline. Fetches Ray White sold listings incrementally (last 35 days) across all states.

```
fetch_raywhite_incremental.py --since 35d
```
- Tables: `sourced_sales_nsw`, `sourced_sales_vic`, `sourced_sales_qld`, etc.
- NDJSON artifacts uploaded (14-day retention)
- Can target a single state: `--state QLD`
- **Notification:** None ← gap

---

### 8. `monitor-lookup-sources.yml`
**Schedule:** Monday 4am AEST (18:00 UTC) · **Timeout:** 15 min

Checks all lookup data sources for changes once a week. Runs the day after the main Sunday pipeline and the Ray White fetch.

```
monitor_lookup_data.py
```

**Behaviour per source:**

| Source | Action on change |
|--------|-----------------|
| HEM benchmarks (JMD Mortgages) | Auto-parse HTML table → upsert `hem_benchmarks` |
| LMI rates (Home Loan Experts) | Auto-parse HTML table → upsert `lmi_rates` |
| NT duty formula (NT Revenue Office) | Auto-verify formula parameters still present |
| Stamp duty pages (8 states — OSR/SRO) | Alert email: page content changed |
| APRA media releases | Alert email: new releases detected |
| ABS ASGS (postcode remoteness) | Alert email: page content changed |
| LMI stamp duty rates (VIC SRO) | Alert email: page content changed |

State tracked in `pipeline_monitor_state` Supabase table (hash per source, timestamps, change count).

Email is sent by the Python script itself (Gmail SMTP) — not by the Actions step — so the summary email contains detail from the parser, not just pass/fail. The workflow sends an additional failure email only if the Python script itself crashes.

**Notification:** Gmail email always (sent by script). Contains ✅ auto-updated / ⚠️ changed (needs review) / ❌ error sections. Workflow sends extra failure email if script crashes before completing.

---

### 9. `vic-sourced-sales.yml`
**Status: SUPERSEDED** — contents: "superseded by sourced-sales-refresh.yml — safe to delete"

---

## Data sources and tables

### Property sales data (raw transactions)

| Source | Update frequency | Script | Supabase table | Notes |
|--------|-----------------|--------|----------------|-------|
| NSW Valuer General | Weekly (auto) | load_nsw_csv.py | property_sales | 146k+ rows, individual sale records |
| VIC Valuer General | Quarterly (auto-detected) | load_vic_quarterly.py | suburb_analytics | Aggregated only — no individual records from this source |

### Agency-sourced sales (bedrooms/bathrooms enrichment)

All agency data lands in `sourced_sales_*` tables, then `match_nsw_enrichment.py` matches to `property_sales`.

| Agency | States | Script | Schedule |
|--------|--------|--------|----------|
| Ray White | All | fetch_raywhite_incremental.py | Weekly Monday |
| Nelson Alexander | VIC | fetch_nelsonalexander.py | Weekly Sunday |
| Jellis Craig | VIC | fetch_jelliscraig.py | Weekly Sunday |
| Barry Plant | All | fetch_barryplant.py | Weekly Sunday |
| Harcourts | All | fetch_harcourts.py | Weekly Sunday |
| LJ Hooker | All | fetch_ljhooker_all_states.py | Weekly Sunday |
| McGrath | All | fetch_mcgrath.py | Weekly Sunday |
| McGrath Franchise | All | fetch_mcgrath_franchise.py | Weekly Sunday |

**NSW enrichment coverage (as of 15 July 2026):**
- Ray White: 9,168 exact + 1,787 historical = 10,955
- McGrath: 4,947 exact + 439 historical = 5,386
- LJ Hooker: 1,368 exact
- Total: ~17,709 / 146,330 = ~12.1%

### Lookup / rate tables

These are read live by calculators and (planned) APIs. Most are updated weekly by `verify_supabase_data.py` or refreshed by dedicated fetch scripts. Legislatively-driven tables (stamp duty) require manual monitoring when governments change rates.

| Table | Source | Update method | Frequency | Volatile? |
|-------|--------|---------------|-----------|-----------|
| benchmark_rates | RBA Statistical Tables | fetch_rba_rates.py | Weekly | Yes — tracks cash rate moves |
| stamp_duty_brackets | State Revenue Offices | Manual (legislative) | When laws change | Medium — review each state budget |
| stamp_duty_concessions | State Revenue Offices | Manual (legislative) | When laws change | Medium |
| lmi_rates | Home Loan Experts (indicative) | Manual | Annually or on lender changes | Low |
| lmi_stamp_duty_rates | State legislation | Manual | Rarely | Very low |
| hem_benchmarks | Melbourne Institute / JMD Mortgages | Manual | Quarterly | Low |
| registration_fees | State land registries | Manual (partly estimated) | Rarely | Very low |
| nt_duty_formula | NT Revenue | Manual | Rarely | Very low |
| lvr_limits | APRA / lender policy | Alert-only monitor | When APRA changes | Low |
| lending_policy_constants | APRA (DTI cap, buffer) | Alert-only monitor | When APRA changes | Low |
| newbuild_concessions | State Revenue Offices | Manual | When programs change | Medium |
| postcode_locations | ABS ASGS Edition 3 | Alert-only monitor | Rarely | Very low |
| pipeline_monitor_state | Internal (monitor script) | Auto (written by monitor_lookup_data.py) | Weekly | n/a — internal state |

---

## Propagation chain

How data flows from source to end consumer:

```
NSW VG data
  → property_sales (Supabase)
    → search.html (live read — realism score)
    → deposit.html / calculators (live read — suburb suggestions)
    → build_suburbs.py → suburbs/nsw/{slug}/index.html → Cloudflare Pages
    → generate_suburbs_nsw_json.py → suburbs-nsw.json → suburbs/index.html (live read)
    → match_nsw_enrichment.py → property_sales.bedrooms / bathrooms

VIC VG data
  → suburb_analytics (Supabase)
    → search.html (live read — VIC score via price_curves proxy)
    → load_vic_quarterly.py → suburb-data.json → suburbs/index.html (live read)
    → build_suburbs.py → suburbs/vic/{slug}/index.html → Cloudflare Pages

Agency sourced sales
  → sourced_sales_* (Supabase)
    → match_nsw_enrichment.py → property_sales (bedrooms/bathrooms)
      → search.html bedroom filter (once coverage ≥ threshold)

RBA / benchmark_rates
  → deposit.html (live read — assessment rate for ceiling calculations)
  → build_income_guides.py → guides/how-much-can-i-borrow/ (baked in at build)
  → build_price_guides.py → guides/can-i-afford/ (baked in at build)
  → [planned] API endpoints (live read)

stamp_duty_brackets + concessions
  → deposit.html (live read — Ceiling 1 stamp duty calc)
  → guides/stamp-duty/ calculator (live read)
  → [planned] API /stamp-duty endpoint (live read)

lmi_rates
  → deposit.html (live read — LMI cost in Ceiling 1)
  → [planned] API /lmi endpoint (live read)

hem_benchmarks
  → deposit.html (live read — HEM floor in Ceiling 3)
  → [planned] API /ceiling/serviceability endpoint (live read)

price_curves
  → search.html (live read — VIC suburb scoring)
  → [planned] API /score endpoints (live read)
```

---

## Notification coverage

| Workflow | Success email | Failure email | Notes |
|----------|--------------|---------------|-------|
| refresh-nsw-data.yml | ❌ | ❌ | No notification at all |
| refresh-vic-data.yml | ❌ | ❌ | No notification at all |
| sourced-sales-refresh.yml | ✅ GitHub issue | ✅ GitHub issue | GitHub emails you on issue update |
| refresh-lookup-data.yml | ✅ Gmail | ✅ Gmail | Uses GMAIL_USER + GMAIL_APP_PASSWORD secrets |
| nsw-enrichment.yml | ❌ | ❌ | No notification at all |
| build-suburb-pages.yml | ❌ | ❌ | No notification at all |
| raywhite-incremental.yml | ❌ | ❌ | No notification at all |
| monitor-lookup-sources.yml | ✅ Gmail (from script) | ✅ Gmail (from workflow) | Script sends detailed summary; workflow catches crashes |

**Gaps:** 3 of 8 active workflows now notify on completion. NSW refresh, enrichment, page builds, and Ray White are still silent.

**Improvement needed:** Add Gmail email step (same pattern as refresh-lookup-data.yml) to: refresh-nsw-data.yml, nsw-enrichment.yml, raywhite-incremental.yml, build-suburb-pages.yml.

---

## Secrets required

| Secret | Used by | Purpose |
|--------|---------|---------|
| SUPABASE_SECRET | All pipeline scripts | Service role key — bypasses RLS, write access |
| GMAIL_USER | refresh-lookup-data.yml, monitor-lookup-sources.yml | Gmail address for sending email notifications |
| GMAIL_APP_PASSWORD | refresh-lookup-data.yml, monitor-lookup-sources.yml | Gmail app password (not account password) |
| GITHUB_TOKEN | refresh-vic-data.yml | Automatically provided by Actions — push access |

---

## Known issues and gaps

- **vic-sourced-sales.yml** — superseded, safe to delete
- **No VIC enrichment matching** — sourced_sales_vic is populated by agencies but `match_nsw_enrichment.py` only matches NSW. VIC matching script not yet built.
- **enrich_property_sales.py (Ray White)** — missing dedup verification query. Add same logic as match_mcgrath_nsw.py before automating.
- **promote_probables.py** — not built. Probable matches from Ray White/McGrath sit unreviewed.
- **enrich_property_sales.py concurrent PATCH timeouts** — occasional failures under load, leaves small % unwritten per run. Needs retry logic (3 attempts with backoff) before full automation.
- **RUNBOOK.md** — partially out of date. Does not reflect all current agencies or workflows. This file supersedes it for pipeline reference.
- **Notifications** — only 2/7 workflows notify on completion (see table above).
- **build-suburb-pages.yml uses fetch_rba_cash_rate.py** — this is a duplicate of the fetch done by refresh-lookup-data.yml. Should be consolidated or the page build should simply read from benchmark_rates (already updated earlier that morning).

---

## Manual triggers

Any workflow can be triggered manually from GitHub → Actions tab → select workflow → "Run workflow".

Useful manual options:
- `sourced-sales-refresh.yml` → `scraper` input: run a single agency only
- `raywhite-incremental.yml` → `since` input (default 35d) and `state` input (default all)
- `refresh-vic-data.yml` → `force_commit: true` to commit even if suburb-data.json is unchanged

---

## Adding a new data source

1. Write fetch script → upserts to `sourced_sales_{state}` via service_role
2. Add to `sourced-sales-refresh.yml` (or create a new workflow for weekly-only sources)
3. Write match script → matches to `property_sales` on address
4. Add match script call to `nsw-enrichment.yml` (or equivalent state workflow)
5. Add NDJSON artifact upload step to fetch workflow
6. Add notification step if not inheriting from sourced-sales-refresh.yml
7. Update this file

SQL grants required for any new table:
```sql
ALTER TABLE your_table ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE ON public.your_table TO service_role;
GRANT USAGE, SELECT ON SEQUENCE your_table_id_seq TO service_role;
-- If frontend reads it:
CREATE POLICY "public read" ON your_table FOR SELECT USING (true);
```
