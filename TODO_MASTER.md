# MASTER BUILD CHECKLIST — Investigator AI Training Factory (130 TODOs)

Home directory: `/Users/test/Desktop/murder-board/`
Target output: `/Users/test/Desktop/murder-board/training/` (zero modifications to existing demo app files)

## Phase 1 — Specifications, Architecture & Link Preservation (12 items)
- [x] 001. Inspect existing `murder-board` repo (`AGENTS.md`, `PROMPTS.md`, `SPEC.md..SPEC6.md`, `REALISM.md`, `app/app.js`).
- [x] 002. Verify git status of `/Users/test/Desktop/murder-board` so zero existing hackathon/demo files are overwritten.
- [x] 003. Write `SPEC7_TRAINING_FACTORY.md` uniting Track 1 (Now: Desk/Vault Retrieval) and Track 2 (Future: Biometric Room Co-Pilot).
- [x] 004. Catalog all 7 unbuilt Specialist AI roles (#1 Detective, #2 911, #3 AML, #4 Crash/Arson, #5 Outbreak, #6 Dark Fleet, #7 Bid-Rigging).
- [x] 005. Save `CrimeOwl.ai` cold-case platform links in `SOURCES_AND_LINKS.md` without downloading external weights.
- [x] 006. Save `DetectiveQA`, `MuSR`, `TurnaboutLLM`, and `WhodunitBench` dataset/paper links in `SOURCES_AND_LINKS.md`.
- [x] 007. Save Temporal (`TORQUE`, `TimeQA`, `TempReason`), NLI (`FEVER`, `MuSiQue`, `ContractNLI`), and Graph (`DocRED`, `OntoNotes`) links.
- [x] 008. Save Biometric & Deception calibration links (`WESAD`, `Bag-of-Lies`, `Real-Life Trial Deception`, `MU3D`, `UBFC-rPPG`).
- [x] 009. Save all verified live municipal 911 CAD, Old Bailey, DOJ, and Treasury OFAC API endpoints.
- [ ] 010. Write `training/README.md` documenting CLI commands, shard schemas, SFT format, and RLVR reward hooks.
- [ ] 011. Write Chair 12 agent specification `training/track2_future/12_room_copilot.md` matching `agents/01..11` house-rule style.
- [ ] 012. Consolidate/sync work from `/Users/test/investigator-llms` so `/Users/test/Desktop/murder-board` holds the complete factory.

## Phase 2 — Core Shared Procedural & Validation Library (`training/common/`) (14 items)
- [ ] 013. Create `training/__init__.py` and `training/common/__init__.py`.
- [ ] 014. Implement SHA-256 deterministic split-isolated seed generator (`train`, `val`, `test` mathematically disjoint).
- [ ] 015. Port exact `quote_ok(quote, doc_id, docs_by_id)` from `app/app.js` (`norm(quote) >= 8` chars, whitespace-normalized substring).
- [ ] 016. Port exact `recompute_score(components)` (`+40` high contradiction, `+25` in window, `+20` closes gap, `+15` reachable).
- [ ] 017. Implement Prosecutor veto scanner verifying zero forbidden phrases leak into any generated Lead Detective brief.
- [ ] 018. Expand procedural name pools to 120+ first names and 120+ surnames across diverse backgrounds + realistic nickname/alias maps.
- [ ] 019. Build procedural county, street, corridor, zip, coordinate, and Euclidean-to-road transit time calculator.
- [ ] 020. Build vehicle registry pool (25+ realistic makes/models/years/body styles/plate generators).
- [ ] 021. Build historical Almanac generator (weather, precipitation, moon phase/illumination %, sunset time, transit schedules, city inspections).
- [ ] 022. Build OCR/scan/typewriter grit & ASR speech disfluency mutators (preserving quoted spans where required).
- [ ] 023. Build corporate entity, registered-agent address, commodity benchmark, and offshore jurisdiction pools.
- [ ] 024. Build physiological baseline & autonomic response curves (`HR`, `HRV RMSSD`, `EDA µS`, periorbital `°C`, pupil `mm`, vocal jitter) grounded in `WESAD` / `CIT` ranges.
- [ ] 025. Add strict JSON schema validators for Track 1 (all 11 chairs + vault tool calls) and Track 2 (Chair 12 biometric turns).
- [ ] 026. Unit-test `training/common/` validators, RNG isolation, and quote checker.

## Phase 3 — Track 1A: Murder-Board 11-Chair Cold-Case Simulator (`murder_board_sim.py`) (16 items)
- [ ] 027. Load live prompts directly from `/Users/test/Desktop/murder-board/agents/01_first_officer.md` .. `11_lead_detective.md`.
- [ ] 028. Expand venue archetypes to 10+ distinct realistic settings (cold storage, auto body, bowling lounge, marina, textile mill, night diner, freight depot, motel, pharmacy warehouse, scrap yard).
- [ ] 029. Generate realistic agency document chrome, complaint numbers, and Bates footers (`REALISM.md` §1.2).
- [ ] 030. Implement 4-link survival-floor death-window narrowing (ME wide window narrowed by verified outgoing text/call + door credential).
- [ ] 031. Plant loud high-motive red-herring suspects who lie in Year 1, get caught by ALPR/toll/tow logs, and are cleared of the narrowed window.
- [ ] 032. Plant longitudinal multi-year statement drift (`MEDIUM` severity) across 2–3 interviews with benign memory-decay `innocent_alternative`.
- [ ] 033. Plant fake "killer-only knowledge" news/tip items neutralized by prior public municipal inspection filings.
- [ ] 034. Plant CSI physical count discrepancies (scene report counts 2; property ledger logs 1) + uncollected EXIF media + unpulled exterior cameras.
- [ ] 035. Implement `INSUFFICIENT_EVIDENCE` holdout cases (~20% of sim cases) where no suspect's window alibi is broken yet.
- [ ] 036. Emit verified `custody`, `records`, `coroner`, and `csi` chair training turns.
- [ ] 037. Emit verified `intake`, `analyst`, and `digital` chair training turns (distinguishing code entry from biometric proof, ping radius from dot).
- [ ] 038. Emit verified `cross_examiner` and `interviewer` chair turns (quote-anchored funnel questions).
- [ ] 039. Emit verified `prosecutor` and `lead_detective` chair turns ending with `"This board judges the file. The detective does the detecting."`
- [ ] 040. Assert 0 quote-check drops across every generated 11-chair bundle at generation time.
- [ ] 041. Build exporter writing playable Murder-Board case folders (`doc01..doc16` + `registry.json` + `golden_outputs.json`).
- [ ] 042. Verify exported synthetic cases against `/Users/test/Desktop/murder-board/app/app.js` validator rules.

## Phase 4 — Track 1B: Active Vault Retrieval, GraphRAG & Almanac Engine (`noisy_vault_retrieval.py`) (14 items)
- [ ] 043. Design tool-calling schema (`search_vault`, `read_document`, `query_entity_graph`, `check_almanac`, `diff_statements`, `submit_findings`).
- [ ] 044. Generate 60–120 background clutter exhibits per vault (uninvolved employee timecards, negative neighborhood canvasses, irrelevant caller rows, junk tips).
- [ ] 045. Plant Almanac traps (witness claims clear moonlight at 11:15 PM vs. Almanac overcast + 4% waning crescent; claims rain after ballgame vs. dry weather + 9:40 PM game end).
- [ ] 046. Build multi-hop Entity Graph per vault (`Person -> Alias -> Vehicle/Plate -> Shared PO Box -> LLC -> Uninterviewed Subject`).
- [ ] 047. Hide key peripheral records (tow slip, smart meter, bridge ALPR, public inspection) behind targeted retrieval queries rather than Turn-0 context.
- [ ] 048. Synthesize optimal multi-turn detective trajectories (`<think>` hypothesis update -> tool call -> observation -> next hop).
- [ ] 049. Include dead-end search turns (negative results) so the model learns resilient re-querying instead of giving up or hallucinating.
- [ ] 050. Include unsolvable missing-record vaults where the agent must stop and emit an exact subpoena/records shopping list.
- [ ] 051. Enforce `quote_ok()` against retrieved vault documents on the final `submit_findings` payload.
- [ ] 052. Format multi-turn tool trajectories into standard `messages` + `tools` JSONL compatible with Qwen/Llama tool-use SFT.
- [ ] 053. Include `ground_truth` hop-efficiency and clue-recall targets for RLVR trajectory grading.
- [ ] 054. Add Columbo "Proxy Interrogation Funnel" output when an archival gap can only be closed by a human interview.
- [ ] 055. Test deterministic replay of vault search sessions across `train`/`val`/`test`.
- [ ] 056. Benchmark token length distribution of multi-hop vault trajectories.

## Phase 5 — Track 1C: The 5 Foundational Forensic Micro-Skill Drills (`forensic_micro_skills.py`) (12 items)
- [ ] 057. Drill 1 (`temporal_clock_math`): Relative witness time + DVR clock skew / DST offset + road-distance transit math -> ISO-8601 window & collision verdict.
- [ ] 058. Drill 2 (`forensic_nli`): Multi-hop claim verification outputting strict `SUPPORTED` / `REFUTED` / `NOT_ENOUGH_INFORMATION` + verbatim quote spans.
- [ ] 059. Drill 3 (`entity_resolution_graph`): Alias, nickname, maiden name, partial plate, and phone linking into JSON graph triples.
- [ ] 060. Drill 3b (`name_collision_guard`): Same-name different-DOB/address traps teaching `NEVER_MERGE_WITHOUT_PROOF`.
- [ ] 061. Drill 4 (`pathology_and_trace`): Lividity fixation vs. moved-body detection, rigor/algor bounds, and legacy serology -> modern `M-VAC`/`STRmix`/`IGG`/`NIBIN` retest selection.
- [ ] 062. Drill 4b (`digital_machine_literacy`): Cell-sector azimuth/radius vs. pinpoint error, keypad entry-only vs. exit gap, EXIF stripped screenshot vs. original file.
- [ ] 063. Drill 5 (`hypothesis_tournament`): Scoring 3 competing case theories (`explained_facts`, `unexplained_gaps`, `contradicting_records`) to break tunnel vision.
- [ ] 064. Drill 5b (`fake_insider_knowledge`): Auditing putative "killer-only details" against prior public dockets/press releases.
- [ ] 065. Ensure every micro-skill drill enforces Murder-Board house rules (no guilt labels, verbatim quotes).
- [ ] 066. Balance positive, refuted, and `NOT_ENOUGH_INFORMATION` labels (~33% each) on NLI drills.
- [ ] 067. Add `ground_truth` exact answer keys on all 5 micro-skill families for RLVR.
- [ ] 068. Unit-test all 5 micro-skill generators.

## Phase 6 — Track 1D: 911 Triage & Cartel/Shell AML Simulators (`dispatch_911_sim.py`, `aml_hunter_sim.py`) (18 items)
- [ ] 069. Expand 911 coerced-caller ruses (pizza order, hair salon, wrong-number utility, ride-share pickup, pretend "wrong apartment" call, Spanish/English code-switch).
- [ ] 070. Expand 911 deadly medical traps (cardiac agonal gasps = "snoring", opioid M-30 apnea, stroke Last-Known-Well window, pediatric choking vs. croup, anaphylaxis, arterial tourniquet).
- [ ] 071. Expand 911 unknown-location triangulation (flooding ditch milepost math, child caller knowing school/landmarks only, trunk abduction turn/rumble-strip counting).
- [ ] 072. Expand 911 physical/environmental hazards (13.8kV downed wire on car step-potential electrocution, odorless carbon monoxide multi-occupant headache/confusion, apartment fire floor conflict).
- [ ] 073. Expand 911 silent-line & swatting protocols (intentional double-DTMF distress vs. retail pocket-dial; VOIP swatting claiming 3rd-floor/basement at verified 1-story slab ranch).
- [ ] 074. Add multi-turn streaming 911 update trajectories (Turn 1 vague intake -> Turn 2 dispatcher <=18-word probe -> Turn 3 acoustic/caller reveal -> priority upgrade).
- [ ] 075. Enforce strict `<= 18 words` cap on every `next_dispatcher_line`.
- [ ] 076. Expand AML Typology 1: Multi-branch `<$10,000` smurfing + zero-payroll funnel shell (<30 days old, >95% 24hr velocity).
- [ ] 077. Expand AML Typology 2: Trade-Based Money Laundering (`$/kg` 10x–35x over-invoicing & Bill-of-Lading container gross-weight physical impossibilities across 12 commodities).
- [ ] 078. Expand AML Typology 3: Multi-jurisdiction Delaware/Wyoming/BVI/Panama/UAE shell round-trips (27-hour formation bursts, shared registered agent suites, fake IP/loan loops).
- [ ] 079. Expand AML Typology 4: Cash-intensive front co-mingling (car washes, coin laundries, nail spas, parking lots, vending fleets vs. municipal water/kwh/linen physical capacity).
- [ ] 080. Expand AML Typology 5: P2P/ACH mule fan-in -> stablecoin OTC desk / high-risk trade settlement.
- [ ] 081. Expand AML Typology 6: All-cash shell LLC commercial real-estate integration & ghost-vendor procurement kickbacks.
- [ ] 082. Include 20% completely clean `CLEAR_NO_SAR` packets featuring high-dollar legitimate wires (heavy equipment liens, street-festival POS surges, dental scanners, lease escrows).
- [ ] 083. Require every AML `<audit>` trace to show explicit unit-price, cash-split, and capacity arithmetic.
- [ ] 084. Require verbatim ledger/annex quote grounding in AML findings.
- [ ] 085. Add multi-step AML investigative tool trajectories (`query_ubo_registry`, `check_commodity_spot`, `pull_utility_meter`).
- [ ] 086. Unit-test 911 and AML simulators across 500 random seeds.

## Phase 7 — Track 2 (FUTURE): In-Room Biometric & Cognitive-Load Co-Pilot (`interrogation_room_sim.py`) (18 items)
- [ ] 087. Write `12_room_copilot.md` prompt codifying non-accusatory psychophysiological doctrine & mandatory Othello-error guardrails.
- [ ] 088. Implement realistic baseline physiological generator (`HR 58–95 BPM`, `HRV RMSSD 24–68 ms`, `EDA 1.0–3.5 µS`, `resp 12–18 RPM`, latency `450–900 ms`).
- [ ] 089. Implement **Archetype 1 (35%): Calm Rehearsed Concealer** — flat baseline on direct blame questions; autonomic collapse (`HRV` drop, `EDA` phasic burst, pupil dilation, latency jump) on withheld CIT stimulus & reverse-order recall.
- [ ] 090. Implement **Archetype 2 (35%): Othello-Error Terrified Innocent** — elevated sweat (`EDA 5.5–9.5 µS`) & tachycardia (`115–138 BPM`) across *both* control and crime questions (or spiking on an embarrassing non-crime secret), cleared via checkable peripheral detail + record match.
- [ ] 091. Implement **Archetype 3 (30%): Traumatized Cooperative Witness** — sympathetic spikes during sensory trauma recall; Co-Pilot recommends open PEACE / Cognitive Interview support, zero pressure.
- [ ] 092. Build 5-item **Concealed Information Test (CIT)** protocol turns (1 withheld crime-scene artifact embedded among 4 matched control items -> measuring stimulus-locked `Z-score` across `HRV`, `EDA`, `pupil`).
- [ ] 093. Build **Reverse-Chronology & Spatial-Sketch Cognitive Load** turns (testing rehearsed forward alibis by asking backward step-by-step recall).
- [ ] 094. Fuse Track 2 room telemetry directly with `Murder Board` case documents (`doc05` keypad, `doc09` ALPR, `doc11` smart meter) so physiological spikes trigger exact file cross-checks.
- [ ] 095. Extend Track 2 to **Future 911 / Bodycam Voice-Stress & rPPG Triage** (detecting coerced "forced-calm" caller via `140+ BPM` vocal micro-tremor & breath suppression vs. calm swatting hoax).
- [ ] 096. Extend Track 2 to **Future AML / Customs Secondary Inspection** (nominee director / cash courier shown 6 shell-LLC or vessel names -> stimulus-locked recognition spike on hidden syndicate node).
- [ ] 097. Enforce mandatory `innocent_physiological_alternative` field on every single Track 2 turn.
- [ ] 098. Enforce hard prohibition on phrases `"biometrics prove lying"` / `"sweat confirms guilt"`.
- [ ] 099. Emit both single-turn real-time room state evaluations and multi-turn adaptive questioning trajectories.
- [ ] 100. Populate `ground_truth` with `true_subject_state` (`CONCEALING_CASE_FACT`, `OTHELLO_INNOCENT_ANXIOUS`, `OTHELLO_EMBARRASSED_SECRET`, `TRAUMA_WITNESS`) for RLVR reward cliffs.
- [ ] 101. Validate physiological numbers stay within human biological bounds on 1,000 random turns.
- [ ] 102. Unit-test Track 2 room engine across Homicide, 911, and AML room modes.
- [ ] 103. Export sample room session transcripts for human review.
- [ ] 104. Verify zero prompt/seed overlap across `train`/`val`/`test` splits in Track 2.

## Phase 8 — Real De-Spoiled Historical & Modern Archives (`harvest_and_despoil.py`) (12 items)
- [ ] 105. Build clean in-memory **De-Spoiler for `/Users/test/Desktop/murder-board/case4` (`duck-2020`)** removing `doc11`/`doc12` verdict spoilers while keeping primary surveillance/phone/vehicle exhibits intact.
- [ ] 106. Import gold benchmark turns from `delgado-2019`, `screens-2025`, `harborlight-2016`, and `starlite-2017` caches.
- [ ] 107. Scale Old Bailey (1700s–1913) murder & manslaughter harvester across multiple decades (`GUILTY` and `NOT GUILTY` verdicts stripped to `ground_truth`).
- [ ] 108. Split Old Bailey HTML transcripts into witness, constable, and post-mortem surgeon Murder-Board documents (`doc01..docN`) and verify every extracted quote with `quote_ok()`.
- [ ] 109. Scale DOJ Federal Homicide / Cold-Case / Violent-Crime factual harvester (`justice.gov` API, de-spoiling pleas/sentences).
- [ ] 110. Scale DOJ Money-Laundering, Cartel Funnel, TBML & Shell-Company harvester across multiple pages (`justice.gov` API, de-spoiled).
- [ ] 111. Harvest real US Treasury OFAC SDN cartel/front-company entity names & offshore addresses (`treasury.gov` public CSV slice) to enrich real-world AML corporate graph realism.
- [ ] 112. Scale FDNY/NYC 911 EMS historical (2005–2010) + modern (2025–2026) triage escalation calls (`initial_call_type != final_call_type`) + matched non-escalated baselines.
- [ ] 113. Scale SFPD 2026 Police 911 reclassified calls (`call_type_original != call_type_final`) + Seattle Fire 911 dispatches.
- [ ] 114. Cache all HTTP JSON/CSV responses in `training/datasets/raw_cache/` for instant offline rebuilds.
- [ ] 115. Deduplicate all real archival records by canonical source ID and isolate across `train`/`val`/`test`.
- [ ] 116. Audit 100% of harvested real turns for spoiler removal and schema compliance.

## Phase 9 — RLVR / GRPO Reward Suite, Massive 50K+ Corpus Build & Final Audit (14 items)
- [ ] 117. Build `training/rlvr_rewards.py` — self-contained verifiable reward functions (`score_murder_board_turn`, `score_vault_trajectory`, `score_911_turn`, `score_aml_turn`, `score_track2_room_turn` with `-1.0` Othello-error cliff).
- [ ] 118. Test `rlvr_rewards.py` on gold outputs (must score `1.0`) vs. corrupted/hallucinated/Othello-violating outputs (must penalize accurately).
- [ ] 119. Build `training/build_factory_corpus.py` — multi-core parallel orchestrator combining Track 1 (11-Chair + Noisy Vault + Micro-Skills + 911 + AML), Track 2 (Future Room Co-Pilot), and Real De-Spoiled Archives.
- [ ] 120. Build `training/verify_factory_corpus.py` — exhaustive shard auditor checking JSON validity, `quote_ok()` zero drops, Prosecutor vetoes, `<=18` word 911 caps, biological bounds, split isolation, and token counts.
- [ ] 121. Build `training/tests/test_all.py` covering every module, verifier, and reward function.
- [ ] 122. Run `test_all.py` and confirm 100% pass.
- [ ] 123. Run scaled real-archive harvest (`Old Bailey` + `DOJ Homicide` + `DOJ AML` + `OFAC` + `NYC/SF/Seattle 911` + de-spoiled `duck-2020`).
- [ ] 124. Execute massive multi-core generation producing **50,000+ verified training examples (~75M–95M tokens)** in `training/datasets/v1_50k/`.
- [ ] 125. Export 12 brand-new playable synthetic Murder-Board case directories under `training/datasets/v1_50k/playable_murder_board_cases/`.
- [ ] 126. Run `verify_factory_corpus.py` across all 50,000+ examples and confirm **0 quote drops**, **0 split collisions**, and **0 schema errors**.
- [ ] 127. Run `rlvr_rewards.py` self-audit across a random 1,000-row sample of `v1_50k` confirming deterministic `1.0` reward on ground-truth completions.
- [ ] 128. Generate `training/datasets/v1_50k/DATASET_CARD.md` with exact domain/track/split counts, token histograms, and Axolotl / Unsloth / TRL GRPO launch configs.
- [ ] 129. Clean up temporary staging directories and verify `/Users/test/Desktop/murder-board` existing app (`node -c app/app.js`) remains 100% untouched and healthy.
- [ ] 130. Mark all 130 checklist items complete in `TODO_MASTER.md` with final verified metrics.
