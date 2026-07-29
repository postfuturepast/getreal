/**
 * GetReal — Gemini buying coach API
 * Cloudflare Pages Function: POST /api/ask
 *
 * Body: { messages: Array }  — conversation history in Gemini format
 * Returns: { reply: string, toolResult: object|null }
 */

// ─── Inline engine (copied from engine.js) ────────────────────────────────────
// Cloudflare Pages Functions can't import from the static site root,
// so the calculation engine is inlined here.

const HARDCODED_LMI_RATES = [
  { lvr_min: 80, lvr_max: 82, loan_max: 300000,  rate_pct: 0.56 },
  { lvr_min: 80, lvr_max: 82, loan_max: 500000,  rate_pct: 0.61 },
  { lvr_min: 80, lvr_max: 82, loan_max: 750000,  rate_pct: 0.75 },
  { lvr_min: 80, lvr_max: 82, loan_max: 1000000, rate_pct: 0.81 },
  { lvr_min: 80, lvr_max: 82, loan_max: null,    rate_pct: 0.90 },
  { lvr_min: 82, lvr_max: 84, loan_max: 300000,  rate_pct: 0.81 },
  { lvr_min: 82, lvr_max: 84, loan_max: 500000,  rate_pct: 0.87 },
  { lvr_min: 82, lvr_max: 84, loan_max: 750000,  rate_pct: 0.95 },
  { lvr_min: 82, lvr_max: 84, loan_max: 1000000, rate_pct: 1.10 },
  { lvr_min: 82, lvr_max: 84, loan_max: null,    rate_pct: 1.15 },
  { lvr_min: 84, lvr_max: 85, loan_max: 300000,  rate_pct: 0.87 },
  { lvr_min: 84, lvr_max: 85, loan_max: 500000,  rate_pct: 0.94 },
  { lvr_min: 84, lvr_max: 85, loan_max: 750000,  rate_pct: 1.02 },
  { lvr_min: 84, lvr_max: 85, loan_max: 1000000, rate_pct: 1.20 },
  { lvr_min: 84, lvr_max: 85, loan_max: null,    rate_pct: 1.25 },
  { lvr_min: 85, lvr_max: 86, loan_max: 300000,  rate_pct: 1.19 },
  { lvr_min: 85, lvr_max: 86, loan_max: 500000,  rate_pct: 1.29 },
  { lvr_min: 85, lvr_max: 86, loan_max: 750000,  rate_pct: 1.41 },
  { lvr_min: 85, lvr_max: 86, loan_max: 1000000, rate_pct: 1.64 },
  { lvr_min: 85, lvr_max: 86, loan_max: null,    rate_pct: 1.76 },
  { lvr_min: 86, lvr_max: 87, loan_max: 300000,  rate_pct: 1.19 },
  { lvr_min: 86, lvr_max: 87, loan_max: 500000,  rate_pct: 1.29 },
  { lvr_min: 86, lvr_max: 87, loan_max: 750000,  rate_pct: 1.41 },
  { lvr_min: 86, lvr_max: 87, loan_max: 1000000, rate_pct: 1.64 },
  { lvr_min: 86, lvr_max: 87, loan_max: null,    rate_pct: 1.76 },
  { lvr_min: 87, lvr_max: 88, loan_max: 300000,  rate_pct: 1.25 },
  { lvr_min: 87, lvr_max: 88, loan_max: 500000,  rate_pct: 1.35 },
  { lvr_min: 87, lvr_max: 88, loan_max: 750000,  rate_pct: 1.48 },
  { lvr_min: 87, lvr_max: 88, loan_max: 1000000, rate_pct: 1.73 },
  { lvr_min: 87, lvr_max: 88, loan_max: null,    rate_pct: 1.85 },
  { lvr_min: 88, lvr_max: 89, loan_max: 300000,  rate_pct: 1.32 },
  { lvr_min: 88, lvr_max: 89, loan_max: 500000,  rate_pct: 1.43 },
  { lvr_min: 88, lvr_max: 89, loan_max: 750000,  rate_pct: 1.56 },
  { lvr_min: 88, lvr_max: 89, loan_max: 1000000, rate_pct: 1.82 },
  { lvr_min: 88, lvr_max: 89, loan_max: null,    rate_pct: 1.96 },
  { lvr_min: 89, lvr_max: 90, loan_max: 300000,  rate_pct: 1.32 },
  { lvr_min: 89, lvr_max: 90, loan_max: 500000,  rate_pct: 1.43 },
  { lvr_min: 89, lvr_max: 90, loan_max: 750000,  rate_pct: 1.56 },
  { lvr_min: 89, lvr_max: 90, loan_max: 1000000, rate_pct: 1.82 },
  { lvr_min: 89, lvr_max: 90, loan_max: null,    rate_pct: 1.96 },
  { lvr_min: 90, lvr_max: 91, loan_max: 300000,  rate_pct: 1.63 },
  { lvr_min: 90, lvr_max: 91, loan_max: 500000,  rate_pct: 1.80 },
  { lvr_min: 90, lvr_max: 91, loan_max: 750000,  rate_pct: 2.12 },
  { lvr_min: 90, lvr_max: 91, loan_max: 1000000, rate_pct: 2.27 },
  { lvr_min: 90, lvr_max: 91, loan_max: null,    rate_pct: 2.27 },
  { lvr_min: 91, lvr_max: 92, loan_max: 300000,  rate_pct: 1.73 },
  { lvr_min: 91, lvr_max: 92, loan_max: 500000,  rate_pct: 1.88 },
  { lvr_min: 91, lvr_max: 92, loan_max: 750000,  rate_pct: 2.22 },
  { lvr_min: 91, lvr_max: 92, loan_max: 1000000, rate_pct: 2.37 },
  { lvr_min: 91, lvr_max: 92, loan_max: null,    rate_pct: 2.37 },
  { lvr_min: 92, lvr_max: 93, loan_max: 300000,  rate_pct: 1.87 },
  { lvr_min: 92, lvr_max: 93, loan_max: 500000,  rate_pct: 2.05 },
  { lvr_min: 92, lvr_max: 93, loan_max: 750000,  rate_pct: 2.41 },
  { lvr_min: 92, lvr_max: 93, loan_max: 1000000, rate_pct: 2.58 },
  { lvr_min: 92, lvr_max: 93, loan_max: null,    rate_pct: 2.58 },
  { lvr_min: 93, lvr_max: 94, loan_max: 300000,  rate_pct: 2.13 },
  { lvr_min: 93, lvr_max: 94, loan_max: 500000,  rate_pct: 2.30 },
  { lvr_min: 93, lvr_max: 94, loan_max: 750000,  rate_pct: 2.73 },
  { lvr_min: 93, lvr_max: 94, loan_max: 1000000, rate_pct: 2.94 },
  { lvr_min: 93, lvr_max: 94, loan_max: null,    rate_pct: 2.94 },
  { lvr_min: 94, lvr_max: 95, loan_max: 300000,  rate_pct: 2.13 },
  { lvr_min: 94, lvr_max: 95, loan_max: 500000,  rate_pct: 2.30 },
  { lvr_min: 94, lvr_max: 95, loan_max: 750000,  rate_pct: 2.73 },
  { lvr_min: 94, lvr_max: 95, loan_max: 1000000, rate_pct: 2.94 },
  { lvr_min: 94, lvr_max: 95, loan_max: null,    rate_pct: 2.94 },
  { lvr_min: 95, lvr_max: 97, loan_max: 300000,  rate_pct: 3.14 },
  { lvr_min: 95, lvr_max: 97, loan_max: 500000,  rate_pct: 3.35 },
  { lvr_min: 95, lvr_max: 97, loan_max: 750000,  rate_pct: 3.70 },
  { lvr_min: 95, lvr_max: 97, loan_max: 1000000, rate_pct: 3.70 },
  { lvr_min: 95, lvr_max: 97, loan_max: null,    rate_pct: 3.70 },
  { lvr_min: 97, lvr_max: 100, loan_max: 300000,  rate_pct: 3.14 },
  { lvr_min: 97, lvr_max: 100, loan_max: 500000,  rate_pct: 3.35 },
  { lvr_min: 97, lvr_max: 100, loan_max: 750000,  rate_pct: 3.70 },
  { lvr_min: 97, lvr_max: 100, loan_max: 1000000, rate_pct: 3.70 },
  { lvr_min: 97, lvr_max: 100, loan_max: null,    rate_pct: 3.70 },
];
const HARDCODED_LMI_SD_RATES = { NSW:0.09, VIC:0.10, QLD:0.09, WA:0.10, SA:0.11, TAS:0.10, ACT:0.06, NT:0.10 };
const HARDCODED_REG_FEES     = { NSW:670, VIC:1700, QLD:1250, WA:1120, SA:800, TAS:600, ACT:1100, NT:500 };

function _br(p, tbl) { for(const b of tbl){if(p<=b.max)return b.base+(p-b.min)*b.rate;} return 0; }
function _nsw(p){return _br(p,[{min:0,max:16000,base:0,rate:0.0125},{min:16000,max:35000,base:200,rate:0.015},{min:35000,max:93000,base:485,rate:0.0175},{min:93000,max:351000,base:1500,rate:0.035},{min:351000,max:1168000,base:10530,rate:0.045},{min:1168000,max:3505000,base:47295,rate:0.055},{min:3505000,max:Infinity,base:175830,rate:0.07}]);}
function _vicG(p){if(p<=25000)return p*0.014;if(p<=130000)return 350+(p-25000)*0.024;if(p<=960000)return 2870+(p-130000)*0.06;if(p<=2000000)return p*0.055;return 110000+(p-2000000)*0.065;}
function _vicP(p){if(p<=25000)return p*0.014;if(p<=130000)return 350+(p-25000)*0.024;if(p<=440000)return 2870+(p-130000)*0.05;if(p<=550000)return 18370+(p-440000)*0.06;return _vicG(p);}
function _qld(p){return _br(p,[{min:0,max:5000,base:0,rate:0},{min:5000,max:75000,base:0,rate:0.015},{min:75000,max:540000,base:1050,rate:0.035},{min:540000,max:1000000,base:17325,rate:0.045},{min:1000000,max:Infinity,base:38025,rate:0.0575}]);}
function _wa(p){return _br(p,[{min:0,max:120000,base:0,rate:0.019},{min:120000,max:150000,base:2280,rate:0.0285},{min:150000,max:360000,base:3135,rate:0.038},{min:360000,max:725000,base:11115,rate:0.0475},{min:725000,max:Infinity,base:28453,rate:0.0515}]);}
function _sa(p){return _br(p,[{min:0,max:12000,base:0,rate:0.01},{min:12000,max:30000,base:120,rate:0.02},{min:30000,max:50000,base:480,rate:0.03},{min:50000,max:100000,base:1080,rate:0.035},{min:100000,max:200000,base:2830,rate:0.04},{min:200000,max:250000,base:6830,rate:0.0425},{min:250000,max:300000,base:8955,rate:0.0475},{min:300000,max:500000,base:11330,rate:0.05},{min:500000,max:Infinity,base:21330,rate:0.055}]);}
function _tas(p){if(p<=3000)return 50;if(p<=25000)return 50+(p-3000)*0.0175;if(p<=75000)return 435+(p-25000)*0.0225;if(p<=200000)return 1560+(p-75000)*0.035;if(p<=375000)return 5935+(p-200000)*0.04;if(p<=725000)return 12935+(p-375000)*0.0425;return 27810+(p-725000)*0.045;}
function _act(p){return _br(p,[{min:0,max:200000,base:0,rate:0.022},{min:200000,max:300000,base:4400,rate:0.034},{min:300000,max:500000,base:7800,rate:0.0432},{min:500000,max:750000,base:16440,rate:0.059},{min:750000,max:1000000,base:31190,rate:0.064},{min:1000000,max:1455000,base:47190,rate:0.072},{min:1455000,max:Infinity,base:80034,rate:0.0454}]);}
function _nt(p){if(p<=525000){const V=p/1000;return 0.06571441*V*V+15*V;}return p*0.0495;}

function calcStampDuty(price, ctx) {
  const { state, isFHB=false, isOO=true, isHBCS=false } = ctx;
  switch(state) {
    case 'NSW': { const f=_nsw(price); if(isFHB){if(price<=800000)return 0;if(price<=1000000)return Math.round(f*(price-800000)/200000);} return Math.round(f); }
    case 'VIC': { if(isFHB){const f=_vicG(price);if(price<=600000)return 0;if(price<=750000)return Math.round(f*(price-600000)/150000);return Math.round(f);} if(isOO&&price<=550000)return Math.round(_vicP(price));return Math.round(_vicG(price)); }
    case 'QLD': { const f=_qld(price);if(isFHB){if(price<=500000)return 0;if(price<=550000)return Math.round(f*(price-500000)/50000);}return Math.round(f); }
    case 'WA':  { const f=_wa(price);if(isFHB){if(price<=600000)return 0;if(price<=800000)return Math.round(f*(price-600000)/200000);}return Math.round(f); }
    case 'SA':  return Math.round(_sa(price));
    case 'TAS': { const f=_tas(price);if(isFHB&&price<600000)return Math.round(f*0.5);return Math.round(f); }
    case 'ACT': if(isFHB||isHBCS)return 0; return Math.round(_act(price));
    case 'NT':  { const f=_nt(price);if(isFHB&&price<650000){const fac=price<=500000?1:(650000-price)/150000;const disc=Math.min(f,18601*fac);return Math.max(0,Math.round(f-disc));}return Math.round(f); }
    default: return 0;
  }
}

function lookupLMIRate(lvrPct, baseLoan) {
  const rows = HARDCODED_LMI_RATES.filter(r => lvrPct > r.lvr_min && lvrPct <= r.lvr_max);
  if (!rows.length) return 0;
  const exact = rows.find(r => r.loan_max === null || baseLoan <= r.loan_max);
  return (exact ? exact.rate_pct : rows[rows.length-1].rate_pct) / 100;
}

function getMaxLVR(propType, isOO) {
  if (propType === 'apartment') return isOO ? 0.90 : 0.80;
  return isOO ? 0.95 : 0.90;
}

function _computeAtPrice(price, savings, maxLVR, stampDuty, regFee, lmiSdRate) {
  let lmiSd=0, lmiPrem=0, avail, baseLoan, baseLVR, effLoan, effLVR;
  for(let i=0;i<6;i++){
    const up=stampDuty+regFee+lmiSd;
    avail=savings-up; if(avail<=0)return null;
    baseLoan=price-avail; if(baseLoan<=0)return null;
    baseLVR=baseLoan/price; if(baseLVR>maxLVR)return null;
    if(baseLVR<=0.80){lmiPrem=0;lmiSd=0;effLoan=baseLoan;effLVR=baseLVR;break;}
    const rate=lookupLMIRate(baseLVR*100,baseLoan);
    lmiPrem=baseLoan*rate; effLoan=baseLoan+lmiPrem; effLVR=effLoan/price;
    if(effLVR>maxLVR)return null;
    lmiSd=lmiPrem*lmiSdRate;
  }
  const lvrTier=baseLVR<=0.80?0.80:(baseLVR<=0.90?0.90:0.95);
  return {price,stampDuty,regFee,lmiSd:Math.round(lmiSd),availDeposit:avail,baseLoan,baseLVR,lmiPremium:Math.round(lmiPrem),effectiveLoan:Math.round(effLoan),effectiveLVR:effLVR,lvrTier};
}

function solveDepositCeiling(opts) {
  const {savings,state,isFHB=false,isOO=true,isHBCS=false,propType='house'}=opts;
  if(!savings||savings<=0)return null;
  const maxLVR=getMaxLVR(propType,isOO);
  const regFee=HARDCODED_REG_FEES[state]||400;
  const lmiSdRate=HARDCODED_LMI_SD_RATES[state]||0;
  const ctx={state,isFHB,isOO,isHBCS,propType};
  let lo=0,hi=Math.min(Math.ceil(savings*25),15000000),best=null;
  for(let i=0;i<60;i++){
    const mid=Math.floor((lo+hi)/2);
    if(mid<=0){hi=mid-1;continue;}
    const duty=calcStampDuty(mid,ctx);
    const r=_computeAtPrice(mid,savings,maxLVR,duty,regFee,lmiSdRate);
    if(r!==null){best=r;lo=mid+1;}else{hi=mid-1;}
  }
  return best;
}

function findMaxPriceForLoanCap(loanCap, opts) {
  const {savings,state,isFHB=false,isOO=true,isHBCS=false,propType='house'}=opts;
  if(loanCap<=0||!savings||savings<=0)return null;
  const maxLVR=getMaxLVR(propType,isOO);
  const regFee=HARDCODED_REG_FEES[state]||400;
  const lmiSdRate=HARDCODED_LMI_SD_RATES[state]||0;
  const ctx={state,isFHB,isOO,isHBCS,propType};
  let lo=0,hi=Math.min(loanCap+savings,15000000),best=null;
  for(let i=0;i<60;i++){
    const mid=Math.floor((lo+hi)/2);
    if(mid<=0){hi=mid-1;continue;}
    const dep=mid-loanCap; if(dep<0){lo=mid+1;continue;}
    const baseLVR=loanCap/mid; if(baseLVR>maxLVR){lo=mid+1;continue;}
    const stamp=calcStampDuty(mid,ctx);
    let lmiPrem=0,lmiSd=0;
    if(baseLVR>0.80){const rate=lookupLMIRate(baseLVR*100,loanCap);lmiPrem=Math.round(loanCap*rate);lmiSd=Math.round(lmiPrem*lmiSdRate);}
    const needed=dep+stamp+regFee+lmiSd;
    if(needed<=savings){const lvrTier=baseLVR<=0.80?0.80:(baseLVR<=0.90?0.90:0.95);best={price:mid,loanCap,baseLVR,lvrTier,depositNeeded:dep,stampDuty:stamp,regFee,lmiPremium:lmiPrem,lmiSd,savingsNeeded:needed,effectiveLoan:loanCap+lmiPrem};lo=mid+1;}
    else{hi=mid-1;}
  }
  return best;
}

function calcMonthlyRepayment(loan, annualRatePct) {
  const r=annualRatePct/100/12,n=360;
  if(r===0)return loan/n;
  return loan*r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1);
}

function calculateBuyingPosition(inputs) {
  const {
    savings=0, state='NSW', propertyType='house',
    isOwnerOccupier=true, isFirstHomeBuyer=false, isNewBuild=false, isHBCS=false,
    grossIncome1=0, grossIncome2=0, creditCardLimits=0,
    mortgages=[], otherLoans=[], rentalIncome=0,
    takeHome1=0, takeHome1Freq='monthly', takeHome2=0, takeHome2Freq='monthly',
    hemMonthly=3500, rent=0, schoolFees=0, healthInsurance=0,
    stressRateAnnual=9.0,
  } = inputs;

  const baseOpts = {savings,state,isFHB:isFirstHomeBuyer,isOO:isOwnerOccupier,isHBCS,propType:propertyType};

  // C1
  const c1Result=solveDepositCeiling(baseOpts);
  const c1Price=c1Result?c1Result.price:0;

  // C2 — DTI
  const newPropRental=isOwnerOccupier?0:rentalIncome*52*0.80;
  const existInvRental=mortgages.filter(m=>m.isInvestment&&m.weeklyRent>0).reduce((s,m)=>s+m.weeklyRent*52*0.80,0);
  const totalIncome=grossIncome1+grossIncome2+newPropRental+existInvRental;
  const mortBal=mortgages.reduce((s,m)=>s+(m.balance||0),0);
  const loanBal=otherLoans.reduce((s,l)=>s+(l.amount||0),0);
  const existDebt=creditCardLimits+mortBal+loanBal;
  const maxNewMortgage=Math.max(0,totalIncome*6-existDebt);

  let c2Result=null,c2Price=0;
  if(maxNewMortgage>0){
    c2Result=findMaxPriceForLoanCap(maxNewMortgage,baseOpts);
    c2Price=c2Result?c2Result.price:0;
  }

  // C3 — Serviceability
  const toMo=(amt,freq)=>{
    if(freq==='weekly')return amt*52/12;
    if(freq==='fortnightly')return amt*26/12;
    return amt;
  };
  const netMonthly=toMo(takeHome1,takeHome1Freq)+(takeHome2>0?toMo(takeHome2,takeHome2Freq):0)
    +(isOwnerOccupier?0:(newPropRental+existInvRental)/12);

  const mortReps=mortgages.map(m=>{
    if(m.monthlyRepayment)return m.monthlyRepayment;
    const r=stressRateAnnual/100/12,n=360;
    return r>0?(m.balance||0)*r*Math.pow(1+r,n)/(Math.pow(1+r,n)-1):(m.balance||0)/n;
  });
  const loanReps=otherLoans.map(l=>l.monthlyRepayment||0);
  const mortMo=mortReps.reduce((s,r)=>s+(r||0),0);
  const loanMo=loanReps.reduce((s,r)=>s+(r||0),0);
  const cardMo=creditCardLimits*0.03;
  const existMo=mortMo+loanMo+cardMo;
  const committedMo=(rent||0)+(schoolFees||0)+(healthInsurance||0);
  const maxRepay=netMonthly-(hemMonthly||0)-committedMo-existMo;

  let c3Result=null,c3Price=0,maxLoan=0;
  if(maxRepay>0){
    const r=stressRateAnnual/100/12,n=360;
    maxLoan=r>0?maxRepay*(Math.pow(1+r,n)-1)/(r*Math.pow(1+r,n)):maxRepay*n;
    if(maxLoan>0){
      c3Result=findMaxPriceForLoanCap(Math.round(maxLoan),baseOpts);
      c3Price=c3Result?c3Result.price:0;
    }
  }

  const prices=[c1Price,c2Price>0?c2Price:Infinity,c3Price>0?c3Price:Infinity].filter(p=>p>0&&p<Infinity);
  const maximum=prices.length?Math.min(...prices):0;

  let bindingCeiling='deposit';
  if(c2Price>0&&c2Price===maximum)bindingCeiling='dti';
  else if(c3Price>0&&c3Price===maximum)bindingCeiling='serviceability';

  const lvrTier=c1Result?c1Result.lvrTier:0.80;
  const regFee=HARDCODED_REG_FEES[state]||400;

  return {
    c1Price,c2Price,c3Price,maximum,bindingCeiling,
    dti:{maxNewMortgage,totalIncome,existingDebt:existDebt,mortgageBalances:mortBal,loanBalances:loanBal},
    svc:{maxLoan:Math.round(maxLoan),maxMonthlyRepayment:maxRepay,netMonthly,hemMonthly,existingMonthly:existMo,stressRateAnnual},
    c1Result,c2Result,c3Result,
    breakdown:{
      stampDuty:c1Result?c1Result.stampDuty:calcStampDuty(maximum||savings,{state,isFHB:isFirstHomeBuyer,isOO:isOwnerOccupier,isHBCS}),
      regFee,
      lvrTier,
      lmiPremium:c1Result?c1Result.lmiPremium:0,
    },
  };
}

// ─── Gemini tool definition ───────────────────────────────────────────────────
const TOOLS = [{
  functionDeclarations: [{
    name: 'calculate_buying_position',
    description: 'Calculate the maximum property purchase price for an Australian buyer given their savings, income, debts and property preferences. Always call this when you have enough information rather than estimating.',
    parameters: {
      type: 'OBJECT',
      properties: {
        state:            { type: 'STRING', enum: ['NSW','VIC','QLD','WA','SA','TAS','NT','ACT'], description: 'Australian state' },
        savings:          { type: 'NUMBER', description: 'Total savings available' },
        propertyType:     { type: 'STRING', enum: ['house','apartment','townhouse'] },
        isOwnerOccupier:  { type: 'BOOLEAN' },
        isFirstHomeBuyer: { type: 'BOOLEAN' },
        isNewBuild:       { type: 'BOOLEAN' },
        grossIncome1:     { type: 'NUMBER', description: 'Annual gross income person 1' },
        grossIncome2:     { type: 'NUMBER', description: 'Annual gross income person 2 (0 if sole buyer)' },
        takeHome1:        { type: 'NUMBER', description: 'Monthly take-home pay person 1' },
        takeHome2:        { type: 'NUMBER', description: 'Monthly take-home pay person 2 (0 if sole)' },
        creditCardLimits: { type: 'NUMBER', description: 'Total credit card approved limits' },
        otherLoans: {
          type: 'ARRAY',
          items: { type: 'OBJECT', properties: { amount: { type: 'NUMBER' }, monthlyRepayment: { type: 'NUMBER' } } },
        },
        hemMonthly:       { type: 'NUMBER', description: 'Monthly living expenses (HEM estimate if unknown)' },
        stressRateAnnual: { type: 'NUMBER', description: 'Stress test rate, default 9.0' },
      },
      required: ['state','savings','propertyType','isOwnerOccupier','isFirstHomeBuyer','grossIncome1','takeHome1'],
    },
  }],
}];

const SYSTEM_PROMPT = `You are GetReal's buying coach. You help Australians work out what they can realistically spend on a property.

Your job:
1. Understand what the user wants to know
2. Ask only the questions you need — don't ask for information they've already given
3. When you have enough information, call calculate_buying_position — never estimate financial figures yourself
4. Explain results in plain English: what their ceiling is, what's limiting them, what it means in practice

You only help with Australian property buying. If asked about anything else, redirect politely.

Required before calling the tool: state, savings, property type, owner-occupier or investor, first home buyer status, gross income (at least one person), take-home pay (at least one person).

For take-home pay: if the user gives gross income but not take-home, estimate take-home as roughly 72% of gross for incomes under $120k, 68% for $120k-$180k, 65% above $180k — but flag that this is an estimate and ask them to confirm if they know the figure.

For HEM: if the user hasn't given living expenses, use a default of $3,500/month for singles, $5,000/month for couples, plus $500/month per dependent.

Keep responses concise. When showing a result, explain the most important number first, then what's limiting them, then one clear next step.

Never say "as an AI" or refer to yourself as a language model. You are GetReal.`;

// ─── Handler ──────────────────────────────────────────────────────────────────
export async function onRequestPost(context) {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  try {
    const body = await context.request.json();
    const { messages } = body;

    if (!Array.isArray(messages)) {
      return new Response(JSON.stringify({ error: 'messages array required' }), {
        status: 400, headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const GEMINI_API_KEY = context.env.GEMINI_API_KEY;
    if (!GEMINI_API_KEY) {
      return new Response(JSON.stringify({ error: 'GEMINI_API_KEY not configured' }), {
        status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const GEMINI_MODEL = 'gemini-1.5-flash';
    const geminiUrl = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${GEMINI_API_KEY}`;

    // ── First Gemini call ──
    const geminiBody = {
      system_instruction: { parts: [{ text: SYSTEM_PROMPT }] },
      contents: messages,
      tools: TOOLS,
      tool_config: { function_calling_config: { mode: 'AUTO' } },
    };

    const ctrl1 = new AbortController();
    const t1 = setTimeout(() => ctrl1.abort(), 25000);
    let geminiRes;
    try {
      geminiRes = await fetch(geminiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(geminiBody),
        signal: ctrl1.signal,
      });
    } catch (fetchErr) {
      clearTimeout(t1);
      return new Response(JSON.stringify({ error: `Gemini fetch failed: ${fetchErr.message}` }), {
        status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }
    clearTimeout(t1);

    if (!geminiRes.ok) {
      const errText = await geminiRes.text();
      return new Response(JSON.stringify({ error: `Gemini API error: ${geminiRes.status}`, detail: errText }), {
        status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const geminiData = await geminiRes.json();
    const candidate  = geminiData.candidates?.[0];
    const parts      = candidate?.content?.parts || [];

    // ── Check for tool call ──
    const fnCall = parts.find(p => p.functionCall);

    if (!fnCall) {
      // Plain text reply
      const text = parts.map(p => p.text || '').join('');
      return new Response(JSON.stringify({ reply: text, toolResult: null }), {
        headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    // ── Execute tool ──
    const { name: fnName, args: fnArgs } = fnCall.functionCall;
    let toolResult = null;

    if (fnName === 'calculate_buying_position') {
      try {
        toolResult = calculateBuyingPosition({
          ...fnArgs,
          takeHome1Freq: 'monthly',
          takeHome2Freq: 'monthly',
          hemMonthly:    fnArgs.hemMonthly || 3500,
          stressRateAnnual: fnArgs.stressRateAnnual || 9.0,
          otherLoans:    fnArgs.otherLoans || [],
          mortgages:     fnArgs.mortgages  || [],
        });
      } catch (calcErr) {
        toolResult = { error: calcErr.message };
      }
    }

    // ── Second Gemini call with tool result ──
    const toolResponseContents = [
      ...messages,
      { role: 'model', parts },
      {
        role: 'user',
        parts: [{
          functionResponse: {
            name: fnName,
            response: { name: fnName, content: toolResult },
          },
        }],
      },
    ];

    const geminiBody2 = {
      system_instruction: { parts: [{ text: SYSTEM_PROMPT }] },
      contents: toolResponseContents,
      tools: TOOLS,
    };

    const ctrl2 = new AbortController();
    const t2 = setTimeout(() => ctrl2.abort(), 25000);
    let geminiRes2;
    try {
      geminiRes2 = await fetch(geminiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(geminiBody2),
        signal: ctrl2.signal,
      });
    } catch (fetchErr2) {
      clearTimeout(t2);
      return new Response(JSON.stringify({ error: `Gemini fetch 2 failed: ${fetchErr2.message}` }), {
        status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }
    clearTimeout(t2);

    if (!geminiRes2.ok) {
      const errText = await geminiRes2.text();
      return new Response(JSON.stringify({ error: `Gemini API error (tool response): ${geminiRes2.status}`, detail: errText }), {
        status: 502, headers: { 'Content-Type': 'application/json', ...corsHeaders },
      });
    }

    const geminiData2 = await geminiRes2.json();
    const finalParts  = geminiData2.candidates?.[0]?.content?.parts || [];
    const finalText   = finalParts.map(p => p.text || '').join('');

    return new Response(JSON.stringify({ reply: finalText, toolResult }), {
      headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500, headers: { 'Content-Type': 'application/json', ...corsHeaders },
    });
  }
}

export async function onRequestGet(context) {
  const key = context.env.GEMINI_API_KEY;
  return new Response(JSON.stringify({ status: 'ok', keyConfigured: !!key }), {
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
  });
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    },
  });
}
