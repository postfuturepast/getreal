# GetReal — Australian Property Tools

Free, independent tools to help Australians assess whether their property search is realistic. No spin. No vested interests. Built on open government data.

**Live at [get-real.co](https://get-real.co)**

---

## Tools

- **[Buying Ceiling Calculator](https://get-real.co/deposit)** — Find your maximum purchase price under three constraints: deposit floor, DTI cap, and serviceability stress test.
- **[Property Realism Checker](https://get-real.co/search)** — See what share of a suburb's actual sold properties fall within your budget.
- **[Stamp Duty Calculator](https://get-real.co/stamp-duty)** — All 8 states and territories, FHB concessions included.

---

## API

The full calculation engine is available as a free HTTP API — no authentication required.

**Base URL:** `https://get-real.co/api/v1/`

**15 endpoints across three groups:**

| Group | Endpoints |
|---|---|
| Stamp Duty & Costs | `stamp-duty`, `lmi`, `repayments` |
| Ceiling Calculator | `ceiling/deposit`, `ceiling/deposit/min-income`, `ceiling/dti`, `ceiling/serviceability`, `ceiling/all`, `ceiling/check`, `ceiling/deposit/sensitivity` |
| Realism Score | `score`, `score/batch`, `score/budget-for-score`, `score/suburbs-in-range`, `score/ceiling` |

**Quick example:**
```bash
# NSW FHB stamp duty on $750k
curl "https://get-real.co/api/v1/stamp-duty?state=NSW&price=750000&buyer_type=fhb"

# Suburb realism score
curl "https://get-real.co/api/v1/score?suburb=fitzroy&state=VIC&property_type=house&budget=1200000"
```

- [Developer hub](https://get-real.co/developer.html) — overview, examples, data sources
- [Full API reference](https://get-real.co/api-docs.html) — interactive Redoc docs
- [OpenAPI spec](https://get-real.co/openapi.json) — OpenAPI 3.1

---

## Data Sources

- **NSW:** 146,000+ individual sale records from the NSW Valuer General (bulk PSI download)
- **VIC:** Suburb-level median prices and annual sales from the Victorian Valuer General quarterly reports (Q4 2025)
- **Stamp duty:** All state revenue offices, stored in versioned Supabase lookup tables
- **LMI rates:** Home Loan Experts indicative table (May 2026)
- **HEM benchmarks:** JMD Mortgages (March 2026)
- **Serviceability buffer:** 3% above benchmark rate, per APRA APG 223

---

## Stack

- **Frontend:** Static HTML/CSS/JS, deployed on Cloudflare Pages
- **API:** Cloudflare Pages Functions (single catch-all function)
- **Database:** Supabase (PostgreSQL) — property sales, suburb analytics, lookup tables
- **Pipeline:** Python scripts + GitHub Actions for weekly data refresh

---

## Disclaimer

GetReal is a best-efforts side project, not a licensed financial service. Results are indicative only. Always verify with a licensed mortgage broker before making property decisions.
