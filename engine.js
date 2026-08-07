/**
 * GetReal Engine — pure calculation functions for the buying ceiling calculator.
 *
 * Works in two environments:
 *   Browser  — loaded via <script src="/engine.js">, exposes window.GetRealEngine
 *   Node.js / Cloudflare Worker — import via require() or import
 *
 * No DOM, no global state, no Supabase dependency.
 * All external data (lmiRates, regFees, lmiSdRates) accepted as parameters
 * and fall back to the hardcoded tables below.
 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    // CommonJS / Node.js
    module.exports = factory();
  } else if (typeof define === 'function' && define.amd) {
    // AMD
    define(factory);
  } else {
    // Browser global
    root.GetRealEngine = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ─── Hardcoded: LMI rates ─────────────────────────────────────────────────
  // 15 LVR bands × 5 loan-size bands = 75 rows.
  // Source: Home Loan Experts indicative Helia/QBE rates, May 2026.
  // rate_pct is expressed as a percentage of the base loan (e.g. 0.56 means 0.56%).
  // loan_max: null = no upper limit (catch-all highest band).
  const DEFAULT_LMI_RATES = [
    // LVR 80–82%
    { lvr_min: 80, lvr_max: 82, loan_max: 300000,  rate_pct: 0.56 },
    { lvr_min: 80, lvr_max: 82, loan_max: 500000,  rate_pct: 0.61 },
    { lvr_min: 80, lvr_max: 82, loan_max: 750000,  rate_pct: 0.75 },
    { lvr_min: 80, lvr_max: 82, loan_max: 1000000, rate_pct: 0.81 },
    { lvr_min: 80, lvr_max: 82, loan_max: null,    rate_pct: 0.90 },
    // LVR 82–84%
    { lvr_min: 82, lvr_max: 84, loan_max: 300000,  rate_pct: 0.81 },
    { lvr_min: 82, lvr_max: 84, loan_max: 500000,  rate_pct: 0.87 },
    { lvr_min: 82, lvr_max: 84, loan_max: 750000,  rate_pct: 0.95 },
    { lvr_min: 82, lvr_max: 84, loan_max: 1000000, rate_pct: 1.10 },
    { lvr_min: 82, lvr_max: 84, loan_max: null,    rate_pct: 1.15 },
    // LVR 84–85%
    { lvr_min: 84, lvr_max: 85, loan_max: 300000,  rate_pct: 0.87 },
    { lvr_min: 84, lvr_max: 85, loan_max: 500000,  rate_pct: 0.94 },
    { lvr_min: 84, lvr_max: 85, loan_max: 750000,  rate_pct: 1.02 },
    { lvr_min: 84, lvr_max: 85, loan_max: 1000000, rate_pct: 1.20 },
    { lvr_min: 84, lvr_max: 85, loan_max: null,    rate_pct: 1.25 },
    // LVR 85–86%
    { lvr_min: 85, lvr_max: 86, loan_max: 300000,  rate_pct: 1.19 },
    { lvr_min: 85, lvr_max: 86, loan_max: 500000,  rate_pct: 1.29 },
    { lvr_min: 85, lvr_max: 86, loan_max: 750000,  rate_pct: 1.41 },
    { lvr_min: 85, lvr_max: 86, loan_max: 1000000, rate_pct: 1.64 },
    { lvr_min: 85, lvr_max: 86, loan_max: null,    rate_pct: 1.76 },
    // LVR 86–87%
    { lvr_min: 86, lvr_max: 87, loan_max: 300000,  rate_pct: 1.19 },
    { lvr_min: 86, lvr_max: 87, loan_max: 500000,  rate_pct: 1.29 },
    { lvr_min: 86, lvr_max: 87, loan_max: 750000,  rate_pct: 1.41 },
    { lvr_min: 86, lvr_max: 87, loan_max: 1000000, rate_pct: 1.64 },
    { lvr_min: 86, lvr_max: 87, loan_max: null,    rate_pct: 1.76 },
    // LVR 87–88%
    { lvr_min: 87, lvr_max: 88, loan_max: 300000,  rate_pct: 1.25 },
    { lvr_min: 87, lvr_max: 88, loan_max: 500000,  rate_pct: 1.35 },
    { lvr_min: 87, lvr_max: 88, loan_max: 750000,  rate_pct: 1.48 },
    { lvr_min: 87, lvr_max: 88, loan_max: 1000000, rate_pct: 1.73 },
    { lvr_min: 87, lvr_max: 88, loan_max: null,    rate_pct: 1.85 },
    // LVR 88–89%
    { lvr_min: 88, lvr_max: 89, loan_max: 300000,  rate_pct: 1.32 },
    { lvr_min: 88, lvr_max: 89, loan_max: 500000,  rate_pct: 1.43 },
    { lvr_min: 88, lvr_max: 89, loan_max: 750000,  rate_pct: 1.56 },
    { lvr_min: 88, lvr_max: 89, loan_max: 1000000, rate_pct: 1.82 },
    { lvr_min: 88, lvr_max: 89, loan_max: null,    rate_pct: 1.96 },
    // LVR 89–90%
    { lvr_min: 89, lvr_max: 90, loan_max: 300000,  rate_pct: 1.32 },
    { lvr_min: 89, lvr_max: 90, loan_max: 500000,  rate_pct: 1.43 },
    { lvr_min: 89, lvr_max: 90, loan_max: 750000,  rate_pct: 1.56 },
    { lvr_min: 89, lvr_max: 90, loan_max: 1000000, rate_pct: 1.82 },
    { lvr_min: 89, lvr_max: 90, loan_max: null,    rate_pct: 1.96 },
    // LVR 90–91%
    { lvr_min: 90, lvr_max: 91, loan_max: 300000,  rate_pct: 1.63 },
    { lvr_min: 90, lvr_max: 91, loan_max: 500000,  rate_pct: 1.80 },
    { lvr_min: 90, lvr_max: 91, loan_max: 750000,  rate_pct: 2.12 },
    { lvr_min: 90, lvr_max: 91, loan_max: 1000000, rate_pct: 2.27 },
    { lvr_min: 90, lvr_max: 91, loan_max: null,    rate_pct: 2.27 },
    // LVR 91–92%
    { lvr_min: 91, lvr_max: 92, loan_max: 300000,  rate_pct: 1.73 },
    { lvr_min: 91, lvr_max: 92, loan_max: 500000,  rate_pct: 1.88 },
    { lvr_min: 91, lvr_max: 92, loan_max: 750000,  rate_pct: 2.22 },
    { lvr_min: 91, lvr_max: 92, loan_max: 1000000, rate_pct: 2.37 },
    { lvr_min: 91, lvr_max: 92, loan_max: null,    rate_pct: 2.37 },
    // LVR 92–93%
    { lvr_min: 92, lvr_max: 93, loan_max: 300000,  rate_pct: 1.87 },
    { lvr_min: 92, lvr_max: 93, loan_max: 500000,  rate_pct: 2.05 },
    { lvr_min: 92, lvr_max: 93, loan_max: 750000,  rate_pct: 2.41 },
    { lvr_min: 92, lvr_max: 93, loan_max: 1000000, rate_pct: 2.58 },
    { lvr_min: 92, lvr_max: 93, loan_max: null,    rate_pct: 2.58 },
    // LVR 93–94%
    { lvr_min: 93, lvr_max: 94, loan_max: 300000,  rate_pct: 2.13 },
    { lvr_min: 93, lvr_max: 94, loan_max: 500000,  rate_pct: 2.30 },
    { lvr_min: 93, lvr_max: 94, loan_max: 750000,  rate_pct: 2.73 },
    { lvr_min: 93, lvr_max: 94, loan_max: 1000000, rate_pct: 2.94 },
    { lvr_min: 93, lvr_max: 94, loan_max: null,    rate_pct: 2.94 },
    // LVR 94–95%
    { lvr_min: 94, lvr_max: 95, loan_max: 300000,  rate_pct: 2.13 },
    { lvr_min: 94, lvr_max: 95, loan_max: 500000,  rate_pct: 2.30 },
    { lvr_min: 94, lvr_max: 95, loan_max: 750000,  rate_pct: 2.73 },
    { lvr_min: 94, lvr_max: 95, loan_max: 1000000, rate_pct: 2.94 },
    { lvr_min: 94, lvr_max: 95, loan_max: null,    rate_pct: 2.94 },
    // LVR 95–97%
    { lvr_min: 95, lvr_max: 97, loan_max: 300000,  rate_pct: 3.14 },
    { lvr_min: 95, lvr_max: 97, loan_max: 500000,  rate_pct: 3.35 },
    { lvr_min: 95, lvr_max: 97, loan_max: 750000,  rate_pct: 3.70 },
    { lvr_min: 95, lvr_max: 97, loan_max: 1000000, rate_pct: 3.70 },
    { lvr_min: 95, lvr_max: 97, loan_max: null,    rate_pct: 3.70 },
    // LVR 97–100%
    { lvr_min: 97, lvr_max: 100, loan_max: 300000,  rate_pct: 3.14 },
    { lvr_min: 97, lvr_max: 100, loan_max: 500000,  rate_pct: 3.35 },
    { lvr_min: 97, lvr_max: 100, loan_max: 750000,  rate_pct: 3.70 },
    { lvr_min: 97, lvr_max: 100, loan_max: 1000000, rate_pct: 3.70 },
    { lvr_min: 97, lvr_max: 100, loan_max: null,    rate_pct: 3.70 },
  ];

  // ─── Hardcoded: LMI stamp duty rates by state ─────────────────────────────
  // State governments charge stamp duty on LMI premiums.
  // Source: state revenue offices, indicative 2025-2026.
  const DEFAULT_LMI_SD_RATES = {
    NSW: 0.09,
    VIC: 0.10,
    QLD: 0.09,
    WA:  0.10,
    SA:  0.11,
    TAS: 0.10,
    ACT: 0.06,
    NT:  0.10,
  };

  // ─── Hardcoded: Registration + transfer fees by state ─────────────────────
  // Combined transfer registration + mortgage registration fees.
  // These are flat estimates; NSW figures are accurate, others indicative.
  // Source: state land titles offices, indicative 2025-2026.
  const DEFAULT_REG_FEES = {
    NSW: 670,
    VIC: 1700,
    QLD: 1250,
    WA:  1120,
    SA:  800,
    TAS: 600,
    ACT: 1100,
    NT:  500,
  };

  // ─── Hardcoded: Lending policy constants ──────────────────────────────────
  // Regulatory constants (APRA guidelines) that rarely change.
  // Live values loaded from Supabase lending_policy_constants table.
  const DEFAULT_LENDING_CONSTANTS = {
    dti_multiplier:         6,     // Max total debt ÷ gross annual income
    stress_rate_buffer_pct: 3,     // Percentage points above benchmark for serviceability test
    cc_repayment_rate:      0.03,  // Monthly minimum as fraction of total credit card limit
    loan_term_months:       360,   // Standard loan term used in repayment formula (30 years)
  };

  // ─── Hardcoded: LVR limits by property type and occupancy ─────────────────
  // Live values loaded from Supabase lvr_limits table.
  const DEFAULT_LVR_LIMITS = [
    { property_type: 'standard',  is_owner_occupier: true,  max_lvr: 0.95 },
    { property_type: 'standard',  is_owner_occupier: false, max_lvr: 0.90 },
    { property_type: 'apartment', is_owner_occupier: true,  max_lvr: 0.90 },
    { property_type: 'apartment', is_owner_occupier: false, max_lvr: 0.80 },
  ];

  // ─── State stamp duty calculators ─────────────────────────────────────────
  function _brackets(price, tbl) {
    for (const b of tbl) {
      if (price <= b.max) return b.base + (price - b.min) * b.rate;
    }
    return 0;
  }
  function _nswDuty(p) {
    return _brackets(p, [
      { min: 0,       max: 16000,    base: 0,      rate: 0.0125 },
      { min: 16000,   max: 35000,    base: 200,    rate: 0.015  },
      { min: 35000,   max: 93000,    base: 485,    rate: 0.0175 },
      { min: 93000,   max: 351000,   base: 1500,   rate: 0.035  },
      { min: 351000,  max: 1168000,  base: 10530,  rate: 0.045  },
      { min: 1168000, max: 3505000,  base: 47295,  rate: 0.055  },
      { min: 3505000, max: Infinity, base: 175830, rate: 0.07   },
    ]);
  }
  function _vicGeneral(p) {
    if (p <= 25000)   return p * 0.014;
    if (p <= 130000)  return 350   + (p - 25000)   * 0.024;
    if (p <= 960000)  return 2870  + (p - 130000)  * 0.06;
    if (p <= 2000000) return p * 0.055;
    return 110000 + (p - 2000000) * 0.065;
  }
  function _vicPPR(p) {
    if (p <= 25000)   return p * 0.014;
    if (p <= 130000)  return 350   + (p - 25000)   * 0.024;
    if (p <= 440000)  return 2870  + (p - 130000)  * 0.05;
    if (p <= 550000)  return 18370 + (p - 440000)  * 0.06;
    return _vicGeneral(p);
  }
  function _qldDuty(p) {
    return _brackets(p, [
      { min: 0,       max: 5000,     base: 0,     rate: 0      },
      { min: 5000,    max: 75000,    base: 0,     rate: 0.015  },
      { min: 75000,   max: 540000,   base: 1050,  rate: 0.035  },
      { min: 540000,  max: 1000000,  base: 17325, rate: 0.045  },
      { min: 1000000, max: Infinity, base: 38025, rate: 0.0575 },
    ]);
  }
  function _waDuty(p) {
    return _brackets(p, [
      { min: 0,       max: 120000,   base: 0,     rate: 0.019  },
      { min: 120000,  max: 150000,   base: 2280,  rate: 0.0285 },
      { min: 150000,  max: 360000,   base: 3135,  rate: 0.038  },
      { min: 360000,  max: 725000,   base: 11115, rate: 0.0475 },
      { min: 725000,  max: Infinity, base: 28453, rate: 0.0515 },
    ]);
  }
  function _saDuty(p) {
    return _brackets(p, [
      { min: 0,       max: 12000,    base: 0,     rate: 0.01   },
      { min: 12000,   max: 30000,    base: 120,   rate: 0.02   },
      { min: 30000,   max: 50000,    base: 480,   rate: 0.03   },
      { min: 50000,   max: 100000,   base: 1080,  rate: 0.035  },
      { min: 100000,  max: 200000,   base: 2830,  rate: 0.04   },
      { min: 200000,  max: 250000,   base: 6830,  rate: 0.0425 },
      { min: 250000,  max: 300000,   base: 8955,  rate: 0.0475 },
      { min: 300000,  max: 500000,   base: 11330, rate: 0.05   },
      { min: 500000,  max: Infinity, base: 21330, rate: 0.055  },
    ]);
  }
  function _tasDuty(p) {
    if (p <= 3000)   return 50;
    if (p <= 25000)  return 50    + (p - 3000)   * 0.0175;
    if (p <= 75000)  return 435   + (p - 25000)  * 0.0225;
    if (p <= 200000) return 1560  + (p - 75000)  * 0.035;
    if (p <= 375000) return 5935  + (p - 200000) * 0.04;
    if (p <= 725000) return 12935 + (p - 375000) * 0.0425;
    return 27810 + (p - 725000) * 0.045;
  }
  function _actDuty(p) {
    return _brackets(p, [
      { min: 0,        max: 200000,   base: 0,     rate: 0.022  },
      { min: 200000,   max: 300000,   base: 4400,  rate: 0.034  },
      { min: 300000,   max: 500000,   base: 7800,  rate: 0.0432 },
      { min: 500000,   max: 750000,   base: 16440, rate: 0.059  },
      { min: 750000,   max: 1000000,  base: 31190, rate: 0.064  },
      { min: 1000000,  max: 1455000,  base: 47190, rate: 0.072  },
      { min: 1455000,  max: Infinity, base: 80034, rate: 0.0454 },
    ]);
  }
  function _ntDuty(p) {
    if (p <= 525000) {
      const V = p / 1000;
      return 0.06571441 * V * V + 15 * V;
    }
    return p * 0.0495;
  }

  // ─── Supabase-sourced stamp duty helpers ──────────────────────────────────

  // Applies one bracket from the stamp_duty_brackets Supabase schema.
  // Iterates sorted ascending by bracket_min; returns when price <= bracket_max (null = ∞).
  function _supabaseBrackets(price, brackets) {
    for (const b of brackets) {
      const maxVal = b.bracket_max === null ? Infinity : b.bracket_max;
      if (price <= maxVal) {
        if (b.is_full_price) return price * b.rate;
        return b.base_amount + (price - b.bracket_min) * b.rate;
      }
    }
    return 0;
  }

  // Applies hardcoded FHB concession thresholds when sdConcessions data is unavailable.
  function _fhbHardcodedConcession(price, full, state) {
    switch (state) {
      case 'NSW':
        if (price <= 800000) return 0;
        if (price <= 1000000) return Math.round(full * (price - 800000) / 200000);
        return Math.round(full);
      case 'VIC':
        if (price <= 600000) return 0;
        if (price <= 750000) return Math.round(full * (price - 600000) / 150000);
        return Math.round(full);
      case 'QLD':
        if (price <= 500000) return 0;
        if (price <= 550000) return Math.round(full * (price - 500000) / 50000);
        return Math.round(full);
      case 'WA':
        if (price <= 600000) return 0;
        if (price <= 800000) return Math.round(full * (price - 600000) / 200000);
        return Math.round(full);
      case 'TAS':
        if (price < 600000) return Math.round(full * 0.5);
        return Math.round(full);
      default:
        return Math.round(full);
    }
  }

  // Computes duty using live Supabase bracket data.
  // Returns null if the required data for this state isn't available (caller falls back to hardcoded).
  function _calcDutyFromSupabase(price, ctx, sdBrackets, sdConcessions, ntFormula) {
    const { state, isFHB = false, isOO = true, isHBCS = false } = ctx;

    // NT uses a formula, not brackets
    if (state === 'NT') {
      if (!ntFormula) return null;
      const V = price / ntFormula.divisor;
      const full = price <= ntFormula.formula_threshold
        ? ntFormula.coeff_a * V * V + ntFormula.coeff_b * V
        : price * ntFormula.flat_rate_above;
      if (isFHB) {
        const conc = sdConcessions && sdConcessions['NT'];
        const priceCap    = (conc && conc.fhb_price_cap)        || 650000;
        const phaseStart  = (conc && conc.fhb_phaseout_start)   || 500000;
        const maxDiscount = (conc && conc.fhb_max_discount)      || 18601;
        if (price < priceCap) {
          const factor   = price <= phaseStart ? 1 : (priceCap - price) / (priceCap - phaseStart);
          const discount = Math.min(full, maxDiscount * factor);
          return Math.max(0, Math.round(full - discount));
        }
      }
      return Math.round(full);
    }

    // Filter brackets for this state
    const stateBrackets = sdBrackets.filter(b => b.state === state);
    if (!stateBrackets.length) return null; // state not in Supabase — signal caller to use hardcoded

    // ACT: full exemption for FHB / HBCS before bracket lookup
    if (state === 'ACT') {
      if (isFHB || isHBCS) return 0;
    }

    // Select bracket set: VIC has 'standard' and 'vic_ppr'; all others use 'standard'
    // FHB always uses 'standard' (concession applied on top), PPR rate only applies to non-FHB OO ≤ $550k
    const bracketSet = (state === 'VIC' && !isFHB && isOO && price <= 550000) ? 'vic_ppr' : 'standard';
    const selectedBrackets = stateBrackets
      .filter(b => b.bracket_set === bracketSet)
      .sort((a, b_) => a.bracket_min - b_.bracket_min);
    if (!selectedBrackets.length) return null;

    const full = _supabaseBrackets(price, selectedBrackets);
    if (!isFHB) return Math.round(full);

    // Apply FHB concession — use Supabase data if available, else fall back to hardcoded thresholds
    const conc = sdConcessions && sdConcessions[state];

    // Taper-based exemption (NSW, VIC, QLD, WA)
    if (conc && conc.fhb_exempt_threshold !== undefined && conc.fhb_taper_top !== undefined) {
      if (price <= conc.fhb_exempt_threshold) return 0;
      if (price <= conc.fhb_taper_top) {
        return Math.round(full * (price - conc.fhb_exempt_threshold) / (conc.fhb_taper_top - conc.fhb_exempt_threshold));
      }
      return Math.round(full);
    }

    // Percentage discount (TAS)
    if (conc && conc.fhb_discount_pct !== undefined && conc.fhb_price_cap !== undefined) {
      if (price < conc.fhb_price_cap) return Math.round(full * (1 - conc.fhb_discount_pct / 100));
      return Math.round(full);
    }

    // No concession data — apply hardcoded thresholds for this state's FHB concession
    return _fhbHardcodedConcession(price, full, state);
  }

  // ─── Public: calcStampDuty ─────────────────────────────────────────────────
  /**
   * Returns the stamp duty payable after FHB/HBCS/PPR concessions.
   * Does NOT apply new-build concessions (those require live Supabase data).
   *
   * @param {number} price
   * @param {{ state, isFHB, isOO, isHBCS, isNewBuild, propType }} ctx
   * @param {Array}  [sdBrackets]   rows from stamp_duty_brackets Supabase table (all states)
   * @param {object} [sdConcessions] { state → { concession_key → value } } from stamp_duty_concessions
   * @param {object} [ntFormula]    single row from nt_duty_formula Supabase table
   * @returns {number} rounded duty in dollars
   */
  function calcStampDuty(price, ctx, sdBrackets, sdConcessions, ntFormula) {
    // Try Supabase-sourced data first
    if (sdBrackets && sdBrackets.length) {
      const result = _calcDutyFromSupabase(price, ctx, sdBrackets, sdConcessions, ntFormula);
      if (result !== null) return result;
    }

    // Fall back to hardcoded tables
    const { state, isFHB = false, isOO = true, isHBCS = false } = ctx;
    switch (state) {
      case 'NSW': {
        const full = _nswDuty(price);
        if (isFHB) {
          if (price <= 800000) return 0;
          if (price <= 1000000) return Math.round(full * (price - 800000) / 200000);
        }
        return Math.round(full);
      }
      case 'VIC': {
        if (isFHB) {
          const full = _vicGeneral(price);
          if (price <= 600000) return 0;
          if (price <= 750000) return Math.round(full * (price - 600000) / 150000);
          return Math.round(full);
        }
        if (isOO && price <= 550000) return Math.round(_vicPPR(price));
        return Math.round(_vicGeneral(price));
      }
      case 'QLD': {
        const full = _qldDuty(price);
        if (isFHB) {
          if (price <= 500000) return 0;
          if (price <= 550000) return Math.round(full * (price - 500000) / 50000);
        }
        return Math.round(full);
      }
      case 'WA': {
        const full = _waDuty(price);
        if (isFHB) {
          if (price <= 600000) return 0;
          if (price <= 800000) return Math.round(full * (price - 600000) / 200000);
        }
        return Math.round(full);
      }
      case 'SA':
        return Math.round(_saDuty(price));
      case 'TAS': {
        const full = _tasDuty(price);
        if (isFHB && price < 600000) return Math.round(full * 0.5);
        return Math.round(full);
      }
      case 'ACT':
        if (isFHB)  return 0;  // From 1 July 2026: all FHB full exemption
        if (isHBCS) return 0;
        return Math.round(_actDuty(price));
      case 'NT': {
        const full = _ntDuty(price);
        if (isFHB && price < 650000) {
          const factor = price <= 500000 ? 1 : (650000 - price) / 150000;
          const discount = Math.min(full, 18601 * factor);
          return Math.max(0, Math.round(full - discount));
        }
        return Math.round(full);
      }
      default:
        return 0;
    }
  }

  // ─── Public: lookupLMIRate ─────────────────────────────────────────────────
  /**
   * Returns the LMI rate as a decimal fraction (e.g. 0.0056 for 0.56%).
   * lvrPct is the LVR as a percentage (e.g. 85 for 85%).
   *
   * @param {number} lvrPct
   * @param {number} baseLoan
   * @param {Array}  [lmiRates]  defaults to DEFAULT_LMI_RATES
   * @returns {number}
   */
  function lookupLMIRate(lvrPct, baseLoan, lmiRates) {
    const rates = lmiRates || DEFAULT_LMI_RATES;
    const lvrMatch = rates.filter(r => lvrPct > r.lvr_min && lvrPct <= r.lvr_max);
    if (!lvrMatch.length) return 0;
    const exact = lvrMatch.find(r => r.loan_max === null || baseLoan <= r.loan_max);
    if (exact) return exact.rate_pct / 100;
    return lvrMatch[lvrMatch.length - 1].rate_pct / 100;
  }

  // ─── Public: getMaxLVR ────────────────────────────────────────────────────
  /**
   * Returns the maximum LVR (as decimal) for the property/purpose combination.
   *
   * @param {{ propType, isOO }} ctx
   * @param {Array} [lvrLimits]  rows from lvr_limits Supabase table
   * @returns {number}  e.g. 0.95
   */
  function getMaxLVR(ctx, lvrLimits) {
    const { propType, isOO = true } = ctx;
    const propKey = (propType === 'apartment') ? 'apartment' : 'standard';
    const rows = (lvrLimits && lvrLimits.length) ? lvrLimits : DEFAULT_LVR_LIMITS;
    const row = rows.find(r => r.property_type === propKey && r.is_owner_occupier === isOO);
    return row ? Number(row.max_lvr) : (propKey === 'apartment' ? (isOO ? 0.90 : 0.80) : (isOO ? 0.95 : 0.90));
  }

  // ─── Internal: computeAtPrice ─────────────────────────────────────────────
  // Evaluates whether `savings` can support a purchase at `price` under `maxLVR`.
  // Returns a result object on success, null if the price is out of reach.
  function _computeAtPrice(price, savings, maxLVR, stampDuty, regFee, lmiSdRate, lmiRates) {
    let lmiSd = 0, lmiPremium = 0;
    let availDeposit, baseLoan, baseLVR, effectiveLoan, effectiveLVR;

    for (let inner = 0; inner < 6; inner++) {
      const upfront = stampDuty + regFee + lmiSd;
      availDeposit  = savings - upfront;
      if (availDeposit <= 0) return null;

      baseLoan = price - availDeposit;
      if (baseLoan <= 0) return null;

      baseLVR = baseLoan / price;
      if (baseLVR > maxLVR) return null;

      if (baseLVR <= 0.80) {
        lmiPremium = 0; lmiSd = 0;
        effectiveLoan = baseLoan;
        effectiveLVR  = baseLVR;
        break;
      }

      const lvrPct  = baseLVR * 100;
      const rate    = lookupLMIRate(lvrPct, baseLoan, lmiRates);
      lmiPremium    = baseLoan * rate;
      effectiveLoan = baseLoan + lmiPremium;
      effectiveLVR  = effectiveLoan / price;
      if (effectiveLVR > maxLVR) return null;
      lmiSd = lmiPremium * lmiSdRate;
    }

    const lvrTier = baseLVR <= 0.80 ? 0.80 : (baseLVR <= 0.90 ? 0.90 : 0.95);
    return {
      price, stampDuty, regFee, lmiSd: Math.round(lmiSd),
      availDeposit, baseLoan, baseLVR,
      lmiPremium: Math.round(lmiPremium),
      effectiveLoan: Math.round(effectiveLoan),
      effectiveLVR, lvrTier,
    };
  }

  // ─── Public: solveDepositCeiling ──────────────────────────────────────────
  /**
   * Binary-searches for the maximum purchase price given savings and buyer context.
   * This is the C1 (deposit) ceiling calculation.
   *
   * @param {{ savings, state, isFHB, isOO, isHBCS, isNewBuild, propType,
   *            lmiRates, regFees, lmiSdRates }} opts
   * @returns {object|null}  full result object or null if savings are insufficient
   */
  function solveDepositCeiling(opts) {
    const {
      savings, state, isFHB = false, isOO = true,
      isHBCS = false, isNewBuild = false, propType = 'house',
      lmiRates, regFees: regFeesMap, lmiSdRates: lmiSdRatesMap,
      sdBrackets, sdConcessions, ntDutyFormula,
      lvrLimits, lendingConstants,
    } = opts;

    if (!savings || savings <= 0) return null;

    const maxLVR    = getMaxLVR({ propType, isOO }, lvrLimits);
    const regFee    = (regFeesMap && regFeesMap[state]) || DEFAULT_REG_FEES[state] || 400;
    const lmiSdRate = (lmiSdRatesMap && lmiSdRatesMap[state]) || DEFAULT_LMI_SD_RATES[state] || 0;
    const ctx       = { state, isFHB, isOO, isHBCS, isNewBuild, propType };

    let low  = 0;
    let high = Math.min(Math.ceil(savings * 25), 15000000);
    let best = null;

    for (let i = 0; i < 60; i++) {
      const mid = Math.floor((low + high) / 2);
      if (mid <= 0) { high = mid - 1; continue; }
      const duty = calcStampDuty(mid, ctx, sdBrackets, sdConcessions, ntDutyFormula);
      const r    = _computeAtPrice(mid, savings, maxLVR, duty, regFee, lmiSdRate, lmiRates);
      if (r !== null) { best = r; low = mid + 1; }
      else            { high = mid - 1; }
    }

    return best;
  }

  // ─── Public: requiredSavingsForPrice ──────────────────────────────────────
  /**
   * Returns the minimum savings needed to purchase at `price` using `lvrTier`.
   * Includes deposit component, stamp duty, reg fee, and LMI stamp duty.
   *
   * @param {number} price
   * @param {{ state, isFHB, isOO, isHBCS, isNewBuild, propType, lvrTier,
   *            lmiRates, regFees, lmiSdRates }} opts
   * @returns {object|null}
   */
  function requiredSavingsForPrice(price, opts) {
    const {
      state, isFHB = false, isOO = true, isHBCS = false,
      isNewBuild = false, propType = 'house', lvrTier = 0.80,
      lmiRates, regFees: regFeesMap, lmiSdRates: lmiSdRatesMap,
      sdBrackets, sdConcessions, ntDutyFormula,
    } = opts;

    if (price <= 0 || lvrTier <= 0) return null;

    const ctx       = { state, isFHB, isOO, isHBCS, isNewBuild, propType };
    const stampDuty = calcStampDuty(price, ctx, sdBrackets, sdConcessions, ntDutyFormula);
    const regFee    = (regFeesMap && regFeesMap[state]) || DEFAULT_REG_FEES[state] || 400;
    const lmiSdRate = (lmiSdRatesMap && lmiSdRatesMap[state]) || DEFAULT_LMI_SD_RATES[state] || 0;
    const baseLoan  = Math.round(price * lvrTier);
    const depositComponent = price - baseLoan;
    let lmiPremium = 0, lmiSd = 0;
    if (lvrTier > 0.80) {
      const rate = lookupLMIRate(lvrTier * 100, baseLoan, lmiRates);
      lmiPremium = Math.round(baseLoan * rate);
      lmiSd      = Math.round(lmiPremium * lmiSdRate);
    }
    const requiredSavings = depositComponent + stampDuty + regFee + lmiSd;
    return { requiredSavings, depositComponent, stampDuty, regFee, lmiPremium, lmiSd, lvrTier };
  }

  // ─── Public: findMaxPriceForLoanCap ───────────────────────────────────────
  /**
   * Binary-searches for the highest purchase price reachable given a maximum loan
   * cap and available savings (for upfront costs + deposit component).
   * Used by both C2 (DTI) and C3 (serviceability) to convert a loan ceiling
   * into a purchase-price ceiling.
   *
   * @param {number} loanCap
   * @param {{ savings, state, isFHB, isOO, isHBCS, isNewBuild, propType,
   *            lmiRates, regFees, lmiSdRates }} opts
   * @returns {object|null}
   */
  function findMaxPriceForLoanCap(loanCap, opts) {
    const {
      savings, state, isFHB = false, isOO = true,
      isHBCS = false, isNewBuild = false, propType = 'house',
      lmiRates, regFees: regFeesMap, lmiSdRates: lmiSdRatesMap,
      sdBrackets, sdConcessions, ntDutyFormula,
      lvrLimits,
    } = opts;

    if (loanCap <= 0 || !savings || savings <= 0) return null;

    const maxLVR    = getMaxLVR({ propType, isOO }, lvrLimits);
    const regFee    = (regFeesMap && regFeesMap[state]) || DEFAULT_REG_FEES[state] || 400;
    const lmiSdRate = (lmiSdRatesMap && lmiSdRatesMap[state]) || DEFAULT_LMI_SD_RATES[state] || 0;
    const ctx       = { state, isFHB, isOO, isHBCS, isNewBuild, propType };

    let lo   = 0;
    let hi   = Math.min(loanCap + savings, 15000000);
    let best = null;

    for (let i = 0; i < 60; i++) {
      const mid = Math.floor((lo + hi) / 2);
      if (mid <= 0) { hi = mid - 1; continue; }

      const depositNeeded = mid - loanCap;
      if (depositNeeded < 0) { lo = mid + 1; continue; }

      const baseLVR = loanCap / mid;
      if (baseLVR > maxLVR) { lo = mid + 1; continue; }

      const stampDuty = calcStampDuty(mid, ctx, sdBrackets, sdConcessions, ntDutyFormula);
      let lmiPremium = 0, lmiSd = 0;
      if (baseLVR > 0.80) {
        const rate = lookupLMIRate(baseLVR * 100, loanCap, lmiRates);
        lmiPremium = Math.round(loanCap * rate);
        lmiSd      = Math.round(lmiPremium * lmiSdRate);
      }

      const savingsNeeded = depositNeeded + stampDuty + regFee + lmiSd;
      if (savingsNeeded <= savings) {
        const lvrTier = baseLVR <= 0.80 ? 0.80 : (baseLVR <= 0.90 ? 0.90 : 0.95);
        best = { price: mid, loanCap, baseLVR, lvrTier, depositNeeded, stampDuty, regFee,
                 lmiPremium, lmiSd, savingsNeeded,
                 effectiveLoan: loanCap + lmiPremium };
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }

    return best;
  }

  // ─── Public: solveDTICeiling ──────────────────────────────────────────────
  /**
   * Returns the maximum new-mortgage loan under the 6× DTI rule.
   *
   * @param {{ grossIncome1, grossIncome2, rentalIncome, creditCards,
   *            hasHECS, mortgages, otherLoans }} opts
   *   mortgages:  [{balance, isInvestment, weeklyRent}]
   *   otherLoans: [{amount}]
   *   rentalIncome: weekly rent on the NEW investment property (0 if OO)
   * @returns {{ maxNewMortgage, maxTotalDebt, totalIncome, existingDebt,
   *             mortgageBalances, loanBalances, newPropRental, existInvRental }}
   */
  function solveDTICeiling(opts) {
    const {
      grossIncome1 = 0,
      grossIncome2 = 0,
      rentalIncome = 0,         // weekly rent on NEW investment purchase
      isOO         = true,      // if false, rental income is counted
      creditCards  = 0,
      hasHECS      = false,
      mortgages    = [],        // [{balance, isInvestment, weeklyRent}]
      otherLoans   = [],        // [{amount}]
      lendingConstants,
    } = opts;

    const newPropRental  = isOO ? 0 : rentalIncome * 52 * 0.80;
    const existInvRental = mortgages
      .filter(m => m.isInvestment && m.weeklyRent > 0)
      .reduce((s, m) => s + m.weeklyRent * 52 * 0.80, 0);
    const totalIncome    = grossIncome1 + grossIncome2 + newPropRental + existInvRental;

    const mortgageBalances = mortgages.reduce((s, m) => s + (m.balance || 0), 0);
    const loanBalances     = otherLoans.reduce((s, l) => s + (l.amount || 0), 0);
    const existingDebt     = creditCards + mortgageBalances + loanBalances;
    const dtiMult          = (lendingConstants && lendingConstants.dti_multiplier) || DEFAULT_LENDING_CONSTANTS.dti_multiplier;
    const maxTotalDebt     = totalIncome * dtiMult;
    const maxNewMortgage   = Math.max(0, maxTotalDebt - existingDebt);

    return {
      maxNewMortgage, maxTotalDebt, totalIncome, existingDebt,
      mortgageBalances, loanBalances, newPropRental, existInvRental,
    };
  }

  // ─── Public: solveServiceabilityCeiling ───────────────────────────────────
  /**
   * Returns the maximum loan supportable under the APRA serviceability test
   * (repayment at benchmark + 3% stress rate).
   *
   * @param {{ takeHome1, takeHome1Freq, takeHome2, takeHome2Freq,
   *            rentalIncomeMonthly,
   *            hemAmount, rent, schoolFees, healthInsurance,
   *            mortgageRepayments, loanRepayments, creditCards,
   *            stressRateAnnual }} opts
   *   takeHome1Freq / takeHome2Freq: 'weekly' | 'fortnightly' | 'monthly'
   *   mortgageRepayments: [number]  monthly repayment per existing mortgage
   *   loanRepayments:     [number]  monthly repayment per other loan
   *   creditCards:        total credit card limits (3% of limit treated as monthly min)
   *   stressRateAnnual:   e.g. 9.0 (default). Pass benchmarkRate + 3 if known.
   * @returns {{ maxLoan, maxMonthlyRepayment, netMonthly, hemMonthly,
   *             committedMonthly, mortgageMonthly, loanMonthly, cardMonthly,
   *             existingMonthly, stressRateAnnual }}
   */
  function solveServiceabilityCeiling(opts) {
    const {
      takeHome1         = 0,
      takeHome1Freq     = 'fortnightly',
      takeHome2         = 0,
      takeHome2Freq     = 'fortnightly',
      rentalIncomeMonthly = 0,
      hemAmount         = 0,
      rent              = 0,
      schoolFees        = 0,
      healthInsurance   = 0,
      mortgageRepayments = [],
      loanRepayments    = [],
      creditCards       = 0,
      stressRateAnnual  = 9.0,
      lendingConstants,
    } = opts;

    const toMonthly = (amt, freq) => {
      if (freq === 'weekly')      return amt * 52 / 12;
      if (freq === 'fortnightly') return amt * 26 / 12;
      return amt;
    };

    const income1Monthly = toMonthly(takeHome1, takeHome1Freq);
    const income2Monthly = takeHome2 > 0 ? toMonthly(takeHome2, takeHome2Freq) : 0;
    const netMonthly     = income1Monthly + income2Monthly + rentalIncomeMonthly;

    const hemMonthly       = hemAmount || 0;
    const committedMonthly = (rent || 0) + (schoolFees || 0) + (healthInsurance || 0);
    const mortgageMonthly  = mortgageRepayments.reduce((s, r) => s + (r || 0), 0);
    const loanMonthly      = loanRepayments.reduce((s, r) => s + (r || 0), 0);
    const CC_RATE          = (lendingConstants && lendingConstants.cc_repayment_rate) || DEFAULT_LENDING_CONSTANTS.cc_repayment_rate;
    const cardMonthly      = creditCards * CC_RATE;
    const existingMonthly  = mortgageMonthly + loanMonthly + cardMonthly;

    const maxMonthlyRepayment = netMonthly - hemMonthly - committedMonthly - existingMonthly;
    if (maxMonthlyRepayment <= 0) {
      return {
        maxLoan: 0, maxMonthlyRepayment, netMonthly, hemMonthly, committedMonthly,
        mortgageMonthly, loanMonthly, cardMonthly, existingMonthly, stressRateAnnual,
      };
    }

    const r = stressRateAnnual / 100 / 12;
    const n = (lendingConstants && lendingConstants.loan_term_months) || DEFAULT_LENDING_CONSTANTS.loan_term_months;
    const maxLoan = r > 0
      ? maxMonthlyRepayment * (Math.pow(1 + r, n) - 1) / (r * Math.pow(1 + r, n))
      : maxMonthlyRepayment * n;

    return {
      maxLoan: Math.round(maxLoan),
      maxMonthlyRepayment, netMonthly, hemMonthly, committedMonthly,
      mortgageMonthly, loanMonthly, cardMonthly, existingMonthly, stressRateAnnual,
    };
  }

  // ─── Public: calcMonthlyRepayment ─────────────────────────────────────────
  /**
   * Standard P&I monthly repayment formula.
   * @param {number} loan
   * @param {number} annualRatePct  e.g. 6.5
   * @returns {number}
   */
  function calcMonthlyRepayment(loan, annualRatePct, loanTermMonths) {
    const r = annualRatePct / 100 / 12;
    const n = loanTermMonths || DEFAULT_LENDING_CONSTANTS.loan_term_months;
    if (r === 0) return loan / n;
    return loan * r * Math.pow(1 + r, n) / (Math.pow(1 + r, n) - 1);
  }

  // ─── Public: calculateBuyingPosition ──────────────────────────────────────
  /**
   * Top-level function. Runs all three ceiling checks and returns a combined result.
   * This is what the Gemini agent calls.
   *
   * @param {{
   *   // C1 — deposit
   *   savings:          number,
   *   state:            string,   // 'NSW'|'VIC'|'QLD'|'WA'|'SA'|'TAS'|'ACT'|'NT'
   *   propertyType:     string,   // 'house'|'apartment'|'townhouse'
   *   isOwnerOccupier:  boolean,
   *   isFirstHomeBuyer: boolean,
   *   isNewBuild:       boolean,
   *   isHBCS:           boolean,
   *
   *   // C2 — debt-to-income
   *   grossIncome1:    number,   // annual gross income person 1
   *   grossIncome2:    number,   // annual gross income person 2 (0 if sole)
   *   creditCardLimits: number,  // total approved limits
   *   mortgages:       [{balance, isInvestment, weeklyRent}],
   *   otherLoans:      [{amount, monthlyRepayment}],
   *   rentalIncome:    number,   // weekly rent on new purchase (investment path)
   *
   *   // C3 — serviceability
   *   takeHome1:       number,
   *   takeHome1Freq:   string,
   *   takeHome2:       number,
   *   takeHome2Freq:   string,
   *   hemMonthly:      number,   // monthly living expenses (HEM benchmark)
   *   rent:            number,   // monthly rent paid
   *   schoolFees:      number,   // monthly school fees
   *   healthInsurance: number,   // monthly health insurance
   *   stressRateAnnual: number,  // default 9.0
   *
   *   // Optional: pass live Supabase data to override hardcoded tables
   *   lmiRates:        Array,
   *   regFees:         object,   // { NSW: 670, ... }
   *   lmiSdRates:      object,   // { NSW: 0.09, ... }
   *   sdBrackets:      Array,    // rows from stamp_duty_brackets (all states)
   *   sdConcessions:   object,   // { state → { concession_key → value } }
   *   ntDutyFormula:   object,   // single row from nt_duty_formula
   * }} inputs
   *
   * @returns {{
   *   c1Price: number, c2Price: number, c3Price: number,
   *   maximum: number, bindingCeiling: 'deposit'|'dti'|'serviceability',
   *   dti: object, svc: object,
   *   c1Result: object|null, c2Result: object|null, c3Result: object|null,
   * }}
   */
  function calculateBuyingPosition(inputs) {
    const {
      savings          = 0,
      state            = 'NSW',
      propertyType     = 'house',
      isOwnerOccupier  = true,
      isFirstHomeBuyer = false,
      isNewBuild       = false,
      isHBCS           = false,

      grossIncome1     = 0,
      grossIncome2     = 0,
      creditCardLimits = 0,
      mortgages        = [],
      otherLoans       = [],
      rentalIncome     = 0,

      takeHome1        = 0,
      takeHome1Freq    = 'monthly',
      takeHome2        = 0,
      takeHome2Freq    = 'monthly',
      hemMonthly       = 3500,
      rent             = 0,
      schoolFees       = 0,
      healthInsurance  = 0,
      stressRateAnnual = 9.0,

      lmiRates,
      regFees: regFeesIn,
      lmiSdRates: lmiSdRatesIn,
      sdBrackets,
      sdConcessions,
      ntDutyFormula,
      lvrLimits,
      lendingConstants,
    } = inputs;

    const baseOpts = {
      state,
      isFHB: isFirstHomeBuyer,
      isOO: isOwnerOccupier,
      isHBCS,
      isNewBuild,
      propType: propertyType,
      lmiRates,
      regFees: regFeesIn,
      lmiSdRates: lmiSdRatesIn,
      sdBrackets,
      sdConcessions,
      ntDutyFormula,
      lvrLimits,
      lendingConstants,
    };

    // ── C1: Deposit ceiling ──
    const c1Result = solveDepositCeiling({ savings, ...baseOpts });
    const c1Price  = c1Result ? c1Result.price : 0;

    // ── C2: DTI ceiling ──
    const dti = solveDTICeiling({
      grossIncome1, grossIncome2,
      rentalIncome, isOO: isOwnerOccupier,
      creditCards: creditCardLimits,
      mortgages, otherLoans,
      lendingConstants,
    });

    let c2Result = null, c2Price = 0;
    if (dti.maxNewMortgage > 0) {
      c2Result = findMaxPriceForLoanCap(dti.maxNewMortgage, { savings, ...baseOpts });
      c2Price  = c2Result ? c2Result.price : 0;
    }

    // ── C3: Serviceability ceiling ──
    // Build mortgage and loan repayment arrays from inputs
    const _loanTerm = (lendingConstants && lendingConstants.loan_term_months) || DEFAULT_LENDING_CONSTANTS.loan_term_months;
    const mortgageRepayments = mortgages.map(m => {
      if (m.monthlyRepayment) return m.monthlyRepayment;
      // Estimate from balance at stress rate if not provided
      const r = stressRateAnnual / 100 / 12;
      const n = _loanTerm;
      return r > 0 ? (m.balance || 0) * r * Math.pow(1+r,n) / (Math.pow(1+r,n)-1) : (m.balance || 0) / n;
    });
    const loanRepayments = otherLoans.map(l => l.monthlyRepayment || 0);

    // Rental income for serviceability (same 80% rule as DTI)
    const rentalForSvc = isOwnerOccupier
      ? 0
      : (rentalIncome * 52 * 0.80 + mortgages.filter(m => m.isInvestment).reduce((s, m) => s + (m.weeklyRent || 0) * 52 * 0.80, 0)) / 12;

    const svc = solveServiceabilityCeiling({
      takeHome1, takeHome1Freq, takeHome2, takeHome2Freq,
      rentalIncomeMonthly: rentalForSvc,
      hemAmount: hemMonthly, rent, schoolFees, healthInsurance,
      mortgageRepayments, loanRepayments,
      creditCards: creditCardLimits,
      stressRateAnnual,
      lendingConstants,
    });

    let c3Result = null, c3Price = 0;
    if (svc.maxLoan > 0) {
      c3Result = findMaxPriceForLoanCap(svc.maxLoan, { savings, ...baseOpts });
      c3Price  = c3Result ? c3Result.price : 0;
    }

    // ── Binding ceiling ──
    const prices  = [c1Price, c2Price > 0 ? c2Price : Infinity, c3Price > 0 ? c3Price : Infinity];
    const maximum = prices[0] > 0 || prices[1] < Infinity || prices[2] < Infinity
      ? Math.min(...prices.filter(p => p > 0))
      : 0;

    let bindingCeiling = 'deposit';
    if (c2Price > 0 && c2Price === maximum) bindingCeiling = 'dti';
    else if (c3Price > 0 && c3Price === maximum) bindingCeiling = 'serviceability';

    return {
      c1Price, c2Price, c3Price,
      maximum,
      bindingCeiling,
      dti, svc,
      c1Result, c2Result, c3Result,
    };
  }

  // ─── Exports ──────────────────────────────────────────────────────────────
  return {
    calcStampDuty,
    lookupLMIRate,
    getMaxLVR,
    requiredSavingsForPrice,
    solveDepositCeiling,
    findMaxPriceForLoanCap,
    solveDTICeiling,
    solveServiceabilityCeiling,
    calcMonthlyRepayment,
    calculateBuyingPosition,
    // Expose default tables for inspection / testing
    DEFAULT_LMI_RATES,
    DEFAULT_LMI_SD_RATES,
    DEFAULT_REG_FEES,
    DEFAULT_LENDING_CONSTANTS,
    DEFAULT_LVR_LIMITS,
  };
}));
