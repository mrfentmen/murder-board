#!/usr/bin/env python3
"""Compile deduplicated, shuffled SFT/QLoRA train/val JSONL bundles for Modal LoRA fine-tuning.

Emits:
  - bundle/detective_train_mix.jsonl   (all tracks combined, strict {"messages": [...]})
  - bundle/detective_val.jsonl         (leak-free validation, strict {"messages": [...]})
  - bundle/by_specialist/<track>_train.jsonl (per-specialist QLoRA streams)
  - bundle/MANIFEST.json               (counts, track breakdown, SHA-256 hashes)
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random

from bank_detective import DATA_DIR, SYSTEM_PROMPT, TRACKS, norm_prompt

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = BASE_DIR / "bundle"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compile_bundle(data_dir: Path = DATA_DIR, out_dir: Path = DEFAULT_OUT_DIR, seed: int = 42) -> dict:
    seen: set[str] = set()
    val_rows: list[dict] = []
    train_rows: list[dict] = []
    by_track_rows: dict[str, list[dict]] = defaultdict(list)
    track_counts: Counter[str] = Counter()
    duplicates = 0

    # Load val first so validation prompts can never leak into train
    ordered_tracks = ["val"] + [tk for tk in TRACKS if tk != "val"]
    for tk in ordered_tracks:
        path = data_dir / TRACKS[tk]["file"]
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                msgs = obj.get("messages", [])
                if not msgs or msgs[0].get("content") != SYSTEM_PROMPT:
                    continue
                nu = norm_prompt(msgs[1]["content"])
                if nu in seen:
                    duplicates += 1
                    continue
                seen.add(nu)
                track_counts[tk] += 1
                if obj.get("split") == "val" or tk == "val":
                    val_rows.append(obj)
                else:
                    train_rows.append(obj)
                    by_track_rows[tk].append(obj)

    rng = random.Random(seed)
    rng.shuffle(train_rows)

    out_dir.mkdir(parents=True, exist_ok=True)
    spec_dir = out_dir / "by_specialist"
    spec_dir.mkdir(parents=True, exist_ok=True)

    train_path = out_dir / "detective_train_mix.jsonl"
    val_path = out_dir / "detective_val.jsonl"
    manifest_path = out_dir / "MANIFEST.json"

    with train_path.open("w", encoding="utf-8") as tf:
        for r in train_rows:
            tf.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")

    with val_path.open("w", encoding="utf-8") as vf:
        for r in val_rows:
            vf.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")

    specialist_files: dict[str, dict] = {}
    for tk, trows in sorted(by_track_rows.items()):
        random.Random(seed + hash(tk) % 1000).shuffle(trows)
        sp_path = spec_dir / f"{tk}_train.jsonl"
        with sp_path.open("w", encoding="utf-8") as sf:
            for r in trows:
                sf.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")
        specialist_files[tk] = {
            "rows": len(trows),
            "file": str(sp_path),
            "sha256": sha256_file(sp_path),
        }

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "total_unique_rows": len(train_rows) + len(val_rows),
        "duplicates_skipped": duplicates,
        "track_counts": dict(track_counts),
        "train_file": str(train_path),
        "val_file": str(val_path),
        "train_sha256": sha256_file(train_path),
        "val_sha256": sha256_file(val_path),
        "specialist_streams": specialist_files,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    print(json.dumps(compile_bundle(args.data_dir, args.out_dir, args.seed), indent=2))


if __name__ == "__main__":
    main()
