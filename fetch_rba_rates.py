#!/usr/bin/env python3
from __future__ import annotations
"""
fetch_rba_rates.py — Download RBA Table F6 (Housing Lending Rates) and upsert to Supabase.

Usage:
    export SUPABASE_SECRET=<secret>
    python3 fetch_rba_rates.py

What it does:
    1. Downloads the RBA F6 CSV from rba.gov.au
    2. Parses all rate series (purpose × repayment × rate type × loan status × LVR band × loan size)
    3. Upserts every series into the benchmark_rates Supabase table
    4. Prints a summary of what was loaded

Run this once manually to seed the table.
The same script is used by GitHub Actions monthly (RBA publishes ~5 business days after month end).

RBA F6 actual CSV format (confirmed July 2026):
    Row 0:  ['F6 - HOUSING LENDING RATES']
    Row 1:  ['Title', desc1, desc2, ...]
    Row 2:  ['Description', desc1, desc2, ...]
    Row 3:  ['Frequency', 'Monthly', ...]
    Row 4:  ['Type', 'Original', ...]
    Row 5:  ['Units', 'Per cent per annum', ...]
    Row 6:  []
    Row 7:  []
    Row 8:  ['Source', 'APRA, RBA', ...]
    Row 9:  ['Publication date', 'DD-Mon-YYYY', ...]
    Row 10: ['Series ID', 'FLRHOOTL', 'FLRHOOTA', ...]
    Row 11+: ['DD/MM/YYYY', val1, val2, ...]

    Description format: semicolon-separated segments, e.g.:
    "Lending rates; Housing credit; New loans funded in the month; Owner-occupied; Variable-rate; All institutions"
    "Lending rates; Housing credit; New loans funded in the month; Owner-occupied; By loan-to-valuation ratio at commitment; Less than 81%"
    "Lending rates; Housing credit; New loans funded in the month; Owner-occupied; By repayment type; Interest-only"
"""

import os
import sys
import csv
import io
import requests
from datetime import datetime, date
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ.get("SUPABASE_SECRET")

RBA_F6_CSV_URL = "https://www.rba.gov.au/statistics/tables/csv/f6-data.csv"


# ── Description parser ────────────────────────────────────────────────────────

def parse_description(series_id: str, description: str) -> dict | None:
    """
    Parse an RBA F6 series description into benchmark_rates schema fields.

    Descriptions are semicolon-separated segments. We parse segment-by-segment
    rather than using regex across the full string, which is more robust to
    RBA wording changes.

    Returns None for series we don't want to store (non-housing, large-institution-only).
    """
    # Split into lowercase segments for matching
    raw_segs = [s.strip() for s in description.split(";")]
    segs = [s.lower() for s in raw_segs]

    # Must be a housing lending rate
    if not any("housing credit" in s or "lending rates" in s for s in segs):
        return None

    # Skip "Large institutions" — "All institutions" covers the market.
    # LVR/loan-size series don't specify institution type — include those.
    has_institution_qualifier = any(
        "large institutions" in s or "all institutions" in s for s in segs
    )
    if any("large institutions" in s for s in segs):
        return None  # skip — "All institutions" equivalent exists

    # ── Purpose ───────────────────────────────────────────────────────────────
    purpose = None
    for s in segs:
        if "owner-occupied" in s or "owner occupied" in s:
            purpose = "oo"
            break
        if "investor" in s or "investment" in s:
            purpose = "investor"
            break
    if not purpose:
        return None  # can't determine purpose

    # ── Loan status ───────────────────────────────────────────────────────────
    loan_status = None
    for s in segs:
        if "new loans funded" in s or "funded in the month" in s:
            loan_status = "new"
            break
        if "outstanding" in s:
            loan_status = "outstanding"
            break
    if not loan_status:
        return None  # can't determine loan status

    # ── Rate type (optional — not all series specify) ─────────────────────────
    rate_type = None
    for s in segs:
        if "variable-rate" in s or "variable rate" in s:
            rate_type = "variable"
            break
        if "5-year" in s or "5 year" in s:
            rate_type = "fixed_5yr"
            break
        if "3-year" in s or "3 year" in s:
            rate_type = "fixed_3yr"
            break
        if "2-year" in s or "2 year" in s:
            rate_type = "fixed_2yr"
            break
        if "1-year" in s or "1 year" in s:
            rate_type = "fixed_1yr"
            break
        if "fixed-rate" in s or "fixed rate" in s:
            rate_type = "fixed"
            break

    # ── Repayment type (optional) ─────────────────────────────────────────────
    repayment_type = None
    for s in segs:
        if "principal-and-interest" in s or "principal and interest" in s:
            repayment_type = "pi"
            break
        if "interest-only" in s or "interest only" in s:
            repayment_type = "io"
            break

    # ── LVR band (optional) ───────────────────────────────────────────────────
    # RBA uses: "By loan-to-valuation ratio at commitment; Less than 81%"
    #           "By loan-to-valuation ratio at commitment; Greater than or equal to 81%"
    lvr_band = None
    for i, s in enumerate(segs):
        if "loan-to-valuation" in s or "loan to valuation" in s or "lvr" in s:
            # The next segment is the band description
            if i + 1 < len(segs):
                band = raw_segs[i + 1].strip()
                lvr_band = normalise_lvr_band(band)
            break

    # ── Loan size band (optional) ─────────────────────────────────────────────
    # RBA uses: "By value at commitment; Less than or equal to $600,000"
    #           "By value at commitment; $600,000 - $1,000,000"
    loan_size_band = None
    for i, s in enumerate(segs):
        if "value at commitment" in s or "loan size" in s or "loan amount" in s:
            if i + 1 < len(segs):
                band = raw_segs[i + 1].strip()
                loan_size_band = normalise_size_band(band)
            break

    return {
        "series_id": series_id,
        "description": description,
        "purpose": purpose,
        "repayment_type": repayment_type,
        "rate_type": rate_type,
        "loan_status": loan_status,
        "lvr_band": lvr_band,
        "loan_size_band": loan_size_band,
    }


def normalise_lvr_band(band: str) -> str:
    """
    Normalise RBA LVR band descriptions to compact form.
    e.g. "Less than 81%" → "<81%"
         "Greater than or equal to 81%" → "≥81%"
         "60 to less than 70 per cent" → "60-70%"
    """
    b = band.lower().strip()
    b = b.replace("per cent", "%").replace("percent", "%")
    b = b.replace("greater than or equal to", "≥")
    b = b.replace("greater than", ">")
    b = b.replace("less than or equal to", "≤")
    b = b.replace("less than", "<")
    b = b.replace(" to ", "-")
    # Remove spaces around % and numbers
    import re
    b = re.sub(r'\s*%', '%', b)
    b = re.sub(r'(\d)\s+(\d)', r'\1\2', b)
    b = re.sub(r'([<>≤≥])\s+', r'\1', b)
    return b.strip()


def normalise_size_band(band: str) -> str:
    """
    Normalise RBA loan size band descriptions to compact form.
    e.g. "Less than or equal to $600,000" → "≤$600k"
         "$600,000 - $1,000,000" → "$600k-$1m"
         "Greater than $1,000,000" → ">$1m"
    """
    import re
    b = band.strip()
    # Normalise comparator words
    b = re.sub(r'[Ll]ess than or equal to\s*', '≤', b)
    b = re.sub(r'[Gg]reater than or equal to\s*', '≥', b)
    b = re.sub(r'[Ll]ess than\s*', '<', b)
    b = re.sub(r'[Gg]reater than\s*', '>', b)
    # Compact dollar amounts: $600,000 → $600k, $1,000,000 → $1m
    def compact_dollars(m):
        raw = m.group(0).replace(',', '').replace('$', '')
        n = int(raw)
        if n >= 1_000_000 and n % 1_000_000 == 0:
            return f'${n // 1_000_000}m'
        elif n >= 1_000 and n % 1_000 == 0:
            return f'${n // 1_000}k'
        return m.group(0)
    b = re.sub(r'\$[\d,]+', compact_dollars, b)
    b = re.sub(r'\s*-\s*', '-', b)
    return b.strip()


# ── CSV parser ────────────────────────────────────────────────────────────────

def parse_rba_date(date_str: str) -> date | None:
    """Parse RBA date formats: 'DD/MM/YYYY' or 'Mon-YYYY'."""
    s = date_str.strip()
    for fmt in ("%d/%m/%Y", "%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def download_f6() -> str:
    print(f"Downloading RBA F6 from {RBA_F6_CSV_URL} ...")
    resp = requests.get(RBA_F6_CSV_URL, timeout=60)
    resp.raise_for_status()
    print(f"  Downloaded {len(resp.content):,} bytes")
    return resp.text


def parse_f6(csv_text: str) -> tuple[dict, list[date], dict]:
    """
    Parse RBA F6 CSV into series metadata, date list, and data values.

    Returns:
        series_meta: {col_index: parsed field dict}
        dates:       [date, ...]
        data:        {col_index: [float|None, ...]}
    """
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)

    # Find key rows
    series_ids_row = None
    descriptions_row = None
    data_start = None

    for i, row in enumerate(rows):
        if not row:
            continue
        label = row[0].strip().lower()
        if label == "series id":
            series_ids_row = i
        elif label in ("title", "description") and descriptions_row is None:
            descriptions_row = i
        elif parse_rba_date(row[0]) is not None and data_start is None:
            data_start = i

    if series_ids_row is None:
        raise ValueError("Could not find 'Series ID' row in F6 CSV")

    if data_start is None:
        print("\n⚠  Could not find data rows. First 30 rows:")
        for i, row in enumerate(rows[:30]):
            print(f"  [{i:02d}] {row[:3]}")
        raise ValueError("Could not find data rows — see above")

    series_row = rows[series_ids_row]
    desc_row = rows[descriptions_row] if descriptions_row else [""] * len(series_row)

    # Pad to same length
    max_len = max(len(series_row), len(desc_row))
    series_row += [""] * (max_len - len(series_row))
    desc_row   += [""] * (max_len - len(desc_row))

    # Parse series metadata
    series_meta = {}
    skipped_large = 0
    skipped_no_match = 0

    print(f"\nParsing {len(series_row) - 1} series columns ...")

    for col in range(1, len(series_row)):
        sid  = series_row[col].strip()
        desc = desc_row[col].strip()
        if not sid:
            continue
        parsed = parse_description(sid, desc)
        if parsed is None:
            if sid and "large institutions" in desc.lower():
                skipped_large += 1
            else:
                skipped_no_match += 1
        else:
            series_meta[col] = parsed

    print(f"  Matched:              {len(series_meta)} series")
    print(f"  Skipped (large inst): {skipped_large}")
    print(f"  Skipped (no match):   {skipped_no_match}")

    if not series_meta:
        print("\n⚠  No series matched. All descriptions:")
        for col in range(1, len(desc_row)):
            if series_row[col].strip():
                print(f"   [{series_row[col].strip()}] {desc_row[col].strip()}")
        raise ValueError(
            "No series matched — descriptions may have changed. "
            "Update parse_description() based on the output above."
        )

    # Parse data rows
    dates = []
    data = {col: [] for col in series_meta}

    for row in rows[data_start:]:
        if not row or not row[0].strip():
            continue
        d = parse_rba_date(row[0])
        if d is None:
            continue
        dates.append(d)
        for col in series_meta:
            raw = row[col].strip() if col < len(row) else ""
            try:
                data[col].append(float(raw))
            except ValueError:
                data[col].append(None)

    print(f"  Date range: {dates[0]} → {dates[-1]}  ({len(dates)} months)")
    return series_meta, dates, data


# ── Upsert ────────────────────────────────────────────────────────────────────

def build_rows(series_meta: dict, dates: list[date], data: dict) -> list[dict]:
    now = datetime.utcnow().isoformat()
    # Use a dict keyed on the unique constraint to deduplicate.
    # If two series map to the same key, last one wins (arbitrary but consistent).
    deduped: dict[tuple, dict] = {}
    duplicates = 0

    for col, meta in series_meta.items():
        for i, ref_date in enumerate(dates):
            rate = data[col][i]
            if rate is None:
                continue
            key = (
                ref_date.isoformat(),
                meta["purpose"],
                meta["repayment_type"],
                meta["rate_type"],
                meta["loan_status"],
                meta["lvr_band"],
                meta["loan_size_band"],
            )
            if key in deduped:
                duplicates += 1
            deduped[key] = {
                "source":          "RBA F6",
                "reference_month": key[0],
                "purpose":         meta["purpose"],
                "repayment_type":  meta["repayment_type"],
                "rate_type":       meta["rate_type"],
                "loan_status":     meta["loan_status"],
                "lvr_band":        meta["lvr_band"],
                "loan_size_band":  meta["loan_size_band"],
                "rate_pct":        rate,
                "fetched_at":      now,
            }

    rows = list(deduped.values())
    print(f"\nBuilt {len(rows):,} rows to upsert ({duplicates} duplicates removed)")
    return rows


def upsert_rows(sb, rows: list[dict]) -> None:
    BATCH = 500
    total = len(rows)
    upserted = 0
    for start in range(0, total, BATCH):
        batch = rows[start : start + BATCH]
        sb.table("benchmark_rates").upsert(
            batch,
            on_conflict="reference_month,purpose,repayment_type,rate_type,loan_status,lvr_band,loan_size_band",
        ).execute()
        upserted += len(batch)
        print(f"  Upserted {upserted:,} / {total:,}", end="\r")
    print(f"\n  Done — {upserted:,} rows upserted")


# ── Summary ───────────────────────────────────────────────────────────────────

def print_series_summary(series_meta: dict) -> None:
    print("\n── Series matched ─────────────────────────────────────────────────────────")
    print(f"  {'ID':<12} {'Purpose':<10} {'Repay':<6} {'Rate type':<12} {'Status':<12} {'LVR':<10} {'Size':<14} Description (truncated)")
    print("  " + "-" * 110)
    for col, meta in sorted(series_meta.items(), key=lambda x: (x[1]["loan_status"], x[1]["purpose"])):
        print(
            f"  {meta['series_id']:<12} {meta['purpose']:<10} {(meta['repayment_type'] or '-'):<6} "
            f"{(meta['rate_type'] or '-'):<12} {meta['loan_status']:<12} "
            f"{(meta['lvr_band'] or '-'):<10} {(meta['loan_size_band'] or '-'):<14} "
            f"{meta['description'][:55]}"
        )
    print()


def print_latest_rates(sb, latest_month: str) -> None:
    print(f"\nLatest month ({latest_month}) — key rates (new loans, no LVR/size filter):")
    result = (
        sb.table("benchmark_rates")
        .select("purpose,repayment_type,rate_type,loan_status,rate_pct")
        .eq("reference_month", latest_month)
        .eq("loan_status", "new")
        .is_("lvr_band", "null")
        .is_("loan_size_band", "null")
        .order("purpose").order("repayment_type").order("rate_type")
        .execute()
    )
    for r in result.data:
        rt = r["rate_type"] or "all-loans"
        rp = r["repayment_type"] or "all-repayment"
        print(f"  {r['purpose']:<10} {rp:<16} {rt:<14}  {r['rate_pct']:.2f}%")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not SUPABASE_SECRET:
        print("ERROR: SUPABASE_SECRET environment variable not set.")
        print("Run:  export SUPABASE_SECRET=<your-secret-key>")
        sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_SECRET)

    csv_text = download_f6()
    series_meta, dates, data = parse_f6(csv_text)
    print_series_summary(series_meta)

    rows = build_rows(series_meta, dates, data)
    upsert_rows(sb, rows)

    result = sb.table("benchmark_rates").select("id", count="exact").execute()
    print(f"\n✓ benchmark_rates now has {result.count:,} rows total")

    print_latest_rates(sb, dates[-1].isoformat())


if __name__ == "__main__":
    main()
