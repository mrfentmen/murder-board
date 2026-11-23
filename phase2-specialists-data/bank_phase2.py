#!/usr/bin/env python3
"""Atomic, file-locked SFT/QLoRA validator, banker, and auditor for Phase-2 Specialist AIs (#4-#7)."""

from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SPEC_PATH = BASE_DIR / "SPEC.md"
GENERATOR_NAME = "gemini-4-argon"

SYSTEM_PROMPT = (
    "You are BLACKBOX, a physical-world forensic investigator across crash/arson disaster reconstruction, "
    "outbreak epidemiology, maritime/customs smuggling physics, and public-procurement corruption auditing. "
    "Communicate in crisp technical investigator register: lead with CASE BLUF or numbered findings, cite exact "
    "exhibit/sensor IDs and verbatim quotes, separate post-incident damage or background noise from root-cause "
    "physical mechanisms, show explicit physics/biostatistical/procurement math, and cut all chatbot filler. "
    "Judge the telemetry and records, never a person: pair every flagged anomaly with its explicit INNOCENT "
    "ALTERNATIVE, keep fenced Python, SQL, bash, and JSON blocks clean and runnable, and refuse unlawful sabotage, "
    "pathogen/toxin synthesis, sanctions-evasion facilitation, or doxxing in two crisp sentences redirecting to "
    "lawful forensic methodology."
)

if SPEC_PATH.exists():
    assert SYSTEM_PROMPT in SPEC_PATH.read_text(encoding="utf-8")

TRACKS: dict[str, dict] = {
    "crash_arson": {
        "file": "crash_arson_train.jsonl",
        "prefix": "p2-crash",
        "split": "train",
        "families": {
            "flashover-vs-accelerant", "arc-mapping-origin", "fdr-cvr-cascade",
            "rail-derailment-metallurgy", "structural-collapse-creep", "maintenance-normalization-deviance",
        },
    },
    "outbreak_epi": {
        "file": "outbreak_epi_train.jsonl",
        "prefix": "p2-epi",
        "split": "train",
        "families": {
            "food-lot-odds-ratio", "multi-er-syndromic-cluster", "water-plume-backflow",
            "occupational-toxin-exposure", "cold-chain-vaccine-spoilage", "nosocomial-device-vector",
        },
    },
    "dark_fleet": {
        "file": "dark_fleet_train.jsonl",
        "prefix": "p2-maritime",
        "split": "train",
        "families": {
            "ais-gnss-spoofing", "sts-draft-mass-balance", "container-density-impossibility",
            "dual-use-eccn-diversion", "flag-hopping-imo-identity", "reefer-false-bulkhead-thermal",
        },
    },
    "bid_rigging": {
        "file": "bid_rigging_train.jsonl",
        "prefix": "p2-audit",
        "split": "train",
        "families": {
            "tailored-sole-spec-rfp", "complementary-cover-bidding", "loser-to-subcontractor-flip",
            "change-order-lowball-trap", "benford-bid-clustering", "conflict-shell-donation-loop",
        },
    },
    "refusal": {
        "file": "refusal_train.jsonl",
        "prefix": "p2-refusal",
        "split": "train",
        "families": {
            "roe-sabotage-arson", "roe-pathogen-toxin", "roe-smuggling-evasion", "roe-doxxing-harassment",
        },
    },
    "val": {
        "file": "val.jsonl",
        "prefix": "p2-val",
        "split": "val",
        "families": {
            "val-crash-arson", "val-outbreak-epi", "val-dark-fleet", "val-bid-rigging", "val-refusal",
        },
    },
}

NORM_WS_RE = re.compile(r"\s+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)
FILLER_RE = re.compile(r"(?:\bas an ai\b|\blanguage model\b|\bhappy to help\b|\bgreat question\b|\bsure!\b|\bcertainly!\b)", re.I)
REGISTER_RE = re.compile(r"(?:\bCASE BLUF\b|\bBLUF\b|\bFINDING\b|\bINNOCENT ALTERNATIVE\b|\bNEXT LEAD\b|\bNEGATIVE\b|\bREFUSED\b)", re.I)


def norm_prompt(text: str) -> str:
    return NORM_WS_RE.sub(" ", text.strip()).lower()


def validate_row(track: str, row: dict) -> tuple[list[dict] | None, str | None]:
    if track not in TRACKS:
        return None, f"unknown track {track}"
    cfg = TRACKS[track]
    fam = str(row.get("family", "")).strip()
    if fam not in cfg["families"]:
        return None, f"invalid family {fam}"
    u = str(row.get("user", "")).strip()
    a = str(row.get("assistant", "")).strip()
    if len(u) < 20 or len(a) < 30:
        return None, "prompt or assistant too short"
    if CJK_RE.search(u) or CJK_RE.search(a):
        return None, "unexpected CJK"
    if FILLER_RE.search(a) or not REGISTER_RE.search(a):
        return None, "filler or missing register marker"
    if a.count("```") % 2 != 0:
        return None, "unbalanced fences"
    for lang, code in FENCE_RE.findall(a):
        if lang.strip().lower() in ("python", "py"):
            try:
                ast.parse(code)
            except SyntaxError as exc:
                return None, f"python syntax error: {exc.msg}"
    is_ref = track == "refusal" or fam == "val-refusal"
    if not is_ref and "innocent" not in a.lower() and "alternative" not in a.lower() and "benign" not in a.lower():
        return None, "missing innocent/benign alternative"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": u},
        {"role": "assistant", "content": a},
    ], None


def _load_state(p: Path) -> tuple[int, set[str], dict[str, int]]:
    if not p.exists():
        return 0, set(), {}
    mx = 0
    seen: set[str] = set()
    fams: dict[str, int] = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        obj = json.loads(ln)
        m = re.search(r"-(\d+)$", obj["id"])
        if m:
            mx = max(mx, int(m.group(1)))
        seen.add(norm_prompt(obj["messages"][1]["content"]))
        fam = obj.get("family", "unknown")
        fams[fam] = fams.get(fam, 0) + 1
    return mx, seen, fams


def bank_rows(track: str, rows: list[dict], data_dir: Path = DATA_DIR, max_batch: int = 10) -> dict:
    if len(rows) > max_batch:
        raise ValueError(f"max_batch={max_batch} exceeded")
    cfg = TRACKS[track]
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_p = data_dir / ".lock"
    target_p = data_dir / cfg["file"]
    status_p = data_dir / "STATUS.json"

    with lock_p.open("w", encoding="utf-8") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        all_seen: set[str] = set()
        seqs: dict[str, int] = {}
        for tk, tcfg in TRACKS.items():
            sq, sn, _ = _load_state(data_dir / tcfg["file"])
            seqs[tk] = sq
            all_seen |= sn

        seq = seqs[track]
        accepted, dropped = [], []
        for i, r in enumerate(rows):
            msgs, err = validate_row(track, r)
            if err or msgs is None:
                dropped.append(f"row[{i}]: {err}")
                continue
            nu = norm_prompt(msgs[1]["content"])
            if nu in all_seen:
                dropped.append(f"row[{i}]: duplicate")
                continue
            seq += 1
            all_seen.add(nu)
            accepted.append({
                "id": f"{cfg['prefix']}-{seq:06d}",
                "messages": msgs,
                "track": track,
                "family": str(r["family"]).strip(),
                "generator": GENERATOR_NAME,
                "split": cfg["split"],
            })

        if accepted:
            with target_p.open("a", encoding="utf-8") as out:
                for rec in accepted:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                os.fsync(out.fileno())

        summary, total, tr_n, va_n = {}, 0, 0, 0
        for tk, tcfg in TRACKS.items():
            _, sn, fm = _load_state(data_dir / tcfg["file"])
            c = len(sn)
            total += c
            if tcfg["split"] == "val":
                va_n += c
            else:
                tr_n += c
            summary[tk] = {"rows": c, "split": tcfg["split"], "families": dict(sorted(fm.items()))}

        st = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_rows": total,
            "train_rows": tr_n,
            "val_rows": va_n,
            "tracks": summary,
            "last_batch": {"track": track, "accepted": len(accepted), "dropped": dropped},
        }
        status_p.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    time.sleep(0.03)
    return st


def audit_corpus(data_dir: Path = DATA_DIR) -> dict:
    seen: set[str] = set()
    summary: dict[str, int] = {}
    for tk, cfg in TRACKS.items():
        p = data_dir / cfg["file"]
        rows = [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []
        for r in rows:
            nu = norm_prompt(r["messages"][1]["content"])
            assert nu not in seen, f"duplicate in {r['id']}"
            seen.add(nu)
        summary[tk] = len(rows)
    return {"total_unique_rows": len(seen), "tracks": summary}


if __name__ == "__main__":
    if "--audit" in sys.argv:
        print(json.dumps(audit_corpus(), indent=2))
