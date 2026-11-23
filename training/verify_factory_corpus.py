#!/usr/bin/env python3
"""Exhaustive verifier for SPEC 7 Training Factory corpora.

Audits every JSONL shard in a dataset directory:
  1. Disk budget gate (strictly < 10.0 GB per batch directory)
  2. Unique example IDs and valid message / tool structure
  3. Zero exact user-prompt leakage across train / val / test splits
  4. Zero quote drops on Murder-Board 11-chair turns + Prosecutor veto cleanliness
  5. Strict <= 18-word next_dispatcher_line enforcement on 911 turns
  6. Othello-Error guardrail & mandatory innocent_physiological_alternative on Track 2 Room turns
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from training.common import check_prosecutor_vetoes

MAX_BATCH_GIGABYTES = 10.0

FORBIDDEN_POLYGRAPH_CLAIMS = (
    "sweat proves lying",
    "sweat confirms guilt",
    "heartbeat confirms guilt",
    "biometrics prove guilt",
    "heart rate proves he is lying",
    "heart rate proves she is lying",
)


def verify_corpus_directory(corpus_dir: Path) -> dict[str, Any]:
    shards = sorted(corpus_dir.glob("*/*.jsonl"))
    if not shards:
        raise SystemExit(f"No JSONL shards found under {corpus_dir}/*/*.jsonl")

    total_bytes = sum(p.stat().st_size for p in shards)
    total_gb = total_bytes / (1024 ** 3)
    if total_gb >= MAX_BATCH_GIGABYTES:
        raise AssertionError(f"Batch size {total_gb:.2f} GB exceeds 10.0 GB ceiling!")

    seen_ids: set[str] = set()
    split_hashes: dict[str, set[bytes]] = defaultdict(set)
    by_split: Counter[str] = Counter()
    by_track: Counter[str] = Counter()
    by_domain: Counter[str] = Counter()
    by_subtask: dict[str, Counter[str]] = defaultdict(Counter)
    total_chars = 0
    row_count = 0

    for shard in shards:
        with shard.open("r", encoding="utf-8") as f:
            for line_no, raw in enumerate(f, start=1):
                if not raw.strip():
                    continue
                row = json.loads(raw)
                rid = row["id"]
                if rid in seen_ids:
                    raise AssertionError(f"Duplicate ID '{rid}' at {shard}:{line_no}")
                seen_ids.add(rid)

                split = row["split"]
                track = row.get("track", "track1_now")
                domain = row["domain"]
                subtask = row.get("subtask") or row.get("step") or "default"
                msgs = row["messages"]
                gt = row["ground_truth"]

                assert len(msgs) >= 3, f"Expected >=3 messages at {rid}"
                assert msgs[0]["role"] == "system", f"First message must be system at {rid}"
                assert msgs[-1]["role"] == "assistant", f"Final message must be assistant at {rid}"

                user_concat = "\n".join(m["content"] for m in msgs if m["role"] == "user")
                uhash = hashlib.sha256(user_concat.encode("utf-8")).digest()[:12]
                split_hashes[split].add(uhash)

                row_chars = sum(len(str(m.get("content", ""))) for m in msgs)
                total_chars += row_chars
                row_count += 1

                by_split[split] += 1
                by_track[track] += 1
                by_domain[domain] += 1
                by_subtask[domain][subtask] += 1

                final_text = msgs[-1]["content"]
                final_low = final_text.lower()

                if domain == "cold_case_murder_board":
                    assert gt.get("quote_check_drops", 0) == 0, f"Non-zero quote drops at {rid}"
                    parsed = json.loads(final_text)
                    assert isinstance(parsed, dict)
                    if subtask == "lead_detective":
                        veto_hits = check_prosecutor_vetoes(parsed.get("brief", ""), [])
                        assert not veto_hits, f"Prosecutor veto leaked in {rid}: {veto_hits}"

                elif domain == "dispatch_911_triage":
                    wc = gt.get("next_line_word_count")
                    if wc is not None:
                        assert wc <= 18, f"911 dispatcher line > 18 words ({wc}) at {rid}"

                elif track == "track2_future" or domain == "future_room_biometric_copilot":
                    for bad in FORBIDDEN_POLYGRAPH_CLAIMS:
                        assert bad not in final_low, f"Forbidden polygraph overclaim '{bad}' in {rid}"
                    assert "innocent" in final_low or "alternative" in final_low, (
                        f"Missing innocent physiological alternative in {rid}"
                    )

    # Check cross-split user-prompt isolation
    splits = sorted(split_hashes.keys())
    for i in range(len(splits)):
        for j in range(i + 1, len(splits)):
            sa, sb = splits[i], splits[j]
            overlap = split_hashes[sa] & split_hashes[sb]
            if overlap:
                raise AssertionError(f"Split leakage between {sa} and {sb}: {len(overlap)} shared prompts!")

    est_tokens = int(total_chars / 4)
    report = {
        "status": "PASSED",
        "shards": len(shards),
        "total_rows": row_count,
        "total_megabytes": round(total_bytes / (1024 ** 2), 2),
        "total_gigabytes": round(total_gb, 4),
        "under_10gb_cap": total_gb < MAX_BATCH_GIGABYTES,
        "estimated_total_tokens": est_tokens,
        "estimated_avg_tokens_per_row": int(est_tokens / max(1, row_count)),
        "by_split": dict(by_split),
        "by_track": dict(by_track),
        "by_domain": dict(by_domain),
        "subtasks_per_domain": {k: dict(v) for k, v in by_subtask.items()},
    }
    (corpus_dir / "verification_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("training/datasets/v1_50k")
    verify_corpus_directory(target)
