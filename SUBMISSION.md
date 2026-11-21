# SUBMISSION — Gemini 4 NYC, Cerebral Valley (due 5:00 PM EST, 2026-11-21)

Form-ready fields. Paste, do not retype.

- **Project name:** Murder Board
- **Demo link:** https://murder-board.pages.dev
- **Repository:** https://github.com/mrfentmen/murder-board (public)
- **Problem statement:** Problem Statement One, 5 Sigma
- **Team:** Abdelrahman El Sayad (solo). Add any team members on the
  form if the room team differs.

## One line

A homicide file is a thousand pages that do not agree with each
other. Murder Board puts ten named Gemini agents on the file,
sorts it into one murder book, and judges it: every finding
carries a verbatim quote or it does not exist.

## What it does

The detective (or the user) gives an order in the squad room
chat ("work the case", "work the Duck case") and ten agents,
each holding a real chair from a real investigation (First
Officer, Records, Coroner, CSI, Analyst, Digital,
Cross-Examiner, Interviewer, Prosecutor, Lead Detective), work
the file live on screen: a case folder header, a corkboard with
pinned faces and yarn, one clock for the whole case, judgments
with alibi ratings stamped, leads scored by a rubric the runner
recomputes in the open, and a one page brief. Three laws run in
code, not in prompts: no quote, no finding (a validator drops
any claim whose quote is not verbatim in the file, and shows the
count); the runner recomputes every lead score from the rubric;
a failed step turns its chair red and the run continues.

## The four Gemini 4 models

- **Argon judges** (reasoning): the Cross-Examiner and the Lead
  Detective, the two steps that weigh the file.
- **Carbon builds** (visual coding): First Officer, Records,
  Coroner, CSI, Intake, Interviewer, Prosecutor.
- **Hydrogen holds the world** (world models): the Analyst, one
  clock and one map of the case.
- **Neon works the machines** (robotics): Digital, the cameras,
  keypads, plate readers and phones that watched the scene.
- Decisions API: no decision model exists in the event key's
  model list (checked live). The decision function is the
  rubric recompute in the runner: deterministic, inspectable,
  arithmetic shown. Stated in EVAL.md.

## Proof (EVAL.md)

Scored against per-case bibles: three fictional cases (a police
file, an internet drill case built from public posts, and a
cold case sim built to be solved only by a four record chain)
plus the Duck File, the real 2020 Chicago FBG Duck case rebuilt
from the public record and run blind twice. The squad caught
the planted contradictions at HIGH, the watchman's keypad code
in the sim, and the defense lawyer's "unknown person" claim in
the real case; it never claimed the masked gunmen on camera
were anybody. A single call baseline found the seams too; the
squad's edge is discipline: dropped findings counted in the
open, severity that discriminates, leads kept to single
actions, no person judged. Misses are in EVAL.md too, named.

## The video

One minute, script approved, produced on Del's word. Beats: the
folder and the order in the chat, the room posting, the Webb
tow catch in two quotes, the Harborlight keypad catch, the
standing line: "It judges the file. The detective does the
detecting."
