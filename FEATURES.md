# FEATURES — from case review to case advancement

**Date:** 2026-11-21
**Scope:** product features for Murder Board that improve actual cold-case work. No code
changed. This is a build roadmap for Codex, not a UI polish list.
**Read "finding murders" two ways:** (1) finding homicides that were missed or
misclassified, and (2) finding the person responsible in an open or cold case. The
roadmap covers both. The second is the core.

---

## The gap, in one sentence

Murder Board currently answers **"what does this file say?"** It does not answer
**"which case should we work, what do we do Monday, what has already been tried, what can
still be tested, who is still alive, and can this be charged?"**

That is the difference between a case review and a case advancement tool. The current
pipeline is a strong review: quote-checked findings, contradictions, alibi ratings,
gaps, ranked leads, a brief. A cold-case unit needs the next layer.

Three questions drive the whole roadmap:

| Question | Current answer | Missing capability |
|---|---|---|
| Which case should we work next? | none; one case at a time | solvability review + portfolio queue |
| What do we do Monday? | ranked leads with scores | next-best-action queue with owners and status |
| What has already been tried? | almost nothing | do-not-redo / negative-results ledger |
| What can still be tested? | a gap list | forensic opportunity finder + lab packet |
| Who is still alive and reachable? | statements in the file | witness viability + interview sequencer |
| Is the alibi physically possible? | qualitative rating | time-distance feasibility validator |
| Are any of our cases linked? | per-case only | cross-case entity and MO links |
| What else could explain the file? | one innocent alternative per contradiction | hypothesis / alternative-suspect matrix |
| Can this be charged? | a six-row "court test" | element-by-element readiness matrix |
| What changed since last month? | full re-run | case delta / living file |

---

## Top 10, ranked by investigative impact

| # | Feature | Job it does | Effort | Risk |
|---:|---|---|---|---|
| 1 | **Solvability review** | Decide which cold case is worth working, and why | M | Low if framed as triage, not prediction |
| 2 | **Next-best-action queue** | Turn leads into assigned, tracked work | S–M | Low |
| 3 | **Do-not-redo ledger** | Stop the unit from repeating old checks | S | Low |
| 4 | **Forensic opportunity finder** | Find untested evidence and generate lab requests | M | Low; lab decides |
| 5 | **Witness viability + interview sequencer** | Find who is still alive and in what order to talk | M | Medium; privacy/contact rules |
| 6 | **Time-distance alibi validator** | Test whether claimed movements are possible | M | Low with uncertainty labels |
| 7 | **Cross-case link analysis** | Find shared people, phones, plates, addresses, MO | L | Medium; false links |
| 8 | **Hypothesis / alternative-suspect matrix** | Prevent tunnel vision; test competing explanations | M | Low if sourced and labeled |
| 9 | **Handoff + prosecution-readiness packet** | Make the case usable by a new detective or ADA | M | Low |
| 10 | **Case delta / incremental re-run** | Keep a long-lived case current when new paper arrives | M | Low |

Two enablers sit underneath these: a **portfolio dashboard** (the unit view) and a
**records/camera/canvass request generator** (the bridge from gap to evidence). Both are
covered below.

---

## What the pipeline already gives you

You are closer than it looks. The caches already contain the raw material for most of
these features.

| Current output | What it can power |
|---|---|
| `custody.documents` — doc id, type, legible, custody note | file inventory, OCR queue, page index, missing-document audit |
| `csi.ledger` — 22 items with item_no, description, quote, doc_id | evidence inventory, test-status tracker, chain audit |
| `csi.gaps` — 19 items with mentioned_in, problem, quote, doc_id | records/lab/canvass request generator |
| `digital.camera_gaps` — camera, mentioned_in, quote | camera canvass matrix |
| `intake.persons` / `claims` / `events` — 9 people, 30 claims, 7 events | witness index, entity resolution, victimology, timeline |
| `analyst.events` / `collisions` — 8 events, 2 collisions | time-distance validator, where-was-everyone matrix |
| `cross_examiner.alibis` / `contradictions` — 3 alibis, 5 contradictions | alibi matrix, hypothesis matrix, materiality scoring |
| `interviewer.histories` / `next_questions` — 2 histories, 9 questions | witness viability, interview packet, sequencing |
| `prosecutor.sufficiency` / `vetoes` / `corroboration_needed` | prosecution-readiness matrix, Brady/admissibility flags |
| `lead_detective.leads` / `gaps` / `brief` — 9 leads, 6 gaps | action queue, handoff packet, brief |

The missing piece is not extraction. It is **state**: what has been requested, what came
back, who owns it, what was negative, and what changed. Add state and the product becomes
a case-management system instead of a one-shot report.

---

# Part 1 — Case advancement

## 1.1 Solvability review

### Problem

Cold-case units have more files than time. The current app works whichever case is
selected. There is no defensible way to choose, and no record of why one case was picked
over another.

### Feature

A one-page **Solvability Review** generated from the file plus a short investigator
questionnaire for facts not in the file. It scores the *case*, never a person, on factors
that make a cold case workable today.

**Factors and weights (100 points):**

| Factor | Weight | What counts as present |
|---|---:|---|
| Named suspect | 10 | A person named as a suspect in a document, not merely mentioned |
| Suspect reachable | 10 | Alive, locatable, not already cleared by a documented check |
| Forensic evidence available | 15 | Physical items with probative value and a documented chain |
| Untested forensic opportunity | 15 | An item or test never submitted, or a new test now available |
| Witness available | 10 | A living, locatable witness who can prove a material fact |
| Video / imaging | 5 | Footage or stills that exist and have not been exhausted |
| Phone / digital records | 10 | CDR, tower, extraction, cloud, or platform records obtainable |
| Weapon recovered | 5 | Weapon or ballistic evidence in custody |
| Scene integrity / chain | 5 | Chain intact; no documented contamination or loss |
| Relationship / motive documented | 5 | A sourced relationship, debt, dispute, or benefit |
| Cross-jurisdiction cooperation | 5 | Another agency has records or a suspect and will respond |
| Family / community cooperation | 5 | A cooperative family or community channel |

Each factor is `present`, `absent`, or `unknown`. **Unknown is not zero evidence; it is a
data gap** and must be listed separately. Every `present` factor carries a quote and doc
id, or it does not count. The score is a sum with the arithmetic shown, in the same
spirit as the lead rubric.

**Tiers:** A = 70–100, B = 40–69, C = 0–39. The tier is a work-ordering aid, not a
prediction of clearance and not a judgment about any person.

**Output:**

- Score and tier, with the arithmetic.
- The three actions that would raise the score most.
- The unknowns, framed as "ask the detective" or "pull this record."
- A one-paragraph "why this case, why now" for the unit log.

**Data shape:**

```json
{
  "case_id": "delgado-2019",
  "score": 62,
  "tier": "B",
  "factors": [
    {
      "key": "untested_forensic",
      "label": "Untested forensic opportunity",
      "state": "present",
      "weight": 15,
      "evidence": { "quote": "Two shell casings were observed...", "doc_id": "doc01" },
      "note": "Second casing never entered the ledger; item 7 has a chain."
    }
  ],
  "unknowns": [
    { "key": "suspect_reachable", "question": "Is Webb still in New York?" }
  ],
  "top_actions": [
    "Submit item 7 for NIBIN and latent comparison.",
    "Locate and re-interview Ellen Vasquez; she was 71 in 2021.",
    "Pull Webb's full phone toll record for 11–14 OCT 2019."
  ]
}
```

### Why it solves cases

It directs scarce hours to cases with surviving evidence and living witnesses. It also
creates an auditable reason for prioritization, which matters when a family asks why
their case is not being worked.

### Guardrail

Do not call this a probability of solving. Do not score suspects. Do not let an unknown
factor become an accusation. The output is "where the work is," not "who did it."

### Effort

M — one new agent/step plus deterministic scoring, a questionnaire, and a screen. Most
inputs already exist in the book.

---

## 1.2 Next-best-action queue

### Problem

The Lead Detective produces nine leads with a 0–100 score. A score is not a work plan.
There is no owner, no status, no cost, no expected outcome, and no way to hand a lead to
the Records chair or the lab.

### Feature

Extend every lead into an **action item** with a lifecycle and an owner.

Add to the lead schema:

| Field | Values | Why |
|---|---|---|
| `action_type` | record pull / lab request / interview / canvass / legal / analysis | routes the work |
| `owner` | Records / Digital / Lab / Interviewer / CSI / ADA / Lead | who does it |
| `effort` | hours / days / weeks | cost |
| `probative_value` | high / medium / low | what it can prove |
| `likelihood` | high / medium / low | chance the record exists or the test works |
| `if_true` | sentence | what the case looks like if the action succeeds |
| `if_false` | sentence | what it means if the action fails |
| `status` | not started / requested / received / denied / done / dead end | state |
| `requested_at` / `due_at` / `closed_at` | dates | aging |
| `depends_on` | action ids | sequencing |
| `what_would_close` | sentence | definition of done |
| `doc_ids` | sources | provenance |

**Priority tiers:** P1 = high probative value + high likelihood + days or less. P2 =
medium/medium. P3 = backlog. Do not use a decimal expected-value score; it implies a
precision the file does not have.

**Views:**

- **Today** — actions that can be started now, grouped by owner.
- **Waiting** — requests sent, with aging and a follow-up date.
- **Backlog** — lower-value work.
- **Closed** — done, dead end, or denied, with the result.

**Example row (Delgado):**

```
ACTION   Pull the full phone toll record for Webb, 11–14 OCT 2019.
OWNER    Records            TYPE record pull        EFFORT days
VALUE    high               LIKELIHOOD high         PRIORITY P1
IF TRUE  Places or excludes Webb near the shop on Sunday night.
IF FALSE The alibi remains uncorroborated; the car contradiction stands alone.
CLOSES   The missing call record referenced in doc03; the Sunday gap in doc04.
SOURCE   doc03, doc04, doc11
```

### Why it solves cases

Most cold cases do not fail for lack of a theory. They fail because nobody owns the next
record, the request sits in a queue, and the case goes quiet. A tracked action queue is
the operating system of a cold-case unit.

### Guardrail

One action per item, as the Lead Detective prompt already requires. No bundling. Contact
actions are phrased as the detective's work, never as something the board does.

### Effort

S–M. Schema extension, deterministic grouping, a queue screen, and export.

---

## 1.3 Do-not-redo ledger

### Problem

Cold cases are full of repeated work: the same canvass, the same camera, the same lab
submission, the same relative interviewed three times by three detectives. The file may
record the original statement but not the negative result. Nobody knows what was already
tried.

### Feature

A **checks ledger** that records every investigative action and its outcome, including
negative and inconclusive results.

**Check object:**

```json
{
  "id": "chk-0042",
  "subject_type": "camera",
  "subject": "Diner across Fifth Avenue",
  "what": "Pull footage for 13 OCT 2019, 2100–2400",
  "result": "negative",
  "result_detail": "Footage overwritten; 30-day retention. Earliest available 12 SEP 2019.",
  "who": "Det. S. Park #3901",
  "when": "2021-03-18",
  "source": "supplemental report",
  "doc_id": "doc10",
  "confidence": "high",
  "follow_up": "none; do not re-request unless retention policy changes"
}
```

**Results:** `positive`, `negative`, `inconclusive`, `not done`, `destroyed`,
`unavailable`, `refused`.

**Behaviors:**

- Before a new action is created, search the ledger for the same subject/record.
- If a match exists, show a warning: **"Already checked 18 MAR 2021 — negative. Open the
  report before assigning."**
- Let a detective override with a reason ("new retention window," "new custodian," "new
  legal process").
- Include the ledger in the handoff packet and the brief appendix.
- Show a **"checked, negative"** section on the Clock and the gap list, so absence is
  visible, not lost.

**Examples to seed:**

- Diner camera — overwritten.
- Shop DVR — no drives installed.
- Webb's workplace — verified he was at the shop Friday, not Sunday.
- Rosa Delgado — interviewed 2019; no re-interview since.
- Neighbor Vasquez — interviewed 2021, two years late.
- Whitfield — three statements; never re-interviewed after the third.

### Why it solves cases

It saves the single scarcest resource in a cold case: detective hours. It also prevents
contamination and contradiction: a witness interviewed repeatedly with different
questioners is a defense attorney's gift.

### Guardrail

A negative check is not proof of innocence, and a positive check is not proof of guilt.
Record the source and the date. Never delete a check; supersede it.

### Effort

S. New object, a small screen, and a lookup at action creation.

---

## 1.4 Forensic opportunity finder

### Problem

The CSI chair reconciles the ledger and lists gaps, but the app does not know what has
been tested, what is still testable, or what new tests exist. "Evidence" is a list, not a
testing plan.

### Feature

An **evidence test inventory** and a **forensic opportunity finder**.

**Per item:**

| Field | Values |
|---|---|
| `item_no` | ledger item |
| `description` | as logged |
| `test_status` | untested / tested-negative / tested-inconclusive / consumed / destroyed / unknown |
| `last_tested` | date or unknown |
| `result` | profile/hit/negative/unknown |
| `sample_remaining` | yes / no / unknown |
| `storage` | property / lab / returned / unknown |
| `chain_ok` | yes / no / gap |
| `candidate_tests` | DNA STR / Y-STR / mitochondrial / SNP / IGG / latent prints / NIBIN / touch DNA / hair / fibers / GSR / tox / digital extraction / video enhancement / audio / questioned documents |
| `priority` | A / B / C |
| `rationale` | what the test could prove or exclude |

**Output:**

- A ranked testing plan: item, test, question, expected value, sample risk, estimated
  turnaround.
- A **lab submission packet**: item, chain, test requested, question it answers, form
  fields, contact, return instructions.
- A **"never tested"** list. This is often the whole cold case.

**Delgado example:**

- Item 7, spent casing → NIBIN; question: does it match a known firearm? Chain is intact.
- Item 21, swabs from door handle → DNA; question: does an unknown profile exist? Sample
  status unknown.
- Item 11, DVR with no drives → digital forensic examination of the unit; question: is
  there remnant video or configuration data?
- Victim's phone, item 3 → extraction; question: last calls, messages, location.
- The second casing → no item exists; the finding is "locate or account for it," not a
  lab request.

### Why it solves cases

New forensic testing is the single most common way a cold case breaks: DNA, latent
prints, NIBIN, digital extractions, and re-testing with newer methods. A tool that finds
untested items and writes the request is directly generating investigative action.

### Guardrail

The lab decides what to test and whether a sample is sufficient. Never claim a test will
identify a person. Never access CODIS/NDIS directly; the output is a submission packet
for a qualified human. Label all expected results as questions, not predictions.

### Effort

M. Inventory schema, test catalog, deterministic ranking, packet template. No external
database integration.

---

## 1.5 Witness viability and interview sequencer

### Problem

The app lists witnesses and next questions, but not who is alive, who is locatable, who
has been re-interviewed, who is fragile, who is protected, or what order to approach them
in. In a cold case, the witness list is a race against time.

### Feature

A **witness card** for every person with a material statement:

| Field | Values / source |
|---|---|
| `status` | alive / deceased / incarcerated / unknown (public records only) |
| `age` | from file or public record |
| `last_known_location` | from file or public record |
| `last_contact` | date and source |
| `prior_statements` | count, dates, doc ids |
| `reinterviewed` | yes/no; date |
| `reliability` | high / medium / low; why, sourced |
| `relationship` | victim / suspect / family / employee / neighbor / official |
| `can_prove` | material facts, each with a quote |
| `legal_flags` | minor / protected / represented / immunity / pending case |
| `interview_order` | 1..n, with reason |
| `cautions` | do not reveal X; do not show Y; attorney present |

**Sequencing logic (deterministic, explainable):**

1. Start with the witness most likely to be lost to time (oldest, ill, out of state).
2. Start with the witness least connected to the suspect, to avoid alerting the suspect.
3. Re-interview inconsistent witnesses before new witnesses.
4. Pull records before interviews when the record can confirm or refute the account.
5. Leave the suspect for last, after the record and the peripheral witnesses are locked.

**Output:** an **interview packet** per witness: prior statements, changes, questions
anchored to quotes, documents to show or withhold, legal cautions, and a follow-up plan.

**Delgado example:**

- Rosa Delgado — last call with the victim; interview first, before her memory or health
  changes. Ask about the debt and the last conversation.
- Ellen Vasquez — neighbor; interviewed two years late; ask why she remembered the car
  and what she saw, not what she concluded.
- Dana Whitfield — three statements; re-interview on the Sunday visit; ask what time she
  used her key, not whether she was there.
- Marcus Webb — last; after the tow record, the phone record, and the neighbor are
  locked.

### Why it solves cases

Witnesses die, move, and become unavailable. The order and the packet are the difference
between a productive re-interview and a lost one. It also protects the case from
contamination and from alerting a suspect too early.

### Guardrail

The board does not contact anyone. It prepares the knock. Public-record status checks
only; no credentialed systems. Label "unknown" rather than guessing. Flag minors,
protected witnesses, and represented persons.

### Effort

M. Person status fields, deterministic ordering, packet template. Uses existing
`next_questions` and `histories`.

---

## 1.6 Time-distance alibi feasibility

### Problem

Alibi ratings are qualitative. "CONTRADICTED" can mean a real impossibility or a
20-minute drive the model did not check. The Clock lists events but does not compute
whether a person could be in two places in the available time.

### Feature

A deterministic **feasibility validator** for claimed movements.

**Inputs:**

- Claimed place and time (from statements).
- Recorded place and time (from records, cameras, calls, receipts).
- Travel mode and route (walk, car, transit).
- Distance and travel time (configurable speed table for MVP; routing service later).
- Uncertainty: "about," "around," "approximately," "after."

**Output per alibi:**

```
Webb: home (78th St) 21:00–24:00  vs  shop (Fifth Ave) 23:30
Distance 2.4 mi · drive 9–14 min · walk 45–55 min
Verdict: POSSIBLE, not exculpatory. The car claim is contradicted; the presence claim is not.
```

**Verdicts:** `impossible`, `tight`, `possible`, `unknown`. Every verdict shows the
assumptions and the source of the time and place. The model proposes; the runner
computes.

**Why this matters:** it prevents false contradictions and finds real impossibilities.
It also gives the alibi table a quantitative backbone without pretending to precision.

### Guardrail

Travel time is an estimate, not proof. Never say "impossible" without naming the route,
the mode, and the uncertainty. A person can lie about a time without being physically
unable to commit the act.

### Effort

M for the deterministic validator and a speed table; L if adding live routing. Start
with a small table of known distances in the case file, not a third-party dependency.

---

# Part 2 — Cold-case portfolio

## 2.1 Cross-case link analysis

### Problem

Every case is an island. The app cannot see that the same phone, plate, address, person,
weapon, or MO appears in another file. Serial cases and pattern cases are exactly the
ones a per-case tool misses.

### Feature

A **cross-case entity index** and a **related cases** panel.

**Entity types:**

- Person: name + DOB + aliases; exact and fuzzy.
- Phone: normalized number; burner patterns; shared contacts.
- Vehicle: plate, VIN, make/model/color.
- Address: normalized address; business; storage; residence.
- Weapon: caliber, casing, NIBIN lead, recovery location.
- MO / signature: entry method, time of day, victim profile, location type, staging.
- Financial: account, policy, beneficiary, debt.
- Digital: handle, email, device, platform ID.

**Matching tiers:**

1. **Exact** — same normalized value. Show automatically.
2. **Strong** — same value plus a second identifier (name + DOB, plate + vehicle).
3. **Weak** — same surname, similar address, same MO. Show as "candidate," never merge.
4. **Human-confirmed** — a detective marks the link; it becomes part of the case.

**Output:**

```
RELATED CASE · Harborlight 2016
Link: same phone number (555-0142) appears in Delgado doc10 and Harborlight doc10.
Confidence: strong · Source: two records · Not merged.
[open both documents]
```

### Why it solves cases

Cross-case links are how serial offenders are found and how a cold case gets a new
suspect, a new witness, or a new jurisdiction. This is the highest-leverage "finding
murders" feature in the roadmap.

### Guardrail

Same-name collisions are shown, never merged; this is already a house rule. Never label
a case "serial" or a person "linked" without human review. A shared phone can be a
family plan, a business line, or a data error. Show the evidence and the uncertainty.

### Effort

L. Needs a portfolio store, entity normalization, and a review UI. Start with exact
matches on phone, plate, and address; add names and MO later.

---

## 2.2 Portfolio dashboard

### Problem

The app has a case dropdown. A cold-case unit has a caseload, statuses, deadlines, and
stalled requests. There is no unit view.

### Feature

A **case index** with one row per case:

| Case | Victim | Status | Solvability | Top action | Outstanding | Last worked | Next deadline |
|---|---|---|---|---|---|---|---|
| MB-2019-1014 | Delgado | Cold | B | NIBIN item 7 | Phone record | 21 NOV | 28 NOV |
| MB-2016-1010 | Marsh | Cold | A | Re-interview Herrera | Lab DNA | 18 NOV | 25 NOV |
| MB-2025-1012 | Ellis | Open | B | Plate record | Camera | 21 NOV | 24 NOV |

**Views:** all cases, my cases, stalled (no action in 30 days), court dates, family
requests.

**Batch action:** select cases and run a triage pass; the output is a ranked work queue,
not a pile of reports. This is the "optimized" unit-level feature.

### Why it solves cases

It makes the work visible. Stalled cases get noticed; deadlines do not slip; a supervisor
can see which case has an untested item and no owner.

### Guardrail

Do not rank cases by victim importance or media attention. Rank by solvability factors
and documented opportunities.

### Effort

M–L. Needs persistent case metadata and the solvability output; can start as a static
index over the four cases.

---

## 2.3 Records, camera, and canvass request generator

### Problem

The gap list says "diner camera never pulled." It does not produce the request, the
custodian, the legal basis, the deadline, or the follow-up. A gap without a request is a
note.

### Feature

A **request generator** for the common cold-case paper trails:

- **Camera canvass grid:** address, business, camera type, angle, retention window,
  owner/contact, status (not asked / asked / pulled / overwritten / refused), footage
  range, what it shows, chain.
- **Neighborhood canvass grid:** address, contact, date, officer, result, follow-up.
- **Phone preservation letter:** number, provider, legal process, date range, content
  sought, preservation deadline.
- **Records requests:** DMV, insurance, tow, utility, court, jail, probation, business
  filing, social media preservation.
- **Lab submission packet:** item, chain, test, question, form.
- **Interview request:** witness, location, questions, cautions.

Each request has: legal basis, custodian, contact/portal, what to ask, return format,
deadline, owner, status, and chain notes. The output is a packet a detective can send,
not a paragraph.

**Camera grid example:**

| Address | Camera | Retention | Status | Footage range | Notes |
|---|---|---|---|---|---|
| 1150 Fifth Ave (diner) | exterior, front | 30 days | overwritten | none | requested 15 OCT 2019; earliest 12 SEP |
| 1140 Fifth Ave (shop) | DVR, no drives | unknown | no record | none | unit seized, item 11 |
| 1120 Fifth Ave (laundry) | door cam | 14 days | not asked | unknown | ask owner; faces shop front |

### Why it solves cases

Video and phone records are perishable. A grid shows what was never asked and what is
about to disappear. The request packet turns analysis into evidence.

### Guardrail

No contact by the board. Human review before sending. No pretexting, no impersonation,
no access to credentialed systems. Public-records and lawful process only.

### Effort

M. Templates and deterministic generation from gaps; no external integrations required.

---

# Part 3 — Investigative reasoning

## 3.1 Hypothesis / alternative-suspect matrix

### Problem

The board builds one narrative and attaches one innocent alternative to each
contradiction. That is better than most tools, but it is not a structured test of
competing explanations. Cold cases are especially vulnerable to tunnel vision: the
original detective's theory becomes the file's theory.

### Feature

A **hypothesis matrix** with competing explanations, evidence for and against, and the
evidence that would discriminate between them.

**Hypotheses (example, Delgado):**

1. The partner, Webb, committed the murder for the business.
2. A supplier or debtor committed the murder over money.
3. A burglary interrupted, not a planned killing.
4. Someone known to the victim, not yet named in the file.
5. Unknown / outside the file.

**Per hypothesis:**

| Field | Content |
|---|---|
| `statement` | one sentence, no names as fact |
| `status` | open / weakened / eliminated / needs evidence |
| `evidence_for` | quote + doc id |
| `evidence_against` | quote + doc id |
| `discriminating_evidence` | what would separate this from the others |
| `records_to_pull` | record + what it would show |
| `questions_to_ask` | person + question |
| `confidence` | low / medium / high, with reason |

**"What would change my mind"** is mandatory for every key finding. A board that cannot
state its disconfirming evidence is a prosecution memo, not an investigation.

### Why it solves cases

It prevents premature closure, surfaces exculpatory evidence, and produces the exact
questions and records that distinguish one theory from another. It is also the strongest
ethical feature in the product: it makes the board argue with itself.

### Guardrail

Hypotheses are labeled as hypotheses. No guilt score, no suspect ranking, no "most
likely killer." Every row is sourced or marked unknown. The unknown/outside hypothesis
is always present.

### Effort

M. Mostly prompt/schema work plus a matrix screen. Uses existing contradictions, claims,
and alibis.

---

## 3.2 Element-by-element prosecution readiness

### Problem

The "court test" is six rows of weak/strong. A prosecutor needs the elements of the
offense, the evidence for each, the gaps, and the admissibility problems. "Strong" is not
a legal analysis.

### Feature

A **readiness matrix** keyed to the charged offense (homicide) and the likely legal
theory:

| Element | Evidence | Source | Gap | Strength | Owner |
|---|---|---|---|---|---|
| Identity | | | | | |
| Act / causation | | | | | |
| Intent / mens rea | | | | | |
| Venue | | | | | |
| Corpus delicti | | | | | |
| Chain of custody | | | | | |
| Admissibility (hearsay, confrontation) | | | | | |
| Brady / Giglio | | | | | |
| Statute / jurisdiction | | | | | |

Each cell: evidence, quote, doc id, gap, and a `weak / developing / sufficient` rating
with a reason. Add a **defense challenge** column: what the defense will attack.

### Why it solves cases

A cold case is not solved when the board has a theory; it is solved when a prosecutor
can charge it. This matrix tells the unit what evidence is missing for trial, not just
for the file. It also surfaces Brady material early, which is both legally required and
case-saving.

### Guardrail

This is an investigative aid, not legal advice. An ADA reviews every row. Do not label a
person guilty; label the evidence sufficient or insufficient for an element.

### Effort

M. Uses `prosecutor.sufficiency`, `vetoes`, `corroboration_needed`; add an element
template and a matrix.

---

## 3.3 Claim provenance and confidence

### Problem

The quote check proves the quote is in the file. It does not prove the *claim* is a
quote, an inference, or an absence. A model can string two real quotes into a false
inference, and the board will show both quotes as if the conclusion were sourced.

### Feature

Every finding gets a **claim type** and a **confidence**:

- `direct` — the document says it in one sentence.
- `inference` — the finding is a conclusion from two or more passages.
- `absence` — the finding is that something is missing.
- `external` — a record outside the file (only with a source label).
- `unknown` — the file does not support a conclusion.

Plus:

- `source_reliability`: record / official statement / witness statement / anonymous /
  public post / summary.
- `what_it_does_not_prove`: one sentence.
- `confidence`: high / medium / low, with a reason.
- `corroboration_count`: how many independent sources.

This is a foundational layer. It makes the hypothesis matrix, the readiness matrix, and
the witness reliability fields honest.

### Why it solves cases

It prevents the most dangerous failure mode in an AI investigation tool: a true quote
supporting a false conclusion. It also tells the detective where to spend verification
time.

### Guardrail

Do not let a confidence label become a guilt score. Confidence is about the support for
the claim, not about the person.

### Effort

S–M. Schema additions and rendering; no new model call required for the type if the
prompts already separate claims, events, and gaps.

---

# Part 4 — Finding murders that were missed

## 4.1 Death-review / missed-homicide screen (P2, requires an advisor)

### Problem

Some homicides are filed as accidents, overdoses, suicides, natural deaths, or
"undetermined." The app only works files that are already labeled homicide. It cannot
help a coroner, family, or journalist spot a death that deserves a second look.

### Feature

A separate **Death Review** mode with a structured checklist, not a diagnosis:

- Scene: altered, cleaned, staged, unlocked, valuables untouched, body moved.
- Injuries: pattern inconsistent with the stated mechanism; defensive wounds; burns;
  ligature; petechiae; multiple sites.
- History: prior domestic calls, protective orders, threats, insurance changes, recent
  beneficiary change, debt, custody dispute.
- Medical: death certificate vs autopsy; tox missing; prescription anomalies; doctor
  shopping; multiple providers.
- Cluster: same address, same care facility, same demographic, same cause, same
  coroner, unusual frequency.
- Investigation: no scene photos, no canvass, no interviews, short report, no follow-up.

**Output:** "Second look recommended" with the specific reasons and sources, plus the
records/questions that would resolve it. Never "this is a homicide."

### Why it solves cases

This is literally finding murders that were missed. Clusters of undetermined deaths in
hospitals, nursing homes, and same-address cases have been caught this way. It is also a
strong public-interest story for a hackathon.

### Guardrail

This is the highest-risk feature in the document. It requires a medical examiner or
forensic pathologist advisor, a legal review, and careful language. It must not diagnose,
accuse, or imply a person is responsible. It recommends a human second look, with
sources. Do not ship it as a standalone accusation tool.

### Effort

L–XL. New front door, new intake, new checklist, new evidence model, and expert review.
Keep it out of the core demo unless the advisor is real.

---

## 4.2 Tip intake and public appeal (P2)

### Problem

Cold cases often break on a tip or a public appeal. The app has no tip object and no way
to turn verified file facts into a public ask.

### Feature

**Tip intake:** source (named/anonymous/Crimestoppers/jailhouse), date, handler,
reliability, what it claims, what it corroborates, what it contradicts, follow-up,
status. Tips are not evidence; they are leads to verify.

**Public appeal draft:** verified facts only, redactions, timeline, photos (with rights),
what the public should look for, how to submit, and a "do not approach" line. Every
sentence cites the file or is removed.

### Why it solves cases

Publicity is one of the few ways a cold case generates new witnesses. A verified,
redacted appeal is safer and faster than a detective writing one from scratch.

### Guardrail

Human review, legal review, no naming of uncharged suspects, no defamatory language, no
release of victim privacy, no contact by the board.

### Effort

M–L. Tip schema + appeal template; the hard part is review, not code.

---

# Part 5 — Engine optimizations that unlock the features

These are not "make it faster" tweaks. They are what lets the product handle a real
cold-case file and a real caseload.

| Optimization | What it unlocks | Effort |
|---|---|---|
| **Parallel independent chairs** | Records, Coroner, CSI, and Intake can run concurrently after custody; cuts run time and lets the room feel like a squad | M |
| **Incremental step cache** | Re-run only steps affected by a new document; powers case delta and cheap portfolio runs | M |
| **Page/offset quote index** | O(1) quote verification, click-to-highlight, page cites, diffing; essential for 1,000-page files | S–M |
| **Retrieval / chunking** | Send each chair only the relevant pages; handles large files without context overflow and improves recall | L |
| **OCR / layout parsing** | Ingest scanned reports, forms, handwritten statements; map text to page and box | L |
| **Entity resolution** | Canonical person/phone/plate/address IDs across steps and cases; prevents duplicate people and enables links | M–L |
| **Deterministic validators** | Time math, distance, counts, identity, chain; the runner owns more than lead arithmetic | M |
| **Evaluation harness** | Per-case precision/recall, false positives, alibi calibration, lead usefulness, cost/latency; A/B prompts | M |
| **Model routing / escalation** | Cheap extraction, reasoning for judgment, second pass on low confidence; controls cost | S–M |
| **Local / private deployment** | Real departments cannot send case files to a public API; a local mode is a product requirement, not a nice-to-have | L |
| **Redaction / PII pipeline** | Public demos, records requests, and family communication without leaking identifiers | M |
| **Batch / portfolio runs** | Triage 50 cold cases overnight; the unit-level "optimized" story | M–L |

The most important one for the current demo is **page/offset quote index**, because it
makes every quote clickable and every page citable. The most important one for a real
unit is **local/private deployment**, because without it the product cannot touch a
real case file.

---

# Part 6 — Build order

## Phase 0 — foundations (1–2 days)

1. Claim provenance and confidence fields.
2. Page/offset quote index and click-to-highlight.
3. Canonical entity IDs (person, phone, plate, address).
4. Action and check schemas (even if the UI is minimal).
5. A persistent case metadata object (status, owner, last worked, next deadline).

Without these, the features become another pile of JSON.

## Phase 1 — single-case advancement (3–5 days)

6. Solvability review, single case.
7. Next-best-action queue with owners and status.
8. Do-not-redo ledger.
9. Forensic opportunity finder + lab packet.
10. Witness viability + interview sequencer.
11. Time-distance alibi validator.
12. Case delta / incremental re-run.
13. Hypothesis matrix (cheap, high value; can move earlier).

This phase makes the product useful on one cold case. It is the best demo.

## Phase 2 — unit-level cold-case work (1–2 weeks)

14. Portfolio dashboard + batch triage.
15. Cross-case entity index and related-cases panel.
16. Records/camera/canvass request generator.
17. Handoff + prosecution-readiness packet.

This phase makes it a unit tool, not a single-case demo. Cross-case links are the
headline.

## Phase 3 — differentiators and new front doors (2–4 weeks)

18. Death-review / missed-homicide screen, with a medical advisor.
19. Tip intake + public appeal.
20. Collaboration, assignments, sign-off, audit log.
21. Local/private deployment and redaction.

Do not start Phase 3 without the Phase 0 foundations.

---

# Part 7 — How to measure whether it works

Do not measure "cases solved" in a hackathon; the sample is too small and the claim is
too easy to fake. Measure whether the tool produces **actionable, verified work**.

| Question | Metric | Target |
|---|---|---|
| Is triage real? | % of cases with a solvability review; % of factors with a source or an explicit unknown | 100% / >80% |
| Is the work plan real? | # actions with owner, status, due date; % of actions completed or closed as dead end | >90% / tracked |
| Is the evidence plan real? | # untested items found; # lab requests generated; # items with a documented test status | baseline + |
| Are witnesses being worked? | # witnesses with viability status; # re-interviews scheduled; # statements that changed | baseline + |
| Is the file staying current? | # new documents processed; # findings changed; # gaps closed | per month |
| Are cases linked? | # candidate links; # human-confirmed links; # new investigative openings | >0 confirmed |
| Is the reasoning honest? | false-contradiction rate after detective review; alibi calibration; quote verification pass rate | decrease / >95% quote |
| Is it efficient? | time to first actionable lead; run time per 100 pages; cost per case; duplicate checks avoided | improve |

Never report "clearance rate" as a product metric. The product does not clear cases; the
detective does.

---

# Part 8 — Guardrails and do-not-build list

**Guardrails**

- No guilt score, suspect probability, or "most likely killer" ranking.
- No direct access to NCIC, CODIS, NDIS, Accurint, CLEAR, or other credentialed systems.
- No contact with anyone; interview questions are for the detective.
- Every finding carries a quote; every inference is labeled as an inference.
- Every action is human-reviewed before it is sent or executed.
- Labs decide tests; medical examiners decide cause/manner; prosecutors decide charges.
- Public-record and lawful-process sources only; no breach data, no pretexting, no
  impersonation.
- Same-name collisions are shown, never merged.
- Privacy: minimize PII, redact exports, audit access, support local deployment.
- Bias: alternative hypotheses, disconfirming evidence, and a "what would change my
  mind" field are mandatory.

**Do not build**

- A "Solve" button.
- A chatbot that contacts witnesses or suspects.
- Face recognition on crowd video or social media.
- Genetic genealogy without a legal/ethical framework and consent.
- A generic case summarizer with no provenance.
- A prediction of dangerousness or guilt.
- More agents for the sake of more agents.
- A public leaderboard of "cases solved" by the model.

---

# Part 9 — The three-minute demo this unlocks

The current demo shows a contradiction. The cold-case demo shows **a case moving**.

1. **0:00 — the portfolio.** Three cold cases. The solvability review puts Harborlight
   at A, Delgado at B, Screens at B. It says why: an untested item, a living witness, a
   phone record never pulled.
2. **0:30 — the work plan.** Delgado opens. Three actions are assigned: NIBIN on item 7,
   a phone toll pull, and a re-interview of Rosa. The do-not-redo ledger warns that the
   diner camera was checked in 2021 and is gone.
3. **1:10 — the evidence.** The forensic finder shows item 7 untested, sample intact,
   chain intact. It generates a lab packet with the exact question: does the casing match
   a known firearm?
4. **1:40 — the people.** The witness sequencer puts Rosa first, Whitfield second, Webb
   last, with reasons and questions anchored to quotes.
5. **2:10 — the pattern.** A cross-case link shows the same phone number in another
   file. It is a candidate, not a conclusion; both documents open side by side.
6. **2:35 — the handoff.** A packet exports: solvability, actions, evidence plan,
   witness plan, hypotheses, readiness matrix, brief, and the do-not-redo ledger.

Close: **"It does not solve the case. It finds the work that can."**

That is a stronger claim than another contradiction, and it is still honest.

---

# Part 10 — Copy-paste prompt for Codex

Use this after reading the doc. It is scoped to Phase 0 + Phase 1.

```
Read FEATURES.md in the repo. Build Phase 0 and Phase 1 only. Do not change the
quote check, the scoring rubric, the case data, or the existing screens' behavior
except where the new fields need to render.

Phase 0:
1. Add claim_type (direct/inference/absence/external/unknown), confidence,
   source_reliability, what_it_does_not_prove, corroboration_count to every claim
   and finding. Render them as small labels, not new prose.
2. Store page number and character offsets for every accepted quote; make quote
   clicks highlight the span in the document viewer.
3. Add canonical entity ids for persons, phones, plates, and addresses.
4. Add actions[] and checks[] to the book. Persist them per case in localStorage
   for now; design the schema so a server can own it later.
5. Add case metadata: status, owner, last_worked, next_deadline.

Phase 1:
6. Solvability review: 12 factors, 100 points, present/absent/unknown, source
   quote or explicit unknown, tier A/B/C, top three actions. No person scored.
7. Next-best-action queue: extend leads with action_type, owner, effort,
   probative_value, likelihood, if_true, if_false, status, requested_at, due_at,
   what_would_close, depends_on. Group by Today / Waiting / Backlog / Closed.
8. Do-not-redo ledger: checks with subject, what, result, who, when, source,
   doc_id, follow_up. Warn when a new action matches an existing negative check.
9. Forensic opportunity finder: item test_status, last_tested, result,
   sample_remaining, chain_ok, candidate_tests, priority, rationale. Generate a
   lab packet.
10. Witness viability: status, age, last_known_location, last_contact,
    prior_statements, reinterviewed, reliability, legal_flags, interview_order,
    cautions. Generate an interview packet.
11. Time-distance alibi validator: parse times/places, use a small configurable
    speed table, return impossible/tight/possible/unknown with assumptions.
12. Case delta: when a document is added, re-run only affected steps and show
    new/changed/resolved findings with quotes.

Rules:
- Every new finding still needs a quote and doc id or it is dropped.
- Unknown is a valid, visible state. Never guess.
- No guilt score, no suspect ranking, no contact, no external databases.
- Keep the existing four cases working. Add tests for the new validators using
  the Delgado cache.
Report what you ran and what you could not verify.
```

---

## Bottom line

The current product is a very good **case review**. The features above turn it into a
**case advancement** system: it chooses the case, assigns the next record, finds the
untested evidence, sequences the witnesses, checks the alibi math, remembers what was
already tried, links the cases, argues with its own theory, and hands the next detective
a packet.

That is what "optimized for solving cold cases" actually means. Not a faster summary —
a shorter path from a file on a shelf to a piece of evidence someone can test.
