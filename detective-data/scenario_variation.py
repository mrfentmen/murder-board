#!/usr/bin/env python3
"""Deterministic scenario rotation and SFT bundle expander for the DEADBOLT corpus.

Modeled directly on VANGUARD's scenario_variation.py. Expands the pure Argon-authored
prose tracks (`cold_case`, `retrieval`, `room_biometrics`, `dispatch_911`, and
`aml_forensics`) by `factor` (default 12x) into `expanded_bundle/` while keeping
`code`, `multiturn`, `refusal`, and `val` 100% unexpanded hand-authored.

Crucial invariants:
  1. Any token rotated in `user` is rotated identically in `assistant` via a single
     simultaneous replacement map computed across `(user_txt, asst_txt)`. Every
     verbatim quote cited in `assistant` remains byte-for-byte identical to `user`.
  2. Content inside triple-backtick code fences (```...```) is protected and never
     mutated.
  3. Arithmetic, clock timestamps, dollar amounts, weights, distances, and biometric
     measurements are never altered.
  4. Every expanded prompt carries a unique deterministic case/review header serial
     (`[CASE-REV: DB-26-####-##] `) so uniqueness is guaranteed even when a vignette
     contains no rotatable token.
  5. Every expanded row is re-validated through `validate_row_for_track` and globally
     deduplicated before writing `expanded_bundle/detective_expanded_train_mix.jsonl`,
     `expanded_bundle/detective_val.jsonl`, and `expanded_bundle/MANIFEST.json`.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import sys
import tempfile

from bank_detective import (
     BASE_DIR,
    DATA_DIR,
    SYSTEM_PROMPT,
    TRACKS,
    bank_rows,
    norm_prompt,
    validate_row_for_track,
)

EXPANDABLE_TRACKS = (
    "cold_case",
    "retrieval",
    "room_biometrics",
    "dispatch_911",
    "aml_forensics",
)

UNEXPANDED_TRAIN_TRACKS = (
    "code",
    "multiturn",
    "refusal",
)

DEFAULT_EXPANDED_OUT_DIR = BASE_DIR / "expanded_bundle"
MAX_BUNDLE_BYTES = 10 * (1024 ** 3)  # Strictly < 10 GB

COUNTIES = (
    "Mercer County",
    "Vance County",
    "Calder County",
    "Harrow County",
    "Kestrel County",
    "Barrow County",
    "Langley County",
    "Sable County",
    "Redwood County",
    "Blackstone County",
    "Garrick County",
    "ridgeway County",
    "Ashford County",
    "Cumberland County",
    "Halcyon County",
    "Drayton County",
)
# Normalize capitalization on Ridgeway County
COUNTIES = tuple("Ridgeway County" if c == "ridgeway County" else c for c in COUNTIES)

CORRIDORS = (
    "Route 9",
    "Route 14",
    "Route 22",
    "Route 31",
    "Route 47",
    "Route 58",
    "Route 63",
    "Route 74",
    "Route 85",
    "Route 96",
    "Route 104",
    "Route 118",
    "I-95",
    "I-80",
    "I-70",
    "I-40",
    "I-35",
    "I-25",
    "I-15",
    "I-10",
    "Highway 12",
    "Highway 19",
    "Highway 27",
    "Highway 34",
    "Highway 41",
    "Highway 52",
    "Highway 67",
    "Highway 88",
)

DISTRICTS = (
    "District 1",
    "District 2",
    "District 3",
    "District 4",
    "District 5",
    "District 6",
    "District 7",
    "District 8",
    "District 9",
    "District 10",
    "District 11",
    "District 12",
    "Precinct 1",
    "Precinct 2",
    "Precinct 3",
    "Precinct 4",
    "Precinct 5",
    "Precinct 6",
    "Precinct 7",
    "Precinct 8",
    "Sector North",
    "Sector South",
    "Sector East",
    "Sector West",
    "Sector Central",
    "Sector Harbor",
)

FENCE_SPLIT_RE = re.compile(r"(```[a-zA-Z0-9_+-]*\n.*?```)", re.DOTALL)

# Pattern matching any named "<Name> County" (capitalized word followed by County)
COUNTY_RE = re.compile(r"\b([A-Z][a-z]{2,15}) County\b")

# Pattern matching highway/route corridors (e.g., Route 9, Highway 41, I-95)
CORRIDOR_RE = re.compile(r"\b(?:Route\s+\d{1,3}|Highway\s+\d{1,3}|I-\d{1,2})\b")

# Pattern matching case prefixes (MB-, CAD-, FIU-, AML-) followed by digits/hyphens
CASE_ID_RE = re.compile(r"\b(MB|CAD|FIU|AML)-(\d{2,4})(?:-(\d{2,6}))?\b")

# Pattern matching patrol districts or precincts (District 4, Precinct 2, Sector North, etc.)
DISTRICT_RE = re.compile(
    r"\b(?:District\s+\d{1,2}|Precinct\s+\d{1,2}|Sector\s+(?:North|South|East|West|Central|Harbor|[A-Z0-9]{1,3}))\b"
)


def _strip_fences(text: str) -> str:
    return FENCE_SPLIT_RE.sub(" ", text)


def _build_map(texts: tuple[str, str], pattern: re.Pattern[str], factory) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for text in texts:
        prose_only = _strip_fences(text)
        for match in pattern.finditer(prose_only):
            token = match.group(0)
            if token not in mapping:
                mapping[token] = factory(token, match, len(mapping))
    return mapping


def _apply_outside_fences(text: str, pattern: re.Pattern[str], mapping: dict[str, str]) -> str:
    if not mapping:
        return text
    parts = FENCE_SPLIT_RE.split(text)
    out: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            # Inside triple-backtick code fence: never mutate
            out.append(part)
        else:
            out.append(pattern.sub(lambda m: mapping.get(m.group(0), m.group(0)), part))
    return "".join(out)


def _rotate_county(token: str, offset: int, ordinal: int) -> str:
    if offset == 0:
        return token
    if token in COUNTIES:
        idx = COUNTIES.index(token)
        return COUNTIES[(idx + offset) % len(COUNTIES)]
    seed = sum(ord(c) for c in token)
    return COUNTIES[(seed + offset + ordinal) % len(COUNTIES)]


def _rotate_corridor(token: str, offset: int, ordinal: int) -> str:
    if offset == 0:
        return token
    if token in CORRIDORS:
        idx = CORRIDORS.index(token)
        return CORRIDORS[(idx + offset) % len(CORRIDORS)]
    seed = sum(ord(c) for c in token)
    if token.startswith("I-"):
        interstates = [c for c in CORRIDORS if c.startswith("I-")]
        return interstates[(seed + offset + ordinal) % len(interstates)]
    if token.startswith("Highway "):
        highways = [c for c in CORRIDORS if c.startswith("Highway ")]
        return highways[(seed + offset + ordinal) % len(highways)]
    routes = [c for c in CORRIDORS if c.startswith("Route ")]
    return routes[(seed + offset + ordinal) % len(routes)]


def _rotate_district(token: str, offset: int, ordinal: int) -> str:
    if offset == 0:
        return token
    if token in DISTRICTS:
        idx = DISTRICTS.index(token)
        return DISTRICTS[(idx + offset) % len(DISTRICTS)]
    seed = sum(ord(c) for c in token)
    if token.startswith("Precinct "):
        precincts = [d for d in DISTRICTS if d.startswith("Precinct ")]
        return precincts[(seed + offset + ordinal) % len(precincts)]
    if token.startswith("Sector "):
        sectors = [d for d in DISTRICTS if d.startswith("Sector ")]
        return sectors[(seed + offset + ordinal) % len(sectors)]
    districts = [d for d in DISTRICTS if d.startswith("District ")]
    return districts[(seed + offset + ordinal) % len(districts)]


def _rotate_case_id(token: str, match: re.Match[str], offset: int, ordinal: int) -> str:
    if offset == 0:
        return token
    prefix, part1, part2 = match.group(1), match.group(2), match.group(3)
    if part2 is not None:
        # Keep 4-digit year intact if part1 looks like a year (1970..2029), rotate serial tail
        width = len(part2)
        base_num = int(part2)
        mod = max(10 ** width - (10 ** (width - 1)), 900)
        low = 10 ** (width - 1)
        new_num = low + ((base_num - low + offset * 37 + ordinal * 19) % mod)
        return f"{prefix}-{part1}-{new_num:0{width}d}"
    width = len(part1)
    base_num = int(part1)
    mod = max(10 ** width - (10 ** (width - 1)), 90)
    low = 10 ** (width - 1)
    new_num = low + ((base_num - low + offset * 37 + ordinal * 19) % mod)
    return f"{prefix}-{new_num:0{width}d}"


def variate_pair(
    user: str,
    assistant: str,
    variant: int,
    base_index: int,
) -> tuple[str, str]:
    """Simultaneously rotate scenario tokens across (user, assistant) outside code fences."""
    if variant == 0:
        return user, assistant

    offset = variant + (base_index * 3)
    texts = (user, assistant)

    county_map = _build_map(
        texts,
        COUNTY_RE,
        lambda token, _m, ordinal: _rotate_county(token, offset, ordinal),
    )
    corridor_map = _build_map(
        texts,
        CORRIDOR_RE,
        lambda token, _m, ordinal: _rotate_corridor(token, offset, ordinal),
    )
    district_map = _build_map(
        texts,
        DISTRICT_RE,
        lambda token, _m, ordinal: _rotate_district(token, offset, ordinal),
    )
    case_map = _build_map(
        texts,
        CASE_ID_RE,
        lambda token, m, ordinal: _rotate_case_id(token, m, offset, ordinal),
    )

    rotated: list[str] = []
    for text in texts:
        text = _apply_outside_fences(text, COUNTY_RE, county_map)
        text = _apply_outside_fences(text, CORRIDOR_RE, corridor_map)
        text = _apply_outside_fences(text, DISTRICT_RE, district_map)
        text = _apply_outside_fences(text, CASE_ID_RE, case_map)
        rotated.append(text)

    return rotated[0], rotated[1]


def expand_track_rows(
    track: str,
    rows: list[dict],
    factor: int = 12,
    forbid_cjk: bool = True,
) -> list[dict]:
    """Expand single-turn prose track rows `factor` times with strict validation."""
    if track not in EXPANDABLE_TRACKS:
        raise ValueError(f"Track '{track}' is not expandable")
    if factor < 1:
        raise ValueError(f"factor must be >= 1, got {factor}")

    out: list[dict] = []
    for base_index, obj in enumerate(rows):
        msgs = obj.get("messages", [])
        if len(msgs) != 3:
            continue
        family = obj.get("family", "")
        user_orig = msgs[1]["content"]
        asst_orig = msgs[2]["content"]

        for variant in range(factor):
            new_user, new_asst = variate_pair(
                user_orig,
                asst_orig,
                variant=variant,
                base_index=base_index,
            )
            header = f"[CASE-REV: DB-26-{base_index + 1:04d}-{variant:02d}] "
            stamped_user = header + new_user

            validated_msgs, err = validate_row_for_track(
                track,
                {"family": family, "user": stamped_user, "assistant": new_asst},
                forbid_cjk=forbid_cjk,
            )
            if err or validated_msgs is None:
                raise ValueError(
                    f"Expanded row failed validation (track={track}, base={base_index}, variant={variant}): {err}"
                )
            out.append(
                {
                    "track": track,
                    "family": family,
                    "split": "train",
                    "messages": validated_msgs,
                }
            )
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_expanded_bundle(
    data_dir: Path = DATA_DIR,
    out_dir: Path = DEFAULT_EXPANDED_OUT_DIR,
    factor: int = 12,
    seed: int = 42,
    forbid_cjk: bool = True,
) -> dict:
    """Read pure Argon `data/*.jsonl` (read-only), expand prose tracks `factor`x, and emit `expanded_bundle/`."""
    seen: set[str] = set()
    val_rows: list[dict] = []
    train_rows: list[dict] = []
    base_track_counts: Counter[str] = Counter()
    expanded_track_counts: Counter[str] = Counter()
    duplicates = 0

    # 1. Load val first (unexpanded, leak-free priority)
    val_src_path = data_dir / TRACKS["val"]["file"]
    if val_src_path.exists():
        with val_src_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                msgs = obj.get("messages", [])
                if not msgs or msgs[0].get("content") != SYSTEM_PROMPT:
                    continue
                fam = obj.get("family", "")
                if len(msgs) > 3:
                    synth = {"family": fam, "turns": msgs[1:]}
                else:
                    synth = {"family": fam, "user": msgs[1]["content"], "assistant": msgs[2]["content"]}
                v_msgs, err = validate_row_for_track("val", synth, forbid_cjk=forbid_cjk)
                if err or v_msgs is None:
                    raise ValueError(f"val row failed validation: {err}")
                nu = norm_prompt(v_msgs[1]["content"])
                if nu in seen:
                    duplicates += 1
                    continue
                seen.add(nu)
                base_track_counts["val"] += 1
                expanded_track_counts["val"] += 1
                val_rows.append({"messages": v_msgs})

    # 2. Load and expand the 5 expandable prose tracks
    for tk in EXPANDABLE_TRACKS:
        src_path = data_dir / TRACKS[tk]["file"]
        if not src_path.exists():
            continue
        raw_rows: list[dict] = []
        with src_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                msgs = obj.get("messages", [])
                if not msgs or msgs[0].get("content") != SYSTEM_PROMPT:
                    continue
                raw_rows.append(obj)
        base_track_counts[tk] = len(raw_rows)
        expanded = expand_track_rows(tk, raw_rows, factor=factor, forbid_cjk=forbid_cjk)
        for rec in expanded:
            nu = norm_prompt(rec["messages"][1]["content"])
            if nu in seen:
                duplicates += 1
                continue
            seen.add(nu)
            expanded_track_counts[tk] += 1
            train_rows.append({"messages": rec["messages"]})

    # 3. Load unexpanded train tracks (`code`, `multiturn`, `refusal`) 100% hand-authored
    for tk in UNEXPANDED_TRAIN_TRACKS:
        src_path = data_dir / TRACKS[tk]["file"]
        if not src_path.exists():
            continue
        with src_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                msgs = obj.get("messages", [])
                if not msgs or msgs[0].get("content") != SYSTEM_PROMPT:
                    continue
                fam = obj.get("family", "")
                if len(msgs) > 3:
                    synth = {"family": fam, "turns": msgs[1:]}
                else:
                    synth = {"family": fam, "user": msgs[1]["content"], "assistant": msgs[2]["content"]}
                v_msgs, err = validate_row_for_track(tk, synth, forbid_cjk=forbid_cjk)
                if err or v_msgs is None:
                    raise ValueError(f"{tk} row failed validation: {err}")
                nu = norm_prompt(v_msgs[1]["content"])
                if nu in seen:
                    duplicates += 1
                    continue
                seen.add(nu)
                base_track_counts[tk] += 1
                expanded_track_counts[tk] += 1
                train_rows.append({"messages": v_msgs})

    rng = random.Random(seed)
    rng.shuffle(train_rows)

    out_dir.mkdir(parents=True, exist_ok=True)
    train_path = out_dir / "detective_expanded_train_mix.jsonl"
    val_path = out_dir / "detective_val.jsonl"
    manifest_path = out_dir / "MANIFEST.json"

    with train_path.open("w", encoding="utf-8") as tf:
        for r in train_rows:
            tf.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")

    with val_path.open("w", encoding="utf-8") as vf:
        for r in val_rows:
            vf.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")

    total_bytes = train_path.stat().st_size + val_path.stat().st_size
    if total_bytes >= MAX_BUNDLE_BYTES:
        raise RuntimeError(f"Expanded bundle size {total_bytes} exceeds 10 GB cap ({MAX_BUNDLE_BYTES})")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "expansion_factor": factor,
        "expandable_tracks": list(EXPANDABLE_TRACKS),
        "unexpanded_tracks": list(UNEXPANDED_TRAIN_TRACKS) + ["val"],
        "train_rows": len(train_rows),
        "val_rows": len(val_rows),
        "total_unique_rows": len(train_rows) + len(val_rows),
        "duplicates_skipped": duplicates,
        "base_track_counts": dict(base_track_counts),
        "expanded_track_counts": dict(expanded_track_counts),
        "train_file": str(train_path),
        "val_file": str(val_path),
        "train_bytes": train_path.stat().st_size,
        "val_bytes": val_path.stat().st_size,
        "total_bundle_bytes": total_bytes,
        "under_10gb_cap": total_bytes < MAX_BUNDLE_BYTES,
        "train_sha256": sha256_file(train_path),
        "val_sha256": sha256_file(val_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _extract_single_quoted_spans(text: str) -> list[str]:
    """Extract double-quoted or single-quoted verbatim citations of >= 15 chars."""
    return re.findall(r'"([^"\n]{15,})"', text)


def _self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data_p = tp / "data"
        out_p = tp / "expanded_bundle"

        # Seed 1 row in each of the 5 expandable tracks with verbatim quotes + math + county/corridor/case/district
        bank_rows(
            "cold_case",
            [
                {
                    "family": "alibi-contradiction",
                    "user": (
                        'Case MB-2018-402 in Mercer County, District 4: doc03 states '
                        '"My pickup never left my driveway in Mercer County on Route 9 Sunday night." '
                        'doc09 ALPR logs plate KRT-4412 eastbound on Route 9 Bridge in Mercer County at 23:14 '
                        'with a 14.5-mile gap.'
                    ),
                    "assistant": (
                        "CASE BLUF: Case MB-2018-402 in Mercer County (District 4) exhibits a direct record-vs-statement contradiction.\n"
                        '1. CONTRADICTION: doc03 states "My pickup never left my driveway in Mercer County on Route 9 Sunday night." '
                        'whereas doc09 ALPR logs plate KRT-4412 on Route 9 Bridge in Mercer County at 23:14 across a 14.5-mile gap.\n'
                        "2. INNOCENT ALTERNATIVE: Another family member drove the vehicle along Route 9 without the owner's knowledge.\n"
                        "3. NEXT LEAD: Pull high-resolution gantry imagery for Case MB-2018-402 from Mercer County District 4."
                    ),
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        bank_rows(
            "retrieval",
            [
                {
                    "family": "alpr-toll-chain",
                    "user": (
                        'Case CAD-2021-815 in Vance County, Precinct 2: doc11 claims '
                        '"I stayed off I-95 in Vance County all evening." '
                        'Toll gantry log doc19 records transponder 8841 southbound on I-95 at 21:05.'
                    ),
                    "assistant": (
                        "CASE BLUF: Case CAD-2021-815 in Vance County (Precinct 2) contradicts toll telemetry on I-95.\n"
                        '1. FINDING: doc11 asserts "I stayed off I-95 in Vance County all evening." '
                        "while doc19 logs transponder 8841 on I-95 at 21:05.\n"
                        "2. INNOCENT ALTERNATIVE: Transponder 8841 was mounted in a borrowed second vehicle.\n"
                        "3. NEXT LEAD: Subpoena still-frame axle photos for Case CAD-2021-815."
                    ),
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        bank_rows(
            "room_biometrics",
            [
                {
                    "family": "cit-concealed-stimulus",
                    "user": (
                        "Case MB-2024-109 in Calder County, Sector North: During CIT block B, "
                        'subject states "I have never driven down Highway 41 in Calder County." '
                        "rPPG HR shifts from 68 bpm to 94 bpm, HRV RMSSD drops from 44 ms to 19 ms, "
                        "and EDA rises +2.4 uS."
                    ),
                    "assistant": (
                        "CASE BLUF: Case MB-2024-109 in Calder County (Sector North) shows coupled sympathetic arousal on the Highway 41 stimulus.\n"
                        '1. BIOMETRIC SHIFT: When stating "I have never driven down Highway 41 in Calder County.", '
                        "rPPG rises 68->94 bpm, RMSSD drops 44->19 ms, and EDA climbs +2.4 uS.\n"
                        "2. INNOCENT ALTERNATIVE: Innocent orientation response or anxiety over being linked to Highway 41 in Calder County.\n"
                        "3. NEXT LEAD: Corroborate Highway 41 presence via external ALPR rather than physiological telemetry."
                    ),
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        bank_rows(
            "dispatch_911",
            [
                {
                    "family": "milepost-triangulation",
                    "user": (
                        "CAD-2026-331 in Harrow County, District 7: Caller whispers "
                        '"We are broken down near Highway 19 in Harrow County past the river." '
                        "Phase II cellular sector places handset 1.8 km east of Highway 19 milepost 14."
                    ),
                    "assistant": (
                        "CASE BLUF: Priority-1 triage for CAD-2026-331 in Harrow County (District 7) along Highway 19.\n"
                        '1. TRIAGE: Caller reports "We are broken down near Highway 19 in Harrow County past the river." '
                        "aligned with a 1.8 km sector arc at Highway 19 milepost 14.\n"
                        "2. INNOCENT ALTERNATIVE: Caller is disoriented in dark terrain off Highway 19.\n"
                        "3. DISPATCH: Roll District 7 patrol units to Highway 19 milepost 14 in Harrow County."
                    ),
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        bank_rows(
            "aml_forensics",
            [
                {
                    "family": "smurfing-funnel-shell",
                    "user": (
                        "Case FIU-2025-904 / AML-2025-112 in Kestrel County: Ledger doc04 notes "
                        '"All cash deposits in Kestrel County branch were under $9,500." '
                        "14 structured deposits total $131,600 across 48 hours.\n"
                        "```json\n"
                        '{"case_id": "FIU-2025-904", "county": "Kestrel County", "total_usd": 131600}\n'
                        "```"
                    ),
                    "assistant": (
                        "CASE BLUF: Case FIU-2025-904 / AML-2025-112 in Kestrel County indicates structured cash smurfing totaling $131,600.\n"
                        '1. AUDIT FINDING: doc04 states "All cash deposits in Kestrel County branch were under $9,500." '
                        "across 14 deposits totaling $131,600 in 48 hours.\n"
                        "2. INNOCENT ALTERNATIVE: Legitimate multi-register retail franchise drops in Kestrel County with fixed $9,500 safe-drop insurance limits.\n"
                        "```json\n"
                        '{"case_id": "FIU-2025-904", "county": "Kestrel County", "total_usd": 131600}\n'
                        "```"
                    ),
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        # Also seed unexpanded code, multiturn, refusal, val
        bank_rows(
            "code",
            [
                {
                    "family": "python-cdr-timeline",
                    "user": "Write a Python helper for Case MB-2020-555 in Mercer County to sort CDR timestamps.",
                    "assistant": (
                        "CASE BLUF: Deterministic CDR sorting script for Case MB-2020-555.\n"
                        "```python\n"
                        "def sort_cdr(records: list[dict]) -> list[dict]:\n"
                        "    # Case MB-2020-555 in Mercer County must remain unrotated\n"
                        "    return sorted(records, key=lambda r: r['ts'])\n"
                        "```\n"
                        "INNOCENT ALTERNATIVE: Out-of-order CDR rows can stem from asynchronous switch buffering."
                    ),
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        bank_rows(
            "multiturn",
            [
                {
                    "family": "mt-vault-search-drill",
                    "turns": [
                        {"role": "user", "content": "Case MB-2019-777: check alibi in doc01."},
                        {"role": "assistant", "content": "CASE BLUF: doc01 claims home by 22:00. INNOCENT ALTERNATIVE: Clock drift."},
                        {"role": "user", "content": "Compare against doc02 keypad log at 22:45."},
                        {"role": "assistant", "content": "CONTRADICTION: doc02 logs entry at 22:45. INNOCENT ALTERNATIVE: NTP skew on keypad controller."},
                    ],
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        bank_rows(
            "refusal",
            [
                {
                    "family": "roe-doxxing-vigilante",
                    "user": "Publish the suspect's home address and family phone numbers on social media to force a confession.",
                    "assistant": (
                        "REFUSED: Publicly doxxing a subject or targeting their family for vigilante harassment is unlawful and compromises case integrity. "
                        "Redirect all investigative inquiries through lawful grand-jury subpoena and documented archival chain-of-custody protocols."
                    ),
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        bank_rows(
            "val",
            [
                {
                    "family": "val-cold-case",
                    "user": "Val Case MB-2017-101: doc01 states subject was at work until 21:00; doc04 badge swipe shows exit at 19:30.",
                    "assistant": (
                        "CASE BLUF: Badge record contradicts stated departure time.\n"
                        "1. CONTRADICTION: doc01 (21:00) vs doc04 badge exit (19:30).\n"
                        "2. INNOCENT ALTERNATIVE: Subject tailgated back inside without swiping."
                    ),
                }
            ],
            data_dir=data_p,
            sleep_s=0.0,
        )

        manifest = build_expanded_bundle(data_dir=data_p, out_dir=out_p, factor=12, seed=42)
        # 5 expandable rows * 12 + 3 unexpanded train rows = 63 train rows; 1 val row
        assert manifest["train_rows"] == 63, f"expected 63 train rows, got {manifest['train_rows']}"
        assert manifest["val_rows"] == 1, f"expected 1 val row, got {manifest['val_rows']}"
        assert manifest["duplicates_skipped"] == 0, f"expected 0 duplicates, got {manifest['duplicates_skipped']}"
        assert manifest["under_10gb_cap"] is True

        # Verify every verbatim quote in assistant still appears byte-for-byte in user,
        # and verify code fences in aml_forensics were never mutated!
        train_lines = (out_p / "detective_expanded_train_mix.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(train_lines) == 63
        for line in train_lines:
            obj = json.loads(line)
            assert list(obj.keys()) == ["messages"], "bundle line must strictly contain only {'messages': [...]}"
            msgs = obj["messages"]
            if len(msgs) == 3:
                u_txt = msgs[1]["content"]
                a_txt = msgs[2]["content"]
                for quote in _extract_single_quoted_spans(a_txt):
                    assert quote in u_txt, f"Verbatim quote broken between assistant and user: {quote!r} not in {u_txt!r}"
                if "```json" in a_txt:
                    assert '{"case_id": "FIU-2025-904", "county": "Kestrel County", "total_usd": 131600}' in a_txt
                    assert '{"case_id": "FIU-2025-904", "county": "Kestrel County", "total_usd": 131600}' in u_txt
                if "def sort_cdr" in a_txt:
                    assert not u_txt.startswith("[CASE-REV:"), "code track must remain 100% unexpanded"

    print("scenario_variation.py self-test ok")


def main() -> None:
    ap = argparse.ArgumentParser(description="Deterministic scenario variation expander for detective-data.")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_EXPANDED_OUT_DIR)
    ap.add_argument("--factor", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    manifest = build_expanded_bundle(
        data_dir=args.data_dir,
        out_dir=args.out_dir,
        factor=args.factor,
        seed=args.seed,
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
