#!/usr/bin/env python3
"""
load_newbuild_concessions.py
Populates the newbuild_concessions table in Supabase with state-by-state
stamp duty concessions that apply specifically when is_new_build = True.

Only includes rules where new build status changes the calculation vs established.
NSW is excluded — FHB thresholds are identical for new and established homes.
TAS expired 30 June 2026. NT has no new-build concession.

Run:
    export SUPABASE_SECRET=your_secret_key_here
    python3 load_newbuild_concessions.py

Sources verified July 2026:
  QLD: https://aplacetocallhome.initiatives.qld.gov.au/initiatives/stamp-duty-concession
  SA:  https://premier.sa.gov.au/media-releases/news-archive/stamp-duty-officially-abolished-for-all-first-homebuyers-who-build-new-homes
  SA downsizer: https://conveyancingsa.com.au/stamp-duty-relief-in-2026-for-downsizers-in-south-australia/
  ACT: https://www.cmtedd.act.gov.au/open_government/inform/act_government_media_releases/barr/2026/act-budget-26-27-cutting-stamp-duty-for-all-act-first-home-buyers-and-backing-in-the-missing-middle
  VIC: https://www.sro.vic.gov.au/buying-property/land-transfer-stamp-duty/concessions-exemptions-and-waivers/off-plan-duty-concession/strata-apartments-and-townhouses-temporary-concession
  WA:  https://www.wa.gov.au/government/media-statements/Cook%20Labor%20Government/Stamp-duty-concessions-to-give-more-choice-for-home-buyers-20260312
"""

import os
from supabase import create_client

SUPABASE_URL    = "https://lkxzxeeeqfiymunpqvgt.supabase.co"
SUPABASE_SECRET = os.environ["SUPABASE_SECRET"]

sb = create_client(SUPABASE_URL, SUPABASE_SECRET)

rows = [
    # ── Queensland ────────────────────────────────────────────────────────────
    {
        "state":            "QLD",
        "concession_key":   "qld_fhb_newbuild",
        "buyer_type":       "fhb",
        "min_buyer_age":    None,
        "property_types":   "all",          # houses, apartments, vacant land to build
        "concession_type":  "full_exemption",
        "exempt_threshold": None,            # no price cap
        "taper_top":        None,
        "discount_pct":     None,
        "effective_from":   "2025-05-01",
        "effective_until":  None,
        "notes": (
            "Full stamp duty exemption for FHB buying a new home or vacant land to build. "
            "No price cap. From 1 August 2026 buyer must be an Australian citizen or permanent resident. "
            "Established home FHB concession (separate thresholds) handled in stamp_duty_concessions table."
        ),
    },

    # ── South Australia — FHB new build ───────────────────────────────────────
    {
        "state":            "SA",
        "concession_key":   "sa_fhb_newbuild",
        "buyer_type":       "fhb",
        "min_buyer_age":    None,
        "property_types":   "all",          # new homes, off-the-plan, vacant land
        "concession_type":  "full_exemption",
        "exempt_threshold": None,            # no price cap
        "taper_top":        None,
        "discount_pct":     None,
        "effective_from":   "2024-06-06",
        "effective_until":  None,
        "notes": (
            "Full stamp duty exemption for FHB purchasing a new home, off-the-plan apartment, "
            "or vacant land to build. No price cap. "
            "Does NOT apply to established/existing homes — SA has no FHB concession for established homes."
        ),
    },

    # ── South Australia — Downsizer new build ─────────────────────────────────
    {
        "state":            "SA",
        "concession_key":   "sa_downsizer_newbuild",
        "buyer_type":       "downsizer",
        "min_buyer_age":    60,
        "property_types":   "all",          # new homes and off-the-plan apartments
        "concession_type":  "full_exemption",
        "exempt_threshold": 2000000,         # up to $2M
        "taper_top":        None,
        "discount_pct":     None,
        "effective_from":   "2026-03-25",
        "effective_until":  None,
        "notes": (
            "Full stamp duty exemption for eligible downsizers aged 60+ who sell their current home "
            "and purchase a newly built home or off-the-plan apartment up to $2,000,000. "
            "One-time access only. Must be owner-occupier. First scheme of its kind in Australia."
        ),
    },

    # ── Australian Capital Territory — Missing Middle ──────────────────────────
    {
        "state":            "ACT",
        "concession_key":   "act_missing_middle",
        "buyer_type":       "all_oo",       # all owner-occupiers, not just FHB
        "min_buyer_age":    None,
        "property_types":   "strata",       # new unit-titled properties only
        "concession_type":  "full_exemption",
        "exempt_threshold": None,            # no price cap
        "taper_top":        None,
        "discount_pct":     None,
        "effective_from":   "2026-07-01",
        "effective_until":  None,
        "notes": (
            "Full stamp duty exemption for owner-occupiers purchasing new unit-titled (strata) properties. "
            "Part of ACT Missing Middle housing policy. No price cap. Applies to turn-key units and "
            "off-the-plan units. Subject to ongoing legislation."
        ),
    },

    # ── Victoria — Off-the-plan (phase 2 — frontend shows advisory note only) ─
    {
        "state":            "VIC",
        "concession_key":   "vic_off_plan_all",
        "buyer_type":       "all_oo",       # actually applies to all buyers incl. investors — phase 2 to distinguish
        "min_buyer_age":    None,
        "property_types":   "strata",       # apartments, units, townhouses in strata subdivisions
        "concession_type":  "off_plan_deduction",
        "exempt_threshold": None,
        "taper_top":        None,
        "discount_pct":     None,
        "effective_from":   "2023-10-21",
        "effective_until":  "2027-04-20",   # extended in 2026-27 budget (subject to legislation)
        "notes": (
            "PHASE 2 — frontend shows advisory note only, does not calculate. "
            "Deduct construction costs incurred after contract date from the dutiable value; "
            "stamp duty is then calculated on the reduced amount. "
            "Applies to all buyers (FHB, OO, investor, companies) of strata apartments, units and townhouses. "
            "No price cap. Extended to 20 April 2027 subject to legislation."
        ),
    },

    # ── Western Australia — Off-the-plan pre-construction ─────────────────────
    {
        "state":            "WA",
        "concession_key":   "wa_off_plan_all",
        "buyer_type":       "all_oo",       # applies to all buyers — using all_oo as approximation
        "min_buyer_age":    None,
        "property_types":   "strata",       # pre-construction/off-the-plan dwellings
        "concession_type":  "taper",
        "exempt_threshold": 800000,          # no duty up to $800k
        "taper_top":        900000,          # taper $800k–$900k; above $900k 50% discount applies
        "discount_pct":     None,
        "effective_from":   "2022-01-01",   # approximate — scheme predates this; extended to Jun 2028
        "effective_until":  "2028-06-30",
        "notes": (
            "Full stamp duty exemption for pre-construction off-the-plan properties up to $800,000. "
            "Taper applies $800,000–$900,000. Above $900,000 a 50% duty concession applies "
            "(frontend currently calculates taper band only — above $900k shows advisory). "
            "Applies to all buyers including investors. Extended to 30 June 2028."
        ),
    },
]


def main():
    print(f"Upserting {len(rows)} rows into newbuild_concessions...")
    result = (
        sb.table("newbuild_concessions")
        .upsert(rows, on_conflict="concession_key")
        .execute()
    )
    print(f"Done — {len(result.data)} rows upserted.")
    for row in result.data:
        print(f"  {row['state']:3s}  {row['concession_key']}")


if __name__ == "__main__":
    main()
