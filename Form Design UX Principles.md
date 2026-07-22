# Form Design UX Principles

These patterns were established building the GetReal deposit calculator (`deposit.html`) — a multi-step wizard on a brutalist dark web tool. Use this doc to prompt a UX review or to brief future form builds.

---

## Screen structure

Every question screen follows this layout, top to bottom:

1. **← back** — ghost text link, top-left, monospace, uppercase. No label next to it.
2. **Question headline** — large, bold, plain English. One question per screen.
3. **Sub-text** — one short sentence in monospace, muted colour, directly below the headline. Specific, not generic. Tells the user *why* this matters, not what to do.
4. **Input or choices** — the only interactive element on the screen.
5. **"Why does this matter?" toggle** — collapsed by default, reveals detail for curious users. Label uses a down arrow `↓` that flips to `↑` when open. Never show this content expanded by default.
6. **Continue / Next button** — full-width, primary style, bottom of screen. Disabled until input is valid.

---

## Choice buttons (binary / multi-option)

**Order:** Always put the affirmative/Yes answer first, No second. Users scan top-to-bottom — the positive path should be the natural first target.

**Format:** Use an em dash ( — ) to separate the short answer from the explanation.
```
Yes — I have credit cards
No — I don't have credit cards
```

**Do not** put information or sub-text inside the button itself (old pattern). Keep the button label short. Move explanation to the sub-text above or the toggle below.

**For non-binary choices** (three or more options that aren't Yes/No), use plain descriptive labels without em dashes:
```
Keep them as they are
Reduce the limits
Close them completely
```

**Never** put "No" before "Yes" on a binary screen.

---

## Back button

- Positioned top-left, above the question headline
- Ghost style: no background, no border, dim colour, uppercase monospace
- Label: `← back` — nothing else. No step number, no screen name.
- On choice screens: the choice IS the next action. No separate Next button is needed.
- On input screens: back is at the top, Next/Continue is at the bottom (maximum separation = no accidental taps).

**Do not** use a bottom navigation bar with Back on the left and Next on the right. This only works when every screen has exactly two navigation actions — multi-step forms with choice screens don't satisfy that condition.

---

## "Tell me more" / detail toggles

Used in two places:

**On input screens** (below choices): `Why does this matter?` or `Why would I do this?`
- Shows general context about the question
- Collapsed by default

**On review/apply screens** (below each item heading): `Tell me more`
- Hides the explanatory body text
- Only the bold heading is visible by default — this keeps the screen scannable
- Users who want the detail can expand each item individually

Toggle HTML pattern:
```html
<button class="fhb-toggle" onclick="toggleDetail('panel-id','arrow-id')">
  <span id="arrow-id">↓</span> Why does this matter?
</button>
<div class="fhb-detail" id="panel-id" style="display:none">
  Detail text here.
</div>
```

---

## Review screens

Split into two screens — never combine on one page:

**Screen 1 — "Here's what you told us."**
Rows of: label + value + change link. Lets users verify their inputs before committing to the calculation.

**Screen 2 — "Here's what we'll apply."**
Bold headings only, visible by default. Each heading states the rule plainly (e.g. "Your borrowing cap is set at 95%"). Detail hidden behind "Tell me more" toggles. Avoids overwhelming users with technical information they didn't ask for.

---

## Language rules

- **Headlines:** Plain English, no jargon. If a technical term is unavoidable, define it inline in brackets — e.g. "your LVR (Loan to Value Ratio)".
- **Sub-text:** One sentence. Specific to the user's situation. Not generic ("this affects your calculation" is banned).
- **Hedging:** Use "may apply" not "will apply" for anything that depends on price or circumstances not yet known.
- **Tone:** Direct, honest, no fluff. This is a tool for people making major financial decisions.

---

## What not to do

- No information inside button labels (old anti-pattern)
- No step labels or screen names next to the back button
- No expanded detail panels by default
- No bottom bar navigation with Back + Next side-by-side
- No "Yes" below "No" on binary screens
- No em dashes on non-binary choice screens (it implies Yes/No when there isn't one)
- No generic sub-text like "Your answer affects how much you can borrow"
