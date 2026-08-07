"""
GetReal guide pages — editorial content.

This file contains all human-written content for generated guide pages.
Numerical data (stamp duty rates, HEM figures, etc.) is pulled live from
Supabase at build time — do not hardcode it here.

To add a new concept page: add an entry to CONCEPT_PAGES.
To update editorial content for a stamp duty page: edit STAMP_DUTY_EDITORIAL.
To regenerate all HTML: python3 build_guides.py
"""

# ─── Concept pages ───────────────────────────────────────────────────────────
# Each entry produces one static HTML page at /guides/{slug}
# Fields:
#   slug              URL path (e.g. "serviceability-buffer" → /guides/serviceability-buffer)
#   title             H1 and page title — the question the page answers
#   meta_description  160 chars max
#   answer            2–4 sentence direct answer — this is what AI systems cite
#   how_it_affects    paragraph explaining the practical impact
#   worked_example    dict with "label" and "lines" (list of (label, value) tuples)
#   key_factors       list of strings
#   faqs              list of {"q": str, "a": str}
#   calculator_url    relative URL for CTA button
#   calculator_label  CTA button text
#   methodology_anchor anchor on /methodology page (e.g. "serviceability")

CONCEPT_PAGES = [
    {
        "slug": "serviceability-buffer",
        "title": "What is the serviceability buffer in Australia?",
        "meta_description": "The serviceability buffer is a 3% interest rate surcharge lenders must apply when assessing your mortgage. Explains what it is, why it exists, and how it reduces borrowing capacity.",
        "answer": (
            "Australia's serviceability buffer is 3 percentage points added to your mortgage interest rate "
            "for the purpose of assessing whether you can afford the loan. If the actual interest rate is 6.49%, "
            "the lender must verify you can make repayments at 9.49%. This buffer is set by APRA (the Australian "
            "Prudential Regulation Authority) and applies to all banks, credit unions, and building societies. "
            "It cannot be waived or negotiated."
        ),
        "how_it_affects": (
            "The buffer directly reduces your borrowing capacity. Every 1% increase in the stress-test rate "
            "reduces maximum borrowing by roughly 8–10% on a 30-year loan. At a 3% buffer, the reduction is "
            "significant — a borrower who could service a $900,000 loan at the actual rate may only qualify "
            "for around $780,000 when assessed at the stress rate."
        ),
        "worked_example": {
            "label": "How the buffer reduces borrowing capacity",
            "lines": [
                ("Monthly surplus after living costs", "$3,200/month"),
                ("Actual interest rate", "6.49% p.a."),
                ("Stress-test rate (actual + 3%)", "9.49% p.a."),
                ("Max loan at stress-test rate (30yr P&I)", "≈ $393,000"),
                ("Max loan at actual rate (for comparison)", "≈ $516,000"),
                ("Reduction due to buffer", "≈ $123,000"),
            ],
        },
        "key_factors": [
            "The buffer is fixed at 3.0 percentage points — set by APRA regulation and cannot be negotiated with your lender.",
            "It applies to the loan's actual interest rate — a fixed-rate loan is stress-tested at the fixed rate plus 3%, not the lender's variable rate.",
            "The buffer was increased from 2.5% to 3.0% in November 2021 in response to rapid property price growth.",
            "Non-bank lenders are not APRA-regulated and may apply a different buffer, but most still use 3% to remain competitive in securitisation markets.",
        ],
        "faqs": [
            {
                "q": "Why does the serviceability buffer exist?",
                "a": (
                    "The buffer protects borrowers from becoming unable to repay their loan if interest rates rise. "
                    "It also acts as a macro-prudential tool — by limiting how much people can borrow, it reduces the "
                    "risk of a housing-debt-driven financial crisis. APRA introduced the current 3% requirement in "
                    "November 2021 when low rates were encouraging very high borrowing relative to incomes."
                ),
            },
            {
                "q": "Can I avoid the serviceability buffer?",
                "a": (
                    "No — if you borrow from an APRA-regulated lender (any bank, credit union, or building society), "
                    "the buffer applies. Some non-bank lenders are not APRA-regulated and may apply different standards, "
                    "but they typically charge more and may have stricter other requirements. The buffer cannot be waived."
                ),
            },
            {
                "q": "Does the buffer apply to fixed rate loans?",
                "a": (
                    "Yes. If you fix your rate at 6.00%, the lender stress-tests at 9.00%. The buffer is applied "
                    "to whatever rate the loan will actually charge — not to the lender's standard variable rate."
                ),
            },
            {
                "q": "Could the buffer change?",
                "a": (
                    "Yes — APRA has changed it before (from 2.5% to 3.0% in November 2021). If interest rates fell "
                    "significantly, APRA might reduce the buffer to ease lending conditions. GetReal's methodology "
                    "page shows the current buffer in use and when it was last updated."
                ),
            },
        ],
        "calculator_url": "/deposit",
        "calculator_label": "Calculate your borrowing capacity",
        "methodology_anchor": "serviceability",
    },

    {
        "slug": "hecs-and-borrowing",
        "title": "How does HECS debt affect borrowing capacity in Australia?",
        "meta_description": "Since September 2025, HECS/HELP is excluded from lenders' DTI calculations. But it still reduces borrowing capacity by lowering your take-home pay. This page explains exactly how.",
        "answer": (
            "Since 30 September 2025, HECS/HELP balances are excluded from lenders' debt-to-income (DTI) "
            "calculations under APRA direction — your HECS balance no longer counts against the 6× income cap. "
            "However, HECS still reduces your borrowing capacity through a different mechanism: the ATO "
            "automatically withholds compulsory repayments from your salary above $54,435, reducing your net "
            "take-home pay and therefore the monthly surplus available to service a mortgage."
        ),
        "how_it_affects": (
            "The impact depends entirely on your income. At $80,000, HECS costs about $2,800/year in "
            "withholding (~$230/month). At $120,000, it's about $7,800/year (~$650/month). That monthly "
            "reduction flows directly into lower borrowing capacity — roughly $28,000–$78,000 depending on income."
        ),
        "worked_example": {
            "label": "HECS impact at $100,000 gross income",
            "lines": [
                ("Gross income", "$100,000/year"),
                ("HECS repayment rate at $100k", "5.5%"),
                ("Annual HECS withholding", "≈ $5,500/year"),
                ("Monthly reduction in take-home pay", "≈ $458/month"),
                ("Approximate borrowing capacity reduction", "≈ $55,000"),
                ("Impact on DTI ceiling (Ceiling 2)", "None — excluded since Sep 2025"),
            ],
        },
        "key_factors": [
            "HECS/HELP is excluded from DTI since 30 September 2025 — your HECS balance no longer reduces the 6× cap.",
            "HECS still affects serviceability (Ceiling 3) because compulsory repayments reduce net income.",
            "The repayment rate applies to total income, not just the amount above the threshold — at $100k, 5.5% of the full $100k is withheld.",
            "Paying HECS off early to increase borrowing capacity is rarely worth it — the cash is usually better used as deposit.",
        ],
        "faqs": [
            {
                "q": "Should I pay off my HECS before applying for a mortgage?",
                "a": (
                    "Rarely. Since HECS is excluded from DTI, paying it off doesn't increase your 6× income cap. "
                    "It only removes the compulsory withholding from your take-home pay. For most borrowers the "
                    "borrowing capacity gain is much smaller than the cash used — which would serve better as deposit. "
                    "Run the numbers in the calculator both ways before deciding."
                ),
            },
            {
                "q": "What if my partner also has HECS?",
                "a": (
                    "Both borrowers' HECS repayments are deducted from their respective take-home pay in the "
                    "serviceability calculation. If both partners earn $100,000 with HECS, the combined monthly "
                    "reduction is around $916, reducing joint borrowing capacity by approximately $110,000."
                ),
            },
            {
                "q": "Does HECS affect stamp duty or my deposit?",
                "a": (
                    "No. HECS does not affect stamp duty. For the deposit ceiling (Ceiling 1), HECS is irrelevant — "
                    "only your savings, stamp duty, and LMI matter."
                ),
            },
            {
                "q": "How do I enter HECS in the GetReal calculator?",
                "a": (
                    "The deposit calculator asks about HECS debt in the Ceiling 2 (Debt) section. If you enter your "
                    "actual take-home pay (already net of HECS withholding), GetReal will not double-count it. "
                    "HECS withholding is only estimated if you declare a HECS debt and the tool estimates your net income."
                ),
            },
        ],
        "calculator_url": "/deposit",
        "calculator_label": "Calculate your borrowing capacity with HECS",
        "methodology_anchor": "hecs",
    },

    {
        "slug": "what-is-lmi",
        "title": "What is LMI and when do you pay it in Australia?",
        "meta_description": "LMI (Lenders Mortgage Insurance) is paid when your deposit is less than 20%. It protects the lender, not you. This page explains when LMI applies, how much it costs, and how to avoid it.",
        "answer": (
            "Lenders Mortgage Insurance (LMI) is a one-off insurance premium paid by the borrower when the "
            "loan-to-value ratio (LVR) exceeds 80% — meaning your deposit is less than 20% of the purchase "
            "price. LMI protects the lender if you default and the property sale doesn't cover the outstanding "
            "loan. It does not protect you. The premium is typically 0.5%–4% of the loan amount depending on "
            "LVR and loan size, and can be added to the loan balance."
        ),
        "how_it_affects": (
            "LMI directly reduces how much property your deposit can buy. On a $700,000 purchase with a 10% "
            "deposit ($70,000), LMI can cost $10,000–$15,000 — money that can't go toward deposit. "
            "GetReal's calculator accounts for LMI automatically, which is why the maximum purchase price "
            "drops sharply when your LVR crosses the 80% threshold."
        ),
        "worked_example": {
            "label": "LMI cost at different LVR levels — $600,000 purchase, NSW",
            "lines": [
                ("80% LVR — loan $480,000", "No LMI"),
                ("85% LVR — loan $510,000", "≈ $4,550 LMI + $410 stamp duty on LMI"),
                ("90% LVR — loan $540,000", "≈ $7,720 LMI + $695 stamp duty on LMI"),
                ("95% LVR — loan $570,000", "≈ $17,600 LMI + $1,584 stamp duty on LMI"),
                ("Note", "LMI stamp duty is charged on the premium itself (9% in NSW)"),
            ],
        },
        "key_factors": [
            "LMI applies when LVR exceeds 80% — regardless of loan size or income.",
            "The premium is charged as a percentage of the loan amount, not the purchase price.",
            "Most states charge stamp duty on the LMI premium itself — adding 9–10% on top.",
            "LMI can be capitalised into the loan (added to the balance) — you don't pay upfront but pay interest on it over the loan term.",
            "The First Home Guarantee allows eligible first home buyers to borrow up to 95% LVR with no LMI.",
        ],
        "faqs": [
            {
                "q": "Does LMI protect me if I can't make repayments?",
                "a": (
                    "No. LMI protects the lender, not you. If you default and the property sells for less than "
                    "the outstanding loan, LMI covers the lender's shortfall. The insurer may then pursue you "
                    "for recovery of that shortfall."
                ),
            },
            {
                "q": "Can I avoid LMI?",
                "a": (
                    "Yes — if you have a 20% deposit, or use the First Home Guarantee (eligible first home buyers, "
                    "up to 95% LVR). Some lenders also waive LMI for specific occupations including doctors, "
                    "dentists, lawyers, and some engineers — check with a mortgage broker."
                ),
            },
            {
                "q": "Is LMI a one-off cost?",
                "a": (
                    "Yes. LMI is a one-off premium at settlement. If you refinance later, a new LMI assessment "
                    "applies to the new loan — you don't get a refund on the original premium (though some "
                    "insurers offer a partial refund in the early years if the loan is discharged)."
                ),
            },
            {
                "q": "How does GetReal calculate LMI?",
                "a": (
                    "GetReal uses indicative LMI rates from the Home Loan Experts rate table (May 2026), stored "
                    "in Supabase and fetched at calculation time. Actual costs depend on your lender and insurer "
                    "(Genworth or QBE). Use the calculator for an estimate, then confirm with your lender."
                ),
            },
        ],
        "calculator_url": "/deposit",
        "calculator_label": "Calculate your LMI cost",
        "methodology_anchor": "lmi",
    },

    {
        "slug": "what-is-lvr",
        "title": "What is LVR in Australian home loans?",
        "meta_description": "LVR (Loan-to-Value Ratio) is the loan as a percentage of the property value. It determines whether you pay LMI and the maximum you can borrow. This page explains LVR limits by property type and occupancy.",
        "answer": (
            "LVR (Loan-to-Value Ratio) is your loan amount expressed as a percentage of the property's purchase "
            "price. If you borrow $720,000 to buy an $800,000 property, your LVR is 90%. LVR is one of the most "
            "important numbers in a mortgage application — it determines whether you pay LMI, how much you can "
            "borrow, and what interest rate tier you qualify for. Lenders cap LVR based on property type and "
            "whether you'll live there."
        ),
        "how_it_affects": (
            "Your LVR determines your LMI liability and your maximum loan. Below 80% — no LMI. Above 80% — "
            "LMI applies, at increasing cost the higher the LVR. Lenders impose hard maximums: 95% for "
            "owner-occupier houses, 90% for apartments, lower again for investors."
        ),
        "worked_example": {
            "label": "LVR calculation — $850,000 house, NSW",
            "lines": [
                ("Purchase price", "$850,000"),
                ("Savings before stamp duty", "$130,000"),
                ("NSW stamp duty (non-FHB, house)", "≈ $33,000"),
                ("Available deposit after stamp duty", "$97,000"),
                ("Loan required", "$753,000"),
                ("LVR", "88.6%"),
                ("LMI payable?", "Yes — LVR exceeds 80%"),
            ],
        },
        "key_factors": [
            "Owner-occupier houses and townhouses: maximum 95% LVR at most lenders.",
            "Owner-occupier apartments: maximum 90% LVR.",
            "Investor houses and townhouses: maximum 90% LVR.",
            "Investor apartments: maximum 80% LVR (no LMI applies since 80% is the hard cap).",
            "Some lenders apply stricter limits for small apartments, high-density postcodes, or regional areas.",
        ],
        "faqs": [
            {
                "q": "How do I calculate my LVR?",
                "a": (
                    "LVR = (loan amount ÷ purchase price) × 100. Your loan is the purchase price minus your "
                    "deposit — the cash left after stamp duty and upfront costs. GetReal's calculator works "
                    "this out automatically as part of the deposit ceiling."
                ),
            },
            {
                "q": "Does LMI affect my LVR?",
                "a": (
                    "When LMI is capitalised into the loan (added to the balance), it increases the loan — "
                    "which increases the effective LVR. GetReal ensures the final LVR including capitalised "
                    "LMI stays within the ceiling."
                ),
            },
            {
                "q": "What is a good LVR?",
                "a": (
                    "Below 80% is the key threshold — no LMI applies. Below 70% often qualifies for better "
                    "interest rate tiers. The lower your LVR, the stronger your equity position and the lower "
                    "the lender's risk."
                ),
            },
            {
                "q": "Can I reduce my LVR over time?",
                "a": (
                    "Yes — every repayment reduces your loan balance and improves your LVR. If your LVR improves "
                    "below 80% through repayments or property value growth, you may be able to refinance without "
                    "LMI on the new loan."
                ),
            },
        ],
        "calculator_url": "/deposit",
        "calculator_label": "Calculate your LVR and deposit ceiling",
        "methodology_anchor": "lvr",
    },

    {
        "slug": "debt-to-income-ratio",
        "title": "What is the debt-to-income ratio cap in Australian mortgages?",
        "meta_description": "Australia's DTI cap limits total debt to 6× gross income. This page explains what counts as debt, how the cap affects borrowing, and what changed with HECS in September 2025.",
        "answer": (
            "Australia's debt-to-income (DTI) ratio cap limits total debt across all loans to 6 times your "
            "gross annual income. If you earn $100,000, your maximum total debt is $600,000. Existing debts — "
            "mortgages, car loans, and credit card limits (treated as fully drawn regardless of actual balance) "
            "— all count against this cap. HECS/HELP has been excluded since 30 September 2025."
        ),
        "how_it_affects": (
            "For many borrowers, DTI is not the binding ceiling — serviceability often limits first. But for "
            "higher-income earners with existing debt, or borrowers building a property portfolio, DTI "
            "frequently becomes the cap. Credit card limits are the most overlooked factor: a $30,000 limit "
            "you never use still reduces your mortgage ceiling by $30,000."
        ),
        "worked_example": {
            "label": "DTI ceiling example",
            "lines": [
                ("Gross income (single)", "$130,000/year"),
                ("DTI cap (6×)", "$780,000 total debt"),
                ("Existing car loan balance", "− $25,000"),
                ("Credit card limit (fully drawn)", "− $20,000"),
                ("HECS balance", "excluded since Sep 2025"),
                ("Maximum new mortgage", "$735,000"),
            ],
        },
        "key_factors": [
            "Credit card limits are counted in full regardless of actual balance — reducing or closing cards before applying can meaningfully increase your ceiling.",
            "HECS/HELP is excluded from DTI since 30 September 2025 per APRA direction.",
            "Investment property mortgages count against DTI even if the property is positively geared.",
            "The 6× cap is a practical market ceiling — APRA guidance, not a hard legislative limit, but major banks all apply it.",
        ],
        "faqs": [
            {
                "q": "Is the 6× DTI cap a legal requirement?",
                "a": (
                    "Not a hard legal cap — APRA sets macro-prudential guidance rather than a fixed limit. "
                    "But mainstream lenders have aligned on 6× as their practical ceiling. Applications "
                    "above this are typically declined at major banks."
                ),
            },
            {
                "q": "Does DTI apply per borrower or combined?",
                "a": (
                    "Combined. For joint applications, total debt is compared to combined gross income. "
                    "Two borrowers on $80,000 each have a combined cap of $960,000."
                ),
            },
            {
                "q": "How do I reduce my DTI?",
                "a": (
                    "Close or reduce credit card limits — this is the fastest lever. Pay down consumer debt "
                    "before applying. Increasing income (or adding a co-borrower) raises the cap directly."
                ),
            },
            {
                "q": "What counts as debt in the DTI calculation?",
                "a": (
                    "Mortgage balances on all properties, credit card limits in full, car loans, personal "
                    "loans, and BNPL balances if declared. HECS/HELP is excluded since September 2025."
                ),
            },
        ],
        "calculator_url": "/deposit",
        "calculator_label": "Check your DTI ceiling",
        "methodology_anchor": "dti",
    },

    {
        "slug": "household-expenditure-measure",
        "title": "What is HEM and how does it affect your mortgage in Australia?",
        "meta_description": "HEM is the minimum living cost benchmark lenders must apply when assessing your mortgage. Even if you spend less, lenders assume at least HEM. This page explains what it covers and how much it is.",
        "answer": (
            "HEM (Household Expenditure Measure) is a minimum living cost benchmark published quarterly by "
            "the Melbourne Institute. APRA requires all banks and lenders to apply at least HEM when "
            "assessing whether you can afford a mortgage — even if you declare lower expenses. It covers "
            "food, utilities, transport, clothing, and everyday spending. It does not cover rent, school "
            "fees, or health insurance, which are assessed separately."
        ),
        "how_it_affects": (
            "HEM is a serviceability floor. If you declare $1,800/month in living expenses but HEM for "
            "your household is $3,200, the lender uses $3,200. This reduces the surplus income available "
            "to service a mortgage and therefore reduces your maximum loan. Couples with dependants have "
            "significantly higher HEM than singles — often $1,500–$2,000/month more."
        ),
        "worked_example": {
            "label": "HEM benchmarks by household type — metropolitan (indicative)",
            "lines": [
                ("Single, no dependants", "≈ $2,480/month"),
                ("Single, 1 dependant", "≈ $3,050/month"),
                ("Couple, no dependants", "≈ $3,680/month"),
                ("Couple, 1 dependant", "≈ $4,200/month"),
                ("Couple, 2 dependants", "≈ $4,680/month"),
                ("Couple, 3+ dependants", "≈ $5,200/month"),
            ],
        },
        "key_factors": [
            "HEM figures are not publicly published — lenders license them from the Melbourne Institute. GetReal uses indicative estimates.",
            "Regional HEM is lower than metropolitan HEM — GetReal determines your location from your postcode.",
            "The higher of your declared expenses or HEM is used — you cannot beat the floor by declaring lower spending.",
            "Rent, school fees, and private health insurance are added on top of HEM in the serviceability calculation.",
        ],
        "faqs": [
            {
                "q": "Can I negotiate the HEM applied to my application?",
                "a": (
                    "No — HEM is a regulatory floor. You cannot negotiate it below the benchmark for your "
                    "household type. You can (and should) declare your actual expenses if they are higher "
                    "than HEM, as lenders use the higher figure."
                ),
            },
            {
                "q": "Does HEM account for childcare?",
                "a": (
                    "HEM covers basic living expenses. Childcare is often treated separately as a committed "
                    "expense — lenders may add actual childcare costs on top of HEM. Policies vary by lender."
                ),
            },
            {
                "q": "Is HEM different in regional areas?",
                "a": (
                    "Yes — HEM benchmarks are lower for regional and rural areas. GetReal determines your "
                    "location type (metropolitan vs regional) from your postcode using ABS ASGS classifications."
                ),
            },
            {
                "q": "Why does GetReal apply HEM even if I enter lower expenses?",
                "a": (
                    "Because that's what lenders do — APRA requires it. GetReal mirrors lender behaviour "
                    "so its estimates are as realistic as possible."
                ),
            },
        ],
        "calculator_url": "/deposit",
        "calculator_label": "Calculate your serviceability ceiling",
        "methodology_anchor": "hem",
    },
]


# ─── Stamp duty pages ─────────────────────────────────────────────────────────
# One page per state. Numerical data (bracket tables, concession thresholds)
# is pulled from Supabase at build time and injected into the page.
# This dict contains only editorial content that won't auto-update from data.

STAMP_DUTY_EDITORIAL = {
    "NSW": {
        "slug": "stamp-duty/nsw",
        "title": "Stamp duty in New South Wales — 2026 rates",
        "meta_description": "Current NSW stamp duty rates for 2026. Transfer duty on any purchase price, including first home buyer exemptions up to $800,000 and concessions to $1,000,000.",
        "answer": (
            "Stamp duty in New South Wales — officially called transfer duty — is a progressive state tax "
            "on property purchases. On an $800,000 property, a standard (non-FHB) buyer pays approximately "
            "$31,090. First home buyers pay no stamp duty on properties up to $800,000 and receive a "
            "tapered concession between $800,000 and $1,000,000."
        ),
        "key_notes": [
            "NSW uses a single rate scale — no separate owner-occupier vs investor rate.",
            "First home buyers: full exemption under $800,000, tapered concession to $1,000,000.",
            "A small registration fee (around $670) applies in addition to stamp duty.",
            "NSW also offers an annual property tax option for eligible first home buyers as an alternative to stamp duty.",
        ],
        "authority": "Revenue NSW",
        "authority_url": "https://www.revenue.nsw.gov.au/taxes-duties-levies-royalties/transfer-duty",
        "faqs": [
            {"q": "When is stamp duty due in NSW?", "a": "Within 3 months of signing contracts (exchange). Your conveyancer handles payment before settlement."},
            {"q": "Can first home buyers avoid stamp duty in NSW?", "a": "Yes — full exemption under $800,000. Between $800,000 and $1,000,000, a tapered concession applies. Above $1,000,000, full duty applies."},
            {"q": "Does NSW have an annual property tax option?", "a": "Yes — eligible first home buyers can opt into an annual property tax instead of paying stamp duty upfront. The annual tax is based on land value. It's worth modelling both options; the annual tax suits buyers who plan to sell within a few years."},
            {"q": "Is stamp duty the same for investors in NSW?", "a": "Yes — NSW applies the same transfer duty rates to investors and owner-occupiers."},
        ],
    },

    "VIC": {
        "slug": "stamp-duty/vic",
        "title": "Stamp duty in Victoria — 2026 rates",
        "meta_description": "Current Victorian stamp duty (land transfer duty) rates for 2026. Owner-occupier PPR rates, first home buyer exemptions up to $600,000, and standard investor rates.",
        "answer": (
            "Stamp duty in Victoria — called land transfer duty — has two rate scales: a lower owner-occupier "
            "(PPR) rate for homes up to $550,000, and a standard rate for all other purchases. First home "
            "buyers purchasing under $600,000 pay no duty. Between $600,000 and $750,000, a tapered "
            "concession applies."
        ),
        "key_notes": [
            "Victoria has two duty scales — the PPR (principal place of residence) rate is lower for properties up to $550,000.",
            "Above $550,000, the standard rate applies to everyone regardless of whether they'll live there.",
            "First home buyers: full exemption under $600,000, tapered concession to $750,000.",
            "VIC duty is among the highest in Australia at upper price points — around $55,000 on a $1M purchase.",
        ],
        "authority": "State Revenue Office Victoria",
        "authority_url": "https://www.sro.vic.gov.au/land-transfer-duty",
        "faqs": [
            {"q": "What is the PPR concession in Victoria?", "a": "PPR stands for Principal Place of Residence. If you're buying a home you'll live in as your primary residence and it costs $550,000 or less, you pay the lower PPR duty rate. Above $550,000, the standard rate applies to everyone."},
            {"q": "Do investors pay more stamp duty in Victoria?", "a": "At properties under $550,000, yes — investors pay the standard (higher) rate while owner-occupiers pay the PPR rate. Above $550,000, both pay the same standard rate."},
            {"q": "When is stamp duty due in Victoria?", "a": "Within 30 days of settlement. Your conveyancer lodges and pays with the State Revenue Office."},
            {"q": "Are there concessions for off-the-plan purchases in VIC?", "a": "Yes — off-the-plan dutiable value concessions can significantly reduce duty on new builds. GetReal's calculator applies these when you select new build/off the plan."},
        ],
    },

    "QLD": {
        "slug": "stamp-duty/qld",
        "title": "Stamp duty in Queensland — 2026 rates",
        "meta_description": "Current Queensland transfer duty rates for 2026. Home concession rates for owner-occupiers and first home buyer concessions up to $700,000.",
        "answer": (
            "Stamp duty in Queensland — called transfer duty — uses a progressive bracket system with a "
            "lower home concession rate for owner-occupiers. First home buyers purchasing under $700,000 "
            "receive a first home concession. On an $800,000 purchase, a standard buyer pays approximately "
            "$24,525."
        ),
        "key_notes": [
            "Queensland has a home concession rate — lower than the standard rate for owner-occupiers buying their primary residence.",
            "First home buyers: first home concession applies under $700,000, tapered to $800,000.",
            "Foreign buyers pay an additional 8% surcharge (not modelled in GetReal's current calculator).",
            "QLD duty is generally lower than NSW and VIC at most price points.",
        ],
        "authority": "Queensland Revenue Office",
        "authority_url": "https://www.qld.gov.au/housing/buying-owning-home/advice-buying-home/transfer-duty",
        "faqs": [
            {"q": "What is the QLD home concession?", "a": "The home concession reduces transfer duty for buyers purchasing their primary residence. The rate is lower than the standard rate. You must intend to move in within 1 year and live there for at least 1 year."},
            {"q": "When is transfer duty due in Queensland?", "a": "Within 30 days of the liability date, which is generally when you take possession or settle."},
            {"q": "Is there first home buyer relief in QLD?", "a": "Yes — the First Home Concession reduces or eliminates transfer duty on properties up to $700,000. Between $700,000 and $800,000, a tapered concession applies."},
        ],
    },

    "WA": {
        "slug": "stamp-duty/wa",
        "title": "Stamp duty in Western Australia — 2026 rates",
        "meta_description": "Current Western Australia transfer duty rates for 2026. First home buyer exemptions up to $430,000 and concessions to $530,000.",
        "answer": (
            "Stamp duty in Western Australia — called transfer duty — uses a progressive bracket system. "
            "First home buyers receive an exemption on properties up to $450,000 and a tapered concession "
            "up to $600,000. On a $700,000 purchase, a standard buyer pays approximately $24,200."
        ),
        "key_notes": [
            "WA has one of the lower stamp duty regimes among mainland states.",
            "First home buyers: full exemption under $430,000, tapered concession to $530,000.",
            "No separate owner-occupier vs investor rate.",
            "Foreign buyers pay an additional 7% surcharge.",
        ],
        "authority": "Department of Finance WA — State Revenue",
        "authority_url": "https://www.finance.wa.gov.au/cms/State_Revenue/Transfer_Duty.aspx",
        "faqs": [
            {"q": "When is stamp duty due in WA?", "a": "Within 2 months of the liability date (generally settlement)."},
            {"q": "Do first home buyers pay stamp duty in WA?", "a": "No stamp duty on properties up to $430,000. A partial exemption applies up to $530,000, calculated as a straight-line reduction."},
            {"q": "Does WA have different rates for investors?", "a": "No — the same transfer duty rates apply to investors and owner-occupiers in WA."},
        ],
    },

    "SA": {
        "slug": "stamp-duty/sa",
        "title": "Stamp duty in South Australia — 2026 rates",
        "meta_description": "Current South Australia stamp duty rates for 2026. Note: SA has no first home buyer stamp duty concession — eligible FHBs may receive the First Home Owner Grant instead.",
        "answer": (
            "Stamp duty in South Australia uses a progressive bracket system. Unlike every other state, "
            "SA offers no first home buyer stamp duty exemption or concession. Eligible first home buyers "
            "purchasing a new build may receive the $15,000 First Home Owner Grant instead. On an $800,000 "
            "property, a buyer pays approximately $38,730."
        ),
        "key_notes": [
            "South Australia is the only state with no FHB stamp duty concession.",
            "Eligible first home buyers purchasing new builds may receive the $15,000 First Home Owner Grant.",
            "SA rates are on the higher end at upper price points.",
            "No separate owner-occupier vs investor rate.",
        ],
        "authority": "RevenueSA",
        "authority_url": "https://www.revenuesa.sa.gov.au/taxes-and-royalties/real-property-act-land",
        "faqs": [
            {"q": "Is there stamp duty relief for first home buyers in SA?", "a": "No stamp duty exemption or concession. This is unique among Australian states. However, eligible first home buyers purchasing a new build may receive the $15,000 First Home Owner Grant."},
            {"q": "When is stamp duty due in SA?", "a": "Due at or before settlement. Your conveyancer handles this."},
            {"q": "Does SA have different rates for investors?", "a": "No — the same rates apply regardless of how you intend to use the property."},
        ],
    },

    "TAS": {
        "slug": "stamp-duty/tas",
        "title": "Stamp duty in Tasmania — 2026 rates",
        "meta_description": "Current Tasmania stamp duty rates for 2026. First home buyers receive a 50% duty concession on established properties.",
        "answer": (
            "Stamp duty in Tasmania — called duty on conveyances — uses a progressive bracket system. "
            "First home buyers purchasing established homes receive a 50% duty concession. Tasmanian "
            "property prices are generally lower than mainland capitals, making duty bills smaller in "
            "absolute terms. On a $600,000 property, a standard buyer pays approximately $18,247."
        ),
        "key_notes": [
            "First home buyers: 50% duty concession on established properties.",
            "New builds may attract different concession arrangements.",
            "Tasmanian property prices are generally lower than mainland capitals.",
        ],
        "authority": "State Revenue Office Tasmania",
        "authority_url": "https://www.sro.tas.gov.au/duties",
        "faqs": [
            {"q": "What concessions do first home buyers get in Tasmania?", "a": "A 50% concession on stamp duty for established property purchases. The property must be your principal place of residence."},
            {"q": "When is stamp duty due in Tasmania?", "a": "Within 3 months of the date of the instrument (usually settlement)."},
            {"q": "Are there duty concessions for new builds in Tasmania?", "a": "Separate concession arrangements may apply for new builds — check the State Revenue Office for current conditions."},
        ],
    },

    "ACT": {
        "slug": "stamp-duty/act",
        "title": "Stamp duty in the ACT — 2026 rates",
        "meta_description": "Current ACT conveyance duty rates for 2026. The Home Buyer Concession Scheme offers full duty exemption for income-eligible buyers — not just first home buyers.",
        "answer": (
            "Stamp duty in the ACT — called conveyance duty — uses a progressive bracket system. The ACT's "
            "Home Buyer Concession Scheme (HBCS) provides a full duty exemption for income-eligible buyers "
            "purchasing their principal place of residence. Unlike other states, this is not limited to "
            "first home buyers — the concession is income-tested, with a threshold of approximately "
            "$160,000/year for singles."
        ),
        "key_notes": [
            "The ACT Home Buyer Concession Scheme is available to any eligible buyer (not just first home buyers) who meets the income threshold.",
            "Income threshold: approximately $160,000/year for a single buyer. Higher for couples and those with dependants.",
            "The property must be the buyer's principal place of residence.",
            "The ACT is gradually transitioning from stamp duty to a broad-based land tax (rates).",
        ],
        "authority": "ACT Revenue Office",
        "authority_url": "https://www.revenue.act.gov.au/duties/conveyance-duty",
        "faqs": [
            {"q": "Is the ACT Home Buyer Concession Scheme only for first home buyers?", "a": "No — it's available to any eligible buyer purchasing their principal place of residence who meets the income threshold, even if they've owned property before. This is unique among Australian states and territories."},
            {"q": "What is the ACT HBCS income threshold?", "a": "Approximately $160,000/year for a single buyer. The threshold increases with dependants. Check the ACT Revenue Office for current figures — thresholds are updated annually."},
            {"q": "When is stamp duty due in the ACT?", "a": "Within 90 days of the date of the dutiable transaction."},
        ],
    },

    "NT": {
        "slug": "stamp-duty/nt",
        "title": "Stamp duty in the Northern Territory — 2026 rates",
        "meta_description": "Current NT stamp duty rates for 2026. The NT uses a unique formula-based calculation. First home buyers receive an $18,601 rebate, phasing out between $650,000 and $723,000.",
        "answer": (
            "Stamp duty in the Northern Territory uses a quadratic formula rather than the progressive "
            "bracket system used by other states. For purchases up to $525,000, duty is calculated as: "
            "D = (0.06571441 × V² + 15 × V) ÷ 1000, where V = purchase price ÷ 1000. Above $525,000, "
            "a flat 4.95% rate applies. First home buyers receive an $18,601 rebate, which phases out "
            "between $500,000 and $650,000."
        ),
        "key_notes": [
            "The NT is the only jurisdiction that uses a formula rather than bracket tables.",
            "First home buyers receive an $18,601 rebate (paid back after duty is assessed, not an upfront exemption).",
            "The flat 4.95% rate above $525,000 makes NT one of the more expensive jurisdictions for higher-value purchases.",
            "NT property prices are generally lower than most mainland capital cities.",
        ],
        "authority": "Territory Revenue Office",
        "authority_url": "https://nt.gov.au/employ/money-and-taxes/taxes-levies-and-royalties/stamp-duty",
        "faqs": [
            {"q": "Why does the NT use a formula?", "a": "The NT formula produces a smooth, continuous curve rather than the step-function of bracket tables. In practice the results are similar — it's a different mathematical expression of a progressive rate."},
            {"q": "What is the NT first home buyer rebate?", "a": "Eligible first home buyers receive an $18,601 rebate. It's a rebate — you pay duty first, then receive the rebate. It phases out linearly between $500,000 and $650,000, and does not apply above $650,000."},
            {"q": "When is stamp duty due in the NT?", "a": "Within 60 days of the transaction date."},
        ],
    },
}
