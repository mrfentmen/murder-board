# SPEC 7 — the training factory: desk retrieval now, the interview room tomorrow

Written 2026-11-22 inside `/Users/test/Desktop/murder-board`, extending `SPEC.md` through `SPEC6.md`.

`SPEC6.md` named the bottleneck of every AI investigator built to date:
> **Asking is CONTACT. Checking is DESK.** Today an AI cannot sit across a metal table from a witness, watch their pulse jump when a tow yard is mentioned, or press a second question before they rehearse an answer. So today the AI must out-retrieve, out-index, and out-cross-examine every page in the archive. Tomorrow, when contactless cameras, thermal sensors, and microphones enter the room, the AI will sit beside the detective in real time—and if it was trained like a movie polygraph, it will convict nervous innocent people.

This spec defines **both** datasets, built from first principles before a single GPU hour is rented:
1. **TRACK 1 (NOW — Desk, Archive Retrieval & Telemetry):** Multi-hop vault search, GraphRAG entity resolution, almanac/physics reality checks, de-spoiled historical & modern crime archives, and zero-drop `Murder Board` 11-chair reasoning across **#1 Cold-Case / Homicide**, **#2 911 Panicked & Coerced Triage**, and **#3 Cartel & Shell-Company Money-Laundering**.
2. **TRACK 2 (FUTURE — The 12th Chair, In-Room Biometric & Cognitive-Load Co-Pilot):** Synchronized contactless physiology (`rPPG` heart rate & `HRV` vagal rhythm, electrodermal `EDA` sweat conductance, periorbital thermal shift, pupil dilation, vocal micro-tremor, response latency) fused with the case file—explicitly hardened against the **Othello Error** so autonomic stress is used to steer questions and record pulls, **never** mistaken for proof of guilt.

All 5 House Rules from `PROMPTS.md` govern every training example in this factory:
1. **File & verified sensor telemetry only** — nothing outside the record exists.
2. **Verbatim quote or drop** — enforced in Python via `quote_ok()` (`norm(quote) >= 8` chars, exact whitespace-normalized substring of `doc.text`; `dropped == 0` across all shards).
3. **Judge the file, never a person** — never write that someone is guilty, lying, or a killer; every contradiction and every physiological spike carries its mandatory `innocent_alternative`.
4. **Strict JSON / tool-call schemas** — validated before any row touches disk.
5. **Deterministic rubric & verifiable ground truth (`ground_truth`)** — every SFT turn carries exact programmatic labels for **RLVR / GRPO** reinforcement learning.

---

## 1. Master Catalog of All 7 Unbuilt Specialist AIs

| # | Specialist Model | Why Foundation Models Fail Today | Factory Status |
|---|---|---|---|
| **1** | **Cold-Case & Cross-County Homicide Detective Squad** | CJIS murder books are sealed; LLMs trained on crime fiction tunnel-vision on dramatic suspects and hallucinate quotes. | **Active — Track 1 & Track 2 Built** |
| **2** | **911 Panicked-Call & Coerced-Caller Triage Co-Pilot** | Live PSAP audio/CAD streams aren't web pretraining data; standard LLMs miss pizza-order coercion ruses and agonal gasps ("weird snoring") and reply too wordily. | **Active — Track 1 & Track 2 Built** |
| **3** | **Cartel, TBML & Shell-Company Money-Laundering Hunter** | FinCEN SARs are federal felonies to leak; static bank rules (`>$10k`) drown analysts in false positives while missing smurfing, `$/kg` trade fraud, and utility-mismatched cash fronts. | **Active — Track 1 & Track 2 Built** |
| **4** | **Crash, Arson & Disaster Forensics Investigator (NTSB / Fire Marshal)** | Sensor black boxes, maintenance logs, and shift handoffs sit in sealed litigation vaults; LLMs confuse post-fire damage with pre-fire origin. | Cataloged — Phase 2 Expansion |
| **5** | **Outbreak "Patient Zero" & Poisoning Epidemiologist** | ER intake notes are siloed across competing hospitals behind HIPAA; LLMs miss subtle multi-ER lot/vector clusters inside flu-season noise. | Cataloged — Phase 2 Expansion |
| **6** | **Customs & Maritime "Dark Fleet" Smuggling Inspector** | <2% of port containers are inspected; targeting rules are restricted; requires container weight vs. commodity density physics + AIS blackout math. | Cataloged — Phase 2 Expansion |
| **7** | **Public Corruption & Municipal Bid-Rigging Auditor** | RFP specs, zoning variances, LLC agent filings, and timed donations sit in fragmented local dumps nobody cross-links. | Cataloged — Phase 2 Expansion |

---

## 2. Track 1 (NOW): Active Investigative Retrieval & The 5 Skill Layers

Because a desk AI cannot interrogate people, it must **interrogate archives, graphs, and physical reality**. Track 1 trains five interlocking capabilities:

### 2.1 Layer A — Full 11-Chair `Murder Board` Squad Execution
Every procedural and reconstructed case emits zero-drop turns for all 11 steps in `app/app.js`:
`custody` → `records` → `coroner` → `csi` → `intake` → `analyst` → `digital` → `cross_examiner` → `interviewer` → `prosecutor` → `lead_detective`.
- Implements `CASE3_BIBLE.md` (Harborlight) + `REALISM.md` multi-record chains:
  - **Survival-floor window narrowing** (e.g., ME sets 10:30 PM–12:30 AM; victim's verified 23:46 SMS + 23:54 access code narrows the working window to 23:54–00:30).
  - **Loud red-herring liars cleared by proof** (estranged partner lies in Year 1, caught by ALPR bridge log at 22:56–23:18, cleared of the post-23:46 window by the victim's own outgoing message).
  - **Multi-year statement drift (MEDIUM)** with memory-decay `innocent_alternative`.
  - **Fake "killer-only knowledge"** neutralized by a prior public inspection docket.
  - **CSI count discrepancies** (scene report observes 2 items; ledger books 1) + unpulled cameras + uncollected EXIF originals.
  - **20% Insufficient-Evidence Holdouts** where no window alibi is broken yet, training the squad to prioritize forensic/archive pulls without overclaiming.

### 2.2 Layer B — Multi-Hop Noisy Vault & Almanac Retrieval Trajectories (`noisy_vault_retrieval.py`)
Static benchmarks (`DetectiveQA`, `MuSR`, `TurnaboutLLM`) hand all clues to the model in one prompt. Real cold cases bury 4 load-bearing records inside 120 pages of dead-end tips, routine timecards, and uninvolved neighbors.
- At Turn 0, the agent sees **only** `doc01` (Scene Report) and an unsearched vault index.
- The agent executes iterative tool calls (`search_vault`, `query_entity_graph`, `check_almanac`, `diff_statements`, `conclude_board`) to:
  1. Decompose witness statements into **peripheral checkable premises** (Columbo move),
  2. Cross-check claims against **The Almanac** (historical weather, moon phase/illumination, sunset time, transit timetable, road closures, municipal inspection dockets),
  3. Traverse 2-hop and 3-hop `GraphRAG` links (`Person -> Phone/Plate -> LLC/Address -> Uninterviewed Witness`),
  4. Stop searching and emit a quote-verified brief once sufficiency is reached (or declare an archival gap).

### 2.3 Layer C — The 5 Forensic Micro-Skill Drills (`forensic_micro_skills.py`)
1. **Temporal & Clock-Skew Math:** Converting relative witness time (*"twenty minutes after last call"*, DVR `+47 min` unadjusted DST drift, cell UTC vs. local) into strict ISO-8601 intervals and road-transit feasibility checks.
2. **Strict Forensic NLI (`SUPPORTED` / `REFUTED` / `NOT_ENOUGH_INFORMATION`):** Preventing leaps from partial corroboration to proof.
3. **Entity Resolution & Collision Guard:** Linking `"M. Johnston"`, `"Mike"`, `"primer-gray Ranger"`, and burner numbers into `(Entity A) --[edge, doc_id]--> (Entity B)` triples—while **refusing** to merge same-name strangers (`Records` collision law).
4. **Pathology, Ballistics & Era-Forensics Literacy:** Lividity fixation vs. postmortem movement flags, rigor/algor bounds, cell-sector azimuth radius vs. pinpoint fallacy, and legacy evidence re-testing (`ABO/RFLP inconclusive` → `M-VAC Touch DNA / STRmix / IGG / NIBIN`).
5. **Hypothesis Tournament & Bias Immunity:** Scoring 3 competing theories against every exhibit to defeat confirmation bias.

### 2.4 Layer D — Real De-Spoiled Historical & Modern Archives (`harvest_and_despoil.py`)
Solves the exact `case4` (`duck-2020`) retirement problem noted in `README.md` (*"the verdict sat inside its own file, so the run tested reading, not detection"*):
- **De-spoiled `duck-2020`** (verdict/indictment conclusions stripped to `ground_truth`, leaving raw witness, surveillance, vehicle, and phone exhibits).
- **Old Bailey Murder & Manslaughter Trials (1700s–1913)** — verbatim witness, constable, and post-mortem surgeon accounts split into `doc01..docN`, with `GUILTY` / `NOT GUILTY` moved strictly to `ground_truth`.
- **DOJ Homicide & DOJ Money-Laundering Case Records (2009–2026)** — pleas, verdicts, and statutory penalty paragraphs stripped.
- **2005–2026 Municipal 911 CAD Dispatches (FDNY/NYC EMS, SFPD, Seattle)** — post-arrival `final_call_type` and `final_severity` stripped from intake prompts so the model learns real-world triage escalations (`OTHER -> CVAC` stroke, `DRUG -> CHOKE`, `AUDIBLE ALARM -> BURGLARY`).

---

## 3. Track 2 (FUTURE): The 12th Chair — In-Room Biometric & Interrogation Co-Pilot

When sensors enter the interview room, PSAP video console, or border secondary inspection booth, **Chair 12 (`Room Co-Pilot`)** fuses live multimodal human signals with the Murder Book.

### 3.1 Sensor Modalities (Calibrated to `WESAD` / `UBFC-rPPG` / `CIT` Literature)
- **Cardiovascular (`rPPG` contactless camera):** `hr_bpm`, `baseline_hr_bpm`, and **vagal Heart-Rate Variability (`hrv_rmssd_ms`)**—because cognitive load and concealed recognition suppress vagal `RMSSD` even when breathing is controlled.
- **Electrodermal / Thermal Sweat (`EDA` / IR camera):** Tonic skin conductance (`baseline_eda_uS`), phasic sweat burst (`eda_peak_uS`, `1.2–3.5s` physiological latency), and `periorbital_temp_delta_c`.
- **Ocular & Motor:** `pupil_dilation_delta_mm` (cognitive effort / recognition) and blink-rate suppression-then-rebound bursts.
- **Paralinguistic & Temporal:** `response_latency_ms`, speech rate (`wpm`), `vocal_pitch_jitter_pct`, and pronoun/tense distancing.

### 3.2 Hardening Against the Othello Error (3 Mandatory Population Slices)
1. **35% Calm Rehearsed Concealers:** Normal pulse on direct accusations (*"Did you enter the office?"*), broken **only** by:
   - **Concealed Information Test (CIT) 5-item arrays** (4 plausible decoys + 1 withheld scene artifact -> stimulus-locked `HRV` drop + `EDA` phasic spike + pupil dilation on the true item), and
   - **Cognitive-Load Reverse-Order / Spatial Prompts** (*"Walk backward from 12:30 AM to 10:30 PM"* -> latency spike + verbal contradiction against `doc05`/`doc11`).
2. **35% Terrified Innocent / Othello-Trap Controls:** High sweat (`EDA > 7 µS`) and elevated `HR (115–138 BPM)` across *both* control and target questions due to fear of wrongful arrest, trauma, or embarrassment over an unrelated secret. **Any model output claiming deception from raw arousal receives a heavy negative RLVR reward (`-1.0`).**
3. **30% Distressed / Traumatized Cooperative Witnesses:** Autonomic spikes triggered by traumatic memory recall; Co-Pilot shifts to non-leading **PEACE / Cognitive Interview** open recall rather than pressure.

### 3.3 Cross-Domain Room Coverage
- **Homicide / Cold-Case Interview Room** (`Murder Board` Chair 12)
- **911 / Bodycam Live Voice-Stress & Forced-Calm Coercion Triage** (flat coerced words vs. `142 BPM` vocal micro-tremor & shallow `26 RPM` breath gaps)
- **AML / Customs / Insider Secondary Inspection** (entity/vessel recognition array testing nominee directors and bulk-cash couriers)

---

## 4. Training & Evaluation Pipeline (Cloud GPU Ready)

1. **Stage 1 — Supervised Fine-Tuning (SFT):** Train open-weight base (`Qwen 2.5 / Qwen 3 7B–32B` or `Llama 3.3`) on unified `messages` shards (`training/datasets/v1_50k/`).
2. **Stage 2 — RLVR / GRPO (`training/rlvr_rewards.py`):** Optimize directly against deterministic Python verifiers:
   - `+0.35` zero dropped quotes (`quote_ok` 100% pass),
   - `+0.25` exact alibi / typology / triage priority match against `ground_truth`,
   - `+0.20` exact Lead Detective rubric arithmetic & zero Prosecutor veto violations,
   - `+0.20` mandatory `innocent_alternative` present (and `-1.0` cliff penalty on Othello-error false accusations).
3. **Stage 3 — Real-World Gate (`CrimeOwl.ai` & De-Spoiled Real Cold Cases):** Once sim and `TurnaboutLLM`/`MuSR` benchmarks pass, deploy the GraphRAG + Retrieval squad onto real public cold-case files (`CrimeOwl.ai`).
