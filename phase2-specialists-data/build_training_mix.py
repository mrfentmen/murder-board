#!/usr/bin/env python3
"""Compile Phase-2 Specialist (#4-#7) QLoRA bundles (combined + per-specialist)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random

from bank_phase2 import BASE_DIR, DATA_DIR, SYSTEM_PROMPT, TRACKS, norm_prompt


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compile_bundle(seed: int = 42) -> dict:
    seen: set[str] = set()
    val_rows, train_rows = [], []
    by_tk: dict[str, list[dict]] = defaultdict(list)

    for tk in ["val"] + [k for k in TRACKS if k != "val"]:
        p = DATA_DIR / TRACKS[tk]["file"]
        if not p.exists():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            obj = json.loads(ln)
            msgs = obj["messages"]
            if msgs[0]["content"] != SYSTEM_PROMPT:
                continue
            nu = norm_prompt(msgs[1]["content"])
            if nu in seen:
                continue
            seen.add(nu)
            if tk == "val":
                val_rows.append({"messages": msgs})
            else:
                train_rows.append({"messages": msgs})
                by_tk[tk].append({"messages": msgs})

    random.Random(seed).shuffle(train_rows)
    out = BASE_DIR / "bundle"
    spec = out / "by_specialist"
    spec.mkdir(parents=True, exist_ok=True)

    tr_p = out / "phase2_train_mix.jsonl"
    va_p = out / "phase2_val.jsonl"
    tr_p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in train_rows) + "\n", encoding="utf-8")
    va_p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in val_rows) + "\n", encoding="utf-8")

    per_spec = {}
    for tk, rows in sorted(by_tk.items()):
        sp = spec / f"{tk}_train.jsonl"
        sp.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
        per_spec[tk] = {"rows": len(rows), "file": str(sp), "sha256": sha256_file(sp)}

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "total_unique_rows": len(train_rows) + len(val_rows),
        "train_sha256": sha256_file(tr_p),
        "val_sha256": sha256_file(va_p),
        "specialists": per_spec,
    }
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(compile_bundle(), indent=2))
