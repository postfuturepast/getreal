# Stamp Duty Rate Monitor — Pipeline Notes

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

Build immediately after `deposit.html` is live and validated. This is the "professional side project" pattern Tristan wants — the tool works AND has best-effort automated maintenance.

Estimated build time: ~2–3 hours (workflow + scraper script + snapshot file).
