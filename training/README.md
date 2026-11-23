# Murder Board — Specialist Investigator AI Training Factory (`SPEC 7`)

Everything in `training/` builds the training data, 10GB-capped streaming adapters, and RLVR/GRPO reward functions for **Now (Desk / Archive Retrieval)** and **Future (In-Room Biometric Co-Pilot)** Investigator LLMs—without modifying any existing Murder Board demo files (`app/`, `agents/`, `case*`).

## Architecture Overview

1. **`training/common/`** — Collision-free SHA-256 split-isolated RNG, exact ports of `app/app.js` `quote_ok()` and `recompute_score()`, Prosecutor veto checks, Almanac weather/moon/transit generator, and `WESAD`/`rPPG`-calibrated physiological curves.
2. **`training/track1_now/`** (Desk & Telemetry — Ready Today):
   - `murder_board_sim.py` — Full 11-chair Murder Board cases (10 venue archetypes, 4-link survival-floor window narrowing, cleared red-herring liars, statement drift, fake insider knowledge, CSI gaps, 20% insufficient-evidence holds, `0` quote drops).
   - `noisy_vault_retrieval.py` — Multi-hop tool-calling detective trajectories over 80–120 noisy binder exhibits + Entity Graph + Historical Almanac checks.
   - `forensic_micro_skills.py` — 8 foundational drills (Temporal/DVR clock skew math, 3-way Forensic NLI, GraphRAG entity/alias triples, same-name collision guard, pathology/modern DNA re-testing, cell-sector/keypad literacy, 3-theory hypothesis tournaments, fake insider knowledge).
   - `dispatch_911_sim.py` — 18 emergency sub-archetypes (coerced callers, cardiac agonal gasps, opioid M-30, stroke window, submerging car physics, 13.8kV downed-wire step potential, CO clusters, DTMF silent distress, VOIP swatting premise mismatches).
   - `aml_hunter_sim.py` — 6 money-laundering & shell-network playbooks + 20% `CLEAR_NO_SAR` high-dollar legitimate false-positive controls + FIU registry/utility tool trajectories.
3. **`training/track2_future/`** (The 12th Chair — In-Room Biometric & Cognitive-Load Co-Pilot):
   - `12_room_copilot.md` + `interrogation_room_sim.py` — Synchronized `rPPG` (`HR`, `HRV RMSSD`), `EDA` sweat (`µS`), periorbital thermal, pupil dilation, vocal jitter, and response latency across Homicide Rooms, 911/Bodycam Voice-Stress Triage, and AML/Customs Secondary Inspections, hardened with **35% Othello-Error terrified innocent controls**.
4. **`training/real_archives/`** — Live public historical & modern harvester + verdict de-spoiler (`Old Bailey 1700s–1913`, `DOJ Homicide & AML`, `Treasury OFAC SDN`, `2005–2026 FDNY/NYC & SFPD/Seattle 911 CAD`, and in-memory de-spoiled `duck-2020`).
5. **`training/external_adapters/`** — Streaming `<= 10 GB` batch converters + resumable checkpoints for `DetectiveQA`, `MuSR`, `TurnaboutLLM`, `WhodunitBench`, `FEVER`/`ContractNLI`, `MuSiQue`, `DocRED`, `TORQUE`, and `WESAD`.
6. **`training/rlvr_rewards.py`** — Verifiable reward suite for GRPO/RL training (including the `-1.0` Othello-error false-accusation cliff).

## Quick Commands (Run from `/Users/test/Desktop/murder-board`)

```bash
# Run unit tests
python3 -m unittest discover -s training/tests -v

# Build full ~52,000-example Batch-1 corpus (<0.5 GB on disk, ~80M+ tokens)
python3 -m training.build_factory_corpus --out-dir training/datasets/v1_50k

# Exhaustively verify every shard (0 quote drops, 0 split collisions, <10 GB budget)
python3 -m training.verify_factory_corpus training/datasets/v1_50k
```
