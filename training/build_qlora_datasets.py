#!/usr/bin/env python3
"""Multi-Core Strict QLoRA ChatML Dataset Builder (`build_qlora_datasets.py`).

Generates ~52,000 procedural + de-spoiled real-archive (`real_v1`) training examples
across parallel CPU cores and writes them directly into clean, standalone, strict
QLoRA ChatML folders (`{"messages": [{"role": ..., "content": ...}]}` ONLY — zero
Arrow-breaking extra columns):

  /Users/test/Desktop/murder-board/qlora_datasets/
  ├── 01_cold_case_detective/     (train.jsonl, val.jsonl, test.jsonl — ~24,000 rows)
  ├── 02_911_triage_dispatch/     (train.jsonl, val.jsonl, test.jsonl — ~9,200 rows)
  ├── 03_aml_laundering_hunter/   (train.jsonl, val.jsonl, test.jsonl — ~9,200 rows)
  ├── 04_future_biometric_room/   (train.jsonl, val.jsonl, test.jsonl — ~9,000 rows)
  ├── MANIFEST.json
  └── README.md

Every line in every folder is verified by `verify_strict_qlora_folder` from
`training/export_qlora_folders.py`.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing as mp
import os
import random
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from training.export_qlora_folders import (
    normalize_to_strict_qlora_chatml,
    verify_strict_qlora_folder,
)

FOLDER_SPECS: tuple[dict[str, Any], ...] = (
    {
        "folder": "01_cold_case_detective",
        "title": "Cold-Case Homicide Detective (11-Chair Murder Board + 80–120 Doc Noisy Vault + 8 Forensic Micro-Skills + Real Archives)",
        "generators": ("murder_board_11chair", "vault_retrieval", "forensic_micro_skills"),
        "real_domains": ("cold_case_murder_board", "cold_case_vault_retrieval", "forensic_micro_skills"),
    },
    {
        "folder": "02_911_triage_dispatch",
        "title": "911 Panicked & Coerced-Caller Emergency Triage Co-Pilot (21 Archetypes + Real 2005–2026 FDNY/NYC, SFPD & Seattle CAD)",
        "generators": ("dispatch_911",),
        "real_domains": ("dispatch_911_triage",),
    },
    {
        "folder": "03_aml_laundering_hunter",
        "title": "Cartel, TBML & Shell-Company AML Hunter (6 Laundering Typologies + 20% Clean False Positives + Real DOJ AML & OFAC SDN)",
        "generators": ("aml_hunter",),
        "real_domains": ("aml_laundering_hunter",),
    },
    {
        "folder": "04_future_biometric_room",
        "title": "Chair 12 Future Interrogation-Room Biometric & Cognitive-Load Co-Pilot (Othello-Error Hardened)",
        "generators": ("track2_room_copilot",),
        "real_domains": ("future_room_biometric_copilot",),
    },
)

BASE_SIM_PLAN: dict[str, dict[str, int]] = {
    "murder_board_11chair":  {"train": 9020, "val": 495, "test": 495},
    "vault_retrieval":       {"train": 4500, "val": 250, "test": 250},
    "forensic_micro_skills": {"train": 8000, "val": 480, "test": 480},
    "dispatch_911":          {"train": 8100, "val": 450, "test": 450},
    "aml_hunter":            {"train": 8100, "val": 460, "test": 460},
    "track2_room_copilot":   {"train": 8000, "val": 500, "test": 500},
}


def _generate_strict_qlora_chunk(task: tuple[str, str, int, int, str, str]) -> dict[str, Any]:
    """Worker function: generate `count` examples and write normalized strict ChatML lines to `chunk_path_str`."""
    gen_key, split, start_idx, count, chunk_path_str, salt = task

    if gen_key == "murder_board_11chair":
        from training.track1_now.murder_board_sim import generate_murder_board_example as fn
    elif gen_key == "vault_retrieval":
        from training.track1_now.noisy_vault_retrieval import generate_vault_retrieval_example as fn
    elif gen_key == "forensic_micro_skills":
        from training.track1_now.forensic_micro_skills import generate_micro_skill_example as fn
    elif gen_key == "dispatch_911":
        from training.track1_now.dispatch_911_sim import generate_dispatch_911_example as fn
    elif gen_key == "aml_hunter":
        from training.track1_now.aml_hunter_sim import generate_aml_hunter_example as fn
    elif gen_key == "track2_room_copilot":
        from training.track2_future.interrogation_room_sim import generate_interrogation_room_example as fn
    else:
        raise ValueError(f"Unknown generator key: {gen_key}")

    out_path = Path(chunk_path_str)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    n_bytes = 0

    with out_path.open("w", encoding="utf-8") as f:
        for i in range(start_idx, start_idx + count):
            raw_row = fn(split, i, salt)
            strict_row = normalize_to_strict_qlora_chatml(raw_row)
            line = json.dumps(strict_row, ensure_ascii=False) + "\n"
            f.write(line)
            n_bytes += len(line.encode("utf-8"))

    return {
        "generator": gen_key,
        "split": split,
        "start_idx": start_idx,
        "rows": count,
        "bytes": n_bytes,
        "chunk_path": str(out_path),
        "seconds": round(time.perf_counter() - t0, 3),
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _load_real_v1_strict_lines(real_dir: Path) -> dict[tuple[str, str], list[str]]:
    """Load `real_v1` rows grouped by `(folder_name, split)` and normalized to strict QLoRA ChatML."""
    domain_to_folder: dict[str, str] = {}
    for spec in FOLDER_SPECS:
        for d in spec["real_domains"]:
            domain_to_folder[d] = spec["folder"]

    grouped: dict[tuple[str, str], list[str]] = {}
    if not real_dir.exists():
        return grouped

    for split in ("train", "val", "test"):
        split_dir = real_dir / split
        if not split_dir.exists():
            continue
        for jf in sorted(split_dir.glob("*.jsonl")):
            with jf.open("r", encoding="utf-8") as f:
                for raw_line in f:
                    if not raw_line.strip():
                        continue
                    row = json.loads(raw_line)
                    dom = str(row.get("domain", ""))
                    folder_name = domain_to_folder.get(dom)
                    if not folder_name:
                        continue
                    strict_row = normalize_to_strict_qlora_chatml(row)
                    grouped.setdefault((folder_name, split), []).append(
                        json.dumps(strict_row, ensure_ascii=False)
                    )
    return grouped


def build_qlora_datasets(
    out_dir: Path,
    real_dir: Path,
    *,
    scale: float = 1.0,
    chunk_size: int = 1200,
    workers: int = max(1, (os.cpu_count() or 6) - 1),
    salt: str = "mb-spec7-v1",
) -> dict[str, Any]:
    t0 = time.perf_counter()
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Harvest & normalize real_v1 rows by target folder and split
    real_grouped = _load_real_v1_strict_lines(real_dir)

    # 2. Plan multiprocessing chunk tasks across all 6 generators
    tmp_root = Path(tempfile.mkdtemp(prefix="mb_qlora_chunks_"))
    try:
        tasks: list[tuple[str, str, int, int, str, str]] = []
        chunk_order: dict[tuple[str, str], list[Path]] = {}
        gen_to_folder: dict[str, str] = {}
        for spec in FOLDER_SPECS:
            for g in spec["generators"]:
                gen_to_folder[g] = spec["folder"]

        for gen_key, splits in BASE_SIM_PLAN.items():
            folder_name = gen_to_folder[gen_key]
            for split, base_count in splits.items():
                total = max(11, int(round(base_count * scale)))
                if gen_key == "murder_board_11chair":
                    total = (total // 11) * 11
                chunk_idx = 0
                for start in range(0, total, chunk_size):
                    cnt = min(chunk_size, total - start)
                    cpath = tmp_root / folder_name / split / f"{gen_key}_{split}_{chunk_idx:04d}.jsonl"
                    tasks.append((gen_key, split, start, cnt, str(cpath), salt))
                    chunk_order.setdefault((folder_name, split), []).append(cpath)
                    chunk_idx += 1

        pool_size = min(workers, max(1, len(tasks)))
        with mp.Pool(processes=pool_size) as pool:
            chunk_stats = pool.map(_generate_strict_qlora_chunk, tasks)

        # 3. Assemble per-folder train.jsonl, val.jsonl, test.jsonl (deterministically shuffled per split)
        folder_reports: dict[str, Any] = {}
        total_rows_all = 0
        total_sim_rows_all = 0
        total_real_rows_all = 0
        total_bytes_all = 0

        for spec in FOLDER_SPECS:
            folder_name = spec["folder"]
            folder_path = out_dir / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)

            split_details: dict[str, Any] = {}
            folder_sim_rows = 0
            folder_real_rows = 0
            folder_bytes = 0

            for split in ("train", "val", "test"):
                lines: list[str] = []
                for cpath in chunk_order.get((folder_name, split), []):
                    with cpath.open("r", encoding="utf-8") as cf:
                        lines.extend(ln.rstrip("\n") for ln in cf if ln.strip())
                sim_n = len(lines)

                real_lines = real_grouped.get((folder_name, split), [])
                real_n = len(real_lines)
                lines.extend(real_lines)

                # Deterministic shuffle per (folder_name, split) so multi-generator & real rows are interleaved
                shuf_rng = random.Random(f"{salt}|{folder_name}|{split}")
                shuf_rng.shuffle(lines)

                out_fp = folder_path / f"{split}.jsonl"
                with out_fp.open("w", encoding="utf-8") as out_f:
                    for ln in lines:
                        out_f.write(ln + "\n")

                f_bytes = out_fp.stat().st_size
                sha256_hex = _sha256_file(out_fp)
                split_details[split] = {
                    "file": f"{folder_name}/{split}.jsonl",
                    "rows": sim_n + real_n,
                    "simulated_rows": sim_n,
                    "real_archive_rows": real_n,
                    "bytes": f_bytes,
                    "mb": round(f_bytes / (1024 ** 2), 2),
                    "sha256": sha256_hex,
                }
                folder_sim_rows += sim_n
                folder_real_rows += real_n
                folder_bytes += f_bytes

            # 4. Run strict QLoRA folder verification on every single line
            verify_stats = verify_strict_qlora_folder(folder_path)

            folder_total_rows = folder_sim_rows + folder_real_rows
            total_rows_all += folder_total_rows
            total_sim_rows_all += folder_sim_rows
            total_real_rows_all += folder_real_rows
            total_bytes_all += folder_bytes

            folder_reports[folder_name] = {
                "title": spec["title"],
                "generators": list(spec["generators"]),
                "real_domains": list(spec["real_domains"]),
                "strict_qlora_verified": True,
                "verify_strict_qlora_folder_stats": verify_stats,
                "total_rows": folder_total_rows,
                "simulated_rows": folder_sim_rows,
                "real_archive_rows": folder_real_rows,
                "total_bytes": folder_bytes,
                "total_mb": round(folder_bytes / (1024 ** 2), 2),
                "splits": split_details,
            }

    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    elapsed = round(time.perf_counter() - t0, 2)
    total_mb_all = round(total_bytes_all / (1024 ** 2), 2)
    total_gb_all = round(total_bytes_all / (1024 ** 3), 4)
    assert total_mb_all < 1024.0, f"Expected total disk usage < 1 GB (1024 MB), got {total_mb_all} MB"

    generator_breakdown: dict[str, dict[str, int]] = {}
    for st in chunk_stats:
        g = st["generator"]
        sp = st["split"]
        generator_breakdown.setdefault(g, {"train": 0, "val": 0, "test": 0, "total": 0})
        generator_breakdown[g][sp] += st["rows"]
        generator_breakdown[g]["total"] += st["rows"]

    manifest: dict[str, Any] = {
        "schema": "murder-board.qlora_datasets.manifest.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "salt": salt,
        "workers_used": pool_size,
        "elapsed_seconds": elapsed,
        "rows_per_second": round(total_rows_all / max(elapsed, 1e-6), 1),
        "strict_qlora_chatml_schema": {"messages": [{"role": "system|user|assistant", "content": "<string>"}]},
        "all_lines_passed_verify_strict_qlora_folder": True,
        "zero_extra_columns_confirmed": True,
        "under_1gb_verified": total_mb_all < 1024.0,
        "under_10gb_verified": total_gb_all < 10.0,
        "total_rows": total_rows_all,
        "simulated_rows": total_sim_rows_all,
        "real_archive_rows": total_real_rows_all,
        "total_bytes": total_bytes_all,
        "total_mb": total_mb_all,
        "total_gb": total_gb_all,
        "generator_breakdown": generator_breakdown,
        "folders": folder_reports,
    }

    manifest_path = out_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    readme_path = out_dir / "README.md"
    readme_path.write_text(_render_readme(manifest), encoding="utf-8")
    return manifest


def _render_readme(manifest: dict[str, Any]) -> str:
    folders = manifest["folders"]
    lines: list[str] = [
        "# Murder Board — Standalone Strict QLoRA ChatML Datasets (`qlora_datasets/`)",
        "",
        "Clean, standalone, PyArrow/HuggingFace/Unsloth/Axolotl/LLaMA-Factory/TRL QLoRA training folders.",
        "Every single JSONL line across all 4 folders and 12 split files contains **only** the uniform key:",
        "",
        "```json",
        '{"messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}',
        "```",
        "",
        "- **Zero extra top-level columns** (no heterogeneous `ground_truth`, `tools`, or UI metadata that breaks PyArrow schema inference).",
        "- **Strict role alternation** (`system` optional -> `user` -> `assistant` -> `user` -> `assistant`, always ending on `assistant`).",
        "- **100% verified by `verify_strict_qlora_folder`** from `training/export_qlora_folders.py`.",
        f"- **Total Rows:** `{manifest['total_rows']:,}` (`{manifest['simulated_rows']:,}` procedural + `{manifest['real_archive_rows']:,}` de-spoiled `real_v1` historical/modern archive rows).",
        f"- **Total Disk Usage:** `{manifest['total_mb']:.2f} MB` (`{manifest['total_gb']:.4f} GB` — verified strictly `< 1 GB` and `< 10 GB`).",
        "",
        "---",
        "",
        "## Folder Overview",
        "",
        "| Folder | Train Rows | Val Rows | Test Rows | Total Rows | Real `real_v1` Rows | Size (MB) | `verify_strict_qlora_folder` |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]

    for fname, fdata in folders.items():
        sp = fdata["splits"]
        lines.append(
            f"| `{fname}/` | {sp['train']['rows']:,} | {sp['val']['rows']:,} | {sp['test']['rows']:,} | "
            f"**{fdata['total_rows']:,}** | {fdata['real_archive_rows']:,} | **{fdata['total_mb']:.2f} MB** | PASSED |"
        )

    lines.append(
        f"| **TOTAL** | **{sum(f['splits']['train']['rows'] for f in folders.values()):,}** | "
        f"**{sum(f['splits']['val']['rows'] for f in folders.values()):,}** | "
        f"**{sum(f['splits']['test']['rows'] for f in folders.values()):,}** | "
        f"**{manifest['total_rows']:,}** | **{manifest['real_archive_rows']:,}** | "
        f"**{manifest['total_mb']:.2f} MB** | **100% PASSED** |"
    )

    lines.extend([
        "",
        "---",
        "",
        "## Exact Split File Manifest & SHA-256 Hashes",
        "",
        "| File Path | Total Rows | Procedural Rows | Real Archive Rows | Size (MB) | SHA-256 |",
        "|---|---:|---:|---:|---:|---|",
    ])

    for fname, fdata in folders.items():
        for split in ("train", "val", "test"):
            s = fdata["splits"][split]
            lines.append(
                f"| `{s['file']}` | {s['rows']:,} | {s['simulated_rows']:,} | {s['real_archive_rows']:,} | "
                f"{s['mb']:.2f} MB | `{s['sha256']}` |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## Domain & Source Composition",
        "",
        "1. **`01_cold_case_detective/`**",
        "   - `murder_board_sim`: All 11 Murder-Board chairs (`01_first_officer` .. `11_lead_detective`) across 10 venue archetypes, 80% actionable 4-link record chains + 20% archival holdouts.",
        "   - `noisy_vault_retrieval`: Multi-hop tool-use trajectories (`search_vault`, `query_entity_graph`, `read_document`, `check_almanac`, `diff_statements`, `submit_findings`) over 80–120 document vaults.",
        "   - `forensic_micro_skills`: All 8 forensic micro-skill drills (`temporal_clock_math`, `forensic_nli`, `entity_resolution_graph`, `name_collision_guard`, `pathology_and_trace`, `digital_machine_literacy`, `hypothesis_tournament`, `fake_insider_knowledge`).",
        "   - `real_v1`: De-spoiled Old Bailey (1674–1913) homicide trials, DOJ homicide press releases, and playable Case 4 (`duck-2020`) turns.",
        "2. **`02_911_triage_dispatch/`**",
        "   - `dispatch_911_sim`: 21 high-stakes emergency dispatch sub-archetypes (coerced pizza/salon/utility/rideshare/bilingual ruses, agonal breathing traps, fentanyl apnea, stroke LKW, submerging vehicle, downed 13.8kV wire, CO poisoning, VOIP swatting) with strict `<= 18`-word `next_dispatcher_line`.",
        "   - `real_v1`: Real 2005–2026 FDNY/NYC EMS, SFPD, and Seattle 911 CAD triage rows.",
        "3. **`03_aml_laundering_hunter/`**",
        "   - `aml_hunter_sim`: 6 laundering typologies (`SMURFING_FUNNEL`, `TBML_INVOICE_AND_WEIGHT_MISMATCH`, `LAYERED_SHELL_ROUND_TRIP`, `CASH_FRONT_UTILITY_MISMATCH`, `CRYPTO_PEEL_AND_OTC_SETTLEMENT`, `ALL_CASH_REAL_ESTATE_NOMINEE`) + 20% `CLEAR_NO_SAR` legitimate business false-positive clearances across static and tool-use trajectories.",
        "   - `real_v1`: De-spoiled DOJ money-laundering / forfeiture / TBML cases & OFAC SDN sanctions-evasion rows.",
        "4. **`04_future_biometric_room/`**",
        "   - `interrogation_room_sim`: Chair 12 synchronized rPPG heart rate, vagal HRV RMSSD, phasic EDA, periorbital thermal delta, pupil dilation, and acoustic latency across Homicide Interview, 911 Bodycam Triage, and AML/Customs Secondary Inspection.",
        "   - Hardened against the **Othello Error** (`35%` concealing CIT hit, `35%` innocent anxious / embarrassed Othello controls, `30%` trauma cooperative witnesses) with mandatory `innocent_physiological_alternative` on every turn.",
        "",
        "## Quick Load Example (HuggingFace `datasets` / Unsloth / TRL)",
        "",
        "```python",
        "from datasets import load_dataset",
        "",
        'ds = load_dataset("json", data_dir="qlora_datasets/01_cold_case_detective")',
        "print(ds)",
        "```",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build standalone strict QLoRA ChatML dataset folders (<1 GB).")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("/Users/test/Desktop/murder-board/qlora_datasets"),
        help="Output root directory for QLoRA dataset folders.",
    )
    parser.add_argument(
        "--real-dir",
        type=Path,
        default=Path("/Users/test/Desktop/murder-board/training/datasets/real_v1"),
        help="Path to harvested real_v1 shards.",
    )
    parser.add_argument("--scale", type=float, default=1.0, help="Row count multiplier (default 1.0 -> ~52,000 rows).")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 6) - 1))
    parser.add_argument("--salt", type=str, default="mb-spec7-v1")
    args = parser.parse_args()

    manifest = build_qlora_datasets(
        out_dir=args.out_dir,
        real_dir=args.real_dir,
        scale=args.scale,
        chunk_size=args.chunk_size,
        workers=args.workers,
        salt=args.salt,
    )
    print(
        json.dumps(
            {
                "status": "PASSED",
                "total_rows": manifest["total_rows"],
                "simulated_rows": manifest["simulated_rows"],
                "real_archive_rows": manifest["real_archive_rows"],
                "total_mb": manifest["total_mb"],
                "total_gb": manifest["total_gb"],
                "under_1gb_verified": manifest["under_1gb_verified"],
                "elapsed_seconds": manifest["elapsed_seconds"],
                "rows_per_second": manifest["rows_per_second"],
                "folders": {
                    k: {
                        "total_rows": v["total_rows"],
                        "real_archive_rows": v["real_archive_rows"],
                        "total_mb": v["total_mb"],
                        "strict_qlora_verified": v["strict_qlora_verified"],
                    }
                    for k, v in manifest["folders"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
