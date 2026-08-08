/**
 * GetReal API v1 — Cloudflare Pages Function
 * Catch-all handler for /api/v1/* endpoints.
 *
 * All 15 endpoints. Calculation logic inlined from engine.js.
 * Lookup data loaded live from Supabase on each request.
 *
 * Base URL: https://get-real.co/api/v1/
 * Docs:     https://get-real.co/api/
 */

// ─── Supabase config ─────────────────────────────────────────────────────────
const SB_URL = 'https://lkxzxeeeqfiymunpqvgt.supabase.co';
const SB_KEY = 'sb_publishable_1jyBD0hVdHX2ieqFIlC51A_A3ep39Bc';

async function sbFetch(table, params = '') {
  const r = await fetch(`${SB_URL}/rest/v1/${table}?${params}`, {
    headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` },
  });
  if (!r.ok) throw new Error(`Supabase ${r.status} on ${table}`);
  return r.json();
}

// ─── Default constants (from engine.js) ──────────────────────────────────────

const DEFAULT_LMI_RATES = [
  { lvr_min:80, lvr_max:82,  loan_max:300000,  rate_pct:0.56 },
  { lvr_min:80, lvr_max:82,  loan_max:500000,  rate_pct:0.61 },
  { lvr_min:80, lvr_max:82,  loan_max:750000,  rate_pct:0.75 },
  { lvr_min:80, lvr_max:82,  loan_max:1000000, rate_pct:0.81 },
  { lvr_min:80, lvr_max:82,  loan_max:null,    rate_pct:0.90 },
  { lvr_min:82, lvr_max:84,  loan_max:300000,  rate_pct:0.81 },
  { lvr_min:82, lvr_max:84,  loan_max:500000,  rate_pct:0.87 },
  { lvr_min:82, lvr_max:84,  loan_max:750000,  rate_pct:0.95 },
  { lvr_min:82, lvr_max:84,  loan_max:1000000, rate_pct:1.10 },
  { lvr_min:82, lvr_max:84,  loan_max:null,    rate_pct:1.15 },
  { lvr_min:84, lvr_max:85,  loan_max:300000,  rate_pct:0.87 },
  { lvr_min:84, lvr_max:85,  loan_max:500000,  rate_pct:0.94 },
  { lvr_min:84, lvr_max:85,  loan_max:750000,  rate_pct:1.02 },
  { lvr_min:84, lvr_max:85,  loan_max:1000000, rate_pct:1.20 },
  { lvr_min:84, lvr_max:85,  loan_max:null,    rate_pct:1.25 },
  { lvr_min:85, lvr_max:86,  loan_max:300000,  rate_pct:1.19 },
  { lvr_min:85, lvr_max:86,  loan_max:500000,  rate_pct:1.29 },
  { lvr_min:85, lvr_max:86,  loan_max:750000,  rate_pct:1.41 },
  { lvr_min:85, lvr_max:86,  loan_max:1000000, rate_pct:1.64 },
  { lvr_min:85, lvr_max:86,  loan_max:null,    rate_pct:1.76 },
  { lvr_min:86, lvr_max:87,  loan_max:300000,  rate_pct:1.19 },
  { lvr_min:86, lvr_max:87,  loan_max:500000,  rate_pct:1.29 },
  { lvr_min:86, lvr_max:87,  loan_max:750000,  rate_pct:1.41 },
  { lvr_min:86, lvr_max:87,  loan_max:1000000, rate_pct:1.64 },
  { lvr_min:86, lvr_max:87,  loan_max:null,    rate_pct:1.76 },
  { lvr_min:87, lvr_max:88,  loan_max:300000,  rate_pct:1.25 },
  { lvr_min:87, lvr_max:88,  loan_max:500000,  rate_pct:1.35 },
  { lvr_min:87, lvr_max:88,  loan_max:750000,  rate_pct:1.48 },
  { lvr_min:87, lvr_max:88,  loan_max:1000000, rate_pct:1.73 },
  { lvr_min:87, lvr_max:88,  loan_max:null,    rate_pct:1.85 },
  { lvr_min:88, lvr_max:89,  loan_max:300000,  rate_pct:1.32 },
  { lvr_min:88, lvr_max:89,  loan_max:500000,  rate_pct:1.43 },
  { lvr_min:88, lvr_max:89,  loan_max:750000,  rate_pct:1.56 },
  { lvr_min:88, lvr_max:89,  loan_max:1000000, rate_pct:1.82 },
  { lvr_min:88, lvr_max:89,  loan_max:null,    rate_pct:1.96 },
  { lvr_min:89, lvr_max:90,  loan_max:300000,  rate_pct:1.32 },
  { lvr_min:89, lvr_max:90,  loan_max:500000,  rate_pct:1.43 },
  { lvr_min:89, lvr_max:90,  loan_max:750000,  rate_pct:1.56 },
  { lvr_min:89, lvr_max:90,  loan_max:1000000, rate_pct:1.82 },
  { lvr_min:89, lvr_max:90,  loan_max:null,    rate_pct:1.96 },
  { lvr_min:90, lvr_max:91,  loan_max:300000,  rate_pct:1.63 },
  { lvr_min:90, lvr_max:91,  loan_max:500000,  rate_pct:1.80 },
  { lvr_min:90, lvr_max:91,  loan_max:750000,  rate_pct:2.12 },
  { lvr_min:90, lvr_max:91,  loan_max:1000000, rate_pct:2.27 },
  { lvr_min:90, lvr_max:91,  loan_max:null,    rate_pct:2.27 },
  { lvr_min:91, lvr_max:92,  loan_max:300000,  rate_pct:1.73 },
  { lvr_min:91, lvr_max:92,  loan_max:500000,  rate_pct:1.88 },
  { lvr_min:91, lvr_max:92,  loan_max:750000,  rate_pct:2.22 },
  { lvr_min:91, lvr_max:92,  loan_max:1000000, rate_pct:2.37 },
  { lvr_min:91, lvr_max:92,  loan_max:null,    rate_pct:2.37 },
  { lvr_min:92, lvr_max:93,  loan_max:300000,  rate_pct:1.87 },
  { lvr_min:92, lvr_max:93,  loan_max:500000,  rate_pct:2.05 },
  { lvr_min:92, lvr_max:93,  loan_max:750000,  rate_pct:2.41 },
  { lvr_min:92, lvr_max:93,  loan_max:1000000, rate_pct:2.58 },
  { lvr_min:92, lvr_max:93,  loan_max:null,    rate_pct:2.58 },
  { lvr_min:93, lvr_max:94,  loan_max:300000,  rate_pct:2.13 },
  { lvr_min:93, lvr_max:94,  loan_max:500000,  rate_pct:2.30 },
  { lvr_min:93, lvr_max:94,  loan_max:750000,  rate_pct:2.73 },
  { lvr_min:93, lvr_max:94,  loan_max:1000000, rate_pct:2.94 },
  { lvr_min:93, lvr_max:94,  loan_max:null,    rate_pct:2.94 },
  { lvr_min:94, lvr_max:95,  loan_max:300000,  rate_pct:2.13 },
  { lvr_min:94, lvr_max:95,  loan_max:500000,  rate_pct:2.30 },
  { lvr_min:94, lvr_max:95,  loan_max:750000,  rate_pct:2.73 },
  { lvr_min:94, lvr_max:95,  loan_max:1000000, rate_pct:2.94 },
  { lvr_min:94, lvr_max:95,  loan_max:null,    rate_pct:2.94 },
  { lvr_min:95, lvr_max:97,  loan_max:300000,  rate_pct:3.14 },
  { lvr_min:95, lvr_max:97,  loan_max:500000,  rate_pct:3.35 },
  { lvr_min:95, lvr_max:97,  loan_max:750000,  rate_pct:3.70 },
  { lvr_min:95, lvr_max:97,  loan_max:1000000, rate_pct:3.70 },
  { lvr_min:95, lvr_max:97,  loan_max:null,    rate_pct:3.70 },
  { lvr_min:97, lvr_max:100, loan_max:300000,  rate_pct:3.14 },
  { lvr_min:97, lvr_max:100, loan_max:500000,  rate_pct:3.35 },
  { lvr_min:97, lvr_max:100, loan_max:750000,  rate_pct:3.70 },
  { lvr_min:97, lvr_max:100, loan_max:1000000, rate_pct:3.70 },
  { lvr_min:97, lvr_max:100, loan_max:null,    rate_pct:3.70 },
];

const DEFAULT_LMI_SD_RATES = { NSW:0.09, VIC:0.10, QLD:0.09, WA:0.10, SA:0.11, TAS:0.10, ACT:0.06, NT:0.10 };
const DEFAULT_REG_FEES     = { NSW:670,  VIC:1700, QLD:1250, WA:1120, SA:800,  TAS:600,  ACT:1100, NT:500  };
const DEFAULT_LENDING      = { dti_multiplier:6, stress_rate_buffer_pct:3, cc_repayment_rate:0.03, loan_term_months:360 };
const DEFAULT_LVR_LIMITS   = [
  { property_type:'standard',  is_owner_occupier:true,  max_lvr:0.95 },
  { property_type:'standard',  is_owner_occupier:false, max_lvr:0.90 },
  { property_type:'apartment', is_owner_occupier:true,  max_lvr:0.90 },
  { property_type:'apartment', is_owner_occupier:false, max_lvr:0.80 },
];

// ─── Calculation functions (engine.js parity) ────────────────────────────────

function _brackets(price, tbl) {
  for (const b of tbl) {
    if (price <= b.max) return b.base + (price - b.min) * b.rate;
  }
  return 0;
}
function _nswDuty(p) { return _brackets(p, [ {min:0,max:16000,base:0,rate:0.0125},{min:16000,max:35000,base:200,rate:0.015},{min:35000,max:93000,base:485,rate:0.0175},{min:93000,max:351000,base:1500,rate:0.035},{min:351000,max:1168000,base:10530,rate:0.045},{min:1168000,max:3505000,base:47295,rate:0.055},{min:3505000,max:Infinity,base:175830,rate:0.07} ]); }
function _vicGeneral(p) { if(p<=25000)return p*0.014; if(p<=130000)return 350+(p-25000)*0.024; if(p<=960000)return 2870+(p-130000)*0.06; if(p<=2000000)return p*0.055; return 110000+(p-2000000)*0.065; }
function _vicPPR(p) { if(p<=25000)return p*0.014; if(p<=130000)return 350+(p-25000)*0.024; if(p<=440000)return 2870+(p-130000)*0.05; if(p<=550000)return 18370+(p-440000)*0.06; return _vicGeneral(p); }
function _qldDuty(p) { return _brackets(p, [ {min:0,max:5000,base:0,rate:0},{min:5000,max:75000,base:0,rate:0.015},{min:75000,max:540000,base:1050,rate:0.035},{min:540000,max:1000000,base:17325,rate:0.045},{min:1000000,max:Infinity,base:38025,rate:0.0575} ]); }
function _waDuty(p)  { return _brackets(p, [ {min:0,max:120000,base:0,rate:0.019},{min:120000,max:150000,base:2280,rate:0.0285},{min:150000,max:360000,base:3135,rate:0.038},{min:360000,max:725000,base:11115,rate:0.0475},{min:725000,max:Infinity,base:28453,rate:0.0515} ]); }
function _saDuty(p)  { return _brackets(p, [ {min:0,max:12000,base:0,rate:0.01},{min:12000,max:30000,base:120,rate:0.02},{min:30000,max:50000,base:480,rate:0.03},{min:50000,max:100000,base:1080,rate:0.035},{min:100000,max:200000,base:2830,rate:0.04},{min:200000,max:250000,base:6830,rate:0.0425},{min:250000,max:300000,base:8955,rate:0.0475},{min:300000,max:500000,base:11330,rate:0.05},{min:500000,max:Infinity,base:21330,rate:0.055} ]); }
function _tasDuty(p) { if(p<=3000)return 50; if(p<=25000)return 50+(p-3000)*0.0175; if(p<=75000)return 435+(p-25000)*0.0225; if(p<=200000)return 1560+(p-75000)*0.035; if(p<=375000)return 5935+(p-200000)*0.04; if(p<=725000)return 12935+(p-375000)*0.0425; return 27810+(p-725000)*0.045; }
function _actDuty(p) { return _brackets(p, [ {min:0,max:200000,base:0,rate:0.022},{min:200000,max:300000,base:4400,rate:0.034},{min:300000,max:500000,base:7800,rate:0.0432},{min:500000,max:750000,base:16440,rate:0.059},{min:750000,max:1000000,base:31190,rate:0.064},{min:1000000,max:1455000,base:47190,rate:0.072},{min:1455000,max:Infinity,base:80034,rate:0.0454} ]); }
function _ntDuty(p)  { if(p<=525000){const V=p/1000;return 0.06571441*V*V+15*V;} return p*0.0495; }

function _supabaseBrackets(price, brackets) {
  for (const b of brackets) {
    const maxVal = b.bracket_max === null ? Infinity : b.bracket_max;
    if (price <= maxVal) {
      return b.is_full_price ? price * b.rate : b.base_amount + (price - b.bracket_min) * b.rate;
    }
  }
  return 0;
}

function _fhbHardcoded(price, full, state) {
  switch(state) {
    case 'NSW': if(price<=800000)return 0; if(price<=1000000)return Math.round(full*(price-800000)/200000); return Math.round(full);
    case 'VIC': if(price<=600000)return 0; if(price<=750000)return Math.round(full*(price-600000)/150000); return Math.round(full);
    case 'QLD': if(price<=500000)return 0; if(price<=550000)return Math.round(full*(price-500000)/50000); return Math.round(full);
    case 'WA':  if(price<=600000)return 0; if(price<=800000)return Math.round(full*(price-600000)/200000); return Math.round(full);
    case 'TAS': if(price<600000)return Math.round(full*0.5); return Math.round(full);
    default: return Math.round(full);
  }
}

function _calcDutySupabase(price, ctx, sdBrackets, sdConcessions, ntFormula) {
  const { state, isFHB=false, isOO=true, isHBCS=false } = ctx;
  if (state === 'NT') {
    if (!ntFormula) return null;
    const V = price / ntFormula.divisor;
    const full = price <= ntFormula.formula_threshold
      ? ntFormula.coeff_a * V * V + ntFormula.coeff_b * V
      : price * ntFormula.flat_rate_above;
    if (isFHB) {
      const conc = sdConcessions && sdConcessions['NT'];
      const priceCap = (conc && conc.fhb_price_cap) || 650000;
      const phaseStart = (conc && conc.fhb_phaseout_start) || 500000;
      const maxDiscount = (conc && conc.fhb_max_discount) || 18601;
      if (price < priceCap) {
        const factor = price <= phaseStart ? 1 : (priceCap - price) / (priceCap - phaseStart);
        return Math.max(0, Math.round(full - Math.min(full, maxDiscount * factor)));
      }
    }
    return Math.round(full);
  }
  const stateBrackets = sdBrackets.filter(b => b.state === state);
  if (!stateBrackets.length) return null;
  if (state === 'ACT' && (isFHB || isHBCS)) return 0;
  const bracketSet = (state === 'VIC' && !isFHB && isOO && price <= 550000) ? 'vic_ppr' : 'standard';
  const selected = stateBrackets.filter(b => b.bracket_set === bracketSet).sort((a,b) => a.bracket_min - b.bracket_min);
  if (!selected.length) return null;
  const full = _supabaseBrackets(price, selected);
  if (!isFHB) return Math.round(full);
  const conc = sdConcessions && sdConcessions[state];
  if (conc && conc.fhb_exempt_threshold !== undefined && conc.fhb_taper_top !== undefined) {
    if (price <= conc.fhb_exempt_threshold) return 0;
    if (price <= conc.fhb_taper_top) return Math.round(full * (price - conc.fhb_exempt_threshold) / (conc.fhb_taper_top - conc.fhb_exempt_threshold));
    return Math.round(full);
  }
  if (conc && conc.fhb_discount_pct !== undefined && conc.fhb_price_cap !== undefined) {
    if (price < conc.fhb_price_cap) return Math.round(full * (1 - conc.fhb_discount_pct / 100));
    return Math.round(full);
  }
  return _fhbHardcoded(price, full, state);
}

function calcStampDuty(price, ctx, sdBrackets, sdConcessions, ntFormula) {
  if (sdBrackets && sdBrackets.length) {
    const r = _calcDutySupabase(price, ctx, sdBrackets, sdConcessions, ntFormula);
    if (r !== null) return r;
  }
  const { state, isFHB=false, isOO=true, isHBCS=false } = ctx;
  switch(state) {
    case 'NSW': { const f=_nswDuty(price); if(isFHB){if(price<=800000)return 0; if(price<=1000000)return Math.round(f*(price-800000)/200000);} return Math.round(f); }
    case 'VIC': { if(isFHB){const f=_vicGeneral(price);if(price<=600000)return 0;if(price<=750000)return Math.round(f*(price-600000)/150000);return Math.round(f);} if(isOO&&price<=550000)return Math.round(_vicPPR(price)); return Math.round(_vicGeneral(price)); }
    case 'QLD': { const f=_qldDuty(price); if(isFHB){if(price<=500000)return 0;if(price<=550000)return Math.round(f*(price-500000)/50000);} return Math.round(f); }
    case 'WA':  { const f=_waDuty(price);  if(isFHB){if(price<=600000)return 0;if(price<=800000)return Math.round(f*(price-600000)/200000);} return Math.round(f); }
    case 'SA':  return Math.round(_saDuty(price));
    case 'TAS': { const f=_tasDuty(price); if(isFHB&&price<600000)return Math.round(f*0.5); return Math.round(f); }
    case 'ACT': if(isFHB||isHBCS)return 0; return Math.round(_actDuty(price));
    case 'NT':  { const f=_ntDuty(price); if(isFHB&&price<650000){const factor=price<=500000?1:(650000-price)/150000;return Math.max(0,Math.round(f-Math.min(f,18601*factor)));} return Math.round(f); }
    default: return 0;
  }
}

function lookupLMIRate(lvrPct, baseLoan, lmiRates) {
  const rates = lmiRates || DEFAULT_LMI_RATES;
  const match = rates.filter(r => lvrPct > r.lvr_min && lvrPct <= r.lvr_max);
  if (!match.length) return 0;
  const exact = match.find(r => r.loan_max === null || baseLoan <= r.loan_max);
  return (exact || match[match.length-1]).rate_pct / 100;
}

function getMaxLVR(ctx, lvrLimits) {
  const { propType, isOO=true } = ctx;
  const propKey = propType === 'apartment' ? 'apartment' : 'standard';
  const rows = (lvrLimits && lvrLimits.length) ? lvrLimits : DEFAULT_LVR_LIMITS;
  const row = rows.find(r => r.property_type === propKey && r.is_owner_occupier === isOO);
  return row ? Number(row.max_lvr) : (propKey==='apartment'?(isOO?0.90:0.80):(isOO?0.95:0.90));
}

function calcMonthlyRepayment(loan, annualRatePct, loanTermMonths) {
  const r = annualRatePct / 100 / 12;
  const n = loanTermMonths || DEFAULT_LENDING.loan_term_months;
  if (r === 0) return loan / n;
  return loan * r * Math.pow(1+r,n) / (Math.pow(1+r,n)-1);
}

function _computeAtPrice(price, savings, maxLVR, stampDuty, regFee, lmiSdRate, lmiRates) {
  let lmiSd=0, lmiPremium=0, availDeposit, baseLoan, baseLVR, effectiveLoan, effectiveLVR;
  for (let i=0; i<6; i++) {
    const upfront = stampDuty + regFee + lmiSd;
    availDeposit = savings - upfront;
    if (availDeposit <= 0) return null;
    baseLoan = price - availDeposit;
    if (baseLoan <= 0) return null;
    baseLVR = baseLoan / price;
    if (baseLVR > maxLVR) return null;
    if (baseLVR <= 0.80) { lmiPremium=0; lmiSd=0; effectiveLoan=baseLoan; effectiveLVR=baseLVR; break; }
    const rate = lookupLMIRate(baseLVR*100, baseLoan, lmiRates);
    lmiPremium = baseLoan * rate;
    effectiveLoan = baseLoan + lmiPremium;
    effectiveLVR = effectiveLoan / price;
    if (effectiveLVR > maxLVR) return null;
    lmiSd = lmiPremium * lmiSdRate;
  }
  return { price, stampDuty, regFee, lmiSd:Math.round(lmiSd), availDeposit, baseLoan, baseLVR, lmiPremium:Math.round(lmiPremium), effectiveLoan:Math.round(effectiveLoan), effectiveLVR };
}

function solveDepositCeiling(opts) {
  const { savings, state, isFHB=false, isOO=true, isHBCS=false, isNewBuild=false, propType='house',
    lmiRates, regFees, lmiSdRates, sdBrackets, sdConcessions, ntDutyFormula, lvrLimits } = opts;
  if (!savings || savings <= 0) return null;
  const maxLVR   = getMaxLVR({ propType, isOO }, lvrLimits);
  const regFee   = (regFees && regFees[state]) || DEFAULT_REG_FEES[state] || 400;
  const lmiSdRate= (lmiSdRates && lmiSdRates[state]) || DEFAULT_LMI_SD_RATES[state] || 0;
  const ctx      = { state, isFHB, isOO, isHBCS, isNewBuild, propType };
  let lo=0, hi=Math.min(Math.ceil(savings*25),15000000), best=null;
  for (let i=0; i<60; i++) {
    const mid = Math.floor((lo+hi)/2);
    if (mid<=0){hi=mid-1;continue;}
    const duty = calcStampDuty(mid, ctx, sdBrackets, sdConcessions, ntDutyFormula);
    const r = _computeAtPrice(mid, savings, maxLVR, duty, regFee, lmiSdRate, lmiRates);
    if (r) {best=r;lo=mid+1;} else {hi=mid-1;}
  }
  return best;
}

function findMaxPriceForLoanCap(loanCap, opts) {
  const { savings, state, isFHB=false, isOO=true, isHBCS=false, isNewBuild=false, propType='house',
    lmiRates, regFees, lmiSdRates, sdBrackets, sdConcessions, ntDutyFormula, lvrLimits } = opts;
  if (loanCap<=0 || !savings || savings<=0) return null;
  const maxLVR   = getMaxLVR({ propType, isOO }, lvrLimits);
  const regFee   = (regFees && regFees[state]) || DEFAULT_REG_FEES[state] || 400;
  const lmiSdRate= (lmiSdRates && lmiSdRates[state]) || DEFAULT_LMI_SD_RATES[state] || 0;
  const ctx      = { state, isFHB, isOO, isHBCS, isNewBuild, propType };
  let lo=0, hi=Math.min(loanCap+savings,15000000), best=null;
  for (let i=0; i<60; i++) {
    const mid = Math.floor((lo+hi)/2);
    if (mid<=0){hi=mid-1;continue;}
    const depositNeeded = mid - loanCap;
    if (depositNeeded < 0){lo=mid+1;continue;}
    const baseLVR = loanCap / mid;
    if (baseLVR > maxLVR){lo=mid+1;continue;}
    const stampDuty = calcStampDuty(mid, ctx, sdBrackets, sdConcessions, ntDutyFormula);
    let lmiPremium=0, lmiSd=0;
    if (baseLVR > 0.80) { const rate=lookupLMIRate(baseLVR*100,loanCap,lmiRates); lmiPremium=Math.round(loanCap*rate); lmiSd=Math.round(lmiPremium*lmiSdRate); }
    const savingsNeeded = depositNeeded + stampDuty + regFee + lmiSd;
    if (savingsNeeded <= savings) { best={price:mid,loanCap,baseLVR,depositNeeded,stampDuty,regFee,lmiPremium,lmiSd,savingsNeeded,effectiveLoan:loanCap+lmiPremium}; lo=mid+1; }
    else { hi=mid-1; }
  }
  return best;
}

function solveDTICeiling(opts) {
  const { grossIncome1=0, grossIncome2=0, rentalIncome=0, isOO=true,
    creditCards=0, mortgages=[], otherLoans=[], lendingConstants } = opts;
  const newPropRental  = isOO ? 0 : rentalIncome * 52 * 0.80;
  const existInvRental = mortgages.filter(m=>m.isInvestment&&m.weeklyRent>0).reduce((s,m)=>s+m.weeklyRent*52*0.80, 0);
  const totalIncome    = grossIncome1 + grossIncome2 + newPropRental + existInvRental;
  const mortgageBalances = mortgages.reduce((s,m)=>s+(m.balance||0), 0);
  const loanBalances     = otherLoans.reduce((s,l)=>s+(l.amount||0), 0);
  const existingDebt     = creditCards + mortgageBalances + loanBalances;
  const dtiMult          = (lendingConstants && lendingConstants.dti_multiplier) || DEFAULT_LENDING.dti_multiplier;
  const maxTotalDebt     = totalIncome * dtiMult;
  const maxNewMortgage   = Math.max(0, maxTotalDebt - existingDebt);
  return { maxNewMortgage, maxTotalDebt, totalIncome, existingDebt, mortgageBalances, loanBalances, newPropRental, existInvRental };
}

function solveServiceabilityCeiling(opts) {
  const { takeHome1=0, takeHome1Freq='monthly', takeHome2=0, takeHome2Freq='monthly',
    rentalIncomeMonthly=0, hemAmount=0, rent=0, schoolFees=0, healthInsurance=0,
    mortgageRepayments=[], loanRepayments=[], creditCards=0, stressRateAnnual=9.0, lendingConstants } = opts;
  const toMonthly = (a,f) => f==='weekly'?a*52/12:f==='fortnightly'?a*26/12:a;
  const netMonthly = toMonthly(takeHome1,takeHome1Freq) + (takeHome2>0?toMonthly(takeHome2,takeHome2Freq):0) + rentalIncomeMonthly;
  const hemMonthly = hemAmount || 0;
  const committedMonthly = (rent||0) + (schoolFees||0) + (healthInsurance||0);
  const mortgageMonthly  = mortgageRepayments.reduce((s,r)=>s+(r||0),0);
  const loanMonthly      = loanRepayments.reduce((s,r)=>s+(r||0),0);
  const CC_RATE = (lendingConstants && lendingConstants.cc_repayment_rate) || DEFAULT_LENDING.cc_repayment_rate;
  const cardMonthly = creditCards * CC_RATE;
  const existingMonthly = mortgageMonthly + loanMonthly + cardMonthly;
  const maxMonthlyRepayment = netMonthly - hemMonthly - committedMonthly - existingMonthly;
  if (maxMonthlyRepayment <= 0) return { maxLoan:0, maxMonthlyRepayment, netMonthly, hemMonthly, committedMonthly, mortgageMonthly, loanMonthly, cardMonthly, existingMonthly, stressRateAnnual };
  const r = stressRateAnnual / 100 / 12;
  const n = (lendingConstants && lendingConstants.loan_term_months) || DEFAULT_LENDING.loan_term_months;
  const maxLoan = r>0 ? maxMonthlyRepayment*(Math.pow(1+r,n)-1)/(r*Math.pow(1+r,n)) : maxMonthlyRepayment*n;
  return { maxLoan:Math.round(maxLoan), maxMonthlyRepayment, netMonthly, hemMonthly, committedMonthly, mortgageMonthly, loanMonthly, cardMonthly, existingMonthly, stressRateAnnual };
}

// ─── Score functions (search.html parity) ────────────────────────────────────

const FALLBACK_CURVE = [[0.50,0.02],[0.60,0.05],[0.70,0.12],[0.75,0.18],[0.80,0.26],[0.85,0.33],[0.90,0.40],[0.95,0.45],[1.00,0.50],[1.05,0.55],[1.10,0.62],[1.15,0.67],[1.20,0.72],[1.30,0.80],[1.40,0.86],[1.50,0.90],[1.75,0.94],[2.00,0.97]];

function interpolateCurve(tbl, ratio) {
  if (ratio <= tbl[0][0]) return tbl[0][1];
  if (ratio >= tbl[tbl.length-1][0]) return tbl[tbl.length-1][1];
  for (let i=0; i<tbl.length-1; i++) {
    if (ratio >= tbl[i][0] && ratio < tbl[i+1][0]) {
      const t = (ratio-tbl[i][0])/(tbl[i+1][0]-tbl[i][0]);
      return tbl[i][1] + t*(tbl[i+1][1]-tbl[i][1]);
    }
  }
  return 0.50;
}

function getPriceBracket(median) {
  if (median < 500000)  return 'under_500k';
  if (median < 800000)  return '500k_800k';
  if (median < 1200000) return '800k_1200k';
  if (median < 1800000) return '1200k_1800k';
  return 'over_1800k';
}

function buildPriceCurves(rows) {
  // rows from price_curves table: property_type, price_bracket, depth_tier, ratio_thresholds (JSON array)
  // Build: curves[ptype][bracket][tier] = [[ratio, pct], ...]
  const curves = {};
  for (const row of rows) {
    if (!curves[row.property_type]) curves[row.property_type] = {};
    if (!curves[row.property_type][row.price_bracket]) curves[row.property_type][row.price_bracket] = {};
    // ratio_thresholds is an array of {ratio, pct} objects from the table
    const pairs = Array.isArray(row.ratio_thresholds)
      ? row.ratio_thresholds.map(t => [t.ratio, t.pct])
      : Object.entries(row.ratio_thresholds || {}).map(([k,v]) => [Number(k), v]);
    curves[row.property_type][row.price_bracket][row.depth_tier] = pairs.sort((a,b)=>a[0]-b[0]);
  }
  return curves;
}

function getPricePercentile(ratio, ptype, median, annualSales, priceCurves) {
  if (priceCurves && ptype && median && annualSales !== undefined) {
    const bracket = getPriceBracket(median);
    const tier = annualSales >= 30 ? 'active' : 'thin';
    const ptypes = ptype === 'townhouse' ? ['townhouse','house'] : [ptype];
    for (const pt of ptypes) {
      const curve = priceCurves[pt]?.[bracket]?.[tier];
      if (curve) return interpolateCurve(curve, ratio);
    }
  }
  return interpolateCurve(FALLBACK_CURVE, ratio);
}

function calcScore(median, annualSales, budget, priceCurves, propertyType=null) {
  if (!median) return null;
  const ratio = budget / median;
  const pricePct = getPricePercentile(ratio, propertyType, median, annualSales || 1, priceCurves);
  const score = Math.round(pricePct * 100);
  return { score, ratio, pricePct, annualSales, median };
}

function scoreLabel(score) {
  if (score >= 75) return { label:'very_strong',  description:'You can access roughly 3 in 4 properties that sold in this market.' };
  if (score >= 55) return { label:'strong',        description:'You can access roughly half or more of properties that sold in this market.' };
  if (score >= 35) return { label:'comfortable',   description:'You can access roughly a third of properties that sold in this market.' };
  if (score >= 15) return { label:'tight',         description:'You can access roughly 1 in 5 properties that sold in this market.' };
  if (score >=  5) return { label:'very_tight',    description:'Very few properties that sold here are within your budget.' };
  return                  { label:'out_of_range',  description:'Almost no properties that sold here are within your budget.' };
}

// ─── Supabase data loaders ────────────────────────────────────────────────────

async function loadCeilingData() {
  const [sdBracketsRaw, sdConcessionsRaw, ntFormulaRaw, lmiRatesRaw, lmiSdRaw,
    regFeesRaw, ratesRaw, hemRaw, lvrRaw, lcRaw] = await Promise.all([
    sbFetch('stamp_duty_brackets', 'select=*&order=state,bracket_min'),
    sbFetch('stamp_duty_concessions', 'select=*'),
    sbFetch('nt_duty_formula', 'select=*&limit=1'),
    sbFetch('lmi_rates', 'select=*&order=lvr_min,loan_max'),
    sbFetch('lmi_stamp_duty_rates', 'select=*'),
    sbFetch('registration_fees', 'select=*'),
    sbFetch('benchmark_rates', 'select=purpose,rate_pct,reference_month&repayment_type=eq.pi&loan_status=eq.new&rate_type=is.null&lvr_band=is.null&loan_size_band=is.null&order=reference_month.desc&limit=4'),
    sbFetch('hem_benchmarks', 'select=*'),
    sbFetch('lvr_limits', 'select=*'),
    sbFetch('lending_policy_constants', 'select=*'),
  ]);

  // Transform concessions: { state → { key → value } }
  const sdConcessions = {};
  for (const r of sdConcessionsRaw) {
    if (!sdConcessions[r.state]) sdConcessions[r.state] = {};
    sdConcessions[r.state][r.concession_key] = r.value;
  }

  // Transform regFees: { state → total amount }
  const regFees = {};
  for (const r of regFeesRaw) regFees[r.state] = (regFees[r.state] || 0) + r.amount;

  // Transform lmiSdRates: { state → decimal rate }
  const lmiSdRates = {};
  for (const r of lmiSdRaw) lmiSdRates[r.state] = r.rate_pct / 100;

  // Transform lendingConstants: { key → number }
  const lendingConstants = {};
  for (const r of lcRaw) lendingConstants[r.key] = Number(r.value);

  // Transform benchmarkRates: { purpose → rate_pct }
  const benchmarkRates = {};
  for (const r of ratesRaw) { if (!benchmarkRates[r.purpose]) benchmarkRates[r.purpose] = r; }

  const ntDutyFormula = ntFormulaRaw[0] || null;
  const stressBuffer = (lendingConstants.stress_rate_buffer_pct || DEFAULT_LENDING.stress_rate_buffer_pct);
  const ooRate = benchmarkRates['oo'] ? benchmarkRates['oo'].rate_pct : 6.14;
  const stressRate = ooRate + stressBuffer;

  return {
    sdBrackets: sdBracketsRaw,
    sdConcessions,
    ntDutyFormula,
    lmiRates: lmiRatesRaw,
    lmiSdRates,
    regFees,
    hemData: hemRaw,
    lvrLimits: lvrRaw,
    lendingConstants,
    benchmarkRates,
    ooRate,
    stressRate,
  };
}

async function loadSuburb(suburb, state, propertyType) {
  const suburbNorm = suburb.toLowerCase().trim();
  const params = `suburb=eq.${encodeURIComponent(suburbNorm)}&state=eq.${state}&property_type=eq.${propertyType}&select=suburb,suburb_display,state,property_type,median_price,annual_sales,data_year&limit=1`;
  const rows = await sbFetch('suburb_analytics', params);
  return rows[0] || null;
}

async function loadSuburbAllTypes(suburb, state) {
  const suburbNorm = suburb.toLowerCase().trim();
  const params = `suburb=eq.${encodeURIComponent(suburbNorm)}&state=eq.${state}&select=suburb,suburb_display,state,property_type,median_price,annual_sales,data_year`;
  return sbFetch('suburb_analytics', params);
}

async function loadPriceCurves() {
  const rows = await sbFetch('price_curves', 'select=*');
  return buildPriceCurves(rows);
}

async function loadAllSuburbsForState(state, propertyType) {
  const params = `state=eq.${state}&property_type=eq.${propertyType}&select=suburb,suburb_display,median_price,annual_sales&order=suburb`;
  return sbFetch('suburb_analytics', params);
}

function getHEM(hemData, householdType, dependants, locationType) {
  if (!hemData || !hemData.length) return 3500;
  const hh = householdType || 'single';
  const dep = Math.min(dependants || 0, 4);
  const loc = locationType || 'metro';
  const row = hemData.find(r => r.household_type === hh && r.dependants === dep && r.location_type === loc)
    || hemData.find(r => r.household_type === hh && r.location_type === loc)
    || hemData[0];
  return row ? row.monthly_amount : 3500;
}

// ─── Input helpers ────────────────────────────────────────────────────────────

function buyerTypeToFlags(buyerType) {
  switch ((buyerType || 'owner').toLowerCase()) {
    case 'fhb': return { isFHB: true,  isOO: true  };
    case 'investor': return { isFHB: false, isOO: false };
    default:         return { isFHB: false, isOO: true  };
  }
}

function require(body, ...fields) {
  for (const f of fields) {
    if (body[f] === undefined || body[f] === null) throw { code: 'MISSING_PARAM', field: f };
  }
}

function err(status, message, code = 'ERROR') {
  return new Response(JSON.stringify({ error: message, code }), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

function ok(data) {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { 'Content-Type': 'application/json', ...CORS_HEADERS },
  });
}

const CORS_HEADERS = {
  'Access-Control-Allow-Origin':  '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
};

// ─── Endpoint handlers ────────────────────────────────────────────────────────

async function handleStampDuty(body) {
  require(body, 'price', 'state');
  const { price, state, buyer_type='owner', is_owner_occupier=true, is_new_build=false } = body;
  const { isFHB, isOO } = buyerTypeToFlags(buyer_type);
  const ld = await loadCeilingData();
  const ctx = { state, isFHB, isOO, isNewBuild: is_new_build, propType: 'house' };
  const ctxNoFHB = { ...ctx, isFHB: false };
  const gross = calcStampDuty(price, ctxNoFHB, ld.sdBrackets, ld.sdConcessions, ld.ntDutyFormula);
  const payable = calcStampDuty(price, ctx, ld.sdBrackets, ld.sdConcessions, ld.ntDutyFormula);
  const regFees = (ld.regFees[state] || DEFAULT_REG_FEES[state] || 400);
  const concessionApplied = isFHB && payable < gross ? 'fhb_concession' : 'none';
  return ok({
    gross_stamp_duty: gross,
    concession_applied: concessionApplied,
    concession_amount: gross - payable,
    net_stamp_duty: payable,
    registration_fees: regFees,
    total_upfront_government_costs: payable + regFees,
    state,
    price,
  });
}

async function handleLMI(body) {
  require(body, 'purchase_price', 'deposit', 'state');
  const { purchase_price, deposit, state } = body;
  const loan = purchase_price - deposit;
  if (loan <= 0) return err(400, 'Deposit exceeds purchase price', 'INVALID_INPUT');
  const lvrPct = (loan / purchase_price) * 100;
  if (lvrPct <= 80) {
    return ok({ lvr_pct: Math.round(lvrPct*10)/10, loan_amount: loan, lmi_premium: 0, lmi_stamp_duty: 0, total_lmi_cost: 0, lmi_capitalised_loan: loan, notes: ['LVR is 80% or below — no LMI applies.'] });
  }
  const ld = await loadCeilingData();
  const rate = lookupLMIRate(lvrPct, loan, ld.lmiRates);
  const lmiPremium = Math.round(loan * rate);
  const lmiSdRate = (ld.lmiSdRates[state] || DEFAULT_LMI_SD_RATES[state] || 0);
  const lmiSd = Math.round(lmiPremium * lmiSdRate);
  return ok({
    lvr_pct: Math.round(lvrPct * 10) / 10,
    loan_amount: loan,
    lmi_premium: lmiPremium,
    lmi_stamp_duty: lmiSd,
    total_lmi_cost: lmiPremium + lmiSd,
    lmi_capitalised_loan: loan + lmiPremium,
    notes: ['LMI applies — LVR exceeds 80%.', 'LMI is typically added to the loan, not paid upfront.'],
  });
}

async function handleRepayments(body) {
  require(body, 'loan_amount');
  const { loan_amount } = body;
  const ld = await loadCeilingData();
  const ooRate = ld.ooRate;
  const rate_pct = body.rate_pct !== undefined ? body.rate_pct : ooRate;
  const term_years = body.term_years || 30;
  const stressRate = ld.stressRate;
  const monthly = Math.round(calcMonthlyRepayment(loan_amount, rate_pct, term_years * 12));
  const monthlyStress = Math.round(calcMonthlyRepayment(loan_amount, stressRate, term_years * 12));
  const totalPaid = monthly * term_years * 12;
  return ok({
    monthly_repayment: monthly,
    annual_repayment: monthly * 12,
    stress_rate_pct: stressRate,
    monthly_repayment_stress_tested: monthlyStress,
    total_interest: totalPaid - loan_amount,
    rate_used: rate_pct,
    term_years,
    rate_source: 'benchmark_rates table (RBA) + APRA 3% buffer',
  });
}

async function handleCeilingDeposit(body) {
  require(body, 'savings', 'state');
  const { savings, state, property_type='house', buyer_type='owner', is_owner_occupier=true, is_new_build=false } = body;
  const { isFHB, isOO } = buyerTypeToFlags(buyer_type);
  const ld = await loadCeilingData();
  const opts = {
    savings, state, isFHB, isOO, isNewBuild: is_new_build, propType: property_type,
    lmiRates: ld.lmiRates, regFees: ld.regFees, lmiSdRates: ld.lmiSdRates,
    sdBrackets: ld.sdBrackets, sdConcessions: ld.sdConcessions, ntDutyFormula: ld.ntDutyFormula,
    lvrLimits: ld.lvrLimits,
  };
  const result = solveDepositCeiling(opts);
  if (!result) return err(422, 'Savings are insufficient to purchase any property in this state.', 'INSUFFICIENT_SAVINGS');
  const ctx = { state, isFHB, isOO, isNewBuild: is_new_build, propType: property_type };
  const dutyFull = calcStampDuty(result.price, { ...ctx, isFHB: false }, ld.sdBrackets, ld.sdConcessions, ld.ntDutyFormula);
  const maxLVR = getMaxLVR({ propType: property_type, isOO }, ld.lvrLimits);
  const monthly = Math.round(calcMonthlyRepayment(result.effectiveLoan, ld.stressRate, 360));
  const notes = [];
  if (result.lmiPremium > 0) notes.push('LMI applies — LVR exceeds 80%.');
  if (isFHB && result.stampDuty < dutyFull) notes.push(`FHB concession applied — saves $${(dutyFull - result.stampDuty).toLocaleString()} in stamp duty.`);
  return ok({
    max_price: result.price,
    stamp_duty: result.stampDuty,
    stamp_duty_full: dutyFull,
    concession_applied: isFHB && result.stampDuty < dutyFull ? 'fhb_concession' : 'none',
    lmi_premium: result.lmiPremium,
    lmi_stamp_duty: result.lmiSd,
    registration_fees: result.regFee,
    net_deposit: result.availDeposit,
    loan_amount: result.effectiveLoan,
    lvr_pct: Math.round(result.baseLVR * 1000) / 10,
    max_lvr_ceiling: Math.round(maxLVR * 100),
    monthly_repayment_estimate: monthly,
    assessment_rate_used: ld.stressRate,
    notes,
  });
}

async function handleCeilingDepositMinIncome(body) {
  require(body, 'savings', 'state');
  const { savings, state, property_type='house', buyer_type='owner', is_owner_occupier=true, is_new_build=false,
    household_type='single', dependants=0, location_type='metro' } = body;
  const { isFHB, isOO } = buyerTypeToFlags(buyer_type);
  const ld = await loadCeilingData();
  const baseOpts = {
    savings, state, isFHB, isOO, isNewBuild: is_new_build, propType: property_type,
    lmiRates: ld.lmiRates, regFees: ld.regFees, lmiSdRates: ld.lmiSdRates,
    sdBrackets: ld.sdBrackets, sdConcessions: ld.sdConcessions, ntDutyFormula: ld.ntDutyFormula,
    lvrLimits: ld.lvrLimits,
  };
  const result = solveDepositCeiling(baseOpts);
  if (!result) return err(422, 'Savings are insufficient.', 'INSUFFICIENT_SAVINGS');
  const hemMonthly = getHEM(ld.hemData, household_type, dependants, location_type);
  const dtiMult = (ld.lendingConstants.dti_multiplier || DEFAULT_LENDING.dti_multiplier);
  const minGrossIncomeDTI = Math.ceil(result.effectiveLoan / dtiMult);
  const monthly = Math.round(calcMonthlyRepayment(result.effectiveLoan, ld.stressRate, 360));
  const minNetIncomeServiceability = monthly + hemMonthly;
  return ok({
    ceiling_price: result.price,
    loan_at_ceiling: result.effectiveLoan,
    stamp_duty: result.stampDuty,
    lmi_premium: result.lmiPremium,
    net_deposit: result.availDeposit,
    lvr_pct: Math.round(result.baseLVR * 1000) / 10,
    min_gross_income_dti: minGrossIncomeDTI,
    min_net_income_serviceability: minNetIncomeServiceability,
    min_net_income_note: `Monthly net income needed to service loan at HEM floor (${household_type}, ${dependants} dep., ${location_type}), no other debts`,
    hem_floor_monthly: hemMonthly,
    stress_rate_used: ld.stressRate,
  });
}

async function handleCeilingDTI(body) {
  require(body, 'gross_income_1');
  const { gross_income_1=0, gross_income_2=0, existing_mortgages=[], credit_card_limit=0, other_loans=[], is_owner_occupier=true } = body;
  const ld = await loadCeilingData();
  const dti = solveDTICeiling({
    grossIncome1: gross_income_1, grossIncome2: gross_income_2,
    creditCards: credit_card_limit, isOO: is_owner_occupier,
    mortgages: (existing_mortgages || []).map(m => ({ balance: m.balance || 0, isInvestment: m.is_rental || false, weeklyRent: m.weekly_rent || 0 })),
    otherLoans: (other_loans || []).map(l => ({ amount: l.balance || 0 })),
    lendingConstants: ld.lendingConstants,
  });
  return ok({
    max_new_loan: dti.maxNewMortgage,
    gross_income_total: dti.totalIncome,
    dti_cap: dti.maxTotalDebt,
    existing_debt_total: dti.existingDebt,
    credit_card_counted: credit_card_limit,
    dti_ratio_if_max_borrowed: dti.maxNewMortgage > 0 ? Math.round((dti.existingDebt + dti.maxNewMortgage) / dti.totalIncome * 10) / 10 : null,
    dti_multiplier: (ld.lendingConstants.dti_multiplier || DEFAULT_LENDING.dti_multiplier),
    binding: dti.maxNewMortgage === 0,
  });
}

async function handleCeilingServiceability(body) {
  require(body, 'takehome_monthly');
  const { takehome_monthly, household_type='single', dependants=0, location_type='metro',
    existing_loan_repayments_monthly=0, rent_monthly=0, school_fees_annual=0, health_insurance_monthly=0 } = body;
  const ld = await loadCeilingData();
  const stressRate = body.assessment_rate_pct !== undefined ? body.assessment_rate_pct : ld.stressRate;
  const hemMonthly = getHEM(ld.hemData, household_type, dependants, location_type);
  const svc = solveServiceabilityCeiling({
    takeHome1: takehome_monthly, takeHome1Freq: 'monthly',
    hemAmount: hemMonthly,
    rent: rent_monthly,
    schoolFees: school_fees_annual / 12,
    healthInsurance: health_insurance_monthly,
    loanRepayments: existing_loan_repayments_monthly > 0 ? [existing_loan_repayments_monthly] : [],
    stressRateAnnual: stressRate,
    lendingConstants: ld.lendingConstants,
  });
  return ok({
    max_loan: svc.maxLoan,
    monthly_repayment_at_max: Math.round(svc.maxMonthlyRepayment),
    monthly_surplus_at_max: 0,
    hem_floor_monthly: hemMonthly,
    committed_expenses_monthly: Math.round(svc.committedMonthly),
    available_for_repayment: Math.round(svc.maxMonthlyRepayment),
    stress_rate_used: stressRate,
    hem_was_binding: svc.hemMonthly > 0,
  });
}

async function handleCeilingAll(body) {
  require(body, 'savings', 'state', 'gross_income_1', 'takehome_monthly');
  const {
    savings, state, property_type='house', buyer_type='owner', is_owner_occupier=true, is_new_build=false,
    gross_income_1=0, gross_income_2=0, credit_card_limit=0, existing_mortgages=[], other_loans=[],
    takehome_monthly, household_type='single', dependants=0, location_type='metro',
    rent_monthly=0, school_fees_annual=0, health_insurance_monthly=0,
  } = body;
  const { isFHB, isOO } = buyerTypeToFlags(buyer_type);
  const ld = await loadCeilingData();
  const baseOpts = {
    savings, state, isFHB, isOO, isNewBuild: is_new_build, propType: property_type,
    lmiRates: ld.lmiRates, regFees: ld.regFees, lmiSdRates: ld.lmiSdRates,
    sdBrackets: ld.sdBrackets, sdConcessions: ld.sdConcessions, ntDutyFormula: ld.ntDutyFormula,
    lvrLimits: ld.lvrLimits, lendingConstants: ld.lendingConstants,
  };

  // C1: deposit
  const c1Result = solveDepositCeiling(baseOpts);
  const c1Price = c1Result ? c1Result.price : 0;

  // C2: DTI
  const dti = solveDTICeiling({
    grossIncome1: gross_income_1, grossIncome2: gross_income_2,
    creditCards: credit_card_limit, isOO,
    mortgages: (existing_mortgages || []).map(m => ({ balance: m.balance||0, isInvestment: m.is_rental||false, weeklyRent: m.weekly_rent||0 })),
    otherLoans: (other_loans || []).map(l => ({ amount: l.balance||0 })),
    lendingConstants: ld.lendingConstants,
  });
  let c2Result = null, c2Price = 0;
  if (dti.maxNewMortgage > 0) { c2Result = findMaxPriceForLoanCap(dti.maxNewMortgage, { ...baseOpts }); c2Price = c2Result ? c2Result.price : 0; }

  // C3: serviceability
  const hemMonthly = getHEM(ld.hemData, household_type, dependants, location_type);
  const svc = solveServiceabilityCeiling({
    takeHome1: takehome_monthly, takeHome1Freq: 'monthly',
    hemAmount: hemMonthly, rent: rent_monthly,
    schoolFees: school_fees_annual/12, healthInsurance: health_insurance_monthly,
    stressRateAnnual: ld.stressRate, lendingConstants: ld.lendingConstants,
  });
  let c3Result = null, c3Price = 0;
  if (svc.maxLoan > 0) { c3Result = findMaxPriceForLoanCap(svc.maxLoan, { ...baseOpts }); c3Price = c3Result ? c3Result.price : 0; }

  // Binding
  const prices = [c1Price, c2Price>0?c2Price:Infinity, c3Price>0?c3Price:Infinity];
  const effective = Math.min(...prices.filter(p=>p>0));
  let bindingCeiling = 1, bindingLabel = 'Deposit';
  if (c2Price>0 && c2Price===effective){bindingCeiling=2;bindingLabel='Debt-to-income ratio';}
  else if (c3Price>0 && c3Price===effective){bindingCeiling=3;bindingLabel='Serviceability';}

  return ok({
    ceiling_1_deposit: c1Result ? { max_price:c1Price, stamp_duty:c1Result.stampDuty, lmi_premium:c1Result.lmiPremium, net_deposit:c1Result.availDeposit, lvr_pct:Math.round(c1Result.baseLVR*1000)/10 } : null,
    ceiling_2_dti: { max_loan:dti.maxNewMortgage, max_price_implied:c2Price, binding:bindingCeiling===2 },
    ceiling_3_serviceability: { max_loan:svc.maxLoan, max_price_implied:c3Price },
    binding_ceiling: bindingCeiling,
    binding_ceiling_label: bindingLabel,
    effective_max_price: effective === Infinity ? 0 : effective,
    effective_max_loan: (() => { if(bindingCeiling===1&&c1Result)return c1Result.effectiveLoan; if(bindingCeiling===2&&c2Result)return c2Result.effectiveLoan; if(c3Result)return c3Result.effectiveLoan; return 0; })(),
    stress_rate_used: ld.stressRate,
    notes: [`Ceiling ${bindingCeiling} (${bindingLabel}) is your binding constraint.`],
  });
}

async function handleCeilingCheck(body) {
  require(body, 'target_price', 'savings', 'state');
  const allResult = await handleCeilingAll(body);
  const allData = JSON.parse(await allResult.clone().text());
  if (allData.error) return allResult;
  const target = body.target_price;
  const effective = allData.effective_max_price;
  const canAfford = effective >= target;
  const shortfalls = [];
  if (!canAfford) {
    const gap = target - effective;
    if (allData.binding_ceiling === 2) shortfalls.push({ ceiling:2, ceiling_label:'Debt-to-income', shortfall:gap, lever:'Reduce existing debt or increase gross income to expand your DTI ceiling.' });
    else if (allData.binding_ceiling === 3) shortfalls.push({ ceiling:3, ceiling_label:'Serviceability', shortfall:gap, lever:'Increase take-home pay or reduce committed expenses to service a larger loan.' });
    else shortfalls.push({ ceiling:1, ceiling_label:'Deposit', shortfall:gap, lever:'More savings or a higher-LVR lender could extend your deposit ceiling.' });
  }
  return ok({ target_price:target, can_afford:canAfford, shortfalls, ceiling_results:allData });
}

async function handleCeilingDepositSensitivity(body) {
  require(body, 'savings', 'state');
  const { savings, state, property_type='house', buyer_type='owner', is_owner_occupier=true, is_new_build=false,
    scenarios=[25000, 50000, 100000, 150000] } = body;
  const { isFHB, isOO } = buyerTypeToFlags(buyer_type);
  const ld = await loadCeilingData();
  const buildOpts = (s) => ({
    savings:s, state, isFHB, isOO, isNewBuild:is_new_build, propType:property_type,
    lmiRates:ld.lmiRates, regFees:ld.regFees, lmiSdRates:ld.lmiSdRates,
    sdBrackets:ld.sdBrackets, sdConcessions:ld.sdConcessions, ntDutyFormula:ld.ntDutyFormula,
    lvrLimits:ld.lvrLimits,
  });
  const baseResult = solveDepositCeiling(buildOpts(savings));
  if (!baseResult) return err(422, 'Base savings are insufficient.', 'INSUFFICIENT_SAVINGS');
  const scenarioResults = await Promise.all(
    scenarios.map(async (additional) => {
      const r = solveDepositCeiling(buildOpts(savings + additional));
      return r ? { additional, savings: savings+additional, max_price:r.price, lmi:r.lmiPremium>0, lvr_pct:Math.round(r.baseLVR*1000)/10 } : null;
    })
  );
  const lmiEscape = scenarioResults.find(r => r && !r.lmi && baseResult.lmiPremium > 0);
  return ok({
    base: { savings, max_price:baseResult.price, lmi:baseResult.lmiPremium>0, lvr_pct:Math.round(baseResult.baseLVR*1000)/10 },
    scenarios: scenarioResults.filter(Boolean),
    lmi_escape_savings: lmiEscape ? lmiEscape.savings : null,
    lmi_escape_note: lmiEscape ? `At $${lmiEscape.savings.toLocaleString()} savings you cross 80% LVR and avoid LMI entirely, saving approximately $${baseResult.lmiPremium.toLocaleString()}.` : null,
  });
}

async function handleScore(body) {
  require(body, 'suburb', 'state', 'budget');
  const { suburb, state, property_type='house', budget } = body;
  const [suburbRow, priceCurves] = await Promise.all([
    loadSuburb(suburb, state, property_type),
    loadPriceCurves(),
  ]);
  if (!suburbRow) return err(404, `No data found for ${suburb} ${state} ${property_type}`, 'SUBURB_NOT_FOUND');
  const { median_price, annual_sales, suburb_display, data_year } = suburbRow;
  if (!median_price) return err(404, `No median price data for ${suburb} ${state} ${property_type}`, 'NO_PRICE_DATA');
  const scoreResult = calcScore(median_price, annual_sales || 1, budget, priceCurves, property_type);
  if (!scoreResult) return err(500, 'Score calculation failed — missing suburb data', 'SCORE_FAILED');
  const { label, description } = scoreLabel(scoreResult.score);
  const isVIC = state === 'VIC';
  return ok({
    score_pct: scoreResult.score,
    label,
    label_description: description,
    suburb: suburb_display || suburb,
    median_price,
    budget_to_median_ratio: Math.round(scoreResult.ratio * 100) / 100,
    annual_sales,
    methodology: isVIC ? 'vic_estimated' : 'nsw_direct',
    methodology_note: isVIC
      ? 'VIC score estimated from NSW price distribution curves matched by property type, price bracket, and market depth. Individual sale records are not publicly available in VIC.'
      : 'NSW score based on actual sale records from the NSW Valuer General.',
    data_vintage: `${data_year} (VGV annual data)`,
  });
}

async function handleScoreBatch(body) {
  require(body, 'suburbs', 'budget');
  const { suburbs, budget } = body;
  if (!Array.isArray(suburbs) || suburbs.length === 0) return err(400, 'suburbs must be a non-empty array', 'INVALID_INPUT');
  if (suburbs.length > 20) return err(400, 'Maximum 20 suburbs per batch call', 'TOO_MANY_SUBURBS');
  const priceCurves = await loadPriceCurves();
  const results = await Promise.all(suburbs.map(async ({ suburb, state, property_type='house' }) => {
    try {
      const row = await loadSuburb(suburb, state, property_type);
      if (!row) return { suburb, state, property_type, score_pct: null, label: 'not_found', median_price: null };
      const s = calcScore(row.median_price, row.annual_sales, budget, priceCurves);
      const { label } = scoreLabel(s.score);
      return { suburb: row.suburb_display || suburb, state, property_type, score_pct: s.score, label, median_price: row.median_price };
    } catch { return { suburb, state, property_type, score_pct: null, label: 'error', median_price: null }; }
  }));
  results.sort((a,b) => (b.score_pct||0) - (a.score_pct||0));
  return ok({ budget, results, sorted_by: 'score_pct_desc' });
}

async function handleScoreBudgetForScore(body) {
  require(body, 'suburb', 'state', 'target_score_pct');
  const { suburb, state, property_type='house', target_score_pct } = body;
  const [suburbRow, priceCurves] = await Promise.all([
    loadSuburb(suburb, state, property_type),
    loadPriceCurves(),
  ]);
  if (!suburbRow) return err(404, `No data found for ${suburb} ${state} ${property_type}`, 'SUBURB_NOT_FOUND');
  const { median_price, annual_sales } = suburbRow;
  const targetPct = target_score_pct / 100;
  // Binary search for budget that yields the target score
  let lo = median_price * 0.3, hi = median_price * 3, best = null;
  for (let i=0; i<60; i++) {
    const mid = Math.floor((lo+hi)/2);
    const s = calcScore(median_price, annual_sales, mid, priceCurves);
    if (s.pricePct >= targetPct) { best = mid; hi = mid-1; } else { lo = mid+1; }
  }
  if (!best) best = Math.round(median_price * 3);
  const vsMedian = ((best - median_price) / median_price * 100).toFixed(1);
  return ok({
    target_score_pct,
    required_budget: best,
    current_median: median_price,
    budget_vs_median: `${vsMedian >= 0 ? '+' : ''}${vsMedian}%`,
    methodology: state === 'VIC' ? 'vic_estimated' : 'nsw_direct',
  });
}

async function handleScoreSuburbsInRange(body) {
  require(body, 'state', 'budget');
  const { state, property_type='house', budget, min_score_pct=30, limit=20 } = body;
  const [allSuburbs, priceCurves] = await Promise.all([
    loadAllSuburbsForState(state, property_type),
    loadPriceCurves(),
  ]);
  const scored = allSuburbs
    .map(row => {
      const s = calcScore(row.median_price, row.annual_sales, budget, priceCurves);
      const { label } = scoreLabel(s.score);
      return { suburb: row.suburb_display || row.suburb, score_pct: s.score, label, median_price: row.median_price };
    })
    .filter(r => r.score_pct >= min_score_pct)
    .sort((a,b) => b.score_pct - a.score_pct)
    .slice(0, limit);
  return ok({
    budget, state, property_type,
    total_qualifying: scored.length,
    suburbs: scored,
    note: scored.length === limit ? `Results capped at ${limit}. Use min_score_pct to narrow results.` : undefined,
  });
}

async function handleScoreCeiling(body) {
  require(body, 'suburb', 'state', 'savings');
  const { suburb, state, property_type='house' } = body;
  // Run ceiling/all
  const allResponse = await handleCeilingAll(body);
  const allData = JSON.parse(await allResponse.clone().text());
  if (allData.error) return allResponse;
  const effectiveMaxPrice = allData.effective_max_price;
  if (!effectiveMaxPrice) return err(422, 'Could not compute a ceiling price.', 'NO_CEILING');
  // Score the ceiling against the suburb
  const [suburbRow, priceCurves] = await Promise.all([
    loadSuburb(suburb, state, property_type),
    loadPriceCurves(),
  ]);
  if (!suburbRow) return err(404, `No data found for ${suburb} ${state} ${property_type}`, 'SUBURB_NOT_FOUND');
  const s = calcScore(suburbRow.median_price, suburbRow.annual_sales, effectiveMaxPrice, priceCurves);
  const { label, description } = scoreLabel(s.score);
  const isVIC = state === 'VIC';
  let verdict;
  if (s.score >= 55) verdict = `Your ceiling comfortably reaches this suburb — about ${s.score} in 100 properties sold here are within your limit.`;
  else if (s.score >= 35) verdict = `Your ceiling reaches this suburb, but options are limited — about ${s.score} in 100 properties sold here are within your limit.`;
  else if (s.score > 0) verdict = `Your ceiling barely reaches this suburb — only about ${s.score} in 100 properties sold here are within your limit.`;
  else verdict = `Your ceiling does not reach this suburb at the median price level.`;
  return ok({
    ceiling: {
      effective_max_price: effectiveMaxPrice,
      binding_ceiling: allData.binding_ceiling,
      binding_ceiling_label: allData.binding_ceiling_label,
    },
    suburb_score: {
      score_pct: s.score,
      label,
      median_price: suburbRow.median_price,
      budget_used: effectiveMaxPrice,
    },
    verdict,
    methodology: isVIC ? 'vic_estimated' : 'nsw_direct',
  });
}

// ─── Router ───────────────────────────────────────────────────────────────────

export async function onRequest(context) {
  const { request } = context;

  // CORS preflight
  if (request.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: CORS_HEADERS });
  }

  const url = new URL(request.url);
  const segments = context.params.path || [];
  // Strip leading 'v1' if present
  const route = segments.filter(s => s !== 'v1').join('/');

  if (request.method !== 'GET') {
    return err(405, 'Method not allowed. All API endpoints accept GET with query parameters.', 'METHOD_NOT_ALLOWED');
  }

  // Parse query params with automatic type coercion:
  // numbers, booleans, and JSON arrays/objects are coerced; plain strings stay as strings.
  function parseQueryBody(searchParams) {
    const obj = {};
    for (const [k, v] of searchParams) {
      try { obj[k] = JSON.parse(v); } catch { obj[k] = v; }
    }
    return obj;
  }
  const body = parseQueryBody(url.searchParams);

  try {
    switch (route) {
      case 'stamp-duty':                    return await handleStampDuty(body);
      case 'lmi':                           return await handleLMI(body);
      case 'repayments':                    return await handleRepayments(body);
      case 'ceiling/deposit':               return await handleCeilingDeposit(body);
      case 'ceiling/deposit/min-income':    return await handleCeilingDepositMinIncome(body);
      case 'ceiling/dti':                   return await handleCeilingDTI(body);
      case 'ceiling/serviceability':        return await handleCeilingServiceability(body);
      case 'ceiling/all':                   return await handleCeilingAll(body);
      case 'ceiling/check':                 return await handleCeilingCheck(body);
      case 'ceiling/deposit/sensitivity':   return await handleCeilingDepositSensitivity(body);
      case 'score':                         return await handleScore(body);
      case 'score/batch':                   return await handleScoreBatch(body);
      case 'score/budget-for-score':        return await handleScoreBudgetForScore(body);
      case 'score/suburbs-in-range':        return await handleScoreSuburbsInRange(body);
      case 'score/ceiling':                 return await handleScoreCeiling(body);
      default:
        return err(404, `Unknown endpoint: /api/v1/${route}. See /api/ for documentation.`, 'NOT_FOUND');
    }
  } catch (e) {
    if (e && e.code === 'MISSING_PARAM') {
      return err(400, `Missing required parameter: ${e.field}`, 'MISSING_PARAM');
    }
    console.error('API error:', e);
    return err(500, 'Internal server error. Please try again.', 'INTERNAL_ERROR');
  }
}
