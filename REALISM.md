# REALISM — how to make it read as a real file, a real squad, and a real system

**Date:** 2026-11-21
**Scope:** `app/app.js` (1,698 lines), `app/index.html`, `app/style.css`, all four `case*/`
document sets, the cached runs in `cache/`, `AGENTS.md`, `EVAL.md`, `README.md`,
`SUBMISSION.md`, `DEMO_SCRIPT.md`. Read-only. No code changed.
**Method:** I counted what the app actually has — documents, characters, persons, claims,
contradictions, gaps, ledger items — then compared each surface to how the real artifact
works. Numbers below are from the files and caches, not impressions.

---

## The five-minute version

If you change only five things, change these. They buy the most "real" per hour:

1. **Stop lying about time.** The replay stamps every message with the current clock
   (`new Date()` in `chatBubble` and `chatHandoff`) and the run clock counts the ten
   seconds the replay takes. A judge who watches a "7.5 minute run" finish in ten
   seconds and sees every post timestamped 2:47 PM learns the whole room is theater.
   Record per-step times in the cache and render `T+00:04:12`, plus the recorded
   duration and a `REPLAY ×N` badge. This is the single biggest tell.

2. **Move the submission page out of the product.** The header currently carries the
   public repo link, the eval link, the demo script link, "Built today at Gemini 4 NYC",
   a live API-key field, a "Replay cached run" checkbox, and the model line
   (`ARGON judges · CARBON builds...`). None of that belongs in a homicide tool. Put it
   in a `System / About this build` drawer. The public demo should never show a key
   field. Keep the proof one click away; stop wearing it as a hat.

3. **Give every document its paper.** Today every document is a 250–1,335 character
   text blob rendered in one `<pre>`. No case number, report number, page number,
   author badge, signature, received stamp, classification, or Bates number. Add a
   page template, page counts, a footer, and highlight the quoted span when a quote is
   opened. The file will instantly stop reading like a `.txt` export.

4. **Make the board mean something.** Right now every person–document citation draws
   yarn, so 14 documents and 30 claims produce a pale web that says "these papers are
   in the same folder." Red string should mean a conflict, and every string should
   carry a label. Stop pinning every named person: the Delgado board pins three cops
   and a tow operator; the Duck board pins 22 people including "Unnamed woman,"
   "Unnamed man," a teenager killed in 2011, and a rapper who died in 2020.

5. **Add one visceral artifact and one negative result per case.** A CAD/911 log for
   Delgado, a deleted-story placeholder for Screens, a federal court caption for Duck,
   a marina camera that was offline for Harborlight. Real files are mostly absence,
   and absence is what makes the presence feel real.

Then read the rest in order: file, board, room, system, copy deck, build order.

---

## Verdict

The spine is real. The quote check, the runner-owned arithmetic, the alibi ratings, the
"judges the file, never a person" position, the four cases with answer keys, and the
honest eval are stronger than most hackathon submissions. Do not touch those.

The **surface** is still a demo. Not because the design is ugly — the corkboard is good —
but because the artifacts behave like data structures instead of paper, the agents talk
like a product tour, and the system hides every sign of being a system.

Three different realnesses are being confused:

| Realness | What it means | Current state |
|---|---|---|
| **Artifact realism** | This looks like a homicide file pulled from a shelf | 14 short text files, no page chrome, no chain of custody |
| **Procedural realism** | This is how detectives and records actually work | Strong doctrine, weak titles, no negative results, no noise |
| **System realism** | This is a running pipeline with timestamps, failures, and receipts | No run receipt, no per-step timing, no retry, no trace |

Fix them in that order. Artifact realism is cheapest and most visible. System realism is
what survives a judge's hardest question.

---

## What the scan actually found

### The Delgado file, measured

- **14 documents. 10,537 characters total.** That is roughly six pages of dense text,
  printed as fourteen one-page documents. A real homicide murder book for a case this
  age is hundreds to thousands of pages. The app calls it "the file" and gives it a
  case number, but a judge can read the whole thing in twelve minutes.
- **9 persons**: the victim, four civilian witnesses/suspects, three police officers
  (Brennan, Osei, Park), and the tow operator. `renderBoard` pins **all nine** with
  portraits, including the patrol officer and the cold-case detective.
- **30 claims, 7 events, 5 contradictions, 19 gaps, 22 ledger items, 2 collisions.**
- **The whole run is one 14-document stack.** No noise, no irrelevant paperwork, no
  duplicate, no dead end. Every document is load-bearing. Real files are mostly
  irrelevant; that is why detectives complain about them.

### The other cases

| Case | Docs | Persons extracted | Contradictions | Gaps | Ledger |
|---|---:|---:|---:|---:|---:|
| Delgado (police file) | 14 | 9 | 5 | 19 | 22 |
| Screens (internet case) | 12 | 8 | 6 | 4 | 5 |
| Harborlight (sim) | 18 | — | — | — | — |
| Duck (real case) | 12 | **22** | 1 | 13 | **0** |

The Duck extraction is the clearest evidence that the board needs a roster rule. Those
22 persons include "Unnamed woman," "Unnamed man," "Unnamed informant," "Unnamed friend
of Ralph Turpin," a teenager killed in 2011, a dead O Block member, and King Von. All of
them become person cards. A detective would pin the victim, the defendants, the
witnesses who matter, and the records. Not the entire cast of the public record.

### The replay is timestamped now

The cache stores `created_at` and the outputs. It does **not** store per-step start/end
times, latency, model, or token counts. `run_log` for Delgado is two lines. So:

- `chatBubble()` and `chatHandoff()` call `new Date().toLocaleTimeString()` when the
  message is rendered, not when the step ran.
- The run clock in `work()` starts at zero when the replay starts.
- The header labels the run with its saved start time; the room stamps every post with the moment the replay renders.
- The demo script says a live run takes about 7.5 minutes; the replay compresses that
  to seconds, and nothing on screen acknowledges the compression.

This is not a cosmetic bug. It is the one thing that makes a judge say "so the chat is
fake." The chat output is real; the time is not. Fix the time and the same output reads
as a recording of real work.

### The documents are 7–31 lines each

| Case | Shortest | Longest | Lines |
|---|---:|---:|---|
| Delgado | 291 chars (diner receipt) | 1,090 (ledger) | 13–25 |
| Screens | 250 (Kayla comment) | 1,048 (Reddit collation) | 7–28 |
| Harborlight | 253 (toll record) | 917 (scene report) | 7–21 |
| Duck | 566 (Chrysler record) | 1,335 (verdict summary) | 15–31 |

Every document is a single screen. There is no multi-page artifact anywhere: no
six-page autopsy protocol, no eleven-page phone toll record, no forty-page court filing,
no photo log, no CAD printout. The file has no weight. A judge cannot feel it.

### The people are all the same kind of person

`book.persons` is flat. A patrol officer, a victim, a defendant, an unnamed witness, a
dead 2011 teenager, and a tow operator all get the same card shape, the same photo
treatment, and the same pin. There is no `role_class` (victim / witness / subject /
officer / attorney / medical / records / unnamed / deceased). The intake prompt extracts
names; the UI never triages them.

This is also why the board reads as an accusation wall: everyone on it looks like a
suspect because everyone is pinned the same way.

### The gaps are a list, not a triage

19 gaps on Delgado become 19 equal cards on Judgments and six sticky notes on the board.
No owner, no status, no "who can close this," no "this is a records pull vs a question
for the detective," no "checked, negative." A real gap list is assigned and worked. The
current list is a dump.

---

# Part 1 — The file doesn't feel like a file

## 1.1 Frame it as a working set, not the whole book

You cannot fake four thousand pages. You can stop claiming fourteen documents is the
whole file.

Do:

- Rename the Intake screen from **"The file"** to **"The murder book"**.
- Add a file inventory line: **"Working set: 14 of 212 catalogued pages · 6 binders ·
  reviewed 21 Nov 2026."** The other pages can be "not relevant to the current
  assignment," which is exactly how a cold-case review works.
- Give the folder a **page count**, a **binder count**, and a **last reviewed** date.
- Add **three long artifacts** per case that are real multi-page documents:
  - Delgado: the **autopsy protocol** (6 pages, body diagram, tox pending), the
    **phone toll record** for Webb (11 pages, 40 rows, mostly irrelevant), and the
    **CAD/incident log** (2 pages, 0712 call, units, times).
  - Screens: a **platform export** with 60 posts (most irrelevant), and a **podcast
    transcript** with timestamps and crosstalk.
  - Duck: a **federal court caption + proffer excerpt** (10 pages, case number, page
    numbers, exhibit stamp) and a **CPD incident report** (3 pages).
  - Harborlight: a **marina keypad audit** (8 pages of entries, one line matters) and a
    **guest photo memo** with a photo log.

The long documents do one job: they make the short ones feel selected. Selection is what
detectives do; a file where everything is short and relevant is a puzzle, not an
investigation.

## 1.2 Give every page document chrome

Every page of a real file carries the same furniture. Add it to the document viewer and
to the print/export path:

```
NYPD — HOMICIDE DIVISION
SUPPLEMENTAL INVESTIGATION REPORT
Case: MB-2019-1014            Complaint: 2019-1014-0712
Offense: Homicide (PL 125.25) Date of incident: 13 OCT 2019, approx. 2300 hrs
Prepared: 14 OCT 2019, 1042 hrs
Prepared by: Det. R. Osei #4412, Homicide Squad, 68th Precinct
```

Footer on every page:

```
MB-2019-1014 · Doc 011 · Page 1 of 2 · LAW ENFORCEMENT SENSITIVE
```

Add, per document type:

- **Report:** report number, date/time prepared, author, rank, badge, unit, "Continued
  on page 2," signature block, "Received" stamp with date/time and clerk initials.
- **Statement:** location, date/time started/ended, interviewer, rights advisement line,
  attorney present (yes/no), interpreter (yes/no), "This statement was read back,"
  subject signature, detective signature, page number.
- **Record:** issuer letterhead, account/job/reference number, "CERTIFIED COPY" or
  "TRUE COPY," page x of y, records custodian signature.
- **Ledger/property:** property clerk invoice number, item number, date/time collected,
  collecting officer, location recovered, seal number, disposition.
- **Court filing:** court caption, case number, "GOVERNMENT'S EXHIBIT," page numbers,
  redaction bars, certificate of service.
- **Photo log:** frame number, date/time, photographer, location, description, "1 of 24."

The viewer should show a page, not a `<pre>` blob. Paginate at ~40 lines, number the
pages, and keep the footer fixed. When a quote is opened, **highlight the span** and
scroll to it. A quote without a page is a citation; a quote with a page and a highlight
is evidence.

## 1.3 Chain of custody is the missing verb

The evidence ledger is currently a numbered list. It says what was collected, not who
collected it, when, where, under what seal, or where it went. That is the difference
between a list of objects and a chain a court will accept.

Add a **Chain** panel to every evidence item:

| Field | Example |
|---|---|
| Item | 7 |
| Description | One (1) spent shell casing, brass, 9mm |
| Recovered | 14 OCT 2019, 0915 hrs |
| Location | Office floor, near desk, marker 7 |
| Collecting officer | Ofc. T. Brennan #2218 |
| Seal | S-4417 |
| Transferred to | Property Clerk, 14 OCT 2019, 1132 hrs |
| Custodian | P. Nunez, Property Clerk |
| Disposition | Submitted to lab, 15 OCT 2019 |
| Lab request | F-2019-1044 |

Then make the missing casing a **chain** finding, not a count finding:

- Scene report: "Two shell casings were observed..."
- Photo log: markers 7 and 8, both "spent casing."
- Ledger: item 7 only.
- Chain: item 7 sealed and transferred. No item 8. No seal. No entry.
- The finding writes itself: **"Marker 8 appears in the photo log; no property receipt
  exists. The second casing is not merely unlisted — it never entered custody."**

That is a real detective's sentence, and it makes the second catch stronger than the
current "mentioned vs logged" gap.

## 1.4 Rewrite the statements to sound like people

The statements are too tidy, too grammatical, and too responsive. Real interview
transcripts hedge, restart, correct themselves, answer a different question, and contain
long irrelevant passages. The interviewer interrupts and follows up.

Current Webb:

> Q: Where were you Sunday night, October 13?
> A: Home. I was home alone Sunday night. I never left the house. I watched television
> and went to bed early.

Real Webb:

> Q: Where were you Sunday night, October 13?
> A: At the house. I mean — I was home. I didn't go anywhere. I was home all night.
>
> Q: Anyone with you?
> A: No. My wife was— she was away. So just me.
>
> Q: Did you drive anywhere that weekend?
> A: I couldn't. The car was in the shop. Transmission. It was on the lift from Monday
> on.
>
> Q: Monday the seventh?
> A: I don't— yeah. Monday. It was there all week.
>
> Q: You're sure about that.
> A: That's what I said.

The contradiction is still exact. The quote check still works. But now the person
sounds like a person, and the interviewer sounds like an interviewer. Add:

- Rights advisement and whether the subject waived.
- Start/end times and breaks.
- "Subject was shown the tow record" (or not shown — that matters).
- Corrections initialed in the margin: "Subject corrected 'Friday' to 'Monday' at 10:42."
- One irrelevant aside per statement (the dog, the weather, a sick relative).
- One unanswered question the detective never went back to. Real files are full of them.

The same applies to the reports. "At 0712 hours I responded to a call of a person down"
is good. "The caller's statement was taken separately" is a summary, not a report line.
Replace with "Caller transported to the 68th Precinct; statement taken by Det. Osei at
1040 hrs (see Doc 005)." Cross-references are realism.

## 1.5 Add negative results

Real investigations are mostly things that did not work. Add one negative result per
case, and show it on the Clock or the gap list as **CHECKED — NEGATIVE**:

- Delgado: "Diner camera, Fifth Avenue: footage overwritten on 30-day retention.
  Requested 15 OCT 2019; earliest available 12 SEP 2019. No footage."
- Screens: "Deleted Instagram story, 1:02 a.m.: no archive, no screen capture, account
  private. Platform preservation request returned 'no content.'"
- Harborlight: "Marina camera 3: offline 22:40–01:10 for scheduled maintenance. No
  footage."
- Duck: "POD camera at 116 E. Oak: frame rate 1 fps, no usable identification. Masked
  subjects. No face match."

These are not failures of the product. They are the product being honest about the file,
and they make the successful pulls feel earned. A board where every lead works is a
tutorial.

## 1.6 Add noise

Add 20–30% irrelevant documents. Not fake-looking filler: real adjacent paperwork that a
detective would have to read and discard.

Delgado candidates:

- A 2017 burglary report at the same address (different owner, unrelated).
- The shop's 2018 business license renewal.
- A supplier's demand letter for $3,200 (motive texture, not a contradiction).
- A parking ticket on Webb's street, dated 12 OCT 2019 (wrong day, useful red herring).
- A neighbor's noise complaint from 2016.
- A vacation photo from Rosa's phone, submitted by the family.
- A prior insurance claim for a stolen catalytic converter.

Screens candidates:

- A fan account's tribute post.
- A different Brooklyn drill artist's release announcement.
- A since-deleted post that turns out to be about a different shooting.
- A local blog's unrelated "crime is up" piece.

Realism is not more evidence. It is **the discipline of ignoring most of it**, which is
exactly what the product claims to do. Noise also gives the quote check something real
to reject, and gives the Eval a place to show precision.

## 1.7 The registry is a developer table

`renderRegistry()` renders: Doc / Title / Type / Date / Author / "view". `doc01` is a
filename, not a document control number. There is no page count, no tab, no copy number.

Replace with a murder-book index:

| Tab | Doc | Description | Date | Author | Pages | Copy |
|---|---|---|---|---|---|---|
| 01 Reports | 001 | Scene report, 1140 Fifth Ave | 14 OCT 2019 | Ofc. T. Brennan #2218 | 1 of 1 | File |
| 02 Statements | 003 | Marcus Webb, first statement | 15 OCT 2019 | Det. R. Osei #4412 | 2 of 2 | File |
| 03 Records | 011 | Tow yard record, Webb vehicle | 11 OCT 2019 | Kowalski Towing | 1 of 1 | Certified |
| 04 Evidence | 013 | Property clerk ledger | 14 OCT 2019 | P. Nunez | 3 of 3 | File |
| 05 Photos | 024 | Photo log, office and shop | 14 OCT 2019 | CSI M. Alvarez | 2 of 2 | File |

Group rows by binder tab, collapse by default, and show a tab count. The index becomes a
map of the book instead of a database table. The "view" column becomes a page icon or a
"Open" action; a real index does not say "view."

## 1.8 Different eras need different paper

Every document currently renders in the same Courier `<pre>` with the same cream page.
But the four cases are four different artifacts:

- **Delgado 2019:** typed reports, carbon-copy forms, handwritten corrections, fax
  headers, staple holes, a manila folder. Typewriter font, uneven margins.
- **Screens 2025:** platform screenshots, phone captures, Reddit printouts, a podcast
  transcript with timecodes, a plate-cam still with grain. Sans-serif, UI chrome,
  timestamps, usernames, engagement counts.
- **Harborlight 2016:** marina logbooks, keypad exports, a guest photo memo, a local
  newspaper clipping. Mixed handwriting and dot-matrix.
- **Duck 2020:** federal court PDFs with caption and page numbers, CPD reports, news
  clippings, POD/LPR stills. Legal typography, exhibit stamps, redactions.

Give each case a **document skin**: font, paper color, header rule, footer format, and
one or two physical defects (staple, punch holes, fold line, redaction). This is a CSS
and template job, not a model job. It will do more for "real" than another case.

The Screens case especially should not render a social post as plain text. A post card
with handle, avatar, timestamp, caption, "Comments off," "Edited," or "Deleted" reads
like a capture. A generic platform ("CHIRP" or "PUBLIC POST") avoids trademark issues.
The deleted story should be a **placeholder card**: "Posted 1:02 a.m. · Deleted 1:19
a.m. · No archive · 0 captures." That absence is the case.

## 1.9 The people problem (photos, roles, and the board roster)

Three separate problems:

**A. Everyone is pinned.** The board is not a cast list. Add a `role_class` and a board
eligibility rule:

| Class | Board? | Card type |
|---|---|---|
| Victim | Yes | Family snapshot, age, next of kin notified |
| Subject / defendant | Yes | Booking photo only if arrested; otherwise DMV/employee/social capture with source label |
| Key witness | Yes, if they carry a claim | Snapshot or employee photo; "witness" tab |
| Officer / ME / attorney | No | File personnel list; open from the document, not the cork |
| Unnamed / deceased non-witness | No | "Unidentified persons" appendix, not a card |
| Records custodian / tow operator | No | A record card, not a person card |

**B. The photos are all the same kind of photo.** A witness, a patrol officer, and a
suspect should not all look like a casting headshot. Use different treatments:

- Victim: family snapshot, slightly crooked, date printed on the border.
- Arrested subject: booking photo, height chart, blue background, case number plate.
- Witness: employee badge or DMV-style photo, flat lighting.
- Unidentified: silhouette or "NO PHOTO IN FILE."
- Officer: department portrait or no photo at all.

**C. Honesty vs. fiction.** The current caption "Illustrative portrait · not evidence"
under every face is honest but breaks the frame and adds visual noise. Consolidate:

- Put an "About this file" note in the footer/System drawer: **"Faces in the fictional
  cases are AI-generated stand-ins. No real person is depicted. The Duck file uses no
  generated faces."**
- Put a small corner tag on each generated photo: **"AI likeness."** It is a sticker,
  not a caption, and it preserves the disclosure.
- Remove the repeated `portrait-caption` line from the card. One global disclosure and
  one small tag is enough.
- Never attach a generated face to a real person in the Duck case. The current
  `photos-data.js` correctly has no Duck entries; keep it that way.

## 1.10 The case folder is decoration, and Door 2 is bolted on

The folder header is good but incomplete. A real folder cover has:

- Agency and bureau: **NYPD / Detective Bureau / Homicide Squad**
- Case number and complaint number
- Offense and statute
- Date of incident and date opened
- Assigned detective and squad
- Victim name, age, last known address
- Status: **OPEN / COLD / CLEARED BY ARREST / EXCEPTIONAL CLEARANCE**
- Page count and binder count
- "WORKING COPY — NOT EVIDENCE" or "PROPERTY OF HOMICIDE"

Add those fields, and add the **"WORKING COPY"** stamp. It is a small thing that signals
the board is an internal artifact, not a claim.

Door 2 is a different product workflow sitting inside an active homicide file. On the
Intake screen, under the victim's registry, there is a dashed box that asks for a name,
DOB, and state to run a public-records census. That is an **intake/identification**
workflow, not a case-file screen. Move it to:

- a **"Start a new file"** action from the case index, or
- a **"Records request"** modal opened from the squad room, or
- a separate **"Unidentified / next of kin"** tab.

Then label the demo fixtures once — "SIMULATED CENSUS" on the panel — instead of
writing "(simulation fixture)" into every source name. One clear label, not twenty
immersion breaks.

---

# Part 2 — The board doesn't behave like a board

## 2.1 Every citation is yarn, so the yarn means nothing

`drawYarn()` draws a pale `yarn-related` curve for every person–document link returned
by `documentedLinks()`. Delgado has 30 claims across 14 documents and 9 people; the
board is a cat's cradle of "this person is mentioned in this document." That is not a
relationship. It is a bibliography.

Change the semantics:

- **Red string** = a contradiction between two sources (keep).
- **Labeled string** = a typed relationship between two people or a person and an
  object: money, work, family, phone, vehicle, location. Only draw it when a claim
  supports the type.
- **No string** for mere citation. Put the source doc IDs in the card footer:
  `doc03 · doc04 · doc11`.

A board with eight meaningful strings reads as an investigation. A board with eighty
pale strings reads as a graph visualization.

## 2.2 Label the string

Real boards put a paper tag on the string, not a legend. Add a small tag at the curve
midpoint:

- `CAR IN SHOP ALL WEEK` (Webb → tow record)
- `TOWED 11 OCT` (tow record → Webb residence)
- `"STUDIO ALL NIGHT"` (Reed post → plate cam)
- `11:05 PM · BQE` (plate cam → timeline)

The label is the claim. It also solves the "which string do I click" problem without a
legend. Keep the legend as a taped index card, but make it secondary.

## 2.3 The document pins are bibliographic cards

`pinCard("docslip")` shows doc ID, type, title, date, author. That is registry metadata.
A detective pins the **page** that matters, with the line highlighted.

Replace document pins with **page pulls**:

- A cropped page, 3–5 lines of context, the relevant sentence highlighted in yellow.
- A Bates footer: `MB-2019-1014-011 · p.1`.
- A tab: `STATEMENT` / `RECORD` / `LAB`.
- A handwritten margin note: `contradicts Doc 3` or `verify`.
- The source quote's doc ID in the corner, not the title.

This makes the board look like it was assembled from paper, not generated from JSON.
It also makes the yarn endpoints meaningful: string goes from a person card to a page
pull, not to a bibliographic label.

## 2.4 The board needs mixed media

A corkboard with only index cards is a mood board. A murder board has:

- **A floor plan** of the shop: body position, desk, door, bay doors, camera cone,
  evidence markers 1–22, scale bar, "NOT TO SCALE." This can be an SVG generated from
  doc01 and the ledger. It is the single best visual addition for Delgado.
- **A route map**: tow yard → Webb residence → shop, with times, for the car thread.
- **A phone-record strip**: 12 calls, one highlighted, with `23:58` and `00:07` in the
  margin. For Harborlight, this is the case.
- **A news clipping**: the Screens case's initial article, with a red circle around
  "no suspects identified."
- **A photo log**: 24 frames, 6 pinned, 18 "not printed."
- **An evidence bag tag** for item 7, with seal number and initials.
- **A court caption page** for Duck, with the case number and "EXHIBIT."

You do not need all of these in every case. One per case, plus the floor plan for
Delgado, changes the board from "cards on cork" to "a working surface."

## 2.5 The board is too clean and too uniform

Every card is cream, every pin is the same red circle, every tilt is one of five
values, every shadow is the same. Real boards are messy in a specific way:

- Pin colors vary (red, blue, yellow, black) and some are pushed in at an angle.
- Some cards are taped, not pinned; tape is yellowed and torn.
- Photo corners, not just pins, on photos.
- A coffee ring on one document; a folded corner on another.
- Punch holes on filed pages; staple marks on reports.
- A redaction bar on one statement (informant name, phone number).
- A "COPY" stamp, a "RECEIVED" stamp, a "NOT EVIDENCE" stamp.
- Handwritten initials and a date on the back of a photo.
- One card upside down or facing away, because someone tossed it there.

Seed the variation deterministically by item ID, not random per render, so the board is
stable across reloads. The current `tiltFor()` is a good start; widen the range and add
2–3 defect variants per card type.

## 2.6 Stamps, not pills

The alibi rating is rendered as a rounded chip (`.alibi-chip`). It reads as a UI badge,
not a stamp. Replace with a rubber-stamp treatment:

- `CONTRADICTED` in red, rotated -4°, uneven ink, slightly off the card edge.
- `UNCORROBORATED` in amber, rotated 2°.
- `CORROBORATED` in green, rotated -1°.
- `NOT APPLICABLE` in gray for the dead or those who made no claim.

Use a mask/noise texture or `mix-blend-mode: multiply` for ink coverage. Keep the text
selectable and accessible. A stamp is one of the cheapest realism wins on the board.

Also fix the semantics: a dead defendant or a person who made no claim should not be
rated `UNCORROBORATED`. `EVAL.md` already flags Ezell Rawls; the UI should show `NOT
APPLICABLE — no claim in file`, not a rating.

## 2.7 The board headline is still an accusation

The largest text on the corkboard is **"WHO DID IT"** (`renderBoard`), and the case
question modal asks **"Who killed Raymond Delgado?"** The product's entire ethical
position is that it does not answer that. Change both:

- Board headline: **"WHAT THE FILE CONTRADICTS"** (or **"WHAT THE FILE SUPPORTS"**).
- Subline: victim, death window, case number.
- Case question modal: **"What remains unresolved in this file?"** with the death window
  and the standing line.

Keep the giant question mark if you like the visual. Change the words. This is a
five-minute fix with a large perceptual effect, and it is already in `REVIEW.md` — it
belongs in the realism pass too because it is the board's central lie.

## 2.8 The board should show its own provenance

Add a small plate on the cork frame:

```
MB-2019-1014 · HOMICIDE · WORKING BOARD
NOT EVIDENCE · DO NOT REMOVE FROM SQUAD ROOM
```

This does two things: it makes the board an artifact, and it prevents the "did this
board solve it?" confusion. On the Duck case, change the folder stamp from `SOLVED 2024`
to **`CONVICTED 2024 — STATE CASE`** and add a provenance line: "Rebuilt from public
court record. This board did not decide it." The current stamp reads as a product claim.

## 2.9 The board has no pre-run state

On load, `DOMContentLoaded` auto-runs the cached case. The judge never sees the file
before the squad works it. The board is already full, the room already busy, and the
"Work the Case" button is moot. That is the difference between "watch it work" and
"look at a finished demo."

Choose one:

- **Option A (recommended):** open on the folder and an empty corkboard with the victim
  photo, the case number, and "No pins yet. Work the file." The saved run is a button:
  `Open saved run · 21 Nov, 16:14`. The live run is the primary action.
- **Option B:** auto-load the results, but keep the room feed empty and label the board
  "Saved run — 21 Nov 16:14." Then "Work the file" replays the room with recorded
  timing. The board can be pre-populated; the room should not be.

Either way, the first ten seconds should show the file, not the conclusion.

## 2.10 Gap notes need owners and status

19 gaps on Delgado is not a board; it is an inbox. Group them:

- **Records pulls** (who can close it): plate record, tow invoice, phone toll, dealership
  paper.
- **Lab / CSI**: second casing, DNA on the door handle, latent prints on the drawer.
- **Interview questions**: Whitfield's third statement, Webb's timeline, Rosa's
  knowledge of the debt.
- **Checked — negative**: diner camera, shop DVR (no drives).
- **Unassigned**: everything the file mentions but nobody owns.

Each note gets a checkbox, an owner chair, and a one-line "what would close it." Add a
`Copy tomorrow's list` action. This is already in `REVIEW.md`; the realism angle is that
real gap lists are assigned, not displayed.

---

# Part 3 — The squad room doesn't feel like a room

## 3.1 The replay timestamps are the biggest tell

Fix this first. Concretely:

- Extend the cache format with per-step `started_at`, `ended_at`, `duration_ms`,
  `model`, `tokens_in`, `tokens_out`, `retries`, `status`.
- In replay, render each chat line with `T+00:04:12` from the **recorded** start, not
  `new Date()`. Show the wall-clock time in a tooltip or a secondary line.
- Show the recorded run duration in the header: **"Recorded 16:14–16:22Z · 7m 32s ·
  11/11 steps · 4 rejected."**
- Add a **`REPLAY ×N`** badge when the replay compresses time. Honest compression reads
  as a recording; silent compression reads as a fake.
- Stop the run clock at the recorded duration, not at the elapsed replay time.

This is a small data change and a medium UI change, and it removes the strongest signal
that the room is scripted. Do it before any visual polish.

## 3.2 Give the agents different voices

Right now every agent speaks in the same first-person, helpful, complete-sentence voice:
"I logged 14 documents...", "I pinned 7 people...", "I reconciled 22 ledger items...".
That is a product tour, not a squad room.

Write per-chair registers:

- **Sgt. Voss (custody):** clipped, procedural, no adjectives. "14 received. 2 copies,
  1 unreadable, 1 unsealed. Log attached."
- **Dr. Halden (ME):** precise, clinical, refuses to speculate. "Cause: two gunshot
  wounds to the chest. Manner: homicide. Window: 2100–0000. I will not narrow it
  further without tox."
- **Ibarra (analyst):** time-first. "23:05, BQE at Atlantic. 23:42, post. Those cannot
  both be true."
- **Quill (digital):** device-first, skeptical of screenshots. "The still is a
  re-compress. Plate is unreadable past 417. Pull the source file or it is not a
  record."
- **Vane (cross-examiner):** the only one allowed a little theater. "The record says the
  car was towed Friday. He says it was on the lift all week. One of those is wrong."
- **Mercer (interviewer):** question-first. "He changed the visit in statement three.
  Ask him what time he used his key, not whether he was there."
- **Kessler (prosecutor):** risk-first. "This lead says 'confront.' Strike it. We do not
  put a person in the brief."
- **Rook (lead):** short, decisive, one action. "Tomorrow: the tow invoice, the diner
  camera, and Whitfield's key. In that order."

The names and chairs already exist. The voice is the missing layer.

## 3.3 Handoffs should be payloads, not prose

A real multi-agent handoff is a data transfer. The current handoff line is a sentence:
"Voss → Ibarra · 14 documents, 9 persons..." (paraphrased). Make it a receipt:

```
CUSTODY → INTAKE
14 docs · 10,537 chars · 9 persons · 30 claims · 2 duplicate · 1 unreadable
sha256 4f2a…c19 · 0.42s
[open payload]
```

Expanding shows the JSON keys and counts, not the full text. This is the "real system"
feel: the room is passing structured work, and you can inspect it. It also gives the
"is the chat scripted?" question a concrete answer: the handoffs are runner-generated
payload receipts, and the prose reports are composed from the same output.

## 3.4 Move the model names to a system layer

The fiction currently leaks the implementation everywhere:

- Header model line: `ARGON judges · CARBON builds · HYDROGEN holds the world · NEON
  works the machines`.
- Chair chips: `CUSTODY · CARBON`.
- Chat role: `Cross-Examiner · ARGON`.
- Brief: `Prepared by the Lead Detective chair (Argon)`.
- Header: `Live key`, `Replay cached run`, proof links, `Built today at Gemini 4 NYC`.

This is the **diegetic break** principle: keep two layers.

**In-world layer (what the detective sees):**

- Roster: rank, name, unit, assignment, status, elapsed.
- Chat role: `Det. Vane · Homicide / Cross-Examination`.
- Brief: `Prepared by: Det. Vane, Homicide. Reviewed by: ADA Kessler.`

**System layer (what the engineer/judge inspects):**

- A `System` drawer or footer: run ID, models per step, temperature, tokens, latency,
  retries, drops, verifier version, cache hash.
- The hackathon proof links and "built at" line live here, under `About this build`.
- A small `4 models · 10 assignments` badge in the header can open the drawer.

You keep every proof point. You stop wrapping the product in its own submission form.
This is the highest-leverage realism change after the clock, because it affects every
screen at once.

## 3.5 The header is a submission page

Specifically:

- `Public repo · The evaluation · Demo script · Built today at Gemini 4 NYC` — move to
  `About this build`.
- `Live key: paste to run live` — move to `System → Live run`. Never show an API-key
  field on a public demo. A judge seeing it thinks "dev build"; a security reviewer
  thinks "key handling."
- `Replay cached run` — rename `Saved run` and show the run timestamp/ID.
- `Quote check dropped: 4` — keep the number, but make it a clickable receipt:
  `4 submissions rejected · review`. Move the engineering phrase to the System layer;
  in-world, call it "rejected for want of a source."

## 3.6 The roster should look like a shift board

The current squad strip is ten equal chips with an agent surname, chair name, model,
and "posted" count. It reads as a dashboard. Make it a **shift roster**:

```
HOMICIDE SQUAD · SHIFT 3 · 21 NOV 2026
Lt. Voss        Squad Sergeant      ON DESK   00:00   —
Dr. Halden      Medical Examiner    REVIEWING 00:42   3 findings
I. Ibarra       Crime Analyst       DONE      01:18   23 events
...
```

Add rank, unit, status, elapsed, and posted count. Statuses: `ON DESK`, `REVIEWING`,
`WAITING`, `DONE`, `BLOCKED`. The "blocked" state is important; a real room has people
waiting on records. It also gives the runner a place to show a failed step without a
red chip that looks like an error toast.

## 3.7 "First Officer" is a Navy title

This is a small thing that a police advisor will catch instantly. "First Officer" is a
ship's officer; the patrol officer first on scene is the **responding officer**, and the
squad supervisor is the **squad sergeant** or **case manager**. Rename the chair:

- `FIRST OFFICER` → `SQUAD SERGEANT` or `CASE MANAGER` (the person who logs everything
  and owns custody).
- Keep the agent name (Voss) and the custody mandate.

While renaming, tighten the other titles to real units:

| Current | Real-world label |
|---|---|
| First Officer | Squad Sergeant / Case Manager |
| Records | Records & Identification (Records Unit) |
| Coroner | Medical Examiner (OCME in New York) |
| CSI | Crime Scene Unit (CSU) |
| Intake | Case Intake / Indexing |
| Analyst | Crime Analyst |
| Digital | Digital Forensics |
| Cross-Examiner | Case Agent / Cross-Examination |
| Interviewer | Interview Team |
| Prosecutor | Assistant District Attorney (ADA) |
| Lead Detective | Case Detective / Lead |

You can keep the literary chair names in the pitch and the tab labels; use the real
titles in the roster, chat roles, and brief. That dual naming is how the product can be
both charming and credible.

## 3.8 The chat should be able to say "not in the file"

`answerQuestion` falls back to deterministic `personReply` / `boardAnswer` / `statusReply`
when there is no live key. Those can answer confidently from partial data. Add an
explicit, common response:

> "That is not in the file I have. I can give you what the file supports, or name the
> record that would answer it."

And when the question names a person with no alibi, the current code already says "I
won't fill that gap with a guess." That is the right instinct. Make it the house style:
**the room refuses to answer outside the file.** A system that says "I don't know" is
more credible than one that always has a paragraph.

## 3.9 The room needs a header and a shift

Add a thin room header above the feed:

```
SQUAD ROOM · CASE MB-2019-1014 · SHIFT 3 · 21 NOV 2026 14:02
11 assignments · 4 models · 14 documents · 1 saved run
```

This is the "place" the chat lives in. Right now the feed floats between the case folder
and the tabs with a developer sentence ("Step reports summarize chair outputs..."). The
header gives it a location and a time, and lets you delete the developer sentence.

## 3.10 The tabs are numbered like a guided tour

`1 Intake · 2 The Board · 3 The Clock · 4 Judgments · 5 The Brief · 6 The Eval` is demo
choreography, not product navigation. Real tools do not number their tabs. Remove the
numbers, or move the numbered sequence into a `Judge mode` overlay. Rename `The Eval` to
`Validation` and treat it as an appendix/model card, not a primary tab. The demo script
can still walk 1→6; the UI should not advertise that it is a walkthrough.

---

# Part 4 — The system doesn't show its work

## 4.1 Add a run receipt

A real AI pipeline has a receipt. Add a collapsible `Run receipt` in the System drawer
and a one-line summary in the header:

```
RUN 2026-11-21T16:14:25Z · delgado-2019 · 7m 32s · 11/11 steps
models: argon, carbon, hydrogen, neon · temp 0.2
tokens: 48,210 in / 12,904 out · retries: 1
quote check: 4 rejected / 214 verified · verifier 1.3
cache sha256: 4f2a…c19
```

This is the answer to "is this real?" It also makes the eval's claims auditable. The
cache currently stores only `created_at`, `outputs`, `dropped`, and a `run_log` that
is two lines for Delgado; add the rest at run time.

## 4.2 Give every accepted finding a verification receipt

Already in `REVIEW.md`, but it belongs in the realism pass because it is the product's
trust moment. On every quote card and contradiction:

```
VERIFIED · doc03 · chars 1,204–1,318 · 114 chars · exact after whitespace/case normalization
```

Clicking opens the document at the highlighted span. On every rejected finding, a
rejection slip:

```
REJECTED · Cross-Examiner · "Webb's car was at the shop all week"
cited doc11 · no verbatim match · closest: "Vehicle condition: not running"
reason: quote not in cited document
```

This turns the drop count from a brag into an audit trail. It also gives the board a
"receipts" texture that matches the paper theme.

## 4.3 Show failures and retries

The runner already retries once and turns a chair red. The UI shows a red chair and a
chat line, but no detail, no retry action, no duration. Add:

- `Step failed · schema error · retried once · 00:42` in the chair.
- A `Retry step` button on the failed chair.
- The raw error in the System drawer, not the chat.
- A `Run completed with 1 failed step` banner that persists on the Brief.

A system that never shows a failure is a demo. A system that shows a failure, a retry,
and a partial result is a tool.

## 4.4 Add a run log drawer

Every log line the runner writes (`fallback`, `quote check dropped`, `Lead score
corrected`) should be visible, timestamped, and clickable:

```
16:18:04  cross_examiner  2 findings rejected  [open]
16:19:11  lead_detective  score corrected 100 → 80  [open]
16:20:02  analyst         fallback: carbon covered hydrogen  [open]
```

This is the real "agentic system" surface. It also gives the eval's "one Harborlight
lead was corrected in the open" claim a place to live in the product.

## 4.5 Make the replay/receipt visible, not hidden

The header currently shows the saved time in small text. Make the mode
a first-class badge:

- `SAVED RUN · 21 NOV 16:14Z · 7m 32s`
- `LIVE · started 14:02:11 · 3/11 steps`
- `REPLAY ×N · recorded 7m 32s compressed to seconds`

A judge should never have to guess whether they are watching a live run or a recording.
The current honesty in `DEMO_SCRIPT.md` is good; the UI should match it.

## 4.6 Export a packet, not just a printout

`window.print()` prints the Brief only. A real case tool exports a packet:

1. Cover sheet (case number, victim, date, prepared by, classification).
2. Index of documents with page counts.
3. Findings and ratings.
4. Contradictions with both quotes and verification receipts.
5. Alibi matrix.
6. Gap list with owners.
7. Leads with arithmetic.
8. Brief.
9. Run receipt and rejection log.
10. Page numbers and "LAW ENFORCEMENT SENSITIVE" footer on every page.

This is the deliverable a detective would carry into a squad meeting. It also gives the
demo a physical artifact to hold up. The print stylesheet already exists; extend it to a
packet with CSS page breaks and counters.

## 4.7 Add a status bar

A slim footer:

```
LOCAL · SAVED RUN · 14 docs · 10,537 chars · 212 catalogued pages · last run 21 NOV 16:14
Fictional training file · faces are AI stand-ins · not a real case
```

This is where the disclaimers belong: one place, small type, always available. It
replaces the repeated "illustrative" captions and the header proof links, and it makes
the app feel like an installed tool rather than a web page.

---

# Part 5 — The copy deck

These exact replacements do a lot of work. Hand this table to Codex.

| Where | Current | Replace with |
|---|---|---|
| Header | `Public repo · The evaluation · Demo script · Built today at Gemini 4 NYC` | Move to `About this build` drawer |
| Header | `Live key: paste to run live` | Remove from public header; `System → Live run` |
| Header | `Replay cached run` | `Saved run · 21 Nov 16:14Z` |
| Header chip | `Quote check dropped: 4` | `4 submissions rejected · review` |
| Models line | `ARGON judges · CARBON builds · HYDROGEN holds the world · NEON works the machines` | Move to System drawer; header badge `4 models · 10 assignments` |
| Intake h2 | `The file` | `The murder book` |
| Tab | `4 Judgments` | `4 Findings` (or `The read`) |
| Tab | `6 The Eval` | `6 Validation` (appendix) |
| Board headline | `WHO DID IT` | `WHAT THE FILE CONTRADICTS` |
| Case question | `Who killed Raymond Delgado?` | `What remains unresolved in this file?` |
| Board note | `Portraits are illustrative, not evidence.` | Remove; use footer disclosure + `AI likeness` corner tag |
| Photo caption | `Illustrative portrait · not evidence` | `AI likeness` corner tag only |
| Folder stamp (Duck) | `SOLVED 2024` | `CONVICTED 2024 — STATE CASE` |
| Brief head | `Prepared by the Lead Detective chair (Argon)` | `Prepared by: Det. Vane, Homicide · Reviewed by: ADA Kessler` |
| Brief footer | (none) | `Case MB-2019-1014 · Page 1 of 2 · LAW ENFORCEMENT SENSITIVE` |
| Chat role | `Cross-Examiner · ARGON` | `Det. Vane · Homicide / Cross-Examination` |
| Chair | `FIRST OFFICER` | `SQUAD SERGEANT` |
| Chair | `DIGITAL` | `DIGITAL FORENSICS` |
| Feed head | `Step reports summarize chair outputs. Live handoffs pass runner inputs; replay handoffs are rebuilt from saved findings.` | `SQUAD ROOM · CASE MB-2019-1014 · SHIFT 3` |
| Chat placeholder | `Ask the Lead Detective what’s happening, or ask about a finding…` | `Message the room…` |
| Send button | `Send` | `Post` |
| Cache label | `Ran today, <time> (saved run)` | `SAVED RUN · 21 NOV 16:14Z · 7m 32s` |
| Door 2 | `Door 2: a name and a photo` | `Records request: identify a name` |
| Door 2 note | `(simulation fixture)` repeated per source | One `SIMULATED CENSUS` panel label |
| Case title | `The Delgado File — fictional demo case, written for Gemini 4 NYC` | `The Delgado File` + `FICTIONAL TRAINING FILE` stamp |
| Header tagline | `It sorts the file. It judges the file. The detective does the detecting.` | Keep, but set as an engraved plate / About line, not marketing copy |

---

# Part 6 — Build order, by impact per hour

## P0 — do first (a focused afternoon)

1. **Replay time truth.** Add per-step timestamps/durations to the cache; render
   `T+mm:ss`, recorded duration, `REPLAY ×N`. Stop using `new Date()` for replay
   messages. Stop the run clock at the recorded duration. *(~2–3 h)*
2. **System drawer.** Move the key field, proof links, models line, cache checkbox,
   "built today" line, and all engineering labels into a `System / About this build`
   panel. Add the status bar with disclaimers. *(~1–2 h)*
3. **Document chrome.** Page template with case number, report number, author/badge,
   page x of y, footer, signature/received blocks; paginate the viewer at ~40 lines;
   highlight the quoted span. *(~3–4 h)*
4. **Board semantics.** Remove citation yarn; keep string for contradictions and typed
   relationships; add string labels; change the headline; add the board plate. *(~2–3 h)*
5. **Roster triage.** Add `role_class`; stop pinning officers, unnamed persons, and
   deceased non-witnesses; add the "file personnel" list; unify the photo disclosure.
   *(~2–3 h)*
6. **Stamps and physical variety.** Alibi stamps, pin/tape/photo-corner variety, paper
   defects seeded by ID, redaction bars on one doc. *(~2 h)*

## P1 — the same day if there is time

7. **Chain of custody + ledger reconciliation.** Property receipt fields, transfer log,
   seal numbers; the marker-8 finding. *(~3–4 h)*
8. **Rejection ledger + verification receipts.** Store rejected findings, render slips
   and offsets. *(~2–3 h)*
9. **One visceral artifact + one negative result per case.** CAD/911 (Delgado), deleted
   story (Screens), court caption (Duck), offline camera (Harborlight). *(~3–4 h)*
10. **Brief as a real memo.** TO/FROM/DATE/RE, classification, page numbers, signature,
    distribution list; separate system footer. *(~1–2 h)*
11. **Roster strip + handoff payloads.** Rank/unit/status/elapsed; payload receipts.
    *(~2–3 h)*
12. **Floor plan + route map.** SVG from doc01/ledger; evidence markers; scale bar.
    *(~3–4 h)*

## P2 — only if the demo has room

13. Export packet (cover, index, findings, receipts, brief, run log).
14. Per-case era skins for documents (2019 typewriter, 2025 platform, 2020 court).
15. Empty pre-run board state and a proper "open saved run" action.
16. Retry chair + run log drawer.
17. Case index screen (status, victim, last worked) instead of a dropdown.
18. Judge mode (already in `REVIEW.md`; keep it separate from the realism pass).

---

# Part 7 — Do not add

- **Fake loading bars, fake "AI is thinking" delays, fake static, or fake scan noise.**
  Realism comes from accurate artifacts, not from pretending to compute.
- **More disclaimers inside the fiction.** One footer disclosure, one photo tag, one
  simulated-census label. Repeating "fictional" on every card makes it a demo.
- **More model branding in-world.** The models belong in the System drawer and the
  roster's small type, not in the brief signature or the chat role.
- **A guilt score, suspect ranking, or "solve" button.** The product's whole position is
  that it judges the file. Do not undermine it for a demo moment.
- **AI-generated faces for real people.** The Duck case must stay initials/silhouettes.
- **3D corkboard, sound effects, or physics.** The board is a working surface, not a toy.
- **More cards without triage.** Adding documents to the board without roles, filters,
  and owners makes it less real, not more.
- **A second visual language.** Do not add another theme. Fix the dark-chrome/paper
  relationship instead: paper is an object inside the workspace, not a full-screen mode.

---

# Appendix A — Document templates Codex can copy

## A.1 Report header and footer

```
NYPD — HOMICIDE DIVISION
SUPPLEMENTAL INVESTIGATION REPORT

Case: MB-2019-1014                  Complaint: 2019-1014-0712
Offense: Homicide (PL 125.25)       Date of incident: 13 OCT 2019, approx. 2300 hrs
Prepared: 14 OCT 2019, 1042 hrs
Prepared by: Det. R. Osei #4412, Homicide Squad, 68th Precinct
Assisted by: Det. S. Park #3901, Cold Case Review

[body]

Received: 14 OCT 2019, 1105 hrs     By: P. Nunez, Property Clerk
Signature: ______________________________

MB-2019-1014 · Doc 011 · Page 1 of 2 · LAW ENFORCEMENT SENSITIVE
```

## A.2 Property receipt fields

```
PROPERTY CLERK INVOICE
Invoice: PC-2019-1044-07
Case: MB-2019-1014
Item: 7
Description: One (1) spent shell casing, brass, 9mm
Recovered: 14 OCT 2019, 0915 hrs
Location: Office floor, near desk, evidence marker 7
Collecting officer: Ofc. T. Brennan #2218
Seal: S-4417
Transferred to: Property Clerk, 14 OCT 2019, 1132 hrs
Custodian: P. Nunez
Disposition: Submitted to lab, 15 OCT 2019
Lab request: F-2019-1044
```

## A.3 Statement header

```
STATEMENT OF MARCUS WEBB
Case: MB-2019-1014
Date: 15 OCT 2019
Location: 68th Precinct, Interview Room 2
Started: 1012 hrs    Ended: 1108 hrs
Interviewer: Det. R. Osei #4412
Present: Det. S. Park #3901
Rights advised: Yes, 1014 hrs. Waiver signed: Yes.
Attorney present: No. Interpreter: No.
Statement read back: Yes, 1106 hrs.
```

## A.4 Brief letterhead

```
MEMORANDUM
TO:      Squad Commander, Homicide
FROM:    Det. Vane, Homicide
DATE:    21 NOV 2026
RE:      Case MB-2019-1014 — Delgado, Raymond — case brief
CLASSIFICATION: LAW ENFORCEMENT SENSITIVE

[body]

Prepared by: Det. Vane, Homicide
Reviewed by: ADA Kessler, Kings County DA
Page 1 of 2
```

## A.5 Run receipt shape

```json
{
  "run_id": "2026-11-21T16:14:25Z-delgado-2019",
  "case_id": "delgado-2019",
  "started_at": "2026-11-21T16:14:25.045Z",
  "ended_at": "2026-11-21T16:21:57.112Z",
  "duration_ms": 452067,
  "steps": [
    {
      "id": "cross_examiner",
      "chair": "cross_examiner",
      "model": "gemini-4-argon",
      "started_at": "2026-11-21T16:18:02.114Z",
      "ended_at": "2026-11-21T16:18:44.902Z",
      "duration_ms": 42788,
      "tokens_in": 8214,
      "tokens_out": 1902,
      "retries": 0,
      "status": "ok",
      "dropped": 2
    }
  ],
  "totals": {
    "steps_ok": 11,
    "steps_failed": 0,
    "dropped": 4,
    "verified": 214,
    "tokens_in": 48210,
    "tokens_out": 12904
  },
  "verifier": "1.3",
  "cache_sha256": "4f2a…c19"
}
```

## A.6 Handoff payload line

```
CUSTODY → INTAKE
14 docs · 10,537 chars · 9 persons · 30 claims · 2 duplicates · 1 unreadable
sha256 4f2a…c19 · 0.42s · [open payload]
```

## A.7 Board string labels

```
CAR IN SHOP ALL WEEK
TOWED 11 OCT · 16:52
"STUDIO ALL NIGHT"
11:05 PM · BQE ATLANTIC
KEYPAD 23:58 · HER OWN CODE
00:07 · MASTER CODE
```

---

# Appendix B — What is already strong (protect it)

- The quote check is code, not a prompt. Keep it exactly as is.
- The runner recomputes lead scores and prints the arithmetic. Keep it.
- Every contradiction carries an innocent reading. Keep it.
- The alibi table rates the file, not the person. Keep it.
- The brief ends with the standing line. Keep it.
- The four cases have bibles and answer keys. Keep them.
- The evals include misses. Keep them.
- The replay cache survives a dead network. Keep it.
- The corkboard, pins, yarn, and string key are the best visual in the product. Keep the
  material language; change the semantics.
- The person drawer is the strongest screen in the app. Give it a real document reader
  and it becomes the product's centerpiece.

---

# Appendix C — Copy-paste prompt for Codex

Use this after reading the doc; it is scoped to P0 only.

```
Read REALISM.md in the repo. Make only the P0 changes, in this order, and do not
change the runner, the quote check, the scoring rubric, or any case data.

1. Replay time truth:
   - Extend the cache format with per-step started_at/ended_at/duration_ms/model/
     tokens/retries/status. If the existing cache lacks them, derive stable
     timestamps from created_at plus per-step order and label the run "recorded".
   - Render replay chat lines with T+mm:ss from the recorded start, not new Date().
   - Show recorded duration in the header; add a REPLAY ×N badge when compressed.
   - Stop the run clock at the recorded duration.

2. System drawer:
   - Move the live-key input, proof links, models line, cache checkbox, and
     "built today" line into a System / About this build panel.
   - Add a slim status bar with the disclaimers.
   - Rename "Replay cached run" to "Saved run" with date/time/duration.

3. Document chrome:
   - Add a page template with case number, doc number, author/badge, page x of y,
     footer, signature/received blocks. Paginate the viewer at ~40 lines.
   - When a quote is opened, highlight the span and scroll to it.
   - Add Bates-style footers to every page.

4. Board semantics:
   - Remove yarn for mere person-document citation. Keep red yarn for
     contradictions and add labeled yarn for typed relationships only.
   - Add a paper tag at the midpoint of each remaining string.
   - Change "WHO DID IT" to "WHAT THE FILE CONTRADICTS".
   - Add the board plate "WORKING BOARD · NOT EVIDENCE".

5. Roster triage:
   - Add role_class to persons (victim, subject, witness, officer, attorney,
     medical, records, unnamed, deceased).
   - Pin only victim, subjects, key witnesses, and key records. Put officers and
     unnamed/deceased persons in a file-personnel list.
   - Consolidate the AI-likeness disclosure into the footer and a small corner tag.

6. Physical variety:
   - Add seeded pin/tape/photo-corner variants and 2-3 paper defects per card type.
   - Replace alibi pills with stamp treatments. Add NOT APPLICABLE for no-claim
     persons.

Do not add dependencies. Do not change the demo script. Report what you ran and
what you could not verify.
```

---

## Bottom line

The product already does the hard, honest thing: it checks every quote and refuses to
judge a person. The interface just needs to stop looking like the submission form and
start looking like the file it claims to be. Fix the clock, move the chrome, put paper
under every claim, make the board mean something, and triage the people. That is the
difference between "impressive hackathon demo" and "a detective could actually use this."
