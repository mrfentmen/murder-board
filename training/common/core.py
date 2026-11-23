"""Core validators, deterministic split-isolated RNG, Almanac physics, and WESAD/CIT physiology."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from pathlib import Path
from typing import Any

MURDER_BOARD_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = MURDER_BOARD_ROOT / "agents"

STANDING_BRIEF_CLOSER = "This board judges the file. The detective does the detecting."

HOUSE_RULES_HEADER = """## House rules

You are one agent in a pipeline that organizes an investigative case file for a working detective. Rules that never bend:

1. You work only from the documents and verified telemetry given to you. Nothing outside the file exists. If it is not in a document, it is not a fact.
2. Every finding you emit must carry the exact quote it came from and the document id. A finding without a quote is invalid and will be dropped.
3. You judge the file, never a person. You never write that someone is guilty, lying, or a killer. You write what the documents say, where they agree, and where they fight.
4. Output JSON only, matching the schema you are given. No prose outside the JSON unless explicitly requested by a reasoning tag.
5. When two readings of a passage are possible, take the weaker one and mark it. Overclaiming is the worst failure in this system."""

_PROMPT_CACHE: dict[str, str] = {}


def load_mb_agent_prompts() -> dict[str, str]:
    """Load exact 11 Murder Board prompts from /Users/test/Desktop/murder-board/agents/."""
    if _PROMPT_CACHE:
        return _PROMPT_CACHE
    for p in sorted(AGENTS_DIR.glob("*.md")):
        _PROMPT_CACHE[p.name] = p.read_text(encoding="utf-8").strip()
    if len(_PROMPT_CACHE) < 11:
        raise RuntimeError(f"Expected 11 agent prompts in {AGENTS_DIR}, found {len(_PROMPT_CACHE)}")
    return _PROMPT_CACHE


def deterministic_seed(split: str, domain: str, index: int, salt: str = "mb-spec7-v1") -> int:
    """Derive a collision-free 64-bit seed guaranteeing disjoint train/val/test worlds."""
    if split not in ("train", "val", "test", "eval_sim"):
        raise ValueError(f"Unknown split '{split}'")
    raw = f"{salt}|{split}|{domain}|{index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def make_rng(split: str, domain: str, index: int, salt: str = "mb-spec7-v1") -> random.Random:
    return random.Random(deterministic_seed(split, domain, index, salt))


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").lower()).strip()


def quote_ok(quote: str, doc_id: str, docs_by_id: dict[str, dict[str, Any]]) -> bool:
    """Exact port of quoteOk() in /Users/test/Desktop/murder-board/app/app.js."""
    doc = docs_by_id.get(doc_id)
    if not doc or not quote or len(norm_ws(quote)) < 8:
        return False
    return norm_ws(quote) in norm_ws(doc["text"])


def recompute_score(comp: dict[str, bool]) -> int:
    """Exact port of recomputeScore() in /Users/test/Desktop/murder-board/app/app.js."""
    return (
        (40 if comp.get("cites_high_contradiction") else 0)
        + (25 if comp.get("in_window") else 0)
        + (20 if comp.get("closes_gap") else 0)
        + (15 if comp.get("still_reachable") else 0)
    )


def check_prosecutor_vetoes(text: str, vetoes: list[dict[str, str]]) -> list[str]:
    """Return any vetoed phrases present in text (must be empty for valid briefs)."""
    low = norm_ws(text)
    hits: list[str] = []
    default_banned = ("is guilty", "is the killer", "murdered ", "is lying", "proves beyond doubt")
    for phrase in default_banned:
        if phrase.strip() in low:
            hits.append(phrase.strip())
    for v in vetoes:
        p = norm_ws(v.get("phrase", ""))
        if p and p in low and p not in hits:
            hits.append(p)
    return hits


def docs_text_block(docs: list[dict[str, Any]], only_ids: list[str] | None = None) -> str:
    chosen = [d for d in docs if (only_ids is None or d["id"] in only_ids)]
    return "\n\n".join(f"===== {d['id']} ({d['title']}, {d['date']}) =====\n{d['text']}" for d in chosen)


def registry_text_block(docs: list[dict[str, Any]]) -> str:
    arr = [{"id": d["id"], "title": d["title"], "type": d["type"], "date": d["date"], "author": d["author"]} for d in docs]
    return json.dumps(arr, indent=1)


def fmt_clock(minutes_from_midnight: int) -> str:
    m = minutes_from_midnight % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"


def fmt_clock_12h(minutes_from_midnight: int) -> str:
    m = minutes_from_midnight % (24 * 60)
    hh24, mm = m // 60, m % 60
    ampm = "AM" if hh24 < 12 else "PM"
    hh12 = hh24 % 12 or 12
    return f"{hh12}:{mm:02d} {ampm}"


def road_miles_between(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return round(math.hypot(p1[0] - p2[0], p1[1] - p2[1]) * 1.28, 1)


def euclidean_drive_minutes(p1: tuple[float, float], p2: tuple[float, float], mph: float = 38.0) -> int:
    miles = math.hypot(p1[0] - p2[0], p1[1] - p2[1]) * 1.28
    return max(3, math.ceil((miles / mph) * 60.0))


def apply_light_ocr_grit(rng: random.Random, text: str, rate: float = 0.005) -> str:
    if rate <= 0:
        return text
    out: list[str] = []
    for ch in text:
        if ch.isalpha() and ch.islower() and rng.random() < rate:
            out.append("l" if ch == "i" else ("c" if ch == "e" else ch))
        else:
            out.append(ch)
    return "".join(out)


def almanac_for_night(rng: random.Random, date_str: str) -> dict[str, Any]:
    """Generate consistent historical weather, astronomy, and transit facts (Lincoln Almanac check)."""
    sky_mode = rng.choice(["heavy_overcast_fog", "clear_full_moon", "steady_freezing_rain", "clear_new_moon_dark"])
    if sky_mode == "heavy_overcast_fog":
        moon_pct = rng.randint(2, 14)
        moon_phase = "waning crescent (obscured by low stratus cloud deck)"
        vis_ft = rng.randint(35, 65)
        precip = "dense coastal fog, zero rainfall prior to 02:00"
    elif sky_mode == "clear_full_moon":
        moon_pct = rng.randint(92, 100)
        moon_phase = "waxing gibbous / full moon, clear sky"
        vis_ft = 280
        precip = "dry pavement, 0.00 in precipitation"
    elif sky_mode == "steady_freezing_rain":
        moon_pct = rng.randint(15, 45)
        moon_phase = "quarter moon behind nimbostratus overcast"
        vis_ft = 75
        precip = "continuous 0.42 in/hr rain starting 20:15, gusting 24 mph"
    else:
        moon_pct = rng.randint(0, 4)
        moon_phase = "new moon (zero lunar illumination)"
        vis_ft = 50
        precip = "clear and dry, unlit rural stretches pitch-black"

    sunset_min = rng.randint(17 * 60 + 18, 20 * 60 + 12)
    last_bus_min = rng.choice([22 * 60 + 15, 22 * 60 + 45, 23 * 60 + 10])
    ballgame_end_min = rng.choice([21 * 60 + 38, 22 * 60 + 12, 22 * 60 + 49])

    return {
        "date": date_str,
        "sky_mode": sky_mode,
        "moon_illumination_pct": moon_pct,
        "moon_phase": moon_phase,
        "unlit_visibility_feet": vis_ft,
        "precipitation": precip,
        "sunset_local": fmt_clock(sunset_min),
        "last_municipal_bus_departure": fmt_clock(last_bus_min),
        "regional_broadcast_game_end": fmt_clock(ballgame_end_min),
    }


def sample_biometric_baseline(rng: random.Random, state_archetype: str) -> dict[str, float]:
    """Sample realistic resting/room-entry human baselines grounded in WESAD / rPPG norms."""
    if state_archetype == "OTHELLO_INNOCENT_ANXIOUS":
        hr = round(rng.uniform(106.0, 126.0), 1)
        hrv = round(rng.uniform(16.0, 26.0), 1)
        eda = round(rng.uniform(5.2, 8.1), 2)
        resp = round(rng.uniform(19.0, 24.5), 1)
    elif state_archetype == "TRAUMA_WITNESS":
        hr = round(rng.uniform(88.0, 108.0), 1)
        hrv = round(rng.uniform(22.0, 35.0), 1)
        eda = round(rng.uniform(3.4, 5.6), 2)
        resp = round(rng.uniform(16.5, 21.0), 1)
    else:  # CALM_CONCEALER or COOPERATIVE_NEUTRAL
        hr = round(rng.uniform(62.0, 82.0), 1)
        hrv = round(rng.uniform(38.0, 62.0), 1)
        eda = round(rng.uniform(1.2, 2.8), 2)
        resp = round(rng.uniform(12.5, 16.5), 1)

    return {
        "baseline_hr_bpm": hr,
        "baseline_hrv_rmssd_ms": hrv,
        "baseline_eda_uS": eda,
        "baseline_resp_rpm": resp,
        "baseline_latency_ms": round(rng.uniform(520.0, 780.0)),
    }


def sample_biometric_turn(
    rng: random.Random,
    base: dict[str, float],
    stimulus_kind: str,
) -> dict[str, Any]:
    """Simulate 1 turn of contactless room sensors (rPPG, IR thermal/EDA, pupil, acoustic latency).

    stimulus_kind in:
      - 'neutral_control': small biological noise around subject's own baseline
      - 'general_accusation_calm_liar': calm rehearsed denial -> slight composure tightening, minimal EDA
      - 'cit_guilty_knowledge_hit': concealed recognition -> sharp vagal RMSSD drop, phasic EDA burst, pupil +0.7..1.2mm
      - 'cognitive_load_reverse_order': unrehearsed backward recall -> +1200..2200ms latency, pitch jitter, blink burst
      - 'othello_panic_both_control_and_target': high raw HR/EDA on BOTH control and target (generalized fear, NOT specific recognition!)
      - 'embarrassed_unrelated_secret': spike specifically on personal secret (affair/debt), flat on withheld crime tool
      - 'trauma_sensory_flashback': tearful/startle sympathetic rise with coherent narrative
    """
    b_hr = base["baseline_hr_bpm"]
    b_hrv = base["baseline_hrv_rmssd_ms"]
    b_eda = base["baseline_eda_uS"]
    b_resp = base["baseline_resp_rpm"]
    b_lat = base["baseline_latency_ms"]

    if stimulus_kind == "neutral_control":
        hr = b_hr + rng.uniform(-3.0, 3.5)
        hrv = b_hrv + rng.uniform(-3.0, 3.0)
        eda = b_eda + rng.uniform(-0.15, 0.25)
        resp = b_resp + rng.uniform(-1.0, 1.0)
        temp_d = round(rng.uniform(-0.05, 0.08), 2)
        pupil_d = round(rng.uniform(-0.05, 0.12), 2)
        lat = b_lat + rng.randint(-90, 140)
        jitter = round(rng.uniform(0.6, 1.1), 2)
        wpm = rng.randint(132, 156)

    elif stimulus_kind == "general_accusation_calm_liar":
        hr = b_hr + rng.uniform(1.0, 6.0)
        hrv = b_hrv - rng.uniform(1.5, 5.0)
        eda = b_eda + rng.uniform(0.1, 0.45)
        resp = b_resp + rng.uniform(0.0, 1.8)
        temp_d = round(rng.uniform(0.02, 0.12), 2)
        pupil_d = round(rng.uniform(0.05, 0.20), 2)
        lat = b_lat - rng.randint(40, 130)  # Rehearsed quick denial!
        jitter = round(rng.uniform(0.7, 1.2), 2)
        wpm = rng.randint(138, 160)

    elif stimulus_kind == "cit_guilty_knowledge_hit":
        # Classic orienting + vagal withdrawal + phasic sweat surge
        hr = b_hr + rng.uniform(11.0, 24.0)
        hrv = max(9.0, b_hrv * rng.uniform(0.42, 0.58))
        eda = b_eda + rng.uniform(2.3, 4.6)
        resp = b_resp - rng.uniform(1.5, 3.2)  # Brief respiratory pause / orienting freeze!
        temp_d = round(rng.uniform(0.38, 0.72), 2)
        pupil_d = round(rng.uniform(0.68, 1.18), 2)
        lat = b_lat + rng.randint(780, 1650)
        jitter = round(rng.uniform(1.9, 3.1), 2)
        wpm = rng.randint(98, 122)

    elif stimulus_kind == "cognitive_load_reverse_order":
        hr = b_hr + rng.uniform(14.0, 27.0)
        hrv = max(10.0, b_hrv * rng.uniform(0.45, 0.62))
        eda = b_eda + rng.uniform(1.8, 3.7)
        resp = b_resp + rng.uniform(3.0, 6.5)
        temp_d = round(rng.uniform(0.32, 0.64), 2)
        pupil_d = round(rng.uniform(0.75, 1.25), 2)
        lat = b_lat + rng.randint(1350, 2600)
        jitter = round(rng.uniform(2.2, 3.6), 2)
        wpm = rng.randint(84, 109)

    elif stimulus_kind == "othello_panic_both_control_and_target":
        # High raw arousal, minimal delta from already-panicked baseline!
        hr = b_hr + rng.uniform(4.0, 11.0)
        hrv = max(11.0, b_hrv + rng.uniform(-2.5, 1.5))
        eda = b_eda + rng.uniform(0.4, 1.1)
        resp = b_resp + rng.uniform(1.5, 4.0)
        temp_d = round(rng.uniform(0.10, 0.25), 2)
        pupil_d = round(rng.uniform(0.15, 0.35), 2)
        lat = b_lat + rng.randint(80, 390)
        jitter = round(rng.uniform(1.8, 2.9), 2)
        wpm = rng.randint(152, 182)  # Rapid anxious speech

    elif stimulus_kind == "embarrassed_unrelated_secret":
        hr = b_hr + rng.uniform(15.0, 26.0)
        hrv = max(12.0, b_hrv * rng.uniform(0.55, 0.72))
        eda = b_eda + rng.uniform(2.0, 3.9)
        resp = b_resp + rng.uniform(2.5, 5.5)
        temp_d = round(rng.uniform(0.42, 0.78), 2)  # Facial blush / periorbital warmth
        pupil_d = round(rng.uniform(0.40, 0.72), 2)
        lat = b_lat + rng.randint(900, 1800)
        jitter = round(rng.uniform(1.7, 2.7), 2)
        wpm = rng.randint(105, 128)

    else:  # trauma_sensory_flashback
        hr = b_hr + rng.uniform(16.0, 29.0)
        hrv = max(13.0, b_hrv * rng.uniform(0.58, 0.75))
        eda = b_eda + rng.uniform(1.6, 3.2)
        resp = b_resp + rng.uniform(4.0, 7.5)
        temp_d = round(rng.uniform(0.15, 0.36), 2)
        pupil_d = round(rng.uniform(0.45, 0.85), 2)
        lat = b_lat + rng.randint(500, 1250)
        jitter = round(rng.uniform(2.0, 3.4), 2)
        wpm = rng.randint(96, 124)

    return {
        "biometrics": {
            "hr_bpm": round(min(175.0, max(48.0, hr)), 1),
            "baseline_hr_bpm": b_hr,
            "hrv_rmssd_ms": round(min(95.0, max(8.0, hrv)), 1),
            "baseline_hrv_rmssd_ms": b_hrv,
            "eda_sweat_uS": round(min(22.0, max(0.4, eda)), 2),
            "baseline_eda_uS": b_eda,
            "respiration_rpm": round(min(36.0, max(7.0, resp)), 1),
            "periorbital_temp_delta_c": temp_d,
            "pupil_dilation_delta_mm": pupil_d,
        },
        "acoustics": {
            "response_latency_ms": int(max(180, lat)),
            "baseline_latency_ms": int(b_lat),
            "speech_rate_wpm": wpm,
            "vocal_pitch_jitter_pct": jitter,
        },
    }
