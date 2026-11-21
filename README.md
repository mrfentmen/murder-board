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

## Status

Build day. App code lands here as it is written at the event.
