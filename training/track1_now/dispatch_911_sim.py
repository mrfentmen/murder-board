"""Track 1 Simulator: 911 Panicked-Call & Coerced-Caller Triage Co-Pilot (SPEC 7).

Implements 21 distinct high-stakes 911 sub-archetypes across 6 major classes:
  1. COERCED_CALLER (5 ruses: pepperoni pizza, hair salon confirm, wrong-number water
     utility bill, rideshare ETA ruse, bilingual code-switch 'wrong auntie' call)
  2. MEDICAL_CRITICAL (6 traps: cardiac agonal gasps mistaken for 'weird snoring',
     fentanyl M-30 respiratory arrest + Narcan query, acute stroke Last-Known-Well NPO,
     toddler complete airway choking vs. barky croup stridor, severe arterial femoral bleed
     high-and-tight tourniquet, anaphylactic airway swelling + EpiPen thigh check)
  3. UNKNOWN_LOCATION_PANIC (3 sub-cases: submerging ditch SUV milepost projection +
     hydrostatic window escape, young child caller school/landmark + WPH2 triangulation,
     trunk abduction highway exit turns & rumble-strip sector counting)
  4. MULTI_HAZARD_CHAOS (3 sub-cases: 13.8kV energized downed wire over truck hood
     step-potential trap, multi-occupant winter furnace Carbon Monoxide poisoning,
     multi-caller 3-story apartment fire with conflicting trapped-tenant floor accounts)
  5. SILENT_OR_OPEN_LINE (2 sub-cases: confirmed duress via double-DTMF taps + whispered
     'help' vs. benign grocery/laundromat pocket-dial requiring SMS/callback check)
  6. SWATTING_OR_FALSE_REPORT (2 sub-cases: non-native VOIP + dead acoustics/keyboard clicks
     claiming '3rd-floor attic/basement hostages' or 'sub-basement pipe bombs' at a verified
     1-story slab ranch -> stage & verify without blind dynamic breach or hanging up)

Generates BOTH:
  - Single-turn real-time triage (70%)
  - Multi-turn streaming CAD escalation trajectories (30%)

Enforces verbatim `evidence_quotes` verified via `quote_ok()` against CAD/transcript
records, mandatory `innocent_alternative`, zero Prosecutor veto violations, and strict
`len(next_dispatcher_line.split()) <= 18` on every assistant turn.
"""

from __future__ import annotations

import json
import random
from typing import Any

from training.common import (
    COUNTIES,
    VEHICLES,
    check_prosecutor_vetoes,
    fmt_clock,
    make_rng,
    quote_ok,
    random_address,
    random_plate,
    sample_unique_names,
)

SYSTEM_PROMPT_911 = """You are a Real-Time 911 Emergency Triage & Coerced-Caller Dispatch Co-Pilot.
Work strictly from the verified CAD header (ANI/ALI telemetry, premise history) and live streaming call transcript:
1. Detect disguised or coerced callers (pizza, salon, utility, rideshare, or bilingual 'wrong auntie' ruses, or intentional DTMF keypad taps) -> set coercion_detected=true, silent_approach_required=true, and ask ONLY closed yes/no or keypad DTMF prompts so an assailant overhearing the line is not alerted.
2. Catch deadly life-safety traps callers misdescribe (agonal gasps mistaken for 'weird snoring', M-30 opioid apnea, stroke Last-Known-Well NPO window, complete pediatric choking vs. barky croup stridor, arterial femoral hemorrhage, anaphylaxis EpiPen thigh delivery, submerging SUV hydrostatic window lock, 13.8kV downed-wire step potential, odorless carbon monoxide, and VOIP swatting architecture mismatches).
3. Ground every finding in exact verbatim substrings (`evidence_quotes`) from `CAD_HEADER` or `TRANSCRIPT`, include a neutral `innocent_alternative` where ambiguity exists, and never declare guilt.
4. Keep `next_dispatcher_line` calm, protocol-exact, and strictly <= 18 words on every turn.

Respond with a concise <triage>...</triage> reasoning block followed by a single valid JSON dispatch packet."""

USER_PROMPTS_SINGLE = (
    "Triage this active 911 stream immediately. Output <triage> reasoning and the structured JSON CAD dispatch packet.",
    "Live PSAP console feed attached. Identify hidden hazards or coercion, cite verbatim CAD/transcript quotes, and emit <triage> + JSON.",
    "Evaluate ANI/ALI telemetry and caller audio below. Flag life-safety traps, assign units/priority, and provide a <=18-word next_dispatcher_line.",
)

USER_PROMPTS_MULTI_OPEN = (
    "INITIAL STREAMING INTAKE (T+04s): Triage partial caller statement, cite verbatim quotes, and issue a <=18-word diagnostic probe.",
    "LIVE CAD STREAM OPENED: Provide provisional triage packet and exact <=18-word question to resolve the critical life-safety unknown.",
)

USER_PROMPTS_MULTI_UPDATE = (
    "LIVE STREAM UPDATE (T+14s): Caller and acoustic telemetry updated below. Re-evaluate priority, units, and issue next <=18-word instruction.",
    "CAD & AUDIO ESCALATION FEED: Incorporate new transcript lines and CAD premise return. Emit updated <triage> + JSON dispatch packet.",
)

MAJOR_ARCHETYPES = (
    "COERCED_CALLER",
    "MEDICAL_CRITICAL",
    "UNKNOWN_LOCATION_PANIC",
    "MULTI_HAZARD_CHAOS",
    "SILENT_OR_OPEN_LINE",
    "SWATTING_OR_FALSE_REPORT",
)

SUB_ARCHETYPE_CATALOG: tuple[tuple[str, str], ...] = (
    # 1. COERCED_CALLER (5 ruses)
    ("COERCED_CALLER", "coerced_pepperoni_pizza_ruse"),
    ("COERCED_CALLER", "coerced_hair_salon_confirm"),
    ("COERCED_CALLER", "coerced_water_utility_wrong_number"),
    ("COERCED_CALLER", "coerced_rideshare_eta_ruse"),
    ("COERCED_CALLER", "coerced_bilingual_wrong_auntie"),
    # 2. MEDICAL_CRITICAL (6 traps)
    ("MEDICAL_CRITICAL", "cardiac_arrest_agonal_snoring_trap"),
    ("MEDICAL_CRITICAL", "fentanyl_m30_apnea_narcan"),
    ("MEDICAL_CRITICAL", "acute_stroke_lkw_npo_window"),
    ("MEDICAL_CRITICAL", "toddler_complete_airway_choking"),
    ("MEDICAL_CRITICAL", "pediatric_barky_croup_stridor"),
    ("MEDICAL_CRITICAL", "arterial_femoral_bleed_tourniquet"),
    ("MEDICAL_CRITICAL", "anaphylaxis_airway_epipen_thigh"),
    # 3. UNKNOWN_LOCATION_PANIC (3 sub-cases)
    ("UNKNOWN_LOCATION_PANIC", "submerging_ditch_suv_hydrostatic"),
    ("UNKNOWN_LOCATION_PANIC", "child_caller_school_landmark_wph2"),
    ("UNKNOWN_LOCATION_PANIC", "trunk_abduction_turns_rumble_sectors"),
    # 4. MULTI_HAZARD_CHAOS (3 sub-cases)
    ("MULTI_HAZARD_CHAOS", "downed_13_8kv_wire_step_potential"),
    ("MULTI_HAZARD_CHAOS", "winter_furnace_carbon_monoxide"),
    ("MULTI_HAZARD_CHAOS", "apartment_fire_conflicting_floors"),
    # 5. SILENT_OR_OPEN_LINE (2 sub-cases)
    ("SILENT_OR_OPEN_LINE", "silent_duress_double_dtmf"),
    ("SILENT_OR_OPEN_LINE", "benign_pocket_dial_retail_laundromat"),
    # 6. SWATTING_OR_FALSE_REPORT (2 sub-cases)
    ("SWATTING_OR_FALSE_REPORT", "voip_swatting_3rd_floor_attic_on_ranch"),
    ("SWATTING_OR_FALSE_REPORT", "voip_swatting_basement_bombs_on_slab"),
)


def _pick_sub_archetype(rng: random.Random) -> tuple[str, str]:
    roll = rng.random()
    if roll < 0.24:
        major = "COERCED_CALLER"
    elif roll < 0.52:
        major = "MEDICAL_CRITICAL"
    elif roll < 0.68:
        major = "UNKNOWN_LOCATION_PANIC"
    elif roll < 0.82:
        major = "MULTI_HAZARD_CHAOS"
    elif roll < 0.91:
        major = "SILENT_OR_OPEN_LINE"
    else:
        major = "SWATTING_OR_FALSE_REPORT"
    candidates = [pair for pair in SUB_ARCHETYPE_CATALOG if pair[0] == major]
    return rng.choice(candidates)


def _build_scenario(
    rng: random.Random,
    archetype: str,
    sub_archetype: str,
    call_id: str,
    call_time: str,
    county: str,
    corridor: str,
) -> dict[str, Any]:
    names = sample_unique_names(rng, 3)
    caller_name, other_name = names[0], names[1]
    addr = random_address(rng)
    apt = f"{rng.randint(1, 8)}{rng.choice('ABCD')}"
    lat = round(rng.uniform(33.1500, 42.8500), 5)
    lon = round(rng.uniform(-118.4000, -75.2000), 5)
    radius_m = rng.randint(12, 38)
    veh_model, veh_color, _ = rng.choice(VEHICLES)
    plate = random_plate(rng)

    # ------------------------------------------------------------------
    # 1. COERCED CALLER (5 distinct ruses)
    # ------------------------------------------------------------------
    if sub_archetype == "coerced_pepperoni_pizza_ruse":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 (Phase II Wireless) | EST COORDS: {lat}, {lon} (+/- {radius_m}m)\n"
            f"PREMISE HISTORY ({addr}): 1 prior domestic disturbance report (7 mos ago)."
        )
        tr_t1 = f"[00:02] CALLER: Hi, yeah, I need a large pepperoni pizza delivered to {addr}, Apt {apt}, right away please."
        q1_cad = f"1 prior domestic disturbance report"
        q1_tr = f"large pepperoni pizza delivered to {addr}, Apt {apt}"
        probe_line = "Ma'am, you reached 911. Do you have an emergency right now?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:10] CALLER: Yeah, extra cheese please, hurry, he gets furious waiting. [BG: male voice: 'Put the phone down now!']\n"
            f"[00:15] CALLER: No, please don't slice it—he already has a big butcher knife out right here."
        )
        q2_tr = "he already has a big butcher knife out right here"
        final_line = "Police are coming silently. Say 'yes' if anyone is bleeding right now."
        traps = ["coerced_caller_pizza_order_ruse", "speakerphone_overhear_risk", "edged_weapon_present"]
        units_t1 = ["PD_PATROL_UNIT"]
        units_final = ["PD_PATROL_TWO_UNIT", "PD_SUPERVISOR", "STAGE_BLS_NEARBY"]
        prio_t1 = "P2_BRAVO"
        prio_final = "P1_DELTA"
        pre_t1 = "Possible coded distress call at WPH2 premise with domestic history; probe with closed yes/no question."
        pre_final = f"SILENT APPROACH REQUIRED (lights/sirens OFF final block) to {addr} Apt {apt}; edged weapon reported in room. Closed yes/no or DTMF prompts only."
        inno = "Caller could have misdialed 911 while attempting to place a food order, though deliberate apartment disclosure and background threat strongly indicate coercion."

    elif sub_archetype == "coerced_hair_salon_confirm":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m near {addr})\n"
            f"PREMISE HISTORY ({addr}): Prior protective-order service logged 5 months ago."
        )
        tr_t1 = f"[00:02] CALLER: Hi salon desk, I'm calling to confirm my trim at {addr}, Unit {apt}, as soon as possible."
        q1_cad = "Prior protective-order service logged 5 months ago"
        q1_tr = f"confirm my trim at {addr}, Unit {apt}"
        probe_line = "This is 911 emergency. Are you unable to speak freely right now?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:11] CALLER: Uh-huh, right now works great. Please don't knock loud, the baby's sleeping. [BG: glass shattering]\n"
            f"[00:16] CALLER: Yeah, bring clips—he still has his black pistol case open on the table."
        )
        q2_tr = "still has his black pistol case open on the table"
        final_line = "Help is coming with sirens off. Press 1 if the gun is loaded."
        traps = ["coerced_caller_hair_salon_ruse", "firearm_handgun_risk", "silent_approach_requested_by_code"]
        units_t1 = ["PD_PATROL_UNIT"]
        units_final = ["PD_PATROL_TWO_UNIT", "PD_SUPERVISOR", "STAGE_ALS_MEDIC"]
        prio_t1 = "P2_BRAVO"
        prio_final = "P1_DELTA"
        pre_t1 = "Suspected salon-appointment ruse matching protective-order address; test with closed yes/no question."
        pre_final = f"SILENT APPROACH REQUIRED to {addr} Unit {apt}; handgun case open in room, infant on scene. Maintain closed yes/no or keypad tone communication."
        inno = "Caller may have misdialed while checking an appointment, though supplying her own residential unit and 'don't knock loud' matches coded duress."

    elif sub_archetype == "coerced_water_utility_wrong_number":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m)\n"
            f"PREMISE HISTORY ({addr}): 2 prior welfare-check dispatches this year."
        )
        tr_t1 = f"[00:02] CALLER: Sorry, is this municipal water billing for {addr}, Apt {apt}? Our water bill looks wrong."
        q1_cad = "2 prior welfare-check dispatches this year"
        q1_tr = f"municipal water billing for {addr}, Apt {apt}"
        probe_line = "This is county 911. Do you need police sent to that address?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:10] CALLER: Yes ma'am, that's the exact service address, please send a tech quick. [BG: shouting: 'Who is on speaker?!']\n"
            f"[00:15] CALLER: Nothing is leaking except my split lip—I mean the sink pipe."
        )
        q2_tr = "Nothing is leaking except my split lip"
        final_line = "Officers are rolling silently now. Press 1 if he blocked the door."
        traps = ["coerced_caller_utility_bill_ruse", "active_speakerphone_monitoring", "assault_injury_disclosed"]
        units_t1 = ["PD_PATROL_UNIT"]
        units_final = ["PD_PATROL_TWO_UNIT", "PD_SUPERVISOR", "STAGE_BLS_NEARBY"]
        prio_t1 = "P2_BRAVO"
        prio_final = "P1_DELTA"
        pre_t1 = "Possible utility-bill ruse at address with prior welfare checks; verify safely with yes/no prompt."
        pre_final = f"SILENT APPROACH REQUIRED to {addr} Apt {apt}; caller on speakerphone with injured lip. Use keypad DTMF prompts only."
        inno = "Caller could be confused dialing municipal directory numbers, though affirmative reply after 'This is county 911' indicates intentional duress signaling."

    elif sub_archetype == "coerced_rideshare_eta_ruse":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m parked along {corridor})\n"
            f"PREMISE HISTORY: Commercial strip lot along {addr}."
        )
        tr_t1 = f"[00:02] CALLER: Hey driver, are you still two minutes from {addr} in the {veh_color} {veh_model}, plate {plate}?"
        q1_cad = f"EST COORDS: {lat}, {lon}"
        q1_tr = f"{veh_color} {veh_model}, plate {plate}"
        probe_line = "You called 911. Are you unsafe inside that vehicle right now?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:10] CALLER: Yep, that's right, we're parked behind {addr} right now, he locked the child-locks. [BG: male: 'Stop texting your sister!']\n"
            f"[00:15] CALLER: Yeah, just pull up quiet without flashing brights so we don't miss you."
        )
        q2_tr = "parked behind {addr} right now, he locked the child-locks".format(addr=addr)
        final_line = "Units are approaching dark. Tap the keypad twice if we are moving."
        traps = ["coerced_caller_rideshare_eta_ruse", "unlawful_restraint_child_locks", "vehicle_flight_risk"]
        units_t1 = ["PD_PATROL_UNIT"]
        units_final = ["PD_PATROL_TWO_UNIT", "PD_SUPERVISOR", "HIGHWAY_INTERCEPT"]
        prio_t1 = "P2_BRAVO"
        prio_final = "P1_DELTA"
        pre_t1 = f"Caller reading vehicle description ({veh_color} {veh_model}, {plate}) to 911 as rideshare ruse; confirm threat via closed yes/no."
        pre_final = f"SILENT APPROACH REQUIRED behind {addr}; target vehicle {veh_color} {veh_model} plate {plate} with doors child-locked. Block exit silently; closed/DTMF prompts only."
        inno = "Caller might have tapped emergency SOS instead of rideshare contact, though explicit child-lock and plate readout confirms deliberate rescue signal."

    elif sub_archetype == "coerced_bilingual_wrong_auntie":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m)\n"
            f"PREMISE HISTORY ({addr}): 1 domestic battery call 4 months ago."
        )
        tr_t1 = f"[00:02] CALLER: Hola Tia, perdón, left my sweater at {addr} Apt {apt}—ayuda por favor, don't hang up."
        q1_cad = "1 domestic battery call 4 months ago"
        q1_tr = f"left my sweater at {addr} Apt {apt}—ayuda por favor"
        probe_line = "This is 911. Say 'si' or 'yes' if someone is threatening you."
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:10] CALLER: Sí Tia, exacto, right here in the kitchen. [BG: chair slammed, male yelling in English: 'Hang up on her!']\n"
            f"[00:15] CALLER: No traigas ruido Tia—tiene un bate de metal by the door."
        )
        q2_tr = "No traigas ruido Tia—tiene un bate de metal"
        final_line = "Policia viene en silencio. Say 'si' if the front door is unlocked."
        traps = ["coerced_bilingual_code_switch_ruse", "blunt_weapon_metal_bat", "assailant_monolingual_english_overhear"]
        units_t1 = ["PD_PATROL_UNIT"]
        units_final = ["PD_PATROL_TWO_UNIT", "PD_BILINGUAL_OFFICER", "STAGE_BLS_NEARBY"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_DELTA"
        pre_t1 = "Caller embedding Spanish 'ayuda por favor' inside English/Spanish 'wrong auntie' ruse; respond with closed yes/no prompt."
        pre_final = f"SILENT APPROACH REQUIRED ('no traigas ruido') to {addr} Apt {apt}; subject armed with metal bat ('bate de metal') by door. Keep closed bilingual yes/si prompts."
        inno = "Code-switching can occur naturally in family calls, but pairing 'ayuda por favor' and 'tiene un bate de metal' after 911 identification establishes active coercion."

    # ------------------------------------------------------------------
    # 2. MEDICAL_CRITICAL (6 life-safety traps)
    # ------------------------------------------------------------------
    elif sub_archetype == "cardiac_arrest_agonal_snoring_trap":
        age = rng.randint(49, 74)
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: RESIDENTIAL_E911 | REGISTERED ADDR: {addr}\n"
            f"PREMISE HISTORY ({addr}): Cardiac history note on senior registry."
        )
        tr_t1 = f"[00:01] CALLER ({caller_name}): Send help to {addr}! My {age}-year-old husband collapsed off the couch and is snoring super loud!"
        q1_cad = f"REGISTERED ADDR: {addr}"
        q1_tr = f"collapsed off the couch and is snoring super loud"
        probe_line = "Can you wake him up? Count seconds between each breath right now."
        tr_t2_extra = (
            f"[00:05] DISPATCH: {probe_line}\n"
            f"[00:11] CALLER: No! His eyes are rolled back and he only makes a weird snorting gasp every 8 seconds! [BG: raspy agonal gasp]"
        )
        q2_tr = "weird snorting gasp every 8 seconds"
        final_line = "Gasping is cardiac arrest. Lay him flat; push hard, fast center-chest now."
        traps = ["agonal_gasps_mistaken_for_snoring", "immediate_hands_only_cpr_required"]
        units_t1 = ["ALS_MEDIC"]
        units_final = ["ALS_MEDIC", "ENGINE_FIRST_RESPONDER", "AED_POLICE_UNIT"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_ECHO"
        pre_t1 = "Unresponsive collapse with 'loud snoring'; immediately rule out agonal gasps of sudden cardiac arrest."
        pre_final = f"CONFIRMED AGONAL BREATHING / CARDIAC ARREST ({age}yo M at {addr}). Coach hands-only CPR at 100-120 compressions/min on hard floor until AED arrival."
        inno = "Post-ictal seizure recovery or deep sleep can cause loud stertorous breathing, but unresponsive collapse with 8-second gasps must be treated as cardiac arrest."

    elif sub_archetype == "fentanyl_m30_apnea_narcan":
        age = rng.randint(19, 39)
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m — {addr})\n"
            f"PREMISE HISTORY ({addr}): None."
        )
        tr_t1 = f"[00:02] CALLER: Hurry to {addr} Apt {apt}! My {age}-year-old brother is slumped on the bathroom floor and won't wake up!"
        q1_cad = f"EST COORDS: {lat}, {lon}"
        q1_tr = f"slumped on the bathroom floor and won't wake up"
        probe_line = "Is his chest rising, and do you see pills, foil, or Narcan?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:11] CALLER: His lips are blue-gray, barely one breath in twenty seconds! There's foil and half a blue M-30 pill on the vanity!"
        )
        q2_tr = "blue-gray, barely one breath in twenty seconds! There's foil and half a blue M-30 pill"
        final_line = "Do you have Narcan? Spray one nostril now, then tilt his head back."
        traps = ["fentanyl_m30_opioid_respiratory_arrest", "naloxone_query_and_airway_head_tilt"]
        units_t1 = ["ALS_MEDIC"]
        units_final = ["ALS_MEDIC", "PD_NARCAN_FIRST_RESPONDER", "ENGINE_BLS"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_ECHO"
        pre_t1 = "Unresponsive young adult in bathroom; check respiratory rate and screen for opioid/Narcan availability."
        pre_final = f"SUSPECTED FENTANYL M-30 OVERDOSE APNEA at {addr} Apt {apt}. Query/coach intranasal Naloxone (Narcan) immediately + rescue breathing / CPR."
        inno = "Hypoglycemia or syncope can cause bathroom unresponsiveness, but cyanosis, <3 breaths/min, and pressed M-30 tablet warrant immediate Naloxone and airway support."

    elif sub_archetype == "acute_stroke_lkw_npo_window":
        age = rng.randint(56, 83)
        lkw_mins_ago = rng.choice([12, 18, 25, 35])
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: RESIDENTIAL_E911 | REGISTERED ADDR: {addr}\n"
            f"PREMISE HISTORY ({addr}): None."
        )
        tr_t1 = f"[00:02] CALLER ({caller_name}): Please send an ambulance to {addr}, my {age}-year-old mother dropped her mug and looks confused!"
        q1_cad = f"REGISTERED ADDR: {addr}"
        q1_tr = f"dropped her mug and looks confused"
        probe_line = "Is her face drooping, does one arm drift, and when was she normal?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:12] CALLER: Left face is drooping, her left arm drops down, speech is slurred! She was talking fine {lkw_mins_ago} minutes ago—should I give aspirin and water?"
        )
        q2_tr = f"talking fine {lkw_mins_ago} minutes ago—should I give aspirin and water"
        final_line = "No food, water, or aspirin! Keep her propped up; stroke medics are coming."
        traps = ["acute_stroke_last_known_well_capture", "strict_npo_no_aspirin_before_ct_scan"]
        units_t1 = ["BLS_AMBULANCE"]
        units_final = ["ALS_STROKE_MEDIC", "ENGINE_FIRST_RESPONDER"]
        prio_t1 = "P2_BRAVO"
        prio_final = "P1_DELTA"
        pre_t1 = "Sudden unilateral weakness/confusion; run FAST stroke screen and establish exact Last-Known-Well time."
        pre_final = f"STROKE ALERT at {addr}: FAST-positive, Last-Known-Well = {lkw_mins_ago} min prior to {call_time}. STRICT NPO (aspiration risk & hemorrhagic stroke contraindication to aspirin prior to CT)."
        inno = "Bell's palsy or transient hypoglycemia can mimic facial droop, so EMS glucose check and hospital CT remain mandatory before antithrombotic therapy."

    elif sub_archetype == "toddler_complete_airway_choking":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m — {addr})\n"
            f"PREMISE HISTORY ({addr}): Single-family residence."
        )
        tr_t1 = f"[00:01] CALLER: Help at {addr}! My 2-year-old son was eating whole grapes and suddenly grabbed his throat!"
        q1_cad = "Single-family residence"
        q1_tr = "2-year-old son was eating whole grapes and suddenly grabbed his throat"
        probe_line = "Can he cry, cough, or make any sound at all right now?"
        tr_t2_extra = (
            f"[00:05] DISPATCH: {probe_line}\n"
            f"[00:09] CALLER: No sound at all! Mouth is wide open, zero air moving, his lips are turning dusky blue!"
        )
        q2_tr = "No sound at all! Mouth is wide open, zero air moving"
        final_line = "Give 5 firm back slaps between shoulder blades, then 5 chest thrusts now!"
        traps = ["complete_pediatric_airway_obstruction", "silent_cyanosis_back_slaps_and_thrusts", "no_blind_finger_sweep"]
        units_t1 = ["ALS_MEDIC"]
        units_final = ["ALS_PEDIATRIC_MEDIC", "ENGINE_FIRST_RESPONDER"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_ECHO"
        pre_t1 = "Toddler acute choking onset while eating grapes; differentiate silent complete obstruction vs. vocalizing cough/stridor."
        pre_final = f"COMPLETE AIRWAY OBSTRUCTION (2yo M at {addr}): silent, cyanotic. Coach alternating 5 back slaps / 5 abdominal-or-chest thrusts; NO blind finger sweeps."
        inno = "Brief gagging with effective coughing would warrant observation only, whereas silent open-mouth cyanosis confirms complete foreign-body obstruction."

    elif sub_archetype == "pediatric_barky_croup_stridor":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m — {addr})\n"
            f"PREMISE HISTORY ({addr}): Single-family residence."
        )
        tr_t1 = f"[00:01] CALLER: Help at {addr}! My 2-year-old woke up from a nap gasping loud like he's choking!"
        q1_cad = "Single-family residence"
        q1_tr = "2-year-old woke up from a nap gasping loud like he's choking"
        probe_line = "Was he eating anything, or is he making a loud barky cough?"
        tr_t2_extra = (
            f"[00:05] DISPATCH: {probe_line}\n"
            f"[00:10] CALLER: Nothing in his mouth, low fever all day—he has a loud seal-bark cough and high squeaky whistle breathing in! [BG: barky croup cough, inspiratory stridor]"
        )
        q2_tr = "loud seal-bark cough and high squeaky whistle breathing in"
        final_line = "Do not put fingers in his mouth. Hold him upright and calm him."
        traps = ["barky_croup_stridor_at_rest_differential", "avoid_agitation_and_blind_mouth_probing"]
        units_t1 = ["ALS_MEDIC"]
        units_final = ["ALS_PEDIATRIC_MEDIC", "ENGINE_BLS"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_DELTA"
        pre_t1 = "Toddler acute respiratory distress from sleep; distinguish foreign-body choking from viral croup / airway swelling."
        pre_final = f"PEDIATRIC STRIDOR AT REST / SEVERE CROUP (2yo M at {addr}): febrile prodrome + barky seal cough + inspiratory stridor. Keep child calm upright; avoid oral probing or forceful abdominal thrusts."
        inno = "Unwitnessed toy aspiration remains on the differential until EMS auscultation, so ALS transport is required while avoiding airway-spasm agitation."

    elif sub_archetype == "arterial_femoral_bleed_tourniquet":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: COMMERCIAL_E911 | REGISTERED ADDR: {addr}\n"
            f"PREMISE HISTORY ({addr}): Woodworking & metal fabrication shop."
        )
        tr_t1 = f"[00:01] CALLER: Ambulance to {addr}! A circular saw kicked back into my coworker's upper inner thigh—blood is everywhere!"
        q1_cad = "Woodworking & metal fabrication shop"
        q1_tr = "circular saw kicked back into my coworker's upper inner thigh"
        probe_line = "Is bright red blood spurting, and do you have a trauma tourniquet?"
        tr_t2_extra = (
            f"[00:05] DISPATCH: {probe_line}\n"
            f"[00:10] CALLER: Yes, bright red blood is pulsing straight through two shop towels and he's turning pale gray! We have a CAT tourniquet on the wall kit!"
        )
        q2_tr = "bright red blood is pulsing straight through two shop towels"
        final_line = "Strap the tourniquet high and tight above the cut; twist until bleeding stops."
        traps = ["pulsatile_femoral_arterial_hemorrhage", "high_and_tight_windlass_tourniquet_never_loosen"]
        units_t1 = ["ALS_MEDIC"]
        units_final = ["ALS_TRAUMA_MEDIC", "PD_TOURNIQUET_UNIT", "ENGINE_FIRST_RESPONDER"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_ECHO"
        pre_t1 = "Severe proximal thigh laceration; check for pulsatile arterial hemorrhage and commercial tourniquet availability."
        pre_final = f"EXSANGUINATING FEMORAL ARTERIAL BLEED at {addr}. Coach CAT windlass tourniquet HIGH AND TIGHT proximal to wound (or deep wound packing + full body-weight direct pressure if junctional); log application time, NEVER loosen."
        inno = "Venous oozing normally responds to direct towel pressure alone, whereas bright red pulsatile spurting soaked through dressings indicates arterial transection."

    elif sub_archetype == "anaphylaxis_airway_epipen_thigh":
        age = rng.randint(14, 46)
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m — {addr})\n"
            f"PREMISE HISTORY ({addr}): Neighborhood restaurant patio."
        )
        tr_t1 = f"[00:02] CALLER: Need EMS at {addr}! My {age}-year-old sister broke out in hives right after eating Thai noodles!"
        q1_cad = "Neighborhood restaurant patio"
        q1_tr = "broke out in hives right after eating Thai noodles"
        probe_line = "Is her tongue or throat swelling, or is she having trouble breathing?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:11] CALLER: Yes! Her lips and tongue are huge, she's wheezing hard and dizzy, and she has an EpiPen in her purse!"
        )
        q2_tr = "lips and tongue are huge, she's wheezing hard and dizzy, and she has an EpiPen"
        final_line = "Press the EpiPen firmly into her outer mid-thigh now and hold 3 seconds."
        traps = ["anaphylactic_airway_edema_and_shock", "epipen_outer_thigh_autoinjector_immediate"]
        units_t1 = ["BLS_AMBULANCE"]
        units_final = ["ALS_MEDIC", "ENGINE_FIRST_RESPONDER"]
        prio_t1 = "P2_BRAVO"
        prio_final = "P1_ECHO"
        pre_t1 = "Acute post-meal urticaria; immediately screen for multisystem anaphylaxis (airway angioedema, wheezing, hypotension)."
        pre_final = f"ACUTE ANAPHYLAXIS WITH AIRWAY COMPROMISE at {addr}. Coach immediate intramuscular EpiPen into outer mid-thigh (through clothing OK); do NOT wait for antihistamines; prepare second dose if unimproved in 5 min."
        inno = "Isolated cutaneous hives without respiratory or hemodynamic symptoms could be mild urticaria, but tongue edema + wheezing + dizziness confirms life-threatening anaphylaxis."

    # ------------------------------------------------------------------
    # 3. UNKNOWN_LOCATION_PANIC (3 triangulation / physics sub-cases)
    # ------------------------------------------------------------------
    elif sub_archetype == "submerging_ditch_suv_hydrostatic":
        mile_exit = rng.randint(22, 88)
        mins_since = rng.choice([2, 3, 4])
        dir_travel = rng.choice(["northbound", "southbound", "eastbound", "westbound"])
        delta_mi = round(mins_since * 1.05)
        proj_mm = mile_exit + delta_mi if dir_travel in ("northbound", "eastbound") else mile_exit - delta_mi
        wide_r = rng.randint(190, 410)
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {wide_r}m along {corridor})\n"
            f"PREMISE HISTORY: Unlit drainage canal paralleling {corridor}."
        )
        tr_t1 = f"[00:02] CALLER: Help! Our SUV hydroplaned off {corridor} into deep water and we don't know where we are!"
        q1_cad = f"EST COORDS: {lat}, {lon} (+/- {wide_r}m along {corridor})"
        q1_tr = f"SUV hydroplaned off {corridor} into deep water"
        probe_line = "Which direction on the highway, last exit passed, and is water entering?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:11] CALLER: Going {dir_travel}, passed Milepost {mile_exit} about {mins_since} minutes ago! Water is up to the dashboard and the doors won't push open! [BG: rushing water]"
        )
        q2_tr = f"passed Milepost {mile_exit} about {mins_since} minutes ago! Water is up to the dashboard"
        final_line = "Unbuckle seatbelts now, open or break a side window, and get onto roof!"
        traps = ["submerging_vehicle_hydrostatic_door_lock", "milepost_time_distance_projection"]
        units_t1 = ["HIGHWAY_PATROL", "FIRE_RESCUE_ENGINE"]
        units_final = ["FIRE_SWIFTWATER_RESCUE", "ALS_MEDIC", "HIGHWAY_PATROL"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_ECHO"
        pre_t1 = "Vehicle in flooded canal with wide WPH2 radius; get direction + last milepost and check water intrusion immediately."
        pre_final = f"SUBMERGING VEHICLE on {corridor} {dir_travel} projected ~Milepost {proj_mm} (Milepost {mile_exit} + {mins_since} min @ ~60 mph, matching WPH2 +/-{wide_r}m). Coach SWOC: Seatbelts off, Side Windows open/broken BEFORE electronics fail, Out onto roof."
        inno = "Shallow roadside puddle stalls pose no drowning threat, but dashboard-deep rising water creates hydrostatic door lock within 30-60 seconds."
        addr = f"{corridor} {dir_travel} approx Milepost {proj_mm}"

    elif sub_archetype == "child_caller_school_landmark_wph2":
        wide_r = rng.randint(85, 195)
        apt_color = rng.choice(["red brick", "yellow stucco", "tan siding"])
        school_name = f"{ county.split()[0] } Elementary"
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {wide_r}m; GIS polygon contains {addr} across from {school_name})\n"
            f"PREMISE HISTORY: Multi-building garden apartments at {addr}."
        )
        tr_t1 = f"[00:02] CALLER (young child, ~6yo): Mommy fell down on the kitchen floor and she won't talk to me! I don't know my street number!"
        q1_cad = f"GIS polygon contains {addr} across from {school_name}"
        q1_tr = "Mommy fell down on the kitchen floor and she won't talk to me"
        probe_line = "You're doing great, buddy. Look out the window—what building or school is outside?"
        tr_t2_extra = (
            f"[00:07] DISPATCH: {probe_line}\n"
            f"[00:13] CALLER: I see {school_name} playground and a big blue mailbox! Our door has number {apt} on the {apt_color} building! Mommy's chest is moving up and down."
        )
        q2_tr = f"I see {school_name} playground and a big blue mailbox! Our door has number {apt}"
        final_line = "Helpers are coming fast! Unlock the front door for me and stay by Mommy."
        traps = ["pediatric_caller_landmark_gis_triangulation", "verify_parent_breathing_and_unlock_access"]
        units_t1 = ["ALS_MEDIC", "PD_PATROL_UNIT"]
        units_final = ["ALS_MEDIC", "ENGINE_FIRST_RESPONDER", "PD_WELFARE_ENTRY"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_DELTA"
        pre_t1 = "6yo child caller with unresponsive parent inside WPH2 polygon; use calm child-friendly landmark prompts to pinpoint building/unit."
        pre_final = f"TRIANGULATED CHILD CALLER LOCATION: {addr} ({apt_color} building across from {school_name} / USPS blue box), Unit {apt}. Parent breathing; instruct child to unlock front door without leaving apartment."
        inno = "Parent may have fainted briefly (vasovagal syncope or hypoglycemia) rather than cardiac arrest since chest rise is present, but immediate ALS entry is essential."
        addr = f"{addr}, {apt_color} Bldg Unit {apt} (opp. {school_name})"

    elif sub_archetype == "trunk_abduction_turns_rumble_sectors":
        hwy_speed_mins = rng.randint(6, 11)
        sector_az = rng.choice([45, 135, 225, 310])
        wide_r = rng.randint(240, 520)
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2_MOVING_HANDOFF | TOWER SECTOR: {sector_az} deg along {corridor} (+/- {wide_r}m)\n"
            f"PREMISE HISTORY: Cell handoff progressing rapidly along {corridor}."
        )
        tr_t1 = f"[00:02] CALLER (whispering): [BG: loud road tire roar] Please whisper—a man forced me into the trunk of a {veh_color} {veh_model}!"
        q1_cad = f"TOWER SECTOR: {sector_az} deg along {corridor}"
        q1_tr = f"forced me into the trunk of a {veh_color} {veh_model}"
        probe_line = "Keep whispering. Tap once for yes: did you feel highway speed or turns?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:12] CALLER (whispering): [DTMF TONE: '1'] Drove fast {hwy_speed_mins} minutes, crossed bridge expansion joints, then slowed right over rumble strips onto a gravel road!"
        )
        q2_tr = f"crossed bridge expansion joints, then slowed right over rumble strips onto a gravel road"
        final_line = "Troopers are tracking your phone silently. Pull the glowing trunk release only when stopped."
        traps = ["moving_abduction_cell_handoff_acoustic_dead_reckoning", "silent_highway_intercept_no_sirens", "glow_in_dark_trunk_release_safety"]
        units_t1 = ["HIGHWAY_PATROL", "PD_SUPERVISOR"]
        units_final = ["HIGHWAY_PATROL_INTERCEPT", "PD_SUPERVISOR", "AVIATION_FLIR_UNIT", "STAGE_ALS_MEDIC"]
        prio_t1 = "P1_ECHO"
        prio_final = "P1_ECHO"
        pre_t1 = "Active trunk kidnapping moving on cell sector; preserve whisper/DTMF stealth and gather acoustic dead-reckoning cues (bridges, exits, surface)."
        pre_final = f"ACTIVE ABDUCTION IN {veh_color.upper()} {veh_model.upper()} exiting {corridor} (Sector {sector_az} deg +/-{wide_r}m) after bridge joints + exit rumble strips onto gravel turnoff. Continuous ALI re-bid every 15s; SILENT INTERCEPT."
        inno = "Prank calls from moving vehicles rarely match progressive multi-tower WPH2 handoffs plus whispered road-noise physics; treat as Priority-1 abduction."
        addr = f"{corridor} Sector {sector_az} deg gravel exit post-bridge ({lat}, {lon} +/-{wide_r}m)"

    # ------------------------------------------------------------------
    # 4. MULTI_HAZARD_CHAOS (3 physical / multi-caller hazards)
    # ------------------------------------------------------------------
    elif sub_archetype == "downed_13_8kv_wire_step_potential":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m near {addr})\n"
            f"PREMISE HISTORY ({addr}): Overhead 13.8kV three-phase utility primary feeder."
        )
        tr_t1 = f"[00:02] CALLER: A {veh_color} pickup just sheared a power pole at {addr} and wires are draped across the hood!"
        q1_cad = "Overhead 13.8kV three-phase utility primary feeder"
        q1_tr = f"sheared a power pole at {addr} and wires are draped across the hood"
        probe_line = "Stay far back! Is the truck on fire, and is the driver inside?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:11] CALLER: No fire or smoke, driver's awake pushing his door open onto wet asphalt—I'm running up to help him out! [BG: electrical arcing buzz]"
        )
        q2_tr = "No fire or smoke, driver's awake pushing his door open onto wet asphalt"
        final_line = "STOP! Stay 35 feet back and yell for him to stay inside!"
        traps = ["energized_13_8kv_step_and_touch_potential", "stay_inside_faraday_cab_unless_active_fire"]
        units_t1 = ["FIRE_RESCUE_ENGINE", "UTILITY_EMERGENCY_SHUTOFF"]
        units_final = ["FIRE_RESCUE_ENGINE", "UTILITY_EMERGENCY_SHUTOFF", "ALS_MEDIC", "PD_TRAFFIC_PERIMETER"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_ECHO"
        pre_t1 = "Vehicle vs. 13.8kV utility pole with wires on hood; assess fire status and halt bystander approach."
        pre_final = f"LIVE 13.8kV WIRE ON VEHICLE at {addr} (NO FIRE). Deadly step/touch potential on wet asphalt: keep bystanders >=35 ft away; occupant MUST STAY INSIDE cab until utility de-energizes (bunny-hop feet together ONLY if cab catches fire)."
        inno = "Telecom/cable lines on lower crossarms carry low voltage, but audible arcing buzz beneath a 13.8kV feeder must be treated as lethal primary voltage."

    elif sub_archetype == "winter_furnace_carbon_monoxide":
        temp_f = rng.randint(14, 29)
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: RESIDENTIAL_E911 | REGISTERED ADDR: {addr}\n"
            f"PREMISE HISTORY ({addr}): Gas-heated duplex; ambient weather {temp_f}F freezing."
        )
        tr_t1 = f"[00:02] CALLER ({caller_name}): Send an ambulance to {addr}—my wife, two kids, and I all woke up dizzy with pounding headaches and nausea!"
        q1_cad = f"Gas-heated duplex; ambient weather {temp_f}F freezing"
        q1_tr = "wife, two kids, and I all woke up dizzy with pounding headaches and nausea"
        probe_line = "Did symptoms start together indoors with the heater running? Any detector chirping?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:12] CALLER: Yeah, our gas furnace has been cycling nonstop all night, our dog can barely stand up, and I don't smell any gas at all!"
        )
        q2_tr = "gas furnace has been cycling nonstop all night, our dog can barely stand up"
        final_line = "Carbon monoxide has no smell! Get everyone and pets outside into fresh air now!"
        traps = ["acute_odorless_carbon_monoxide_mass_poisoning", "odorless_gas_misconception_immediate_evacuation"]
        units_t1 = ["BLS_AMBULANCE", "FIRE_HAZMAT_ENGINE"]
        units_final = ["FIRE_HAZMAT_CO_MONITOR", "ALS_MULTI_PATIENT_MEDIC", "GAS_UTILITY_EMERGENCY"]
        prio_t1 = "P1_DELTA"
        prio_final = "P1_ECHO"
        pre_t1 = "Simultaneous whole-household winter headache/dizziness/nausea; suspect acute Carbon Monoxide exposure."
        pre_final = f"PROBABLE ACUTE CARBON MONOXIDE POISONING (4 humans + pet symptomatic at {addr}, {temp_f}F, gas furnace running). CO is completely odorless—evacuate all occupants outdoors immediately; Fire SCBA entry with 4-gas meter."
        inno = "Shared foodborne gastroenteritis can cause family nausea, but simultaneous morning headache, dizziness, pet lethargy, and continuous winter furnace use strongly indicate lethal CO."

    elif sub_archetype == "apartment_fire_conflicting_floors":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2_MULTI_CALL_CLUSTER | TARGET PREMISE: {addr} (3-story 18-unit wood-frame apartment)\n"
            f"LINKED CAD NOTE: Secondary Caller #2 ({other_name}) reports heavy black smoke banking on 2nd-floor stairwell, claims 'everyone got out of Floor 3'."
        )
        tr_t1 = f"[00:02] CALLER #1 ({caller_name}): Fire at {addr}! Flames are blowing out a 2nd-floor window right below us!"
        q1_cad = "claims 'everyone got out of Floor 3'"
        q1_tr = f"Flames are blowing out a 2nd-floor window right below us"
        probe_line = "What exact floor and apartment are you in, and is smoke entering?"
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:11] CALLER #1: We're trapped in 3rd-floor Apt 3B rear bedroom with my grandmother! The hallway is black smoke, we cannot use the stairs! [BG: smoke alarm screaming, coughing]"
        )
        q2_tr = "trapped in 3rd-floor Apt 3B rear bedroom with my grandmother"
        final_line = "Close the bedroom door, stuff wet towels under it, and signal at the window!"
        traps = ["conflicting_multi_caller_evacuation_account", "shelter_in_place_seal_door_above_stairwell_fire"]
        units_t1 = ["WORKING_FIRE_BOX_ALARM"]
        units_final = ["WORKING_FIRE_RESCUE_BOX", "LADDER_TRUCK_AERIAL", "BATTALION_CHIEF", "TWO_ALS_MEDICS"]
        prio_t1 = "P1_ECHO"
        prio_final = "P1_ECHO"
        pre_t1 = "Working 3-story structure fire with conflicting evacuation claim; pinpoint Caller #1 exact apartment/side."
        pre_final = f"CONFIRMED TRAPPED OCCUPANTS OVERRIDE CALLER #2 CLEARANCE: 2 occupants trapped in 3rd-floor Apt 3B Charlie/Rear bedroom at {addr} above 2nd-floor fire. Priority aerial ladder rescue to Charlie side; shelter-in-place door seal coached."
        inno = "Caller #2 likely saw front-stairwell 3rd-floor neighbors exit and sincerely believed the floor was empty; verified first-party trapped caller always governs rescue priority."
        addr = f"{addr}, Apt 3B (3rd-Floor Rear)"

    # ------------------------------------------------------------------
    # 5. SILENT_OR_OPEN_LINE (2 contrasting sub-cases)
    # ------------------------------------------------------------------
    elif sub_archetype == "silent_duress_double_dtmf":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m — maps to {addr})\n"
            f"PREMISE HISTORY ({addr}): Prior stalking/harassment complaint 6 weeks ago."
        )
        tr_t1 = "[00:02] CALLER: [Open silent line — rapid shallow breathing, closet door latch click]"
        q1_cad = "Prior stalking/harassment complaint 6 weeks ago"
        q1_tr = "Open silent line — rapid shallow breathing, closet door latch click"
        probe_line = "This is 911. If you cannot speak safely, press two keypad buttons now."
        tr_t2_extra = (
            f"[00:06] DISPATCH: {probe_line}\n"
            f"[00:10] CALLER: [DTMF TONE: '1'] [DTMF TONE: '1'] [BG: heavy footsteps outside door, barely audible whisper: 'help']"
        )
        q2_tr = "[DTMF TONE: '1'] [DTMF TONE: '1'] [BG: heavy footsteps outside door"
        final_line = "I heard your taps. Police are coming silently. Press 1 if armed."
        traps = ["silent_line_intentional_double_dtmf_duress", "silent_approach_no_voice_exposure"]
        units_t1 = ["PD_PATROL_UNIT"]
        units_final = ["PD_PATROL_TWO_UNIT", "PD_SUPERVISOR", "STAGE_BLS_NEARBY"]
        prio_t1 = "P2_BRAVO"
        prio_final = "P1_DELTA"
        pre_t1 = "Silent wireless open line with shallow breathing at address with stalking history; issue TDD/DTMF keypad challenge."
        pre_final = f"CONFIRMED SILENT DURESS at {addr} (WPH2 +/-{radius_m}m): caller answered prompt with double DTMF '1','1' + whispered 'help'. SILENT APPROACH REQUIRED; keep earpiece volume warning in mind, DTMF prompts only."
        inno = "Accidental pocket friction rarely produces synchronous double DTMF tones immediately following a dispatcher keypad prompt alongside whispered speech."

    elif sub_archetype == "benign_pocket_dial_retail_laundromat":
        venue_tag = rng.choice([
            ("supermarket barcode scanner beeps", "Yeah grab oat milk and bananas from aisle four"),
            ("coin-laundry dryer hum and folding table chatter", "Put two quarters in dryer six for the towels"),
        ])
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: WPH2 | EST COORDS: {lat}, {lon} (+/- {radius_m}m — commercial plaza at {addr})\n"
            f"PREMISE HISTORY ({addr}): Retail grocery & laundromat strip plaza; 0 violence history."
        )
        tr_t1 = f"[00:02] CALLER: [Open line — rhythmic denim pocket rustling, {venue_tag[0]}]"
        q1_cad = "Retail grocery & laundromat strip plaza; 0 violence history"
        q1_tr = f"rhythmic denim pocket rustling, {venue_tag[0]}"
        probe_line = "911 emergency on an open line. Speak or press any key for help."
        tr_t2_extra = (
            f"[00:07] DISPATCH: {probe_line}\n"
            f"[00:13] CALLER: [Distant relaxed voice: '{venue_tag[1]}'] [Zero DTMF tones, zero distress acoustics]"
        )
        q2_tr = f"{venue_tag[1]}"
        final_line = "No emergency heard on this open line; sending SMS and callback check now."
        traps = ["benign_retail_pocket_dial_classification", "mandatory_sms_callback_verification_before_close"]
        units_t1 = []
        units_final = []
        prio_t1 = "P4_NON_EMERG_VERIFY"
        prio_final = "P4_NON_EMERG_VERIFY"
        pre_t1 = "Open line in retail plaza with pocket friction; run verbal + DTMF duress check before classifying."
        pre_final = f"PROBABLE INADVERTENT POCKET-DIAL at {addr} commercial plaza (calm routine errands, zero DTMF response). Hold patrol units; execute mandatory PSAP SMS/voice callback verification."
        inno = "High-confidence accidental SOS trigger in pocket during shopping/laundry; callback/SMS check still required per open-line SOP."

    # ------------------------------------------------------------------
    # 6. SWATTING_OR_FALSE_REPORT (2 premise-mismatch VOIP sub-cases)
    # ------------------------------------------------------------------
    elif sub_archetype == "voip_swatting_3rd_floor_attic_on_ranch":
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: UNVERIFIED_NON_NATIVE_VOIP (Zero ALI GPS; overseas SIP relay header)\n"
            f"PREMISE HISTORY ({addr}): Verified Assessor & Senior Registry — 1-story 1,140 sq ft concrete-slab ranch; retired couple on file; 1 prior swatting alert on street."
        )
        tr_t1 = f"[00:02] CALLER (flat monotone): I am inside {addr} with a rifle and hostages tied up upstairs."
        q1_cad = "UNVERIFIED_NON_NATIVE_VOIP (Zero ALI GPS; overseas SIP relay header)"
        q1_tr = f"inside {addr} with a rifle and hostages tied up upstairs"
        probe_line = "Stay on the line. Which floor are you on, and describe the house?"
        tr_t2_extra = (
            f"[00:07] DISPATCH: {probe_line}\n"
            f"[00:12] CALLER: I'm in the third-floor attic bathroom and I rigged tripwires on the basement stairs, breach now! [BG: dead studio room acoustics, mechanical keyboard clicks]"
        )
        q2_tr = "third-floor attic bathroom and I rigged tripwires on the basement stairs"
        final_line = "Keep talking with me on this line. What vehicles are in the driveway?"
        traps = ["voip_swatting_architectural_impossibility", "stage_and_verify_no_blind_dynamic_breach", "never_hang_up_preserve_sip_trace"]
        units_t1 = ["PD_SUPERVISOR_STAGING", "PD_PERIMETER_VERIFY"]
        units_final = ["PD_SUPERVISOR_STAGING", "PD_PERIMETER_CONTAIN_VERIFY", "STAGE_BLS_SAFE_DISTANCE"]
        prio_t1 = "P2_TACTICAL_VERIFY"
        prio_final = "P2_TACTICAL_VERIFY"
        pre_t1 = "Non-native overseas SIP VOIP threat against 1-story senior ranch; challenge architectural specifics while staging supervisor."
        pre_final = f"SEVERE SWATTING INDICATORS at {addr}: Non-native VOIP + keyboard clicks + claim of 'third-floor attic' & 'basement stairs' at a verified 1-story concrete-slab ranch. STAGE SILENTLY, DO NOT EXECUTE BLIND DYNAMIC BREACH, call resident's verified landline, keep caller on line for SIP trace."
        inno = "A caller under genuine panic could misstate an address by one digit, so units must still stage and verify resident welfare peacefully rather than canceling without check."

    else:  # voip_swatting_basement_bombs_on_slab
        cad_t1 = (
            f"CALL ID: {call_id} | TIME: {call_time} | JURISDICTION: {county}\n"
            f"ANI/ALI CLASS: UNVERIFIED_NON_NATIVE_VOIP (One-way burner OTT VoIP; no cell tower sector)\n"
            f"PREMISE HISTORY ({addr}): Fire Pre-Plan & Parcel Record — single-story 980 sq ft slab-on-grade bungalow (no basement, no 2nd/3rd story); streamer swatting hazard flag active."
        )
        tr_t1 = f"[00:02] CALLER (scripted cadence): Send SWAT to {addr}, I just shot two people and locked prisoners in the sub-basement."
        q1_cad = "single-story 980 sq ft slab-on-grade bungalow (no basement, no 2nd/3rd story)"
        q1_tr = f"locked prisoners in the sub-basement"
        probe_line = "Stay with me. What are your hostages' names and where are you standing?"
        tr_t2_extra = (
            f"[00:07] DISPATCH: {probe_line}\n"
            f"[00:12] CALLER: Looking down from the third-floor loft window with pipe bombs in the cellar boiler room! [BG: zero gunshot reverb, gaming headset mouse clicks]"
        )
        q2_tr = "third-floor loft window with pipe bombs in the cellar boiler room"
        final_line = "Stay on the line with me. Tell me what color the front door is."
        traps = ["voip_swatting_flag_and_slab_contradiction", "stage_perimeter_call_premise_contact_first", "never_disconnect_caller"]
        units_t1 = ["PD_SUPERVISOR_STAGING", "PD_PERIMETER_VERIFY"]
        units_final = ["PD_SUPERVISOR_STAGING", "PD_PERIMETER_CONTAIN_VERIFY", "STAGE_BLS_SAFE_DISTANCE"]
        prio_t1 = "P2_TACTICAL_VERIFY"
        prio_final = "P2_TACTICAL_VERIFY"
        pre_t1 = "Burner VoIP call hitting flagged swatting-target address claiming 'sub-basement' on slab bungalow; stage supervisor and verify."
        pre_final = f"HIGH-CONFIDENCE SWATTING HOAX PROTOCOL at {addr}: Active swatting hazard flag + OTT VoIP + mouse clicks + impossible 'third-floor loft / cellar boiler room' on verified 1-story slab-on-grade bungalow. Stage perimeter silently, contact resident via verified callback number, NO blind dynamic entry, keep line open."
        inno = "An unrecorded garage conversion or neighbor address confusion is theoretically possible, which is why officers verify peacefully from cover rather than ignoring the call."

    coercion_t1 = archetype == "COERCED_CALLER"
    coercion_final = (archetype == "COERCED_CALLER") or (sub_archetype == "silent_duress_double_dtmf")
    silent_t1 = archetype in ("COERCED_CALLER", "SWATTING_OR_FALSE_REPORT") or (sub_archetype == "trunk_abduction_turns_rumble_sectors")
    silent_final = coercion_final or (archetype == "SWATTING_OR_FALSE_REPORT") or (sub_archetype == "trunk_abduction_turns_rumble_sectors")

    loc_t1 = f"{addr} (initial CAD / WPH2 telemetry)"
    loc_final = (
        f"{addr}, Apt {apt} (verified WPH2 +/-{radius_m}m)"
        if archetype == "COERCED_CALLER" and "rideshare" not in sub_archetype
        else (f"{addr} ({veh_color} {veh_model}, plate {plate})" if "rideshare" in sub_archetype else f"{addr}")
    )

    return {
        "cad_t1": cad_t1,
        "tr_t1": tr_t1,
        "tr_full": f"{tr_t1}\n{tr_t2_extra}",
        "q1_cad": q1_cad,
        "q1_tr": q1_tr,
        "q2_tr": q2_tr,
        "probe_line": probe_line,
        "final_line": final_line,
        "prio_t1": prio_t1,
        "prio_final": prio_final,
        "coercion_t1": coercion_t1,
        "coercion_final": coercion_final,
        "silent_t1": silent_t1,
        "silent_final": silent_final,
        "loc_t1": loc_t1,
        "loc_final": loc_final,
        "traps": traps,
        "units_t1": units_t1,
        "units_final": units_final,
        "pre_t1": pre_t1,
        "pre_final": pre_final,
        "innocent_alternative": inno,
    }


def _assert_turn_valid(
    packet: dict[str, Any],
    assistant_text: str,
    docs_by_id: dict[str, dict[str, str]],
) -> int:
    line = packet["next_dispatcher_line"]
    wc = len(line.split())
    assert 1 <= wc <= 18, f"next_dispatcher_line exceeded 18 words ({wc}): {line!r}"
    quotes = packet["evidence_quotes"]
    assert len(quotes) >= 2, "Expected >=2 verbatim evidence_quotes per dispatch turn"
    for q in quotes:
        assert quote_ok(q["quote"], q["doc_id"], docs_by_id), (
            f"Quote failed quote_ok on {q['doc_id']}: {q['quote']!r}"
        )
    assert packet.get("innocent_alternative") and len(packet["innocent_alternative"]) >= 20
    veto_hits = check_prosecutor_vetoes(assistant_text, [])
    assert not veto_hits, f"Prosecutor veto violation in 911 turn: {veto_hits}"
    return wc


def generate_dispatch_911_example(
    split: str,
    index: int,
    salt: str = "mb-spec7-v1",
) -> dict[str, Any]:
    """Generate one deterministic single-turn (70%) or multi-turn streaming (30%) 911 example."""
    rng = make_rng(split, "dispatch_911_triage", index, salt)

    county_a, _, corridor = rng.choice(COUNTIES)
    call_min = rng.randint(0, 23 * 60 + 59)
    call_time = fmt_clock(call_min)
    call_id = f"CAD-{rng.randint(2024, 2026)}-{rng.randint(100000, 999999)}"

    archetype, sub_archetype = _pick_sub_archetype(rng)
    is_multi_turn = rng.random() < 0.30

    sc = _build_scenario(rng, archetype, sub_archetype, call_id, call_time, county_a, corridor)

    if not is_multi_turn:
        docs_full = {
            "CAD_HEADER": {"id": "CAD_HEADER", "text": sc["cad_t1"]},
            "TRANSCRIPT": {"id": "TRANSCRIPT", "text": sc["tr_full"]},
        }
        final_quotes = [
            {"doc_id": "CAD_HEADER", "quote": sc["q1_cad"]},
            {"doc_id": "TRANSCRIPT", "quote": sc["q1_tr"]},
            {"doc_id": "TRANSCRIPT", "quote": sc["q2_tr"]},
        ]
        packet_final = {
            "call_id": call_id,
            "archetype": archetype,
            "sub_archetype": sub_archetype,
            "priority": sc["prio_final"],
            "coercion_detected": sc["coercion_final"],
            "silent_approach_required": sc["silent_final"],
            "resolved_location": sc["loc_final"],
            "life_safety_traps_flagged": sc["traps"],
            "units_to_dispatch": sc["units_final"],
            "evidence_quotes": final_quotes,
            "innocent_alternative": sc["innocent_alternative"],
            "cad_pre_arrival_note": sc["pre_final"],
            "next_dispatcher_line": sc["final_line"],
        }
        triage_thought = (
            f"<triage>\n"
            f"- Archetype & Telemetry: `{archetype}` (`{sub_archetype}`) on {call_id}; CAD notes \"{sc['q1_cad']}\".\n"
            f"- Transcript Evidence: Caller opens with \"{sc['q1_tr']}\" and reveals \"{sc['q2_tr']}\".\n"
            f"- Life-Safety Traps & Protocol: {', '.join(sc['traps'])} -> Priority `{sc['prio_final']}`, "
            f"coercion={sc['coercion_final']}, silent_approach={sc['silent_final']}.\n"
            f"- Alternative Reading Kept Open: {sc['innocent_alternative']}\n"
            f"</triage>"
        )
        assistant_final = f"{triage_thought}\n```json\n{json.dumps(packet_final, indent=2)}\n```"
        wc_final = _assert_turn_valid(packet_final, assistant_final, docs_full)

        user_prompt = (
            f"{rng.choice(USER_PROMPTS_SINGLE)}\n\n"
            f"=== CAD_HEADER ===\n{sc['cad_t1']}\n\n"
            f"=== TRANSCRIPT ===\n{sc['tr_full']}"
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_911},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_final},
        ]
        word_counts = [wc_final]
    else:
        # Turn 1 -> Turn 2 (provisional triage + <=18-word probe)
        docs_t1 = {
            "CAD_HEADER": {"id": "CAD_HEADER", "text": sc["cad_t1"]},
            "TRANSCRIPT": {"id": "TRANSCRIPT", "text": sc["tr_t1"]},
        }
        quotes_t1 = [
            {"doc_id": "CAD_HEADER", "quote": sc["q1_cad"]},
            {"doc_id": "TRANSCRIPT", "quote": sc["q1_tr"]},
        ]
        packet_t1 = {
            "call_id": call_id,
            "archetype": archetype,
            "sub_archetype": sub_archetype,
            "priority": sc["prio_t1"],
            "coercion_detected": sc["coercion_t1"],
            "silent_approach_required": sc["silent_t1"],
            "resolved_location": sc["loc_t1"],
            "life_safety_traps_flagged": [sc["traps"][0]],
            "units_to_dispatch": sc["units_t1"],
            "evidence_quotes": quotes_t1,
            "innocent_alternative": sc["innocent_alternative"],
            "cad_pre_arrival_note": sc["pre_t1"],
            "next_dispatcher_line": sc["probe_line"],
        }
        thought_t1 = (
            f"<triage>\n"
            f"- Initial Intake ({call_id}): CAD shows \"{sc['q1_cad']}\" while caller states \"{sc['q1_tr']}\".\n"
            f"- Provisional Hold: Assign `{sc['prio_t1']}` and issue a <=18-word diagnostic probe to confirm `{sc['traps'][0]}` before locking final response.\n"
            f"- Alternative Reading Kept Open: {sc['innocent_alternative']}\n"
            f"</triage>"
        )
        assistant_t1 = f"{thought_t1}\n```json\n{json.dumps(packet_t1, indent=2)}\n```"
        wc_t1 = _assert_turn_valid(packet_t1, assistant_t1, docs_t1)

        # Turn 3 -> Turn 4 (streaming reveal + priority upgrade / final protocol)
        tr_delta = sc["tr_full"][len(sc["tr_t1"]):].lstrip("\n")
        docs_t2 = {
            "CAD_HEADER": {"id": "CAD_HEADER", "text": sc["cad_t1"]},
            "TRANSCRIPT": {"id": "TRANSCRIPT", "text": sc["tr_full"]},
        }
        quotes_t2 = [
            {"doc_id": "CAD_HEADER", "quote": sc["q1_cad"]},
            {"doc_id": "TRANSCRIPT", "quote": sc["q2_tr"]},
        ]
        packet_t2 = {
            "call_id": call_id,
            "archetype": archetype,
            "sub_archetype": sub_archetype,
            "priority": sc["prio_final"],
            "coercion_detected": sc["coercion_final"],
            "silent_approach_required": sc["silent_final"],
            "resolved_location": sc["loc_final"],
            "life_safety_traps_flagged": sc["traps"],
            "units_to_dispatch": sc["units_final"],
            "evidence_quotes": quotes_t2,
            "innocent_alternative": sc["innocent_alternative"],
            "cad_pre_arrival_note": sc["pre_final"],
            "next_dispatcher_line": sc["final_line"],
        }
        thought_t2 = (
            f"<triage>\n"
            f"- Streaming Escalation ({call_id}): Caller response reveals \"{sc['q2_tr']}\" against CAD record \"{sc['q1_cad']}\".\n"
            f"- Priority Transition: `{sc['prio_t1']}` -> `{sc['prio_final']}`; coercion={sc['coercion_final']}, silent_approach={sc['silent_final']}.\n"
            f"- Critical Action: {', '.join(sc['traps'])}. Emit <=18-word pre-arrival instruction.\n"
            f"- Alternative Reading Kept Open: {sc['innocent_alternative']}\n"
            f"</triage>"
        )
        assistant_t2 = f"{thought_t2}\n```json\n{json.dumps(packet_t2, indent=2)}\n```"
        wc_t2 = _assert_turn_valid(packet_t2, assistant_t2, docs_t2)

        user_t1 = (
            f"{rng.choice(USER_PROMPTS_MULTI_OPEN)}\n\n"
            f"=== CAD_HEADER ===\n{sc['cad_t1']}\n\n"
            f"=== TRANSCRIPT ===\n{sc['tr_t1']}"
        )
        user_t2 = (
            f"{rng.choice(USER_PROMPTS_MULTI_UPDATE)}\n\n"
            f"=== TRANSCRIPT (STREAMING APPEND) ===\n{tr_delta}"
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_911},
            {"role": "user", "content": user_t1},
            {"role": "assistant", "content": assistant_t1},
            {"role": "user", "content": user_t2},
            {"role": "assistant", "content": assistant_t2},
        ]
        word_counts = [wc_t1, wc_t2]
        final_quotes = quotes_t2

    return {
        "id": f"dispatch_911_{split}_{index:07d}",
        "track": "track1_now",
        "domain": "dispatch_911_triage",
        "subtask": archetype,
        "sub_archetype": sub_archetype,
        "split": split,
        "messages": messages,
        "ground_truth": {
            "call_id": call_id,
            "archetype": archetype,
            "sub_archetype": sub_archetype,
            "interaction_mode": "multi_turn_escalation" if is_multi_turn else "single_turn",
            "initial_priority": sc["prio_t1"],
            "priority": sc["prio_final"],
            "coercion_detected": sc["coercion_final"],
            "silent_approach_required": sc["silent_final"],
            "resolved_location": sc["loc_final"],
            "life_safety_traps_flagged": sc["traps"],
            "units_to_dispatch": sc["units_final"],
            "evidence_quotes": final_quotes,
            "quote_check_drops": 0,
            "next_line_word_count": word_counts[-1],
            "all_turn_word_counts": word_counts,
        },
    }
