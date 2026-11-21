
# EXPANSION — data model, contracts, rubrics, names, judging map

## Name shortlist (Del picks at the venue)

Note: "alley" is Del's word for the lane, the niche we work. It is
not a name candidate.

1. **Murder Board** — working title. Descriptive, instantly
   understood, less ownable.
2. **Cold Desk** — the desk where cold cases sit. Quiet, professional.
3. **The Second Chair** — detective language for the seat beside the
   lead investigator.

Del names it when he names it. Until then everything ships as
Murder Board.

## Data model

Every object carries `source_doc` and `quote` wherever it came from a
document. No quote, no object. That rule is the product's spine.

- **Document** — id, title, type (report, statement, transcript,
  record, ledger, photo), date, author, raw text.
- **Person** — id, name, aliases, role (victim, suspect, witness,
  officer, family, other), card of all mentions.
- **Claim** — id, person, statement text, quote, doc, date claimed,
  kind (whereabouts, action, observation, relationship, object).
- **Event** — id, what happened, when (exact or window), where, who,
  claims that support it, claims that fight it.
- **EvidenceItem** — id, description, logged_in (doc), mentioned_in
  (docs), status (logged, mentioned-only, missing).
- **Contradiction** — id, claim A, claim B, both quotes, kind
  (record-vs-statement, statement-vs-statement, timeline-collision),
  severity (high, medium, low), innocent alternative (one line, always
  present: memory, wording, clock error — the board offers it, the
  detective weighs it).
- **Alibi** — person, window claimed, claims, rating (corroborated,
  uncorroborated, contradicted), reasons with quotes.
- **Lead** — id, action ("re-interview X about Y"), score, reasons.
- **Gap** — id, what is missing, which documents prove it should exist.

## Agent contracts

Pipeline order is fixed: Intake, then Timeline, then Cross-Examiner,
then Sergeant. Each agent emits JSON only, validated before the next
agent runs. Any finding without two quotes (for contradictions) or one
quote (for everything else) is dropped by the runner, not shown.

1. **Intake** — in: raw documents. Out: persons, claims, events,
   evidence items, each with doc + quote.
2. **Timeline** — in: events + claims. Out: ordered events, time
   windows normalized, collisions marked where two claims put the
   same person or object in two places in one window.
3. **Cross-Examiner** — in: all claims + timeline + evidence ledger.
   Out: contradictions with both quotes and an innocent alternative
   each; alibi ratings with reasons; evidence items whose status is
   mentioned-only or missing.
4. **Sergeant** — in: everything above. Out: ranked leads (action,
   score, reason), the gap list, and the one page brief in detective
   language.

## Scoring rubrics

**Alibi rating** (decision rules, applied in order):
- CONTRADICTED if any claim inside the alibi window is contradicted
  by a record (tow log, receipt, examiner window, ledger) or by two
  independent statements.
- CORROBORATED if at least one record or independent statement inside
  the window supports it and nothing contradicts it.
- UNCORROBORATED otherwise. Most real alibis land here, and the board
  says so plainly instead of inflating.

**Contradiction severity:**
- HIGH: a record contradicts a statement, or the contradiction sits
  inside the time-of-death window.
- MEDIUM: statement vs statement on a checkable fact (place, object,
  visit).
- LOW: wording drift, minor time drift under one hour, secondhand
  claims.

**Lead score** (0–100, shown with its arithmetic):
- +40 if it touches a HIGH contradiction.
- +25 if it touches the time-of-death window.
- +20 if it closes a gap (missing evidence, missing interview).
- +15 if the person or record is still reachable (alive, in business,
  records retained).
The score is a sort order, not a probability. The brief says so.

## Judging map (what the room rewards, and where we score)

- **Use of Gemini / Managed Agents:** four named agents with visible
  jobs and a strict pipeline. The Cross-Examiner is a reasoning job;
  assign the reasoning variant (Argon) there, the fast variant to
  Intake. Say this on stage, it shows the models were chosen, not
  defaulted.
- **Impact:** homicide clearance rates are the stat. Roughly half of
  US murders go unsolved in recent FBI data years (verify the exact
  figure at the venue before quoting it; if unverified, say "about
  half" and move on). Cold files are where organization dies first.
- **Technical:** the quote-or-drop rule. Every judgment on screen can
  be clicked to the two quotes that produced it. That is the
  engineering claim: no uncited findings exist in the system.
- **Presentation:** the board building itself live, then the red
  thread click. Theatre with receipts.

## The alley after tomorrow (one paragraph, for the last slide)

Departments will not buy a hackathon demo, and the pitch should not
pretend otherwise. The alley is entered through the side door:
private investigators, cold case nonprofits, and journalists work
the same files with none of the big vendors' compliance overhead.
Win one of those rooms, learn the file formats and the language,
and the department version is a second product, not a first sale.
