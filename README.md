# Murder Board

An AI investigator of death. Built at Gemini 4 NYC, November 21, 2026.

It sorts a homicide case file and judges it: what connects, what
contradicts, what is missing, and which lead is worth tomorrow
morning. It judges the file, never a person. The detective stays
the detective.

A squad of ten Gemini agents, each holding a real homicide squad
job (First Officer, Coroner, CSI, Analyst, Cross-Examiner, Digital,
Interviewer, Prosecutor, Lead Detective, Records), builds the
murder book from the raw file: person cards, one timeline, an
evidence ledger, then the judgments — contradiction flags with both
quotes, alibi ratings, scored leads, and the gap list.

The spine of the system: **no quote, no finding.** Every judgment
carries the exact quote it came from, and the runner verifies each
quote against its source document in code. A finding whose quote
is not in the file is dropped before it can reach the board.

## Problem statement and model jobs

**Problem Statement One, 5 Sigma.** A real task agents struggle
with (judging a case file without inventing evidence), a system
that does it reliably, and proof: `EVAL.md` scores the squad
against a single-model-call baseline on all four cases, with
the failure analysis left in.

All four Gemini 4 models, four clear jobs. **Argon judges**
(reasoning): the Cross-Examiner and the Lead Detective, the two
steps that weigh the file. **Carbon builds** (visual coding):
the First Officer, Records, the Coroner, CSI, Intake, the
Interviewer, and the Prosecutor, the extraction and sorting
that builds the murder book. **Hydrogen holds the world**
(world models): the Analyst, one clock and one map of the
case, every event placed in time and space, every collision
surfaced. **Neon works the machines** (robotics): Digital,
the field devices that watched the scene, cameras, keypads,
plate readers, phones, and exactly what each record proves.
If Hydrogen or Neon ever returns no usable output, Carbon
covers the step and the substitution is written into the run
log, never hidden. The chair strip in the app names the model
holding each chair. The judging criteria also name a Decisions API;
no decision model appears in the model list on this event's
key (checked 2026-11-21), so the decision function here, which
lead outranks which and by how much, is the rubric recompute in
the runner: deterministic, inspectable, shown with its
arithmetic. `EVAL.md` states this in full.

## The demo case

The demo runs on a fictional 2019 cold case written for this event
(`case/`, 14 documents). No real case data. The file contains three
planted catches: a suspect's car placed in two locations by his own
statement, a tow record, and a neighbor; a bookkeeper whose third
statement adds a visit her first two deny; and a shell casing a
scene report counts and the evidence ledger does not.
`EXPECTED_FINDINGS.md` is the acceptance test a live run must pass.

## Layout

- `SPEC.md` to `SPEC5.md` — concept, data model and rubrics, the
  two front doors, the cast and the murder book, the build spec.
- `AGENTS.md` — the ten agents: mandate, inputs, outputs, prompt,
  and the lines each never crosses.
- `PROMPTS.md` — the four core agent prompts and JSON schemas.
- `CASE_BIBLE.md` — the fictional case, its people, its catches.
- `DEMO_SCRIPT.md` — the three minute demo, word for word.
- `case/` — the 14 demo documents and their registry.
- `EXPECTED_FINDINGS.md` — the golden output.
- `case2/`, `CASE2_BIBLE.md` — the Screens File, the internet case.
- `case3/`, `CASE3_BIBLE.md` — the Harborlight File, the sim: a
  cold case built to be investigated, solved by a chain of four
  records, with the loud suspect provably out of the window.
- `case4/`, `CASE4_BIBLE.md` — the Duck File: a real, solved
  case (Chicago, 2020) rebuilt from the public record and run
  blind, scored against what actually solved it.
- `EVAL.md` — the squad against a single model call, scored
  against the bibles, failures included.
- `records/` — the Door 2 census fixtures (fictional), with the
  Records prototype described in `PAX_DECISION.md`.
- `RESEARCH_DETECTIVES_2.md` — detective method research, pass 2.
- `CODEX_HANDOFF.md` — the full brief for a fresh agent.

## Status

Built at the event, 2026-11-21. The app lives in `app/` (static,
no build step): open it through any static server, copy
`config.example.js` to `config.js`, add the Gemini API key, and
press Work the Case. Model map: `gemini-4-argon` judges for the
Cross-Examiner and the Lead Detective; `gemini-4-carbon` builds
the book; `gemini-4-hydrogen` holds the world for the Analyst;
`gemini-4-neon` works the machines for Digital. Full live runs
of all four cases are saved as
the replay cache (`app/cache-data.js`), so the demo survives a
network failure, and the site now works the selected case from
its cache on its own when the page opens. The Board screen is a
corkboard: pinned cards, sticky notes for the gaps, and yarn for
the threads, red where the file contradicts itself.

The app carries four cases. The Delgado file is a police file.
The Screens File (`CASE2_BIBLE.md`, `case2/`) is the internet
case: a fictional Brooklyn drill killing whose whole file is
public posts, a plate cam still, a podcast transcript, and the
Reddit thread where strangers collated the night. Same squad,
same checks. Its first live run caught both planted
contradictions at HIGH, rated the poster CONTRADICTED, and
carried the innocent reading on the partial plate. The Duck
File (`CASE4_BIBLE.md`, `case4/`) is the real one: the 2020
Chicago killing of Carlton "FBG Duck" Weekly, rebuilt from
court filings and reporting, run blind and scored in
`EVAL.md` against what actually solved it.

First live run, scored against `EXPECTED_FINDINGS.md`: the Webb car
contradiction at HIGH with the tow record quote, the Whitfield
Sunday visit flagged, the missing second casing at the top of the
gap list, Webb's alibi rated CONTRADICTED, Whitfield's
UNCORROBORATED, top lead 80. Validation dropped 4 findings whose
quotes were not in the file. SPEC6.md holds the working doctrine:
asking is contact, checking is desk work; the squad works paper and
public internet records, and hands the human detective the exact
question when a lead needs a person.
