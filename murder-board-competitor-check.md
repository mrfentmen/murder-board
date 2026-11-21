# MURDER BOARD — Competitor Check + Demo-Day Runbook
*Researched by Lapis, 2026-11-21 ~12:30pm EST. Demo deadline 5:00pm EST today. Repo untouched; research only. Read live repo + live demo + vendor sites this morning — do not re-verify from memory.*

## 1. The catch: DEMO_SCRIPT's "What exists already?" answer is risky as worded

DEMO_SCRIPT.md (repo, main, commit a73bc08) says, for a judge asking what exists already:

> "Truleo summarizes cases, Conectir checks statements. Nobody packages the full judgment, alibi ratings, lead scores, and the evidence ledger cross-check, aimed at homicide. That is the alley."

Both halves of the first sentence check out. The second sentence — "Nobody packages…" — does **not** survive a look at Conectir's own site, and Truleo is closer than "summarizes cases" suggests. A judge who has seen either product can push back on this line, and it is the one scripted answer most likely to get challenged.

## 2. What I verified

### Truleo — real, and now does case summarization, not just bodycam
- Chicago-based, founded 2019; body-worn-camera transcription/classification for police professionalism review (Popular Science, Feb 2023).
- Its own investigator blog describes case summarization built with investigators: "Consolidates case materials — reports, audio files, transcripts, video metadata, digital evidence logs — into one system. Analyzes each source using LLMs … to identify facts, **inconsistencies, patterns, and gaps**. Generates a detailed, organized summary with **timelines, person-of-interest linkages**, tips categorized by credibility or corroboration, and metadata comparisons. Surfaces weak points … **discrepancies in witness accounts, gaps in timelines**, or procedural lapses."
- It also did real cold-case work: the Papakee / Rita missing-person case (Meskwaki Nation, 2015), structuring a decade of interviews, phone records, social tips, bodycam, sonar/financial records.
- Sources: https://resources.truleo.co/blog/buried-evidence-to-breakthroughs-why-we-built-ai-for-investigators ; https://www.popsci.com/technology/police-body-cam-ai-truleo/ ; Casper PD pilot notice https://www.casperwy.gov/news_detail_T6_R230.php
- Verdict: "summarizes cases" is fair shorthand, but undersells it — it also flags inconsistencies and gaps. It does **not** appear to do alibi ratings, scored leads recomputed by code, or a quote-verification drop rule.

### Conectir — real, and much closer than the script implies
- conectir.com, "AI investigation & case management software … built for government and law-enforcement investigators."
- **Cross-statement timeline reconciliation:** "Paste in two, three, four statements. See every contradiction in seconds… lines up every event from every statement, side by side, on a single timeline. **Every flagged contradiction comes with at least one innocent alternative** … Conectir never decides who is lying." Product page: "flags each contradiction with the **verbatim quotes from both sides**."
- **AI Advisor that reads the whole case:** "One button reads the entire case … and comes back with a **prioritised list of what to do next, the gaps still open**, and the interview questions worth asking."
- Also: SCAN statement analysis (22 rules, 90+ languages, innocent alternative per marker), Case Council (defence / prosecution / investigator / due-process panel peer-reviewing the case), OSINT report ("Leads to verify. Never a verdict."), financial analysis "computed by code" with every sum rebuildable, tamper-evident evidence vault (SHA-256) + hash-chained audit trail.
- Sources: https://www.conectir.com/ ; https://www.conectir.com/product ; https://www.conectir.com/product/scan
- Verdict: Conectir already packages contradictions-with-quotes + innocent readings + gaps + prioritised leads + interview questions in one workspace. What it does **not** advertise (on the pages checked): a homicide-squad role split, an **alibi rating table**, **lead scores recomputed by code from a published rubric**, a **quote check in code that drops findings**, or an evidence-ledger-vs-scene-report count cross-check. That is where Murder Board's defensible edge actually lives.

## 3. What Murder Board still uniquely combines (verified in repo, 2026-11-21)
- Ten Gemini agents in real homicide-squad roles (First Officer, Coroner, CSI, Analyst, Cross-Examiner, Digital, Interviewer, Prosecutor, Lead Detective, Records) — README + CODEX_HANDOFF.md.
- **No quote, no finding, in code:** quoteOk checks a verbatim normalized substring; first live Delgado run **dropped 4 findings** whose quotes weren't in the file. Conectir shows quotes; Murder Board *enforces* them and reports the drop count.
- **Alibi ratings table** for the death window (Webb CONTRADICTED, Whitfield UNCORROBORATED) + **lead scores recomputed by the runner** from declared components (40 high contradiction / 25 in death window / 20 closes a gap / 15 still reachable; top lead 80 Delgado, 85 Screens).
- **Evidence-ledger cross-check:** scene report says two shell casings, ledger lists one — top gap. That specific ledger-vs-report count check is the demo's second catch.
- **Falsifiable fictional cases with an answer key:** EXPECTED_FINDINGS.md + CASE_BIBLE.md for Delgado (14 docs, 3 planted catches) and CASE2_BIBLE.md for the Screens/internet case. A judge can score the run.
- **Open, static, replayable demo:** murder-board.pages.dev works with no key in replay mode (~10 sec vs ~7.5 min live). Both cases have saved runs.
- **Door 2 (Records) is now visible on the live demo** (checked 12:27pm EST): "Simulation build: the census answers from bundled fixtures for the two fictional cases (Ray Delgado, Treyvon Ellis). Live lookups are off." — say that out loud if a judge clicks it; do not present it as live lookups.

## 4. Suggested replacement lines for DEMO_SCRIPT (pick one, ~15 seconds)

Option A (safest, keeps the alley):
> "Truleo summarizes cases and flags inconsistencies. Conectir checks statements against each other, with quotes and innocent readings — that's the closest thing out there. What nobody else packages is the homicide squad itself: ten roles, alibi ratings, lead scores recomputed by code, and a quote check that drops findings that can't be sourced — on a fictional case with an answer key you can score."

Option B (shorter):
> "The pieces exist — Truleo on summaries, Conectir on statement contradictions. The package doesn't: a full squad, alibi table, scored leads, and code-enforced quotes, aimed at the cold homicide file nobody has time to re-read."

Do **not** keep "Nobody packages the full judgment…" unqualified — Conectir's Advisor + reconciliation is close enough that the claim reads as not having looked.

## 5. Minor script inconsistency worth a 10-second fix
DEMO_SCRIPT 0:25 says "Four agents work the file." The repo is a squad of **ten** agents / 11 steps (README, CODEX_HANDOFF). If del says "four" on stage a judge counting chairs will notice. Change to "The squad works the file" or "Ten agents work the file" — no other line depends on the number.

## 6. Demo-day runbook — the next 4.5 hours to 5:00pm EST
- **Demo on replay, not live.** Full live run ~7.5 min; replay ~10 sec (CODEX_HANDOFF). Live only if there is slack time — never as the first run in front of judges.
- **Dry-run both cases in replay** before leaving: Delgado (Webb car / tow record, Whitfield visit, missing casing) and Screens (studio-all-night post vs livestream + plate cam, Reed CONTRADICTED, partial plate innocent reading). Both saved runs are on the live site.
- **Say the 4 dropped findings out loud** — it is the strongest trust line in the whole pitch (already in murder-board-judge-qa.md).
- **Key expiry trap:** the Gemini key at the event belonged to a temporary hackathon account **deleted the day after the event (after 2026-11-22)** — live runs after that need a fresh key from del. Replay needs nothing. (CODEX_HANDOFF.)
- **Never commit `config.js`** or keys; a leaked key gets every key on it killed automatically (CODEX_HANDOFF).
- **Codex is on the Records prototype** (PAX_DECISION option 1, scoped: fictional fixtures only, live adapters UNIMPLEMENTED). Lapis research for it is already delivered: murder-board-records-research.md (public stack + Fellegi–Sunter) and murder-board-judge-qa.md in ~/workspace/your_files/ — del said he is committing those files.
- **If a judge asks "is this real police data?"** — script answer stands: no, fictional case written for the event; real files need chain of custody and local processing.
- **Clock:** now ~12:30pm EST, deadline 5:00pm EST (2026-11-21). ~4.5 hours left.

## What I did NOT verify
- I did not run the live demo end-to-end or click through replay myself beyond reading the live page text; a 2-minute click-through by del/Codex is still the real check.
- I did not check Conectir/Truleo pricing, customer lists, or whether either has an alibi-rating feature hidden behind login — the comparison above is from their public product pages as of today.
- Codex's current Records-prototype progress is not in the repo snapshot I read (commit a73bc08, 39 commits); del/Codex know the live state.
