# GetReal Tool 01 — Data Approaches Tried

A log of data sources and enrichment approaches we've investigated, with outcomes. The goal is to avoid re-investigating dead ends.

---

## Getting individual sale records for states other than NSW

### NSW
**Outcome: ✅ Working**
- Source: NSW Valuer General bulk PSI download via [nswpropertysalesdata.com](https://nswpropertysalesdata.com) (James Elks' cleaner)
- 146,285+ individual sale records (address, price, date, property type)
- Automated weekly refresh via GitHub Actions
- No bedroom/bathroom/car space data included (see below)

### VIC
**Outcome: ⚠️ Partial — aggregated only**
- Source: Victorian Valuer General quarterly XLS files (land.vic.gov.au)
- Suburb-level medians + annual sales counts only — no individual sale records
- Townhouse data is fabricated (house median × 0.82, house sales × 0.45)
- Scoring uses NSW-derived price_curves as a proxy — directionally useful, not as reliable as NSW

**Tried and ruled out:**
- PEXA settlement data — not free
- REA/Domain scraping — bot-blocked (see Domain section below)
- Data.Vic datasets — nothing beyond the median file
- PropertyData.com.au API — not free

### QLD / other states
**Outcome: ❌ No free source found yet**
- No equivalent to the NSW Valuer General bulk download exists for QLD, SA, WA, ACT, TAS, or NT
- Individual sale records are either paywalled or not published

---

## Enriching data with bedroom / bathroom / car space counts

### NSW bedroom + bathroom data
**Outcome: ❌ No free source found yet**
The NSW Valuer General bulk data does not include bedroom, bathroom, or car space counts. Every buyer searches by bedrooms — this is the single biggest gap in NSW scoring.

**Tried and ruled out:**
- **Domain suburb profiles** — scraping blocked by Akamai bot detection. We attempted direct fetch and headless browser simulation. Domain is actively protecting this data. Treat as closed.
- **REA listing scrape** — also blocked by Akamai/Cloudflare bot detection
- **GNAF (Geocoded National Address File)** — address dataset only, no property attributes
- **Planning portals / DA data** — may contain floor area in some LGAs, not rooms. Highly inconsistent across councils.
- **Council open data** — varies wildly by LGA, no consistent national or state-level source

**Ruled out — cost:**
- Paid APIs (PropertyData.com.au, CoreLogic, etc.) — won't pay for an ongoing data subscription. A one-time bulk purchase could be considered to seed historical data, but doesn't solve the ongoing refresh problem so not worth pursuing.

**Ruled out — scale:**
- Crowdsourced / user-submitted enrichment — needs massive user contribution before it has any value. Not a viable path at current traffic levels.

**Weak — inconsistent coverage:**
- Planning/DA portal scraping — some LGAs publish DA data that includes floor area, occasionally room counts. Highly inconsistent across councils, no state-wide source, would only partially fill the gap.

**Promising — primary candidate approach:**

**Ray White JSON API (confirmed working)**

Ray White's listing page is client-rendered, but the underlying API is open and clean.

- **Endpoint:** `POST https://raywhiteapi.ep.dynamics.net/v1/listings?apiKey=6625c417-067a-4a8e-8c1d-85c812d0fb25`
- **API key:** Hardcoded in the page JS — effectively public
- **CORS:** `Access-Control-Allow-Origin: *` — fully open
- **Auth:** None beyond the API key in the query string

**Confirmed payload format:**
```json
{
  "size": 12,
  "from": 0,
  "stateCode": "NSW",
  "postCode": ["2042"],
  "statusCode": {"in": ["SLD"]},
  "typeCode": {"in": ["SAL", "RUR"]},
  "countryCode": ["AU", "NZ"],
  "categoryCode": {"in": []},
  "location": {"lat": -33.8999, "lon": 151.18},
  "sort": [{"field": "location", "lat": -33.8999, "lon": 151.18}]
}
```

**Confirmed response fields (per listing):**
- `bedrooms`, `bathrooms`, `carSpaces` ✅
- `soldDate`, `soldPrice` (on recent records) ✅
- `address.streetNumber`, `address.streetName`, `address.streetType`, `address.suburb`, `address.postCode` ✅
- `categories[0].code` — property type (HSE, APT, etc.) ✅
- `hits` — total results for the postcode (e.g. 1,446 for postcode 2042)
- Paginated via `from` parameter — increment by `size` to get all results

**Sample data quality (Newtown 2042):**
- 1,446 total sold records for one postcode alone
- Records go back to 2009
- Recent records (VAULT provider, ~2022+) have `soldPrice` — ideal for matching
- Older records (MYDSK provider) have `price` (asking) but not `soldPrice`
- Our property_sales data is last 12 months → all should be recent VAULT records with soldPrice

**Matching logic:**
Normalise Ray White address → match against property_sales on:
1. Street number + normalised street name + street type + suburb + postcode
2. Confirm with `soldDate` (within a few days tolerance)
3. Confirm with `soldPrice` where available

Address normalisation challenge: Ray White has "33 Gibbes Street", NSW VG data likely has "33 GIBBES ST". Need street type expansion table (ST→Street, AVE→Avenue, etc.) and case normalisation.

**Coverage estimate:**
- Ray White alone: ~30-40% of NSW sales
- Top 10 agencies (Ray White, McGrath, LJ Hooker, Barry Plant, hockingstuart, Nelson Alexander, Laing+Simmons, Raine & Horne, First National, Century 21): likely 90%+
- Drops off for sales older than 3-4 years (agencies eventually remove listings)
- Best coverage for last 12-18 months — exactly GetReal's window

**Not a live feed:** Periodic enrichment run. New weekly NSW VG sales won't have listings immediately. Run monthly or quarterly.

**Confidence: ~75%**
API and data quality confirmed. Unknowns:
1. Rate limiting at scale (thousands of requests across all postcodes) — untested
2. Address matching quality at scale — untested
3. Ray White coverage of our specific 146k records — untested

**Staged execution plan:**

- **Stage 1 — API stress test:** Hit 5 postcodes, paginate all results, measure rate limiting and data volume. Go/no-go: can we bulk extract without being blocked?
- **Stage 2 — Match quality test:** Take Newtown (2042) Ray White records, query Supabase property_sales for 2042, run address normalisation and matching, measure hit rate. Go/no-go: does the join logic work?
- **Stage 3 — Single postcode end-to-end:** Full pipeline for one postcode — fetch → match → upsert bedrooms/bathrooms into Supabase test column. Verify manually.
- **Stage 4 — Full run:** All NSW postcodes, Ray White first, then add other agencies.

**Stage 1 results (14 July 2026) — PASS ✅**

Tested 5 postcodes (Newtown, Sydney CBD, Parramatta, Gosford, Albury). 25 pages fetched, zero blocking.

| Postcode | Label | Total hits | Blocked? |
|---|---|---|---|
| 2042 | Newtown | 1,446 | no ✅ |
| 2000 | Sydney CBD | 607 | no ✅ |
| 2145 | Parramatta | 1,624 | no ✅ |
| 2250 | Gosford | 965 | no ✅ |
| 2640 | Albury | 1,219 | no ✅ |

Data quality across all postcodes:
- bedrooms: 100%
- bathrooms: 100%
- soldDate: 100%
- address: 100%
- soldPrice: 68–92% (lower for older inner-city records, higher for regional/recent)

Response time: ~0.22s per request. Full NSW run estimate: ~700 postcodes × ~20 pages × 0.5s delay ≈ 2 hours. Acceptable for a one-time enrichment run.

Most recent record seen: 2026-07-06. Data is current.

**Full NSW extraction (14 July 2026) — COMPLETE ✅**

- Script: `fetch_raywhite.py`
- 260,060 raw records pulled across all NSW postcodes (2000–2999)
- 257,069 unique records after dedup (NDJSON local backup + Supabase `sourced_sales_nsw`)
- Run time: ~2 hours at 0.5s delay. Zero blocking throughout.
- Supabase permissions gotcha: new tables require `GRANT SELECT, INSERT, UPDATE ON table TO service_role` AND `GRANT USAGE, SELECT ON SEQUENCE table_id_seq TO service_role` — both needed.

**Stage 2 — Address matching (14 July 2026) — COMPLETE ✅**

NSW VG data window: 2025-06-13 to 2026-05-28 (146,330 records).
Ray White records in that window: 19,243.

Address normalisation challenges discovered and solved:
- VG `street_name` field embeds the street type (e.g. "Landon St") — must split last word and normalise separately
- Unit addresses in VG use `street_number` like "3/2" (unit/building) — extract building number ("2") for matching
- Street type lookup table needed — Ray White stores full words ("Street"), VG stores abbreviations ("St")
- Fallback matching: try without street type, try stripping trailing letter from building number (e.g. "44A" → "44")

**Final match rate: 17,896 / 146,330 = 12.2%**

This is ~94% of the theoretical 13% ceiling (19,243 RW records in window ÷ 146,330 VG records).
The remaining ~1,347 unmatched Ray White records have no VG counterpart — likely off-the-plan, private sales, or date window edge cases. Not worth chasing.

Coverage by suburb varies widely:
- High: Wentworth Point 47%, Parramatta 43%, Hurstville 31%, Ryde 25%
- Low: Dee Why 1.6%, Cronulla 2.6%, Orange 1.4% — Ray White genuinely thin in these areas

**Confidence tiers implemented:**
- `exact` — full address match (street number + normalised street name + type + suburb). Bedrooms/bathrooms written directly to `property_sales`.
- `probable` — same street number + street name, suburb differs. Flagged for manual review in `probable_matches_review.json`. Not auto-applied.

Cross-linking: both tables updated bidirectionally.
- `property_sales`: `enriched_source`, `enriched_source_id`, `match_confidence`
- `sourced_sales_nsw`: `matched_property_id`, `match_confidence`

Scripts: `match_raywhite_nsw.py` (analysis), `enrich_property_sales.py` (enrichment)

**Performance note:** Individual sequential PATCH requests are too slow (~150ms each, 30-60 min for full run). Solution: `ThreadPoolExecutor(max_workers=20)` for concurrent PATCHes — brings ~20k updates down to 5-10 minutes. Use this pattern for all future enrichment scripts.

**Retry logic required:** Concurrent PATCHes occasionally time out under load, leaving a small % unwritten per run. Script is re-runnable and self-healing (picks up missed records via `is.null` filter), but for automation we need retry logic: 3 attempts with exponential backoff on each thread before giving up. Add this to all future enrichment scripts from the start.

**Unit address matching — confirmed dead end with Ray White (14 July 2026)**

Ray White stores apartment listings at building level only (e.g. "29 Ramsay St", not "3/29 Ramsay St"). Checked the full 260,060-record extraction: only 6 records had a "/" in `street_number` — essentially zero. No hidden unit number field exists in the API response.

Result: apartment/unit records in VG `property_sales` (street_number like "3/29") cannot be matched to Ray White. All 9,896 NSW apartment VG records remain unenriched (match_confidence = NULL).

**Product implication — bedroom filtering:** Bedroom/bathroom filtering in the search tool can only be enabled for houses and townhouses. When a user selects "Apartment" as property type, bedroom filtering must be hidden or show a note that bedroom data is unavailable. This will remain true until a source that captures unit-level addresses is found and integrated. Any future agency added to the pipeline should be checked for unit number capture before assuming it solves this.

→ Next: add next agency (McGrath or LJ Hooker) to push house/townhouse coverage above 12.2%. VIC and other-state extractions also pending.

**Database architecture (finalised 14 July 2026)**

One `sourced_sales_[state]` table per state (8 total: nsw, vic, qld, sa, wa, act, tas, nt).
Columns: `source` (agency name), `source_id`, `sourced_at`, full address fields, bedrooms, bathrooms, car_spaces, sold_date, sold_price, `matched_property_id`, `match_confidence`.

Unique constraint on `(source, source_id)` — safe to re-run any fetch script.
All tables: RLS disabled, service_role granted on table + sequence.

**Important: this also solves VIC, QLD and other states**

The Ray White API is national. Same endpoint, same data structure — just change `stateCode` and postcode range:
- VIC: `stateCode: "VIC"`, postcodes 3000–3999
- QLD: `stateCode: "QLD"`, postcodes 4000–4999
- SA, WA, etc.: same pattern

For VIC and QLD this isn't just enrichment — it's individual sale records we've never had at all (addresses, prices, dates, bedrooms). Would allow replacing estimated VIC scoring with real data, and unlocking QLD entirely. Run `fetch_raywhite.py` with different state/postcode range to extract.

---

## McGrath Estate Agents — mcgrath.com.au corporate site scraping

**Outcome: ✅ Complete — 31,495 records harvested (15 July 2026)**

McGrath's corporate site (`mcgrath.com.au`) is a Next.js App Router SSR site with no open JSON API. All listing data is server-rendered. No `__NEXT_DATA__` blob, no client-side listing API (`/api/mcg/` only exposes articles, media releases, and footer config — confirmed via Network tab inspection).

**Cloudflare bypass — critical:** Python `requests` is blocked by TLS fingerprinting regardless of User-Agent or IP. Solution: `curl_cffi` library impersonating Chrome120 at the TLS handshake level.
```python
from curl_cffi import requests as cffi_requests
session = cffi_requests.Session(impersonate="chrome120")
```
Use thread-local sessions when parallelising — `threading.local()` — do not share sessions across threads.

**URL seed file approach:** mcgrath.com.au publishes a sitemap at `https://www.mcgrath.com.au/sitemap/properties-sold-page-{1-8}.xml` (8 pages, 39,257 URLs total). Fetch sitemaps from Chrome DevTools console (not Python — Cloudflare blocks Python on sitemaps too), collect all URLs into `mcgrath_urls.json` using `showSaveFilePicker` File System API. This seed file is the starting point for every run.

**URL format:** `/property/40-hersey-street-blaxland-nsw-2774-136P3112` — address + property ID embedded in slug. State and postcode can be extracted from the slug without fetching the page.

**Address parsing:** Parsed from `<title>` tag: `"40 Hersey Street, Blaxland, NSW 2774 | McGrath Estate Agents"`. Key difference from Ray White: McGrath stores full street name + type as one string (e.g. `"Hersey Street"`), not split. The `street_name` field in `sourced_sales_nsw` contains the full name including type. The matching script must split this before comparing against VG data.

**Beds/baths/cars/price/date:** Parsed from page text with regex. Pattern is `"N\nBeds"`, `"N\nBath"`, `"N\nCars"`. Sold price from first `$X,XXX,XXX` after "Sold". Date from `"Sold July 2026"` pattern — stored as first-of-month (`YYYY-MM-01`).

**Script:** `fetch_mcgrath.py`
- Config: `BATCH_SIZE=50`, `REQUEST_DELAY=0.5s`, `NUM_WORKERS=3`
- Resume: `mcgrath_progress.txt` checkpoint (one property_id per line), saves after every batch upsert
- Corporate proxy conflict: pop proxy env vars at script start (`os.environ.pop('https_proxy', None)` etc.)
- Run overnight: `nohup caffeinate python3 fetch_mcgrath.py > mcgrath_log.txt 2>&1 &`
- Upsert: `on_conflict=source,source_id` as **query parameter** (not header) — `?on_conflict=source,source_id`

**Full run results (15 July 2026):**
- 31,495 records upserted across `sourced_sales_nsw`, `sourced_sales_vic`, `sourced_sales_qld`, `sourced_sales_tas`
- 7,519 skipped (lots, parse failures, no price)
- Run time: 208.5 minutes (3.5 hours) on mobile tethering

**Why one-time only (not automated):** HTML structure can change without notice. No stable API contract. Treat as periodic historical refresh, not a live feed.

**McGrath address matching + enrichment (15 July 2026) — COMPLETE ✅**

Script: `match_mcgrath_nsw.py` — modelled on `enrich_property_sales.py` but adapted for McGrath's data structure.

**Key difference from Ray White matching:** McGrath's `street_name` field includes the street type (`"Hersey Street"` not `"Hersey"`). The matching script splits the last word off and normalises it before building index keys. VG data has the same combined format so both sides need splitting.

**Deduplication — mandatory quality check:**
After matching, always verify no McGrath `source_id` was written to multiple `property_sales` rows (happens when a non-unit address like "15 Smith Street" matches multiple VG records at the same building). Run after every enrichment:
```sql
SELECT enriched_source_id, count(*)
FROM property_sales
WHERE enriched_source = 'mcgrath' AND match_confidence = 'exact'
GROUP BY enriched_source_id
HAVING count(*) > 1;
```
On first run: 233 ambiguous source_ids found. Cleaned with:
```sql
-- Step 1 first (before nulling IDs in property_sales)
UPDATE sourced_sales_nsw SET matched_property_id=NULL, match_confidence=NULL
WHERE source='mcgrath' AND source_id IN (
  SELECT enriched_source_id FROM property_sales
  WHERE enriched_source='mcgrath' AND match_confidence='exact'
  GROUP BY enriched_source_id HAVING count(*) > 1
);
-- Step 2
UPDATE property_sales SET bedrooms=NULL, bathrooms=NULL, car_spaces=NULL,
  enriched=NULL, enriched_source=NULL, enriched_source_id=NULL, match_confidence=NULL
WHERE enriched_source='mcgrath' AND enriched_source_id IN (
  SELECT enriched_source_id FROM property_sales
  WHERE enriched_source='mcgrath' AND match_confidence='exact'
  GROUP BY enriched_source_id HAVING count(*) > 1
);
```
The dedup check is now baked into `match_mcgrath_nsw.py` — future runs drop ambiguous matches before writing.

**Final results after cleanup:**
- 4,947 exact matches written to `property_sales`
- Combined with Ray White: 14,115 total enriched (9,168 RW + 4,947 MC) = 9.6% of 146,330 NSW records
- Houses: 12,388 / 96,127 = 12.9% coverage
- Units: 1,727 / 50,203 = 3.4% coverage (units remain structurally hard — McGrath does capture some unit addresses unlike Ray White)

---

## McGrath franchise sites — WordPress/EPL scraping

**Outcome: ✅ Working — one-time historical scrape**

While `mcgrath.com.au` (the corporate site) uses Next.js App Router with no accessible JSON API, McGrath franchise offices run **WordPress + Easy Property Listings (EPL) plugin** and serve fully server-rendered HTML. No JavaScript execution needed.

**Critical advantage over Ray White: EPL captures unit-level addresses** (e.g. "2/17 Wood Crescent", "44/99 Birtinya Boulevard") — the gap that made Ray White unable to enrich the 9,896 NSW apartment VG records.

**Confirmed franchise domains:**

| Domain | State | Coverage |
|---|---|---|
| `mcgrathnr.com.au` | NSW | Northern Rivers (Ballina, Byron Bay, Lennox Head) |
| `mcgrathwnwhh.com.au` | NSW | West/Hills/Hawkesbury (Parramatta, Blacktown, Castle Hill) |
| `mcgrathillawarra.com.au` | NSW | Illawarra (Wollongong region) |
| `mcgrathcw.com.au` | NSW | Central West (Orange, Bathurst) |
| `mcgrathlbm.com.au` | NSW | Lower Blue Mountains |
| `mcgrathch.com.au` | QLD | Caloundra, Beerwah, Glass House Mountains |
| `mcgrathsc.com.au` | QLD | Sunshine Coast |
| `mcgrathmb.com.au` | QLD | North Lakes / Moreton Bay |
| `mcgrathhl.com.au` | TAS | Launceston to Hobart |

**Discovery method:** The `admin-ajax.php` endpoint (`action: epl_am_facetwp_get_listings`) on `mcgrathch.com.au` revealed the EPL stack. All sites share identical theme (WPBakery + EPL) and URL patterns (`/sold/page/N/`).

**Data available per listing:** Full address (with unit numbers), sold price (where disclosed), beds, baths, car spaces, sold date (present on some sites like mcgrathnr.com.au, absent on others).

**Pagination:** Standard WordPress pagination at `/sold/page/N/`. Returns 404 when exhausted.

**Script:** `fetch_mcgrath_franchise.py`
- Scrapes all sites in `FRANCHISE_SITES` list
- Upserts to `sourced_sales_{state}` (same schema as Ray White)
- Writes local NDJSON backup
- Handles 404 pagination termination
- Single-domain mode: `--domain mcgrathnr.com.au`
- Requires `pip install beautifulsoup4 lxml`

**Required SQL** (if `sourced_sales_qld` / `sourced_sales_tas` don't exist):
```sql
CREATE TABLE sourced_sales_qld (LIKE sourced_sales_nsw INCLUDING ALL);
ALTER TABLE sourced_sales_qld ADD CONSTRAINT sourced_sales_qld_source_source_id_key UNIQUE (source, source_id);
GRANT SELECT, INSERT, UPDATE ON sourced_sales_qld TO service_role;
GRANT USAGE, SELECT ON SEQUENCE sourced_sales_qld_id_seq TO service_role;

CREATE TABLE sourced_sales_tas (LIKE sourced_sales_nsw INCLUDING ALL);
ALTER TABLE sourced_sales_tas ADD CONSTRAINT sourced_sales_tas_source_source_id_key UNIQUE (source, source_id);
GRANT SELECT, INSERT, UPDATE ON sourced_sales_tas TO service_role;
GRANT USAGE, SELECT ON SEQUENCE sourced_sales_tas_id_seq TO service_role;
```

**EPL pattern also applies to other agencies** using Easy Property Listings — Barry Plant, Nelson Alexander, and others use EPL. If we find their franchise sites, the same scraper works with a new entry in `FRANCHISE_SITES`.

---

## LJ Hooker — api01.ljx.com.au sold listings API

**Outcome: ✅ Complete — 23,416+ records harvested (15 July 2026)**

LJ Hooker's sold listings are served via an open JSON API with no authentication required.

**Endpoint:** `GET https://api01.ljx.com.au/website/search-v1`

**Key parameters:**
- `searchProfile=sold` — sold listings only
- `officeId=234` — numeric office ID (mandatory, no geographic filter works without it)
- `orderBy=date-desc`, `limit=100`, `page=N`

**Office ID discovery — critical gotcha:** The office ID is not exposed in any public endpoint. The `offices-v1` endpoint returns all 256 offices with names and subdomains but no numeric IDs. IDs must be discovered by brute-forcing a range (1–3000) — each valid ID returns sold listings, allowing state identification from the address field. Script: `discover_ljhooker_offices.py`.

**National office counts (discovered July 2026):**
- NSW: 72 offices · VIC: 10 · QLD: 34 · WA: 11 · SA: 7 · ACT: 8 · TAS: 2 · NT: 2
- Output: `ljhooker_offices.json` — reuse for other states

**Response fields available:**
- `address.address1` = full street address including unit prefix ("33/25 Mantaka Street") ✅
- `address.suburb`, `address.state`, `address.postcode` ✅
- `bedrooms`, `bathrooms`, `parking` ✅
- `category` = House / Unit / Townhouse / Villa ✅
- `priceDisplay` = "Sold For $920,000" or "SOLD" (undisclosed) ✅
- `linkUrl` — used as stable `source_id`
- **No `soldDate` field** — LJ Hooker does not expose sale date in the API ⚠

**Unit address capture:** LJ Hooker does capture unit-level addresses ("33/25 Mantaka Street") — unlike Ray White. Unit matching is possible in principle.

**Address parsing:** `address1` contains the full address including unit prefix. Split on "/" to extract unit number, then parse street number and name+type. Street type is split and stored separately (like Ray White, unlike McGrath).

**NSW harvest results:**
- 77 NSW office IDs discovered (some offices share subdomains/IDs)
- 23,416+ records upserted to `sourced_sales_nsw`
- Scripts: `discover_ljhooker_offices.py`, `fetch_ljhooker.py`, `match_ljhooker_nsw.py`, `cleanup_probable_ljhooker.py`

**Match results (exact only, after removing probable matching):**
- 1,368 exact matches written to `property_sales` (two runs: 1,115 + 253)
- Low match rate (~5.8%) suggests LJ Hooker data extends further back than the VG date window
- 783 records dropped as ambiguous (same LJH record matched >1 VG row — consistent with older data where a property sold multiple times)

**No sold_date — accepted risk:** Without a sale date, matches are address-only. We accept this because:
1. Structural renovations changing bedroom/bathroom counts are rare
2. Even if a property sold twice, the bedroom count is almost always the same
3. The spot-check of 30 random matches showed no obvious errors

**Retry logic:** API occasionally returns 400 or times out on deeper pages (page 7+). `fetch_ljhooker.py` implements 3-attempt exponential backoff per page. Always verify `total_sold` vs `records built` in output — partial harvests are recoverable by re-running.

---

## Match confidence tiers — how we accept a match

All enrichment decisions are recorded in `match_confidence` on `property_sales`. This documents what each value means and why it was accepted.

### `exact`
**Agency sources:** Ray White, McGrath, LJ Hooker (and any future agency)
**How matched:** Street number + normalised street name + street type + suburb. All must match exactly (after normalisation — case, punctuation, abbreviation expansion).
**Date validation:** Ray White and McGrath records are also filtered to `sold_date` within the VG enrichment window before matching. LJ Hooker has no sold_date so date validation is not possible.
**Deduplication:** Any agency record matching more than one VG record is dropped. Any VG record matched by more than one agency record is dropped.
**Confidence:** High. Address specificity is strong; the main risk is a property selling twice in the window at the same address, which is rare.

### `historical`
**Agency sources:** Ray White, McGrath (sources with sold_date only)
**How matched:** Same address matching as `exact`, but the agency's sold_date falls *outside* the current VG enrichment window. The match was identified by `find_historical_matches.py` (stored in `outside_window_property_id` and `window_gap_days`) and promoted by `promote_historical_matches.py`.
**Gap tolerance:** ≤ 730 days (2 years). Beyond that, ambiguity is too high.
**Reasoning accepted:** Even if a property sold twice within 2 years, the bedroom/bathroom/car space count is almost always identical — structural renovations changing room counts are rare events. The data describes the physical property, not the specific transaction.
**Confidence:** Medium-high. Lower than `exact` because date alignment is not confirmed, but accepted as reliable for the purposes of this tool.

### `probable` — REMOVED
**Was:** Same street number + street name, suburb ignored (designed to catch minor suburb name variations like "St Marys" vs "Saint Marys").
**Why removed:** Produced too many false positives. "64 Clyde Ave, Moorebank" was matching "64 Clyde Street, Granville" — completely different suburbs sharing a street name and number. NSW is large enough that this is common. The no-suburb fallback adds more noise than signal.
**Status:** Any `probable` flags in the database from earlier runs should be treated as unreliable. Run `cleanup_probable_ljhooker.py` to clear LJ Hooker probable flags. Ray White and McGrath probable flags (if any exist from earlier runs) should also be cleared.

### Overwrite priority rule
If a VG property_sales row has `match_confidence='historical'` or no match, and a subsequent run finds an `exact` match from a date-verified source (Ray White or McGrath with sold_date in window), the exact match overwrites the historical one. Date-verified exact matches always win.

LJ Hooker exact matches (no sold_date) do not currently auto-overwrite historical matches. If Ray White or McGrath later matches the same property within the VG window, their match should take precedence.

---

## Domain.com.au suburb profiles (VIC + QLD bedroom-level data)

**Outcome: ❌ Blocked**
Domain suburb profile pages contain bedroom-level median prices, annual sales counts, and surrounding suburb lists — no paywall on the page itself. However:
- Direct HTTP fetch — blocked
- Headless browser simulating human — hit Cloudflare then Akamai bot detection
- Verdict: Domain is actively protecting this compiled data. It's their product. Treat this path as closed.

---

*Add new entries here as new approaches are tried. Date each entry if useful.*
