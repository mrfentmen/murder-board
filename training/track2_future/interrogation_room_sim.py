"""Track 2 (FUTURE) — Chair 12 In-Room Biometric & Cognitive-Load Co-Pilot Simulator.

Simulates synchronized contactless room physiology (rPPG HR & vagal HRV RMSSD,
infrared phasic EDA & periorbital thermal delta, pupil dilation, vocal pitch jitter,
and acoustic response latency) fused with Murder-Board case records across three
future operating environments:
  - Mode A (50%): Homicide / Cold-Case Interview Room (doc05, doc09, doc11, withheld artifact)
  - Mode B (25%): Future 911 / Bodycam Live Voice-Stress & rPPG Triage Room
  - Mode C (25%): Future AML / Customs / Insider Secondary Inspection Room (6-entity CIT array)

Strictly enforces the Othello Law and the 3 population slices across Homicide & AML:
  - 35% CONCEALING_CASE_FACT
  - 35% OTHELLO_INNOCENT_CONTROL (50/50 OTHELLO_INNOCENT_ANXIOUS & OTHELLO_EMBARRASSED_SECRET)
  - 30% TRAUMA_COOPERATIVE_WITNESS
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from training.common import (
    CASH_FRONT_ARCHETYPES,
    COMMODITY_BENCHMARKS,
    COUNTIES,
    LEGIT_BUSINESS_PROFILES,
    OFFSHORE_JURISDICTIONS,
    SHELL_PREFIXES,
    SHELL_SUFFIXES,
    VEHICLES,
    check_prosecutor_vetoes,
    docs_text_block,
    fmt_clock,
    fmt_clock_12h,
    make_rng,
    norm_ws,
    pick_distinct,
    quote_ok,
    random_address,
    random_plate,
    sample_biometric_baseline,
    sample_biometric_turn,
    sample_unique_names,
)

TRACK_NAME = "track2_future"
DOMAIN_NAME = "future_room_biometric_copilot"
COPILOT_PROMPT_PATH = Path(__file__).resolve().parent / "12_room_copilot.md"

PROHIBITED_GUILT_PHRASES: tuple[str, ...] = (
    "sweat proves lying",
    "heartbeat confirms guilt",
    "subject is lying",
    "is guilty",
    "is lying",
    "is the killer",
    "murdered ",
    "proves beyond doubt",
    "proves deception",
    "confirms deception",
    "confirms guilt",
    "proves guilt",
    "proves lying",
    "deception detected",
    "failed the polygraph",
    "biometrics prove",
    "telemetry proves guilt",
)

VALID_PROTOCOL_CODES: tuple[str, ...] = (
    "calibrate_baseline",
    "run_5_item_cit_array",
    "ask_reverse_order_timeline_step",
    "hold_confrontation_and_verify_via_record",
    "hold_confrontation_and_calibrate_baseline",
    "switch_to_peace_supportive_open_recall",
    "dispatch_silent_pd_approach",
    "run_swatting_verification_protocol",
    "upgrade_als_hemorrhagic_shock_priority",
)

_COPILOT_PROMPT_CACHE: str | None = None


def load_room_copilot_prompt() -> str:
    """Load Chair 12 system prompt from 12_room_copilot.md."""
    global _COPILOT_PROMPT_CACHE
    if _COPILOT_PROMPT_CACHE is None:
        _COPILOT_PROMPT_CACHE = COPILOT_PROMPT_PATH.read_text(encoding="utf-8").strip()
    return _COPILOT_PROMPT_CACHE


def _build_proportional_cycle(weights: list[tuple[str, int]]) -> tuple[str, ...]:
    """Deterministically interleave labels to exact integer counts with minimum prefix discrepancy."""
    total = sum(count for _, count in weights)
    acc = {label: 0 for label, _ in weights}
    used = {label: 0 for label, _ in weights}
    out: list[str] = []
    for _ in range(total):
        best_label = ""
        best_deficit = -10**9
        for label, count in weights:
            acc[label] += count
            if used[label] < count and acc[label] > best_deficit:
                best_deficit = acc[label]
                best_label = label
        acc[best_label] -= total
        used[best_label] += 1
        out.append(best_label)
    return tuple(out)


# Exact 40-slot cycle for Homicide & AML:
# 14/40 (35.0%) CONCEALING_CASE_FACT
#  7/40 (17.5%) OTHELLO_INNOCENT_ANXIOUS  \__ 14/40 (35.0%) OTHELLO_INNOCENT_CONTROL
#  7/40 (17.5%) OTHELLO_EMBARRASSED_SECRET /
# 12/40 (30.0%) TRAUMA_COOPERATIVE_WITNESS
_HOMICIDE_AML_ARCHETYPE_CYCLE: tuple[str, ...] = _build_proportional_cycle([
    ("CONCEALING_CASE_FACT", 14),
    ("OTHELLO_INNOCENT_ANXIOUS", 7),
    ("OTHELLO_EMBARRASSED_SECRET", 7),
    ("TRAUMA_COOPERATIVE_WITNESS", 12),
])

# Exact 4-slot room-mode cycle: 50% Mode A, 25% Mode B, 25% Mode C
_ROOM_MODE_CYCLE: tuple[str, ...] = (
    "homicide_interview",
    "triage_911_bodycam",
    "homicide_interview",
    "aml_customs_secondary",
)

_TRIAGE_SUBTYPE_CYCLE: tuple[str, ...] = (
    "COERCED_VICTIM_FORCED_CALM",
    "CALM_VOIP_SWATTING_CALLER",
    "OCCULT_HEMORRHAGIC_SHOCK_VICTIM",
)

_SPLIT_PHASE_OFFSET: dict[str, int] = {
    "train": 0,
    "val": 11,
    "test": 23,
    "eval_sim": 31,
}

HOMICIDE_CIT_ARTIFACTS: tuple[tuple[str, tuple[str, str, str, str], str], ...] = (
    (
        "stamped brass padlock shackle",
        ("chrome cabinet hasp", "black nylon zip-tie bundle", "steel deadbolt cylinder", "copper conduit clamp"),
        "sheared beside the interior drop-safe",
    ),
    (
        "cracked green ledger binder",
        ("blue spiral payroll notebook", "manila tax envelope", "gray aluminum clipboard", "black vinyl checkbook"),
        "wedged beneath the overturned desk return",
    ),
    (
        "cordless yellow impact driver",
        ("red pry bar", "hickory claw hammer", "rubber-grip pipe wrench", "folding box cutter"),
        "left behind the electrical sub-panel",
    ),
    (
        "torn navy canvas bank pouch",
        ("tan leather coin satchel", "clear tamper-evident deposit bag", "gray steel petty-cash tin", "kraft currency sleeve"),
        "tucked behind the breakroom vending machine",
    ),
    (
        "amber glass apothecary vial",
        ("white travel aspirin tin", "silver insulin pen case", "blue plastic inhaler shell", "clear eyedropper bottle"),
        "recovered in the floor drain grate",
    ),
    (
        "engraved brass boiler tag #44",
        ("laminated visitor badge #12", "aluminum locker token #09", "plastic dock pass #71", "magnetic elevator fob #03"),
        "snagged on the rear stairwell strike plate",
    ),
    (
        "unplugged orange Cat-6 NVR patch cord",
        ("black coaxial BNC jumper", "white USB printer lead", "braided HDMI monitor cord", "gray RJ11 handset cord"),
        "pulled from port 4 of the office recorder",
    ),
    (
        "singed blue shop rag",
        ("white paper towel roll", "yellow microfiber cloth", "black nitrile work glove", "heavy canvas apron"),
        "dropped inside the loading-bay service sink",
    ),
)

HOMICIDE_VENUES: tuple[tuple[str, str, str], ...] = (
    ("Harborlight Cold Storage", "night shift supervisor", "compressor office"),
    ("Garrick Marina Fuel Dock", "harbor bookkeeper", "harbormaster counting room"),
    ("Millbrook Municipal Transfer Station", "scale-house clerk", "weighbridge office"),
    ("Foundry Street Wholesale Florist", "overnight dispatcher", "cooler dispatch office"),
    ("Kestrel Valley Auto Auction", "title vault coordinator", "rear title cage"),
    ("Sycamore Point Ferry Terminal", "purser", "ticket settlement office"),
)

EMBARRASSED_PERSONAL_SECRETS_HOMICIDE: tuple[tuple[str, str, str], ...] = (
    (
        "parked behind the Budget Motor Lodge two blocks west",
        "meeting a married coworker off the clock and trying to keep it out of a pending divorce filing",
        "Budget Motor Lodge guest-lot camera or cell Wi-Fi handoff log",
    ),
    (
        "stopped at the 24-hour check-cashing kiosk on Frontage Rd",
        "wiring an overdue personal gambling debt behind a spouse's back",
        "kiosk transaction receipt timestamped prior to 23:35",
    ),
    (
        "idling behind the closed union hall annex",
        "handing off union organizing cards that would get a probationary worker fired if management heard",
        "annex badge reader or organizer text thread",
    ),
    (
        "parked outside St. Jude parish basement lot",
        "attending a late-night narcotics recovery meeting under a first name only",
        "parish lot exit camera prior to 23:30",
    ),
)

EMBARRASSED_PERSONAL_SECRETS_AML: tuple[tuple[str, str, str], ...] = (
    (
        "carrying an undeclared $6,800 wristwatch box in carry-on luggage",
        "hiding an anniversary watch purchase from customs duty assessment and a joint family bank statement",
        "retail boutique receipt and customs personal-effects amendment form",
    ),
    (
        "routing $14,200 to a personal brokerage account in Miami",
        "shielding a quiet job-change signing bonus during an uncontested marital separation",
        "domestic W-2 signing-bonus stub and retail brokerage statement",
    ),
    (
        "visiting a competitor's warehouse in the free-trade zone",
        "interviewing confidentially for a lateral operations role without alerting current employer",
        "visitor sign-in badge and recruiter calendar invite",
    ),
)

DARK_FLEET_VESSELS: tuple[str, ...] = (
    "M/V Caspian Horizon",
    "M/V Boreal Star",
    "M/V Obsidian Mariner",
    "M/V Halcyon Carrier",
    "M/V Solstice Trader",
    "M/V Aegis Pioneer",
    "M/V Equinox Venture",
    "M/V Cobalt Navigator",
)


def _select_schedule(split: str, index: int) -> tuple[str, str, str]:
    """Return (room_mode, population_slice, subject_state) deterministically."""
    phase = _SPLIT_PHASE_OFFSET.get(split, 0)
    mode_slot = (index + phase) % 4
    room_mode = _ROOM_MODE_CYCLE[mode_slot]

    if room_mode == "homicide_interview":
        k_h = (index // 4) * 2 + (1 if (index + phase) % 4 == 2 else 0)
        subject_state = _HOMICIDE_AML_ARCHETYPE_CYCLE[(k_h + phase) % len(_HOMICIDE_AML_ARCHETYPE_CYCLE)]
    elif room_mode == "aml_customs_secondary":
        k_c = index // 4
        subject_state = _HOMICIDE_AML_ARCHETYPE_CYCLE[(k_c + phase + 19) % len(_HOMICIDE_AML_ARCHETYPE_CYCLE)]
    else:
        k_b = index // 4
        subject_state = _TRIAGE_SUBTYPE_CYCLE[(k_b + phase) % len(_TRIAGE_SUBTYPE_CYCLE)]
        return room_mode, "TRIAGE_PHYSIOLOGY_DIVERGENCE", subject_state

    if subject_state in ("OTHELLO_INNOCENT_ANXIOUS", "OTHELLO_EMBARRASSED_SECRET"):
        pop_slice = "OTHELLO_INNOCENT_CONTROL"
    else:
        pop_slice = subject_state
    return room_mode, pop_slice, subject_state


def _format_turn_doc(
    turn_id: str,
    stage_label: str,
    clock_offset: str,
    investigator_prompt: str,
    subject_reply: str,
    sensor_pkt: dict[str, Any],
) -> dict[str, Any]:
    bio = sensor_pkt["biometrics"]
    ac = sensor_pkt["acoustics"]
    telemetry_line = json.dumps({"biometrics": bio, "acoustics": ac}, separators=(", ", ": "))
    text = (
        f"[Room Stage: {stage_label}]\n"
        f"Question: \"{investigator_prompt}\"\n"
        f"Subject: \"{subject_reply}\"\n"
        f"Telemetry: {telemetry_line}"
    )
    return {
        "id": turn_id,
        "title": stage_label,
        "type": "room_telemetry_turn",
        "date": clock_offset,
        "author": "Chair 12 Contactless Sensor Rig",
        "text": text,
        "biometrics": bio,
        "acoustics": ac,
        "subject_reply": subject_reply,
        "investigator_prompt": investigator_prompt,
    }


def _mean_eda(turns: list[dict[str, Any]]) -> float:
    vals = [t["biometrics"]["eda_sweat_uS"] for t in turns]
    return round(sum(vals) / max(1, len(vals)), 2)


def _generate_mode_a_homicide(
    rng: random.Random,
    subject_state: str,
    pop_slice: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    names = sample_unique_names(rng, 4)
    victim_name, subject_name, opener_name, coworker_name = names
    county_a, county_b, corridor = rng.choice(COUNTIES)
    venue_name, victim_role, room_label = rng.choice(HOMICIDE_VENUES)
    veh_model, veh_color, _ = rng.choice(VEHICLES)
    plate = random_plate(rng)
    site_addr = random_address(rng)

    year = rng.randint(2018, 2026)
    month = rng.randint(1, 11)
    day = rng.randint(3, 25)
    incident_date = f"{year}-{month:02d}-{day:02d}"
    interview_date = f"{year}-{month:02d}-{day + 2:02d}"

    victim_pin = str(rng.randint(3104, 4899))
    subject_pin = str(rng.randint(7102, 9894))
    surv_min = 23 * 60 + rng.randint(44, 56)  # ~23:44 - 23:56
    entry_min = 24 * 60 + rng.randint(4, 14)  # ~00:04 - 00:14
    meter_off_min = entry_min + rng.randint(11, 19)  # ~00:15 - 00:33
    outbound_alpr_min = meter_off_min + rng.randint(6, 12)

    artifact, decoys, artifact_loc = rng.choice(HOMICIDE_CIT_ARTIFACTS)
    cit_order = list(decoys)
    rng.shuffle(cit_order)
    target_pos = rng.randint(1, 4)  # 0-indexed -> slot 2..5 so slot 1 is always buffer decoy
    cit_five_items = cit_order[:target_pos] + [artifact] + cit_order[target_pos:]

    if subject_state == "CONCEALING_CASE_FACT":
        doc05_quote = (
            f"PIN {victim_pin} ({victim_name}) entered {room_label} at {fmt_clock(surv_min)}; "
            f"PIN {subject_pin} ({subject_name}) logged door entry at {fmt_clock(entry_min)}."
        )
        doc09_quote = (
            f"Eastbound {corridor} ALPR logged {veh_color} {veh_model} plate {plate} "
            f"departing {county_a} industrial spur at {fmt_clock(outbound_alpr_min)}."
        )
        doc11_quote = (
            f"Sub-meter circuit B4 ({room_label} task lights and terminal) drew 1.46 kW continuously "
            f"until abrupt load drop to 0.08 kW at {fmt_clock(meter_off_min)}."
        )
        scene_quote = (
            f"Withheld scene artifact: {artifact} {artifact_loc}; zero public or media release."
        )
        base = sample_biometric_baseline(rng, "CALM_CONCEALER")
        t1_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t2_pkt = sample_biometric_turn(rng, base, "general_accusation_calm_liar")
        t3_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t4_pkt = sample_biometric_turn(rng, base, "cit_guilty_knowledge_hit")
        t5_pkt = sample_biometric_turn(rng, base, "cognitive_load_reverse_order")

        t2_reply = (
            f"I never stepped inside the {room_label} after 11:00 PM; the lights were already dark when I checked the hall."
        )
        t4_reply = f"No, I do not recognize any {artifact}, all five of those sound unfamiliar to me."
        t5_reply = (
            f"Going backward from 12:30 AM—uh, wait—I was already across {corridor} by 11:25 PM, maybe 11:30 PM."
        )

        turns = [
            _format_turn_doc(
                "turn01",
                "Calibration Control — Shift Roster & Vehicle Confirmation",
                "00:01:10",
                f"For calibration, confirm your assigned {veh_color} {veh_model} plate {plate} and start-of-shift time.",
                f"Yes, {plate} is my {veh_model}, and I clocked in at 6:00 PM at {venue_name}.",
                t1_pkt,
            ),
            _format_turn_doc(
                "turn02",
                "Broad Timeline & Access Denial Question",
                "00:03:05",
                f"Did you enter the {room_label} or see {victim_name} after 11:00 PM on {incident_date}?",
                t2_reply,
                t2_pkt,
            ),
            _format_turn_doc(
                "turn03",
                "5-Item CIT Probe — 4 Non-Case Buffer & Decoy Stimuli",
                "00:05:20",
                f"Listen as I name scene-check items and answer no to each: {', '.join(decoys)}.",
                "No to each of those items, none of those mean anything to me.",
                t3_pkt,
            ),
            _format_turn_doc(
                "turn04",
                f"5-Item CIT Probe — Position #{target_pos + 1} Withheld Artifact Stimulus",
                "00:06:04",
                f"Item {target_pos + 1} in the sequence: a {artifact}.",
                t4_reply,
                t4_pkt,
            ),
            _format_turn_doc(
                "turn05",
                "Reverse-Chronology Cognitive-Load Prompt",
                "00:08:15",
                f"Walk backward in 10-minute steps from 00:35 back to 23:15, naming each room and road.",
                t5_reply,
                t5_pkt,
            ),
        ]
        if rng.random() < 0.5:
            t6_pkt = sample_biometric_turn(rng, base, "cognitive_load_reverse_order")
            turns.append(
                _format_turn_doc(
                    "turn06",
                    "Spatial Badge Custody Check",
                    "00:10:02",
                    f"Starting from your {veh_model} seat at departure, trace backward where your keypad PIN {subject_pin} card sat.",
                    f"It stayed clipped to my belt loop—unless somebody borrowed the spare hook earlier that week.",
                    t6_pkt,
                )
            )

        use_cit_replication = rng.random() < 0.35
        proto_code = "run_5_item_cit_array" if use_cit_replication else "ask_reverse_order_timeline_step"
        next_move_text = (
            f"Run a second independent 5-item CIT array on the {room_label} point-of-exit hardware without revealing why '{artifact}' was probed, then ask {subject_name} in reverse order to account for the gap between {fmt_clock(entry_min)} and {fmt_clock(outbound_alpr_min)}; hold direct accusation."
            if use_cit_replication
            else f"Ask {subject_name} a reverse-order timeline step from the {fmt_clock(outbound_alpr_min)} {corridor} transit back to {fmt_clock(entry_min)} and request physical inspection of keypad credential {subject_pin} while holding confrontation on '{artifact}'."
        )
        assessment = "stimulus_locked_cit_and_cognitive_load"
        pattern_desc = (
            f"Subject maintained a calm resting baseline (HR {base['baseline_hr_bpm']} BPM, HRV {base['baseline_hrv_rmssd_ms']} ms, EDA {base['baseline_eda_uS']} uS) "
            f"and remained composed during the broad accusation in turn02 (HR {t2_pkt['biometrics']['hr_bpm']} BPM, latency {t2_pkt['acoustics']['response_latency_ms']} ms) "
            f"and all four CIT decoys in turn03 (EDA {t3_pkt['biometrics']['eda_sweat_uS']} uS). "
            f"A sharp within-subject orienting shift occurred exclusively on withheld item '{artifact}' in turn04 "
            f"(HRV suppressed to {t4_pkt['biometrics']['hrv_rmssd_ms']} ms, phasic EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS, pupil +{t4_pkt['biometrics']['pupil_dilation_delta_mm']} mm), "
            f"followed by a cognitive-load latency surge to {t5_pkt['acoustics']['response_latency_ms']} ms in turn05 alongside record friction against doc05, doc09, and doc11."
        )
        innocent_alt = (
            f"{subject_name} may have handled or seen a {artifact} during routine prior-shift duties at {venue_name} before {incident_date}, "
            f"and backward time reconstruction naturally elevates working-memory latency while badge PIN {subject_pin} could reflect shared or borrowed credential access."
        )
        cross_check = (
            f"Pull prior 30-day maintenance/inventory logs for {venue_name} to test innocent prior exposure to '{artifact}', "
            f"audit physical custody of PIN {subject_pin} against hallway camera gaps around {fmt_clock(entry_min)}, and verify {plate} ALPR frame image from doc09."
        )
        findings = [
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"Composed broad denial: HR {t2_pkt['biometrics']['hr_bpm']} vs {base['baseline_hr_bpm']} BPM baseline; EDA {t2_pkt['biometrics']['eda_sweat_uS']} uS.",
                "note": "Rehearsed broad denial shows minimal autonomic change, demonstrating why broad-question arousal alone is uninformative.",
            },
            {
                "doc_id": "doc05",
                "quote": doc05_quote,
                "telemetry_delta": "Paper access timestamp conflicts with turn02 hallway-only claim.",
                "note": "Keypad logs an entry event on assigned PIN inside the post-survival window.",
            },
            {
                "doc_id": "doc11",
                "quote": doc11_quote,
                "telemetry_delta": "Sub-meter 1.46 kW draw refutes turn02 dark-room premise.",
                "note": f"Electrical load remained active until {fmt_clock(meter_off_min)}.",
            },
            {
                "doc_id": "turn04",
                "quote": t4_reply,
                "telemetry_delta": f"Stimulus-locked CIT differential: EDA {t4_pkt['biometrics']['eda_sweat_uS']} vs {t3_pkt['biometrics']['eda_sweat_uS']} uS decoys; HRV {t4_pkt['biometrics']['hrv_rmssd_ms']} ms; pupil +{t4_pkt['biometrics']['pupil_dilation_delta_mm']} mm.",
                "note": "Orienting recognition response isolated to withheld doc_scene artifact relative to four decoys.",
            },
            {
                "doc_id": "turn05",
                "quote": t5_reply,
                "telemetry_delta": f"Reverse-order latency {t5_pkt['acoustics']['response_latency_ms']} ms vs {base['baseline_latency_ms']} ms baseline; {t5_pkt['acoustics']['speech_rate_wpm']} wpm.",
                "note": f"Backward timeline claim conflicts with doc09 ALPR read at {fmt_clock(outbound_alpr_min)}.",
            },
        ]
        cit_eval = {
            "administered": True,
            "target_stimulus": artifact,
            "decoy_mean_eda_uS": t3_pkt["biometrics"]["eda_sweat_uS"],
            "target_eda_uS": t4_pkt["biometrics"]["eda_sweat_uS"],
            "target_hrv_rmssd_ms": t4_pkt["biometrics"]["hrv_rmssd_ms"],
            "orienting_differential_observed": True,
        }

    elif subject_state == "OTHELLO_INNOCENT_ANXIOUS":
        early_alpr_min = surv_min - rng.randint(24, 42)
        doc05_quote = (
            f"PIN {victim_pin} ({victim_name}) entered {room_label} at {fmt_clock(surv_min)}; "
            f"zero entries recorded for {subject_name} PIN {subject_pin} after 22:15."
        )
        doc09_quote = (
            f"Westbound {corridor} ALPR logged {veh_color} {veh_model} plate {plate} clearing into {county_b} at {fmt_clock(early_alpr_min)}."
        )
        doc11_quote = (
            f"Sub-meter circuit B4 ({room_label} task lights and terminal) remained steady at 1.46 kW until {fmt_clock(meter_off_min)}."
        )
        scene_quote = (
            f"Withheld scene artifact: {artifact} {artifact_loc}; zero public or media release."
        )
        base = sample_biometric_baseline(rng, "OTHELLO_INNOCENT_ANXIOUS")
        t1_pkt = sample_biometric_turn(rng, base, "othello_panic_both_control_and_target")
        t2_pkt = sample_biometric_turn(rng, base, "othello_panic_both_control_and_target")
        t3_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t4_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t5_pkt = sample_biometric_turn(rng, base, "othello_panic_both_control_and_target")

        t1_reply = f"My address is {site_addr}—look, my hands are shaking because I have never been in an interrogation room in my life."
        t2_reply = f"I clocked out at 10:15 PM and drove my {veh_model} across {corridor} before {fmt_clock_12h(early_alpr_min + 4)}, I swear I did not hurt {victim_name}."
        t4_reply = f"No, I have no idea about a {artifact}, I never went back near the {room_label}."

        turns = [
            _format_turn_doc(
                "turn01",
                "Calibration Control — Residential Address & Vehicle",
                "00:01:05",
                f"Take a breath; for baseline calibration, state your home address and confirm plate {plate}.",
                t1_reply,
                t1_pkt,
            ),
            _format_turn_doc(
                "turn02",
                "Broad Timeline Question",
                "00:02:48",
                f"Account for your movements between 22:15 and 00:30 on {incident_date}.",
                t2_reply,
                t2_pkt,
            ),
            _format_turn_doc(
                "turn03",
                "5-Item CIT Probe — 4 Non-Case Decoy Stimuli",
                "00:04:50",
                f"Answer simply no as I list items: {', '.join(decoys)}.",
                "No, none of those mean anything to me.",
                t3_pkt,
            ),
            _format_turn_doc(
                "turn04",
                f"5-Item CIT Probe — Position #{target_pos + 1} Withheld Artifact Stimulus",
                "00:05:38",
                f"Item {target_pos + 1}: a {artifact}.",
                t4_reply,
                t4_pkt,
            ),
            _format_turn_doc(
                "turn05",
                "Reverse-Chronology Verification Step",
                "00:07:22",
                f"Walk backward from arriving home in {county_b} to crossing {corridor}.",
                f"I parked at home around {fmt_clock_12h(early_alpr_min + 18)}, came off {corridor} bridge at {fmt_clock_12h(early_alpr_min)}, and stopped for gas at 10:25 PM.",
                t5_pkt,
            ),
        ]

        proto_code = "hold_confrontation_and_calibrate_baseline"
        assessment = "generalized_othello_arousal_non_specific"
        pattern_desc = (
            f"Classic Othello-trap profile: high raw tachycardia and tonic sweat already present at room entry "
            f"(baseline HR {base['baseline_hr_bpm']} BPM, HRV {base['baseline_hrv_rmssd_ms']} ms, EDA {base['baseline_eda_uS']} uS) "
            f"and sustained equally across neutral control turn01 (HR {t1_pkt['biometrics']['hr_bpm']} BPM, EDA {t1_pkt['biometrics']['eda_sweat_uS']} uS) "
            f"and timeline turn02 (HR {t2_pkt['biometrics']['hr_bpm']} BPM, EDA {t2_pkt['biometrics']['eda_sweat_uS']} uS). "
            f"Critically, within-subject CIT response to withheld artifact '{artifact}' in turn04 (EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS, HRV {t4_pkt['biometrics']['hrv_rmssd_ms']} ms) "
            f"shows zero orienting differential over the four decoys in turn03 (EDA {t3_pkt['biometrics']['eda_sweat_uS']} uS)."
        )
        innocent_alt = (
            f"Generalized sympathetic panic from fear of wrongful suspicion in a police interview room elevates HR above 110 BPM and EDA above 5 uS across every question indiscriminately, "
            f"while doc09 and doc05 independently place {subject_name} out of {county_a} {surv_min - early_alpr_min} minutes before {victim_name}'s verified live PIN entry."
        )
        cross_check = (
            f"Pull the {county_b} gas-station POS receipt around 22:25 and confirm doc09 ALPR cab driver image at {fmt_clock(early_alpr_min)} "
            f"against doc05 survival floor at {fmt_clock(surv_min)} to formally corroborate {subject_name}'s window clearance."
        )
        next_move_text = (
            f"Hold all confrontation immediately, de-escalate room tone to re-calibrate baseline, and clear/verify {subject_name}'s pre-window departure via doc09 and POS records rather than pressuring an anxious witness."
        )
        findings = [
            {
                "doc_id": "turn01",
                "quote": t1_reply,
                "telemetry_delta": f"Non-specific control-turn panic: HR {t1_pkt['biometrics']['hr_bpm']} BPM, EDA {t1_pkt['biometrics']['eda_sweat_uS']} uS on routine address control.",
                "note": "High raw sweat and pulse on neutral calibration establishes generalized room fear under the Othello Law.",
            },
            {
                "doc_id": "turn04",
                "quote": t4_reply,
                "telemetry_delta": f"Null CIT differential: target EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS vs decoy {t3_pkt['biometrics']['eda_sweat_uS']} uS; pupil +{t4_pkt['biometrics']['pupil_dilation_delta_mm']} mm.",
                "note": "Zero stimulus-locked recognition of the withheld scene artifact.",
            },
            {
                "doc_id": "doc09",
                "quote": doc09_quote,
                "telemetry_delta": "Corroborates turn02 and turn05 outbound corridor transit.",
                "note": f"Places vehicle into {county_b} prior to narrowed homicide window.",
            },
            {
                "doc_id": "doc05",
                "quote": doc05_quote,
                "telemetry_delta": "Fixes victim alive well after subject cleared the corridor.",
                "note": f"Victim used own PIN {victim_pin} at {fmt_clock(surv_min)}, corroborating clearance for {subject_name}.",
            },
        ]
        cit_eval = {
            "administered": True,
            "target_stimulus": artifact,
            "decoy_mean_eda_uS": t3_pkt["biometrics"]["eda_sweat_uS"],
            "target_eda_uS": t4_pkt["biometrics"]["eda_sweat_uS"],
            "target_hrv_rmssd_ms": t4_pkt["biometrics"]["hrv_rmssd_ms"],
            "orienting_differential_observed": False,
        }

    elif subject_state == "OTHELLO_EMBARRASSED_SECRET":
        secret_loc, secret_reason, secret_record = rng.choice(EMBARRASSED_PERSONAL_SECRETS_HOMICIDE)
        early_alpr_min = surv_min - rng.randint(22, 36)
        doc05_quote = (
            f"PIN {victim_pin} ({victim_name}) entered {room_label} at {fmt_clock(surv_min)}; "
            f"no keypad entry logged for {subject_name} PIN {subject_pin} after 21:40."
        )
        doc09_quote = (
            f"Municipal ALPR unit #7 logged {veh_color} {veh_model} plate {plate} {secret_loc} at 23:08 and outbound onto {corridor} at {fmt_clock(early_alpr_min)}."
        )
        doc11_quote = (
            f"Sub-meter circuit B4 ({room_label} task lights and terminal) remained active at 1.46 kW through {fmt_clock(meter_off_min)}."
        )
        scene_quote = (
            f"Withheld scene artifact: {artifact} {artifact_loc}; zero public or media release."
        )
        base = sample_biometric_baseline(rng, "CALM_CONCEALER")
        t1_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t2_pkt = sample_biometric_turn(rng, base, "embarrassed_unrelated_secret")
        t3_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t4_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t5_pkt = sample_biometric_turn(rng, base, "neutral_control")

        t2_reply = (
            f"Okay, I lied earlier about going straight home—I was {secret_loc} at 11:10 PM because I was {secret_reason}, and I left onto {corridor} around {fmt_clock_12h(early_alpr_min)}."
        )
        t4_reply = f"No, I have never seen a {artifact}, I did not set foot inside {venue_name} after 9:40 PM."

        turns = [
            _format_turn_doc(
                "turn01",
                "Calibration Control — Routine Shift Verification",
                "00:01:02",
                f"Confirm your role at {venue_name} and your {veh_color} {veh_model} plate {plate}.",
                f"I work inventory there and drive the {veh_color} {veh_model}, plate {plate}.",
                t1_pkt,
            ),
            _format_turn_doc(
                "turn02",
                "ALPR Proximity Question Touching Unrelated Personal Secret",
                "00:02:55",
                f"ALPR logged plate {plate} {secret_loc} at 23:08 instead of at your residence; explain why.",
                t2_reply,
                t2_pkt,
            ),
            _format_turn_doc(
                "turn03",
                "5-Item Crime CIT Probe — 4 Non-Case Decoy Stimuli",
                "00:05:10",
                f"Answer no to each item in this sequence: {', '.join(decoys)}.",
                "No to all four, none of those are familiar.",
                t3_pkt,
            ),
            _format_turn_doc(
                "turn04",
                f"5-Item Crime CIT Probe — Position #{target_pos + 1} Withheld Artifact Stimulus",
                "00:05:54",
                f"Item {target_pos + 1}: a {artifact}.",
                t4_reply,
                t4_pkt,
            ),
            _format_turn_doc(
                "turn05",
                "Reverse-Chronology Post-23:15 Check",
                "00:07:30",
                f"Trace backward from midnight to 23:05 along {corridor}.",
                f"At midnight I was home in bed; working back, I merged onto {corridor} at {fmt_clock_12h(early_alpr_min)} right after leaving that lot.",
                t5_pkt,
            ),
        ]

        proto_code = "hold_confrontation_and_verify_via_record"
        assessment = "unrelated_personal_secret_cit_negative"
        pattern_desc = (
            f"Subject entered near resting baseline (HR {base['baseline_hr_bpm']} BPM, EDA {base['baseline_eda_uS']} uS) "
            f"and exhibited a pronounced embarrassment/blush surge exclusively in turn02 when asked about {secret_loc} "
            f"(periorbital temp +{t2_pkt['biometrics']['periorbital_temp_delta_c']} C, EDA {t2_pkt['biometrics']['eda_sweat_uS']} uS, HR {t2_pkt['biometrics']['hr_bpm']} BPM). "
            f"Across the 5-item crime CIT array, withheld artifact '{artifact}' in turn04 produced zero orienting differential "
            f"(EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS vs decoy {t3_pkt['biometrics']['eda_sweat_uS']} uS; HRV {t4_pkt['biometrics']['hrv_rmssd_ms']} ms), "
            f"and reverse-chronology recall in turn05 remained calm ({t5_pkt['acoustics']['response_latency_ms']} ms latency)."
        )
        innocent_alt = (
            f"Social shame and privacy fear over {secret_reason} produce genuine facial thermal blush and phasic EDA spikes on whereabouts questions "
            f"without any connection to the post-{fmt_clock(surv_min)} homicide window."
        )
        cross_check = (
            f"Pull the {secret_record} and cross-verify doc09 outbound read at {fmt_clock(early_alpr_min)} against {victim_name}'s live PIN entry at {fmt_clock(surv_min)} in doc05 to confirm window elimination."
        )
        next_move_text = (
            f"Hold homicide confrontation; do not mistake embarrassment arousal on turn02 for involvement in the {room_label} offense, and verify the {secret_record} at the desk."
        )
        findings = [
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"Embarrassment blush spike: periorbital +{t2_pkt['biometrics']['periorbital_temp_delta_c']} C, EDA {t2_pkt['biometrics']['eda_sweat_uS']} uS, latency {t2_pkt['acoustics']['response_latency_ms']} ms.",
                "note": "Autonomic surge locks onto personal privacy disclosure rather than the crime window.",
            },
            {
                "doc_id": "turn04",
                "quote": t4_reply,
                "telemetry_delta": f"Flat CIT target response: EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS vs {t3_pkt['biometrics']['eda_sweat_uS']} uS decoys; HRV {t4_pkt['biometrics']['hrv_rmssd_ms']} ms.",
                "note": "Complete absence of orienting recognition on withheld crime artifact.",
            },
            {
                "doc_id": "doc09",
                "quote": doc09_quote,
                "telemetry_delta": "Matches disclosed turn02 lot presence and pre-window departure.",
                "note": f"Confirms outbound movement at {fmt_clock(early_alpr_min)}, before narrowed incident window.",
            },
            {
                "doc_id": "doc05",
                "quote": doc05_quote,
                "telemetry_delta": "Establishes victim alive after subject departed area.",
                "note": f"Victim entered {room_label} on PIN {victim_pin} at {fmt_clock(surv_min)}.",
            },
        ]
        cit_eval = {
            "administered": True,
            "target_stimulus": artifact,
            "decoy_mean_eda_uS": t3_pkt["biometrics"]["eda_sweat_uS"],
            "target_eda_uS": t4_pkt["biometrics"]["eda_sweat_uS"],
            "target_hrv_rmssd_ms": t4_pkt["biometrics"]["hrv_rmssd_ms"],
            "orienting_differential_observed": False,
        }

    else:  # TRAUMA_COOPERATIVE_WITNESS
        opener_pin = str(rng.randint(5100, 6899))
        discover_min = 5 * 60 + rng.randint(18, 49)
        doc05_quote = (
            f"PIN {victim_pin} ({victim_name}) entered {room_label} at {fmt_clock(surv_min)}; "
            f"morning opener PIN {opener_pin} ({opener_name}) unlocked {room_label} at {fmt_clock(discover_min)}."
        )
        doc09_quote = (
            f"Corridor ALPR logged {opener_name}'s vehicle plate {plate} arriving inbound toward {venue_name} at {fmt_clock(discover_min - 9)}."
        )
        doc11_quote = (
            f"Sub-meter circuit B4 dropped from 1.46 kW to 0.08 kW at {fmt_clock(meter_off_min)} and stayed at 0.08 kW until {fmt_clock(discover_min)}."
        )
        scene_quote = (
            f"Withheld scene artifact: {artifact} {artifact_loc}; {opener_name} backed out from doorway threshold without entering interior safe alcove."
        )
        subject_name = opener_name
        base = sample_biometric_baseline(rng, "TRAUMA_WITNESS")
        t1_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t2_pkt = sample_biometric_turn(rng, base, "trauma_sensory_flashback")
        t3_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t4_pkt = sample_biometric_turn(rng, base, "trauma_sensory_flashback")

        t2_reply = (
            f"When I punched PIN {opener_pin} at {fmt_clock(discover_min)}, the overhead lights were off and I saw {victim_name} on the floor—my chest locked up and I backed straight into the hall to call 911."
        )
        t4_reply = (
            f"I remember the smell of ozone or cold metal from the doorway and {coworker_name}'s clipboard on the outer counter, I cannot stop picturing the doorway."
        )

        turns = [
            _format_turn_doc(
                "turn01",
                "Calibration Control — Morning Arrival Routine",
                "00:01:08",
                f"Thank you for coming in, {opener_name}; confirm your usual opening route and plate {plate}.",
                f"I drive in on {corridor} in plate {plate} around five-fifteen every weekday morning.",
                t1_pkt,
            ),
            _format_turn_doc(
                "turn02",
                "Scene Discovery Free-Recall Turn",
                "00:02:40",
                f"In your own words, tell us what happened when you reached the {room_label} door.",
                t2_reply,
                t2_pkt,
            ),
            _format_turn_doc(
                "turn03",
                "Supportive Pacing & Breathing Grounding Turn",
                "00:04:55",
                "Take all the time you need and sip some water; who else had arrived in the parking lot by then?",
                "Nobody else was in the employee stalls yet, the lot asphalt was still empty.",
                t3_pkt,
            ),
            _format_turn_doc(
                "turn04",
                "Sensory Context Recall Turn",
                "00:06:30",
                "Without guessing, what sounds, lighting, or objects stood out from the hallway threshold?",
                t4_reply,
                t4_pkt,
            ),
        ]

        proto_code = "switch_to_peace_supportive_open_recall"
        assessment = "trauma_recall_sympathetic_surge"
        pattern_desc = (
            f"Cooperative witness entered with mildly elevated sympathetic tone (HR {base['baseline_hr_bpm']} BPM, EDA {base['baseline_eda_uS']} uS), "
            f"surged sharply during acute sensory flashbacks of discovering the scene in turn02 (HR {t2_pkt['biometrics']['hr_bpm']} BPM, resp {t2_pkt['biometrics']['respiration_rpm']} RPM, jitter {t2_pkt['acoustics']['vocal_pitch_jitter_pct']}%) "
            f"and turn04 (HR {t4_pkt['biometrics']['hr_bpm']} BPM, EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS), "
            f"and down-regulated cleanly to {t3_pkt['biometrics']['hr_bpm']} BPM during supportive pacing in turn03 while matching doc05, doc09, and doc11."
        )
        innocent_alt = (
            f"Acute post-traumatic sensory re-experiencing when recounting the discovery of a deceased coworker triggers sympathetic heart-rate, respiratory, and vocal-tremor surges "
            f"that reflect trauma memory encoding rather than concealment."
        )
        cross_check = (
            f"Corroborate {opener_name}'s {fmt_clock(discover_min)} doorway timeline against 911 PSAP audio intake timestamp, doc05 PIN {opener_pin} entry, "
            f"and unpulled exterior parking-lot CCTV to verify empty stalls upon arrival."
        )
        next_move_text = (
            f"Switch immediately to supportive PEACE Cognitive Interview open-ended recall: allow witness-paced pauses, reinstate outer-lot sensory context without leading questions, and refrain from CIT or reverse-order pressure."
        )
        findings = [
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"Trauma flashback surge: HR {t2_pkt['biometrics']['hr_bpm']} BPM, resp {t2_pkt['biometrics']['respiration_rpm']} RPM, jitter {t2_pkt['acoustics']['vocal_pitch_jitter_pct']}%.",
                "note": "Sympathetic spike aligns with visual discovery of the victim and immediate 911 call.",
            },
            {
                "doc_id": "doc05",
                "quote": doc05_quote,
                "telemetry_delta": "Exact clock match to witness PIN entry and dark-room state.",
                "note": f"Confirms opener PIN {opener_pin} at {fmt_clock(discover_min)} hours after homicide window closed.",
            },
            {
                "doc_id": "doc11",
                "quote": doc11_quote,
                "telemetry_delta": "Corroborates witness report that overhead lights were already off at discovery.",
                "note": f"Circuit load dropped to 0.08 kW back at {fmt_clock(meter_off_min)}.",
            },
            {
                "doc_id": "turn04",
                "quote": t4_reply,
                "telemetry_delta": f"Sensory recall wave: EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS, HR {t4_pkt['biometrics']['hr_bpm']} BPM after calming to {t3_pkt['biometrics']['hr_bpm']} BPM in turn03.",
                "note": "Normalizes under supportive pacing, confirming cooperative trauma recall.",
            },
        ]
        cit_eval = {
            "administered": False,
            "target_stimulus": artifact,
            "decoy_mean_eda_uS": 0.0,
            "target_eda_uS": 0.0,
            "target_hrv_rmssd_ms": 0.0,
            "orienting_differential_observed": False,
        }

    case_docs = [
        {"id": "doc05", "title": f"{venue_name} Electronic Keypad Log", "type": "access_log", "date": incident_date, "author": "Facility Security System", "text": doc05_quote},
        {"id": "doc09", "title": f"{county_a} Corridor ALPR Log", "type": "alpr_log", "date": incident_date, "author": "Automated License Plate Reader", "text": doc09_quote},
        {"id": "doc11", "title": f"{venue_name} Utility Smart-Meter Log", "type": "smart_meter", "date": incident_date, "author": "Grid Sub-Meter Telemetry", "text": doc11_quote},
        {"id": "doc_scene", "title": "CSI Withheld Artifact Memo", "type": "csi_memo", "date": incident_date, "author": "Crime Scene Unit", "text": scene_quote},
    ]

    user_prompt = (
        f"CHAIR 12 ROOM CONSOLE — MODE: homicide_interview\n"
        f"Session Date: {interview_date} | Subject: {subject_name} | Venue: {venue_name} ({county_a})\n"
        f"CIT 5-Item Array Sequence: {json.dumps(cit_five_items)}\n\n"
        f"=== CASE FILE SUMMARY RECORDS ===\n"
        f"{docs_text_block(case_docs)}\n\n"
        f"=== SYNCHRONIZED BIOMETRIC & TRANSCRIPT STREAM ===\n"
        f"{docs_text_block(turns)}\n\n"
        f"Emit Chair 12 JSON only."
    )

    assistant_obj = {
        "room_mode": "homicide_interview",
        "subject_state_assessment": assessment,
        "protocol_action_code": proto_code,
        "baseline_adjusted_pattern": pattern_desc,
        "cit_probe_evaluation": cit_eval,
        "turn_findings": findings,
        "innocent_physiological_alternative": innocent_alt,
        "record_cross_check_to_pull": cross_check,
        "next_room_protocol_move": next_move_text,
    }

    docs_by_id = {d["id"]: d for d in (case_docs + turns)}
    gt = {
        "room_mode": "homicide_interview",
        "population_slice": pop_slice,
        "subject_state": subject_state,
        "othello_trap": subject_state in ("OTHELLO_INNOCENT_ANXIOUS", "OTHELLO_EMBARRASSED_SECRET"),
        "cit_target_stimulus": artifact,
        "cit_orienting_hit_expected": subject_state == "CONCEALING_CASE_FACT",
        "expected_protocol_action_code": proto_code,
        "expected_subject_state_assessment": assessment,
        "expected_record_doc_ids": ["doc05", "doc09", "doc11", "doc_scene"],
        "baseline": base,
        "turn_count": len(turns),
        "docs_by_id": docs_by_id,
    }
    return user_prompt, assistant_obj, gt


def _generate_mode_b_triage(
    rng: random.Random,
    subject_state: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    names = sample_unique_names(rng, 2)
    caller_name, other_name = names
    county_a, _, corridor = rng.choice(COUNTIES)
    addr = random_address(rng)
    call_date = f"2026-{rng.randint(1, 11):02d}-{rng.randint(2, 27):02d}"

    if subject_state == "COERCED_VICTIM_FORCED_CALM":
        base = sample_biometric_baseline(rng, "OTHELLO_INNOCENT_ANXIOUS")
        pkts = [sample_biometric_turn(rng, base, "othello_panic_both_control_and_target") for _ in range(4)]
        # Enforce exact high-acuity coerced forced-calm signature (138+ BPM, ~14ms HRV, ~2.8% jitter, 26+ RPM)
        for idx, p in enumerate(pkts):
            p["biometrics"]["hr_bpm"] = round(rng.uniform(138.5, 147.8) + idx * 0.8, 1)
            p["biometrics"]["hrv_rmssd_ms"] = round(rng.uniform(12.5, 15.2), 1)
            p["biometrics"]["respiration_rpm"] = round(rng.uniform(26.0, 29.2), 1)
            p["biometrics"]["eda_sweat_uS"] = round(rng.uniform(7.4, 9.8), 2)
            p["acoustics"]["vocal_pitch_jitter_pct"] = round(rng.uniform(2.70, 3.15), 2)
            p["acoustics"]["speech_rate_wpm"] = rng.randint(108, 126)

        cad_quote = (
            f"NG911 video-assisted residential line from {addr} ({county_a}); prior CAD flag shows active stay-away order involving {other_name}."
        )
        sensor_quote = (
            "Background acoustic floor registers a low male secondary voice 1.8 meters off-axis and an interior deadbolt latch click at 00:00:19."
        )
        t1_reply = "Everything is fine here, sorry, wrong number, nobody meant to dial emergency."
        t2_reply = "Yes, uh, correct, I just meant to order a large pepperoni delivery to this apartment."
        t3_reply = "No, thank you, I have to hang up right now, everything is fine."
        t4_reply = "Uh-huh, yes, exact apartment number is 4B."

        turns = [
            _format_turn_doc("turn01", "NG911 Initial Open Line", "00:00:06", "911, what is the address of your emergency?", t1_reply, pkts[0]),
            _format_turn_doc("turn02", "Coded Yes/No Safety Probe", "00:00:18", "I hear you dialed by mistake—if someone is in the room preventing you from speaking freely, ask for pepperoni.", t2_reply, pkts[1]),
            _format_turn_doc("turn03", "Forced-Calm Dismissal Turn", "00:00:31", "Understood ma'am, confirm with yes or no whether anyone holds a weapon right now.", t3_reply, pkts[2]),
            _format_turn_doc("turn04", "Unit Confirmation Coded Turn", "00:00:44", "Before disconnecting, confirm unit 4B for our wrong-number log.", t4_reply, pkts[3]),
        ]

        proto_code = "dispatch_silent_pd_approach"
        assessment = "coerced_victim_forced_calm_vocal_autonomic_mismatch"
        pattern_desc = (
            f"Extreme verbal-autonomic divergence: caller delivers flat, monotone wrong-number dismissals in turn01 and turn03 "
            f"while video rPPG and acoustic sensors record sustained sympathetic terror (HR {pkts[0]['biometrics']['hr_bpm']} to {pkts[3]['biometrics']['hr_bpm']} BPM, "
            f"suppressed vagal HRV {pkts[1]['biometrics']['hrv_rmssd_ms']} ms, vocal micro-tremor jitter {pkts[1]['acoustics']['vocal_pitch_jitter_pct']}%, "
            f"and shallow tachypnea {pkts[1]['biometrics']['respiration_rpm']} RPM) alongside off-axis room acoustics in doc_sensor."
        )
        innocent_alt = (
            "Caller could be experiencing paroxysmal supraventricular tachycardia, an acute asthma/panic episode, or stimulant medication effects during a genuine misdial while a roommate speaks nearby."
        )
        cross_check = (
            f"Pull active protection-order details and building floorplan for {addr} Apt 4B from doc_cad and check prior responder officer-safety hazard notes."
        )
        next_move_text = (
            f"Dispatch immediate silent PD priority approach (sirens and strobes extinguished two blocks from {addr}), keep line passively open if safe without speaking aloud over speakerphone, and use strictly coded yes/no prompts."
        )
        findings = [
            {
                "doc_id": "turn01",
                "quote": t1_reply,
                "telemetry_delta": f"Forced-calm mismatch: HR {pkts[0]['biometrics']['hr_bpm']} BPM, HRV {pkts[0]['biometrics']['hrv_rmssd_ms']} ms, jitter {pkts[0]['acoustics']['vocal_pitch_jitter_pct']}%, {pkts[0]['biometrics']['respiration_rpm']} RPM.",
                "note": "Flat verbal reassurance contradicts extreme sympathetic vasoconstriction and vocal micro-tremor.",
            },
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"Coded coercion confirmation at HR {pkts[1]['biometrics']['hr_bpm']} BPM and EDA {pkts[1]['biometrics']['eda_sweat_uS']} uS.",
                "note": "Caller adopts coded pizza phrase under sustained autonomic terror.",
            },
            {
                "doc_id": "doc_cad",
                "quote": cad_quote,
                "telemetry_delta": "Premise history corroborates acute domestic coercion hazard.",
                "note": f"Active stay-away order logged at {addr}.",
            },
            {
                "doc_id": "doc_sensor",
                "quote": sensor_quote,
                "telemetry_delta": "Acoustic floor confirms second person present in room.",
                "note": "Secondary male voice and deadbolt click explain forced-flat vocal prosody.",
            },
        ]

    elif subject_state == "CALM_VOIP_SWATTING_CALLER":
        base = sample_biometric_baseline(rng, "CALM_CONCEALER")
        base["baseline_hr_bpm"] = round(rng.uniform(67.5, 72.5), 1)
        base["baseline_hrv_rmssd_ms"] = round(rng.uniform(46.0, 58.0), 1)
        pkts = [sample_biometric_turn(rng, base, "neutral_control") for _ in range(4)]
        for p in pkts:
            p["biometrics"]["hr_bpm"] = round(rng.uniform(68.0, 73.2), 1)
            p["biometrics"]["hrv_rmssd_ms"] = round(rng.uniform(45.0, 57.5), 1)
            p["biometrics"]["respiration_rpm"] = round(rng.uniform(13.0, 15.2), 1)
            p["acoustics"]["vocal_pitch_jitter_pct"] = round(rng.uniform(0.68, 0.98), 2)

        cad_quote = (
            f"Inbound call claiming address {addr} ({county_a}) routed via unverified offshore VoIP SIP relay; zero Phase-II cellular tower sector match."
        )
        sensor_quote = (
            "Acoustic channel measures -68 dBFS flat digital noise floor with zero room reverberation, zero gunshot impulse transients, and smart-home alarm at premise reports ARMED-QUIET."
        )
        t1_reply = f"Send SWAT to {addr} right now, two masked men just fired rifles in the kitchen and my father is hit!"
        t2_reply = "They are still shooting down the hallway right next to me, hurry up and breach the front door!"
        t3_reply = "Uh, I do not know whether the house is one story or two stories or what color car is in the driveway."
        t4_reply = "Just send tactical units with sirens now, stop asking me about the street corner!"

        turns = [
            _format_turn_doc("turn01", "Initial High-Severity VoIP Claim", "00:00:05", "911 emergency, state your location and what is happening.", t1_reply, pkts[0]),
            _format_turn_doc("turn02", "Active-Fire Claim vs Acoustic Check", "00:00:19", "Stay on the line—you say shots are being fired next to you right now?", t2_reply, pkts[1]),
            _format_turn_doc("turn03", "Premise Geometry Verification Probe", "00:00:34", "For staging safety, is the residence one story or two stories, and which side is the garage on?", t3_reply, pkts[2]),
            _format_turn_doc("turn04", "Callback & Landmark Check", "00:00:49", "Provide a direct callback number and name the nearest cross-street.", t4_reply, pkts[3]),
        ]

        proto_code = "run_swatting_verification_protocol"
        assessment = "unremarkable_resting_voip_swatting_pattern"
        pattern_desc = (
            f"Caller narrates active indoor rifle fire in turn01 and turn02 while maintaining a relaxed resting vagal rhythm "
            f"(HR {pkts[0]['biometrics']['hr_bpm']} to {pkts[1]['biometrics']['hr_bpm']} BPM, high vagal HRV {pkts[1]['biometrics']['hrv_rmssd_ms']} ms, "
            f"14 RPM even breathing, vocal jitter {pkts[1]['acoustics']['vocal_pitch_jitter_pct']}%), paired with a -68 dBFS dead VoIP acoustic floor "
            f"and inability to answer basic house geometry in turn03."
        )
        innocent_alt = (
            "An actual resident on beta-blocker therapy or in acute dissociative shock could call over Wi-Fi VoIP from a sound-insulated basement closet without hearing current exterior details."
        )
        cross_check = (
            f"Pull verified homeowner telephone registry, utility smart-meter motion/load telemetry, and ring/alarm subscriber callback for {addr} from doc_cad before authorizing any dynamic entry."
        )
        next_move_text = (
            f"Execute swatting verification protocol: hold blind dynamic breach, notify Patrol Supervisor of VoIP/resting-physiology swatting indicators, stage units at covered perimeter, and place immediate verification call to registered resident {caller_name}."
        )
        findings = [
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"Resting physiology during claimed adjacent gunfire: HR {pkts[1]['biometrics']['hr_bpm']} BPM, HRV {pkts[1]['biometrics']['hrv_rmssd_ms']} ms, jitter {pkts[1]['acoustics']['vocal_pitch_jitter_pct']}%.",
                "note": "Zero sympathetic startle or acoustic impulse transient while claiming shots fired next to handset.",
            },
            {
                "doc_id": "doc_cad",
                "quote": cad_quote,
                "telemetry_delta": "Non-native VoIP trunk lacks local cellular sector corroboration.",
                "note": "Matches classic remote swatting relay pattern.",
            },
            {
                "doc_id": "doc_sensor",
                "quote": sensor_quote,
                "telemetry_delta": "Dead -68 dBFS studio floor conflicts with active gunfire claim.",
                "note": "Premise alarm simultaneously reports ARMED-QUIET.",
            },
            {
                "doc_id": "turn03",
                "quote": t3_reply,
                "telemetry_delta": f"Steady {pkts[2]['biometrics']['hr_bpm']} BPM rhythm while failing basic premise description.",
                "note": "Caller cannot state story count or driveway layout of claimed family home.",
            },
        ]

    else:  # OCCULT_HEMORRHAGIC_SHOCK_VICTIM
        veh_model, veh_color, _ = rng.choice(VEHICLES)
        plate = random_plate(rng)
        base = sample_biometric_baseline(rng, "TRAUMA_WITNESS")
        pkts = [sample_biometric_turn(rng, base, "trauma_sensory_flashback") for _ in range(4)]
        hr_curve = [131.6, 135.2, 138.4, 141.8]
        temp_curve = [-0.46, -0.66, -0.80, -0.93]
        for idx, p in enumerate(pkts):
            p["biometrics"]["hr_bpm"] = round(hr_curve[idx] + rng.uniform(-0.8, 1.2), 1)
            p["biometrics"]["hrv_rmssd_ms"] = round(rng.uniform(11.4, 14.8), 1)
            p["biometrics"]["respiration_rpm"] = round(rng.uniform(24.8, 28.4), 1)
            p["biometrics"]["eda_sweat_uS"] = round(rng.uniform(6.8, 9.4), 2)
            p["biometrics"]["periorbital_temp_delta_c"] = round(temp_curve[idx] + rng.uniform(-0.04, 0.04), 2)

        cad_quote = (
            f"Patrol bodycam unit #14 on scene at {corridor} milepost 18 collision involving {veh_color} {veh_model} plate {plate}; driver {caller_name} ambulatory at guardrail."
        )
        sensor_quote = (
            "Vehicle event data recorder logs 41 mph lateral-frontal delta-V, airbag deployment, and steering-rim lower-quadrant deformation."
        )
        t1_reply = "Officer, I feel fine, just shaken up from the airbag dust, you can cancel the ambulance."
        t2_reply = "No bleeding anywhere, just a sore lap-belt mark on my left side, let me sign the refusal form so I can call a tow."
        t3_reply = "I am only a little thirsty and cold from standing in the wind, seriously I feel fine to get a ride home."
        t4_reply = "Hold on, let me lean on the fender a second, the headlights look a little dizzy."

        turns = [
            _format_turn_doc("turn01", "Bodycam Initial Roadside Contact", "00:00:22", f"{caller_name}, stay still by the guardrail—medic rescue is en route, where are you hurting?", t1_reply, pkts[0]),
            _format_turn_doc("turn02", "AMA Transport Refusal Request", "00:01:35", "The steering wheel is bent; do you have abdominal or shoulder pain?", t2_reply, pkts[1]),
            _format_turn_doc("turn03", "Progressive Compensating Tachycardia Turn", "00:02:50", "Your pulse on camera is climbing past 134 and your skin looks pale—sit down on the blanket.", t3_reply, pkts[2]),
            _format_turn_doc("turn04", "Orthostatic Presyncope Turn", "00:03:48", "Keep seated flat right here, ALS paramedics are pulling onto the shoulder now.", t4_reply, pkts[3]),
        ]

        proto_code = "upgrade_als_hemorrhagic_shock_priority"
        assessment = "occult_hemorrhagic_shock_compensating_tachycardia"
        pattern_desc = (
            f"Endorphin-masked Class II/III occult shock trajectory: driver verbally insists 'I feel fine, just shaken' in turn01–turn03 "
            f"while bodycam rPPG and thermal IR show progressive compensating tachycardia climbing from {pkts[0]['biometrics']['hr_bpm']} to {pkts[3]['biometrics']['hr_bpm']} BPM, "
            f"collapsed vagal HRV ({pkts[2]['biometrics']['hrv_rmssd_ms']} ms), tachypnea ({pkts[2]['biometrics']['respiration_rpm']} RPM), cold diaphoresis (EDA {pkts[2]['biometrics']['eda_sweat_uS']} uS), "
            f"and cutaneous vasoconstrictive cooling (periorbital temp {pkts[3]['biometrics']['periorbital_temp_delta_c']} C) alongside 41 mph steering-rim impact in doc_sensor."
        )
        innocent_alt = (
            "Acute post-collision catecholamine surge, hyperventilation, dehydration, and cold roadside wind exposure can elevate heart rate and cool facial skin without intra-abdominal hemorrhage."
        )
        cross_check = (
            f"Transmit 41 mph EDR delta-V and left-quadrant lap-belt sign from doc_sensor to incoming ALS crew for immediate bedside blood-pressure, lactate/shock-index, and trauma-center FAST triage."
        )
        next_move_text = (
            "Upgrade to urgent ALS Code-3 trauma priority immediately, place patient supine with thermal blanket, defer any AMA walk-away refusal until paramedic hemodynamic evaluation, and alert regional trauma bay of suspected occult splenic/mesenteric bleed."
        )
        findings = [
            {
                "doc_id": "turn01",
                "quote": t1_reply,
                "telemetry_delta": f"Initial compensating tachycardia HR {pkts[0]['biometrics']['hr_bpm']} BPM, temp {pkts[0]['biometrics']['periorbital_temp_delta_c']} C despite verbal reassurance.",
                "note": "Acute catecholamine analgesia masks early internal blood loss.",
            },
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"HR rises to {pkts[1]['biometrics']['hr_bpm']} BPM, HRV {pkts[1]['biometrics']['hrv_rmssd_ms']} ms, temp {pkts[1]['biometrics']['periorbital_temp_delta_c']} C.",
                "note": "Left-side lap-belt sign plus rising pulse warns against accepting AMA refusal.",
            },
            {
                "doc_id": "doc_sensor",
                "quote": sensor_quote,
                "telemetry_delta": "High-energy 41 mph mechanism corroborates blunt intra-abdominal risk.",
                "note": "Steering-rim deformation matches left upper quadrant splenic injury mechanism.",
            },
            {
                "doc_id": "turn03",
                "quote": t3_reply,
                "telemetry_delta": f"HR {pkts[2]['biometrics']['hr_bpm']} BPM, cold sweat EDA {pkts[2]['biometrics']['eda_sweat_uS']} uS, facial cooling {pkts[2]['biometrics']['periorbital_temp_delta_c']} C.",
                "note": "Thirst, pallor, and progressive thermal drop mark peripheral vasoconstriction.",
            },
        ]

    case_docs = [
        {"id": "doc_cad", "title": "NG911 / Bodycam CAD Dispatch Header", "type": "cad_record", "date": call_date, "author": "County PSAP Core", "text": cad_quote},
        {"id": "doc_sensor", "title": "Scene Acoustic & Vehicle Telemetry Log", "type": "telemetry_log", "date": call_date, "author": "Automated Field Telemetry", "text": sensor_quote},
    ]

    user_prompt = (
        f"CHAIR 12 ROOM CONSOLE — MODE: triage_911_bodycam\n"
        f"Incident Date: {call_date} | Subject/Caller: {caller_name} | Jurisdiction: {county_a}\n\n"
        f"=== DISPATCH & FIELD TELEMETRY RECORDS ===\n"
        f"{docs_text_block(case_docs)}\n\n"
        f"=== SYNCHRONIZED LIVE VOICE-STRESS & rPPG STREAM ===\n"
        f"{docs_text_block(turns)}\n\n"
        f"Emit Chair 12 JSON only."
    )

    assistant_obj = {
        "room_mode": "triage_911_bodycam",
        "subject_state_assessment": assessment,
        "protocol_action_code": proto_code,
        "baseline_adjusted_pattern": pattern_desc,
        "cit_probe_evaluation": {
            "administered": False,
            "target_stimulus": "",
            "decoy_mean_eda_uS": 0.0,
            "target_eda_uS": 0.0,
            "target_hrv_rmssd_ms": 0.0,
            "orienting_differential_observed": False,
        },
        "turn_findings": findings,
        "innocent_physiological_alternative": innocent_alt,
        "record_cross_check_to_pull": cross_check,
        "next_room_protocol_move": next_move_text,
    }

    docs_by_id = {d["id"]: d for d in (case_docs + turns)}
    gt = {
        "room_mode": "triage_911_bodycam",
        "population_slice": "TRIAGE_PHYSIOLOGY_DIVERGENCE",
        "subject_state": subject_state,
        "othello_trap": subject_state == "CALM_VOIP_SWATTING_CALLER",
        "cit_target_stimulus": None,
        "cit_orienting_hit_expected": False,
        "expected_protocol_action_code": proto_code,
        "expected_subject_state_assessment": assessment,
        "expected_record_doc_ids": ["doc_cad", "doc_sensor"],
        "baseline": base,
        "turn_count": len(turns),
        "docs_by_id": docs_by_id,
    }
    return user_prompt, assistant_obj, gt


def _generate_mode_c_aml_customs(
    rng: random.Random,
    subject_state: str,
    pop_slice: str,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    subject_name, officer_note_name = sample_unique_names(rng, 2)
    juris_city, juris_kind = rng.choice(OFFSHORE_JURISDICTIONS)
    commodity, unit_bench, unit_name, wt_kg = rng.choice(COMMODITY_BENCHMARKS)
    legit_biz, legit_sector, legit_note = rng.choice(LEGIT_BUSINESS_PROFILES)
    front_name, _, front_cap, front_note = rng.choice(CASH_FRONT_ARCHETYPES)
    insp_date = f"2026-{rng.randint(1, 11):02d}-{rng.randint(3, 27):02d}"

    use_vessel = rng.random() < 0.45
    if use_vessel:
        sampled_vessels = pick_distinct(rng, DARK_FLEET_VESSELS, 6)
        target_entity = sampled_vessels[0]
        decoy_entities = sampled_vessels[1:]
        ledger_quote = (
            f"Withheld targeting intelligence: dark-fleet vessel {target_entity} disabled AIS for 16 hours off {juris_city} "
            f"during ship-to-ship transfer tied to over-invoiced {commodity} ($18.40/{unit_name} vs ${unit_bench:.2f}/{unit_name} benchmark)."
        )
    else:
        prefixes = pick_distinct(rng, SHELL_PREFIXES, 6)
        target_entity = f"{prefixes[0]} {rng.choice(SHELL_SUFFIXES)}"
        decoy_entities = [f"{p} {rng.choice(SHELL_SUFFIXES)}" for p in prefixes[1:]]
        ledger_quote = (
            f"Withheld FinCEN targeting ledger: funnel entity {target_entity} ({juris_kind}, {juris_city}) "
            f"received $412,000 structured wires from {front_name} despite {front_note}."
        )

    target_pos = rng.randint(1, 5)  # 0-indexed -> slot 2..6 in 6-entity array
    six_entity_array = decoy_entities[:target_pos] + [target_entity] + decoy_entities[target_pos:]

    if subject_state == "CONCEALING_CASE_FACT":
        manifest_quote = (
            f"Secondary declaration signed by {subject_name} claims sole commercial affiliation with domestic broker and zero offshore shell or vessel charter authority."
        )
        travel_quote = (
            f"Corporate registry extract lists {subject_name}'s passport number as authorized signatory on two {juris_city} escrow instructions dated 11 days prior."
        )
        base = sample_biometric_baseline(rng, "CALM_CONCEALER")
        t1_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t2_pkt = sample_biometric_turn(rng, base, "general_accusation_calm_liar")
        t3_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t4_pkt = sample_biometric_turn(rng, base, "cit_guilty_knowledge_hit")
        t5_pkt = sample_biometric_turn(rng, base, "cognitive_load_reverse_order")

        t2_reply = f"I only handle domestic freight paperwork for {commodity}; I have never dealt with any {juris_city} entities or charter vessels."
        t4_reply = f"No, I have never heard of {target_entity}, none of those six names mean anything to me."
        t5_reply = f"Working backward from final wire settlement—uh, wait—the customs broker paid the warehouse directly, I cannot recall which bank cleared the bill of lading."

        turns = [
            _format_turn_doc("turn01", "Calibration Control — Passport & Domestic Occupation", "00:01:04", f"State your full name and declared commercial role for calibration.", f"My name is {subject_name}, independent freight documentation agent.", t1_pkt),
            _format_turn_doc("turn02", "Broad Offshore Affiliation Denial", "00:02:42", f"Have you signed instructions for any {juris_city} accounts or non-declared maritime charters?", t2_reply, t2_pkt),
            _format_turn_doc("turn03", "6-Entity CIT Array — 5 Synthetic Decoy Entities", "00:04:30", f"Review and answer no to each unfamiliar entity: {', '.join(decoy_entities)}.", "No to all five, I have never transacted with any of those.", t3_pkt),
            _format_turn_doc("turn04", f"6-Entity CIT Array — Position #{target_pos + 1} Withheld Ledger Target", "00:05:22", f"Entity {target_pos + 1} in the inspection array: {target_entity}.", t4_reply, t4_pkt),
            _format_turn_doc("turn05", "Reverse-Order Invoice & Settlement Chain Prompt", "00:07:10", f"Trace the last {commodity} shipment backward from wire settlement to dock scale ticket.", t5_reply, t5_pkt),
        ]

        proto_code = "ask_reverse_order_timeline_step"
        assessment = "stimulus_locked_cit_and_cognitive_load"
        pattern_desc = (
            f"Subject stayed near calm baseline (HR {base['baseline_hr_bpm']} BPM, HRV {base['baseline_hrv_rmssd_ms']} ms, EDA {base['baseline_eda_uS']} uS) "
            f"on broad offshore questioning in turn02 (HR {t2_pkt['biometrics']['hr_bpm']} BPM) and across all five synthetic decoys in turn03 (EDA {t3_pkt['biometrics']['eda_sweat_uS']} uS), "
            f"then exhibited a sharp stimulus-locked orienting shift exclusively on withheld ledger entity '{target_entity}' in turn04 "
            f"(HRV {t4_pkt['biometrics']['hrv_rmssd_ms']} ms, phasic EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS, pupil +{t4_pkt['biometrics']['pupil_dilation_delta_mm']} mm) "
            f"and a reverse-accounting latency spike ({t5_pkt['acoustics']['response_latency_ms']} ms) in turn05."
        )
        innocent_alt = (
            f"{subject_name} may have encountered the name '{target_entity}' passively on an industry freight circular or clerical template without knowing its beneficial owners, "
            f"or passport credentials in doc_travel could reflect unauthorized identity misuse by a third-party formation agent."
        )
        cross_check = (
            f"Pull FinCEN BOI wet-signature/IP filing metadata for {target_entity}, SWIFT MT103 originator logs from doc_ledger, "
            f"and port weighbridge tickets for the {wt_kg} kg {commodity} consignment."
        )
        next_move_text = (
            f"Hold direct accusation on '{target_entity}'; ask {subject_name} in reverse chronological order to name each freight forwarder, escrow bank, and notary used over the past 14 days while verifying passport signatory IP logs."
        )
        findings = [
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"Calm broad denial: HR {t2_pkt['biometrics']['hr_bpm']} BPM, latency {t2_pkt['acoustics']['response_latency_ms']} ms.",
                "note": "Broad compliance question elicits minimal physiological shift.",
            },
            {
                "doc_id": "turn04",
                "quote": t4_reply,
                "telemetry_delta": f"Stimulus-locked CIT hit: EDA {t4_pkt['biometrics']['eda_sweat_uS']} vs {t3_pkt['biometrics']['eda_sweat_uS']} uS decoys; HRV {t4_pkt['biometrics']['hrv_rmssd_ms']} ms; pupil +{t4_pkt['biometrics']['pupil_dilation_delta_mm']} mm.",
                "note": "Isolated orienting recognition on withheld targeting ledger entity.",
            },
            {
                "doc_id": "doc_travel",
                "quote": travel_quote,
                "telemetry_delta": "Registry passport link conflicts with turn02 offshore denial.",
                "note": f"Places passport number on {juris_city} escrow instructions.",
            },
            {
                "doc_id": "turn05",
                "quote": t5_reply,
                "telemetry_delta": f"Cognitive-load latency {t5_pkt['acoustics']['response_latency_ms']} ms vs {base['baseline_latency_ms']} ms baseline; {t5_pkt['acoustics']['speech_rate_wpm']} wpm.",
                "note": "Backward settlement reconstruction exposes missing clearing-bank step.",
            },
        ]
        cit_eval = {
            "administered": True,
            "target_stimulus": target_entity,
            "decoy_mean_eda_uS": t3_pkt["biometrics"]["eda_sweat_uS"],
            "target_eda_uS": t4_pkt["biometrics"]["eda_sweat_uS"],
            "target_hrv_rmssd_ms": t4_pkt["biometrics"]["hrv_rmssd_ms"],
            "orienting_differential_observed": True,
        }

    elif subject_state == "OTHELLO_INNOCENT_ANXIOUS":
        manifest_quote = (
            f"Commercial entry packet for {legit_biz} ({legit_sector}) shows {legit_note}."
        )
        travel_quote = (
            f"Passenger {subject_name} referred to secondary booth after kiosk name-collision alert with unrelated watchlist DOB; tight 55-minute connecting flight."
        )
        base = sample_biometric_baseline(rng, "OTHELLO_INNOCENT_ANXIOUS")
        t1_pkt = sample_biometric_turn(rng, base, "othello_panic_both_control_and_target")
        t2_pkt = sample_biometric_turn(rng, base, "othello_panic_both_control_and_target")
        t3_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t4_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t5_pkt = sample_biometric_turn(rng, base, "othello_panic_both_control_and_target")

        t1_reply = f"I am {subject_name} with {legit_biz}—please, why was I pulled into secondary, my connecting gate closes in forty minutes!"
        t4_reply = f"No, I have never heard of {target_entity}, we only buy domestic equipment for {legit_biz}."

        turns = [
            _format_turn_doc("turn01", "Calibration Control — Traveler Identity & Employer", "00:00:55", "Confirm your full name, employer, and onward flight.", t1_reply, t1_pkt),
            _format_turn_doc("turn02", "General Wire & Cargo Inquiry", "00:02:15", f"Explain the equipment wire listed on {legit_biz}'s commercial invoice.", f"That wire is our {legit_sector} purchase—all invoices and bank liens are in my folder!", t2_pkt),
            _format_turn_doc("turn03", "6-Entity CIT Array — 5 Synthetic Decoy Entities", "00:03:55", f"State yes or no if you recognize any of these entities: {', '.join(decoy_entities)}.", "No, none of those companies at all.", t3_pkt),
            _format_turn_doc("turn04", f"6-Entity CIT Array — Position #{target_pos + 1} Withheld Ledger Target", "00:04:48", f"Entity {target_pos + 1}: {target_entity}.", t4_reply, t4_pkt),
            _format_turn_doc("turn05", "Reverse-Order Procurement Check", "00:06:10", "Walk backward from today's trip to your bank loan closing.", f"Today I flew in from regional hub, Tuesday our local bank wired escrow, and last month we signed the {legit_sector} order.", t5_pkt),
        ]

        proto_code = "hold_confrontation_and_calibrate_baseline"
        assessment = "generalized_othello_arousal_non_specific"
        pattern_desc = (
            f"Othello-law border anxiety: traveler exhibits elevated HR ({t1_pkt['biometrics']['hr_bpm']} BPM) and tonic EDA ({t1_pkt['biometrics']['eda_sweat_uS']} uS) "
            f"from the very first neutral control in turn01 as well as turn02 ({t2_pkt['biometrics']['hr_bpm']} BPM), "
            f"with zero differential orienting response on withheld target '{target_entity}' in turn04 (EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS) "
            f"relative to the five synthetic decoys in turn03 (EDA {t3_pkt['biometrics']['eda_sweat_uS']} uS)."
        )
        innocent_alt = (
            f"Acute secondary-inspection detention stress and fear of missing a 55-minute flight connection drive generalized sympathetic tachycardia and palmar sweat in an innocent traveler triggered by a kiosk DOB name collision."
        )
        cross_check = (
            f"Verify passport DOB mismatch against the watchlist record in doc_travel and confirm {legit_biz}'s verified invoice packet in doc_manifest to release traveler promptly."
        )
        next_move_text = (
            f"Hold all AML confrontation, calm traveler to re-stabilize baseline, resolve the doc_travel name-collision alert against DOB/passport number, and clear {subject_name} for onward travel."
        )
        findings = [
            {
                "doc_id": "turn01",
                "quote": t1_reply,
                "telemetry_delta": f"High control-turn arousal: HR {t1_pkt['biometrics']['hr_bpm']} BPM, EDA {t1_pkt['biometrics']['eda_sweat_uS']} uS on routine identity check.",
                "note": "Generalized border-booth anxiety present before any compliance probe.",
            },
            {
                "doc_id": "turn04",
                "quote": t4_reply,
                "telemetry_delta": f"Zero CIT differential: target EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS vs decoy {t3_pkt['biometrics']['eda_sweat_uS']} uS.",
                "note": "No recognition of withheld cartel/dark-fleet target entity.",
            },
            {
                "doc_id": "doc_manifest",
                "quote": manifest_quote,
                "telemetry_delta": "Corroborates legitimate commercial wire purpose.",
                "note": f"Documented {legit_sector} backing matches traveler account.",
            },
            {
                "doc_id": "doc_travel",
                "quote": travel_quote,
                "telemetry_delta": "Explains secondary referral as name collision plus flight time pressure.",
                "note": "Unrelated watchlist DOB collision accounts for kiosk referral.",
            },
        ]
        cit_eval = {
            "administered": True,
            "target_stimulus": target_entity,
            "decoy_mean_eda_uS": t3_pkt["biometrics"]["eda_sweat_uS"],
            "target_eda_uS": t4_pkt["biometrics"]["eda_sweat_uS"],
            "target_hrv_rmssd_ms": t4_pkt["biometrics"]["hrv_rmssd_ms"],
            "orienting_differential_observed": False,
        }

    elif subject_state == "OTHELLO_EMBARRASSED_SECRET":
        sec_item, sec_reason, sec_record = rng.choice(EMBARRASSED_PERSONAL_SECRETS_AML)
        manifest_quote = (
            f"Baggage X-ray and secondary declaration for {subject_name} ({legit_biz}) note {sec_item}; commercial business ledger clean."
        )
        travel_quote = (
            f"Customs lane referral logged {subject_name} arriving from regional hub with zero FinCEN SAR hits on {legit_biz}."
        )
        base = sample_biometric_baseline(rng, "CALM_CONCEALER")
        t1_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t2_pkt = sample_biometric_turn(rng, base, "embarrassed_unrelated_secret")
        t3_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t4_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t5_pkt = sample_biometric_turn(rng, base, "neutral_control")

        t2_reply = f"Look, I was embarrassed because of {sec_item}—I was {sec_reason}, it has nothing to do with company cargo."
        t4_reply = f"No, I have never heard of {target_entity}, I have zero dealings with offshore shells or vessels."

        turns = [
            _format_turn_doc("turn01", "Calibration Control — Passport & Employer", "00:01:00", "State your name and company position for baseline calibration.", f"I am {subject_name}, operations manager at {legit_biz}.", t1_pkt),
            _format_turn_doc("turn02", "Personal Declaration Discrepancy Question", "00:02:28", f"Secondary screening flagged {sec_item}; explain why it was omitted.", t2_reply, t2_pkt),
            _format_turn_doc("turn03", "6-Entity CIT Array — 5 Synthetic Decoy Entities", "00:04:12", f"Answer no to each unfamiliar entity: {', '.join(decoy_entities)}.", "No to all five names.", t3_pkt),
            _format_turn_doc("turn04", f"6-Entity CIT Array — Position #{target_pos + 1} Withheld Ledger Target", "00:05:01", f"Entity {target_pos + 1}: {target_entity}.", t4_reply, t4_pkt),
            _format_turn_doc("turn05", "Reverse-Order Itinerary Check", "00:06:22", "Trace backward your last 48 hours of travel stops.", f"Airport lounge at noon, hotel checkout at 9:00 AM, and {legit_biz} client dinner last night.", t5_pkt),
        ]

        proto_code = "hold_confrontation_and_verify_via_record"
        assessment = "unrelated_personal_secret_cit_negative"
        pattern_desc = (
            f"Baseline-adjusted telemetry isolates an embarrassment blush and phasic sweat response strictly to turn02 regarding {sec_item} "
            f"(periorbital temp +{t2_pkt['biometrics']['periorbital_temp_delta_c']} C, EDA {t2_pkt['biometrics']['eda_sweat_uS']} uS, HR {t2_pkt['biometrics']['hr_bpm']} BPM), "
            f"while all six entities in the cartel/TBML CIT array—including withheld target '{target_entity}' in turn04 "
            f"(EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS vs decoy {t3_pkt['biometrics']['eda_sweat_uS']} uS; HRV {t4_pkt['biometrics']['hrv_rmssd_ms']} ms)—remain completely flat."
        )
        innocent_alt = (
            f"Personal embarrassment over {sec_reason} drives acute facial warming and electrodermal reactivity on personal-declaration questions without any knowledge of {target_entity}."
        )
        cross_check = (
            f"Inspect the {sec_record} and confirm zero FinCEN/OFAC nexus on {legit_biz} in doc_travel so minor customs duty/administrative handling stays separate from AML targeting."
        )
        next_move_text = (
            f"Hold all AML/cartel confrontation; process only routine administrative verification of the {sec_record} and clear {subject_name} on the negative 6-entity CIT probe."
        )
        findings = [
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"Personal-embarrassment spike: temp +{t2_pkt['biometrics']['periorbital_temp_delta_c']} C, EDA {t2_pkt['biometrics']['eda_sweat_uS']} uS.",
                "note": "Arousal explained by disclosed personal matter in doc_manifest.",
            },
            {
                "doc_id": "turn04",
                "quote": t4_reply,
                "telemetry_delta": f"Flat CIT target: EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS vs {t3_pkt['biometrics']['eda_sweat_uS']} uS decoys.",
                "note": "Zero orienting recognition on withheld funnel/vessel entity.",
            },
            {
                "doc_id": "doc_manifest",
                "quote": manifest_quote,
                "telemetry_delta": "Matches disclosed personal item with clean business ledger.",
                "note": "Confirms anomaly is confined to personal baggage/declaration.",
            },
            {
                "doc_id": "doc_travel",
                "quote": travel_quote,
                "telemetry_delta": "Corroborates absence of SAR hits on employer.",
                "note": "Supports administrative resolution rather than criminal AML escalation.",
            },
        ]
        cit_eval = {
            "administered": True,
            "target_stimulus": target_entity,
            "decoy_mean_eda_uS": t3_pkt["biometrics"]["eda_sweat_uS"],
            "target_eda_uS": t4_pkt["biometrics"]["eda_sweat_uS"],
            "target_hrv_rmssd_ms": t4_pkt["biometrics"]["hrv_rmssd_ms"],
            "orienting_differential_observed": False,
        }

    else:  # TRAUMA_COOPERATIVE_WITNESS
        manifest_quote = (
            f"Voluntary compliance disclosure filed by shipping clerk {subject_name} handing over altered {commodity} weight certificates."
        )
        travel_quote = (
            f"Port police intake log notes {subject_name} requested protective secondary booth escort after {officer_note_name} threatened dock staff."
        )
        base = sample_biometric_baseline(rng, "TRAUMA_WITNESS")
        t1_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t2_pkt = sample_biometric_turn(rng, base, "trauma_sensory_flashback")
        t3_pkt = sample_biometric_turn(rng, base, "neutral_control")
        t4_pkt = sample_biometric_turn(rng, base, "trauma_sensory_flashback")

        t2_reply = (
            f"When {officer_note_name} cornered me by container bay 9 and told me to swap the {commodity} scale sheet, my hands shook so badly I photographed the manifest and ran to the customs booth."
        )
        t4_reply = (
            f"He banged on my car window at the port gate and said he knew where my sister lived—I brought every USB invoice copy I had."
        )

        turns = [
            _format_turn_doc("turn01", "Calibration Control — Protected Booth Intake", "00:01:06", f"You are in a secure customs booth, {subject_name}; confirm your dock clerk badge role.", f"I am {subject_name}, manifest clerk at terminal pier 4.", t1_pkt),
            _format_turn_doc("turn02", "Voluntary Coercion & Altered Manifest Account", "00:02:45", "In your own pace, describe how the altered weight certificate reached your desk.", t2_reply, t2_pkt),
            _format_turn_doc("turn03", "Supportive Grounding & Document Receipt Check", "00:04:30", "Take a breath—we have logged your USB drive into custody; were you alone in the clerk booth before that?", "Yes, my shift relief does not arrive until 8:00 PM.", t3_pkt),
            _format_turn_doc("turn04", "Gate Intimidation Sensory Recall Turn", "00:06:05", "Share whatever details you recall from the port gate encounter without rushing.", t4_reply, t4_pkt),
        ]

        proto_code = "switch_to_peace_supportive_open_recall"
        assessment = "trauma_recall_sympathetic_surge"
        pattern_desc = (
            f"Cooperative whistleblower exhibits trauma-linked sympathetic waves when recalling workplace intimidation in turn02 "
            f"(HR {t2_pkt['biometrics']['hr_bpm']} BPM, resp {t2_pkt['biometrics']['respiration_rpm']} RPM, jitter {t2_pkt['acoustics']['vocal_pitch_jitter_pct']}%) "
            f"and turn04 (HR {t4_pkt['biometrics']['hr_bpm']} BPM, EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS), "
            f"while returning toward baseline ({t3_pkt['biometrics']['hr_bpm']} BPM) during supportive grounding in turn03 and aligning with doc_manifest and doc_travel."
        )
        innocent_alt = (
            f"Acute fear and duress recollection after direct physical intimidation at the port gate drive sympathetic tachycardia and vocal tremor in a truthful cooperating witness."
        )
        cross_check = (
            f"Pull pier-4 container bay 9 and port-gate CCTV around shift change, hash-verify the surrendered USB weight certificates from doc_manifest, and cross-link against {target_entity} in doc_ledger."
        )
        next_move_text = (
            f"Switch to supportive PEACE Cognitive Interview open-ended recall in a protected witness room, avoid adversarial cross-examination or CIT stress probes, and coordinate witness-safety escort while verifying USB invoices."
        )
        findings = [
            {
                "doc_id": "turn02",
                "quote": t2_reply,
                "telemetry_delta": f"Duress recall surge: HR {t2_pkt['biometrics']['hr_bpm']} BPM, resp {t2_pkt['biometrics']['respiration_rpm']} RPM, jitter {t2_pkt['acoustics']['vocal_pitch_jitter_pct']}%.",
                "note": "Autonomic surge accompanies voluntary disclosure of coerced manifest swap.",
            },
            {
                "doc_id": "doc_manifest",
                "quote": manifest_quote,
                "telemetry_delta": "Corroborates proactive surrender of documentary evidence.",
                "note": "Witness initiated disclosure and turned over altered certificates.",
            },
            {
                "doc_id": "doc_travel",
                "quote": travel_quote,
                "telemetry_delta": "Confirms protective escort request following dock threat.",
                "note": "Aligns with acute fear physiology observed in turn02 and turn04.",
            },
            {
                "doc_id": "turn04",
                "quote": t4_reply,
                "telemetry_delta": f"Threat flashback spike: HR {t4_pkt['biometrics']['hr_bpm']} BPM, EDA {t4_pkt['biometrics']['eda_sweat_uS']} uS.",
                "note": "Requires trauma-informed PEACE open recall and witness protection coordination.",
            },
        ]
        cit_eval = {
            "administered": False,
            "target_stimulus": target_entity,
            "decoy_mean_eda_uS": 0.0,
            "target_eda_uS": 0.0,
            "target_hrv_rmssd_ms": 0.0,
            "orienting_differential_observed": False,
        }

    case_docs = [
        {"id": "doc_ledger", "title": "Withheld FinCEN / Maritime Targeting Ledger", "type": "aml_ledger", "date": insp_date, "author": "FinCEN / Customs Targeting Desk", "text": ledger_quote},
        {"id": "doc_manifest", "title": "Secondary Inspection Declaration & Cargo Extract", "type": "customs_manifest", "date": insp_date, "author": "Port Secondary Inspection", "text": manifest_quote},
        {"id": "doc_travel", "title": "Crossing & Registry Metadata Log", "type": "registry_log", "date": insp_date, "author": "Border Crossing System", "text": travel_quote},
    ]

    user_prompt = (
        f"CHAIR 12 ROOM CONSOLE — MODE: aml_customs_secondary\n"
        f"Inspection Date: {insp_date} | Subject: {subject_name} | 6-Entity CIT Array: {json.dumps(six_entity_array)}\n\n"
        f"=== TARGETING LEDGER & MANIFEST SUMMARY ===\n"
        f"{docs_text_block(case_docs)}\n\n"
        f"=== SYNCHRONIZED BIOMETRIC & TRANSCRIPT STREAM ===\n"
        f"{docs_text_block(turns)}\n\n"
        f"Emit Chair 12 JSON only."
    )

    assistant_obj = {
        "room_mode": "aml_customs_secondary",
        "subject_state_assessment": assessment,
        "protocol_action_code": proto_code,
        "baseline_adjusted_pattern": pattern_desc,
        "cit_probe_evaluation": cit_eval,
        "turn_findings": findings,
        "innocent_physiological_alternative": innocent_alt,
        "record_cross_check_to_pull": cross_check,
        "next_room_protocol_move": next_move_text,
    }

    docs_by_id = {d["id"]: d for d in (case_docs + turns)}
    gt = {
        "room_mode": "aml_customs_secondary",
        "population_slice": pop_slice,
        "subject_state": subject_state,
        "othello_trap": subject_state in ("OTHELLO_INNOCENT_ANXIOUS", "OTHELLO_EMBARRASSED_SECRET"),
        "cit_target_stimulus": target_entity,
        "cit_orienting_hit_expected": subject_state == "CONCEALING_CASE_FACT",
        "expected_protocol_action_code": proto_code,
        "expected_subject_state_assessment": assessment,
        "expected_record_doc_ids": ["doc_ledger", "doc_manifest", "doc_travel"],
        "baseline": base,
        "turn_count": len(turns),
        "docs_by_id": docs_by_id,
    }
    return user_prompt, assistant_obj, gt


def validate_interrogation_room_example(example: dict[str, Any]) -> None:
    """Validate biological bounds, verbatim quote grounding, Othello rules, and prohibited phrases."""
    required_top = ("id", "track", "domain", "subtask", "split", "messages", "ground_truth")
    for k in required_top:
        if k not in example:
            raise ValueError(f"Missing top-level key '{k}'")

    if example["track"] != TRACK_NAME:
        raise ValueError(f"Invalid track: {example['track']}")
    if example["domain"] != DOMAIN_NAME:
        raise ValueError(f"Invalid domain: {example['domain']}")

    gt = example["ground_truth"]
    expected_subtask = f"{gt['room_mode']}_{gt['subject_state']}"
    if example["subtask"] != expected_subtask:
        raise ValueError(f"Subtask '{example['subtask']}' != '{expected_subtask}'")

    msgs = example["messages"]
    if len(msgs) != 3 or [m["role"] for m in msgs] != ["system", "user", "assistant"]:
        raise ValueError("messages must be [system, user, assistant]")

    user_text = msgs[1]["content"]
    assistant_raw = msgs[2]["content"]
    payload = json.loads(assistant_raw)

    # 1. Required Chair 12 output fields
    for field in (
        "baseline_adjusted_pattern",
        "innocent_physiological_alternative",
        "record_cross_check_to_pull",
        "next_room_protocol_move",
        "protocol_action_code",
        "subject_state_assessment",
    ):
        val = str(payload.get(field, "")).strip()
        if not val:
            raise ValueError(f"Empty required output field '{field}'")

    if len(payload["innocent_physiological_alternative"].strip()) <= 15:
        raise ValueError("innocent_physiological_alternative must exceed 15 characters")

    if payload["protocol_action_code"] not in VALID_PROTOCOL_CODES:
        raise ValueError(f"Unknown protocol_action_code: {payload['protocol_action_code']}")

    # 2. Zero prohibited polygraph / guilt phrases
    low_out = norm_ws(assistant_raw)
    for banned in PROHIBITED_GUILT_PHRASES:
        if norm_ws(banned) in low_out:
            raise ValueError(f"Prohibited phrase '{banned}' detected in assistant output")
    veto_hits = check_prosecutor_vetoes(assistant_raw, [])
    if veto_hits:
        raise ValueError(f"Prosecutor veto violation: {veto_hits}")

    # 3. Biological bounds across every turn in docs_by_id
    docs_by_id: dict[str, dict[str, Any]] = gt["docs_by_id"]
    turn_docs = [d for d in docs_by_id.values() if d.get("type") == "room_telemetry_turn"]
    if not (4 <= len(turn_docs) <= 6):
        raise ValueError(f"Expected 4..6 room turns, got {len(turn_docs)}")

    for td in turn_docs:
        b = td["biometrics"]
        a = td["acoustics"]
        if not (45.0 <= b["hr_bpm"] <= 180.0 and 45.0 <= b["baseline_hr_bpm"] <= 150.0):
            raise ValueError(f"HR out of biological bounds in {td['id']}: {b}")
        if not (8.0 <= b["hrv_rmssd_ms"] <= 100.0 and 8.0 <= b["baseline_hrv_rmssd_ms"] <= 100.0):
            raise ValueError(f"HRV RMSSD out of biological bounds in {td['id']}: {b}")
        if not (0.3 <= b["eda_sweat_uS"] <= 24.0 and 0.3 <= b["baseline_eda_uS"] <= 18.0):
            raise ValueError(f"EDA out of biological bounds in {td['id']}: {b}")
        if not (7.0 <= b["respiration_rpm"] <= 38.0):
            raise ValueError(f"Respiration out of biological bounds in {td['id']}: {b}")
        if not (-1.8 <= b["periorbital_temp_delta_c"] <= 1.8):
            raise ValueError(f"Periorbital temp delta out of bounds in {td['id']}: {b}")
        if not (-0.4 <= b["pupil_dilation_delta_mm"] <= 2.2):
            raise ValueError(f"Pupil dilation delta out of bounds in {td['id']}: {b}")
        if not (180 <= a["response_latency_ms"] <= 6000 and 300 <= a["baseline_latency_ms"] <= 1500):
            raise ValueError(f"Response latency out of bounds in {td['id']}: {a}")
        if not (60 <= a["speech_rate_wpm"] <= 220):
            raise ValueError(f"Speech rate out of bounds in {td['id']}: {a}")
        if not (0.2 <= a["vocal_pitch_jitter_pct"] <= 6.0):
            raise ValueError(f"Vocal pitch jitter out of bounds in {td['id']}: {a}")

    # 4. Verbatim quote grounding against room transcript & case summary
    findings = payload.get("turn_findings", [])
    if len(findings) < 3:
        raise ValueError("Expected at least 3 verbatim-grounded turn_findings")
    for f in findings:
        doc_id = f.get("doc_id", "")
        quote = f.get("quote", "")
        if not quote_ok(quote, doc_id, docs_by_id):
            raise ValueError(f"Quote verification failed for doc_id='{doc_id}': {quote!r}")
        if norm_ws(quote) not in norm_ws(user_text):
            raise ValueError(f"Quote missing from user prompt text: {quote!r}")

    # 5. Othello & Trauma protocol alignment
    state = gt["subject_state"]
    if state in ("OTHELLO_INNOCENT_ANXIOUS", "OTHELLO_EMBARRASSED_SECRET"):
        if payload["cit_probe_evaluation"]["orienting_differential_observed"] is not False:
            raise ValueError("Othello control must NOT report CIT orienting differential")
        if not payload["protocol_action_code"].startswith("hold_confrontation"):
            raise ValueError(f"Othello control must hold confrontation, got {payload['protocol_action_code']}")
    elif state == "TRAUMA_COOPERATIVE_WITNESS":
        if payload["protocol_action_code"] != "switch_to_peace_supportive_open_recall":
            raise ValueError("Trauma cooperative witness must switch to PEACE open recall")
    elif state == "CONCEALING_CASE_FACT":
        if payload["cit_probe_evaluation"]["orienting_differential_observed"] is not True:
            raise ValueError("Concealing CIT hit must report orienting_differential_observed=True")


def generate_interrogation_room_example(
    split: str,
    index: int,
    salt: str = "mb-spec7-v1",
) -> dict[str, Any]:
    """Generate one deterministic, verified Track 2 Chair-12 training example."""
    rng = make_rng(split, DOMAIN_NAME, index, salt)
    room_mode, pop_slice, subject_state = _select_schedule(split, index)

    if room_mode == "homicide_interview":
        user_prompt, assistant_obj, gt = _generate_mode_a_homicide(rng, subject_state, pop_slice)
    elif room_mode == "triage_911_bodycam":
        user_prompt, assistant_obj, gt = _generate_mode_b_triage(rng, subject_state)
    else:
        user_prompt, assistant_obj, gt = _generate_mode_c_aml_customs(rng, subject_state, pop_slice)

    example = {
        "id": f"t2_room_{split}_{index:06d}",
        "track": TRACK_NAME,
        "domain": DOMAIN_NAME,
        "subtask": f"{room_mode}_{subject_state}",
        "split": split,
        "messages": [
            {"role": "system", "content": load_room_copilot_prompt()},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)},
        ],
        "ground_truth": gt,
    }
    validate_interrogation_room_example(example)
    return example


def generate_interrogation_room_batch(
    split: str,
    count: int,
    start_index: int = 0,
    salt: str = "mb-spec7-v1",
) -> list[dict[str, Any]]:
    """Generate a validated batch of Track 2 room co-pilot examples."""
    return [
        generate_interrogation_room_example(split=split, index=start_index + i, salt=salt)
        for i in range(count)
    ]


if __name__ == "__main__":
    from collections import Counter

    splits = (("train", 160), ("val", 80), ("test", 60))
    examples: list[dict[str, Any]] = []
    for sp, n in splits:
        examples.extend(generate_interrogation_room_batch(sp, n))

    modes = Counter(e["ground_truth"]["room_mode"] for e in examples)
    hom_aml_rows = [
        e for e in examples
        if e["ground_truth"]["room_mode"] in ("homicide_interview", "aml_customs_secondary")
    ]
    slices = Counter(e["ground_truth"]["population_slice"] for e in hom_aml_rows)
    substates = Counter(e["ground_truth"]["subject_state"] for e in hom_aml_rows)
    print(f"Verified {len(examples)} Track 2 examples (100% pass).")
    print("Room modes:", dict(modes))
    print("Homicide+AML slices:", {k: f"{100 * v / len(hom_aml_rows):.1f}%" for k, v in slices.items()})
    print("Homicide+AML substates:", {k: f"{100 * v / len(hom_aml_rows):.1f}%" for k, v in substates.items()})

