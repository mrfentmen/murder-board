"""Layer C — The 8 Forensic Investigative Micro-Skill Drills (SPEC 7, Track 1 NOW).

Implements deterministic, split-isolated SFT + RLVR/GRPO generators for:
  1. temporal_clock_math
  2. forensic_nli
  3. entity_resolution_graph
  4. name_collision_guard
  5. pathology_and_trace
  6. digital_machine_literacy
  7. hypothesis_tournament
  8. fake_insider_knowledge

100% Python stdlib, grounded in Murder Board House Rules and training.common.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any

from training.common.core import (
    HOUSE_RULES_HEADER,
    STANDING_BRIEF_CLOSER,
    check_prosecutor_vetoes,
    docs_text_block,
    euclidean_drive_minutes,
    fmt_clock,
    fmt_clock_12h,
    make_rng,
    quote_ok,
    registry_text_block,
    road_miles_between,
)
from training.common.pools import (
    ALIAS_NICKNAMES,
    COUNTIES,
    FIRST_NAMES,
    LAST_NAMES,
    SHELL_PREFIXES,
    SHELL_SUFFIXES,
    STREET_ROOTS,
    STREET_SUFFIXES,
    VEHICLES,
    pick_distinct,
    random_address,
    random_plate,
    sample_unique_names,
)

MICRO_SKILL_TYPES: tuple[str, ...] = (
    "temporal_clock_math",
    "forensic_nli",
    "entity_resolution_graph",
    "name_collision_guard",
    "pathology_and_trace",
    "digital_machine_literacy",
    "hypothesis_tournament",
    "fake_insider_knowledge",
)

_EXTRA_VETOES: list[dict[str, str]] = [
    {"phrase": "murdered"},
    {"phrase": "is guilty"},
    {"phrase": "is lying"},
    {"phrase": "is the killer"},
    {"phrase": "proves beyond doubt"},
]


def _iso_dt(date_str: str, minutes_from_midnight: int) -> str:
    """Format minutes relative to date_str midnight (handling >=1440 next-day rollover)."""
    year, month, day = (int(x) for x in date_str.split("-"))
    day_offset = minutes_from_midnight // 1440
    rem = minutes_from_midnight % 1440
    # Safe day rollover by choosing dates 1..25 in procedural generators.
    return f"{year:04d}-{month:02d}-{day + day_offset:02d}T{rem // 60:02d}:{rem % 60:02d}:00"


def _sample_incident_date(rng: random.Random, min_year: int = 2012, max_year: int = 2025) -> str:
    year = rng.randint(min_year, max_year)
    month = rng.randint(1, 12)
    day = rng.randint(3, 24)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _sample_phone(rng: random.Random, area: int | None = None) -> str:
    ac = area if area is not None else rng.choice((207, 315, 412, 509, 607, 716, 814, 912))
    exch = rng.randint(210, 899)
    line = rng.randint(1020, 9989)
    return f"({ac}) {exch}-{line}"


def _format_assistant_turn(reasoning_lines: list[str], payload: dict[str, Any]) -> str:
    reasoning_text = "\n".join(reasoning_lines).strip()
    return f"<reasoning>\n{reasoning_text}\n</reasoning>\n{json.dumps(payload, indent=2)}"


def _build_system_prompt(chair_title: str, task_instructions: str, schema_hint: str) -> str:
    return (
        f"{HOUSE_RULES_HEADER}\n\n"
        f"## {chair_title}\n\n"
        f"{task_instructions}\n\n"
        "First write concise step-by-step verification inside `<reasoning>...</reasoning>`, "
        "then output ONLY valid JSON matching this exact schema:\n"
        f"{schema_hint}"
    )


def _build_user_prompt(
    case_id: str,
    drill_header: str,
    docs: list[dict[str, Any]],
    extra_directive: str = "",
) -> str:
    parts = [
        f"CASE FILE: {case_id}",
        drill_header,
        "### Document Registry",
        registry_text_block(docs),
        "### Exhibits",
        docs_text_block(docs),
    ]
    if extra_directive:
        parts.append(extra_directive)
    return "\n\n".join(parts)


def _collect_quote_pairs(node: Any, out: list[tuple[str, str]]) -> None:
    if isinstance(node, dict):
        if "quote" in node and "doc_id" in node and node["quote"] is not None:
            out.append((str(node["doc_id"]), str(node["quote"])))
        if "a_quote" in node and "a_doc" in node and node["a_quote"] is not None:
            out.append((str(node["a_doc"]), str(node["a_quote"])))
        if "b_quote" in node and "b_doc" in node and node["b_quote"] is not None:
            out.append((str(node["b_doc"]), str(node["b_quote"])))
        for v in node.values():
            _collect_quote_pairs(v, out)
    elif isinstance(node, list):
        for item in node:
            _collect_quote_pairs(item, out)


def validate_micro_skill_example(example: dict[str, Any]) -> list[str]:
    """Validate structure, JSON schema parseability, quote_ok(), and zero Prosecutor vetoes."""
    errors: list[str] = []
    for req_key in ("id", "track", "domain", "subtask", "split", "messages", "ground_truth"):
        if req_key not in example:
            errors.append(f"missing_top_key:{req_key}")
    if errors:
        return errors

    if example["track"] != "track1_now":
        errors.append(f"bad_track:{example['track']}")
    if example["domain"] != "forensic_micro_skills":
        errors.append(f"bad_domain:{example['domain']}")
    if example["subtask"] not in MICRO_SKILL_TYPES:
        errors.append(f"bad_subtask:{example['subtask']}")

    msgs = example["messages"]
    if len(msgs) != 3 or [m["role"] for m in msgs] != ["system", "user", "assistant"]:
        errors.append("bad_messages_roles")
        return errors

    assistant_text = msgs[2]["content"]
    veto_hits = check_prosecutor_vetoes(assistant_text, _EXTRA_VETOES)
    if veto_hits:
        errors.append(f"prosecutor_veto:{veto_hits}")

    m = re.match(r"^<reasoning>\n(.+?)\n</reasoning>\n(\{.+\})\s*$", assistant_text, flags=re.DOTALL)
    if not m:
        errors.append("missing_reasoning_or_json_envelope")
        return errors

    try:
        parsed = json.loads(m.group(2))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid_json:{exc}")
        return errors

    docs = example["ground_truth"].get("docs", [])
    docs_by_id = {d["id"]: d for d in docs}
    user_text = msgs[1]["content"]
    for d in docs:
        if d["text"] not in user_text:
            errors.append(f"doc_missing_from_user_prompt:{d['id']}")

    quote_pairs: list[tuple[str, str]] = []
    _collect_quote_pairs(parsed, quote_pairs)
    if not quote_pairs:
        errors.append("zero_quotes_in_output")
    for doc_id, quote in quote_pairs:
        if not quote_ok(quote, doc_id, docs_by_id):
            errors.append(f"quote_failed:{doc_id}:{quote!r}")

    return errors


# ---------------------------------------------------------------------------
# Drill 1: temporal_clock_math
# ---------------------------------------------------------------------------


def _gen_temporal_clock_math(
    rng: random.Random, split: str, index: int, case_id: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    date_str = _sample_incident_date(rng, 2015, 2025)
    subject_name, witness_name, officer_name = sample_unique_names(rng, 3)
    county_a, county_b, corridor = rng.choice(COUNTIES)
    veh_model, veh_color, _ = rng.choice(VEHICLES)
    plate = random_plate(rng)

    # Relative witness phrase anchored to a municipal/maritime schedule
    anchor_kind = rng.choice(("ferry_horn", "midnight_anchor", "bus_departure", "game_end"))
    if anchor_kind == "ferry_horn":
        anchor_min = rng.choice((22 * 60 + 20, 22 * 60 + 35, 22 * 60 + 50))
        offset_min = 25
        witness_true_min = anchor_min + offset_min
        rel_phrase = "twenty-five minutes after the last ferry horn"
        anchor_sentence = (
            f"Harbor Master tariff log confirms the last ferry horn sounded at {fmt_clock(anchor_min)} local time "
            f"before dock lockup at {county_a} Landing."
        )
    elif anchor_kind == "midnight_anchor":
        anchor_min = 24 * 60
        offset_min = -30
        witness_true_min = anchor_min + offset_min
        rel_phrase = "half an hour before midnight"
        anchor_sentence = (
            f"Municipal siren test log confirms the automated midnight chime was silent until 00:00, "
            f"fixing {county_a} station wall clocks to local standard time."
        )
    elif anchor_kind == "bus_departure":
        anchor_min = rng.choice((22 * 60 + 45, 23 * 60 + 10))
        offset_min = 20
        witness_true_min = anchor_min + offset_min
        rel_phrase = "twenty minutes after the last outbound county bus pulled away"
        anchor_sentence = (
            f"Transit Authority dispatch sheet records the last outbound county bus departed Terminal Bay 2 "
            f"at {fmt_clock(anchor_min)} local time."
        )
    else:
        anchor_min = rng.choice((22 * 60 + 12, 22 * 60 + 48))
        offset_min = 35
        witness_true_min = anchor_min + offset_min
        rel_phrase = "thirty-five minutes after the regional broadcast game ended"
        anchor_sentence = (
            f"Affiliate station log confirms the regional broadcast game ended at {fmt_clock(anchor_min)} local time "
            f"prior to the late news."
        )

    # DVR skew: DVR displays raw time ahead by +skew_raw_ahead (e.g. +42 min unadjusted DST + drift)
    # so applied correction to raw DVR timestamp is -skew_raw_ahead (or if behind, +skew).
    skew_ahead = rng.choice((42, 47, 54, -36, -29))
    clock_skew_applied = -skew_ahead  # minutes added to raw DVR display to recover true local time

    # Decide transit feasibility deterministically balanced 50/50
    feasible = ((index // 8) % 2) == 0
    p1 = (0.0, 0.0)
    if feasible:
        # Moderate road distance (~9-15 miles -> ~15-24 min drive), generous gap (28-44 min)
        dx = rng.uniform(5.8, 9.2)
        dy = rng.uniform(3.5, 6.4)
        p2 = (dx, dy)
        req_drive = euclidean_drive_minutes(p1, p2, mph=38.0)
        gap_min = req_drive + rng.randint(9, 22)
    else:
        # Long county transit (~22-34 miles -> ~35-54 min drive), impossible short gap (6-16 min)
        dx = rng.uniform(14.5, 20.5)
        dy = rng.uniform(9.5, 14.0)
        p2 = (dx, dy)
        req_drive = euclidean_drive_minutes(p1, p2, mph=38.0)
        gap_min = max(5, rng.randint(6, min(16, req_drive - 14)))

    miles = road_miles_between(p1, p2)
    dvr_true_min = witness_true_min + rng.choice((4, 6, 8))
    dvr_raw_min = dvr_true_min + skew_ahead

    # Carrier UTC event placed gap_min after DVR true departure in County B
    utc_offset_hours = rng.choice((4, 5, 6, 7))  # local = UTC - utc_offset_hours
    tz_label = {4: "EDT (UTC-4)", 5: "EST (UTC-5)", 6: "CST (UTC-6)", 7: "MST (UTC-7)"}[utc_offset_hours]
    carrier_local_min = dvr_true_min + gap_min
    carrier_utc_min = carrier_local_min + utc_offset_hours * 60

    skew_desc = (
        f"+{skew_ahead} min unadjusted DST + drift verified by officer wristwatch calibration photo"
        if skew_ahead > 0
        else f"{skew_ahead} min CMOS quartz lag verified by officer wristwatch calibration photo"
    )
    calib_wrist = fmt_clock(14 * 60 + 10)
    calib_dvr = fmt_clock(14 * 60 + 10 + skew_ahead)

    q_witness = (
        f"I watched {subject_name} back the {veh_color} {veh_model} out of the {county_a} yard "
        f"{rel_phrase}"
    )
    q_anchor = anchor_sentence
    q_dvr = (
        f" Alleyway DVR ch-03 stamps plate {plate} clearing the {county_a} gate at {fmt_clock(dvr_raw_min)} DVR time; "
        f"system exhibits {skew_desc} (DVR showed {calib_dvr} when Dept. atomic wristwatch read {calib_wrist})."
    ).strip()
    q_carrier = (
        f"Carrier switch record logs {subject_name} handset originating a PIN-verified retail fuel pump session "
        f"at {county_b} Milepost Plaza at {_iso_dt(date_str, carrier_utc_min)}Z (local zone {tz_label})."
    )
    q_roads = (
        f"County Highway Engineering mileage table sets {county_a} gate to {county_b} Milepost Plaza via {corridor} "
        f"at {miles:.1f} road miles (minimum {req_drive} minutes uninterrupted transit at 38 mph)."
    )

    doc_count = rng.choice((3, 4, 5))
    if doc_count == 3:
        docs: list[dict[str, Any]] = [
            {
                "id": "doc01",
                "title": f"Witness Statement & Schedule Note — {witness_name}",
                "type": "statement",
                "date": date_str,
                "author": f"Det. {officer_name}",
                "text": (
                    f"Interview taken at {county_a} Substation. {witness_name} stated: \"{q_witness}.\" "
                    f"Witness did not check a wristwatch and estimated +/- 3 minutes around that mark. {q_anchor}"
                ),
            },
            {
                "id": "doc02",
                "title": "DVR Extraction & Calibration Memo",
                "type": "digital_log",
                "date": date_str,
                "author": f"CSI Tech {officer_name.split()[-1]}",
                "text": f"Property receipt #DVR-88B. {q_dvr} No frames were dropped during export.",
            },
            {
                "id": "doc03",
                "title": "Subpoenaed Carrier UTC & Corridor Mileage Return",
                "type": "carrier_record",
                "date": date_str,
                "author": "Records Custodian",
                "text": f"{q_carrier} {q_roads}",
            },
        ]
        anchor_doc_id = "doc01"
        roads_doc_id = "doc03"
    else:
        docs = [
            {
                "id": "doc01",
                "title": f"Witness Statement — {witness_name}",
                "type": "statement",
                "date": date_str,
                "author": f"Det. {officer_name}",
                "text": (
                    f"Interview taken at {county_a} Substation. {witness_name} stated: \"{q_witness}.\" "
                    f"Witness did not check a wristwatch and estimated +/- 3 minutes around that mark."
                ),
            },
            {
                "id": "doc02",
                "title": "DVR Extraction & Calibration Memo",
                "type": "digital_log",
                "date": date_str,
                "author": f"CSI Tech {officer_name.split()[-1]}",
                "text": f"Property receipt #DVR-88B. {q_dvr} No frames were dropped during export.",
            },
            {
                "id": "doc03",
                "title": "Subpoenaed Carrier & POS Telemetry",
                "type": "carrier_record",
                "date": date_str,
                "author": "Records Custodian",
                "text": f"{q_carrier} Handset IMEI matched subscriber billing profile on file.",
            },
        ]
        if doc_count == 5:
            docs.append(
                {
                    "id": "doc04",
                    "title": "Municipal Schedule Verification",
                    "type": "almanac_record",
                    "date": date_str,
                    "author": "County Clerk Archive",
                    "text": q_anchor,
                }
            )
            docs.append(
                {
                    "id": "doc05",
                    "title": f"{corridor} Transit Mileage Worksheet",
                    "type": "analyst_worksheet",
                    "date": date_str,
                    "author": "Traffic Reconstruction Unit",
                    "text": q_roads,
                }
            )
            anchor_doc_id = "doc04"
            roads_doc_id = "doc05"
        else:
            docs.append(
                {
                    "id": "doc04",
                    "title": "Schedule & Corridor Mileage Verification",
                    "type": "almanac_record",
                    "date": date_str,
                    "author": "Crime Analysis Desk",
                    "text": f"{q_anchor} {q_roads}",
                }
            )
            anchor_doc_id = "doc04"
            roads_doc_id = "doc04"

    collision_detected = not feasible
    iso_windows = [
        {
            "event": f"Witness estimate: {veh_color} {veh_model} backs out of {county_a} yard",
            "doc_id": "doc01",
            "iso_start": _iso_dt(date_str, witness_true_min - 3),
            "iso_end": _iso_dt(date_str, witness_true_min + 3),
        },
        {
            "event": f"Calibrated DVR gate exit for plate {plate} in {county_a}",
            "doc_id": "doc02",
            "iso_start": _iso_dt(date_str, dvr_true_min),
            "iso_end": _iso_dt(date_str, dvr_true_min),
        },
        {
            "event": f"Carrier/POS handset session at {county_b} Milepost Plaza",
            "doc_id": "doc03",
            "iso_start": _iso_dt(date_str, carrier_local_min),
            "iso_end": _iso_dt(date_str, carrier_local_min),
        },
    ]

    innocent_alt = (
        "No spatial-temporal collision exists once DVR clock skew and UTC offset are normalized."
        if feasible
        else (
            "A second driver may have operated the vehicle at the gate while the subscriber handset traveled "
            "separately, or the calibration wristwatch photograph was logged on a different DVR channel."
        )
    )

    payload = {
        "iso_windows": iso_windows,
        "clock_skew_applied_minutes": clock_skew_applied,
        "road_transit_check": {
            "road_miles": miles,
            "required_drive_minutes": req_drive,
            "available_gap_minutes": gap_min,
        },
        "transit_feasible": feasible,
        "collision_detected": collision_detected,
        "innocent_alternative": innocent_alt,
        "verbatim_quotes": [
            {"doc_id": "doc01", "quote": q_witness},
            {"doc_id": anchor_doc_id, "quote": q_anchor},
            {"doc_id": "doc02", "quote": q_dvr},
            {"doc_id": "doc03", "quote": q_carrier},
            {"doc_id": roads_doc_id, "quote": q_roads},
        ],
    }

    reasoning = [
        f"1. Anchor schedule ({anchor_doc_id}): reference mark is {fmt_clock(anchor_min)} local. Applying '{rel_phrase}' ({offset_min:+d} min) yields {fmt_clock(witness_true_min)} (+/-3 min -> {_iso_dt(date_str, witness_true_min - 3)} to {_iso_dt(date_str, witness_true_min + 3)}).",
        f"2. DVR calibration (doc02): raw DVR reads {fmt_clock(dvr_raw_min)}, calibration shows {calib_dvr} vs atomic wristwatch {calib_wrist} ({skew_ahead:+d} min raw offset), so clock_skew_applied_minutes = {clock_skew_applied:+d} min -> true gate exit {_iso_dt(date_str, dvr_true_min)}.",
        f"3. Carrier UTC conversion (doc03): {_iso_dt(date_str, carrier_utc_min)}Z minus {utc_offset_hours}h ({tz_label}) = {_iso_dt(date_str, carrier_local_min)} local.",
        f"4. Transit math ({roads_doc_id}): {miles:.1f} road miles requires {req_drive} min at 38 mph; available gap between {_iso_dt(date_str, dvr_true_min)} and {_iso_dt(date_str, carrier_local_min)} is {gap_min} min -> transit_feasible={feasible}, collision_detected={collision_detected}.",
    ]

    schema_hint = (
        '{"iso_windows": [{"event": "", "doc_id": "", "iso_start": "", "iso_end": ""}], '
        '"clock_skew_applied_minutes": 0, '
        '"road_transit_check": {"road_miles": 0.0, "required_drive_minutes": 0, "available_gap_minutes": 0}, '
        '"transit_feasible": true, "collision_detected": false, "innocent_alternative": "", '
        '"verbatim_quotes": [{"doc_id": "", "quote": ""}]}'
    )
    sys_prompt = _build_system_prompt(
        "The Analyst & Digital: Temporal Clock-Skew & Transit Math",
        "Normalize relative witness time expressions, DVR clock skew, and carrier UTC timestamps to local ISO-8601 windows. "
        "Set `clock_skew_applied_minutes` to the signed integer added to raw DVR time to obtain true local time, "
        "and evaluate road-distance transit feasibility and spatial-temporal collisions.",
        schema_hint,
    )
    usr_prompt = _build_user_prompt(
        case_id,
        f"Evaluate whether the {veh_color} {veh_model} (plate {plate}) and {subject_name}'s handset timeline across {county_a} and {county_b} is physically feasible.",
        docs,
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
        {"role": "assistant", "content": _format_assistant_turn(reasoning, payload)},
    ]
    ground_truth = {
        "subtask": "temporal_clock_math",
        "docs": docs,
        "clock_skew_applied_minutes": clock_skew_applied,
        "transit_feasible": feasible,
        "collision_detected": collision_detected,
        "expected_json": payload,
    }
    return messages, ground_truth


# ---------------------------------------------------------------------------
# Drill 2: forensic_nli
# ---------------------------------------------------------------------------


def _gen_forensic_nli(
    rng: random.Random, split: str, index: int, case_id: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    # Balanced ~34% SUPPORTED, ~33% REFUTED, ~33% NOT_ENOUGH_INFORMATION
    label_idx = (index // 8) % 3
    target_label = ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFORMATION")[label_idx]

    date_str = _sample_incident_date(rng, 2016, 2025)
    p_main, p_other, p_clerk = sample_unique_names(rng, 3)
    addr = random_address(rng)
    pin_code = str(rng.randint(2104, 8979))
    transponder = f"EZP-{rng.randint(40110, 98990)}"
    phone_a = _sample_phone(rng, 607)
    phone_b = _sample_phone(rng, 607)
    variant = rng.randint(0, 1)

    if target_label == "SUPPORTED":
        if variant == 0:
            claim = (
                f"Electronic toll and DMV fleet records place a vehicle registered to {p_main} "
                f"crossing the southbound Riverbend Plaza at 23:14 on {date_str}."
            )
            q1 = f"Lane 04 RFID reader logged transponder {transponder} southbound at Riverbend Plaza at 23:14:09 on {date_str}"
            q2 = f"Active transponder {transponder} is registered to {p_main} at {addr}"
            q3 = f"Maintenance supervisor {p_other} reported locking the east tool crib at 21:40 before heading home"
            docs = [
                {"id": "doc01", "title": "Turnpike Authority RFID Log", "type": "toll_record", "date": date_str, "author": "Toll Systems", "text": f"Automated gantry export: {q1}; axle count 2, account status paid."},
                {"id": "doc02", "title": "DMV & Transponder Subscriber Extract", "type": "records_extract", "date": date_str, "author": f"Clerk {p_clerk}", "text": f"Subscriber lookup verified: {q2}, linked to two-axle pickup."},
                {"id": "doc03", "title": "Facility Shift Note", "type": "shift_log", "date": date_str, "author": p_other, "text": f"Routine closing entry: {q3}."},
            ]
            chained = ["doc01", "doc02"]
            missing_link = None
            innocent_alt = None
            quotes = [{"doc_id": "doc01", "quote": q1, "role": "premise_event"}, {"doc_id": "doc02", "quote": q2, "role": "identity_bridge"}]
        else:
            claim = (
                f"Building power telemetry and electrical panel schedules establish that the Suite 204 office "
                f"lighting-and-workstation circuit remained active until 00:22."
            )
            q1 = "Sub-meter Breaker #14 drew a continuous 480-watt load from 21:00 until dropping to 18-watt standby at 00:22"
            q2 = "Panel schedule maps Breaker #14 exclusively to Suite 204 overhead lighting and desktop workstation outlets"
            q3 = f"Courier {p_other} dropped two manifest envelopes in the lobby vestibule bin at 19:50"
            docs = [
                {"id": "doc01", "title": "Utility Smart-Meter Interval Export", "type": "utility_log", "date": date_str, "author": "Grid Metering", "text": f"1-minute interval log for {addr}: {q1}."},
                {"id": "doc02", "title": "As-Built Electrical Panel Schedule", "type": "building_record", "date": date_str, "author": "Chief Engineer", "text": f"Verified circuit map: {q2}."},
                {"id": "doc03", "title": "Lobby Courier Receipt", "type": "receipt", "date": date_str, "author": p_other, "text": f"Evening drop ticket: {q3}."},
            ]
            chained = ["doc01", "doc02"]
            missing_link = None
            innocent_alt = None
            quotes = [{"doc_id": "doc01", "quote": q1, "role": "load_measurement"}, {"doc_id": "doc02", "quote": q2, "role": "circuit_mapping"}]

    elif target_label == "REFUTED":
        if variant == 0:
            claim = f"{p_main}'s statement that {p_main}'s assigned keycard was never badged at the cold-storage annex after 21:00 on {date_str} aligns with facility records."
            q1 = f"I left the plant at 20:45 on {date_str} and my keycard never touched a reader at the cold-storage annex after nine"
            q2 = f"Door Controller #7 logged credential badge HID-{pin_code} unlocking the cold-storage annex vestibule at 23:38:14 on {date_str}"
            q3 = f"Security roster confirms credential badge HID-{pin_code} was issued solely to {p_main} with zero reported loss tickets"
            docs = [
                {"id": "doc01", "title": f"Voluntary Interview — {p_main}", "type": "statement", "date": date_str, "author": f"Det. {p_clerk}", "text": f"Recorded interview summary: {p_main} stated, \"{q1}.\""},
                {"id": "doc02", "title": "Access Control Raw Audit Log", "type": "digital_log", "date": date_str, "author": "Physical Security", "text": f"Controller export (NTP synced): {q2}."},
                {"id": "doc03", "title": "HR Credential Issuance Ledger", "type": "roster", "date": date_str, "author": "HR Custody", "text": f"Active badge table: {q3}."},
            ]
            chained = ["doc01", "doc02", "doc03"]
            missing_link = None
            innocent_alt = (
                f"{p_main} may have confused the date of an earlier shift, or lent jacket/lanyard carrying badge HID-{pin_code} "
                "to a coworker without filing a loss ticket."
            )
            quotes = [
                {"doc_id": "doc01", "quote": q1, "role": "refuted_claim"},
                {"doc_id": "doc02", "quote": q2, "role": "machine_contradiction"},
                {"doc_id": "doc03", "quote": q3, "role": "credential_assignment"},
            ]
        else:
            claim = f"The file supports {p_main}'s account that {p_main}'s pickup remained parked at {addr} without crossing the county toll bridge between 22:30 and midnight."
            q1 = f"My truck sat in my driveway at {addr} from 22:15 straight through morning and never crossed the bridge"
            q2 = f"Eastbound toll ALPR and RFID reader captured plate and tag {transponder} crossing at 23:06 and returning westbound at 23:29"
            q3 = f"State registration binds tag {transponder} to {p_main}'s pickup garaged at {addr}"
            docs = [
                {"id": "doc01", "title": f"Canvass Statement — {p_main}", "type": "statement", "date": date_str, "author": f"Det. {p_clerk}", "text": f"Doorstep canvass: {p_main} stated, \"{q1}.\""},
                {"id": "doc02", "title": "Bridge Commission ALPR & Toll Log", "type": "toll_record", "date": date_str, "author": "Bridge Ops", "text": f" High-confidence optical + RFID read: {q2}."},
                {"id": "doc03", "title": "Vehicle & Tag Registration Return", "type": "records_extract", "date": date_str, "author": "Records Desk", "text": f"Certified return: {q3}."},
            ]
            chained = ["doc01", "doc02", "doc03"]
            missing_link = None
            innocent_alt = (
                f"A household member or borrower may have driven {p_main}'s pickup across the bridge without {p_main}'s awareness, "
                f"or {p_main} misremembered which night the errand occurred."
            )
            quotes = [
                {"doc_id": "doc01", "quote": q1, "role": "refuted_claim"},
                {"doc_id": "doc02", "quote": q2, "role": "machine_contradiction"},
                {"doc_id": "doc03", "quote": q3, "role": "vehicle_link"},
            ]

    else:  # NOT_ENOUGH_INFORMATION
        if variant == 0:
            claim = f"The keypad and roster records prove that {p_main} personally entered the rear cash office at 23:51 on {date_str}."
            q1 = f"Keypad audit log shows numeric PIN {pin_code} unlatched the rear cash office door at 23:51:04 on {date_str}; no camera covers the hallway"
            q2 = f"Shift binder lists numeric PIN {pin_code} beside {p_main}'s name on the laminated wall sheet hung beside the breakroom phone"
            q3 = f"Delivery driver {p_other} signed out at the loading dock gate at 22:10"
            docs = [
                {"id": "doc01", "title": "Rear Door Keypad Audit Dump", "type": "digital_log", "date": date_str, "author": "CSI Digital", "text": f"Standalone lock memory: {q1}."},
                {"id": "doc02", "title": "Breakroom PIN Roster Sheet", "type": "roster", "date": date_str, "author": "Store Operations", "text": f"Photographed sheet: {q2}."},
                {"id": "doc03", "title": "Dock Visitor Sign-Out Log", "type": "shift_log", "date": date_str, "author": p_other, "text": f"Gate clipboard: {q3}."},
            ]
            chained = ["doc01", "doc02"]
            missing_link = (
                f"A numeric keypad log proves PIN {pin_code} was typed to unlatch the door, not who physically pressed the keys—"
                "especially where the PIN was posted on a visible breakroom wall sheet with no hallway video."
            )
            innocent_alt = (
                f"Any staff member with breakroom access could have read PIN {pin_code} off the laminated wall sheet and keyed the door."
            )
            quotes = [
                {"doc_id": "doc01", "quote": q1, "role": "machine_scope_limit"},
                {"doc_id": "doc02", "quote": q2, "role": "shared_exposure"},
            ]
        else:
            claim = f"Subpoenaed phone records establish that {p_main} spoke personally with {p_other} and arranged a meeting during the 23:19 call."
            q1 = f"Carrier CDR logs a 96-second connected voice circuit from handset {phone_a} to handset {phone_b} at 23:19:12 on {date_str} with no audio content retained"
            q2 = f"Subscriber return lists {phone_a} billed to {p_main} and {phone_b} billed to {p_other}"
            q3 = f"Night clerk {p_clerk} noted heavy rain outside the terminal window at 23:00"
            docs = [
                {"id": "doc01", "title": "Carrier Call Detail Record (CDR)", "type": "carrier_record", "date": date_str, "author": "Subpoena Compliance", "text": f"Switch toll record: {q1}."},
                {"id": "doc02", "title": "Subscriber Billing Verification", "type": "records_extract", "date": date_str, "author": "Records Unit", "text": f"Account match: {q2}."},
                {"id": "doc03", "title": "Terminal Weather Note", "type": "statement", "date": date_str, "author": p_clerk, "text": f"Witness observation: {q3}."},
            ]
            chained = ["doc01", "doc02"]
            missing_link = (
                "A Call Detail Record (CDR) proves a 96-second circuit connection between two billed handsets, "
                "not who held either phone, whether voicemail answered, or what words were spoken."
            )
            innocent_alt = (
                "The call may have rolled to long voicemail greeting, pocket-dialed, or involved another household user without arranging any meeting."
            )
            quotes = [
                {"doc_id": "doc01", "quote": q1, "role": "cdr_limitation"},
                {"doc_id": "doc02", "quote": q2, "role": "subscriber_link"},
            ]

    payload = {
        "hypothesis_claim": claim,
        "label": target_label,
        "chained_doc_ids": chained,
        "missing_link": missing_link,
        "innocent_alternative": innocent_alt,
        "verbatim_quotes": quotes,
    }

    reasoning = [
        f"1. Evaluate claim: '{claim}' strictly against doc01, doc02, and doc03.",
        f"2. Multi-hop chain check across {chained}: compare what each machine/witness exhibit literally proves versus what requires an unproven leap.",
        f"3. Resulting forensic NLI verdict is {target_label}"
        + (f" due to missing link: {missing_link}" if missing_link else "")
        + (f"; mandatory innocent_alternative recorded." if innocent_alt else "."),
    ]

    schema_hint = (
        '{"hypothesis_claim": "", "label": "SUPPORTED|REFUTED|NOT_ENOUGH_INFORMATION", '
        '"chained_doc_ids": [""], "missing_link": null, "innocent_alternative": null, '
        '"verbatim_quotes": [{"doc_id": "", "quote": "", "role": ""}]}'
    )
    sys_prompt = _build_system_prompt(
        "Cross-Examiner & Prosecutor: Multi-Hop Forensic NLI",
        "Classify `HYPOTHESIS_CLAIM` strictly as `SUPPORTED`, `REFUTED`, or `NOT_ENOUGH_INFORMATION` using the 3 exhibits. "
        "Chain documents when required, never upgrade device/PIN/CDR presence into personal action without proof, "
        "and always provide `innocent_alternative` when `REFUTED`.",
        schema_hint,
    )
    usr_prompt = _build_user_prompt(
        case_id,
        "Determine the strict forensic NLI entailment status of the investigative claim below.",
        docs,
        extra_directive=f"### HYPOTHESIS_CLAIM\n{claim}",
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
        {"role": "assistant", "content": _format_assistant_turn(reasoning, payload)},
    ]
    ground_truth = {
        "subtask": "forensic_nli",
        "docs": docs,
        "label": target_label,
        "chained_doc_ids": chained,
        "expected_json": payload,
    }
    return messages, ground_truth


# ---------------------------------------------------------------------------
# Drill 3: entity_resolution_graph
# ---------------------------------------------------------------------------


def _gen_entity_resolution_graph(
    rng: random.Random, split: str, index: int, case_id: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    date_str = _sample_incident_date(rng, 2008, 2024)
    # Pick a first name with canonical ALIAS_NICKNAMES
    canon_first_raw = rng.choice(tuple(ALIAS_NICKNAMES.keys()))
    nick = rng.choice(ALIAS_NICKNAMES[canon_first_raw])
    canon_first = canon_first_raw.capitalize()
    last_a, maiden_last, married_last = pick_distinct(rng, LAST_NAMES, 3)
    woman_first = rng.choice(("Elena", "Valerie", "Nadia", "Miriam", "Camille", "Sabrina", "Lydia"))

    person_1 = f"{canon_first} {last_a}"
    person_1_nick = f"{nick} {last_a}"
    person_2_married = f"{woman_first} {married_last}"
    person_2_maiden = f"{woman_first} {maiden_last}"

    veh_model, veh_color, _ = rng.choice(VEHICLES)
    full_plate = random_plate(rng)
    partial_plate = full_plate[:3] + "-**" + full_plate[-2:]
    po_box = f"P.O. Box {rng.randint(118, 945)}"
    burner = _sample_phone(rng, 315)
    llc_name = f"{rng.choice(SHELL_PREFIXES)} {rng.choice(SHELL_SUFFIXES)}"

    q1 = f"Desk clerk identified frequent caller '{person_1_nick}' (true name on photocopy ID: {person_1}) leaving callback burner {burner}"
    q2 = f"Night watch spotted a {veh_color} {veh_model} bearing partial tag {partial_plate} idling behind Dock 3 between 22:40 and 23:05"
    q3 = (
        f"Municipal tow ticket #T-409 matches {veh_color} {veh_model} full plate {full_plate} to {llc_name} "
        f"receiving mail at {po_box}"
    )
    q4 = (
        f"Postal Box Form 1093 lists {po_box} co-renters as {person_1} and {person_2_married} "
        f"(maiden name {person_2_maiden}) alongside prepaid handset {burner}"
    )

    docs = [
        {
            "id": "doc01",
            "title": "Motel Registration & Desk Note",
            "type": "field_note",
            "date": date_str,
            "author": "Cold Case Intake",
            "text": f"Supplemental slip #14: {q1} on {date_str}.",
        },
        {
            "id": "doc02",
            "title": "Dock Watch Vehicle Sighting",
            "type": "statement",
            "date": date_str,
            "author": "Harbor Patrol",
            "text": f"Canvass entry: {q2} on {date_str}.",
        },
        {
            "id": "doc03",
            "title": "Impound & Registration Cross-Index",
            "type": "records_extract",
            "date": date_str,
            "author": "Records Desk",
            "text": f"Impound audit: {q3}.",
        },
        {
            "id": "doc04",
            "title": "USPS Box Application & Emergency Contact",
            "type": "postal_record",
            "date": date_str,
            "author": "Postal Inspector Return",
            "text": f"Subpoena return: {q4}.",
        },
    ]

    canonical_entities = [
        {
            "entity_id": "ENT_P1",
            "canonical_name": person_1,
            "entity_type": "PERSON",
            "surface_mentions": [person_1, person_1_nick],
            "supporting_docs": ["doc01", "doc04"],
        },
        {
            "entity_id": "ENT_P2",
            "canonical_name": person_2_married,
            "entity_type": "PERSON",
            "surface_mentions": [person_2_married, person_2_maiden],
            "supporting_docs": ["doc04"],
        },
        {
            "entity_id": "ENT_VEH1",
            "canonical_name": f"{veh_color} {veh_model} ({full_plate})",
            "entity_type": "VEHICLE",
            "surface_mentions": [partial_plate, full_plate, f"{veh_color} {veh_model}"],
            "supporting_docs": ["doc02", "doc03"],
        },
        {
            "entity_id": "ENT_PHONE1",
            "canonical_name": burner,
            "entity_type": "PHONE",
            "surface_mentions": [burner],
            "supporting_docs": ["doc01", "doc04"],
        },
        {
            "entity_id": "ENT_BOX1",
            "canonical_name": po_box,
            "entity_type": "PO_BOX",
            "surface_mentions": [po_box],
            "supporting_docs": ["doc03", "doc04"],
        },
        {
            "entity_id": "ENT_ORG1",
            "canonical_name": llc_name,
            "entity_type": "ORG",
            "surface_mentions": [llc_name],
            "supporting_docs": ["doc03"],
        },
    ]

    triples = [
        {
            "head": person_1,
            "relation": "USES_BURNER_PHONE",
            "tail": burner,
            "time_window": f"{date_str}",
            "doc_id": "doc01",
            "quote": q1,
        },
        {
            "head": f"{veh_color} {veh_model} ({full_plate})",
            "relation": "OBSERVED_AT",
            "tail": "Dock 3",
            "time_window": f"{date_str}T22:40/23:05",
            "doc_id": "doc02",
            "quote": q2,
        },
        {
            "head": f"{veh_color} {veh_model} ({full_plate})",
            "relation": "REGISTERED_TO_ORG_AT_PO_BOX",
            "tail": f"{llc_name} / {po_box}",
            "time_window": f"{date_str}",
            "doc_id": "doc03",
            "quote": q3,
        },
        {
            "head": person_1,
            "relation": "SHARES_PO_BOX_WITH",
            "tail": person_2_married,
            "time_window": f"{date_str}",
            "doc_id": "doc04",
            "quote": q4,
        },
    ]

    payload = {
        "canonical_entities": canonical_entities,
        "triples": triples,
    }

    reasoning = [
        f"1. Nickname resolution (doc01): '{person_1_nick}' is explicitly tied via photocopy ID to canonical person '{person_1}' and burner '{burner}'.",
        f"2. Vehicle & partial plate resolution (doc02 + doc03): '{veh_color} {veh_model}' with partial tag '{partial_plate}' matches full plate '{full_plate}' registered to '{llc_name}' at '{po_box}'.",
        f"3. Maiden name & shared box resolution (doc04): '{po_box}' links co-renters '{person_1}' and '{person_2_married}' (née '{person_2_maiden}') and confirms burner '{burner}'.",
    ]

    schema_hint = (
        '{"canonical_entities": [{"entity_id": "", "canonical_name": "", "entity_type": "", '
        '"surface_mentions": [""], "supporting_docs": [""]}], '
        '"triples": [{"head": "", "relation": "", "tail": "", "time_window": "", "doc_id": "", "quote": ""}]}'
    )
    sys_prompt = _build_system_prompt(
        "The Analyst & Records: Cold-Case Entity Resolution & GraphRAG Extraction",
        "Resolve aliases, nicknames, maiden names, partial license plates, shared P.O. boxes, and burner numbers "
        "into canonical entities only where documentary proof connects them, and emit typed GraphRAG JSON triples with verbatim quotes.",
        schema_hint,
    )
    usr_prompt = _build_user_prompt(
        case_id,
        "Resolve canonical entities and build the quote-verified GraphRAG triple list across these 4 cold-case exhibits.",
        docs,
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
        {"role": "assistant", "content": _format_assistant_turn(reasoning, payload)},
    ]
    ground_truth = {
        "subtask": "entity_resolution_graph",
        "docs": docs,
        "canonical_entity_count": len(canonical_entities),
        "triple_count": len(triples),
        "expected_json": payload,
    }
    return messages, ground_truth


# ---------------------------------------------------------------------------
# Drill 4: name_collision_guard
# ---------------------------------------------------------------------------


def _gen_name_collision_guard(
    rng: random.Random, split: str, index: int, case_id: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    date_str = _sample_incident_date(rng, 2014, 2025)
    surname_pair = rng.choice(
        (
            ("Johnston", "Jonson"),
            ("Sorensen", "Sorenson"),
            ("McAllister", "MacAllister"),
            ("Hendricks", "Hendrix"),
            ("Kowalski", "Kowalsky"),
            ("Whitaker", "Whittaker"),
        )
    )
    first_pair = rng.choice(
        (
            ("Michael", "Mike"),
            ("Raymond", "Ray"),
            ("Kenneth", "Kenny"),
            ("Gregory", "Greg"),
            ("Tomas", "Tommy"),
            ("Derrick", "Rick"),
        )
    )
    use_exact_spelling = rng.choice((True, False))
    last_a = surname_pair[0]
    last_b = surname_pair[0] if use_exact_spelling else surname_pair[1]
    name_a = f"{first_pair[0]} {last_a}"
    name_b_display = f"{first_pair[1]} {last_b} / {first_pair[0]} {last_a}"

    dob_a = f"{rng.randint(1981, 1994)}-{rng.randint(1, 12):02d}-{rng.randint(10, 27):02d}"
    dob_b = f"{rng.randint(1955, 1968)}-{rng.randint(1, 12):02d}-{rng.randint(10, 27):02d}"
    addr_a = f"{rng.randint(12, 89)} {rng.choice(STREET_ROOTS)} St"
    addr_b = f"{rng.randint(110, 940)} {rng.choice(STREET_ROOTS)} Rd"
    dl_a = f"DL-{rng.randint(7100, 7999)}-A"
    dl_b = f"DL-{rng.randint(2100, 2999)}-B"

    q_emp = (
        f"Payroll W-4 card lists former prep cook {name_a}, DOB {dob_a}, residing at {addr_a}, "
        f"driver license {dl_a}, separated from employment three weeks prior to {date_str}"
    )
    q_court = (
        f"Prior county docket #CR-09-441 indexes {name_b_display}, DOB {dob_b}, residing at {addr_b}, "
        f"driver license {dl_b}, for commercial warehouse pry-bar entry"
    )
    q_tip = (
        f"Caller suggested the former prep cook on the payroll roster was the same '{first_pair[1]} {last_b}' "
        f"with the warehouse pry-bar docket in county court"
    )

    docs = [
        {
            "id": "doc01",
            "title": "Employer Payroll & W-4 Extract",
            "type": "roster",
            "date": date_str,
            "author": "Bookkeeper",
            "text": f"Personnel folder #19: {q_emp}.",
        },
        {
            "id": "doc02",
            "title": "County Clerk Criminal Index Return",
            "type": "court_record",
            "date": date_str,
            "author": "Records Chair",
            "text": f"Public index query return: {q_court}.",
        },
        {
            "id": "doc03",
            "title": "Tip Line Intake Sheet #08",
            "type": "tip_sheet",
            "date": date_str,
            "author": "Desk Officer",
            "text": f"Unverified phone tip received 11:20: {q_tip}.",
        },
    ]

    payload = {
        "decision": "DO_NOT_MERGE_COLLISION",
        "person_a": {
            "canonical_label": f"{name_a} (DOB {dob_a})",
            "dob": dob_a,
            "address": addr_a,
            "license_id": dl_a,
            "doc_id": "doc01",
            "quote": q_emp,
        },
        "person_b": {
            "canonical_label": f"{name_b_display} (DOB {dob_b})",
            "dob": dob_b,
            "address": addr_b,
            "license_id": dl_b,
            "doc_id": "doc02",
            "quote": q_court,
        },
        "false_lead_prevented": (
            f"Refusing to attach docket #CR-09-441 (DOB {dob_b}, {addr_b}) onto former prep cook {name_a} "
            f"(DOB {dob_a}, {addr_a}), which tip sheet doc03 conflated solely by shared name."
        ),
        "verbatim_quotes": [
            {"doc_id": "doc01", "quote": q_emp},
            {"doc_id": "doc02", "quote": q_court},
            {"doc_id": "doc03", "quote": q_tip},
        ],
    }

    reasoning = [
        f"1. Compare primary identifiers: doc01 records '{name_a}' with DOB {dob_a}, address {addr_a}, and {dl_a}.",
        f"2. Compare court index: doc02 records '{name_b_display}' with DOB {dob_b}, address {addr_b}, and {dl_b}.",
        "3. Per Murder Board Records chair collision law, two people sharing a name with discordant DOBs, addresses, and license numbers are distinct humans; flag DO_NOT_MERGE_COLLISION so doc03's conflated tip does not poison the file.",
    ]

    schema_hint = (
        '{"decision": "DO_NOT_MERGE_COLLISION", '
        '"person_a": {"canonical_label": "", "dob": "", "address": "", "license_id": "", "doc_id": "", "quote": ""}, '
        '"person_b": {"canonical_label": "", "dob": "", "address": "", "license_id": "", "doc_id": "", "quote": ""}, '
        '"false_lead_prevented": "", "verbatim_quotes": [{"doc_id": "", "quote": ""}]}'
    )
    sys_prompt = _build_system_prompt(
        "Records: Identity Collision Guard",
        "Audit candidate records sharing identical or near-identical names. Two people with one name is normal; "
        "merging them when DOB, address, or state identifiers conflict is forbidden. Emit `DO_NOT_MERGE_COLLISION` with exact distinguishing quotes.",
        schema_hint,
    )
    usr_prompt = _build_user_prompt(
        case_id,
        "Audit whether the county criminal docket and tip sheet can be merged onto the former employee on the payroll roster.",
        docs,
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
        {"role": "assistant", "content": _format_assistant_turn(reasoning, payload)},
    ]
    ground_truth = {
        "subtask": "name_collision_guard",
        "docs": docs,
        "decision": "DO_NOT_MERGE_COLLISION",
        "dob_a": dob_a,
        "dob_b": dob_b,
        "expected_json": payload,
    }
    return messages, ground_truth


# ---------------------------------------------------------------------------
# Drill 5: pathology_and_trace
# ---------------------------------------------------------------------------


_TRACE_SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "cause": "ligature strangulation with hyoid fracture",
        "manner": "homicide",
        "test": "M-VAC touch DNA",
        "preserved_item": "braided nylon clothesline ligature stored dry in breathable kraft bag #E-04 at 65F since 1991",
        "legacy_result": "1991 ABO grouping on nylon ligature #E-04 yielded inconclusive non-secretor trace; cotton tip swabbing failed to lift recessed epithelial cells from deep rope weave",
        "red_herring_item": "public diner countertop glass ashtray #E-11 collected at 14:20 after twelve daytime breakfast patrons handled it",
    },
    {
        "cause": "multiple sharp-force thoracic injuries",
        "manner": "homicide",
        "test": "STRmix probabilistic deconvolution",
        "preserved_item": "cotton work-shirt cuff cutting #E-02 air-dried and archived in sealed manila envelope since 1997",
        "legacy_result": "1997 RFLP and early polymarker screen on cuff cutting #E-02 showed an unresolved three-person mixed profile and was marked inconclusive without consumption",
        "red_herring_item": "soaked vinyl floor mat #E-09 sealed wet inside non-breathable plastic bag where heavy black mold degraded biological material",
    },
    {
        "cause": "blunt-force cranial trauma",
        "manner": "homicide",
        "test": "IGG SNP genealogy",
        "preserved_item": "single-source exogenous blood-crust flake #E-06 preserved on dry glass slide in property vault since 1988",
        "legacy_result": "1988 serology typed #E-06 as Type O and a 2006 13-locus STR upload produced a clean single-source unknown male profile with zero CODIS offender or forensic hits",
        "red_herring_item": "unsealed lobby push-plate wipe #E-14 swabbed forty-eight hours after scene release following public business hours",
    },
    {
        "cause": "penetrating gunshot wound of the torso",
        "manner": "homicide",
        "test": "3D NIBIN",
        "preserved_item": "two ejected 9mm Luger brass cartridge casings #E-03 stored dry in coin envelopes since 1994",
        "legacy_result": "1994 2D light-microscope bench notes recorded distinct breech-face shear and firing-pin drag on #E-03 before regional optical 3D ballistic correlation networks existed",
        "red_herring_item": "crushed aluminum soda can #E-12 recovered from curb storm grate outside perimeter tape three days post-incident",
    },
)


def _gen_pathology_and_trace(
    rng: random.Random, split: str, index: int, case_id: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    scen = _TRACE_SCENARIOS[(index // 8) % len(_TRACE_SCENARIOS)]
    era_year = rng.randint(1988, 2001)
    date_str = f"{era_year}-{rng.randint(2, 11):02d}-{rng.randint(4, 24):02d}"
    me_name, csi_name = sample_unique_names(rng, 2)

    start_min = rng.choice((21 * 60 + 30, 22 * 60, 22 * 60 + 30))
    end_min = start_min + 150
    liver_temp = round(rng.uniform(86.4, 89.8), 1)
    ambient_temp = rng.randint(60, 66)

    q_livor = (
        "Fixed, non-blanching purple livor mortis is distributed across the posterior shoulders, back, and buttocks, "
        "whereas the decedent was discovered lying face-down (prone) on the storage room concrete at 06:40"
    )
    q_window = (
        f"Full rigor mortis in jaw and upper extremities with core hepatic temperature {liver_temp}F in a {ambient_temp}F room "
        f"places the physiological time-of-death window between {fmt_clock_12h(start_min)} and {fmt_clock_12h(end_min)}"
    )
    q_cause = f"Autopsy conclusion sets cause of death as {scen['cause']} and manner of death as {scen['manner']}"
    q_preserved = f"Vault audit confirms {scen['preserved_item']} remains intact with unbroken custody seals"
    q_legacy = scen["legacy_result"]
    q_herring = f"Scene log also lists {scen['red_herring_item']}"

    docs = [
        {
            "id": "doc01",
            "title": "Office of the Medical Examiner Autopsy Protocol",
            "type": "autopsy",
            "date": date_str,
            "author": f"Dr. {me_name}, Deputy ME",
            "text": f"External & internal examination: {q_livor}. {q_window}. {q_cause}.",
        },
        {
            "id": "doc02",
            "title": "Cold-Case Evidence Vault & Serology Review",
            "type": "csi_ledger",
            "date": "2024-05-14",
            "author": f"CSI Supervisor {csi_name}",
            "text": f"Dry-storage property audit: {q_preserved}. Legacy bench file notes: {q_legacy}.",
        },
        {
            "id": "doc03",
            "title": "Supplemental Scene Canvass & Perimeter Log",
            "type": "scene_report",
            "date": date_str,
            "author": "First Officer",
            "text": f"Secondary collection note: {q_herring}. Public foot traffic was unrestricted prior to tape.",
        },
    ]

    payload = {
        "cause_of_death": scen["cause"],
        "manner_of_death": scen["manner"],
        "death_window": {
            "start_local": fmt_clock(start_min),
            "end_local": fmt_clock(end_min),
            "doc_id": "doc01",
            "quote": q_window,
        },
        "postmortem_repositioning_flag": True,
        "lividity_analysis": {
            "finding": "Fixed posterior lividity conflicts with prone (face-down) recovery position, indicating the body lay supine for hours until livor fixed and was repositioned postmortem.",
            "doc_id": "doc01",
            "quote": q_livor,
        },
        "recommended_modern_test": scen["test"],
        "target_evidence_item": {
            "item": scen["preserved_item"],
            "doc_id": "doc02",
            "quote": q_preserved,
            "legacy_quote": {"doc_id": "doc02", "quote": q_legacy},
        },
        "excluded_red_herring": {
            "item": scen["red_herring_item"],
            "reason": "High daytime public contamination or biological degradation makes testing low-probative noise.",
            "doc_id": "doc03",
            "quote": q_herring,
        },
    }

    reasoning = [
        "1. Lividity vs. posture (doc01): fixed non-blanching posterior livor mortis requires several hours supine after circulation stops; recovery face-down (prone) triggers `postmortem_repositioning_flag = true`.",
        f"2. Rigor/algor bounds & cause/manner (doc01): liver {liver_temp}F in {ambient_temp}F ambient + rigor sets {fmt_clock(start_min)}–{fmt_clock(end_min)}; cause is '{scen['cause']}', manner is '{scen['manner']}'.",
        f"3. Legacy trace triage (doc02 vs doc03): prioritize '{scen['test']}' on dry-stored item in doc02 while excluding contaminated/degraded red herring in doc03.",
    ]

    schema_hint = (
        '{"cause_of_death": "", "manner_of_death": "", '
        '"death_window": {"start_local": "", "end_local": "", "doc_id": "", "quote": ""}, '
        '"postmortem_repositioning_flag": true, '
        '"lividity_analysis": {"finding": "", "doc_id": "", "quote": ""}, '
        '"recommended_modern_test": "M-VAC touch DNA|STRmix probabilistic deconvolution|IGG SNP genealogy|3D NIBIN", '
        '"target_evidence_item": {"item": "", "doc_id": "", "quote": "", "legacy_quote": {"doc_id": "", "quote": ""}}, '
        '"excluded_red_herring": {"item": "", "reason": "", "doc_id": "", "quote": ""}}'
    )
    sys_prompt = _build_system_prompt(
        "The Coroner & CSI: Pathology Bounds & Legacy Trace Re-Testing",
        "Extract cause vs. manner of death, rigor/algor death-window bounds, and lividity fixation vs. recovery posture flags. "
        "Select the exact modern forensic assay (`M-VAC touch DNA`, `STRmix probabilistic deconvolution`, `IGG SNP genealogy`, or `3D NIBIN`) "
        "for preserved dry-storage evidence while excluding contaminated/daytime red herrings.",
        schema_hint,
    )
    usr_prompt = _build_user_prompt(
        case_id,
        "Interpret the autopsy protocol and cold-case property ledger to set medical facts and select the highest-yield modern forensic test.",
        docs,
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
        {"role": "assistant", "content": _format_assistant_turn(reasoning, payload)},
    ]
    ground_truth = {
        "subtask": "pathology_and_trace",
        "docs": docs,
        "postmortem_repositioning_flag": True,
        "recommended_modern_test": scen["test"],
        "cause_of_death": scen["cause"],
        "manner_of_death": scen["manner"],
        "expected_json": payload,
    }
    return messages, ground_truth


# ---------------------------------------------------------------------------
# Drill 6: digital_machine_literacy
# ---------------------------------------------------------------------------


def _gen_digital_machine_literacy(
    rng: random.Random, split: str, index: int, case_id: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    date_str = _sample_incident_date(rng, 2017, 2025)
    subj_name, wit_name = sample_unique_names(rng, 2)
    addr = random_address(rng)
    azimuth = rng.choice((30, 90, 150, 210, 270, 330))
    radius_low = round(rng.uniform(0.4, 0.7), 1)
    radius_high = round(rng.uniform(1.2, 1.8), 1)
    pin = rng.randint(3100, 9099)
    cam_place = rng.choice(
        (
            "Harbor Fuel & Bait exterior overhang camera facing the north pier",
            "Municipal Credit Union drive-thru ATM camera covering the rear alley",
            "County Transit Park-and-Ride pole camera #P-12 overlooking the lot exit",
            "Foundry Hardware loading-bay camera aimed across the side street",
        )
    )
    retention_days = rng.choice((7, 14, 21, 30))

    q_cell = (
        f"Tower #CT-19 Alpha-Sector attachment (azimuth {azimuth} deg, 120-degree wedge, {radius_low}–{radius_high} mile radius) "
        f"logged {subj_name}'s handset at 23:42; sector footprint covers {addr} plus fourteen residential blocks and the highway ramp"
    )
    q_keypad = (
        f"vestibule keypad controller logs entry unlocks only (code {pin} at 23:54) and has no interior exit sensor, "
        "door-close contact switch, or occupancy timer"
    )
    q_media = (
        f"{wit_name} emailed a cropped social-media screenshot (IMG_repost_882.jpg, EXIF metadata stripped by platform compression, "
        "no original camera-roll HEIC/JPEG collected)"
    )
    q_cam_gap = (
        f"Canvass officer noted an active {cam_place} with a {retention_days}-day circular DVR overwrite, "
        "but no subpoena or USB export appears in the custody ledger"
    )

    docs = [
        {
            "id": "doc01",
            "title": "Carrier Cell-Site Sector Engineering Return",
            "type": "carrier_record",
            "date": date_str,
            "author": "RF Compliance",
            "text": f"LTE attachment record: {q_cell}.",
        },
        {
            "id": "doc02",
            "title": "Building Access Hardware Specification",
            "type": "digital_log",
            "date": date_str,
            "author": "Locksmith / CSI",
            "text": f"Bench inspection confirms the {q_keypad}.",
        },
        {
            "id": "doc03",
            "title": "Witness Digital Submission Receipt",
            "type": "media_intake",
            "date": date_str,
            "author": "First Officer",
            "text": f"Portal upload #M-17: {q_media}.",
        },
        {
            "id": "doc04",
            "title": "Neighborhood Video Canvass Sheet",
            "type": "canvass_note",
            "date": date_str,
            "author": "Patrol Canvass",
            "text": f"Block 400 walk-through: {q_cam_gap}.",
        },
    ]

    payload = {
        "cell_sector_interpretation": {
            "azimuth_degrees": azimuth,
            "sector_width_degrees": 120,
            "radius_miles_range": [radius_low, radius_high],
            "pinpoint_address_proven": False,
            "proves": f"Handset radio attached to a 120-degree sector ({radius_low}–{radius_high} mi radius) at 23:42.",
            "cannot_prove": f"Pinpoint presence inside {addr} versus nearby residential blocks or the highway ramp.",
            "doc_id": "doc01",
            "quote": q_cell,
        },
        "keypad_interpretation": {
            "entry_logged": True,
            "exit_or_duration_logged": False,
            "proves": f"Code {pin} unlatched the vestibule lock at 23:54.",
            "cannot_prove": "Who physically pressed the keys, whether the door opened fully, or when anyone exited.",
            "doc_id": "doc02",
            "quote": q_keypad,
        },
        "media_authenticity_check": {
            "exif_present": False,
            "stripped_screenshot": True,
            "evidentiary_limit": "Platform recompression stripped capture clock, GPS, and device serial; requires native camera-roll HEIC/JPEG pull.",
            "doc_id": "doc03",
            "quote": q_media,
        },
        "unpulled_camera_gaps": [
            {
                "camera": cam_place,
                "retention_days": retention_days,
                "doc_id": "doc04",
                "quote": q_cam_gap,
            }
        ],
    }

    reasoning = [
        f"1. Cell-site literacy (doc01): {azimuth}-deg 120-degree wedge spanning {radius_low}–{radius_high} miles is a radio coverage area, NOT a pinpoint address (`pinpoint_address_proven = false`).",
        f"2. Entry-only keypad (doc02): logs unlock code {pin} at 23:54 only; zero exit sensor or occupancy duration proof.",
        "3. Media provenance (doc03): social-media screenshot lacks EXIF capture metadata; native camera-roll file must be requested.",
        f"4. Camera canvass gap (doc04): '{cam_place}' ({retention_days}-day overwrite) was observed on canvass but never pulled into custody.",
    ]

    schema_hint = (
        '{"cell_sector_interpretation": {"azimuth_degrees": 0, "sector_width_degrees": 120, '
        '"radius_miles_range": [0.0, 0.0], "pinpoint_address_proven": false, "proves": "", "cannot_prove": "", "doc_id": "", "quote": ""}, '
        '"keypad_interpretation": {"entry_logged": true, "exit_or_duration_logged": false, "proves": "", "cannot_prove": "", "doc_id": "", "quote": ""}, '
        '"media_authenticity_check": {"exif_present": false, "stripped_screenshot": true, "evidentiary_limit": "", "doc_id": "", "quote": ""}, '
        '"unpulled_camera_gaps": [{"camera": "", "retention_days": 0, "doc_id": "", "quote": ""}]}'
    )
    sys_prompt = _build_system_prompt(
        "Digital: Machine Witness Literacy & Canvass Gaps",
        "State strictly what each digital/machine exhibit proves, what it cannot prove (120-degree cell sector radius vs. pinpoint fallacy, "
        "entry-only keypad vs. duration, stripped screenshot vs. EXIF original), and flag every unpulled camera.",
        schema_hint,
    )
    usr_prompt = _build_user_prompt(
        case_id,
        "Audit the 4 machine and canvass exhibits so no suggestion is upgraded into a proof.",
        docs,
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
        {"role": "assistant", "content": _format_assistant_turn(reasoning, payload)},
    ]
    ground_truth = {
        "subtask": "digital_machine_literacy",
        "docs": docs,
        "pinpoint_address_proven": False,
        "exit_or_duration_logged": False,
        "exif_present": False,
        "unpulled_camera_count": 1,
        "expected_json": payload,
    }
    return messages, ground_truth


# ---------------------------------------------------------------------------
# Drill 7: hypothesis_tournament
# ---------------------------------------------------------------------------


def _gen_hypothesis_tournament(
    rng: random.Random, split: str, index: int, case_id: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    date_str = _sample_incident_date(rng, 2016, 2025)
    victim_name, partner_name, contractor_name = sample_unique_names(rng, 3)
    # Rotate surviving hypothesis across H3, H1, H2 so ranking reflects evidence, never fixed slot bias
    winner_mode = (index // 8) % 3  # 0 -> H3 wins, 1 -> H1 wins, 2 -> H2 wins

    if winner_mode == 0:  # H3 (Overnight contractor access) survives; H1 cleared by post-departure outgoing SMS; H2 contradicted by CSI inside-glass/intact safe
        q1 = f"Victim {victim_name} sent a verified biometric-unlocked text from inside the office at 23:48 reading 'closing out register batch now'"
        q2 = f"Bridge ALPR logs estranged partner {partner_name}'s truck departing westbound across the county line at 23:16 and remaining 28 miles away through morning"
        q3 = "CSI glass exam shows broken transom shards resting on the exterior sill with dust undisturbed beneath the unopened floor safe"
        q4 = f"Master service keypad logged overnight HVAC vendor code #8804 (issued to {contractor_name}) unlocking the rear corridor at 00:04 inside the 23:48–00:30 window"
        q5 = f"Work-order sheet shows {contractor_name} wrote 'completed exterior roof check 22:30, never entered building' despite zero roof hatch sensor trip"
        ranked = ["H3", "H1", "H2"]
        matrix = [
            {
                "hypothesis_id": "H3",
                "title": "Overnight contractor access",
                "status": "SURVIVES_RECORDS",
                "explains": [
                    {"fact": "Rear corridor unlocked by vendor code #8804 at 00:04 inside the post-23:48 narrowed window.", "doc_id": "doc04", "quote": q4},
                    {"fact": "Conflict between vendor work-order denial of interior entry and keypad unlock record.", "doc_id": "doc05", "quote": q5},
                ],
                "unexplained_gaps": ["Keypad proves vendor code #8804 was entered, not interior room camera confirmation."],
                "contradicted_by": [],
            },
            {
                "hypothesis_id": "H1",
                "title": "Partner dispute",
                "status": "CONTRADICTED_BY_RECORD",
                "explains": [],
                "unexplained_gaps": ["No record places estranged partner near the building after 23:16."],
                "contradicted_by": [
                    {
                        "doc_id": "doc02",
                        "quote": q2,
                        "innocent_alternative": "Partner departed the area 32 minutes before the victim's verified 23:48 outgoing message in doc01.",
                    },
                    {
                        "doc_id": "doc01",
                        "quote": q1,
                        "innocent_alternative": "Scheduled message apps exist, though biometric unlock telemetry matches live handset operation.",
                    },
                ],
            },
            {
                "hypothesis_id": "H2",
                "title": "Staged burglary",
                "status": "WEAKENED_WITH_GAPS",
                "explains": [
                    {"fact": "Outward glass fracture on exterior sill and untouched safe indicate staging rather than genuine forced entry for cash.", "doc_id": "doc03", "quote": q3}
                ],
                "unexplained_gaps": ["Explains post-incident scene staging mechanics, not how the actor gained authorized keypad entry at 00:04."],
                "contradicted_by": [],
            },
        ]
    elif winner_mode == 1:  # H1 survives contact; H3 cleared by verified out-of-state flight/badge deactivation; H2 contradicted by forced-entry absence
        q1 = f"Victim {victim_name}'s last verified outgoing call ended at 23:12, fixing the survival floor inside the 23:12–00:15 medical window"
        q2 = f"License-plate reader and garage gate log place estranged partner {partner_name}'s sedan entering the building basement level at 23:24 despite claiming to be home by 22:00"
        q3 = "CSI notes deadbolt engaged from within with zero pry marks, intact glazing, and $4,200 cash undisturbed in the open desk tray"
        q4 = f"Access server audit confirms overnight contractor {contractor_name}'s vendor credential was deactivated at 17:00 two days prior with zero rejected swipe attempts"
        q5 = f"Airline boarding gate scan confirms {contractor_name} boarded Flight 418 out of state at 19:40 on {date_str}"
        ranked = ["H1", "H2", "H3"]
        matrix = [
            {
                "hypothesis_id": "H1",
                "title": "Partner dispute",
                "status": "SURVIVES_RECORDS",
                "explains": [
                    {"fact": "Garage gate and ALPR place partner's sedan inside basement level at 23:24 within the post-23:12 window.", "doc_id": "doc02", "quote": q2},
                    {"fact": "Intact cash tray ($4,200 untouched) and absence of forced entry align with known-access dispute rather than theft.", "doc_id": "doc03", "quote": q3},
                ],
                "unexplained_gaps": ["Garage ALPR proves vehicle entry, requiring elevator/stairwell fob pull to confirm suite entry."],
                "contradicted_by": [],
            },
            {
                "hypothesis_id": "H2",
                "title": "Staged burglary",
                "status": "CONTRADICTED_BY_RECORD",
                "explains": [],
                "unexplained_gaps": ["No ransacking or property removal occurred."],
                "contradicted_by": [
                    {
                        "doc_id": "doc03",
                        "quote": q3,
                        "innocent_alternative": "An interrupted intruder might flee before touching cash, though zero forced-entry signs exist.",
                    }
                ],
            },
            {
                "hypothesis_id": "H3",
                "title": "Overnight contractor access",
                "status": "CONTRADICTED_BY_RECORD",
                "explains": [],
                "unexplained_gaps": ["Zero contractor credentials active on site."],
                "contradicted_by": [
                    {
                        "doc_id": "doc04",
                        "quote": q4,
                        "innocent_alternative": "Deactivated badge rules out electronic swipe entry.",
                    },
                    {
                        "doc_id": "doc05",
                        "quote": q5,
                        "innocent_alternative": "Verified commercial boarding scan places contractor out of state hours before the 23:12 survival floor in doc01.",
                    },
                ],
            },
        ]
    else:  # H2 (Staged burglary / external break-in disguise) survives; H1 & H3 contradicted by records
        q1 = f"Medical examiner and smart-meter motion log bound the incident inside 23:30–00:10 after {victim_name}'s 23:30 alarm disarm"
        q2 = "CSI reconstruction found pry-bar impressions made on the interior jamb face while the exterior weatherstripping remained uncut and locked drawers were neatly stacked rather than dumped"
        q3 = f"Hospital ER triage wristband and hallway CCTV confirm estranged partner {partner_name} was undergoing wrist suture treatment 19 miles north from 22:40 through 01:15"
        q4 = f"GPS fleet telematics and state weigh-station scale receipt fix contractor {contractor_name}'s service van 64 miles east on I-74 at 23:44"
        q5 = "Evidence ledger notes two serial-numbered petty-cash envelopes missing from the unlocked credenza while high-value laptops sat untouched"
        ranked = ["H2", "H1", "H3"]
        matrix = [
            {
                "hypothesis_id": "H2",
                "title": "Staged burglary",
                "status": "SURVIVES_RECORDS",
                "explains": [
                    {"fact": "Interior-only pry marks with uncut exterior weatherstripping match post-incident staging from inside.", "doc_id": "doc02", "quote": q2},
                    {"fact": "Selective removal of two cash envelopes after 23:30 alarm disarm while laptops remained untouched.", "doc_id": "doc05", "quote": q5},
                ],
                "unexplained_gaps": ["Identity of the authorized key/code holder who disarmed at 23:30 requires alarm user-slot subpoena."],
                "contradicted_by": [],
            },
            {
                "hypothesis_id": "H1",
                "title": "Partner dispute",
                "status": "CONTRADICTED_BY_RECORD",
                "explains": [],
                "unexplained_gaps": ["Partner continuously documented on ER CCTV 19 miles away across the entire 23:30–00:10 window."],
                "contradicted_by": [
                    {
                        "doc_id": "doc03",
                        "quote": q3,
                        "innocent_alternative": "Independent hospital CCTV and triage timestamps corroborate the partner's alibi across doc01's window.",
                    }
                ],
            },
            {
                "hypothesis_id": "H3",
                "title": "Overnight contractor access",
                "status": "CONTRADICTED_BY_RECORD",
                "explains": [],
                "unexplained_gaps": ["Contractor fixed 64 miles east during the 23:30–00:10 window."],
                "contradicted_by": [
                    {
                        "doc_id": "doc04",
                        "quote": q4,
                        "innocent_alternative": "DOT weigh-station scale ticket independently confirms GPS telematics 64 miles away.",
                    },
                    {
                        "doc_id": "doc01",
                        "quote": q1,
                        "innocent_alternative": "Alarm clock sync verified within +/- 15 seconds of carrier time.",
                    },
                ],
            },
        ]

    docs = [
        {"id": "doc01", "title": "Timeline Survival-Floor & Alarm Summary", "type": "digital_log", "date": date_str, "author": "Digital Chair", "text": f"Verified timeline anchor: {q1}."},
        {"id": "doc02", "title": "Exhibit B — Physical / Vehicle Record", "type": "scene_report", "date": date_str, "author": "CSI / Traffic", "text": f"Record finding: {q2}."},
        {"id": "doc03", "title": "Exhibit C — Scene / Alibi Verification", "type": "records_extract", "date": date_str, "author": "Cross-Examiner Pull", "text": f"Verified record: {q3}."},
        {"id": "doc04", "title": "Exhibit D — Vendor Access & Telematics", "type": "digital_log", "date": date_str, "author": "Records Desk", "text": f"Subpoenaed vendor audit: {q4}."},
        {"id": "doc05", "title": "Exhibit E — Supplemental Audit", "type": "csi_ledger", "date": date_str, "author": "Lead Squad", "text": f"Audit note: {q5}."},
    ]

    payload = {
        "hypotheses_matrix": matrix,
        "ranked_hypothesis_ids": ranked,
        "governance_note": f"Hypotheses ranked strictly by surviving falsification against case records, without naming any person culpable. {STANDING_BRIEF_CLOSER}",
    }

    reasoning = [
        "1. Anchor the working incident window from doc01 first before testing any hypothesis.",
        "2. Build an explicit Analysis of Competing Hypotheses (ACH) falsification matrix across H1 (Partner dispute), H2 (Staged burglary), and H3 (Overnight contractor access).",
        f"3. Rank hypotheses strictly by record survival ({ranked[0]} > {ranked[1]} > {ranked[2]}), recording verbatim quotes and innocent alternatives without accusing any person.",
    ]

    schema_hint = (
        '{"hypotheses_matrix": [{"hypothesis_id": "H1|H2|H3", "title": "", '
        '"status": "SURVIVES_RECORDS|WEAKENED_WITH_GAPS|CONTRADICTED_BY_RECORD", '
        '"explains": [{"fact": "", "doc_id": "", "quote": ""}], "unexplained_gaps": [""], '
        '"contradicted_by": [{"doc_id": "", "quote": "", "innocent_alternative": ""}]}], '
        '"ranked_hypothesis_ids": ["H1", "H2", "H3"], "governance_note": ""}'
    )
    sys_prompt = _build_system_prompt(
        "Cross-Examiner & Lead Detective: Competing Hypothesis Tournament",
        "Test H1 (`Partner dispute`), H2 (`Staged burglary`), and H3 (`Overnight contractor access`) against all 5 exhibits. "
        "Build a strict falsification matrix (`explains`, `unexplained_gaps`, `contradicted_by`) with verbatim quotes and rank strictly by surviving contact with records—never naming anyone culpable.",
        schema_hint,
    )
    usr_prompt = _build_user_prompt(
        case_id,
        "Run a 3-hypothesis falsification tournament (`H1: Partner dispute`, `H2: Staged burglary`, `H3: Overnight contractor access`) across these 5 exhibits.",
        docs,
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
        {"role": "assistant", "content": _format_assistant_turn(reasoning, payload)},
    ]
    ground_truth = {
        "subtask": "hypothesis_tournament",
        "docs": docs,
        "top_hypothesis": ranked[0],
        "ranked_hypothesis_ids": ranked,
        "expected_json": payload,
    }
    return messages, ground_truth


# ---------------------------------------------------------------------------
# Drill 8: fake_insider_knowledge
# ---------------------------------------------------------------------------


_INSIDER_ARTIFACTS: tuple[dict[str, str], ...] = (
    {
        "detail": "defective brass mortise latch on the rear manager office door that clicked without throwing the bolt",
        "public_doc_title": "County Fire & Building Code Inspection Docket #BI-2015-882",
        "public_line": "Citation 4B (public portal): defective brass mortise latch on the rear manager office door that clicked without throwing the bolt; 30-day repair notice posted",
        "generic_public_line": "Routine exterior inspection passed front illuminated exit signs and parking-lot hydrant clearance with zero interior hardware citations",
    },
    {
        "detail": "disconnected backup battery lead inside the walk-in cooler temperature alarm panel",
        "public_doc_title": "County Health Department Sanitation Report #HD-4410",
        "public_line": "Public inspection portal note: disconnected backup battery lead inside the walk-in cooler temperature alarm panel flagged during annual kitchen audit",
        "generic_public_line": "Annual sanitation score 96/100 noting only handwashing sink soap dispenser refill in main prep kitchen",
    },
    {
        "detail": "cracked frosted-glass transom pane above the basement accounting stairwell taped from the inside with silver duct tape",
        "public_doc_title": "Municipal Small-Claims Landlord-Tenant Filing #SC-1109",
        "public_line": "Exhibit A public repair list cites cracked frosted-glass transom pane above the basement accounting stairwell taped from the inside with silver duct tape",
        "generic_public_line": "Public lease abstract describes square footage and street-level awning signage requirements only",
    },
)


def _gen_fake_insider_knowledge(
    rng: random.Random, split: str, index: int, case_id: str
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    contaminated = ((index // 8) % 2) == 0
    art = _INSIDER_ARTIFACTS[(index // 8) % len(_INSIDER_ARTIFACTS)]
    inc_year = rng.randint(2017, 2024)
    prior_date = f"{inc_year - 1}-04-12"
    inc_date = f"{inc_year}-10-09"
    tip_date = f"{inc_year + 1}-02-18"
    tipster_name, subject_name = sample_unique_names(rng, 2)

    q_tip = (
        f"Blog column and tipster {tipster_name} claimed {subject_name} mentioned the {art['detail']} "
        f"during a {tip_date} conversation, calling it 'non-public scene-only knowledge'"
    )
    q_seal = (
        f"Lead Detective press-holdback memo dated {inc_date} withheld interior scene details including the {art['detail']} "
        "from police media releases"
    )

    if contaminated:
        q_arch = f"Indexed public record published {prior_date}: {art['public_line']}"
        classification = "PUBLIC_DOMAIN_CONTAMINATED"
        prior_pub = prior_date
        weight = "ZERO_CONTAMINATED"
        innocent_alt = (
            f"The {art['detail']} was published on a public county docket on {prior_date}—eighteen months before "
            f"{subject_name}'s {tip_date} remark—and was visible to employees, contractors, or any reader of public filings."
        )
    else:
        q_arch = f"Exhaustive search of pre-{tip_date} county inspection, court, and press archives returned only {prior_date} entry: {art['generic_public_line']}"
        classification = "GENUINE_WITHHELD_HOLDBACK"
        prior_pub = None
        weight = "CORROBORATIVE_LEAD_ONLY"
        innocent_alt = (
            f"Even when absent from public filings, {subject_name} could have learned of the {art['detail']} via prior lawful workplace "
            "maintenance, an unlogged vendor conversation, or informal word-of-mouth from a witness who saw the room before the incident."
        )

    docs = [
        {
            "id": "doc01",
            "title": "Media Clipping & Tip Intake Summary",
            "type": "tip_sheet",
            "date": tip_date,
            "author": "Cold Case Intake",
            "text": f"Submitted clipping: {q_tip}.",
        },
        {
            "id": "doc02",
            "title": "Detective Holdback & Press Release Log",
            "type": "admin_memo",
            "date": inc_date,
            "author": "Lead Detective",
            "text": f"Media dissemination log: {q_seal}.",
        },
        {
            "id": "doc03",
            "title": art["public_doc_title"],
            "type": "public_archive",
            "date": prior_date,
            "author": "County Archive Search",
            "text": f"Certified archival docket check: {q_arch}.",
        },
    ]

    payload = {
        "classification": classification,
        "claimed_insider_detail": art["detail"],
        "statement_date": tip_date,
        "prior_public_disclosure_date": prior_pub,
        "holdback_weight": weight,
        "innocent_alternative": innocent_alt,
        "verbatim_quotes": [
            {"doc_id": "doc01", "quote": q_tip, "source_role": "sensational_claim"},
            {"doc_id": "doc02", "quote": q_seal, "source_role": "police_holdback_memo"},
            {"doc_id": "doc03", "quote": q_arch, "source_role": "archival_public_domain_check"},
        ],
    }

    reasoning = [
        f"1. Identify claimed holdback detail (doc01): '{art['detail']}', uttered on {tip_date}.",
        f"2. Check police press release holdback (doc02, {inc_date}) AND independent county/court public archives (doc03, {prior_date})—because police withholding a fact from press releases does not mean county inspectors had not already published it!",
        f"3. Archival verdict: {classification} (`holdback_weight = {weight}`), recording mandatory `innocent_alternative`.",
    ]

    schema_hint = (
        '{"classification": "PUBLIC_DOMAIN_CONTAMINATED|GENUINE_WITHHELD_HOLDBACK", '
        '"claimed_insider_detail": "", "statement_date": "", "prior_public_disclosure_date": null, '
        '"holdback_weight": "ZERO_CONTAMINATED|CORROBORATIVE_LEAD_ONLY", "innocent_alternative": "", '
        '"verbatim_quotes": [{"doc_id": "", "quote": "", "source_role": ""}]}'
    )
    sys_prompt = _build_system_prompt(
        "Records & Prosecutor: Holdback Contamination & Public-Domain Audit",
        "Test claims of 'scene-only holdback knowledge' against archival county inspection, civil court, and press filings "
        "dated prior to the statement. Distinguish true withheld holdbacks from details already in the public domain, and always state `innocent_alternative`.",
        schema_hint,
    )
    usr_prompt = _build_user_prompt(
        case_id,
        "Audit whether the claimed 'scene-only knowledge' in doc01 was genuinely withheld or already in the public domain.",
        docs,
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
        {"role": "assistant", "content": _format_assistant_turn(reasoning, payload)},
    ]
    ground_truth = {
        "subtask": "fake_insider_knowledge",
        "docs": docs,
        "classification": classification,
        "holdback_weight": weight,
        "expected_json": payload,
    }
    return messages, ground_truth


_DRILL_BUILDERS = {
    "temporal_clock_math": _gen_temporal_clock_math,
    "forensic_nli": _gen_forensic_nli,
    "entity_resolution_graph": _gen_entity_resolution_graph,
    "name_collision_guard": _gen_name_collision_guard,
    "pathology_and_trace": _gen_pathology_and_trace,
    "digital_machine_literacy": _gen_digital_machine_literacy,
    "hypothesis_tournament": _gen_hypothesis_tournament,
    "fake_insider_knowledge": _gen_fake_insider_knowledge,
}


def generate_micro_skill_example(
    split: str,
    index: int,
    salt: str = "mb-spec7-v1",
) -> dict[str, Any]:
    """Deterministically generate 1 forensic micro-skill example cycling evenly across all 8 drills."""
    if index < 0:
        raise ValueError(f"index must be >= 0, got {index}")
    drill_name = MICRO_SKILL_TYPES[index % len(MICRO_SKILL_TYPES)]
    rng = make_rng(split, "forensic_micro_skills", index, salt=salt)
    case_id = f"MB-FMS-{split.upper()}-{index:06d}"

    messages, ground_truth = _DRILL_BUILDERS[drill_name](rng, split, index, case_id)
    example = {
        "id": f"fms_{split}_{index:06d}_{drill_name}",
        "track": "track1_now",
        "domain": "forensic_micro_skills",
        "subtask": drill_name,
        "split": split,
        "messages": messages,
        "ground_truth": ground_truth,
    }

    errs = validate_micro_skill_example(example)
    if errs:
        raise AssertionError(f"Generated invalid forensic_micro_skills example ({example['id']}): {errs}")
    return example


__all__ = [
    "MICRO_SKILL_TYPES",
    "generate_micro_skill_example",
    "validate_micro_skill_example",
]


if __name__ == "__main__":
    counts = {"train": 192, "val": 64, "test": 64}
    verified = 0
    for sp, n in counts.items():
        for i in range(n):
            ex = generate_micro_skill_example(sp, i)
            assert not validate_micro_skill_example(ex)
            verified += 1
    print(f"forensic_micro_skills self-test passed: {verified}/320 examples verified across {len(MICRO_SKILL_TYPES)} drills.")
