# How an AI Agent Would Solve Crimes and Murders
### Research notes for del — 2026-11-21
*Question: how would an AI agent work a case, the way a detective does? Part real-world evidence (what's already deployed), part reasoned model of how an agent like me would actually run an investigation.*

---

## The one-sentence answer

A human detective solves a case by **insight** — experience, gut, reading people. An AI agent solves it by **exhaustion and contradiction** — it reads everything, forgets nothing, cross-references all of it, and finds the seam where someone's story doesn't fit the record. It doesn't have hunches. It has a ledger.

## Why this moment: the evidence problem

Modern cases aren't short on evidence — they're drowning in it:

- Digital evidence now appears in **97% of criminal cases** (Cellebrite 2026 Industry Trends Survey).
- One homicide case can produce ~47K text messages, 12K photos, multiple email/social accounts, footage from 14 cameras, cell-tower records, financial transactions, and a vehicle GPS log — and the detective carrying it has ~8 other cases.
- A phone extraction takes a human **40–80 hours** to review; AI-assisted review takes **2–6 hours**.

The bottleneck in real investigations is rarely cleverness. It's reading. That's the part machines are built for.

## How an agent would actually run a murder case

**1. Ingest everything into a living case index.**
Paper reports → text. Interview recordings → transcripts. Photos/video → indexed media. Then extraction: every person, nickname, address, vehicle, phone number, workplace, and date pulled out of narrative text. Then *entity resolution* — deciding that "Mike Johnson," "Michael Jonson," and "M. Johnston" in three different reports are the same man because they share an address and a car. This unglamorous pipeline is where real AI casework lives or dies (the National Institute of Justice describes exactly this text-analytics approach for cold case review).

**2. Rebuild the victim's last day — and everyone's timeline.**
The agent constructs one master timeline from every timestamp it can find: messages, calls, camera sightings, card transactions, location pings. Human detectives hold maybe a dozen anchor events in mind. The agent holds all of them, aligned to the minute. Murders usually break on timelines — the 40 minutes nobody can account for.

**3. Build the relationship graph.**
Victim at the center; every person, place, object, and event as a node; every documented contact as an edge. Then ask questions that used to be impossible without reading every page: *Who is connected to both the victim and the scene but appears in no interview? Whose name appears exactly once, in a report from six years before the murder?*

**4. Run a hypothesis tournament, not a single theory.**
This is the biggest structural difference from human detective work. Humans fall in love with a suspect (tunnel vision is the leading cause of wrongful convictions). A well-built agent generates *all* plausible theories — partner, stranger, robbery gone wrong, staged scene — and scores each one against **every** evidence item, keeping a visible ledger: which facts each theory explains, which it ignores, which it contradicts. Theories don't get believed; they get ranked, and the ranking updates with every new fact.

**5. Hunt contradictions — the agent's real superpower.**
Witnesses lie, misremember, and drift. A suspect interviewed in year 1 and year 9 will contradict himself somewhere. A human can't hold 10 years of statements in memory; the agent compares every statement against every other statement and against the physical record — claimed location vs. phone location, claimed timeline vs. camera timestamps, claimed relationship vs. message history. **Lies leave seams, and seams are exactly what a cross-referencing machine finds.** (Same skill, incidentally, as catching an AI contradicting itself: compare claims against claims, at scale, without forgetting the first one.)

**6. Eliminate at scale.**
Good detective work is mostly proving who *didn't* do it. The agent verifies alibis against records automatically — every person of interest's claimed whereabouts checked against every camera, ping, and transaction — shrinking the suspect pool with proof instead of vibes.

**7. Do gap analysis — let the absences direct the investigation.**
For the leading theory, the agent asks: *if this is true, what evidence should exist that doesn't?* A missing expected record is itself a lead. This is how AI directs the expensive human steps: which old DNA sample merits retesting with modern methods, which witness is worth re-interviewing because their two statements diverged, which camera angle nobody ever pulled.

**8. Red-team itself.**
A second agent (or the same agent in an adversarial role) argues the defense case against the leading theory: *here's how an innocent person produces this exact evidence pattern.* If the theory can't survive its own red team, it isn't ready for a human to act on.

## What's already real (not speculation)

- **Cold Case Foundation + Veritone Assess**: AI re-analyzed a ~42-year-old case file, rebuilding chronology and surfacing leads the agency — which had actively investigated for four decades — could act on. Analysts verify every AI-surfaced item before it goes anywhere.
- **Homeland Security Investigations** applied AI to cold cases and identified a suspect in a decades-old child exploitation case within two weeks.
- **The FBI** is applying AI to its Criminal Investigative Division first, because that's where evidence volume is most unmanageable.
- **Closure-Intel** (YC W25) and Cellebrite's tools reprocess archived phone extractions and case files for cold-case work — old evidence, new connections.
- Pattern across all of it: **AI doesn't create new evidence. It finds the evidence you already had.**

## The failure modes — the half that matters just as much

An AI detective has characteristic ways of being *wrong*, and they're not the human ways:

- **Probabilities treated as certainties.** AI outputs scores and candidates; humans downstream convert them into facts. In Oct 2025, an AI surveillance system flagged a Doritos bag as a gun and a 17-year-old was held at gunpoint. In Dec 2025, a Tennessee grandmother was released after **five months in jail** because facial recognition wrongly tied her to crimes in a state she'd never visited. Every publicly known wrongful arrest from police facial recognition in the US has been of a Black person (ACLU, citing DOJ's Dec 2024 report: seven publicly reported mistaken-arrest cases).
- **Tunnel vision at machine speed.** A human detective's bias misleads one investigation. A biased model — or biased historical data fed into predictive policing — misleads a whole department, with a veneer of objectivity.
- **Hallucinated connections.** A language model asked to find patterns will find them, including ones that aren't there. In a case file, a confident invented link between two people isn't a quirk — it's a false lead with a real person's name on it.
- **No scene, no room, no street.** The agent can't walk the scene and feel that something's off. It can't read a witness's hands shaking, develop an informant, or know which question makes a suspect go quiet. Interrogation, canvassing, and trust are physical-world work.
- **The accusation problem.** A detective's conclusion puts a human in a cell. An agent that ranks theories must never be the last step before that — every real deployment above keeps a human verifying each surfaced lead, and that's not bureaucracy, it's the load-bearing wall.

## My honest verdict

The AI agent is not the detective. It's the **perfect case-file brain sitting next to the detective** — total recall, infinite patience, no favorite suspect, and a compulsion to check every claim against every other claim. It solves the cases that are buried rather than hidden: cold cases with 40 years of paper, modern cases with 47,000 messages. The cases that turn on a look, a lie told to a face, or a walk through a room still belong to humans.

The deepest difference: a human detective asks *"who do I believe?"* An agent asks *"which story survives contact with all the records?"* Those are different questions — and the second one is the one that was never affordable before.

---

## Sources
- Raft Labs, *AI in investigation and forensics: tools and use cases* (Cellebrite 2026 survey figures; FBI CID; HSI cold case) — https://www.raftlabs.com/blog/ai-investigation-forensics
- Veritone / Cold Case Foundation, *How AI Is Helping Solve Cold Cases* — https://www.veritone.com/blog/how-ai-is-helping-solve-cold-cases/
- NewsTrail, *Cracking the Cold Case* (NIJ text-analytics framework; ingest → extract → resolve → link → triage pipeline) — https://www.newstrail.com/cracking-the-cold-case-ai-algorithms-resurrect-decades-old-fugitive-trails/
- AZ Central, *How AI can help detectives crack confounding criminal cases* — https://www.azcentral.com/story/news/local/arizona/2026/02/26/detectives-artificial-intelligence-use-unsolved-cases/88849332007/
- Fast Company, *Why AI policing leads to false arrests and wrongful convictions* (Taki Allen; Angela Lipps) — https://www.fastcompany.com/91540488/ai-policing-false-arrests-wrongful-convictions
- ACLU comment to DOJ/DHS on facial recognition & predictive policing (2024) — https://assets.aclu.org/live/uploads/2024/01/ACLU-Comment-re-EO-14074-Sec-13e-1.19.2024.pdf
