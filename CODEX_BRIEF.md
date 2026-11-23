# CODEX BRIEF — Murder Board

**Written:** 2026-11-21
**For:** Codex (or any agent picking this up cold)
**Companion:** `REVIEW.md` — the full read-only audit, with rationale. This file is the build
order, the UI system, and the verified component sources. Read `REVIEW.md` once, then work from
here.

---

## 0. Ground rules

This repo is **static, zero-build, zero-dependency**:

- `app/index.html` loads plain scripts; `app/app.js` is UMD-shaped and runs in browser + Node.
- `app/style.css` is the only stylesheet.
- No React, no Tailwind, no bundler, no npm install. Do not introduce one for buttons.
- `app/case-data.js`, `agents-data.js`, `cache-data.js`, `eval-data.js`, `photos-data.js` are
  GENERATED. Never edit by hand.
- `app/config.js` is gitignored. Never commit a key.

Non-negotiables (from `CODEX_HANDOFF.md`):

1. **No quote, no finding.** Never weaken `quoteOk` or the validators.
2. **The runner owns the arithmetic.** Never let the model's lead score stand.
3. **A failed step never kills the run.**
4. **Judges the file, never a person.** Every contradiction keeps its innocent reading.
5. **No new claims in the UI.** If it is not in the book, it does not render.
6. Smallest sensible change. Label VERIFIED only for what you actually ran.

---

## 1. Verdict, short

The product is stronger than its interface. The differentiators — quote check in code, runner
arithmetic, ten squad chairs, four cases with answer keys — are either buried or invisible. The
UI reads as six dark tabs of output, while the corkboard (the one screen that looks like the
product) is a flex-wrapped gallery with no filter, isolate, or zoom.

Two tracks, in this order:

- **Track A — proof:** make the quote check and the reconciliation inspectable.
- **Track B — presentation:** make the demo and the board legible in ten seconds.

Do Track A before adding any surface area. Do the button system early, because it touches every
screen Codex will edit.

---

## 2. P0 — build these first

### P0-1. Dropped-findings ledger + quote receipts

**Why:** `book.dropped` is only a number. `book.log` gets one line per step. The rejected claim,
its fake quote, and the document it claimed are discarded. This is the product's strongest proof
and the first question a judge will ask.

**Build:**

- Capture every rejection in a structured array: `step`, `chair`, `claim`, `quote`, `doc_id`,
  `reason` (`quote not in cited document` / `unknown doc id` / `quote too short`), and
  `closest_match` (nearest normalized substring, or `none`).
- Add a **Dropped findings** panel on Judgments; header `dropChip` opens it.
- On accepted findings, store a **receipt**: `doc_id`, `char_offset` of the normalized match,
  `normalized_length`. Render `verified · doc03 · offset 1,204` in the quote modal and on
  contradiction cards.
- Cache replays must show the same drops (the cache already carries the outputs; re-run the
  validators or store the receipt alongside the cache).
- Keep `book.dropped` as the count; add `book.dropped_items`.

**Acceptance:** the Delgado replay shows exactly the cached drop count, lists each dropped claim
with a document and a reason, and every accepted contradiction shows a doc + offset that matches
the source text.

### P0-2. Judge mode (presentation pass)

**Why:** the demo is 3 minutes; the UI is a desktop workspace with a 300px feed and 12–14px type.
The story is not visible on a projector.

**Build:** a full-screen mode (header button + `P`):

- hides header controls, model line, tabs, footer;
- enlarges the active screen and body type;
- fixed sequence with `←` / `→`:
  **Folder → Squad room → Board → star contradiction → Judgments → Brief → Eval**;
- thin `1/7` progress marker + `Esc` exit;
- pauses the replay feed between beats instead of dumping 40 lines.

**Acceptance:** the whole 3-minute script can be run with arrow keys only; exit restores the
previous screen; no runner changes.

### P0-3. Entity links, deep links, quote highlighting

**Why:** names are clickable only on the board. “Webb CONTRADICTED” in the alibi table is plain
text. Quote modals open a document with no marker. Nothing is linkable.

**Build:**

- Person names in alibis, contradictions, leads, questions, and the brief open `openProfile`.
- Document ids everywhere open the document drawer.
- In the document view, wrap the quoted span in `<mark>` and scroll it into view.
- Hash routes: `#/delgado-2019/judgments`, `#/delgado-2019/person/marcus-webb`,
  `#/screens-2025/contradiction/2`. Back/forward works; reload restores.
- “Copy citation” on every quote: `doc04 · Webb statement 2020 · "…"`.

**Acceptance:** every person/document id in Judgments, Alibis, Leads, Questions, and Brief is a
link; reloading a deep link opens the same screen/entity; opening a quote highlights the exact
span.

### P0-4. Ledger reconciliation table

**Why:** the missing second casing is the second catch, but it renders as one more gap card. The
count mismatch — scene report 2, ledger 1 — is never shown as a table.

**Build:** a **Ledger reconciliation** block on Judgments (or CSI):

| Item | Mentioned in scene report | Logged in ledger | Delta |
|---|---|---|---|
| Shell casing, by desk | 2 | 1 | **−1 missing** |

One row per item; missing rows first; each row opens the two source quotes. Derive from
`book.ledger`, `book.csi_gaps`, and `book.evidence_items`.

**Acceptance:** the Delgado case shows the casing row as 2 vs 1, sorted first; the row opens both
quotes.

### P0-5. Board filters + click-to-isolate

**Why:** `renderBoard` puts every person, document, evidence item, gap, and legend into one
`flex-wrap` ribbon. There is no filter or isolation. Adding documents makes it unreadable.

**Build (in this order):**

- Filter chips above the board: **All / Contradictions / Gaps / People / Documents / Evidence**,
  plus a person filter. Dim non-matching pins and their yarn; do not reflow.
- Click a person pin → fade everything not connected by a documented link or contradiction;
  click empty cork to reset.
- Keep yarn deterministic. No random positions.
- Zoom/pan and drag can come later; filters + isolate are the demo value.

**Acceptance:** selecting “Contradictions” leaves only the contradiction pins and their yarn
visible; selecting a person dims unrelated pins without moving any pin; reset restores.

### P0-6. Board headline and Duck stamp

**Why:** the largest text on the board is **“WHO DID IT”**. The product explicitly does not answer
that. It is the wrong promise in the biggest type.

**Build:** replace with **“WHAT DOES THE FILE CONTRADICT?”** (or “WHAT THE FILE SAYS”), victim and
death window as the subline. Keep the question mark if desired.

On the Duck folder stamp, add **“in reality — not by this board”** next to “SOLVED 2024”.

**Acceptance:** no “WHO DID IT” string remains; the Duck stamp cannot be read as a system claim.

### P0-7. Replay/live must be impossible to misread

**Build:** persistent badge in the header and on Brief/Eval — **REPLAY · saved 11:35** (amber) or
**LIVE · key in this tab** (red). Hide `#liveKey` behind a “Live run (advanced)” dialog on the
public build. Default to replay.

**Acceptance:** a screenshot of any screen shows which mode produced it.

---

## 3. P1 — after P0

### P1-8. Tomorrow’s assignments, by chair

`AGENTS.md` promises per-agent assignments; the UI shows only a flat lead list. Render a grouped
panel (Records / Digital / Interviewer / CSI / Analyst / Prosecutor) from `leads` + `gaps`:
action, why (quote), expected outcome, checkbox. Include it in the brief export.

### P1-9. The Clock as an alibi chart

Under the event timeline, one row per person: death-window band, claim markers, record-verified
markers, a hairline where they disagree, labelled with the rating. Data already exists in
`alibis`, `timeline`, `machine_events`.

### P1-10. Search / command palette

`Ctrl/⌘+K` over persons, documents, contradictions, gaps, quotes. Enter opens; `→` opens the
source at the highlighted span. `/` is free.

### P1-11. Run receipt + retry chair

Collapsible receipt: duration, mode, steps, drops, failures, model per chair, fallback count.
Retry button on a red chair; “Use saved run” when a live run fails mid-demo.

### P1-12. Deterministic Q&A in the squad room

`sendChat` is a regex router. Add intents over the book (no model call): top gap, weakest alibi,
who contradicts, show `<name>`, why is `<name>` contradicted, what is missing. If no intent, list
what it can answer. Never free-text.

### P1-13. Packet export

“Download murder book” `.md` + print layout: folder, brief, contradictions with both quotes +
innocent readings, alibi table with windows, reconciliation, gaps by chair, lead arithmetic,
quote-check receipt. Plus “Copy brief as Markdown” and a run permalink.

### P1-14. Accessibility + mobile

Arrow-key navigation between pins; `role=status` on run status/drop chip; severity glyphs as well
as color; body text ≥14px on Judgments/Clock/Eval; one step more contrast for `--muted`; remove the
invalid duplicate `--muted: #9a97 8f;` at `style.css:8`. Below 640px replace the corkboard with a
grouped list (people / documents / gaps / threads).

### P1-15. Portrait fallback

`photoHtml` falls back to surname matching, so two people with the same surname can share a face.
Remove the surname fallback; use initials when there is no exact fixture. Same collision risk in
`personProfileData`; note it next to the Records “never merge” claim.

### P1-16. Copy drift

`README` “both cases” vs four; `CODEX_HANDOFF` lists print stylesheet as future work (it exists);
`EVAL` says “two models” in Method then evaluates four; header says “Built today”; the
“Nobody packages…” line in `DEMO_SCRIPT`/`SUBMISSION` was already flagged by the competitor check.
Fix before the next run.

---

## 4. UI overhaul — the buttons

### 4.1 Diagnosis: why it looks cheap

- **Default browser controls** are still visible in places: the replay checkbox, the raw password
  field, native selects, a plain `Send` button, a plain `Print` button.
- **No single button system.** Header actions, tabs, chips, table “view”, modal close, and
  form submits all have different heights, radii, weights, and hover behavior.
- **Dark-on-dark hierarchy.** Panels, buttons, and inputs sit within 2–3 shades of each other, so
  nothing reads as the primary action.
- **Primary actions are small.** `Work the Case` is a 14px uppercase button in a crowded header;
  `Submit` and `Send` are afterthoughts.
- **Pills + rounded rectangles + square chips** coexist. The board is analog; the controls are
  generic SaaS.
- **Micro-type.** 11–12px labels on muted colors disappear on a projector.
- **The best surface (corkboard) has no controls.** The worst surfaces (forms, tables) have
  unstyled ones.

### 4.2 Direction: “case file, not SaaS”

The UI should look like a **printed police file with stamped actions**, not a dashboard:

- paper cream surfaces, black ink, one red stamp accent, one amber attention accent;
- 2px borders, hard 3px offset shadows, no blur, no glow, no gradient;
- 3px radius (paper cut), never pill for primary actions;
- uppercase 11–12px letterspaced labels for actions; sentence case for content;
- press = 2px down, shadow collapses;
- the corkboard stays exactly as it is.

The board already proves this works. Carry its language into the controls.

### 4.3 Button system to implement

One base class, `.btn`, plus modifiers. Put it in `app/style.css` (or a new `app/ui.css` linked
before it) and remove per-screen button styling.

| Token | Value | Use |
|---|---|---|
| `--btn-h-sm` | 30px | table actions, icon buttons |
| `--btn-h-md` | 38px | default |
| `--btn-h-lg` | 46px | Work the Case, Download packet |
| `--btn-radius` | 3px | all except chips |
| `--btn-border` | 2px solid | all |
| `--btn-shadow` | 3px 3px 0 rgba(0,0,0,.5) | default |
| `--btn-shadow-hover` | 4px 4px 0 rgba(0,0,0,.55) | hover |
| `--btn-shadow-active` | 1px 1px 0 rgba(0,0,0,.5) | active |
| `--focus` | 2px solid `--amber`, offset 2px | `:focus-visible` |

| Variant | Look | Use |
|---|---|---|
| `.btn--primary` | red `#d64541` fill, cream text, dark red border, red-black shadow | Work the Case, Send, Download packet, retry |
| `.btn--secondary` | paper `#f4f1e8` fill, ink `#1c1c1c`, tan border | Print, Open record, Copy citation, Run census |
| `.btn--outline` | transparent, cream text, `--line-strong` border, no shadow | secondary actions on dark panels |
| `.btn--ghost` | no fill/border, muted text, underline on hover | Close, Back, Centre, Reset layout |
| `.btn--danger` | transparent, red text/border | Dispute, Delete, Report |
| `.btn--chip` | 26px high, 999px radius, 1px border, 11px uppercase | board filters, case tags, severity filters |
| `.btn--icon` | 32×32, centred 14px icon, 1px border | close, menu, zoom, fit |

**Sizes:** `.btn--sm` 30px / 0 10px; default 38px / 0 14px; `.btn--lg` 46px / 0 20px. No other
heights. Icon-only is always 32×32.

**States, all variants:**

- hover: `translate(-1px,-1px)`, larger shadow;
- active: `translate(2px,2px)`, shadow collapses;
- `:focus-visible`: 2px amber outline, offset 2px (never remove outline);
- `:disabled`: 45% opacity, no shadow, `cursor:not-allowed`;
- `[aria-busy=true]`: inline 12px spinner + label remains visible.

**Never:** gradients, glass, glow, pill primary, `border-radius: 999px` outside chips, pure
`#000`/`#fff`, text below 11px, icon-only buttons without `aria-label`.

### 4.4 Placement map

| Screen / control | Variant | Notes |
|---|---|---|
| Header `Work the Case` | primary + lg | progress fill during run; disabled state shows a spinner, not “wait” |
| Header replay/live | switch + badge | replace the raw checkbox; badge is a stamp |
| Header live key | move to modal | “Live run (advanced)”; never in the header |
| Tabs | folder tabs | active = paper fill, red top rule, ink text; inactive = transparent, 1px border; arrow-key nav |
| Board filters | chips | dim, never reflow; person filter as a select |
| Board zoom/fit | icon | 32×32 |
| Threads list | outline rows | currently fine; use `.btn--outline` height 38 |
| Pin cards | keep | already good; only add focus ring |
| Intake `View` | ghost + sm | table row action |
| Door 2 `Run census` | secondary | label “Simulation” badge next to it |
| Judgments `Show dropped` | secondary | opens P0-1 ledger |
| Judgments `Open source` | ghost + sm | on every finding |
| Alibi row | ghost link | person name opens the drawer |
| Brief `Print` | secondary | |
| Brief `Download packet` | primary | |
| Brief `Copy Markdown` | ghost | |
| Chat `Send` | primary + md | not full-width |
| Chat chips | chip | |
| Modal `Close` | icon + ghost | |
| Modal `Open document` | secondary | |
| Eval `Compare baseline` | secondary | |

### 4.5 Inputs, tabs, and the rest

- Style `input`, `select`, `textarea`, and `input[type=search]` with the same 2px border, 3px
  radius, `--panel` fill, cream text; focus = amber border + 2px offset ring.
- Replace the replay checkbox with a two-state switch labelled REPLAY / LIVE.
- Tabs: folder shape (6px top radius), active paper with red 3px top rule. Keep the existing
  content, change the chrome only.
- Modal and drawer: paper surface, red top rule, ink text; close is an icon button, not a floated
  text button.
- Tables: keep the current ruled-paper look, but raise body to 14px and put actions in the last
  column as ghost sm buttons.
- Do not touch `.corkboard`, `.pin-card`, `.pin-note`, `.yarn*` except focus rings.

---

## 5. Verified button sources

All licenses checked on GitHub, 2026-11-21.

| Source | Stars | License | Last push | What it gives you | Use it for |
|---|---:|---|---|---|---|
| [papercss/papercss](https://github.com/papercss/papercss) | 4,199 | **ISC** | 2025-07-31 | Hand-drawn 2px borders, offset shadows, `.paper-btn`, outline variants, large/small/block | The **visual treatment** of secondary buttons and the paper surface |
| [sButtons/sbuttons](https://github.com/sButtons/sbuttons) | 401 | **MIT** | 2022 (archived) | 50+ pure-CSS variants: `outline-btn`, `shadow-3d-btn`, `handwritten-btn`, `rounded-btn`, `disabled-btn` | Reference for state styling; do not add as a dependency |
| [ganapativs/bttn.css](https://github.com/ganapativs/bttn.css) | 2,053 | **MIT** | 2022 | Clean system: `.bttn-bordered`, `.bttn-minimal`, `.bttn-material-flat`, `.bttn-pill`, `.bttn-danger`, sizes | The **structural base**: class roles and size scale |
| [youneslaaroussi/ui-buttons](https://github.com/youneslaaroussi/ui-buttons) | 3,873 | **MIT** | 2022-08-01 | 100 single-purpose CSS buttons, each with HTML/CSS/preview | **Cherry-pick specific shapes** (below) |
| [shadcn-ui/ui](https://github.com/shadcn-ui/ui) | 128k | **MIT** | 2026-11-21 | Accessible button state table and variant naming | **Reference only** — React/Tailwind, do not integrate |
| [uiverse-io/galaxy](https://github.com/uiverse-io/galaxy) | 15k | **MIT** | 2024 | 1,000s of community CSS/Tailwind snippets | Last resort for one-off styles; quality varies |

### 5.1 The combination to use

Do **not** import a library. Port rules into `.btn`:

1. **Structure and size scale** from `bttn.css` (`bttn-bordered` / `bttn-minimal` / `bttn-danger`,
   `sm/md/lg`).
2. **Surface treatment** from PaperCSS: 2px border, imperfect 3px radius, hard offset shadow,
   paper fill.
3. **Special shapes** from three `ui-buttons` entries (below), renamed and re-colored with the
   app tokens.

That gives a coherent system without a framework, a build step, or 100 unused classes.

### 5.2 Specific `ui-buttons` picks

Class names inside these files are `btn-57`, `btn-80`, etc. **Rename them**; they are references,
not drop-in classes.

**1. `81-progress-fill-right` — the Work the Case button.**
Fill sweeps right during a run. Perfect for a 7.5-minute live run.
[Folder](https://github.com/youneslaaroussi/ui-buttons/tree/main/buttons/81-progress-fill-right) ·
[CSS](https://github.com/youneslaaroussi/ui-buttons/blob/main/buttons/81-progress-fill-right/progress-fill-right.css)

![Progress fill](https://raw.githubusercontent.com/youneslaaroussi/ui-buttons/main/buttons/81-progress-fill-right/preview.webp)

**2. `55-offset` — the secondary / filter button.**
3px border, pill, hard offset shadow. Reads as a printed label.
[Folder](https://github.com/youneslaaroussi/ui-buttons/tree/main/buttons/55-offset) ·
[CSS](https://github.com/youneslaaroussi/ui-buttons/blob/main/buttons/55-offset/offset.css)

![Offset](https://raw.githubusercontent.com/youneslaaroussi/ui-buttons/main/buttons/55-offset/preview.webp)

**3. `94-handdrawn-1` — the stamp / packet button.**
Wobbly border radius, uppercase, lift on hover. The closest thing to a rubber stamp.
[Folder](https://github.com/youneslaaroussi/ui-buttons/tree/main/buttons/94-handdrawn-1) ·
[CSS](https://github.com/youneslaaroussi/ui-buttons/blob/main/buttons/94-handdrawn-1/handdrawn-1.css)

![Handdrawn](https://raw.githubusercontent.com/youneslaaroussi/ui-buttons/main/buttons/94-handdrawn-1/preview.webp)

**4. `100-line-slide` — the ghost / text action.**
Underline slides in. Use for Close, Back, Copy citation, Reset layout.
[Folder](https://github.com/youneslaaroussi/ui-buttons/tree/main/buttons/100-line-slide) ·
[CSS](https://github.com/youneslaaroussi/ui-buttons/blob/main/buttons/100-line-slide/line-slide.css)

![Line slide](https://raw.githubusercontent.com/youneslaaroussi/ui-buttons/main/buttons/100-line-slide/preview.webp)

**5. `49-3d-button-click` — optional press mechanic.**
Take only the 2px bottom travel and shadow collapse; discard the 55° rotation and black/white.
[Folder](https://github.com/youneslaaroussi/ui-buttons/tree/main/buttons/49-3d-button-click) ·
[CSS](https://github.com/youneslaaroussi/ui-buttons/blob/main/buttons/49-3d-button-click/3d-button-click.css)

**6. `28-focus-in` — optional filter-chip hover.**
Border thickens inward; cheap and legible. Do not use it for primary.
[Folder](https://github.com/youneslaaroussi/ui-buttons/tree/main/buttons/28-focus-in) ·
[CSS](https://github.com/youneslaaroussi/ui-buttons/blob/main/buttons/28-focus-in/focus-in.css)

### 5.3 Exact class names worth stealing

- **PaperCSS** — `.paper-btn`, `.btn-large`, `.btn-small`, `.btn-block`, `.btn-primary`,
  `.btn-primary-outline`, `.btn-danger`, `.disabled`.
  [Button source](https://github.com/papercss/papercss/blob/master/src/components/_buttons.scss)
- **sButtons** — `.sbtn`, `.outline-btn`, `.shadow-3d-btn`, `.handwritten-btn`, `.rounded-btn`,
  `.disabled-btn`, `.block-btn`, `.red-btn`.
  [Dist CSS](https://github.com/sButtons/sbuttons/blob/master/dist/sbuttons.css)
- **bttn.css** — `.bttn`, `.bttn-bordered`, `.bttn-minimal`, `.bttn-material-flat`, `.bttn-pill`,
  `.bttn-danger`, `.bttn-block`, `.bttn-sm` / `.bttn-md` / `.bttn-lg`.
  [Standalone CSS files](https://github.com/ganapativs/bttn.css/tree/master/dist/standalone)
- **shadcn/ui** — use only its state/variant table as a checklist:
  default / secondary / ghost / destructive / outline / link; sm / default / lg / icon;
  focus-visible ring; disabled opacity; asChild.
  [button.tsx](https://github.com/shadcn-ui/ui/blob/main/apps/v4/registry/new-york-v4/ui/button.tsx)

### 5.4 Do not use

- **DaisyUI / Tailwind UI / shadcn as a dependency** — would require a stack rewrite. Reference
  only.
- **Uiverse as the primary system** — inconsistent quality, no shared tokens. One-off use only.
- **Any button with a gradient, glow, neon, or 999px primary shape** — fights the case-file
  direction.
- **sButtons as an npm dependency** — archived since 2022. Copy patterns, not the package.

---

## 6. Integration rules for this repo

- Put the system in one place: a new `app/ui.css` linked **after** `tokens.css`/`base.css` and
  **before** `style.css`, or at the top of `style.css`. Do not scatter button CSS per screen.
- Use `:where()` or scope under `.btn` so PaperCSS’s global `button` rules never leak.
- Re-color every ported button with the existing variables: `--red`, `--red-dark`, `--amber`,
  `--ink`, `--panel`, `--panel2`, `--line`, `--line-strong`. No new hex codes except the paper
  `#f4f1e8` already used by the brief.
- Replace, do not layer: remove old `#workBtn`, `.chip`, `.tab`, `.modal-close`, `button` styling
  once `.btn` covers them. Two systems is how the current mess happened.
- Preserve keyboard behavior: every button is a real `<button>` (or `<a>` for navigation), with
  `type="button"` outside forms, `aria-label` on icons, `:focus-visible` never removed.
- No new external fonts. Georgia + Courier already carry the look.
- Test the run path after any button change: `Work the Case` → replay → tabs → quote modal →
  person drawer → print. The runner must be untouched.

---

## 7. Copy-paste prompt for Codex

```
You are working in ~/Desktop/murder-board, a static zero-build murder-board app.
Read REVIEW.md and CODEX_BRIEF.md first. Do not add React, Tailwind, npm packages, or a build step.

Order:
1. Add the unified .btn system from CODEX_BRIEF.md §4.3–4.5 in app/style.css (or app/ui.css).
   Port the surface treatment from PaperCSS, the size/variant structure from bttn.css, and the
   three specific shapes from youneslaaroussi/ui-buttons (§5.2). Rename all ported classes.
2. Replace every existing button, tab, chip, modal close, and form submit with the new system.
   Do not touch the corkboard/pin/yarn styles except focus rings.
3. Implement P0-1 dropped-findings ledger + quote receipts, then P0-2 judge mode, then P0-3
   entity links/deep links/highlighting, then P0-4 reconciliation table, then P0-5 board filters
   + isolate, then P0-6 headline copy, then P0-7 replay/live badge.
4. After each P0, verify with the saved replay: the drop count matches, no runner law is weakened,
   and the case still switches cleanly.
5. Report exactly what you ran. Do not claim a browser check you did not perform.

Hold the line: no quote, no finding; the runner owns the arithmetic; the board judges the file,
never a person.
```

---

## 8. Definition of done

- [ ] One button system; no default browser controls visible on any screen.
- [ ] `Work the Case`, `Send`, `Download packet` are unmistakably primary at 46/38px.
- [ ] Every button has hover, active, focus-visible, disabled, and busy states.
- [ ] Tabs read as folder tabs, not buttons.
- [ ] Dropped findings are listed with claim, quote, doc, reason; accepted quotes show a receipt.
- [ ] Judge mode runs the 7 beats with arrow keys.
- [ ] Person and doc ids are links everywhere; deep links restore state; quotes highlight.
- [ ] Reconciliation table shows 2 vs 1 for the casing.
- [ ] Board filters dim without reflow; person isolate works; reset works.
- [ ] “WHO DID IT” is gone; the Duck stamp cannot be read as a system claim.
- [ ] Replay/live badge is visible on every screen.
- [ ] Runner laws unchanged; replay still matches the cached drop count.
- [ ] No new dependency, no new build step, no committed key.

---

**One-line direction:** the app should read as a case file with stamped actions — not a dark SaaS
dashboard with six tabs.
