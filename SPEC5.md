# SPEC 5 — build spec: stack, runner, validation, screens, fallback

Written 2026-11-21, morning of the event, on top of SPEC.md through
SPEC4.md. The case documents now exist as files in `case/` (registry:
`case/registry.json`); the acceptance test is EXPECTED_FINDINGS.md.

## Stack

- One static page app. No build step, no framework. Plain HTML, CSS,
  and JavaScript in three files: `index.html`, `app.js`, `style.css`.
  It must run from a local static server or a plain file host, and
  survive a venue wifi drop once loaded.
- Gemini calls from the browser via fetch. The API key lives in a
  `config.js` that is loaded before `app.js` and never committed.
  Demo grade only; the roadmap line about local processing covers
  the real deployment story.
- Model assignment, per SPEC2's judging map: the reasoning variant
  (Argon) runs Cross-Examiner and Lead Detective; the fast variant
  runs everything else. Model names are config values, set at the
  venue when access is confirmed, never hardcoded in logic.
- Managed Agents if the venue access supports it; otherwise the
  same ten roles as sequential calls behind the one runner (SPEC.md
  risk plan). The screens do not know the difference.

## The runner

One runner, ten prompt files. Agent prompts are configuration:

- `agents/01_first_officer.md` through `agents/10_lead_detective.md`,
  built from AGENTS.md: house rules block (PROMPTS.md) + the agent's
  system prompt + its output schema.
- Run order is the SPEC4 hand-off order: First Officer → Records
  (Door 2, runs in parallel, idle on a Door 1 demo) → Coroner → CSI
  → Intake extraction (the PROMPTS.md Intake job, run as its own
  step feeding the Analyst) → Analyst → Digital → Cross-Examiner →
  Interviewer → Prosecutor → Lead Detective.
- Each step: assemble prompt (house rules + agent prompt + the
  inputs as JSON + the documents it may read), call, parse JSON,
  validate (below), store. A step that fails validation retries
  once with the validation errors appended; a second failure shows
  the chair red on the squad strip and the run continues without
  that agent's findings. The demo never dies on one agent.

## Validation — the quote check is code, not a promise

This is the technical claim of the whole build, so it is enforced
by the runner, not requested from the model:

1. **Schema check.** Output parses as JSON and matches the agent's
   schema shape. Anything else is rejected.
2. **Quote check.** Every finding carries `doc_id` and `quote`. The
   runner normalizes whitespace and case in both the quote and the
   source document and requires the quote to appear verbatim in
   that document. A finding whose quote is not in its document is
   DROPPED, counted, and the drop count is shown on the Judgments
   screen ("3 findings dropped: no quote in the file"). No uncited
   finding can reach the board. This is the demo's best sentence
   after the catch itself.
3. **Rubric check.** Lead scores are recomputed by the runner from
   the rubric in SPEC2 (40/25/20/15) against the contradiction and
   gap ids the Lead Detective cites. If the model's arithmetic and
   the runner's disagree, the runner's number is shown and the
   disagreement is logged. Scores are a sort order, not a
   probability; the Brief screen says so under the table.

## Data flow

- Load: `case/registry.json` + the 14 document texts. The Intake
  screen lists them from the registry; the demo case is bundled,
  and the drop zone accepts additional text files into the same
  registry shape.
- State: one `book` object in memory (documents, persons, claims,
  events, evidence, contradictions, alibis, leads, gaps, brief),
  exactly the SPEC2 data model. Every object keeps `source_doc` and
  `quote`. The screens render only from `book`; nothing renders
  from a raw model reply.
- Custody: the First Officer's registry output is the document list
  every later step cites. A `doc_id` that is not in the registry
  fails validation like a bad quote.

## Screens (SPEC.md's five, plus the strip)

- **Squad room strip** across the top of every screen after Intake:
  ten named chairs (SPEC4). A chair lights while its agent runs,
  shows a count of posted findings, and turns red on a failed step.
- **1 Intake.** Registry table (title, type, date, author), the
  Work the Case button, Door 2 teaser panel (name and photo in,
  starter file out) shown but not demoed unless asked.
- **2 The Board.** Person cards and evidence cards; plain threads
  for connections, red threads for contradictions. Clicking any
  thread opens the quote panel: the two quotes, side by side, with
  document titles and dates. The C1 thread is the demo's click.
- **3 The Clock.** One horizontal strip for Oct 11 to Oct 14 with
  the death window shaded; events from EXPECTED_FINDINGS' anchor
  list; collisions shown stacked on the same hour with a red tick.
- **4 Judgments.** Contradictions by severity (each expandable to
  its quotes and innocent alternative), the alibi table, evidence
  gaps, leads with score arithmetic shown, and the dropped findings
  count from validation.
- **5 The Brief.** The Lead Detective's one page, printable:
  five line summary, strongest contradiction with both quotes,
  alibi table, top three leads, gap list, and the standing closing
  line. The Prosecutor's vetoes appear as struck sentences in the
  draft view if he cut any; the print view shows the clean page.

## The fallback cache (the insurance)

- After the first full live run of the morning, the runner saves
  every agent's raw output to `cache/delgado-2019.json`.
- A visible toggle, "Replay cached run," reruns the same screen
  choreography from the cache with no network calls. If venue wifi
  or the API dies before the demo, the demo does not.
- The cache is labeled on screen when active ("cached run from
  10:42 AM"). Honesty line from SPEC.md applies: the case was run
  live this morning; the replay is the same outputs.

## Rehearsal checklist (from EXPECTED_FINDINGS.md)

A rehearsal passes when the live run produces: C1 at HIGH with the
tow record quote, C2 at MEDIUM, the G1 casing gap at the top of the
gap list, Webb CONTRADICTED, Whitfield UNCORROBORATED, and the lead
order 80 / 55 / 35. Two timed rehearsals per SPEC.md's build plan,
the second one on the cached replay to prove the fallback works.

## Cut order (unchanged from SPEC.md and SPEC4.md)

Brief screen first (print from Judgments), then the Clock as its
own screen (fold into the Board), then Digital and Interviewer fold
into Analyst and Cross-Examiner. Never cut: the Board, the
Cross-Examiner, the Judgments lists, the quote check.
