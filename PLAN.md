# GetReal — Product Backlog
*Pick the next chunk, work through it, add new chunks as ideas arrive.*
*Last updated: 2026-07-09*

---

## 🚨 MAJOR ISSUE — VIC data reliability

The current VIC data has three significant problems that need to be fixed before VIC can be considered reliable:

1. **Missing suburb/type combinations** — e.g. Collingwood apartments show no data in VGV source file despite being a dense apartment suburb. Manually patched with estimated median ($660k, 90 sales) — this is not real data. Likely affects other dense inner-Melbourne suburbs too.

2. **Townhouse data is fabricated** — VGV doesn't publish a townhouse file. Townhouse median = house median × 0.82, townhouse sales = house sales × 0.45. These are rough estimates, not real figures.

3. **Annual sales counts are estimated, not real** — The VGV median file doesn't include transaction volumes. Sales counts are estimated from price tiers (e.g. median > $1M → 45 sales). Actual volumes could be significantly different.

**What this means for scoring:** VIC scores are directionally useful but not as reliable as NSW. The "X of Y houses sold within your budget" figure uses estimated counts, not real transaction volumes.

**Fix:** Find and use a VIC data source that includes individual sale records (address, price, date, type) — equivalent to what NSW Valuer General publishes. Alternatives to investigate:
- PEXA settlement data (not free)
- REA/Domain scraping (bot-blocked)
- Data.Vic datasets beyond the median file
- PropertyData.com.au API

**Workaround in place:** Collingwood apartment patched in suburb-data.json. Any re-run of load_vic_data.py will overwrite this patch — re-apply if pipeline is re-run.

---

## ✅ DONE

- State selector UI (VIC + NSW live, others coming soon)
- NSW data pipeline (146k rows from nswpropertysalesdata.com)
- NSW live scoring engine (real Supabase queries)
- NSW what-if cards (live queries, "coming soon" for bedrooms)
- NSW comparable cards with real addresses + Street View photos
- suburb-data.json regenerated from full archive.zip dataset (3,165 suburbs)
- Lead capture wired to Supabase
- FAQs updated — data sources accurate, James Elks acknowledged
- Phone number auto-formatting in report modal
- PDF report redesigned — typewriter/brutalist style, correct filename format
- Mobile CSS fixes + full accessibility review (ARIA, focus management, contrast, skip link)
- Australian property data research — all 8 states/territories + NSW bedroom attribute options
- Data freedom manifesto page (`/manifesto.html`) + homepage teaser strip
- FAQ data freedom section updated with full per-state findings
- Contact form on manifesto (Netlify Forms, no email exposed)
- Favicon (SVG, 3-circle mark) + OG/Twitter card meta tags on all pages
- Privacy notice on main tool (dismissible, localStorage)
- robots.txt

---

## BACKLOG

Chunks are roughly prioritised but reorder freely.
Tasks labelled **[T]** (Tristan), **[C]** (Claude), or **[T+C]** (back and forth).

---

### 🔜 PDF v2 — combined improvement list
*Agreed changes from analysis session (July 2026). Implement together in one pass.*

**Layout / structure (Tristan)**
- [ ] Text is too small everywhere except tables — body copy and labels need to be bigger
- [ ] Combine pages 2 (letter) + 3 (result) — letter at top, result content below, saves a page
- [ ] Combine pages 4 (comparables) + 5 (continuation) onto one page — smush images up to make room, keep table. Add section title: "Properties sold closest to your budget"
- [ ] Logo on cover page
- [ ] Page 7 (what-if) needs a full rethink — currently hard to understand, not just cosmetic fix

**Cover (Claude analysis)**
- [ ] Score is sitting too low — centre it vertically (~40% down the page)
- [ ] Too much dead space above the score

**Result page (Claude analysis)**
- [ ] "At or above the median" callout text is wordy — simplify to "≥ median" or show $0 gap
- [ ] N/A bars look like bugs — add "Data coming" label or different visual treatment

**Comparables table (Claude analysis)**
- [ ] GAP value and REA link are colliding in the same column — give REA its own space or move below price

**Suburb table — page 6 (Claude analysis)**
- [ ] Searched suburb is not highlighted — should stand out with a distinct row colour
- [ ] *Tristan: page 6 is actually great — small improvements only*

**What-if — merge into page 2 (Tristan + Claude)**
- [ ] Remove what-if as a standalone page entirely
- [ ] Add what-if content to the bottom of the new combined page 2 (letter + result + what-if)
- [ ] Reframe as plain-language narrative: "If your budget were $X more, your score jumps from 42 to 67 — Marrickville would come into range." Story, not widgets.
- [ ] Keep it brief — 2–4 lines, feels like a coda to the result, not a separate section

**Final page structure — 4 pages:**
1. Cover
2. Letter + result + what-if narrative
3. Comparable sales (images + table, all on one page)
4. Suburb comparison table


---

### 🔜 PDF redesign — big rethink needed
*Tested in production — comparable property cards are not showing at all in the PDF output. This is a regression from an earlier working version. Overall design needs a proper rethink, not just a patch.*

- **[T+C]** Review what the PDF used to show vs what it shows now — identify what broke
- **[T+C]** Decide on the right approach: fix the comparable cards, or redesign the whole PDF from scratch
- **[C]** Rebuild PDF generation to reliably include: score, what-if cards, and comparable property cards with addresses
- **[T]** Test output across several suburbs before deploying

---

### 🔜 NEXT SESSION — GitHub + automated NSW data refresh

**Goal:** Move the project to GitHub, connect Netlify to auto-deploy from it, and set up a weekly GitHub Actions workflow that pulls fresh NSW data from nswpropertysalesdata.com and upserts it into Supabase automatically.

#### Step 1 — Create GitHub repo
- **[T]** Create a free account at github.com if Tristan doesn't have one
- **[T]** Create a new **private** repository called `getreal` (private because SUPABASE_URL is hardcoded in search.html)
- **[T]** Install GitHub Desktop (easiest for non-CLI) from desktop.github.com OR use `git` in terminal
- **[T]** Clone the empty repo locally, copy all project files in, commit and push
  - Files to include: search.html, index.html, faq.html, manifesto.html, styles.css, suburb-data.json, favicon.svg, robots.txt, all .py scripts
  - Files to exclude: archive.zip (too large), any .env files, __pycache__

#### Step 3 — Add Supabase secret to GitHub
- **[T]** In GitHub repo: Settings → Secrets and variables → Actions → New repository secret
- Name: `SUPABASE_SECRET`
- Value: the Supabase SECRET key (not the publishable one — the one used in the pipeline scripts)
- This lets GitHub Actions connect to Supabase without the key appearing in any code

#### Step 4 — Update load_nsw_csv.py to auto-download
- **[C]** Add auto-download of archive.zip from `https://nswpropertysalesdata.com/data/archive.zip` when the file isn't present locally
- The script already handles everything else — parse, filter to 13 months, upsert with merge-duplicates

#### Step 5 — Create GitHub Actions workflow
- **[C]** Create `.github/workflows/refresh-nsw-data.yml`
- Schedule: weekly, Monday 6am AEST (Sunday 8pm UTC)
- Steps: checkout repo → install Python deps → download archive.zip → run load_nsw_csv.py → done
- Uses `SUPABASE_SECRET` from GitHub secrets
- No `--clear` flag — just upsert, so new sales are added and existing ones update in place
- On failure: GitHub emails Tristan automatically

#### How it works end-to-end (after setup)
```
Every Monday 6am:
  GitHub Actions pulls archive.zip from nswpropertysalesdata.com
    → runs load_nsw_csv.py
      → upserts new records into Supabase property_sales
        → GetReal immediately serves fresher data
```
James's site updates daily, so we'll be at most 7 days behind current sales. That's fine.

#### Notes for Claude next session
- suburb-data.json must be committed to the repo — Netlify needs it for the static site
- The .py pipeline scripts don't need to be in the repo to work (Actions can run them from the repo), but include them anyway for reference
- Double-check the Supabase `property_sales` table has a unique constraint on `(suburb, state, property_type, sale_date, address_full)` or similar — needed for upsert dedup to work correctly. If not, add it before running the automated refresh.
- James Elks hasn't replied on LinkedIn yet — worth a follow-up once the tool is live. Crediting his work properly matters.
- Current data is from a one-time load (May 2026 approx). The automated refresh will add new records going forward but won't backfill any gap between then and now — that's fine, the 13-month window query handles it.

---

### 🐛 Bug: Nearby suburb is always "Bonshaw" (and loops)
*Root cause: the NSW what-if "Nearby suburb" card falls back to iterating through ACTIVE_SUBURBS alphabetically when no `nearby` array exists for the searched suburb. "Bonshaw" happens to be near the top alphabetically. Clicking it has the same problem, creating a loop.*

- **[C]** ✅ Fix the nearby suburb logic — now queries Supabase for suburbs in the same postcode prefix
- **[T]** 🔜 Test on redeploy: search a Sydney suburb and verify nearby suggestion is geographically sensible
- **[T]** 🔜 Test on redeploy: clicking nearby suburb should suggest a different nearby, not loop back

---

### 💡 Feature: Suburb map view with nearby sales and surrounding suburbs
*Triggered by the nearby suburb bug — users should be able to see the geography, not just a name.*

- **[T+C]** Design the experience — is this a panel that expands below results, or a link-through to a map page?
- **[C]** Use Maps JavaScript API to render the searched suburb with recent sold properties as pins (price on hover/click)
- **[C]** Overlay surrounding suburbs as clickable regions — clicking one re-runs the search for that suburb
- **[C]** Colour-code surrounding suburbs by score at current budget (green = more realistic, red = less)
- **[T]** Test and give UX feedback
- *Note: this could replace or enhance the "Nearby suburb" what-if card entirely*

---

### Get individual sale records for VIC, QLD and other states
*Ray White API is a strong candidate — same API used for NSW bedroom enrichment, just different stateCode and postcode range. See `TRIED-TOOL-01.md` for full details and staged plan.*

- **[T+C]** Confirm Ray White NSW extraction works end-to-end (Stage 2 matching test)
- **[C]** Run Ray White extraction for VIC (postcodes 3000–3999), QLD (4000–4999)
- **[C]** Wire VIC + QLD scoring engines against real individual sale records
- **[T]** Test and deploy

---

### Data freedom manifesto
*GetReal's data freedom angle is a genuine differentiator and a public good argument. Make it prominent.*

- **[T+C]** ✅ Decide where the manifesto lives — both: `/manifesto.html` + teaser strip on the homepage
- **[C]** ✅ Write a proper manifesto page: what data is locked, why it matters, what NSW got right, call to action
- **[C]** ✅ Add a visible but not obnoxious entry point from the homepage (teaser strip + indicative note link)
- **[T]** 🔜 Review tone and content on redeploy — should feel principled and direct, not ranty
- *Note: FAQ already has a "Why can't you show me data for every state?" section as a placeholder for this*

---

### NSW data — known gaps (pre-launch blockers)
*NSW scoring engine works but has three significant gaps that make it not truly launch-ready.*

#### 1. Bedroom/bathroom/car space data missing
*Every buyer searches by bedrooms. We're using national distribution estimates right now — not real data. See `TRIED-TOOL-01.md` for approaches already ruled out.*
- **[T+C]** Find a viable free source for NSW bedroom/bathroom/car space data
- **[C]** Write enrichment pipeline → update property_sales rows
- **[C]** Update NSW scoring to include real beds/baths, remove "coming soon" notes
- **[T]** Test and deploy

#### 2. Data completeness — validated July 2026
*Queried Supabase directly. Results:*
- *146,330 records — healthy volume*
- *Date range: June 2025 to May 2026 (~12 months). Currently ~6 weeks behind.*
- *High-volume suburbs (Parramatta, Blacktown, Liverpool etc.) all look right*
- *Low-count suburbs are genuine tiny rural localities — not missing data*
- *Verdict: data is complete for the loaded period. Gap is recency, not coverage.*

#### 3. No automated data refresh
*Current dataset is a static one-time load. New sales are not coming in.*
- **[T+C]** Understand the update frequency of nswpropertysalesdata.com (weekly? monthly?)
- **[C]** Write a scheduled refresh script that checks for new data and loads it into Supabase
- **[T+C]** Pick a host for scheduled runs (GitHub Actions is the obvious free option)
- **[T]** Test a full refresh end-to-end

#### VIC
- **[T+C]** Find a free VIC individual sales data source (currently only aggregated medians)
- **[C]** Write pipeline, load into Supabase, wire live scoring + Street View
- **[T]** Test and deploy

#### QLD
- **[T+C]** Find a free QLD property sales data source with bedroom data if possible
- **[C]** Write pipeline, load into Supabase, wire scoring + what-ifs + comparables
- **[T]** Test and sense-check, then deploy

---

### realestate.com.au property links
*Smart deep-link to the REA listing page for each comparable property.*

- **[T+C]** ✅ Figure out the URL pattern — address → slug conversion rules
- **[C]** ✅ Build address-to-URL converter and add link to each comparable card
- **[C]** ✅ Test edge cases (unit numbers, hyphenated streets, etc.)
- **[T]** 🔜 Verify links resolve correctly on live site (test on redeploy)
- **[T+C]** Batch-verify generated REA URLs actually resolve; store confirmed URLs in `property_sales` table and serve from DB instead of generating client-side

---

### User testing and engagement
*Do this before launch. Tristan has UX research background — use it.*

- **[T]** Recruit 5–10 people who are actively searching for property (friends, family, community groups)
- **[T]** Run sessions: observe them using the tool, note where they hesitate or get confused
- **[T]** Collect feedback on: does the score feel right? Is the output useful? What's missing?
- **[T+C]** Prioritise changes based on findings and add to Small UX improvements or other chunks
- **[T]** Repeat with a second round after changes are made

---

### Acknowledge NSW data source
- **[T]** Awaiting reply from James Elks (contacted via LinkedIn)
- **[C]** ✅ Acknowledgement added to FAQs

---

### Lead capture
- **[C]** ✅ Wired to Supabase
- **[T]** ✅ Tested end-to-end
- **[T+C]** Decide what to do with leads — email notification when a new one arrives? *(nothing for now)*

---

### Automated data refresh
- **[T+C]** Figure out how to keep each state's data current automatically (free, no paid API)
- **[C]** Write scheduled refresh scripts per state
- **[T+C]** Pick a host for scheduled runs (GitHub Actions is the obvious free option)
- **[T]** Test a full refresh end-to-end

---

### Property map
- **[T+C]** Decide what the map shows (all suburb sales? just comparables? heatmap?)
- **[C]** Wire Maps JavaScript API — render map with property pins, price + date on each pin
- **[T]** Test and deploy

---

### Add remaining states
*After NSW, VIC, QLD are solid. Same pattern each time.*
- South Australia
- Western Australia
- ACT
- Tasmania
- Northern Territory

Each: find free data source → pipeline → scoring → what-ifs → comparables → test → deploy

---

### Launch
*Target: bedroom data for at least NSW + user testing complete.*
- **[T+C]** Define target audience and launch channels (Reddit r/AusFinance, Facebook property groups, LinkedIn)
- **[T+C]** Draft launch messaging
- **[T]** Set up custom domain (getreal.com.au or similar)
- **[T+C]** Work out monthly running costs (Supabase, Netlify/host, Google APIs, domain)
- **[T+C]** Decide on monetisation model to cover costs (one-time report fee, optional tip, lead gen, referral)
- **[T]** Implement chosen monetisation approach

---

### GetReal as a product suite *(big picture idea — discuss when ready)*
*Tristan has deep background running the NAB/REA partnership and years in property and mortgages. Lots of ideas for tools across the full property ownership lifecycle. The "Get Real" brand has legs as an umbrella for honest, no-BS tools that help people make better decisions — not just the search realism checker.*

*Homepage is now live at index.html with Tool 01 (property search) and Tool 02 (paying it off) teaser.*

#### Tool 02 — "Paying it off?" concept (fleshed out)
*Track your property value and mortgage together against the market. Flag when something has changed enough that you should act. Three triggers:*
- *LVR threshold crossed — property value has risen enough to put you in a better rate tier*
- *Broad rate drop — market rates have moved and your bank hasn't passed it on*
- *New customer rip-off — your bank is offering new customers a better deal than you're on*

*The goal: keep the bastards honest. (Don Chipp, Australian Democrats, 1980.)*

*Phase 2 idea: email reminders when a trigger fires — turns it into a tracking tool, not just a one-off check.*

- **[T]** Flesh out the bigger vision and bring it back for discussion
- **[T+C]** Decide which tool to build second — Tool 02 is the strongest candidate
- **[T+C]** Figure out data sources: property value estimates (free?), RBA rate feed, bank rate scraping

---

### Small UX improvements
*Collect items here until there are enough to batch into one session.*

- ✅ Phone number input auto-formats to 04XX XXX XXX on user input
- Mobile layout — elements don't resize properly on small screens (form cuts off right edge, what-if cards wrap awkwardly, comparable cards stack but sizing is off)
- 🔜 QLD tool behaviour — unknown issue when Queensland is selected. Investigate what happens end-to-end: state change, suburb autocomplete, coming-soon box, any JS errors. Test in production vs local.
- *(add more here)*

---

### Other ideas
*(add here as they come up)*
- Mobile responsiveness audit
- Analytics — how many searches, which suburbs, conversion to PDF
- FAQs improvements

---

### 🔜 Testing on redeploy
*Batch these up and test in one go when the next deploy happens. Don't deploy just to test.*

- Nearby suburb fix — search a Sydney suburb (e.g. Bondi), verify the nearby suggestion is geographically sensible (not Bonshaw, not inner west)
- Nearby suburb loop — click the nearby suggestion, confirm it proposes a different suburb rather than looping back
- REA property links — spot-check 5–10 links actually resolve on realestate.com.au
- PDF redesign — check layout, fonts, filename format, budget line, what-if cards
- Mobile layout — test on an actual phone: form, what-if cards, comparable cards
- Accessibility — test with keyboard-only navigation and a screen reader
- Manifesto page — read through, check tone, verify all state rows look right
- Contact form — submit a test message, confirm it lands in Netlify dashboard, set notification email to Gmail in Netlify settings

---

### 📱 Mobile-friendly CSS + accessibility review
*The tool works on desktop but breaks on small screens. Do this before user testing.*

- **[C]** Audit every major layout section: search form, results panel, score display, what-if cards, comparable cards, FAQs
- **[C]** Fix form — inputs and dropdowns should stack and fill width on small screens
- **[C]** Fix what-if cards — grid should collapse to single column on mobile
- **[C]** Fix comparable cards — address text and street view image should reflow cleanly
- **[C]** Accessibility review: keyboard navigation, focus states, ARIA labels, colour contrast, screen reader landmarks
- **[C]** Fix any accessibility issues found
- **[T]** 🔜 Test on an actual phone and with keyboard-only navigation (test on redeploy)

---

### 🧬 NSW bedroom + bathroom data
*The single biggest gap in NSW scoring. Beds/baths use national distribution estimates right now.*

- **[T+C]** Find a viable free source — see `TRIED-TOOL-01.md` for what's already been ruled out
- **[T+C]** Pick best viable approach and scope the work
- **[C]** Build enrichment pipeline → match addresses to property_sales rows
- **[C]** Update NSW scoring to use real beds/baths, remove "coming soon" notes from what-if cards
- **[T]** Test and sense-check, then deploy

---

*Add new chunks any time. Pick the next one when ready.*
