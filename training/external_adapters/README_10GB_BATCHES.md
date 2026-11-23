# Phased `<10 GB` External Dataset & Sequential LoRA / QLoRA / GRPO Plan

This guide implements the **zero-bloat `<10 GB` streaming training workflow** for SPEC 7 (`Murder Board`).
No external datasets are bundled or auto-downloaded in this repository. On a cloud GPU box (or local workstation with tight NVMe quota), you pull, convert, train, and purge **one `<10 GB` window at a time** using `BatchBudgetGuard(max_bytes=int(9.5 * 1024**3))` and atomic `cursor_checkpoint.json` resumption.

---

## 0. Offline Pre-Flight Self-Tests (Zero Network, `<1s`)

Run both stdlib self-tests from `/Users/test/Desktop/murder-board` before touching cloud storage:

```bash
cd /Users/test/Desktop/murder-board
python3 -m training.external_adapters.chunked_10gb_adapters --self-test
python3 -m training.rlvr_rewards --self-test
```

---

## 1. Master `<10 GB` Batch Schedule

| Batch | Corpora Included | Peak Disk (Raw + JSONL) | Target Skills Trained | Adapter Stage |
|---|---|---:|---|---|
| **Batch 1** | Core SPEC 7 Sim (`v1_50k`) + De-Spoiled Real Archives (`Old Bailey`, `DOJ`, `911 CAD`, `duck-2020`) | **`< 1.0 GB`** (~0.45 GB) | 11-Chair Murder Board, Noisy Vault + Almanac, 911 <=18w Triage, AML/TBML Hunter, Chair 12 Biometrics | `adapter_b1_core` (QLoRA / DoRA Base) |
| **Batch 2** | `DetectiveQA` + `MuSR` + `TurnaboutLLM` + `WhodunitBench` | **`< 2.0 GB`** (~1.4 GB) | 100K-token clue anchoring, neurosymbolic means/window trees, testimony-vs-exhibit contradiction spotting | `adapter_b2_deductive` (Continue from B1) |
| **Batch 3** | `FEVER` + `MuSiQue` + `ContractNLI` + `DocRED` + `TORQUE` | **`< 6.0 GB`** (~5.2 GB) | Strict `SUPPORTED/REFUTED/NEI` NLI, 2–4 hop vault chains, GraphRAG + `DO_NOT_MERGE_COLLISION`, ISO clock-skew math | `adapter_b3_forensic` (Continue from B2) |
| **Batch 4** | `WESAD` + Multimodal Deception (`Bag-of-Lies`, `Real-Life Trial`, `MU3D`, `UBFC-rPPG` feature windows) | **`< 5.0 GB`** (~4.1 GB) | Baseline-adjusted `rPPG/HRV/EDA` deltas, CIT 5-item orienting probes, **Othello-Error `-1.0` cliff** immunity | `adapter_b4_room_chair12` + **GRPO RLVR** |

Every converted shard enforces **House Rule #3** (`sanitize_investigative_prose` strips *"is guilty"*, *"is the killer"*, *"is lying"*, *"murdered"*, and attaches mandatory `innocent_alternative` fields) and **House Rule #2** (`quote_ok()` verbatim span verification).

---

## 2. Step-by-Step Copy-Paste Commands

### Batch 1 — Core Sim + De-Spoiled Real Archives (`< 1 GB`)

```bash
cd /Users/test/Desktop/murder-board

# 1. Generate 50k+ multi-domain synthetic + de-spoiled archive shards (< 500 MB)
python3 -m training.build_factory_corpus \
  --out-dir training/datasets/v1_50k \
  --real-dir training/datasets/real_v1 \
  --scale 1.0

# 2. Verify <10 GB ceiling, zero split leakage, zero quote drops, <=18w 911 lines, and Othello guards
python3 -m training.verify_factory_corpus training/datasets/v1_50k

# 3. Export clean ChatML QLoRA folders (Unsloth / Axolotl / LLaMA-Factory / TRL ready)
python3 -m training.export_qlora_folders

# 4. Train Stage-1 QLoRA / DoRA checkpoint (example: TRL SFTTrainer on Qwen2.5-14B-Instruct)
trl sft \
  --model_name_or_path Qwen/Qwen2.5-14B-Instruct \
  --dataset_name training/datasets/v1_50k/train \
  --use_peft --lora_r 64 --lora_alpha 128 --use_dora \
  --load_in_4bit \
  --max_seq_length 16384 \
  --output_dir checkpoints/adapter_b1_core
```

---

### Batch 2 — Deductive & Contradiction Benchmarks (`< 2 GB`)

Download `DetectiveQA`, `MuSR`, `TurnaboutLLM`, and `WhodunitBench` JSON/JSONL exports into `/tmp/raw_batch2`, stream-convert under a single shared `9.5 GiB` `BatchBudgetGuard`, train `adapter_b2_deductive`, then delete `/tmp/raw_batch2`:

```bash
mkdir -p /tmp/raw_batch2 training/datasets/batch2_deductive/train

# Convert DetectiveQA (long-context clue citation + non-accusatory option analysis)
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset detectiveqa \
  --input /tmp/raw_batch2/detectiveqa_train.json \
  --output training/datasets/batch2_deductive/train/detectiveqa.jsonl \
  --checkpoint training/datasets/batch2_deductive/cursor_checkpoint.json \
  --batch-id batch_02 \
  --max-gb 9.5 --split train

# Convert MuSR (neurosymbolic hypothesis tournament ranking)
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset musr \
  --input /tmp/raw_batch2/musr_murder_mysteries.jsonl \
  --output training/datasets/batch2_deductive/train/musr.jsonl \
  --checkpoint training/datasets/batch2_deductive/cursor_checkpoint.json \
  --batch-id batch_02 \
  --max-gb 9.5 --split train

# Convert TurnaboutLLM (statement-vs-exhibit Cross-Examiner contradictions)
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset turnaboutllm \
  --input /tmp/raw_batch2/turnaboutllm_train.jsonl \
  --output training/datasets/batch2_deductive/train/turnaboutllm.jsonl \
  --checkpoint training/datasets/batch2_deductive/cursor_checkpoint.json \
  --batch-id batch_02 \
  --max-gb 9.5 --split train

# Convert WhodunitBench (multi-character scripts -> rubric-scored Lead Detective brief)
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset whodunitbench \
  --input /tmp/raw_batch2/whodunitbench_train.json \
  --output training/datasets/batch2_deductive/train/whodunitbench.jsonl \
  --checkpoint training/datasets/batch2_deductive/cursor_checkpoint.json \
  --batch-id batch_02 \
  --max-gb 9.5 --split train

# Audit Batch 2 (<10 GB gate + House Rules) & purge raw downloads
python3 -m training.verify_factory_corpus training/datasets/batch2_deductive
rm -rf /tmp/raw_batch2

# Continue LoRA/DoRA adapter from Batch 1
trl sft \
  --model_name_or_path checkpoints/adapter_b1_core \
  --dataset_name training/datasets/batch2_deductive/train \
  --max_seq_length 32768 \
  --output_dir checkpoints/adapter_b2_deductive
```

---

### Batch 3 — NLI, Multi-Hop Vault, GraphRAG & Temporal Math (`< 6 GB`)

Converts `FEVER`, `ContractNLI`, `MuSiQue`, `DocRED`, and `TORQUE`. If you include full `FEVER` wiki pages and `BatchBudgetGuard` reaches `9.5 GiB`, it halts cleanly with `"halted_by_budget": true` in `cursor_checkpoint.json`; pass `--resume` on the next window after clearing intermediate cache.

```bash
mkdir -p /tmp/raw_batch3 training/datasets/batch3_forensic/train

# 1. FEVER + ContractNLI -> SUPPORTED | REFUTED | NOT_ENOUGH_INFORMATION
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset fever \
  --input /tmp/raw_batch3/fever_train.jsonl \
  --output training/datasets/batch3_forensic/train/fever.jsonl \
  --checkpoint training/datasets/batch3_forensic/cursor_checkpoint.json \
  --batch-id batch_03 --max-gb 9.5 --split train

python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset contractnli \
  --input /tmp/raw_batch3/contractnli_train.json \
  --output training/datasets/batch3_forensic/train/contractnli.jsonl \
  --checkpoint training/datasets/batch3_forensic/cursor_checkpoint.json \
  --batch-id batch_03 --max-gb 9.5 --split train

# 2. MuSiQue (incl. unanswerable insufficient-evidence vault holdouts)
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset musique \
  --input /tmp/raw_batch3/musique_full_v1.0_train.jsonl \
  --output training/datasets/batch3_forensic/train/musique.jsonl \
  --checkpoint training/datasets/batch3_forensic/cursor_checkpoint.json \
  --batch-id batch_03 --max-gb 9.5 --split train

# 3. DocRED -> GraphRAG triples + Records Collision Law (DO_NOT_MERGE_COLLISION)
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset docred \
  --input /tmp/raw_batch3/docred_train_annotated.json \
  --output training/datasets/batch3_forensic/train/docred.jsonl \
  --checkpoint training/datasets/batch3_forensic/cursor_checkpoint.json \
  --batch-id batch_03 --max-gb 9.5 --split train

# 4. TORQUE -> DVR clock-skew & ISO-8601 interval normalization
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset torque \
  --input /tmp/raw_batch3/torque_train.json \
  --output training/datasets/batch3_forensic/train/torque.jsonl \
  --checkpoint training/datasets/batch3_forensic/cursor_checkpoint.json \
  --batch-id batch_03 --max-gb 9.5 --split train

# (Optional) If cursor_checkpoint.json shows "halted_by_budget": true on a large dump,
# train on the emitted shard, delete it, and resume from the exact next line offset:
# python3 -m training.external_adapters.chunked_10gb_adapters \
#   --dataset fever --input /tmp/raw_batch3/fever_train.jsonl \
#   --output training/datasets/batch3_forensic_part2/train/fever_cont.jsonl \
#   --checkpoint training/datasets/batch3_forensic/cursor_checkpoint.json \
#   --resume --max-gb 9.5 --split train

python3 -m training.verify_factory_corpus training/datasets/batch3_forensic
rm -rf /tmp/raw_batch3 training/datasets/batch2_deductive

trl sft \
  --model_name_or_path checkpoints/adapter_b2_deductive \
  --dataset_name training/datasets/batch3_forensic/train \
  --max_seq_length 16384 \
  --output_dir checkpoints/adapter_b3_forensic
```

---

### Batch 4 — `WESAD` & Multimodal Deception Hardening (`< 5 GB`) + Stage-2 GRPO RLVR

Converts windowed physiological features (`WESAD` RespiBAN/Empatica CSV/JSONL + `UBFC-rPPG` / `Bag-of-Lies` / `Real-Life Trial` / `MU3D` feature windows, never storing raw uncompressed video beyond the `<10 GB` scratch cap). Maps TSST high-arousal stress (`condition == 2`) to `OTHELLO_INNOCENT_ANXIOUS` (`GENERALIZED_ANXIETY_NON_SPECIFIC`) so the model never mistakes panic for deception.

```bash
mkdir -p /tmp/raw_batch4 training/datasets/batch4_biometric/train

# Convert WESAD & multimodal physiological feature CSV/JSONL windows
python3 -m training.external_adapters.chunked_10gb_adapters \
  --dataset wesad \
  --input /tmp/raw_batch4/wesad_windows.csv /tmp/raw_batch4/multimodal_cit_windows.jsonl \
  --output training/datasets/batch4_biometric/train/wesad_room.jsonl \
  --checkpoint training/datasets/batch4_biometric/cursor_checkpoint.json \
  --batch-id batch_04 --max-gb 9.5 --split train

python3 -m training.verify_factory_corpus training/datasets/batch4_biometric
rm -rf /tmp/raw_batch4 training/datasets/batch3_forensic

# SFT pass on Track 2 Room Biometric Co-Pilot
trl sft \
  --model_name_or_path checkpoints/adapter_b3_forensic \
  --dataset_name training/datasets/batch4_biometric/train \
  --max_seq_length 8192 \
  --output_dir checkpoints/adapter_b4_sft
```

---

## 3. Stage 2 — Deterministic RLVR / GRPO Optimization (`training/rlvr_rewards.py`)

After Batch 4 SFT, optimize the policy directly against `compute_investigator_reward` (`trl_grpo_reward_fn` for HuggingFace TRL `GRPOTrainer`, `verl_compute_score` for `verl`, or `openrlhf_reward_func` for `OpenRLHF`):

```python
from trl import GRPOConfig, GRPOTrainer
from training.rlvr_rewards import trl_grpo_reward_fn

trainer = GRPOTrainer(
    model="checkpoints/adapter_b4_sft",
    reward_funcs=[trl_grpo_reward_fn],
    args=GRPOConfig(
        output_dir="checkpoints/murder_board_grpo_final",
        num_generations=8,
        max_completion_length=2048,
        beta=0.04,
    ),
    train_dataset=rlvr_dataset,  # rows carry `prompt` (messages[:-1]) and `ground_truth`
)
trainer.train()
```

### Active Verifier Gates During GRPO Rollouts
- **Murder Board 11 Chairs & Vault:** `+0.35` requires **zero** hallucinated quotes (`quote_ok() == True` on 100% of cited spans); exact `recompute_score()` rubric arithmetic; `STANDING_BRIEF_CLOSER` on `lead_detective`; **`-0.5` hard penalty** on any `check_prosecutor_vetoes()` hit.
- **Forensic Micro-Skills:** Exact ISO-8601 windows & `collision_detected`, strict `SUPPORTED|REFUTED|NOT_ENOUGH_INFORMATION` NLI, GraphRAG triple F1 + **`DO_NOT_MERGE_COLLISION`** homonym protection, era-forensics re-test selection, and hypothesis tournament ranking.
- **911 Triage:** Priority match, `coercion_detected` & `silent_approach_required` recall, life-safety trap recall, and **strict word-count penalty if `next_dispatcher_line > 18` words**.
- **AML Hunter:** `FILE_SAR_ESCALATE` vs `CLEAR_NO_SAR` disposition (penalizing false-positive SARs on legitimate businesses), typology match, tainted-entity F1, and cleared-entity precision.
- **Track 2 Biometric Co-Pilot:** Baseline-adjusted pattern match, mandatory `innocent_physiological_alternative`, and **`reward = -1.0` Othello-Error Cliff** if an innocent anxious/trauma subject is called deceptive/lying/guilty or denied an innocent physiological explanation.
