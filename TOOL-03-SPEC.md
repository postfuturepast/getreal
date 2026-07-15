# Tool 03 — Deposit Floor Checker: Specification

**Status:** Pre-build — spec only. Research phase to follow.

---

## What this tool does

Given a deposit (free cash) and some personal details, calculate the **maximum property price** a buyer can access. This is meaningfully different from a "borrowing power" calculator, which outputs a maximum loan — not a maximum purchase price. The distinction matters because upfront costs (stamp duty, LMI) come out of the deposit before it reaches the property.

The output also signals which of the three ceilings is doing the limiting, and what the minimum income floor is to service the resulting loan.

---

## The three ceilings

Maximum purchase price is bounded by whichever of the following is hit first:

### Ceiling 1 — Deposit / LVR (primary calculation)
The deposit must first absorb upfront costs. Whatever remains goes toward the property. The resulting loan cannot exceed the lender's maximum LVR (up to 95% for some lenders). This ceiling is **iterative** — stamp duty and LMI both move with price, so the calculation must converge on the highest price at which LVR doesn't breach the limit.

### Ceiling 2 — Serviceability (income floor pointer, not a full calculation)
Even if the deposit allows a given loan size, the borrower must be able to service it. The tool does not attempt a full serviceability assessment — instead, it derives an **income floor** from the Ceiling 1 result: the minimum net monthly income required to service that specific loan with no other debts and expenses at HEM minimum. This is the absolute floor. The user is told: "to get this loan approved, you need to clear at least $X/month."

To make the floor more realistic, the user can optionally add common large expenses that HEM does **not** cover (see Serviceability section for detail).

### Ceiling 3 — Debt-to-income ratio (DTI)
A regulatory hard cap: total debt divided by gross annual income. **APRA activated a binding DTI limit of 6x for new lending in February 2026** — this is no longer a soft flag, it is a firm regulatory ceiling. Still historically less likely to bind than serviceability (Ceiling 2), but must be checked. If the loan from Ceiling 1 ÷ gross annual income > 6, the purchase price must be reduced until it falls within 6x.

---

## Inputs

**Required — for Ceiling 1 (deposit/LVR):**

| Input | Notes |
|---|---|
| Available deposit | Free cash only (not equity or proceeds not yet received) |
| State / territory | Drives stamp duty and transfer fees |
| Property use | Owner-occupier or investment |
| Property type | New build or established |
| First home buyer | Yes / no — affects stamp duty concessions and grant eligibility |

**Required — for HEM minimum (income floor):**

| Input | Notes |
|---|---|
| Household type | Single / couple / family |
| Number of dependants | Children / kids in household |
| Location type | Metro / regional |

**Optional — to personalise the income floor:**

| Input | Notes |
|---|---|
| Gross annual income | If provided, tool checks whether Ceiling 2 or 3 binds |
| Existing loan repayments | Personal loans, car loans — monthly amount |
| Credit card limits | Total across all cards — assessed at ~3% of limit/month regardless of balance |
| Private school fees | Annual total, converted to monthly |
| HECS-HELP debt | Annual repayment (income-contingent — **research required** for how banks assess this) |
| Other regular commitments | Child support, spousal maintenance, etc. |

These optional items are all expenses HEM does **not** cover but that banks will include when assessing serviceability. Adding them raises the income floor to a more realistic level.

---

## Calculation logic — Ceiling 1 in detail

The calculation is circular: stamp duty and LMI are both functions of property price, but they eat into the deposit before price is known. The approach is iterative.

### Step 1 — Stamp duty
Calculate stamp duty for the given state, property use, buyer type, and property type at the trial purchase price. This varies significantly by state and has concessions/thresholds for FHBs and new builds.

**Data source to find:** A reliable stamp duty formula or open-source library covering all Australian states (e.g., a GitHub project or published government calculators). Each state publishes its own schedule.

### Step 2 — Transfer and registration fees
Fixed-ish fees that scale with price. Typically small ($1,000–$3,000). Each state publishes a schedule.

### Step 3 — Deposit available after upfront costs

The two primary costs the deposit must absorb before reaching the property are **stamp duty** and **LMI**. Transfer fees are also deducted here.

```
deposit_net = deposit_total - stamp_duty - transfer_fees
```

**LMI** is the second primary cost. However, LMI is typically **capitalised into the loan** (added on top of the loan amount) rather than paid in cash upfront. This means it does not reduce `deposit_net` directly — but it does increase the loan, which raises the effective LVR. Because LMI is a function of both loan size and LVR, and both of those depend on the purchase price, LMI must be resolved iteratively in Step 4.

The practical effect: LMI acts as a ceiling-reducer. A borrower who would otherwise reach a $700k purchase price might find LMI pushes their effective LVR over the 95% cap, dropping their maximum to $680k. The tool must account for this dynamic.

Note: Fixed costs (conveyancing ~$1,500–$2,500, building inspection ~$500–$800, moving, etc.) are **not** calculated — the tool should flag these as "set aside separately" with a ballpark note, as they vary too much to estimate reliably.

### Step 4 — Iterative price / LVR solve
The tool steps through candidate property prices (e.g., in $10,000 increments) until the LVR ceiling is breached, then steps back to the last valid price.

At each candidate price `P`:

```
loan = P - deposit_net
LVR = loan / P
```

If `LVR > 80%`: LMI applies. LMI is estimated from published insurer tables (Helia / QBE) using loan amount and LVR band.

```
loan_with_LMI = loan + LMI_premium
effective_LVR = loan_with_LMI / P
```

If `effective_LVR > max_LVR` (e.g., 95%): this price is too high. Roll back.

The highest `P` where `effective_LVR ≤ max_LVR` is the **deposit ceiling price**.

### LMI notes
- LMI is typically capitalised into the loan (added on top), which is why it affects effective LVR
- Main providers: **Helia** (formerly Genworth) and **QBE**
- Premiums are tabular: inputs are LVR band and loan amount band
- **Research required:** Obtain current published premium tables. These may have changed since the previous tool was built.
- LMI does not apply to loans ≤ 80% LVR
- Some lenders (e.g., select credit unions) have LMI waiver schemes — out of scope for this tool

### Max LVR
- Standard maximum: **95%** (5% genuine savings required by most lenders)
- Some lenders go to 97% with parental guarantee (out of scope for v1)
- **Research required:** Confirm current maximum LVR across major lenders

---

## Calculation logic — Ceiling 2 (serviceability pointer)

### Loan repayments
Calculate monthly P&I repayment for the deposit-ceiling loan at the **headline rate**:
```
monthly_repayment = PMT(rate/12, 30*12, loan_with_LMI)
```

Display this as the expected repayment.

### Affordability repayment (for income floor)
Recalculate repayment at **affordability rate** = headline rate + APRA buffer (currently +3%):
```
affordability_repayment = PMT(affordability_rate/12, 30*12, loan_with_LMI)
```

### HEM minimum expenses
The **Household Expenditure Measure (HEM)** is the industry-standard minimum living expense benchmark used by Australian banks. Published by the Melbourne Institute. Banks use whichever is higher: the HEM figure or the borrower's declared expenses.

HEM varies by:
- Household type (single / couple / family)
- Number of dependants
- Location (metro / regional)
- (Income band in some versions)

**Research required:** Obtain the current published HEM table or a reliable proxy. The full HEM is proprietary but indicative figures are published in ASIC/RBA commentary and some industry sources.

### Minimum income floor

The floor is derived from the Ceiling 1 loan result. It is a pointer, not a full serviceability assessment.

**Base floor (absolute minimum):**
```
min_monthly_income = affordability_repayment + HEM_monthly
```

This assumes no other debts, no credit cards, and expenses at HEM minimum. It is the lowest possible income floor — real-world approval will require more headroom.

**Personalised floor (if optional expenses provided):**
```
min_monthly_income = affordability_repayment + HEM_monthly + additional_monthly_expenses
```

Where `additional_monthly_expenses` includes any of:
- Existing loan repayments (user-entered monthly amount)
- Credit card cost: `total_card_limits × 3% / 12` — assessed at ~3% of limit per month regardless of balance; a $20,000 limit = $600/month assessed cost
- Private school fees: annual ÷ 12
- HECS-HELP: assessed repayment amount ÷ 12
- Other commitments (child/spousal support, etc.)

**If the user provides their income:**
- `income ≥ personalised floor` → Ceiling 1 (deposit) is binding; income is sufficient
- `income < personalised floor` → Ceiling 2 (serviceability) is binding; show what price their income supports instead
- `loan > 6× gross annual income` → Ceiling 3 (DTI) is binding regardless of serviceability

---

## Calculation logic — Ceiling 3 (DTI check)

```
DTI = loan_with_LMI / gross_annual_income
```

APRA activated a binding 6x DTI cap on new lending in **February 2026**. If DTI > 6, the maximum purchase price must be reduced until `loan_with_LMI ≤ 6 × gross_annual_income`. This requires gross income as an input; if not provided, this check is skipped and the user is told to verify DTI separately.

Display as: "Your loan is X.Xx your income. APRA limits new lending to 6x — [within limit / exceeds limit]."

---

## Interest rate assumptions

The tool needs a headline interest rate. Options:
1. Use a published benchmark rate (e.g., RBA average variable rate for owner-occupier loans) — **research required** for current figure
2. Let the user input a rate they've been quoted
3. Both: show benchmark as default, allow override

The APRA serviceability buffer is **+3.0% over the assessment rate** (confirmed as of 2023 — verify still current).

Loan term: **30 years** (standard assumption).

---

## What the tool does NOT calculate
- Full serviceability (lender-specific policies, actual declared expenses, other debts)
- Specific lender eligibility
- Government grants (FHOG, First Home Guarantee, Help to Buy) — worth flagging as "you may be eligible for these; check separately"
- Exact LMI to the dollar (insurer-specific; tool gives an estimate)
- Conveyancing, building inspection, moving costs — flagged as "allow $3,000–$8,000 separately"

---

## Output structure (proposed)

```
Maximum property price:     $XXX,XXX
  ↳ Binding constraint:     Deposit / Income / DTI

Deposit breakdown:
  Your deposit:             $XX,XXX
  Stamp duty (est.):       -$X,XXX
  Transfer fees (est.):    -$XXX
  Available for purchase:   $XX,XXX

Loan:
  Purchase price:           $XXX,XXX
  Less deposit:            -$XX,XXX
  LMI (est., capitalised): +$X,XXX
  Loan amount:              $XXX,XXX
  LVR:                      XX.X%

Repayments (est.):
  Monthly (at X.XX%):       $X,XXX/month
  Assessed at X.XX%:        $X,XXX/month  ← banks assess at this rate

Minimum income to service this loan:
  Assessed repayment:       $X,XXX/month
  HEM minimum expenses:    +$X,XXX/month
  Minimum net income:       $X,XXX/month

[If income provided]
  Your income:              $X,XXX/month
  Status:                   ✓ Income sufficient / ✗ Income ceiling applies

Also remember to set aside (not included above):
  Conveyancing, inspections, moving: allow $3,000–$8,000

[If state = NT and property use = owner-occupier]
  ⚠ NT owner-occupier note: The NT Territory Home Owner Discount may
    reduce your stamp duty further if you've lived in the NT for 12+
    months. We've applied the standard rate as this discount's value
    isn't publicly documented. Check with NT Revenue or your conveyancer.
```

---

## Open research questions

All lookup tables are to be pre-computed at **$10,000 price increments** up to a **$5,000,000 cap**. Above $5M the tool declines to calculate and tells the user to speak to a financial planner. This avoids hammering any external API during the iterative LVR solve — the tool simply steps through pre-built lookup tables.

---

### 1. Stamp duty

**Approach: algorithm, not lookup table.** A bracket-based formula computes stamp duty at any price, which is cleaner and more maintainable than pre-computed tables. The iterative LVR solve calls the formula directly at each $10k price step.

**Reference implementation found:** [`ravisha22/PersonalFinanceToolkit`](https://github.com/ravisha22/PersonalFinanceToolkit) (MIT licence) — `src/data/stamp-duty-tables.ts`. Contains a clean bracket algorithm using `{ min, max, rate, base }` data structure plus FHB concession logic with sliding scale. VIC and NSW tables are full; QLD and WA are partially stubbed; SA, TAS, ACT, NT are wrongly aliased to WA and need proper data.

**Our approach:** Adopt this algorithm structure. Verify and update all bracket tables against current state revenue office schedules (2025-26 / 2026-27). Add missing states. Add investor vs OO distinction where relevant (e.g. VIC PPR concession). Add $5M cap beyond which the tool declines to calculate.

**What the algorithm needs per state:**
- Standard bracket table: `{ min, max, rate, base }`
- FHB: full exemption threshold, concession top threshold (sliding scale between them)
- Whether FHB concession differs for new vs established
- PPR vs investor rate (where states have a separate schedule)
- Foreign buyer surcharge (out of scope for tool v1)

**Coverage target:** All 8 states/territories fully confirmed. NSW, VIC (general + PPR), QLD, WA, SA, TAS, ACT, NT bracket tables all confirmed — see tables below.

---

All bracket data below is sourced from [AusCalcs](https://auscalcs.com.au/stamp-duty/) (reviewed 2 June 2026, sourced from each state's revenue office). To be cross-checked against official revenue office schedules before building.

---

#### NSW — CONFIRMED (2026-27, source: Revenue NSW / AusCalcs)

Standard transfer duty brackets (same rate for owner-occupier and investor — no separate schedule):

| Property value | Duty payable |
|---|---|
| $0 – $16,000 | $1.25 per $100 |
| $16,001 – $35,000 | $200 + $1.50 per $100 over $16,000 |
| $35,001 – $93,000 | $485 + $1.75 per $100 over $35,000 |
| $93,001 – $351,000 | $1,500 + $3.50 per $100 over $93,000 |
| $351,001 – $1,168,000 | $10,530 + $4.50 per $100 over $351,000 |
| $1,168,001 – $3,505,000 | $47,295 + $5.50 per $100 over $1,168,000 |
| Over $3,505,000 | $175,830 + $7.00 per $100 over $3,505,000 |

FHB concessions (FHBAS):
- Full exemption: purchases ≤ $800,000
- Tapered concession: $800,001 – $1,000,000
- Above $1,000,000: full standard duty applies
- Applies to both new and established homes (must be principal place of residence)

Investors: standard rates, no concessions available.

Source: [Revenue NSW — Transfer duty](https://www.revenue.nsw.gov.au/taxes-duties-levies-royalties/transfer-duty); [AusCalcs NSW 2026-27](https://auscalcs.com.au/stamp-duty/nsw/)

---

#### VIC — CONFIRMED (2026-27, source: SRO VIC / AusCalcs)

General rates (applies to all purchases; PPR concession separate — see below):

| Property value | Duty payable |
|---|---|
| $0 – $25,000 | 1.4% of value |
| $25,001 – $130,000 | $350 + 2.4% over $25,000 |
| $130,001 – $960,000 | $2,870 + 6.0% over $130,000 |
| $960,001 – $2,000,000 | 5.5% of total dutiable value (flat rate on full amount) |
| Over $2,000,000 | $110,000 + 6.5% over $2,000,000 |

Note: The $960k–$2M bracket uses a flat 5.5% rate on the entire purchase price, not a marginal rate — this creates a step-down at the $960k threshold compared to the bracket below.

PPR (Principal Place of Residence) concession — CONFIRMED: Owner-occupiers pay lower rates on purchases **up to $550,000**. Above $550,000 the general schedule applies regardless of intended use.

| Property value | Duty payable |
|---|---|
| $0 – $25,000 | 1.4% of value |
| $25,001 – $130,000 | $350 + 2.4% over $25,000 |
| $130,001 – $440,000 | $2,870 + 5.0% over $130,000 |
| $440,001 – $550,000 | $18,370 + 6.0% over $440,000 |

At $500,000: PPR = $21,970 vs general = $25,070 (saving: $3,100). Above $550,000: general rate applies to both OO and investor.

Source: [SRO Victoria PPR current rates](https://www.sro.vic.gov.au/principal-place-residence-current-rates); [AusTax.tools VIC 2026](https://austax.tools/vic-stamp-duty-2026/) (reviewed March 2026, sourced from SRO VIC)

FHB concessions:
- Full exemption: purchases ≤ $600,000 (new and established homes)
- Tapered sliding scale: $600,001 – $750,000 — concession = full_duty × (750,000 − price) / 150,000
- Above $750,000: full standard duty applies

Off-the-plan concession: Extended to contracts entered before 21 April 2027.

Source: [SRO Victoria](https://www.sro.vic.gov.au/land-transfer-duty); [AusCalcs VIC 2026-27](https://auscalcs.com.au/stamp-duty/vic/)

---

#### QLD — CONFIRMED (2026-27, source: QLD Revenue Office / AusCalcs)

Standard transfer duty brackets (owner-occupier rate; investor rate is the same in QLD — no separate schedule):

| Property value | Duty payable |
|---|---|
| $0 – $5,000 | Nil |
| $5,001 – $75,000 | $1.50 per $100 over $5,000 |
| $75,001 – $540,000 | $1,050 + $3.50 per $100 over $75,000 |
| $540,001 – $1,000,000 | $17,325 + $4.50 per $100 over $540,000 |
| Over $1,000,000 | $38,025 + $5.75 per $100 over $1,000,000 |

FHB concessions:
- Full concession (nil duty): purchases ≤ $500,000 (new or established, must be principal place of residence)
- Partial concession: $500,001 – $550,000 (sliding scale — concession reduces proportionally above $500k)
- Above $550,000: full standard duty applies

First Home Owner Grant (FHOG): $30,000 for new builds under $750,000 (separate from duty; not modelled by this tool but flagged in output).

Source: [Queensland Revenue Office](https://www.qld.gov.au/housing/buying-owning-home/advice-buying-home/transfer-duty); [AusCalcs QLD 2026-27](https://auscalcs.com.au/stamp-duty/qld/)

---

#### WA — CONFIRMED (2026-27, source: WA Revenue / AusCalcs)

Standard transfer duty brackets (same rate for OO and investor — no separate schedule):

| Property value | Duty payable |
|---|---|
| $0 – $120,000 | $1.90 per $100 |
| $120,001 – $150,000 | $2,280 + $2.85 per $100 over $120,000 |
| $150,001 – $360,000 | $3,135 + $3.80 per $100 over $150,000 |
| $360,001 – $725,000 | $11,115 + $4.75 per $100 over $360,000 |
| Over $725,000 | $28,453 + $5.15 per $100 over $725,000 |

FHB concessions:
- Full exemption: purchases ≤ $430,000
- Partial concession: $430,001 – $530,000 (sliding scale)
- Above $530,000: full standard duty applies

Source: [WA Revenue](https://www.wa.gov.au/service/financial-management/taxation/calculate-transfer-duty); [AusCalcs WA 2026-27](https://auscalcs.com.au/stamp-duty/wa/)

---

#### SA — CONFIRMED (2026-27, source: RevenueSA / AusCalcs)

Standard transfer duty brackets (same rate for OO and investor — no separate schedule):

| Property value | Duty payable |
|---|---|
| $0 – $12,000 | $1.00 per $100 |
| $12,001 – $30,000 | $120 + $2.00 per $100 over $12,000 |
| $30,001 – $50,000 | $480 + $3.00 per $100 over $30,000 |
| $50,001 – $100,000 | $1,080 + $3.50 per $100 over $50,000 |
| $100,001 – $200,000 | $2,830 + $4.00 per $100 over $100,000 |
| $200,001 – $250,000 | $6,830 + $4.25 per $100 over $200,000 |
| $250,001 – $300,000 | $8,955 + $4.75 per $100 over $250,000 |
| $300,001 – $500,000 | $11,330 + $5.00 per $100 over $300,000 |
| Over $500,000 | $21,330 + $5.50 per $100 over $500,000 |

FHB concessions: **No stamp duty concession for established homes in SA.** First Home Owner Grant: $15,000 for new builds valued under $650,000 (separate; not modelled but flagged).

Source: [RevenueSA](https://www.revenuesa.sa.gov.au/taxes-and-duties/stamp-duties/real-property); [AusCalcs SA 2026-27](https://auscalcs.com.au/stamp-duty/sa/)

---

#### TAS — CONFIRMED (2026-27, source: State Revenue Office TAS / AusCalcs)

Standard transfer duty brackets (same rate for OO and investor — no separate schedule):

| Property value | Duty payable |
|---|---|
| $0 – $3,000 | $50 minimum |
| $3,001 – $25,000 | $50 + $1.75 per $100 over $3,000 |
| $25,001 – $75,000 | $435 + $2.25 per $100 over $25,000 |
| $75,001 – $200,000 | $1,560 + $3.50 per $100 over $75,000 |
| $200,001 – $375,000 | $5,935 + $4.00 per $100 over $200,000 |
| $375,001 – $725,000 | $12,935 + $4.25 per $100 over $375,000 |
| Over $725,000 | $27,810 + $4.50 per $100 over $725,000 |

FHB concessions:
- 50% discount on duty for established home purchases under $600,000 (owner-occupier)
- First Home Owner Grant: $30,000 for new builds valued under $750,000 (separate; not modelled but flagged)

Source: [SRO Tasmania](https://www.sro.tas.gov.au/duties); [AusCalcs TAS 2026-27](https://auscalcs.com.au/stamp-duty/tas/)

---

#### ACT — CONFIRMED (2026-27, source: ACT Revenue / AusCalcs)

Standard conveyance duty brackets (same rate for OO and investor — no separate schedule):

| Property value | Duty payable |
|---|---|
| $0 – $200,000 | $20 + $2.20 per $100 |
| $200,001 – $300,000 | $4,400 + $3.40 per $100 over $200,000 |
| $300,001 – $500,000 | $7,800 + $4.32 per $100 over $300,000 |
| $500,001 – $750,000 | $16,440 + $5.90 per $100 over $500,000 |
| $750,001 – $1,000,000 | $31,190 + $6.40 per $100 over $750,000 |
| $1,000,001 – $1,455,000 | $47,190 + $7.20 per $100 over $1,000,000 |
| Over $1,455,000 | $80,034 + $4.54 per $100 over $1,455,000 |

Note: The rate drops from 7.20% to 4.54% above $1,455,000 — not a typo; the ACT schedule has this structure.

Home Buyer Concession Scheme (HBCS): Full exemption available for income-eligible buyers — this is **not limited to first home buyers**. Approximate income thresholds: ~$160,000 for singles, scaling up for couples and families. Property must be used as a principal place of residence. This is a means-tested exemption, not an automatic FHB discount.

ACT context: The ACT is progressively replacing stamp duty with an annual land tax (rates) over a 20-year transition. As of 2026-27 stamp duty still applies to most transactions for buyers outside the concession scheme.

Source: [ACT Revenue](https://www.revenue.act.gov.au/duties/conveyance-duty); [AusCalcs ACT 2026-27](https://auscalcs.com.au/stamp-duty/act/)

---

#### NT — CONFIRMED (2026-27, source: NT Revenue / AusCalcs)

**The NT uses a formula-based calculation, not a bracket table.** Two regimes:

For properties valued **up to $525,000:**
```
V = purchase_price / 1000
D = (0.06571441 × V² + 15 × V)
```
Where D is the stamp duty in dollars. This is a quadratic formula unique to the NT.

For properties valued **over $525,000:**
Flat rate of **4.95%** of the total purchase price.

Example: $500,000 → V = 500 → D = (0.06571441 × 250,000) + (15 × 500) = $16,429 + $7,500 = $23,929
Example: $600,000 → 4.95% × $600,000 = $29,700

FHB concessions:
- First Home Owner Discount (FHOD): up to $18,601 off duty for homes valued under $650,000. The discount phases out as price approaches $650k. Applies to new and established homes.

Territory Home Owner Discount (THOD) — known exclusion: The NT also offers a separate discount for owner-occupiers who have lived in the NT for at least 12 months. This is not restricted to FHBs. However, the discount amount and eligibility structure are not publicly documented in a form that can be reliably implemented. **The tool applies the standard rate for NT owner-occupiers and notes this in the output** (see Output section). Users should check with NT Revenue or their conveyancer.

Source: [NT Revenue](https://treasury.nt.gov.au/dtf/territory-revenue-office/stamp-duty); [AusCalcs NT 2026-27](https://auscalcs.com.au/stamp-duty/nt/)

---

**Coverage target:** All 8 states/territories fully confirmed, including VIC PPR concession bracket table. No remaining gaps.

---

### 2. Transfer and registration fees

Registration fees (title transfer + mortgage registration) vary by state and scale slightly with purchase price, but are small relative to stamp duty. For tool purposes, a flat estimate is used with a note to the user.

**Working estimate:** ~$500 across all states (AusCalcs settlement costs page, reviewed 2 June 2026). This is displayed to the user as an estimate, not a precise figure.

The tool output should note separately that the user should budget ~$2,000–$2,500 for conveyancing and ~$500–$800 for building/pest inspection — these are not calculated but are flagged.

**Per-state exact amounts:** Not confirmed. Exact schedules are published by each state's land registry but vary in format (NSW LRS publishes a fee schedule; VIC expresses amounts in "fee units" updated each July). Given the small relative size, the flat ~$500 estimate is sufficient for the MVP. *[TBC — fetch exact per-state amounts if precision is needed in a future version]*

---

### 3. LMI

**What we need:** A sourced formula or rate table for LMI premiums, structured as LVR tier × loan amount band → premium rate (%).

**Where to look:** Helia and QBE broker-facing rate guides (some surface publicly), Canstar and Finder LMI explainers, broker aggregator sites. If full tables aren't publicly available, derive a formula from indicative rates and document the source and derivation explicitly.

**Output:** 2D lookup: LVR band (80–85%, 85–90%, 90–95%) × loan size band → premium rate. LMI is capitalised into the loan, not paid upfront.

**Transparency requirement:** The methodology for how LMI was estimated must be shown clearly in the UI — not buried in fine print. This includes the source, the LVR/loan inputs used, and the formula or table applied. This is non-negotiable given users are making major financial decisions.

---

### 4. Maximum LVR

**CONFIRMED (owner-occupier): 95%** is broadly available across major lenders including all Big 4. LMI required above 80%.

**Investor LVR:** Typically capped at **90%** by most lenders. Westpac recently increased its investor ceiling to 95%, but this is not the market standard. Tool should use 90% for investors.

**LMI waivers:** Some lenders (ANZ, NAB, Westpac) offer LMI waivers for certain professionals (doctors, lawyers, etc.) — out of scope for tool v1.

**Output:** Tool uses **95% for owner-occupier**, **90% for investor** as the ceiling. These are clearly labelled as approximate market maximums, not guarantees from any specific lender.

Source: Canstar, Lendi, lender policy pages (Westpac, CBA, ANZ, NAB, Macquarie)

---

### 5. Interest rate (actual new-lending rate, not SVR)

**The problem with standard calculators:** Most use the Standard Variable Rate (SVR), which almost nobody pays. New borrowers nearly always receive a discount. Using SVR overstates repayments and understates maximum purchase price — a meaningful and misleading error.

**Confirmed figures (July 2026):**
- RBA cash rate: **4.35%** (after three hikes in 2026 — Feb, Mar, May)
- Average variable rate across all borrowers (portfolio): **~6.20%**
- Average new-lending variable rate: **5.93%** (end-March 2026, RBA/ABS data)
- Lowest advertised new-lending rate: **~5.69%**

**Implication:** New borrowers are typically getting ~25–50 bps below the portfolio average. The tool should use new-lending rates, not portfolio SVR.

**What we actually want:** The discount off SVR for new lending, and whether that discount varies by loan size.

**Confirmed figures (July 2026):**
- Big 4 carded SVR (standard variable rate): **~6.50–6.69%**
- CBA documented package discount: **0.70% off SVR** (confirmed in CBA rate documentation effective May 2026)
- Average new-lending rate: **5.93%** (end-March 2026, RBA/ABS) — implies ~60–75 bps typical discount
- Lowest advertised rate (non-bank/digital lenders): **~5.69%**
- Broker-negotiated discounts: typically **50–100 bps** off carded SVR

**Framing for the tool:** Use SVR as the reference point, apply a discount to arrive at estimated actual rate. Express the default as "SVR − X bps" so the assumption is visible and adjustable.

**Loan size effect — partially confirmed:** Larger loans attract better discounts. Lenders' absolute margin is higher on large loans so they compete more aggressively. However, specific tier thresholds (e.g. "$500k gets an extra 15 bps") are not publicly disclosed — they are negotiated through brokers case by case. LVR also affects pricing (lower LVR = better rate). *[TBC: Research broker rate cards and any published lender pricing tiers to quantify this more precisely.]*

**Output:** Tool uses SVR − ~70 bps as the default estimated new-lending rate. A 2D matrix (LVR × loan size) applies adjustments off that baseline where evidence supports it. User can override with their own quoted rate. The tool shows the calculation clearly: "We've estimated your rate at X% (SVR of Y% minus a typical new-lending discount of Z bps). Enter your own rate if you've been quoted something different."

Source: [RBA Lending Rates](https://www.rba.gov.au/statistics/interest-rates/); [ABS Lending Indicators March 2026](https://www.abs.gov.au/statistics/economy/finance/lending-indicators/latest-release); CBA rate documentation May 2026

---

### 6. APRA serviceability buffer

**CONFIRMED: 3.0%** over the assessment rate. Raised from 2.5% to 3.0% in October 2021. Reaffirmed by APRA in its July 2025 review with no change signalled. No planned reduction as of July 2026.

Source: [APRA macroprudential settings update](https://www.apra.gov.au/news-and-publications/apra-announces-update-on-macroprudential-settings); [APG 223](https://www.apra.gov.au/prudential-practice-guide-apg-223-residential-mortgage-lending)

---

### 7. HEM table

**What we need:** Indicative HEM figures by household type (single / couple / family), number of dependants, and location (metro / regional). The full Melbourne Institute HEM is proprietary, but indicative figures appear in ASIC and RBA publications and broker industry resources.

**Where to look:** ASIC MoneySmart, RBA research papers, broker association publications, Canstar/Finder HEM explainers.

**Output:** A lookup table covering the key combinations. Clearly labelled as indicative — the tool cannot know the exact figure a given lender will use.

---

### 8. HECS-HELP serviceability treatment

**What we need:** How banks include HECS-HELP debt when assessing serviceability. Specifically: is it the ATO's income-contingent repayment schedule, a percentage of outstanding balance, or a flat loading? Does it affect the DTI ratio calculation?

**Where to look:** Lender policy pages, broker guides (WealthWorks, Lendi, Mortgage Choice), ASIC commentary.

---

### 9. DTI limit

**CONFIRMED:** APRA activated a binding **6x DTI cap** on new lending in **February 2026**. `loan_with_LMI ÷ gross_annual_income` must not exceed 6. Gross income required as input to check; if not provided, this check is skipped with a note to the user.

**What counts toward total debt (CONFIRMED):** All outstanding debt — mortgage balances (existing + new), car loans, personal loans, and credit card **limits** (not balances). A $15,000 credit card limit you never use still adds $15,000 to total debt.

**What counts as income (CONFIRMED):** Gross before tax. Rental income counted at 80% by most lenders.

**Technically a quota, not a hard ban:** APRA requires lenders to cap loans with DTI ≥ 6x to no more than 20% of new lending in each portfolio (owner-occ and investor assessed separately). In practice this functions as a near-hard cap for most borrowers.

**Exemptions (CONFIRMED):** Bridging loans and new dwelling purchases/construction are exempt.

Source: [APRA — Activation of debt-to-income limits](https://www.apra.gov.au/activation-of-debt-to-income-limits-as-a-macroprudential-policy-tool)

---

## Design notes
- Matches GetReal's existing brutalist dark aesthetic
- Precision and transparency: every figure is labelled as estimated where it is
- All methodology assumptions are disclosed inline or via tooltip/expandable
- No lead capture required for basic calculation; can prompt "speak to a broker" as soft CTA
