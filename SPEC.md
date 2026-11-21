# MURDER BOARD — spec for Gemini 4 NYC (Sat Nov 21, 2026)

Working title. Name is Del's call at the venue.

## The pitch in one line

An AI investigator of death. That is our alley.

It sorts the homicide file and judges it: what connects, what
contradicts, what is missing, and which lead is worth tomorrow
morning. The detective stays the detective.

## Who it is for

Homicide detectives working cold or stalled cases. A real case file is
hundreds of pages nobody has time to re-read. This reads all of it, every
time, and keeps the board current as new material lands.

## What it SORTS

1. Every document becomes structured case data: people, places, vehicles,
   phone numbers, times, objects, each with the exact quote it came from.
2. People get cards. Every mention of a person, in every document, lands on
   their card.
3. Events get a timeline. Every dated or timed claim goes on one clock, so
   the night of the murder reads as a single sequence.
4. Evidence gets a ledger. Every item logged, photographed, or mentioned,
   tracked in one list.

## What it JUDGES

Judged means scored against the file itself, never a verdict on a person.

1. **Statement consistency.** Each witness statement scored against the
   records and against every other statement. Contradictions flagged with
   both quotes side by side.
2. **Alibi strength.** Each alibi checked against the timeline and the
   records. Rated: corroborated, uncorroborated, or contradicted, with the
   reason shown.
3. **Lead ranking.** Every open lead scored by how much of the file touches
   it, so the detective sees what to work first.
4. **Gap list.** What the file should have and does not: the camera nobody
   pulled, the witness never re-interviewed, the evidence item mentioned
   in a report but absent from the ledger.

## The agents (Managed Agents prize angle)

Four Gemini agents, visible working on screen, each with one job:

1. **Intake** reads each document and extracts the structured data.
2. **Timeline** builds and repairs the single clock.
3. **Cross-Examiner** hunts contradictions between statements, records,
   and the timeline. This is the star of the demo.
4. **Sergeant** ranks leads, writes the gap list, and drafts the one page
   case brief.

The detective watches the four work the case in sequence. Their status and
findings stream into the board live.

## Screens

1. **Intake.** Drag the case file in. Document list with type and page
   count. One button: Work the case.
2. **The Board.** The evidence wall. Person cards, evidence cards, red
   threads for contradictions, plain threads for connections. Clicking a
   thread shows the two quotes that created it.
3. **The Clock.** The timeline strip for the night in question. Every
   event placed, conflicts shown as collisions on the same hour.
4. **Judgments.** Three lists: contradictions ranked by severity, alibis
   with their ratings, leads ranked with scores.
5. **The Brief.** One page, detective language, generated from the board:
   case summary, strongest contradiction, top three leads, gap list.
   Printable.

## The demo (3 minutes, fictional case, see CASE_BIBLE.md)

1. (0:00) "This is the file on a 2019 homicide. Fourteen documents. It has
   been cold for six years." Drop the file in.
2. (0:20) The four agents work. The board builds itself, cards and threads
   appearing as the agents post findings.
3. (1:15) Click the red thread. The Cross-Examiner's catch: a witness puts
   the suspect's car at the scene at 9 PM; the suspect's own statement
   says the car was in the shop that week; the tow record in the file
   shows the car was picked up two days BEFORE the murder. Nobody in six
   years put those three pages next to each other.
4. (2:00) Judgments screen. Alibi rated CONTRADICTED, with the reason.
   Lead ranking puts the tow yard first.
5. (2:30) The Brief. One page. "It does not solve the case. It sorts six
   years of work and judges what is strong, what is broken, and what was
   never done. The detective still does the detecting."

## Honesty lines (say them in the demo, they build trust)

- Demoed on a fictional case written for this event. No real case data.
- It judges consistency and completeness of the file. It never names a
  guilty party.
- Real deployment needs chain of custody and local processing. That is
  the roadmap slide, one line, not a claim about tomorrow.

## Build plan (event day, 9 AM to 10 PM)

- 09:00–10:00 Setup. Gemini access sorted, project scaffold, the fictional
  case documents generated from CASE_BIBLE.md (generated at the event, so
  the whole build is fresh).
- 10:00–12:00 Intake agent + document parsing + data model. Documents in,
  structured JSON out.
- 12:00–14:00 The Board screen. Cards, threads, quote viewer.
- 14:00–16:00 Timeline agent + Cross-Examiner. The contradiction engine
  is the demo; it gets the hours.
- 16:00–17:30 Sergeant: lead ranking, gap list, brief generation.
- 17:30–19:00 Judgments screen + Brief screen + polish.
- 19:00–20:30 Demo rehearsal against the fictional case, twice, timed.
- 20:30–22:00 Buffer, submission, demo.

Cut order if time runs short: Brief screen first (print the brief from the
Judgments screen instead), then the Clock as its own screen (fold events
into the Board). The Board, the Cross-Examiner, and the Judgments lists
are never cut. They are the product.

## Risks

- Gemini Managed Agents access at the venue may differ from the docs.
  Fallback: the same four roles as plain sequential Gemini calls behind
  one runner. The screen does not change; only the plumbing does.
- Contradiction detection can over-flag. Mitigation: every flag must cite
  two quotes; a flag without quotes is dropped by the Sergeant.
- Document parsing of messy scans. Mitigation: the demo case is typed
  documents, and intake accepts pasted text as well as files.

## Prior art (checked 2026-11-20, the night before)

The category exists and is forming now. Do not pitch this as a world
first.

- **Conectir** — AI investigation and case management for law
  enforcement. Its wedge feature is cross-statement contradiction
  detection on one timeline, with innocent alternatives offered for
  every flag and the same "never decides who is lying" line. Closest
  match to the Cross-Examiner.
- **Truleo** — established US police AI company. Case summarization
  and analysis for detectives: consolidates case materials, surfaces
  inconsistencies and gaps, builds timelines, prioritizes leads by
  corroboration. Already used on a real cold case (Papakee), which
  produced a 27 page report.
- **IBM i2 Analyst's Notebook, PenLink, Palantir Gotham** — the link
  board itself is decades old, but analyst-built by hand, no AI
  judging of statements.

What none of them leads with, and this build does: homicide-first,
the full judging package in one board — alibi ratings, lead scores,
and the evidence ledger cross-checked against the reports (the
missing casing catch). The pitch is the package and the speed,
not the invention of the category.
