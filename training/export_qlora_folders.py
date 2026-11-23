#!/usr/bin/env python3
"""Export clean, standalone QLoRA-ready dataset folders (pure ChatML `messages` JSONL).

Why this exists:
- HuggingFace `datasets` / PyArrow / Unsloth / Axolotl / LLaMA-Factory QLoRA loaders
  require strict, uniform columns across every JSONL line (`{"messages": [{"role": ..., "content": ...}]}`).
- Mixing Murder-Board JS app schemas or heterogeneous `ground_truth` dicts causes Arrow schema errors
  and ties the model to one UI.

Output layout (`/Users/test/Desktop/murder-board/qlora_datasets/`):
  ├── 01_cold_case_detective/     (train.jsonl, val.jsonl, test.jsonl)
  ├── 02_911_triage_dispatch/     (train.jsonl, val.jsonl, test.jsonl)
  ├── 03_aml_laundering_hunter/   (train.jsonl, val.jsonl, test.jsonl)
  └── 04_future_biometric_room/   (train.jsonl, val.jsonl, test.jsonl)
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


def normalize_to_strict_qlora_chatml(raw_row: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Convert any generator/archive row into strict uniform ChatML `{"messages": [...]}`."""
    msgs = raw_row["messages"]
    clean_msgs: list[dict[str, str]] = []
    for m in msgs:
        role = str(m.get("role", "user")).strip()
        if role == "tool":
            role = "user"
            content = f"[Retrieved Archive / Tool Result]\n{m.get('content', '')}"
        else:
            content = str(m.get("content", ""))
        if role not in ("system", "user", "assistant"):
            role = "user"
        # Merge consecutive identical roles so strict alternating QLoRA chat templates never fail
        if clean_msgs and clean_msgs[-1]["role"] == role and role != "system":
            clean_msgs[-1]["content"] += "\n\n" + content
        else:
            clean_msgs.append({"role": role, "content": content})

    assert len(clean_msgs) >= 2, "Must have at least user + assistant turns"
    assert clean_msgs[-1]["role"] == "assistant", "Last turn in QLoRA sample must be assistant"
    return {"messages": clean_msgs}


def verify_strict_qlora_folder(folder: Path) -> dict[str, Any]:
    """Verify uniform schema, strict role alternation, non-empty content, and <10 GB size."""
    stats: dict[str, Any] = {}
    total_bytes = 0
    for split in ("train", "val", "test"):
        fp = folder / f"{split}.jsonl"
        if not fp.exists():
            continue
        b = fp.stat().st_size
        total_bytes += b
        n_rows = 0
        with fp.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                obj = json.loads(line)
                if list(obj.keys()) != ["messages"]:
                    raise AssertionError(f"{fp}:{line_no} has extra non-QLoRA keys: {list(obj.keys())}")
                msgs = obj["messages"]
                if not isinstance(msgs, list) or len(msgs) < 2:
                    raise AssertionError(f"{fp}:{line_no} invalid messages list")
                for m in msgs:
                    if sorted(m.keys()) != ["content", "role"]:
                        raise AssertionError(f"{fp}:{line_no} message has non-uniform keys: {list(m.keys())}")
                    if m["role"] not in ("system", "user", "assistant") or not m["content"].strip():
                        raise AssertionError(f"{fp}:{line_no} invalid role or empty content")
                # Check strict user/assistant alternation after optional system message
                body = msgs[1:] if msgs[0]["role"] == "system" else msgs
                for idx, m in enumerate(body):
                    expected = "user" if idx % 2 == 0 else "assistant"
                    if m["role"] != expected:
                        raise AssertionError(f"{fp}:{line_no} broke user/assistant alternation at turn {idx}")
                n_rows += 1
        stats[split] = {"rows": n_rows, "mb": round(b / (1024 ** 2), 2)}
    stats["total_mb"] = round(total_bytes / (1024 ** 2), 2)
    assert stats["total_mb"] < 10 * 1024, "Exceeded 10 GB folder limit!"
    return stats
