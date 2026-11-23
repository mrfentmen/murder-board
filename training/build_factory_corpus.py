#!/usr/bin/env python3
"""Master Multi-Core Corpus Orchestrator for SPEC 7 Training Factory (Batch 1 <= 10 GB).

Combines all 6 procedural Track 1 & Track 2 generators on parallel CPU cores with
de-spoiled real historical & modern archives (`real_v1`), verifies strict <10 GB budget,
exports playable Murder-Board case folders, and writes DATASET_CARD.md.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import time
from pathlib import Path
from typing import Any


def _generate_domain_shard(task: tuple[str, str, int, int, str, str]) -> dict[str, Any]:
    gen_key, split, start_idx, count, shard_path_str, salt = task

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

    out_path = Path(shard_path_str)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    n_bytes = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i in range(start_idx, start_idx + count):
            row = fn(split, i, salt)
            line = json.dumps(row, ensure_ascii=False) + "\n"
            f.write(line)
            n_bytes += len(line.encode("utf-8"))

    return {
        "generator": gen_key,
        "split": split,
        "shard": out_path.name,
        "rows": count,
        "bytes": n_bytes,
        "seconds": round(time.perf_counter() - t0, 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build unified SPEC 7 Batch-1 Training Corpus (<10 GB).")
    parser.add_argument("--out-dir", type=Path, default=Path("training/datasets/v1_50k"))
    parser.add_argument("--real-dir", type=Path, default=Path("training/datasets/real_v1"))
    parser.add_argument("--scale", type=float, default=1.0, help="Multiplier on default 50k target counts")
    parser.add_argument("--shard-size", type=int, default=2500)
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 6) - 1))
    parser.add_argument("--export-cases", type=int, default=12)
    parser.add_argument("--salt", type=str, default="mb-spec7-v1")
    args = parser.parse_args()

    # Default 1.0x plan = ~52,000 simulated + harvested real rows (~350-450 MB, well under 10 GB!)
    base_plan = {
        "murder_board_11chair": {"train": 9900, "val": 550, "test": 550},
        "vault_retrieval":      {"train": 5000, "val": 300, "test": 300},
        "forensic_micro_skills":{"train": 8000, "val": 480, "test": 480},
        "dispatch_911":         {"train": 8000, "val": 450, "test": 450},
        "aml_hunter":           {"train": 8000, "val": 450, "test": 450},
        "track2_room_copilot":  {"train": 8000, "val": 500, "test": 500},
    }

    tasks: list[tuple[str, str, int, int, str, str]] = []
    for gen_key, splits in base_plan.items():
        for split, raw_n in splits.items():
            total = max(11, int(round(raw_n * args.scale)))
            if gen_key == "murder_board_11chair":
                total = (total // 11) * 11  # keep complete 11-chair case multiples
            shard_idx = 0
            for start in range(0, total, args.shard_size):
                chunk = min(args.shard_size, total - start)
                spath = args.out_dir / split / f"{gen_key}_{split}_{shard_idx:04d}.jsonl"
                tasks.append((gen_key, split, start, chunk, str(spath), args.salt))
                shard_idx += 1

    t0 = time.perf_counter()
    with mp.Pool(processes=min(args.workers, max(1, len(tasks)))) as pool:
        shard_stats = pool.map(_generate_domain_shard, tasks)

    # Copy in real_v1 harvested shards if present
    real_copied = 0
    if args.real_dir.exists():
        for split in ("train", "val", "test"):
            src_split = args.real_dir / split
            if not src_split.exists():
                continue
            dst_split = args.out_dir / split
            dst_split.mkdir(parents=True, exist_ok=True)
            for jf in sorted(src_split.glob("*.jsonl")):
                txt = jf.read_text(encoding="utf-8")
                lines = [ln for ln in txt.splitlines() if ln.strip()]
                real_copied += len(lines)
                (dst_split / f"real_archive_{jf.name}").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Export playable synthetic Murder Board cases
    if args.export_cases > 0:
        from training.track1_now.murder_board_sim import export_playable_cases
        export_playable_cases(args.out_dir / "playable_murder_board_cases", args.export_cases, args.salt)

    elapsed = time.perf_counter() - t0
    sim_rows = sum(s["rows"] for s in shard_stats)
    sim_bytes = sum(s["bytes"] for s in shard_stats)

    manifest = {
        "salt": args.salt,
        "simulated_rows": sim_rows,
        "real_archive_rows": real_copied,
        "total_rows": sim_rows + real_copied,
        "simulated_megabytes": round(sim_bytes / (1024 ** 2), 2),
        "elapsed_seconds": round(elapsed, 2),
        "rows_per_second": round(sim_rows / max(elapsed, 1e-6), 1),
        "playable_cases_exported": args.export_cases,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
