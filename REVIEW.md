# REVIEW — Murder Board, read-only pass

**Date:** 2026-11-21
**Scope:** `app/app.js` (1,436 lines), `app/index.html`, `app/style.css`, `app/case-data.js` shape,
`agents/*`, `SPEC6.md`, `EVAL.md`, `CODEX_HANDOFF.md`, `README.md`, `SUBMISSION.md`,
`DEMO_SCRIPT.md`, `murder-board-competitor-check.md`.
**Not done:** I did not run the app in a browser or on the live URL. Visual notes below come from
the DOM/CSS structure and the render paths, not from a screenshot. No code was changed.

---

## Verdict

The product is stronger than its interface. The spine — no quote, no finding; runner-owned
arithmetic; ten real squad chairs; four cases with answer keys — is genuinely differentiated, and
`EVAL.md` is more honest than most hackathon submissions. The UI currently presents that spine as
**six tabs and a wall of cards**. A judge has to be told the story; the interface does not lead them
through it.

The three biggest wins are not new features. They are:

1. **Make the quote check visible per finding**, not just a drop count in the header.
2. **Make the board a board** — zoom, isolate, filter — instead of a flex-wrapped card gallery.
3. **Build a presentation pass** so the 3-minute demo is one keypress per beat, in large type.

Everything else is below, ordered by demo impact.

---

## What already works — do not break it

- The **corkboard** is the best-looking screen and the only one that looks like the product's name.
  Cork texture, pins, tilted cards, yarn, and the string key all read instantly.
- **Quote pair modal** with side-by-side sources and the innocent reading is the trust moment.
- **Person drawer** (`openProfile`) is a complete sourced mini-file: aliases, claims, events,
  medical findings, alibi, statement history, contradictions, related documents. This is the
  strongest screen in the app and it is buried behind card clicks.
- **Print brief** exists and is clean (`@media print`), despite `CODEX_HANDOFF` still listing it
  as future work.
- **Replay cache** auto-loads per case and survives a dead network. Correct call for a demo.
- **Run log + red chair** for failed steps. The run never dies. Good.
- **Case folder header** with case number, victim, window, place, and stamp. Cheap, effective
  period detail.

---

## P0 — do these before any new surface area

### 1. Show the dropped findings, not just the number

Today `book.dropped` is a counter and `book.log` gets one line per step: `"csi: 2 finding(s)
dropped by the quote check"`. The individual rejected finding — the claim, the fake quote, the
document it claimed to come from — is thrown away.

That is the product's single best proof point and it is currently un-inspectable. The demo script
says "say the 4 dropped findings out loud"; a judge will ask "which 4?" and the app cannot answer.

**Add:** a `Dropped findings` section on Judgments (and a link from the header chip) listing each
rejection with:

- the step / chair that produced it,
- the claim text,
- the quote it cited,
- the document id,
- the closest matching substring in that document, or "no match",
- a one-line reason (`quote not in cited document`, `unknown doc id`, `quote shorter than 8 chars`).

Also store a **verification receipt** on every accepted finding: doc id, character offset of the
match, and the normalized length. Render a small green "verified · doc03 · offset 1,204" line in
the quote modal and on the contradiction card. This turns "trust us" into "check it yourself".

Why first: it is the one thing Conectir/Truleo do not advertise, it is already computed, and it is
the answer to the hardest judge question.

### 2. A presentation pass ("Judge mode")

The demo is 3 minutes and the UI is a desktop workspace. The feed is 300px tall, body text is
12–14px, and the tabs are always visible. On a projector this will not read.

**Add:** a full-screen mode (key `P`, plus a header button) that:

- hides the header controls, model line, tabs, and footer,
- enlarges the active screen to viewport width and bumps body type,
- steps through a fixed sequence with `←` / `→`: **Folder → Squad room (first 20s of feed) →
  Board → the star contradiction → Judgments → Brief → Eval**,
- keeps a thin "1/7" progress marker and an Exit control,
- pauses the replay feed between beats rather than dumping 40 lines at once.

This is a presentation layer only; no runner changes. It is the highest ratio of judge impact to
engineering effort in this list.

### 3. Make every entity clickable, and make state linkable

Right now a person is clickable only on the board and the thread list. In the alibi table,
contradictions, leads, gaps, and questions, names are plain text. A judge reading "Webb
CONTRADICTED" cannot click Webb.

**Add:**

- Person names in alibis, contradictions, leads, questions, and the brief open the person drawer.
- Document ids everywhere open the document drawer.
- In the full document view, **highlight the quoted span** and scroll to it. Today the drawer
  shows the whole document with no marker, so the judge has to hunt for the quote.
- URL state: `#/duck-2020/judgments`, `#/delgado-2019/person/marcus-webb`,
  `#/screens-2025/contradiction/2`. Reload restores the screen; links can be pasted into the
  submission form, Discord, or a judge's notes.
- A "copy citation" action on every quote: `doc04 · Webb statement 2020 · "…"`.

Deep links are also the cheapest way to make the app feel like a real product rather than a demo.

### 4. A reconciliation panel for the evidence ledger

The missing second casing is the demo's second catch, but the app renders it as one more card in a
generic gap list. The actual reconciliation — scene report says two, ledger lists one — is never
shown as a table.

**Add:** a **Ledger reconciliation** block on Judgments (or under CSI on the board):

| Item | Mentioned in scene report | Logged in evidence ledger | Delta |
|---|---|---|---|
| Shell casing, by desk | 2 | 1 | **−1 missing** |
| … | | | |

One row per item, `mentioned / logged / delta`, with the source quotes on click. This makes the
catch legible in five seconds and gives the second catch the same visual weight as the first.

### 5. The board should behave like a board

`renderBoard` lays every person, document, evidence item, gap, and legend into a single
`flex-wrap` row. `drawYarn` computes curves from DOM offsets. There is no pan, zoom, drag, filter,
or isolation. Adding a case with 40 documents will produce a long ribbon of paper, not a board.

**Add, in order:**

- **Filter chips** above the board: All / Contradictions / Gaps / People / Documents / Evidence,
  plus a person filter. Dim non-matching pins and their yarn instead of removing them (keeps
  spatial memory).
- **Click to isolate:** clicking a person's pin fades everything not connected to that person by a
  documented link or contradiction; click empty cork to restore.
- **Zoom + pan** on the corkboard (CSS transform on the pin layer + SVG, wheel/pinch, fit button).
  Keep pins counter-scaled so text stays legible.
- **Drag pins** and persist positions per case in `localStorage`; a "reset layout" button.
- **Mobile fallback:** below 640px, replace the corkboard with a grouped list of the same pins
  (people, documents, gaps) because a wrapped absolute-SVG board is not usable on a phone. The
  threads list already works; make it the primary mobile view.

Do not randomize positions. Deterministic layout is fine; the value is filtering and isolation,
not freeform arrangement.

### 6. Fix the board's headline

The largest text on the corkboard is **"WHO DID IT"**. The product's entire ethical position is
that it does *not* answer that — it judges the file, never a person. A judge who reads the board
for two seconds sees an accusation wall, then hears the opposite in the pitch.

**Change the headline** to the question the system actually answers: **"WHAT DOES THE FILE
CONTRADICT?"** or **"WHAT THE FILE SAYS"**, with the victim and death window as the subline. Keep
the giant question mark if you want the visual; change the words. This is a five-minute copy fix
with outsized effect on how the product is perceived.

While there: the Duck folder stamp says **"SOLVED 2024"**. Add "in reality — not by this board"
next to it, or the stamp reads as a claim the system solved a real case.

---

## P1 — high value, still contained

### 7. "Tomorrow morning" — assignments by chair

`AGENTS.md` promises the Lead Detective writes "tomorrow's assignments per agent", but the UI only
shows a flat ranked lead list. The squad metaphor is the product's charm; use it.

**Add:** an **Assignments** panel on Judgments or Brief, grouped by chair:

- **Records** — pull the dealership paper for the Fusion.
- **Digital** — pull the POD camera and plate reader for both cars.
- **Interviewer** — ask Herrera about the 00:07 keypad entry.
- **CSI** — locate the second casing or the ledger entry that accounts for it.

Each row: action, why (quote), expected outcome ("confirms / eliminates"), and a checkbox. Add
"Copy tomorrow's list" and include it in the brief export. This is deterministic rendering from
`leads` + `gaps`; no new model call.

### 8. The clock as an alibi chart, not a list

`renderClock` is a vertical list of events with a death-window banner. The real murder-board
artefact is the **"where was everyone"** chart.

**Add:** under the event timeline, one horizontal row per person with:

- a bar for the death window (shaded red),
- a marker for each claimed location/time,
- a marker for each record-verified location/time,
- a hairline connecting claim → record where they disagree, labelled with the rating.

This is the visual that makes "Webb CONTRADICTED" obvious without reading a paragraph. It also
uses data already in `alibis`, `timeline`, and `machine_events`.

### 9. Search / command palette

There is no way to find a name, document, or quote except scrolling. `/` is free.

**Add:** `Ctrl/⌘+K` palette over persons, documents, contradictions, gaps, and quotes; `Enter`
opens the entity, `→` opens the source at the highlighted span. Group results by type with counts.
This also doubles as the demo's "look, it is a real tool" moment.

### 10. A run receipt, and a retry per chair

The chair strip shows state during the run, but afterwards there is no record of what happened:
duration, model per chair, retries, failures, drops, cache vs live. `book.failed_steps` exists but
is only printed into the status line.

**Add:** a collapsible **Run receipt** in the header or above the feed:

```
Run 2026-11-21 11:35 · REPLAY · 10s
11/11 steps · 4 findings dropped · 0 failed · 2 model fallbacks
Argon: Cross-Examiner, Lead Detective
Carbon: First Officer, Records, Coroner, CSI, Intake, Interviewer, Prosecutor
Hydrogen: Analyst · Neon: Digital
```

Plus a **Retry** button on a red chair that re-runs only that step from its cached inputs, and a
"Use saved run" action when a live run fails mid-demo. Stage safety.

### 11. Make replay/live impossible to misread

The only replay indicators are `cacheLabel` ("Ran today, 11:35 (saved run)") and a feed line that
scrolls away. Judges will assume it is live.

**Add:** a persistent badge in the header — **REPLAY · saved 11:35** (amber) or **LIVE · key in
this tab** (red) — and put the same badge on the Brief and Eval screens. On the public deployment,
default to replay and require an explicit "Live run" confirmation before showing the key field.

### 12. Remove the API-key field from the public demo header

`#liveKey` sits in the header of a public page and the browser calls
`generativelanguage.googleapis.com` directly with the user's key. For a hackathon demo it is
convenient; for anyone else it looks like phishing, and it puts a key in a page controlled by the
deployment.

**Recommend:** hide live mode behind a "Live run (advanced)" disclosure on replay builds, and for
the real product put a small proxy in front of the provider so the browser never handles a key.
At minimum, add one line under the field: "stays in this tab; sent only to Google" (the `title`
already says it, but titles are invisible on a projector).

### 13. Let the room answer questions from the book

`sendChat` is a regex router: work, case name, screen name. A judge typing "who has the weakest
alibi?" gets the fallback menu. This is the one place where the "talk to the squad" promise is
visible and unmet.

**Add a deterministic intent set** over the built book (no model call):

- "top gap" → first CSI/CE gap with its quote.
- "strongest alibi" / "weakest alibi" → alibi table sorted, with the reason quote.
- "who contradicts" → contradiction list grouped by person.
- "show <name>" → person drawer.
- "why is <name> contradicted" → the exact contradiction + innocent reading.
- "what is missing" → gap list summary.

If no intent matches, say what it can answer. Never invent a free-text answer; the product's
credibility depends on every sentence being traceable.

### 14. Export the packet, not just the brief

Print works for the brief only. A detective leaves with the whole book.

**Add:** "Download murder book" producing a single `.md` (and print-to-PDF layout) with:

1. case folder fields,
2. brief,
3. contradiction table with both quotes and innocent readings,
4. alibi table with windows,
5. ledger reconciliation,
6. gap list with assigned chair,
7. lead table with arithmetic,
8. quote-check receipt (accepted / dropped).

Also add "Copy brief as Markdown" and a permalink to the current run. This is the artefact judges
can take away and the one a real user would forward.

---

## P2 — worth doing, not before the demo

### 15. Case builder (the real product unlock)

`CODEX_HANDOFF` already lists it: paste documents/posts → generate a case folder + registry. Even a
minimal local version ("drop 5 .txt files, name the case, run it") moves the demo from "four
canned cases" to "bring your own file". Bigger than everything above; do not start it before the
demo unless the other items are done.

### 16. Run diff / baseline comparison in-product

`EVAL.md` has the baseline numbers. The Eval tab does not let you inspect a baseline output beside
a squad run. Add a two-column diff for one case: baseline JSON vs squad book, highlighting
over-called severities, uncited leads, and the drop count. This is the proof, made navigable.

### 17. Accessibility and type pass

- The board is a set of `div[role=button]` with Enter/Space only. Add arrow-key navigation between
  pins and a visible focus order that follows the threads, not the DOM.
- Severity is conveyed by color (`sev-high` red, `sev-medium` amber) and by text; keep the text,
  but add a glyph or label chip for color-blind readers.
- `--muted` on `--panel2` is around 4:1; body copy at 12–13px is below comfortable projector
  reading. Raise the floor to 14px on the Judgments/Clock/Eval screens and increase muted contrast
  one step.
- `aria-live` is on the feed activity but not on the run status or drop chip. Add `role=status`.
- Remove the duplicate/invalid `--muted: #9a97 8f;` declaration in `style.css:8`. It is harmless
  (overridden on the next line) but it is the first thing a CSS reviewer sees.

### 18. Portrait fallback can attach the wrong face

`photoHtml` falls back to a **surname match** when the full name misses. Two people with the same
surname will get the same face, and a person with no fixture can inherit a stranger's portrait.
The caption says "illustrative, not evidence", but a wrong face on a murder board is the kind of
detail a judge remembers.

**Recommend:** remove the surname fallback; use initials when there is no exact fixture match. Keep
the illustrative caption. Same issue in `personProfileData`, which matches names by first/last
tokens; for a demo it is fine, but note it as a known collision risk next to the Records
"never merge" claim.

### 19. Mobile

The media queries exist and the header/tabs wrap, but the board is still 200px cards plus an SVG
overlay, and the quote modal stacks to one column. Replace the board with a grouped list (people /
documents / gaps / threads) under 640px, keep the thread list and person drawer, and collapse the
squad strip into a horizontal scroll. The brief and judgments already read fine on a phone.

### 20. Copy and doc drift

- `README.md` says "both cases have saved runs" in one place and describes four cases elsewhere.
- `CODEX_HANDOFF.md` lists the print stylesheet as future work; it exists.
- `EVAL.md` says "two Gemini 4 models" in the Method section, then evaluates four.
- The header says "Built today at Gemini 4 NYC" — true only today. Use a fixed date.
- `SUBMISSION.md` and `DEMO_SCRIPT.md` still contain the "Nobody packages…" line the competitor
  check already flagged. Fix the script before the next run; it is the answer most likely to be
  challenged.
- The `dropChip` only appears after a drop; a judge who arrives late never sees it. Put the quote
  check result in the run receipt and the brief, not only in a transient chip.

---

## Do not add

- **No guilt score, no suspect ranking, no "most likely killer" bar.** It would contradict the
  product's stated ethics and give a judge an easy reason to distrust it.
- **No free-text chatbot.** The deterministic command set is stronger and safer. A model that
  answers off-book breaks the one law the whole demo rests on.
- **No 3D board, no animated yarn, no page transitions.** The corkboard already lands; motion
  would slow the replay and cheapen it.
- **No accounts, database, or backend for the demo.** Static + cache is a feature.
- **No new real case data.** The Duck file's honesty caveat is already well handled.
- **Do not weaken the quote check to make a result look better.** If a finding drops, show it.

---

## Suggested order for Codex

| Order | Item | Effort | Demo impact |
|---|---|---|---|
| 1 | Board headline copy fix + Duck stamp clarification | XS | High |
| 2 | Dropped-findings ledger + quote receipts | M | Very high |
| 3 | Judge mode (presentation pass) | M | Very high |
| 4 | Deep links + entity links + quote highlight in document | M | High |
| 5 | Ledger reconciliation table | S | High |
| 6 | Persistent REPLAY/LIVE badge + hide key field on demo | S | Medium |
| 7 | Board filters + click-to-isolate (zoom/drag later) | M | High |
| 8 | Run receipt + per-chair retry | S | Medium |
| 9 | Alibi chart on the Clock | M | High |
| 10 | Assignments-by-chair + brief packet export | M | High |
| 11 | Deterministic Q&A intents | S | Medium |
| 12 | Search / command palette | M | Medium |
| 13 | Accessibility + mobile list fallback | M | Low–medium |
| 14 | Case builder | L | Product-level |

If only three things ship: **dropped-findings ledger, judge mode, and the board headline/entity
links.** Those three make the existing product legible without adding a single new claim.

---

## One-sentence positioning for the UI

The app currently says "here are six screens of results." It should say, in the first ten seconds:
**"This is the file. This is the squad. This is the one contradiction nobody put next to each
other. Here is the quote. Here is what we could not prove."**
