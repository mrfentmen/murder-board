# EVAL — Murder Board vs a single model call

Problem statement: **One, 5 Sigma.** A real task agents struggle
with, done reliably, with proof. The task: read a homicide case
file and judge it, contradictions, alibis, gaps, ranked leads,
without inventing a single quote.

Written 2026-11-21, Gemini 4 NYC. All runs below are real runs
from today, on the event key. The squad runs are saved in
`cache/` and replay from the site. The baseline runs are saved
in this file's numbers, quoted from the raw outputs.

## Method

**The squad.** Eleven steps in a fixed order (SPEC4), two
Gemini 4 models with separate jobs: Argon judges (Cross-Examiner,
Lead Detective), Carbon builds (every extraction step). Three
laws enforced in code, not in prompts: no quote, no finding
(every cited quote is checked verbatim against the document,
failures dropped and counted on screen); the runner owns the
arithmetic (lead scores are recomputed from the rubric, the
runner's number wins); a failed step never kills the run (one
retry, then a red chair, and the run continues).

**The baseline.** One single Argon call per case. The whole
file, one plain instruction: list contradictions with quotes,
rate the alibis, rank up to five leads with scores. No squad
prompts, no validation, no rubric, no book. This is the
strongest simple thing a team would ship instead.

**The yardstick.** Each case ships with a bible
(EXPECTED_FINDINGS.md, CASE2_BIBLE.md, CASE3_BIBLE.md) written
before the runs: the planted catches, the expected alibi
ratings, the expected top lead.

## Results

### Delgado (police file, 14 documents)

| | Star catch (the car) | Second catch (statement 3) | Webb alibi | Whitfield alibi | Top lead |
|---|---|---|---|---|---|
| Bible | HIGH | MEDIUM | CONTRADICTED | UNCORROBORATED | Re-interview Webb on the car, 80 |
| Squad | HIGH | HIGH | CONTRADICTED | UNCORROBORATED | 80, arithmetic shown (40+25+15) |
| Baseline | HIGH | HIGH | CONTRADICTED | **CONTRADICTED** | 98, bundled: confront Webb with tow record AND debt AND buyout |

Baseline found 10 contradictions and called 7 of them high,
including a debt entry in the paper ledger, which is motive
texture, not a contradiction. The squad's list is shorter and
graded. The baseline overcalled Whitfield: a statement that
adds a visit is drift, and drift is not a record contradiction.
The squad also dropped 4 findings in this run at the quote
check and shows the count on the Judgments screen. The
baseline has no way to drop anything.

### Screens (internet file, 12 documents)

| | Catch 1 (studio claim) | Catch 2 (the phone call) | Reed alibi | Top lead |
|---|---|---|---|---|
| Bible | HIGH | HIGH | CONTRADICTED | Pull the full plate cam record |
| Squad | HIGH | HIGH | CONTRADICTED | Plate record, rubric-scored |
| Baseline | HIGH | HIGH | CONTRADICTED | 95, subpoena the deleted story |

The baseline missed the plate cam tension (doc03 vs doc09)
that the squad caught at medium. Its leads run 95/92/88 with
no arithmetic behind them. The squad's leads carry the rubric
math and the runner recomputes every score.

### Harborlight (the sim, 18 documents, built to be hard)

| | Keypad chain | Meter chain | Delaney lie | Herrera alibi | Okafor alibi | Top lead |
|---|---|---|---|---|---|---|
| Bible | HIGH | HIGH | HIGH, with resolution | CONTRADICTED | UNCORROBORATED | Re-interview Herrera on the 00:07 entry |
| Squad | HIGH | HIGH | HIGH | CONTRADICTED | **CORROBORATED** | Two Herrera questions, 80 each |
| Baseline | HIGH | HIGH | HIGH | CONTRADICTED | **CORROBORATED** | 100, "re-interview and arrest or search Herrera" |

Read this table honestly: on the hardest file, the single call
found the same chain the squad found. Both systems overcalled
Okafor, whose only corroboration is a wife first asked eight
years later. The difference is in the lead. The baseline's top
lead recommends an arrest. The board's leads are single actions
a detective performs, phrased as questions anchored to quotes,
because the board judges the file and never a person. That is
not a style choice. It is the product's safety property, and
only the pipeline enforces it.

## What the squad adds, stated plainly

A single strong model call finds most of the seams in a clean
file. These three files are clean, and one baseline run each is
a small sample. What the baseline cannot do:

1. **Catch itself.** In these runs its 46 quotes all happened
   to be real. Nothing in a single call checks that. The
   squad's quote check dropped 4 findings in one Delgado run
   and prints the count.
2. **Discriminate.** Seven highs out of ten findings is not
   triage. The squad's severity is graded against a rubric and
   its lead scores are recomputed by the runner; one
   Harborlight lead was corrected in the open, model said 35,
   rubric says 25, and the correction is in the run log.
3. **Stay in its lane.** No arrest language, no person judged,
   every lead one action with its arithmetic shown.
4. **Hand back a book.** Persons, one timeline, an evidence
   ledger, a brief, and a board a detective can stand in front
   of. The baseline hands back one JSON blob.

## Failure analysis, ours included

- **Carbon is slow on long outputs.** Three extraction steps
  in an early run and the Harborlight timeline step failed on
  a 120 second helper timeout, since raised to 300. In the app
  the same failure mode shows as a red chair and the run
  continues, which is the designed behavior, but the timeline
  step is the fragile one and we say so.
- **Argon varies.** One full re-run undercalled Webb's alibi
  and re-bundled its leads at 100 despite the tightened
  prompts. That run was discarded, not shipped; the variance
  is real and the eval does not hide it. The rubric recompute
  bounds the damage on scores; it cannot bind judgment calls.
- **Both systems overcalled Okafor** (see Harborlight above).
  A late spouse statement reads as corroboration to a model.
  A detective would weigh it less. Open problem.
- **Severity wobble.** The second Delgado catch is planted as
  medium and both systems called it high, in every run so far.

## Limits of this evaluation

The three cases were written by this team, which is why the
project declares Problem Statement One and not Two. The
planted catches are known to us, though not to the models. The
baseline ran once per case. The honest next test, already
agreed with the team: rebuild a real, solved case from the
public record, run the squad on it blind, and score it against
what actually solved the case. Faster, better, or different
are all acceptable answers. That run is the unprepared-input
check this evaluation still owes.

## The Decisions API

The judging criteria name a Decisions API. No decision model
appears in the model list on this event's key (checked
2026-11-21 against the live list: Argon, Carbon, Hydrogen,
Neon, and the fast tier). The decision function in this system,
which lead outranks which and by how much, is performed by the
rubric recompute in the runner: deterministic, inspectable,
and shown on screen with its arithmetic. We used the two
Gemini 4 models the key actually serves, each with a clear
job, and we say plainly that the third named piece was not
available to use.
