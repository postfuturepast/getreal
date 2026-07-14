# Data Refresh Runbook

How to update GetReal when new source data is released.

---

## VIC quarterly refresh — AUTOMATED

VIC data is automatically refreshed by GitHub Actions. The workflow runs every Monday —
most weeks it finds nothing new and exits cleanly. When VGV publishes a new quarter,
the next Monday run picks it up automatically.

**You do nothing.** When the workflow runs:
1. It scrapes land.vic.gov.au for the latest median-house and median-unit XLS files
2. Downloads them if they're new
3. Runs `load_vic_quarterly.py` against the Supabase secret
4. Commits the regenerated `suburb-data.json` if it changed
5. Pushes to main → Cloudflare Pages auto-deploys

**Manual trigger** (if you know new data just dropped before the schedule):
→ GitHub → Actions → "Refresh VIC Property Data" → Run workflow

**One-time setup required** (do this once, then forget it):
1. Go to https://github.com/postfuturepast/getreal/settings/secrets/actions
2. Add a new Repository Secret named `SUPABASE_SECRET` with the service role key
   (never store the key anywhere else — never commit it)

**If the automated scraper breaks** (page structure changed):
1. Download the XLS files manually from land.vic.gov.au
2. Put them in this folder, named `median-house-qQ-YYYY.xls` / `median-unit-qQ-YYYY.xls`
3. `export SUPABASE_SECRET=...` then `python3 load_vic_quarterly.py`
4. Commit and push `suburb-data.json`

---

## NSW refresh

NSW individual sale records are published weekly by the NSW Valuer General at:
https://www.valuergeneral.nsw.gov.au/land_values/property_sales_data

New bulk downloads (`.DAT` files) are released as zips. A full refresh is only needed when a significant new batch is available — not weekly.

**Steps:**

1. Download the latest bulk PSI zip from the link above. Extract the `.DAT` files.

2. Run the NSW loader (loads records into the `property_sales` Supabase table):
   ```bash
   export SUPABASE_SECRET=your_secret_key_here
   python3 load_nsw_data.py
   ```

3. After loading new NSW records, refresh the price distribution curves:
   ```bash
   python3 populate_price_curves.py
   ```
   This re-derives the NSW distribution curves used to score VIC suburbs.

4. Regenerate the NSW suburb list for autocomplete:
   ```bash
   python3 generate_nsw_suburbs.py
   ```

5. Commit and deploy:
   ```bash
   git add nsw-suburbs.json
   git commit -m "data: refresh NSW sales data + price curves"
   git push
   ```

---

## Order of operations summary

| Trigger | Scripts to run | Files to commit |
|---|---|---|
| New VIC quarterly XLS | `load_vic_quarterly.py` | `suburb-data.json` |
| New NSW DAT files | `load_nsw_data.py` → `populate_price_curves.py` → `generate_nsw_suburbs.py` | `nsw-suburbs.json` |
| NSW data changed + VIC re-score needed | All of the above | Both files |

---

## Notes

- `SUPABASE_SECRET` is the service role key — never commit it or share it in chat. Store it in your shell profile or a `.env` file (not checked in).
- The publishable/anon key (`sb_publishable_1jyBD0hVdHX2ieqFIlC51A_A3ep39Bc`) is safe to use in the frontend and in `generate_nsw_suburbs.py`. The secret key is only needed for the write pipelines.
- Cloudflare Pages auto-deploys on push to `main`. Allow 1–2 minutes after push before testing.
