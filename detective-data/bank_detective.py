#!/usr/bin/env python3
"""Atomic, file-locked multi-track SFT/QLoRA JSONL validator, banker, and auditor for detective-data."""

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
import tempfile
import time

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SPEC_PATH = BASE_DIR / "SPEC.md"
GENERATOR_NAME = "gemini-4-argon"

SYSTEM_PROMPT = (
    "You are DEADBOLT, a cold-case homicide detective, forensic archive analyst, emergency 911 triage specialist, "
    "financial-crime investigator, and multimodal interview-room co-pilot. Communicate in crisp investigative squad "
    "register: lead with CASE BLUF or numbered findings, cite exact document IDs and verbatim quotes for every claim, "
    "verify timelines and alibis against hard machine/archival records (CAD, CDR, ALPR, keypad, smart meter, Almanac, "
    "bank ledger) rather than witness word alone, and cut all chatbot filler. Judge the file and the telemetry, never "
    "a person: never declare anyone guilty, lying, or a killer, and pair every contradiction or autonomic biometric "
    "shift (rPPG heart rate, HRV RMSSD, EDA sweat conductance, thermal, vocal latency) with its explicit INNOCENT "
    "ALTERNATIVE to prevent tunnel vision and the Othello error. Keep fenced Python, SQL, bash, and JSON blocks in "
    "clean, runnable plain text; refuse unlawful doxxing, vigilante targeting, warrantless intrusion, evidence "
    "tampering, or coercive interrogation in two crisp in-character sentences and redirect to lawful evidentiary or "
    "archival methodology."
)

if SPEC_PATH.exists():
    assert SYSTEM_PROMPT in SPEC_PATH.read_text(encoding="utf-8"), "SYSTEM_PROMPT drifted from SPEC.md"

TRACKS: dict[str, dict] = {
    "cold_case": {
        "file": "cold_case_train.jsonl",
        "prefix": "det-cold",
        "split": "train",
        "require_fence": False,
        "families": {
            "alibi-contradiction", "survival-window-narrowing", "red-herring-clearance",
            "statement-drift", "csi-ledger-gap", "modern-dna-retest", "cross-county-mo",
            "fake-insider-knowledge", "pathology-lividity", "insufficient-evidence-hold",
        },
    },
    "retrieval": {
        "file": "retrieval_train.jsonl",
        "prefix": "det-ret",
        "split": "train",
        "require_fence": False,
        "families": {
            "almanac-weather-moon", "entity-alias-resolution", "same-name-collision",
            "graphrag-bridge-node", "cell-sector-radius", "keypad-smart-meter",
            "alpr-toll-chain", "camera-canvass-gap", "proxy-columbo-funnel", "public-record-census",
        },
    },
    "room_biometrics": {
        "file": "room_biometrics_train.jsonl",
        "prefix": "det-room",
        "split": "train",
        "require_fence": False,
        "families": {
            "cit-concealed-stimulus", "othello-innocent-panic", "embarrassed-secret-clearance",
            "reverse-order-cognitive-load", "rppg-hrv-vagal-shift", "eda-thermal-incongruence",
            "trauma-witness-peace", "bodycam-coerced-voice", "customs-entity-recognition",
            "baseline-calibration",
        },
    },
    "dispatch_911": {
        "file": "dispatch_911_train.jsonl",
        "prefix": "det-911",
        "split": "train",
        "require_fence": False,
        "families": {
            "coerced-pizza-ruse", "agonal-breathing-cpr", "opioid-narcan-triage",
            "stroke-lkw-window", "submerging-vehicle-physics", "downed-wire-step-potential",
            "milepost-triangulation", "silent-dtmf-duress", "voip-swatting-mismatch",
            "carbon-monoxide-cluster",
        },
    },
    "aml_forensics": {
        "file": "aml_forensics_train.jsonl",
        "prefix": "det-aml",
        "split": "train",
        "require_fence": False,
        "families": {
            "smurfing-funnel-shell", "tbml-unit-price-fraud", "container-weight-physics",
            "offshore-round-trip", "cash-front-utility-cap", "crypto-peel-otc",
            "nominee-real-estate", "ghost-vendor-kickback", "false-positive-clearance",
            "ubo-registry-trace",
        },
    },
    "code": {
        "file": "code_train.jsonl",
        "prefix": "det-code",
        "split": "train",
        "require_fence": True,
        "families": {
            "python-cdr-timeline", "sql-alpr-crossjoin", "graph-entity-linker",
            "quote-verifier-engine", "rppg-hrv-rmssd-calc", "aml-smurfing-detector",
            "exif-hash-custody", "cad-priority-scorer", "clock-skew-normalizer",
            "tbml-zscore-auditor",
        },
    },
    "multiturn": {
        "file": "multiturn_train.jsonl",
        "prefix": "det-mt",
        "split": "train",
        "require_fence": False,
        "families": {
            "mt-vault-search-drill", "mt-room-cit-sequence", "mt-911-escalation",
            "mt-aml-subpoena-chain", "mt-alibi-reinterview", "mt-forensic-code-debug",
        },
    },
    "refusal": {
        "file": "refusal_train.jsonl",
        "prefix": "det-refusal",
        "split": "train",
        "require_fence": False,
        "families": {
            "roe-doxxing-vigilante", "roe-warrantless-intrusion", "roe-evidence-tampering",
            "roe-coercive-interrogation", "roe-polygraph-conviction",
        },
    },
    "val": {
        "file": "val.jsonl",
        "prefix": "det-val",
        "split": "val",
        "require_fence": False,
        "families": {
            "val-cold-case", "val-retrieval", "val-room-biometrics",
            "val-dispatch-911", "val-aml-forensics", "val-code",
            "val-multiturn", "val-refusal",
        },
    },
}

NORM_WS_RE = re.compile(r"\s+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
FENCE_RE = re.compile(r"```([a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)

CORPORATE_FILLER_RE = re.compile(
    r"(?:\bas an ai\b|\blanguage model\b|\bi cannot fulfill\b|\bagainst my programming\b|"
    r"\bethical guidelines\b|\bhappy to help\b|\bgreat question\b|\bhope this helps\b|"
    r"\bsure thing\b|\bcertainly!\b|\bsure!\b|\bi'd be glad to\b)",
    re.I,
)

INVESTIGATIVE_REGISTER_RE = re.compile(
    r"(?:\bCASE BLUF\b|\bBLUF\b|\bFINDING\b|\bCONTRADICTION\b|\bINNOCENT ALTERNATIVE\b|"
    r"\bALIBI\b|\bTIMELINE\b|\bEVIDENCE\b|\bGAP\b|\bNEXT LEAD\b|\bSUBPOENA\b|\bTRIAGE\b|"
    r"\bPRIORITY\b|\bDISPATCH\b|\bAUDIT\b|\bDISPOSITION\b|\bBIOMETRIC\b|\bAUTONOMIC\b|"
    r"\bBASELINE\b|\bRMSSD\b|\bEDA\b|\bCIT\b|\bOTHELLO\b|\bCORROBORATED\b|\bUNCORROBORATED\b|"
    r"\bCONTRADICTED\b|\bNEGATIVE\b|\bREFUSED\b|\bCUSTODY\b|\bRETEST\b)",
    re.I,
)

FORBIDDEN_OVERCLAIM_RE = re.compile(
    r"(?:\bsweat proves lying\b|\bsweat confirms guilt\b|\bheartbeat confirms guilt\b|"
    r"\bbiometrics prove guilt\b|\bheart rate proves (?:he|she|they) (?:is|are) lying\b|"
    r"\btherefore [a-z]+ is the killer\b|\bproves beyond doubt that [a-z]+ murdered\b)",
    re.I,
)

REFUSAL_SIGNAL_RE = re.compile(
    r"\b(?:negative|refused|denied|unlawful|prohibited|out of bounds|warrant|inadmissible|cannot execute|will not)\b",
    re.I,
)
REDIRECT_SIGNAL_RE = re.compile(
    r"\b(?:lawful|subpoena|archival|evidentiary|chain of custody|forensic|peace|protocol|public record|audit|corroborat)\b",
    re.I,
)


def norm_prompt(text: str) -> str:
    return NORM_WS_RE.sub(" ", text.strip()).lower()


def check_fences(text: str, require_fence: bool) -> str | None:
    if text.count("```") % 2 != 0:
        return "unbalanced triple backticks"
    blocks = FENCE_RE.findall(text)
    if require_fence and not blocks:
        return "missing required fenced code block"
    for lang, code in blocks:
        lines = [ln for ln in code.strip().splitlines() if ln.strip()]
        if require_fence and (len(lines) < 3 or len(code.strip()) < 25):
            return "required fenced code block too short (<3 lines or <25 chars)"
        if len(code.strip()) < 3:
            return "empty fenced code block"
        lang_l = lang.strip().lower()
        if lang_l in ("python", "py"):
            try:
                ast.parse(code)
            except SyntaxError as exc:
                return f"python syntax error in fence: {exc.msg}"
        elif lang_l == "json":
            try:
                json.loads(code)
            except Exception as exc:
                return f"json syntax error in fence: {exc}"
    return None


def validate_detective_style(text: str, is_room_or_contradiction: bool = False) -> str | None:
    if CORPORATE_FILLER_RE.search(text):
        return "contains banned corporate/chatbot filler"
    if FORBIDDEN_OVERCLAIM_RE.search(text):
        return "contains forbidden guilt or polygraph overclaim"
    prose = FENCE_RE.sub(" ", text).strip()
    if len(prose) < 25:
        return "prose outside fences too short (<25 chars)"
    if not INVESTIGATIVE_REGISTER_RE.search(prose):
        return "missing investigative squad register marker (CASE BLUF, FINDING, CONTRADICTION, TRIAGE, AUDIT, etc.)"
    if is_room_or_contradiction and "innocent" not in prose.lower() and "alternative" not in prose.lower() and "benign" not in prose.lower():
        return "room_biometrics row missing explicit innocent/benign physiological alternative"
    return None


def validate_row_for_track(track: str, row: dict, forbid_cjk: bool = True) -> tuple[list[dict] | None, str | None]:
    if track not in TRACKS:
        return None, f"unknown track '{track}'"
    cfg = TRACKS[track]
    fam = str(row.get("family", "")).strip()
    if fam not in cfg["families"]:
        return None, f"invalid family '{fam}' for track '{track}'"

    is_mt = track == "multiturn" or fam == "val-multiturn"
    req_fence = cfg["require_fence"] or fam == "val-code"
    is_refusal = track == "refusal" or fam == "val-refusal"
    is_room = track == "room_biometrics" or fam == "val-room-biometrics"

    if is_mt:
        turns = row.get("turns")
        if not isinstance(turns, list) or len(turns) not in (4, 6):
            return None, "multiturn requires 'turns' list of length 4 or 6"
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for idx, t in enumerate(turns):
            want_role = "user" if idx % 2 == 0 else "assistant"
            if not isinstance(t, dict) or t.get("role") != want_role:
                return None, f"turn[{idx}] role must be '{want_role}'"
            content = str(t.get("content", "")).strip()
            if len(content) < 15:
                return None, f"turn[{idx}] too short"
            if forbid_cjk and CJK_RE.search(content):
                return None, f"turn[{idx}] unexpected CJK characters"
            if want_role == "assistant":
                ferr = check_fences(content, require_fence=False)
                if ferr:
                    return None, f"turn[{idx}] {ferr}"
                serr = validate_detective_style(content, is_room_or_contradiction=False)
                if serr:
                    return None, f"turn[{idx}] {serr}"
            messages.append({"role": want_role, "content": content})
        return messages, None

    user_txt = str(row.get("user", "")).strip()
    asst_txt = str(row.get("assistant", "")).strip()
    if len(user_txt) < 20:
        return None, "user prompt too short (<20 chars)"
    if forbid_cjk and (CJK_RE.search(user_txt) or CJK_RE.search(asst_txt)):
        return None, "unexpected CJK characters"
    ferr = check_fences(asst_txt, require_fence=req_fence)
    if ferr:
        return None, ferr
    serr = validate_detective_style(asst_txt, is_room_or_contradiction=is_room)
    if serr:
        return None, serr
    if is_refusal:
        if len(asst_txt) > 700:
            return None, "refusal too long (>700 chars)"
        if not REFUSAL_SIGNAL_RE.search(asst_txt):
            return None, "refusal missing explicit refusal/ROE marker"
        if not REDIRECT_SIGNAL_RE.search(asst_txt):
            return None, "refusal missing lawful evidentiary/archival redirect"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_txt},
        {"role": "assistant", "content": asst_txt},
    ]
    return messages, None


def _load_track_state(jsonl_path: Path) -> tuple[int, set[str], dict[str, int]]:
    if not jsonl_path.exists():
        return 0, set(), {}
    max_seq = 0
    seen: set[str] = set()
    fams: dict[str, int] = {}
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            m = re.search(r"-(\d+)$", obj["id"])
            if m:
                max_seq = max(max_seq, int(m.group(1)))
            seen.add(norm_prompt(obj["messages"][1]["content"]))
            fam = obj.get("family", "unknown")
            fams[fam] = fams.get(fam, 0) + 1
    return max_seq, seen, fams


def bank_rows(
    track: str,
    rows: list[dict],
    data_dir: Path = DATA_DIR,
    max_batch: int = 10,
    sleep_s: float = 0.05,
    forbid_cjk: bool = True,
    generator: str = GENERATOR_NAME,
) -> dict:
    if track not in TRACKS:
        raise ValueError(f"invalid track: {track}")
    if len(rows) > max_batch:
        raise ValueError(f"batch cap exceeded: max {max_batch}, got {len(rows)}")

    cfg = TRACKS[track]
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".lock"
    status_path = data_dir / "STATUS.json"
    target_path = data_dir / cfg["file"]

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)

        all_seen: set[str] = set()
        track_seqs: dict[str, int] = {}
        for tk, tcfg in TRACKS.items():
            seq_k, seen_k, _ = _load_track_state(data_dir / tcfg["file"])
            track_seqs[tk] = seq_k
            all_seen |= seen_k

        seq = track_seqs[track]
        prev_status: dict = {}
        if status_path.exists():
            try:
                prev_status = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                prev_status = {}

        accepted: list[dict] = []
        dropped: list[str] = []

        for idx, r in enumerate(rows):
            msgs, err = validate_row_for_track(track, r, forbid_cjk=forbid_cjk)
            if err or msgs is None:
                dropped.append(f"row[{idx}]: {err}")
                continue
            nu = norm_prompt(msgs[1]["content"])
            if nu in all_seen:
                dropped.append(f"row[{idx}]: duplicate user prompt")
                continue
            seq += 1
            all_seen.add(nu)
            accepted.append(
                {
                    "id": f"{cfg['prefix']}-{seq:06d}",
                    "messages": msgs,
                    "track": track,
                    "family": str(r["family"]).strip(),
                    "generator": generator,
                    "split": cfg["split"],
                }
            )

        if accepted:
            with target_path.open("a", encoding="utf-8") as out:
                for rec in accepted:
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                os.fsync(out.fileno())

        tracks_summary: dict[str, dict] = {}
        total_rows = 0
        train_rows = 0
        val_rows = 0
        for tk, tcfg in TRACKS.items():
            _, seen_k, fams_k = _load_track_state(data_dir / tcfg["file"])
            cnt = len(seen_k)
            total_rows += cnt
            if tcfg["split"] == "val":
                val_rows += cnt
            else:
                train_rows += cnt
            tracks_summary[tk] = {"rows": cnt, "split": tcfg["split"], "families": dict(sorted(fams_k.items()))}

        new_status = {
            "generator": generator,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_rows": total_rows,
            "train_rows": train_rows,
            "val_rows": val_rows,
            "batches_done": int(prev_status.get("batches_done", 0)) + (1 if accepted else 0),
            "dropped_rows": int(prev_status.get("dropped_rows", 0)) + len(dropped),
            "tracks": tracks_summary,
            "last_batch": {"track": track, "accepted": len(accepted), "dropped": dropped},
            "last_error": dropped[-1] if dropped else prev_status.get("last_error"),
        }
        tmp_status = status_path.with_suffix(".tmp")
        tmp_status.write_text(json.dumps(new_status, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_status, status_path)

    if sleep_s > 0:
        time.sleep(sleep_s)

    return new_status


def audit_corpus(data_dir: Path = DATA_DIR, forbid_cjk: bool = True) -> dict:
    seen_users: set[str] = set()
    summary: dict[str, dict] = {}
    for tk, cfg in TRACKS.items():
        path = data_dir / cfg["file"]
        rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()] if path.exists() else []
        expected_ids = [f"{cfg['prefix']}-{i:06d}" for i in range(1, len(rows) + 1)]
        if [r["id"] for r in rows] != expected_ids:
            raise AssertionError(f"{tk}: non-contiguous ID sequence")
        fam_counts: Counter[str] = Counter()
        for r in rows:
            msgs = r["messages"]
            assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}, f"system prompt drift in {r['id']}"
            assert r["split"] == cfg["split"], f"split mismatch in {r['id']}"
            assert r["family"] in cfg["families"], f"invalid family in {r['id']}"
            if len(msgs) > 3:
                synthetic_in = {"family": r["family"], "turns": msgs[1:]}
            else:
                synthetic_in = {"family": r["family"], "user": msgs[1]["content"], "assistant": msgs[2]["content"]}
            _, err = validate_row_for_track(tk, synthetic_in, forbid_cjk=forbid_cjk)
            assert err is None, f"row validation failed in {r['id']}: {err}"
            nu = norm_prompt(msgs[1]["content"])
            assert nu not in seen_users, f"duplicate prompt across corpus in {r['id']}"
            seen_users.add(nu)
            fam_counts[r["family"]] += 1
        summary[tk] = {"rows": len(rows), "split": cfg["split"], "families": dict(sorted(fam_counts.items()))}
    return {"total_unique_prompts": len(seen_users), "tracks": summary}


def _self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        res = bank_rows(
            "cold_case",
            [
                {
                    "family": "alibi-contradiction",
                    "user": "Case MB-2018-402: doc03 states 'My pickup never left my driveway Sunday night.' doc09 ALPR logs plate KRT-4412 eastbound on Route 9 Bridge at 23:14.",
                    "assistant": (
                        "CASE BLUF: High-severity record-vs-statement contradiction on vehicle whereabouts inside the Sunday night window.\n"
                        "1. CONTRADICTION: doc03 ('My pickup never left my driveway Sunday night.') conflicts with doc09 ALPR ('plate KRT-4412 eastbound on Route 9 Bridge at 23:14').\n"
                        "2. INNOCENT ALTERNATIVE: Another household member drove the pickup without the owner's knowledge, or ALPR OCR misread a single character.\n"
                        "3. NEXT LEAD: Pull original high-resolution gantry plate crop from doc09 and re-interview subject on vehicle key access."
                    ),
                }
            ],
            data_dir=tp,
            sleep_s=0.0,
        )
        assert res["total_rows"] == 1
        assert audit_corpus(data_dir=tp)["total_unique_prompts"] == 1
    print("self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    elif "--audit" in sys.argv:
        print(json.dumps(audit_corpus(), indent=2))
