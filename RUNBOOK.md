# GetReal — Data Pipeline Runbook

This document describes how to run the full data refresh pipeline. It grows over time as new sources and states are added. The goal is a single weekly cron job that keeps all data fresh.

---

## Prerequisites

```bash
cd ~/Claude/Projects/Property\ Search\ Tool
export SUPABASE_SECRET=your_service_role_key_here
```

The service role key is in Supabase dashboard → Settings → API → service_role. Never commit it. Never share it in chat.

---

## Current pipeline (as of 15 July 2026)

### Step 1 — NSW Valuer General data refresh
Runs automatically via GitHub Actions (weekly). No manual action needed unless the source URL changes.
- Source: nswpropertysalesdata.com (James Elks' cleaner of the NSW VG bulk PSI download)
- Table: `property_sales`
- Records: ~146k, rolling ~12 months
- Script: handled by GitHub Actions (`.github/workflows/`)

### Step 2 — VIC Valuer General data refresh
Run when new quarterly XLS files are released (land.vic.gov.au, ~quarterly).
```bash
# 1. Download new XLS files from land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics
# 2. Replace XLS files in this folder
python3 load_vic_quarterly.py
```
- Table: `suburb_analytics` (aggregated) + regenerates `suburb-data.json`
- Note: VIC data is suburb-level aggregates only, no individual sale records from this source

### Step 3 — Ray White sold listings extraction (all states)

#### NSW (run if re-extracting from scratch)
```bash
python3 fetch_raywhite.py
```
- Postcodes: 2000–2999
- Table: `sourced_sales_nsw`
- Local backup: `raywhite_listings.ndjson`
- Resume-friendly: state tracked in `.raywhite_state.json`
- Run time: ~2 hours

#### VIC
```bash
python3 fetch_raywhite_vic.py
```
- Postcodes: 3000–3999
- Table: `sourced_sales_vic`
- Local backup: `raywhite_vic_listings.ndjson`
- Resume-friendly: state tracked in `.raywhite_vic_state.json`
- Run time: ~2 hours

#### QLD, SA, WA, TAS, NT, ACT (all at once)
```bash
python3 fetch_raywhite_all_states.py
```
Or a single state:
```bash
python3 fetch_raywhite_all_states.py QLD
```
- Tables: `sourced_sales_qld`, `sourced_sales_sa`, `sourced_sales_wa`, `sourced_sales_tas`, `sourced_sales_nt`, `sourced_sales_act`
- Each state has its own resume state file (e.g. `.raywhite_qld_state.json`)

#### Re-loading from NDJSON backup (if Supabase upserts failed during extraction)
```bash
python3 replay_nsw_to_sourced.py   # NSW only
# (add equivalent scripts for other states as needed)
```

### Step 3b — McGrath sold listings extraction
McGrath uses Next.js SSR with Cloudflare protection. Requires `curl_cffi` for TLS impersonation. URL seed file (`mcgrath_urls.json`) must be generated from Chrome DevTools — see TRIED-TOOL-01.md for full method. Run once or when re-extracting historical data.
```bash
pip3 install curl_cffi beautifulsoup4
# mcgrath_urls.json must already exist in this folder
nohup caffeinate python3 fetch_mcgrath.py > mcgrath_log.txt 2>&1 &
tail -f mcgrath_log.txt
```
- Tables: `sourced_sales_nsw`, `sourced_sales_vic`, `sourced_sales_qld`, `sourced_sales_tas`
- Resume: `mcgrath_progress.txt` checkpoint file
- Run time: ~3.5 hours (31,495 records, 7,519 skipped)
- One-time historical scrape only — not suitable for weekly automation (no stable API)

### Step 4 — Ray White address matching + enrichment (NSW)
Matches Ray White `sourced_sales_nsw` records against VG `property_sales`. Writes bedrooms/bathrooms/car_spaces.
```bash
python3 enrich_property_sales.py
```
- Writes exact matches directly to `property_sales` (bedrooms, bathrooms, car_spaces, match_confidence='exact')
- Flags probable matches for review (match_confidence='probable', no bedroom data written)
- Cross-links both tables: `property_sales.enriched_source_id` ↔ `sourced_sales_nsw.matched_property_id`
- Review file: `probable_matches_review.json`
- **Performance: uses 20 concurrent threads for PATCH requests via `ThreadPoolExecutor`. Runs in ~5-10 minutes for ~20k matches. This is the right pattern for all future enrichment scripts — do not use sequential PATCHes.**
- **Known gap: concurrent PATCHes occasionally time out, leaving a small % unwritten per run. Script is re-runnable and picks up stragglers via `match_confidence=is.null` filter. TODO: add retry logic (3 attempts with backoff) to each thread so 100% completes in one pass. Required before automating.**

### Step 4b — McGrath address matching + enrichment (NSW)
Same approach as Step 4, adapted for McGrath's address format (street_name includes type).
```bash
python3 match_mcgrath_nsw.py
```
- Date window: 2022–2026 (McGrath data spans further back than Ray White window)
- Deduplication built-in: drops any source_id that matched >1 VG record before writing
- **Always run the dedup verification query after any enrichment run** (see TRIED-TOOL-01.md)
- Review file: `probable_matches_mcgrath.json`
- Results (15 July 2026): 4,947 exact matches

### Step 5 — Review probable matches (manual, periodic)
```bash
# Open probable_matches_review.json / probable_matches_mcgrath.json and spot-check
# Run promote_probables.py (TO BE WRITTEN) to confirm good ones
```

---

## Supabase permissions checklist

### RLS policy (15 July 2026 — RLS now enabled on all tables)
All tables have RLS enabled. New pipeline tables (internal only — sourced_sales_*, etc.) need service_role access but no public policy:
```sql
-- New internal pipeline table
ALTER TABLE your_table ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE ON public.your_table TO service_role;
GRANT USAGE, SELECT ON SEQUENCE your_table_id_seq TO service_role;
-- No CREATE POLICY needed — service_role bypasses RLS automatically
```

New public-read tables (e.g. a new stats table the frontend queries) also need a read policy:
```sql
ALTER TABLE your_table ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, UPDATE ON public.your_table TO service_role;
GRANT USAGE, SELECT ON SEQUENCE your_table_id_seq TO service_role;
CREATE POLICY "public read" ON your_table FOR SELECT USING (true);
```

**Security note:** The publishable anon key is safe to expose in frontend code. The secret key bypasses RLS and must never appear in any committed file — set via `export SUPABASE_SECRET=...` only.

---

## Known issues / gotchas

- **NDJSON files append on each run** — always deduplicate by `source_id` before replaying into Supabase (the replay scripts handle this automatically)
- **Duplicate source_ids within a postcode** — Ray White occasionally returns duplicate records in paginated results. The fetch scripts deduplicate before upserting.
- **Git HEAD.lock conflicts** — if the sandbox and your local git clash, run: `rm .git/HEAD.lock && git stash && git pull --rebase && git stash pop && git push`
- **enrich_property_sales.py is slow** — individual PATCHes, ~150ms each. Needs batch rewrite before weekly automation.
- **VIC scoring** — currently uses NSW price_curves as proxy (estimated). Will be replaced with real individual sale records from sourced_sales_vic once matching is built.
- **One-to-many enrichment false positives** — after every enrichment run, verify no sourced_sales record was written to multiple property_sales rows (common with apartment buildings where address lacks unit number). See dedup query in TRIED-TOOL-01.md McGrath section. This check is now baked into `match_mcgrath_nsw.py` but `enrich_property_sales.py` (Ray White) also needs it added.
- **McGrath Cloudflare** — `mcgrath_urls.json` seed file must be regenerated from Chrome DevTools if sitemaps change. Python requests cannot fetch mcgrath.com.au pages directly.

---

## Future pipeline steps (not yet built)

- [ ] Add LJ Hooker, Raine & Horne, etc. — check each for JSON API vs HTML scraping requirement
- [ ] Add dedup verification query to `enrich_property_sales.py` (Ray White) — same as McGrath version
- [ ] Build VIC/QLD address matching equivalent of `enrich_property_sales.py`
- [ ] Batch-rewrite `enrich_property_sales.py` for speed (individual PATCHes → bulk)
- [ ] Build `promote_probables.py` — review + confirm probable matches
- [ ] Weekly cron job (GitHub Actions) for Steps 3 + 4 combined
- [ ] Incremental extraction — only fetch postcodes with new sales since last run
- [ ] Refresh `mcgrath_urls.json` seed file periodically (new sold listings added to sitemaps over time)

---

## Coverage targets
- **Done (15 July 2026):** Ray White NSW = 9,168 + McGrath NSW = 4,947 → **14,115 total enriched (9.6% of 146,330)**
- **By type:** Houses 12.9% (12,388 / 96,127) · Units 3.4% (1,727 / 50,203)
- **Unit records:** Still structurally hard. Ray White captures zero unit addresses. McGrath does some (1,727 unit matches). Need more sources that include unit numbers.
- **Product rule:** Bedroom/bathroom filtering can only be enabled for house and townhouse property types. Apartment search must hide or disable bedroom filtering until unit-level coverage is adequate.
- **Target:** 80% of suburbs at 80%+ house/townhouse coverage before bedroom filtering goes live
- **Estimate:** Need ~7-8 agencies of Ray White's size to reach target. Currently at ~2 agencies worth.

## Enrichment monitoring
- **Dashboard:** `enrichment-dashboard.html` — open in browser, queries Supabase live via anon key
- **Live URL:** `get-real.co/enrichment-dashboard.html`
- Shows: overall coverage %, by source, by property type, top 25 suburbs, bedrooms distribution
- Auto-refreshes every 5 minutes

---

*Update this file whenever a new source is added, a script changes, or a new gotcha is discovered.*
