# Data Refresh Runbook

How to update GetReal when new source data is released.

---

## VIC quarterly refresh

New VIC data is released by the Victorian Valuer General each quarter (roughly Jan, Apr, Jul, Oct) at:
https://www.land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics

**What to download:**
- Median house prices by suburb (XLS)
- Median unit prices by suburb (XLS)

**Steps:**

1. Download the two new XLS files from the link above.

2. Rename them to match the pattern in `load_vic_quarterly.py` — update the `FILES` list at the top of the script if the quarter has changed:
   ```python
   FILES = [
       ("median-house-q1-2026.xls", "house"),
       ("median-unit-q1-2026.xls",  "apartment"),
   ]
   ```
   Also update `data_year` and `data_period` strings near the bottom of `main()`.

3. Place the XLS files in the same folder as the script.

4. Run the pipeline:
   ```bash
   export SUPABASE_SECRET=your_secret_key_here
   python3 load_vic_quarterly.py
   ```

5. Commit and deploy the regenerated `suburb-data.json`:
   ```bash
   git add suburb-data.json
   git commit -m "data: refresh VIC data to Q1 2026"
   git push
   ```

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
