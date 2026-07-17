# GetReal — Pipeline Notes

This document covers all data pipelines for GetReal tools: what each pipeline monitors, how it works, what's been built vs. what's planned, and how to refresh each data source manually.

---

## Pipeline status overview

| Pipeline | Table(s) | Initial load | Automated refresh |
|---|---|---|---|
| Stamp duty brackets | `stamp_duty_brackets`, `stamp_duty_concessions`, `nt_duty_formula` | ✓ Done (manual) | ✗ Not built |
| Registration fees | `registration_fees` | ✓ Done (manual, NSW exact / others estimated) | ✗ Not built |
| LMI rates | `lmi_rates`, `lmi_stamp_duty_rates` | ✓ Done (manual) | ✗ Not built |
| HEM benchmarks | `hem_benchmarks` | ✓ Done (manual) | ✗ Not built |
| ABS postcode remoteness | `postcode_locations` | ✓ Done (`load_abs_remoteness.py`) | N/A — refresh every 5 years |
| RBA benchmark rates | `benchmark_rates` | ✓ Done (`fetch_rba_rates.py`) | ✗ Not built |
| VIC quarterly data | `suburb_analytics` | ✓ Done (`load_vic_quarterly.py`) | ✗ Not built |
| NSW enrichment | `sourced_sales_nsw` | ✓ In progress (~12.1%) | ✗ Not built |

**Next milestone:** Build a unified pipeline dashboard (scheduled status + last run + pass/fail + new data flag) covering all rows above.

---

# Stamp Duty Rate Monitor — Pipeline Notes

**Goal:** A GitHub Actions workflow that runs weekly, checks whether any Australian state/territory has changed its stamp duty brackets, and updates the Supabase `stamp_duty_brackets` table if a change is detected.

> ⚠️ **Staleness note (updated July 2026):** This section was originally written when stamp duty values were hardcoded in `deposit.html`. They are now stored in Supabase (`stamp_duty_brackets`, `stamp_duty_concessions`, `nt_duty_formula`). The pipeline must compare scraped values against Supabase — not a local JSON snapshot — and upsert any changes directly to those tables. Alert Tristan whenever a change is detected so the effective_date can be confirmed.

**Goal:** A GitHub Actions workflow that runs weekly, checks whether any Australian state/territory has changed its stamp duty brackets, and alerts Tristan if a change is detected.

---

## What it monitors

The tool stores bracket data hardcoded in `deposit.html` inside the `<script>` block. The pipeline compares current published rates against those hardcoded values and flags any discrepancy.

Eight jurisdictions to check:

| State | Source URL | What to check |
|---|---|---|
| NSW | https://www.revenue.nsw.gov.au/taxes-duties-levies-royalties/transfer-duty | Bracket table, FHB thresholds ($800k/$1M) |
| VIC | https://www.sro.vic.gov.au/land-transfer-duty | General + PPR brackets, FHB thresholds ($600k/$750k) |
| QLD | https://www.qld.gov.au/housing/buying-owning-home/advice-buying-home/transfer-duty | Bracket table, FHB thresholds ($500k/$550k) |
| WA | https://www.wa.gov.au/service/financial-management/taxation/calculate-transfer-duty | Bracket table, FHB thresholds ($430k/$530k) |
| SA | https://www.revenuesa.sa.gov.au/taxes-and-duties/stamp-duties/real-property | Bracket table |
| TAS | https://www.sro.tas.gov.au/duties | Bracket table, FHB 50% discount threshold ($600k) |
| ACT | https://www.revenue.act.gov.au/duties/conveyance-duty | Bracket table, HBCS income threshold (~$160k) |
| NT | https://treasury.nt.gov.au/dtf/territory-revenue-office/stamp-duty | Quadratic formula coefficients, $525k threshold, 4.95% flat rate, FHOD cap ($18,601) |

Cross-reference source: https://auscalcs.com.au/stamp-duty/ — often more parseable HTML than official pages.

---

## What the hardcoded values look like (as of June 2026)

These are the values in `deposit.html` that the pipeline should verify:

### NSW
```
Brackets: 0/0.0125, 16000/0.015, 35000/0.0175, 93000/0.035, 351000/0.045, 1168000/0.055, 3505000/0.07
FHB full exemption: ≤ $800,000
FHB taper top: $1,000,000
```

### VIC General
```
Brackets: 25000/1.4%, 130000/2.4%, 960000/6.0%, 2000000/5.5% FLAT, above/6.5%
```

### VIC PPR (owner-occupier, ≤ $550k)
```
Brackets: 25000/1.4%, 130000/2.4%, 440000/5.0%, 550000/6.0% then reverts to general
FHB full exemption: ≤ $600,000
FHB taper top: $750,000
```

### QLD
```
Brackets: 5000/nil, 75000/1.5%, 540000/3.5%, 1000000/4.5%, above/5.75%
FHB full exemption: ≤ $500,000
FHB taper top: $550,000
```

### WA
```
Brackets: 120000/1.90%, 150000/2.85%, 360000/3.80%, 725000/4.75%, above/5.15%
FHB full exemption: ≤ $430,000
FHB taper top: $530,000
```

### SA
```
Brackets: 12000/1.0%, 30000/2.0%, 50000/3.0%, 100000/3.5%, 200000/4.0%, 250000/4.25%, 300000/4.75%, 500000/5.0%, above/5.5%
```

### TAS
```
Brackets: ≤$3k/$50 flat, 25000/1.75%, 75000/2.25%, 200000/3.5%, 375000/4.0%, 725000/4.25%, above/4.5%
FHB discount: 50% off duty for established homes < $600,000
```

### ACT
```
Brackets: 200000/2.20%, 300000/3.40%, 500000/4.32%, 750000/5.90%, 1000000/6.40%, 1455000/7.20%, above/4.54%
HBCS: income threshold ~$160,000 (singles) — not calculable, advisory note only
```

### NT
```
Formula (≤ $525k): D = 0.06571441 × V² + 15 × V  (where V = price / 1000)
Flat rate (> $525k): 4.95%
FHOD: max discount $18,601, applies < $650,000, phaseout $500k–$650k
```

---

## Approach: what the pipeline actually does

### Option A — Scrape + diff (recommended)
1. Fetch the AusCalcs page for each state (more consistent HTML than official pages)
2. Extract the bracket table using a regex or CSS selector
3. Compare bracket thresholds and rates against a `rates-snapshot.json` file committed in the repo
4. If any value differs → raise a GitHub Issue with a diff, tag it `stamp-duty-alert`
5. Commit updated `rates-snapshot.json` if no changes (updates the "last verified" timestamp)

**Alert format:**
```
Subject: [GetReal] Stamp duty rate change detected — VIC
Body: AusCalcs reports a change in the VIC general bracket table.
      Previous: 960000/6.0%
      Current:  960000/6.5%
      Action needed: Update deposit.html and TOOL-03-SPEC.md
      Source: https://auscalcs.com.au/stamp-duty/vic/
```

### Option B — Email via GitHub Actions + SendGrid/Mailgun
Same detection logic; sends an email instead of (or in addition to) a GitHub Issue.

---

## GitHub Actions workflow structure

```yaml
# .github/workflows/stamp-duty-monitor.yml
name: Stamp Duty Rate Monitor
on:
  schedule:
    - cron: '0 8 * * 1'   # Every Monday 8am UTC (6pm AEST)
  workflow_dispatch:        # Allow manual trigger

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install requests beautifulsoup4
      - run: python scripts/check_stamp_duty_rates.py
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Files to create

- `.github/workflows/stamp-duty-monitor.yml` — workflow definition
- `scripts/check_stamp_duty_rates.py` — scraper + diff script
- `scripts/rates-snapshot.json` — committed baseline rates (update after each confirmed-correct change)

---

## `rates-snapshot.json` structure (to create)

```json
{
  "last_verified": "2026-07-15",
  "source": "AusCalcs (https://auscalcs.com.au/stamp-duty/)",
  "states": {
    "NSW": {
      "brackets": [
        { "min": 0, "max": 16000, "base": 0, "rate": 0.0125 },
        ...
      ],
      "fhb_exempt_threshold": 800000,
      "fhb_taper_top": 1000000
    },
    "VIC": { ... },
    ...
    "NT": {
      "formula_below": 525000,
      "formula_coeff_a": 0.06571441,
      "formula_coeff_b": 15,
      "flat_rate_above": 0.0495,
      "fhod_max_discount": 18601,
      "fhod_threshold": 650000
    }
  }
}
```

---

## Edge cases to handle

- Official pages may be JS-rendered (use AusCalcs as the primary scrape target — it's static HTML)
- The NT formula coefficients are unlikely to change but should be checked
- VIC off-the-plan concession: monitored but not implemented in the tool — note if it changes
- ACT is transitioning away from stamp duty to land tax over 20 years — watch for accelerated changes
- Rate changes typically align with 1 July (start of financial year) — highest-risk period is late June

---

## When to build this

Build as part of the unified pipeline automation sprint — after the initial data loads for all tables are confirmed working. The stamp duty monitor will share the same GitHub Actions pattern as `fetch_rba_rates.py`.

Estimated build time: ~2–3 hours (workflow + scraper script).

---

# RBA Benchmark Rates — Pipeline Notes

**Goal:** Download RBA Table F6 (Housing Lending Rates) monthly and upsert to the `benchmark_rates` Supabase table. Used by the deposit ceiling calculator (deposit.html) for serviceability stress rate calculations.

---

## What it captures

Full matrix from RBA F6 Economic and Financial Statistics (EFS) collection:

| Dimension | Values |
|---|---|
| Purpose | Owner-occupier / Investor |
| Repayment type | P&I / IO |
| Rate type | Variable / Fixed 1yr / Fixed 2yr / Fixed 3yr / Fixed 5yr |
| Loan status | New (funded in month) / Outstanding |
| LVR band | <60% / 60–70% / 70–80% / 80–90% / 90%+ (where published) |
| Loan size band | Tiered bands (where published) |

Not all combinations exist in the data — the RBA publishes what it has. The script handles this gracefully.

**Important context from RBA research:** The RBA notes "there is much less differentiation in average rates by loan size or LVR than you might expect — lenders price LVR risk primarily through LMI, not rate tiers." The data is worth capturing for completeness and future use, but the headline numbers (OO P&I variable new / Investor P&I variable new) do most of the work.

---

## Supabase table

```sql
CREATE TABLE benchmark_rates (
  id              SERIAL PRIMARY KEY,
  source          TEXT NOT NULL DEFAULT 'RBA F6',
  reference_month DATE NOT NULL,
  purpose         TEXT NOT NULL,       -- 'oo' | 'investor'
  repayment_type  TEXT NOT NULL,       -- 'pi' | 'io'
  rate_type       TEXT NOT NULL,       -- 'variable' | 'fixed_1yr' | 'fixed_2yr' | 'fixed_3yr' | 'fixed_5yr' | 'fixed'
  loan_status     TEXT NOT NULL,       -- 'new' | 'outstanding'
  lvr_band        TEXT,                -- '<60%' | '60-70%' | '70-80%' | '80-90%' | '90+%' | NULL (all)
  loan_size_band  TEXT,                -- e.g. '$250k-$500k' | NULL (all)
  rate_pct        NUMERIC(5,2),
  fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (reference_month, purpose, repayment_type, rate_type, loan_status, lvr_band, loan_size_band)
);

CREATE POLICY "Public read" ON benchmark_rates FOR SELECT USING (true);
ALTER TABLE benchmark_rates ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON benchmark_rates TO anon;
```

---

## Script: `fetch_rba_rates.py`

Handles the full load — initial seed and monthly refresh are the same script.

```bash
export SUPABASE_SECRET=<secret>
python3 fetch_rba_rates.py
```

Steps:
1. Downloads F6 CSV from `https://www.rba.gov.au/statistics/tables/csv/f6-data.csv`
2. Parses metadata rows to extract series IDs and descriptions
3. Keyword-matches descriptions to schema fields (purpose/repayment/rate_type/loan_status/LVR/loan_size)
4. Upserts ALL historical months (complete record, not just latest)
5. Prints summary of series matched and latest month's key rates

**If the script prints "No series matched":** The RBA has changed their column descriptions. The script prints all available descriptions — use those to update the keyword maps at the top of the script.

---

## Data source

- **URL:** `https://www.rba.gov.au/statistics/tables/csv/f6-data.csv`
- **Published:** ~5 business days after month end
- **Format:** CSV with ~10 metadata header rows, then monthly data rows (`Jan-2020`, `Feb-2020`, ...)
- **Coverage:** From January 2020 (EFS collection launch)

---

## How the tool uses this

In `deposit.html`, the serviceability stress rate is:

```
stress_rate = benchmark_rate + 3.0%   (APRA buffer, current as of Feb 2026)
```

Query pattern for the tool:
```sql
SELECT rate_pct FROM benchmark_rates
WHERE purpose = 'oo'          -- or 'investor'
  AND repayment_type = 'pi'
  AND rate_type = 'variable'
  AND loan_status = 'new'
  AND lvr_band IS NULL
  AND loan_size_band IS NULL
ORDER BY reference_month DESC
LIMIT 1;
```

The tool displays: *"Stress rate: X.X% (RBA average new variable P&I rate, [Month YYYY] + 3% APRA buffer)"*

---

## Automated refresh

**Schedule:** Monthly — run on the 8th of each month (RBA publishes by the 5th business day).

**GitHub Actions workflow (to build):**
```yaml
# .github/workflows/fetch-rba-rates.yml
name: Fetch RBA Benchmark Rates
on:
  schedule:
    - cron: '0 2 8 * *'   # 8th of each month, 2am UTC (12pm AEST)
  workflow_dispatch:

jobs:
  fetch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install requests supabase
      - run: python3 fetch_rba_rates.py
        env:
          SUPABASE_SECRET: ${{ secrets.SUPABASE_SECRET }}
```

---

## Refresh trigger

Run whenever:
- Monthly automated job fires (handles itself)
- RBA revises historical data (rare — just re-run manually)
- RBA changes column descriptions (update keyword maps in script, re-run)

---

# ABS Postcode Remoteness Data — Pipeline Notes

**Goal:** Populate the `postcode_locations` Supabase table with postcode → metro/regional classifications derived from the ABS Remoteness Structure (ASGS Edition 4).

---

## What this data is

The ABS Australian Statistical Geography Standard (ASGS) Remoteness Structure classifies every SA1 area in Australia into one of five Remoteness Area (RA) categories based on road distance to service centres:

The `location_type` field (metro/regional) is based on **GCCSA (Greater Capital City Statistical Areas)**, not Remoteness Areas. This matches how the Melbourne Institute defines metro for HEM benchmarks — all 8 Australian capital cities are metro:

| GCCSA | Capital | location_type |
|---|---|---|
| 1GSYD | Greater Sydney | metro |
| 2GMEL | Greater Melbourne | metro |
| 3GBRI | Greater Brisbane | metro |
| 4GADE | Greater Adelaide | metro |
| 5GPER | Greater Perth | metro |
| 6GHOB | Greater Hobart | metro |
| 7GDAR | Greater Darwin | metro |
| 8ACTE | Australian Capital Territory | metro |
| 9ROA | Rest of Australia | regional |

The `ra_category` and `ra_name` fields store the ABS Remoteness Area for reference (1=Major Cities through 5=Very Remote). These are kept but not used for HEM classification.

Join chain: Postcode ← MB_CODE → GCCSA_CODE (for location_type) + SA1_CODE → RA_CODE (for ra_category/ra_name).

---

## Data source

- **ABS ASGS Edition 3** (July 2021 – June 2026) — in use now
- Edition 4 release date: **22 July 2026** — refresh on/after 23 July 2026

Three allocation files (all XLSX), joined via Mesh Block:

| File | URL | Columns used |
|---|---|---|
| POA_2021_AUST.xlsx | https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/allocation-files/POA_2021_AUST.xlsx | MB_CODE_2021, POA_CODE_2021 |
| MB_2021_AUST.xlsx | https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/allocation-files/MB_2021_AUST.xlsx | MB_CODE_2021, SA1_CODE_2021, STATE_CODE_2021 |
| RA_2021_AUST.xlsx | https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/allocation-files/RA_2021_AUST.xlsx | SA1_CODE_2021, RA_CODE_2021, RA_NAME_2021 |

Join chain: Postcode ← MB_CODE → SA1_CODE → RA_CODE.
For postcodes spanning multiple RA categories, dominant RA is determined by mesh block count (majority vote).

**Edition 4 refresh:** Update the FILE_URLS dict in `load_abs_remoteness.py` to the Edition 4 equivalents. URL pattern will be identical with `jul2026-jun2031` in the path.

---

## Supabase table

```sql
create table postcode_locations (
  postcode      char(4) primary key,
  state         char(3) not null,
  location_type text    not null,  -- 'metro' or 'regional'
  ra_category   integer not null,  -- 0–4 (ABS RA code)
  ra_name       text    not null   -- e.g. 'Major Cities of Australia'
);

alter table postcode_locations enable row level security;
create policy "Public read" on postcode_locations for select using (true);
```

---

## Script: `load_abs_remoteness.py`

Pattern: same as `load_vic_quarterly.py` — download files, transform, upsert to Supabase.

```bash
export SUPABASE_SECRET=<secret>
python3 load_abs_remoteness.py
```

Steps the script performs:
1. Downloads the three ABS XLSX files (POA, MB, RA) directly from abs.gov.au
2. Joins MB→SA1→RA and MB→POA to get postcode→RA mappings
3. For each postcode, resolves dominant RA by mesh block majority vote
4. Maps RA 0 → 'metro', RA 1–4 → 'regional'
5. Upserts all rows into `postcode_locations` (on conflict → update)

Runtime: ~5–10 min (MB file is 33 MB). Requires `openpyxl` (auto-installed if missing).

---

## Refresh trigger

**Refresh when:** ABS publishes a new ASGS edition (approximately every 5 years, aligned with Census).
- Edition 4: July 2026 – June 2031
- Edition 5: expected ~July 2031

**How to refresh:**
1. Download new correspondence file from ABS
2. Run `python3 load_abs_remoteness.py`
3. No code change required — table is overwritten via upsert

**This does NOT need weekly automated monitoring** — Remoteness Areas change only when a new Census edition is released. Add a calendar reminder for July 2031.

---

## How the tool uses this

When a user enters a postcode (future: auto-detect from suburb selection), the tool fetches `postcode_locations` to determine `location_type`, then uses that to look up the correct HEM benchmark from `hem_benchmarks`. If the postcode is not found (e.g. a new postcode issued after the last ABS release), default to 'metro' and note the uncertainty.
