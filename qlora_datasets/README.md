# Murder Board — Standalone Strict QLoRA ChatML Datasets (`qlora_datasets/`)

Clean, standalone, PyArrow/HuggingFace/Unsloth/Axolotl/LLaMA-Factory/TRL QLoRA training folders.
Every single JSONL line across all 4 folders and 12 split files contains **only** the uniform key:

```json
{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
```

- **Zero extra top-level columns** (no heterogeneous `ground_truth`, `tools`, or UI metadata that breaks PyArrow schema inference).
- **Strict role alternation** (`system` optional -> `user` -> `assistant` -> `user` -> `assistant`, always ending on `assistant`).
- **100% verified by `verify_strict_qlora_folder`** from `training/export_qlora_folders.py`.
- **Total Rows:** `51,631` (`50,990` procedural + `641` de-spoiled `real_v1` historical/modern archive rows).
- **Total Disk Usage:** `612.14 MB` (`0.5978 GB` — verified strictly `< 1 GB` and `< 10 GB`).

---

## Folder Overview

| Folder | Train Rows | Val Rows | Test Rows | Total Rows | Real `real_v1` Rows | Size (MB) | `verify_strict_qlora_folder` |
|---|---:|---:|---:|---:|---:|---:|:---:|
| `01_cold_case_detective/` | 21,708 | 1,237 | 1,239 | **24,184** | 214 | **391.65 MB** | PASSED |
| `02_911_triage_dispatch/` | 8,296 | 475 | 469 | **9,240** | 240 | **43.97 MB** | PASSED |
| `03_aml_laundering_hunter/` | 8,261 | 473 | 473 | **9,207** | 187 | **66.83 MB** | PASSED |
| `04_future_biometric_room/` | 8,000 | 500 | 500 | **9,000** | 0 | **109.69 MB** | PASSED |
| **TOTAL** | **46,265** | **2,685** | **2,681** | **51,631** | **641** | **612.14 MB** | **100% PASSED** |

---

## Exact Split File Manifest & SHA-256 Hashes

| File Path | Total Rows | Procedural Rows | Real Archive Rows | Size (MB) | SHA-256 |
|---|---:|---:|---:|---:|---|
| `01_cold_case_detective/train.jsonl` | 21,708 | 21,520 | 188 | 352.32 MB | `a37a8a15d2a11e38e4336510e23638fb6cfdca7bc723ef531dae9903f649c676` |
| `01_cold_case_detective/val.jsonl` | 1,237 | 1,225 | 12 | 19.64 MB | `2b50f2d4192d5cb919efd0b1e6aae8e9839a6bdc09f4eada53dd2cec144215a6` |
| `01_cold_case_detective/test.jsonl` | 1,239 | 1,225 | 14 | 19.68 MB | `6b5d7df2590f5d93a1192aeca09d8a768c3061d1162504f3fc778c8f9734e909` |
| `02_911_triage_dispatch/train.jsonl` | 8,296 | 8,100 | 196 | 39.52 MB | `3952a8c4c26c6b6139164c6f95e0a1a9e3497173ffa0ef34a5e9e84589d9f292` |
| `02_911_triage_dispatch/val.jsonl` | 475 | 450 | 25 | 2.24 MB | `46d8a9405bf513cbcacfd3e234be679853ef2116b7acf05e42fc1ab9dd8cc528` |
| `02_911_triage_dispatch/test.jsonl` | 469 | 450 | 19 | 2.21 MB | `1fa750eace0dca6c6f06a475da416c9f3bfeee31b78afe760a6babbcdc02b7b5` |
| `03_aml_laundering_hunter/train.jsonl` | 8,261 | 8,100 | 161 | 59.94 MB | `4af7a710d5a1a4f4a6c79a7f96ad474ccf294ab6a8e843bd01c68ffea38effdf` |
| `03_aml_laundering_hunter/val.jsonl` | 473 | 460 | 13 | 3.45 MB | `61915d8ba5d23f29036373372b10eb3a500a8145ca53a2b9badf526120fb1541` |
| `03_aml_laundering_hunter/test.jsonl` | 473 | 460 | 13 | 3.44 MB | `1170c4d1bf6b6a352a80ddc3819b5548570709727f323470445ce460881c9062` |
| `04_future_biometric_room/train.jsonl` | 8,000 | 8,000 | 0 | 97.50 MB | `262ddd42f58e2510531510decf63f1618023d7d7e0f15ea7b0dbbde0696d8ac0` |
| `04_future_biometric_room/val.jsonl` | 500 | 500 | 0 | 6.10 MB | `9f467974cb380b07714bb811f1c704c2c25c74a84567ef2ee07df3bc2bba8245` |
| `04_future_biometric_room/test.jsonl` | 500 | 500 | 0 | 6.09 MB | `b3d8a8791631fed0c1ff85bb11c6380d4bb23935bf4b230541daa344d79eadfd` |

---

## Domain & Source Composition

1. **`01_cold_case_detective/`**
   - `murder_board_sim`: All 11 Murder-Board chairs (`01_first_officer` .. `11_lead_detective`) across 10 venue archetypes, 80% actionable 4-link record chains + 20% archival holdouts.
   - `noisy_vault_retrieval`: Multi-hop tool-use trajectories (`search_vault`, `query_entity_graph`, `read_document`, `check_almanac`, `diff_statements`, `submit_findings`) over 80–120 document vaults.
   - `forensic_micro_skills`: All 8 forensic micro-skill drills (`temporal_clock_math`, `forensic_nli`, `entity_resolution_graph`, `name_collision_guard`, `pathology_and_trace`, `digital_machine_literacy`, `hypothesis_tournament`, `fake_insider_knowledge`).
   - `real_v1`: De-spoiled Old Bailey (1674–1913) homicide trials, DOJ homicide press releases, and playable Case 4 (`duck-2020`) turns.
2. **`02_911_triage_dispatch/`**
   - `dispatch_911_sim`: 21 high-stakes emergency dispatch sub-archetypes (coerced pizza/salon/utility/rideshare/bilingual ruses, agonal breathing traps, fentanyl apnea, stroke LKW, submerging vehicle, downed 13.8kV wire, CO poisoning, VOIP swatting) with strict `<= 18`-word `next_dispatcher_line`.
   - `real_v1`: Real 2005–2026 FDNY/NYC EMS, SFPD, and Seattle 911 CAD triage rows.
3. **`03_aml_laundering_hunter/`**
   - `aml_hunter_sim`: 6 laundering typologies (`SMURFING_FUNNEL`, `TBML_INVOICE_AND_WEIGHT_MISMATCH`, `LAYERED_SHELL_ROUND_TRIP`, `CASH_FRONT_UTILITY_MISMATCH`, `CRYPTO_PEEL_AND_OTC_SETTLEMENT`, `ALL_CASH_REAL_ESTATE_NOMINEE`) + 20% `CLEAR_NO_SAR` legitimate business false-positive clearances across static and tool-use trajectories.
   - `real_v1`: De-spoiled DOJ money-laundering / forfeiture / TBML cases & OFAC SDN sanctions-evasion rows.
4. **`04_future_biometric_room/`**
   - `interrogation_room_sim`: Chair 12 synchronized rPPG heart rate, vagal HRV RMSSD, phasic EDA, periorbital thermal delta, pupil dilation, and acoustic latency across Homicide Interview, 911 Bodycam Triage, and AML/Customs Secondary Inspection.
   - Hardened against the **Othello Error** (`35%` concealing CIT hit, `35%` innocent anxious / embarrassed Othello controls, `30%` trauma cooperative witnesses) with mandatory `innocent_physiological_alternative` on every turn.

## Quick Load Example (HuggingFace `datasets` / Unsloth / TRL)

```python
from datasets import load_dataset

ds = load_dataset("json", data_dir="qlora_datasets/01_cold_case_detective")
print(ds)
```
