"""Procedural 11-Chair Cold-Case Homicide Simulator (`murder_board_sim.py`).

Generates complete 16-document homicide case files across 10 realistic venue archetypes
and emits zero-drop outputs for all 11 Murder Board steps (`01_first_officer.md` ..
`11_lead_detective.md`) under both case modes:
  - 80% `ACTIONABLE_RECORD_CHAIN` (4-link record solve + cleared red-herring liar + MEDIUM drift)
  - 20% `INSUFFICIENT_EVIDENCE_HOLD` (archival/battery holdout where no suspect's narrowed-window
    alibi is contradicted yet and Lead Detective prioritizes archival pull / preserved DNA Item 3)
"""

from __future__ import annotations

import copy
import datetime as _dt
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from training.common import (
    ALIAS_NICKNAMES,
    COUNTIES,
    STANDING_BRIEF_CLOSER,
    VEHICLES,
    check_prosecutor_vetoes,
    docs_text_block,
    fmt_clock,
    fmt_clock_12h,
    load_mb_agent_prompts,
    make_rng,
    pick_distinct,
    quote_ok,
    random_address,
    random_plate,
    recompute_score,
    registry_text_block,
    sample_unique_names,
)

DOMAIN = "cold_case_murder_board"

MB_STEPS: tuple[tuple[str, str], ...] = (
    ("custody", "01_first_officer.md"),
    ("records", "02_records.md"),
    ("coroner", "03_coroner.md"),
    ("csi", "04_csi.md"),
    ("intake", "05_intake.md"),
    ("analyst", "06_analyst.md"),
    ("digital", "07_digital.md"),
    ("cross_examiner", "08_cross_examiner.md"),
    ("interviewer", "09_interviewer.md"),
    ("prosecutor", "10_prosecutor.md"),
    ("lead_detective", "11_lead_detective.md"),
)

VENUE_ARCHETYPES: tuple[dict[str, Any], ...] = (
    {
        "key": "cold_storage_warehouse",
        "label": "cold storage warehouse",
        "venues": ("Glacier Bay Cold Storage", "Northstar Blast Freezer & Logistics", "Polaris Cold-Chain Terminal"),
        "victim_role": "night inventory supervisor",
        "office_name": "insulated manifest office",
        "insider_role": "night refrigeration engineer",
        "relief_role": "relief manifest clerk",
        "drift_role": "freezer pallet loader",
        "rh_role": "ousted cold-freight partner",
        "cause": "blunt force craniocerebral trauma",
        "weapon_scene": "A heavy cast-steel valve wrench lay on the floor beside the desk.",
        "weapon_short": "cast-steel valve wrench",
        "disc_two": "Two cut numbered polypropylene pallet seals were observed beside the floor safe at evidence markers 4 and 5.",
        "disc_one": "One (1) cut numbered polypropylene pallet seal, recovered beside floor safe at marker 4",
        "disc_label": "cut numbered polypropylene pallet seals",
        "latch_defect": "the manifest office insulated door strike plate is misaligned and fails to latch unless pulled firmly shut",
        "blinds_line": "The manifest office wire-glass window blinds were drawn shut.",
        "camera_line": "A municipal industrial-park traffic camera mounted on the east utility pole faces the loading apron; footage has not yet been requested.",
        "circuit_name": "manifest office lighting and terminal sub-circuit",
    },
    {
        "key": "collision_autobody_shop",
        "label": "collision auto-body shop",
        "venues": ("Tri-County Collision & Frame", "Apex Auto Body & Paint", "Foundry Avenue Collision Center"),
        "victim_role": "lead collision estimator",
        "office_name": "estimator glass office",
        "insider_role": "overnight frame technician",
        "relief_role": "parts counter coordinator",
        "drift_role": "prep-bay sander",
        "rh_role": "former co-owner",
        "cause": "two penetrating gunshot wounds to the torso",
        "weapon_scene": "No firearm was present in the office; brass cartridge evidence lay near the file cabinet.",
        "weapon_short": "9mm cartridge evidence",
        "disc_two": "Two spent 9mm Luger brass shell casings were observed near the file cabinet at evidence markers 4 and 5.",
        "disc_one": "One (1) spent 9mm Luger brass shell casing, recovered near file cabinet at marker 4",
        "disc_label": "spent 9mm Luger brass shell casings",
        "latch_defect": "the estimator office fire-rated mortise latch binds in its strike box and appears closed without engaging",
        "blinds_line": "The estimator office aluminum mini-blinds were closed.",
        "camera_line": "A frontage-road transit camera mounted above the сосед/corner signal faces the shop driveway; footage has not yet been pulled.",
        "circuit_name": "estimator office overhead lighting and desktop circuit",
    },
    {
        "key": "bowling_lounge",
        "label": "bowling lounge",
        "venues": ("Starlight 24-Lane Lounge", "TimberPin Bowling & Cocktail Lanes", "Crown Alley Recreation Center"),
        "victim_role": "evening lanes manager",
        "office_name": "cashier counting office",
        "insider_role": "night pinsetter mechanic",
        "relief_role": "league desk supervisor",
        "drift_role": "concourse custodian",
        "rh_role": "terminated bar manager",
        "cause": "blunt force trauma to the head",
        "weapon_scene": "A weighted bronze trophy base lay beside the floor mat near the counting table.",
        "weapon_short": "weighted bronze trophy base",
        "disc_two": "Two torn tamper-evident bank deposit bag stubs were observed beside the counting table at evidence markers 4 and 5.",
        "disc_one": "One (1) torn tamper-evident bank deposit bag stub, recovered beside counting table at marker 4",
        "disc_label": "torn tamper-evident bank deposit bag stubs",
        "latch_defect": "the counting office corridor latch spring is worn and does not catch unless pulled hard from either side",
        "blinds_line": "The counting office exterior frosted-window blinds were closed.",
        "camera_line": "A municipal alley sanitation camera behind Lane 24 faces the rear service lot; recordings have not yet been subpoenaed.",
        "circuit_name": "counting office light and POS server sub-circuit",
    },
    {
        "key": "marina_drydock",
        "label": "marina drydock",
        "venues": ("Harborcrest Drydock & Basin", "Tidewater Boatyard & Slipway", "Kestrel Point Marina Drydock"),
        "victim_role": "drydock operations manager",
        "office_name": "harbormaster yard office",
        "insider_role": "overnight dock watchman",
        "relief_role": "assistant slip coordinator",
        "drift_role": "hull-prep laborer",
        "rh_role": "estranged former spouse",
        "cause": "blunt force cranial trauma",
        "weapon_scene": "A solid brass travel-lift shackle pin lay on the floorboards near the chart desk.",
        "weapon_short": "brass travel-lift shackle pin",
        "disc_two": "Two numbered brass slip-key tags were observed on the floorboards near the chart desk at evidence markers 4 and 5.",
        "disc_one": "One (1) numbered brass slip-key tag, recovered near chart desk at marker 4",
        "disc_label": "numbered brass slip-key tags",
        "latch_defect": "the yard office salt-corroded deadlatch fails to seat in the jamb unless pulled sharply",
        "blinds_line": "The yard office louvered storm blinds were shut.",
        "camera_line": "A port-authority weather and channel camera on Pier B overlooks the drydock parking apron; archive has not yet been requested.",
        "circuit_name": "harbormaster office lighting and billing PC circuit",
    },
    {
        "key": "textile_mill",
        "label": "textile mill",
        "venues": ("Millbrook Woven Goods Plant #2", "Cumberland Cotton & Dye Works", "Piedmont Industrial Looms"),
        "victim_role": "second-shift dye-house superintendent",
        "office_name": "mezzanine dye-house office",
        "insider_role": "night boiler and loom tender",
        "relief_role": "quality-control lab clerk",
        "drift_role": "vat batch handler",
        "rh_role": "dismissed shift foreman",
        "cause": "blunt force head injury",
        "weapon_scene": "A machined iron spindle weight lay beside the sample cabinet inside the office.",
        "weapon_short": "machined iron spindle weight",
        "disc_two": "Two crimped lead bale-lot seals were observed on the floor beside the sample cabinet at evidence markers 4 and 5.",
        "disc_one": "One (1) crimped lead bale-lot seal, recovered beside sample cabinet at marker 4",
        "disc_label": "crimped lead bale-lot seals",
        "latch_defect": "the mezzanine office steel door latch bolt drags on the threshold plate and fails to catch automatically",
        "blinds_line": "The mezzanine office vertical blinds were drawn closed.",
        "camera_line": "A county weighbridge camera across Mill Road faces the employee gate; footage has not yet been requested.",
        "circuit_name": "mezzanine office illumination and terminal circuit",
    },
    {
        "key": "truck_stop_diner",
        "label": "24hr truck-stop diner",
        "venues": ("Interstate Milepost 44 Diner & Fuel", "Redline 24hr Truck Plaza", "Crossroads Diesel & Grill"),
        "victim_role": "overnight commissary manager",
        "office_name": "back commissary safe office",
        "insider_role": "overnight facility porter",
        "relief_role": "late-shift grill supervisor",
        "drift_role": "dishroom steward",
        "rh_role": "estranged ex-husband",
        "cause": "two penetrating .380 gunshot wounds to the chest",
        "weapon_scene": "No handgun was recovered in the office; spent .380 cartridge evidence lay beside the safe.",
        "weapon_short": ".380 cartridge evidence",
        "disc_two": "Two spent .380 ACP brass shell casings were observed beside the floor safe at evidence markers 4 and 5.",
        "disc_one": "One (1) spent .380 ACP brass shell casing, recovered beside floor safe at marker 4",
        "disc_label": "spent .380 ACP brass shell casings",
        "latch_defect": "the commissary office commercial closer under-travels and leaves the latch bolt unengaged unless pulled shut",
        "blinds_line": "The commissary office exterior transom blinds were closed.",
        "camera_line": "A state highway weigh-ramp camera facing the north diesel apron was operational that night; footage has not yet been pulled.",
        "circuit_name": "commissary safe office lights and accounting PC circuit",
    },
    {
        "key": "regional_freight_depot",
        "label": "regional freight depot",
        "venues": ("Mid-Valley LTL Cross-Dock", "Corridor Express Freight Depot", "Seneca Regional Transfer Hub"),
        "victim_role": "graveyard dispatch supervisor",
        "office_name": "dispatch cage office",
        "insider_role": "graveyard yard hostler",
        "relief_role": "outbound bill-of-lading clerk",
        "drift_role": "cross-dock lumper",
        "rh_role": "terminated drayage contractor",
        "cause": "blunt force craniocerebral trauma",
        "weapon_scene": "A forged steel fifth-wheel kingpin puller lay on the tile beside the dispatch console.",
        "weapon_short": "steel fifth-wheel kingpin puller",
        "disc_two": "Two clipped high-security trailer bolt seals were observed beside the dispatch console at evidence markers 4 and 5.",
        "disc_one": "One (1) clipped high-security trailer bolt seal, recovered beside dispatch console at marker 4",
        "disc_label": "clipped high-security trailer bolt seals",
        "latch_defect": "the dispatch cage sliding strike latch is warped and rests flush without locking unless manually seated",
        "blinds_line": "The dispatch cage exterior window blinds were closed.",
        "camera_line": "A rail-spur grade-crossing camera 60 yards west faces the depot employee lot; recordings have not yet been requested.",
        "circuit_name": "dispatch cage office lighting and terminal circuit",
    },
    {
        "key": "motor_lodge",
        "label": "motor lodge",
        "venues": ("Pinecrest Motor Lodge", "Parkway Rest Motor Court", "Sundown Turnpike Lodge"),
        "victim_role": "night-audit general manager",
        "office_name": "registration night-audit office",
        "insider_role": "overnight maintenance clerk",
        "relief_role": "evening front-desk lead",
        "drift_role": "linen room attendant",
        "rh_role": "former franchise co-lessee",
        "cause": "two penetrating 9mm gunshot wounds to the chest",
        "weapon_scene": "No weapon remained on scene; spent brass cartridge evidence lay near the key-rack credenza.",
        "weapon_short": "9mm cartridge evidence",
        "disc_two": "Two spent 9mm brass shell casings were observed near the key-rack credenza at evidence markers 4 and 5.",
        "disc_one": "One (1) spent 9mm brass shell casing, recovered near key-rack credenza at marker 4",
        "disc_label": "spent 9mm brass shell casings",
        "latch_defect": "the night-audit office brass spring latch fails to catch in the warped wooden frame unless pulled firmly",
        "blinds_line": "The night-audit office courtyard blinds were drawn closed.",
        "camera_line": "A DOT toll-connector ramp camera overlooking the lodge breezeway entrance has not yet been requested.",
        "circuit_name": "night-audit office lights and reservation server circuit",
    },
    {
        "key": "pharma_distribution_cage",
        "label": "pharmaceutical distribution cage",
        "venues": ("MedCore Regional Wholesale Cage", "Allied Wholesale Pharmacy Depot", "Veritas Clinical Distribution Hub"),
        "victim_role": "vault compliance manager",
        "office_name": "vault control office",
        "insider_role": "overnight cage security technician",
        "relief_role": "receiving compliance clerk",
        "drift_role": "tote-line picker",
        "rh_role": "dismissed regional courier lead",
        "cause": "ligature and blunt compressive trauma",
        "weapon_scene": "Heavy braided nylon tote strapping and an aluminum scanner cradle lay beside the chair.",
        "weapon_short": "braided tote strapping and scanner cradle",
        "disc_two": "Two severed serialized red DEA tote seals were observed beside the chair at evidence markers 4 and 5.",
        "disc_one": "One (1) severed serialized red DEA tote seal, recovered beside chair at marker 4",
        "disc_label": "severed serialized red DEA tote seals",
        "latch_defect": "the vault control office vestibule latch hydraulic closer stalls short of full latch engagement unless pulled",
        "blinds_line": "The vault control office privacy blinds were closed.",
        "camera_line": "A neighboring cold-freight facility pole camera faces the south employee exit lane; footage has not yet been requested.",
        "circuit_name": "vault control office illumination and inventory workstation circuit",
    },
    {
        "key": "scrap_metal_salvage_yard",
        "label": "scrap-metal salvage yard",
        "venues": ("Ironworks Metal Recycling & Scale", "Blackwater Non-Ferrous Salvage", "Canal Street Scrap & Baling"),
        "victim_role": "scale-house settlement manager",
        "office_name": "scale-house settlement office",
        "insider_role": "night crusher watchman",
        "relief_role": "non-ferrous receiving clerk",
        "drift_role": "torch-bay cutter",
        "rh_role": "disputed copper-lot supplier",
        "cause": "blunt force cranial trauma",
        "weapon_scene": "A calibrated cast-iron scale test weight lay on the linoleum beside the settlement safe.",
        "weapon_short": "cast-iron scale test weight",
        "disc_two": "Two carbon-copy copper weight tickets were observed on the floor beside the settlement safe at evidence markers 4 and 5.",
        "disc_one": "One (1) carbon-copy copper weight ticket, recovered beside settlement safe at marker 4",
        "disc_label": "carbon-copy copper weight tickets",
        "latch_defect": "the scale-house steel door latch tongue is burred and rests unlatched unless pulled hard into the keeper",
        "blinds_line": "The scale-house window steel-slat blinds were closed.",
        "camera_line": "A municipal transfer-station gate camera directly across the road faces the scale-house entrance; archive has not yet been pulled.",
        "circuit_name": "scale-house office lighting and weigh-terminal circuit",
    },
)

_SPLIT_OFFSETS = {"train": 0, "val": 3, "test": 7, "eval_sim": 5}


def _clean_typo(text: str) -> str:
    return text.replace("сосед/", "")


def _bates(case_num: str, doc_num: int) -> str:
    return f"[Bates {case_num}-DOC{doc_num:02d} · Page 1 of 1 · LAW ENFORCEMENT SENSITIVE]"


def generate_murder_board_case_bundle(
    split: str,
    case_index: int,
    salt: str = "mb-spec7-v1",
) -> dict[str, Any]:
    """Generate a complete 16-doc homicide file and verified 11-chair Murder Board outputs."""
    rng = make_rng(split, DOMAIN, case_index, salt)
    split_off = _SPLIT_OFFSETS.get(split, 0)
    venue = VENUE_ARCHETYPES[(case_index + split_off) % len(VENUE_ARCHETYPES)]
    is_holdout = (case_index % 5) == 4
    case_mode = "INSUFFICIENT_EVIDENCE_HOLD" if is_holdout else "ACTIONABLE_RECORD_CHAIN"

    venue_name = venue["venues"][(case_index // len(VENUE_ARCHETYPES) + split_off) % len(venue["venues"])]
    county_main, county_adj, corridor_name = COUNTIES[(case_index + split_off * 2) % len(COUNTIES)]
    scene_addr = random_address(rng)

    inc_year = rng.randint(2015, 2019)
    inc_month = rng.randint(3, 11)
    inc_day = rng.randint(4, 24)
    day0 = _dt.date(inc_year, inc_month, inc_day)
    day1 = day0 + _dt.timedelta(days=1)
    day_me = day0 + _dt.timedelta(days=2)
    day_news = day0 + _dt.timedelta(days=4)
    day_memo = day0 + _dt.timedelta(days=11)
    day_rh2 = day0 + _dt.timedelta(days=rng.randint(120, 240))
    day_insp = day0 - _dt.timedelta(days=rng.randint(280, 410))
    review_year = inc_year + rng.randint(6, 7)
    day_cold = _dt.date(review_year, rng.randint(4, 10), rng.randint(5, 25))

    case_num = f"MB-{inc_year}-{1040 + (case_index % 8900):04d}"
    case_id = f"case_syn_{case_index:04d}"

    # Cast of characters (disjoint per seed)
    names = sample_unique_names(rng, 11)
    victim_name = names[0]
    insider_name = names[1]
    relief_name = names[2]
    rh_name = names[3]
    drift_name = names[4]
    drift_spouse = f"{names[5].split()[0]} {drift_name.split()[1]}"
    resp_officer = f"Ofc. {names[6]}"
    lead_inv = f"Det. {names[7]}"
    me_doctor = f"Dr. {names[8]}"
    prop_clerk = f"P. {names[9].split()[1]}"
    departed_emp = names[10]
    # Near-collision name in roster/records (never to be merged)
    collision_stranger = f"{departed_emp.split()[0]} {departed_emp.split()[1]}son"

    victim_age = rng.randint(34, 56)
    insider_age = rng.randint(42, 61)
    rh_veh_model, rh_veh_color, _ = VEHICLES[rng.randrange(len(VEHICLES))]
    rh_plate = random_plate(rng)

    # Codes
    code_victim = f"{rng.randint(21, 39)}{rng.randint(10, 98)}"
    code_drift = f"{rng.randint(41, 58)}{rng.randint(10, 98)}"
    code_relief = f"{rng.randint(61, 78)}{rng.randint(10, 98)}"
    code_master = f"90{rng.randint(11, 89)}"

    # Strictly ordered clock (off in {0, 2, 4, 6} avoids midnight rollover ambiguity)
    off = rng.choice([0, 2, 4, 6])
    t_drift_code = fmt_clock(21 * 60 + 12 + off)       # 21:12..21:18 day0
    t_drift_y1 = "22:15"                               # day0
    me_start_24 = fmt_clock(22 * 60 + 30 + off)        # 22:30..22:36 day0
    me_start_12 = fmt_clock_12h(22 * 60 + 30 + off)
    t_relief_code = fmt_clock(22 * 60 + 48 + off)      # 22:48..22:54 day0
    t_rh_in = fmt_clock(22 * 60 + 56 + off)            # 22:56..23:02 day0
    t_batt_fault = fmt_clock(23 * 60 + 12 + off)       # 23:12..23:18 day0 (holdout)
    t_rh_out = fmt_clock(23 * 60 + 18 + off)           # 23:18..23:24 day0
    t_rh_cardlock = fmt_clock(23 * 60 + 36 + off)      # 23:36..23:42 day0
    t_photo = fmt_clock(23 * 60 + 39 + off)            # 23:39..23:45 day0
    t_sms = fmt_clock(23 * 60 + 46 + off)              # 23:46..23:52 day0
    t_vic_code = fmt_clock(23 * 60 + 53 + off)         # 23:53..23:59 day0
    t_ins_entry = fmt_clock(7 + off)                   # 00:07..00:13 day1
    t_meter_drop = fmt_clock(19 + off)                 # 00:19..00:25 day1
    me_end_24 = fmt_clock(30 + off)                    # 00:30..00:36 day1
    me_end_12 = fmt_clock_12h(30 + off)
    t_ins_round2 = fmt_clock(36 + off)                 # 00:36..00:42 day1
    t_disc = fmt_clock(6 * 60 + 50 + off)              # 06:50..06:56 day1

    me_iso_start = f"{day0.isoformat()}T{me_start_24}:00"
    me_iso_end = f"{day1.isoformat()}T{me_end_24}:00"
    cam_line = _clean_typo(venue["camera_line"])

    # Exact verbatim anchor sentences reused cleanly in gold outputs
    q_doc01_victim = (
        f"The decedent, {victim_name}, age {victim_age}, {venue['victim_role']} at {venue_name}, "
        f"was found unresponsive on the floor of the {venue['office_name']}."
    )
    q_doc01_weapon = venue["weapon_scene"]
    q_doc01_disc = venue["disc_two"]
    q_doc01_latch = f"Scene inspection noted that {venue['latch_defect']}."
    q_doc01_blinds = f"{venue['blinds_line']} The interior door is equipped with an electronic keypad lock."
    q_doc01_cam = cam_line

    q_doc02_cause = f"Cause of death: {venue['cause']}."
    q_doc02_manner = "Manner of death: homicide."
    q_doc02_window = (
        f"Estimated time-of-death window: between {me_start_24} ({me_start_12}) on {day0.isoformat()} "
        f"and {me_end_24} ({me_end_12}) on {day1.isoformat()}, based on core liver temperature, lividity, and gastric contents."
    )
    q_doc02_annex = "Full toxicology and histology annex follows under separate cover; biological swab Item 3 was sealed for laboratory submission."

    q_doc03_never = (
        f"I never entered the {venue['office_name']} at any point that night. "
        f"On my rounds I only check the exterior handle from the corridor."
    )
    q_doc03_dark = (
        f"When I walked the 23:00 corridor round, the {venue['office_name']} was completely dark and quiet, "
        f"and I saw no vehicles enter the lot after 22:00."
    )
    q_doc03_hours = f"Management cut my weekday shift down to weekends starting {day0.replace(day=1).isoformat()}."

    q_doc04_2300 = f"23:00 — Corridor round completed. {venue['office_name'].capitalize()} dark. Building quiet."
    q_doc04_check = f"{t_ins_entry} — Checked {venue['office_name']} door from corridor, handle secure."
    q_doc04_margin = f"Margin note in same ink: \"Weekday hours cut {day0.replace(day=1).isoformat()} after six years on night shift.\""

    q_doc05_header = "Controller logs door-strike unlock entries only; it does not log exits."
    q_doc05_codes = (
        f"Assigned PIN schedule: {code_victim} = {victim_name} ({venue['victim_role']}); "
        f"{code_drift} = {drift_name} ({venue['drift_role']}); "
        f"{code_relief} = {relief_name} ({venue['relief_role']}); "
        f"{code_master} = Master night-shift PIN issued to {insider_name} ({venue['insider_role']})."
    )
    q_doc05_collision = (
        f"Prior staff note: {departed_emp} separated six weeks prior; do not confuse with {collision_stranger} in {county_adj} civil index."
    )
    q_doc05_drift = f"{day0.isoformat()} {t_drift_code} — PIN {code_drift} UNLOCK"
    q_doc05_relief = f"{day0.isoformat()} {t_relief_code} — PIN {code_relief} UNLOCK"
    if not is_holdout:
        q_doc05_vic = f"{day0.isoformat()} {t_vic_code} — PIN {code_victim} UNLOCK"
        q_doc05_ins = f"{day1.isoformat()} {t_ins_entry} — PIN {code_master} UNLOCK"
        doc05_tail = f"{q_doc05_vic}\n{q_doc05_ins}\nNo subsequent keypad unlocks recorded prior to {t_disc}."
    else:
        q_doc05_fault = (
            f"{day0.isoformat()} {t_batt_fault} — FAULT 0x04: local CMOS backup battery depleted; "
            f"events from {t_batt_fault} through {t_disc} unbuffered locally. Raw serial audit tape spooled to off-site alarm vendor archive reel #AR-{100 + (case_index % 800)}, not yet pulled."
        )
        doc05_tail = q_doc05_fault

    q_doc06_visit = (
        f"I returned to {venue_name} around {t_relief_code} and keyed my own PIN {code_relief} at the {venue['office_name']} door "
        f"to pick up my keys. {victim_name} was seated at the desk alive doing end-of-shift reconciliation. I stayed two minutes and drove straight home by 23:25."
    )

    q_doc07_lie = (
        f"I was in {county_adj} playing cards with friends from 20:30 until 01:15 and never drove anywhere near {venue_name} on {day0.isoformat()}."
    )
    q_doc08_admit = (
        f"After reviewing the toll record, I admit I drove my {rh_veh_color} {rh_veh_model} to the {venue_name} lot around 23:02 "
        f"to discuss our financial dispute. The {venue['office_name']} window looked dark behind the blinds, nobody answered, "
        f"so I pulled out by 23:14, crossed {corridor_name} back into {county_adj}, and fueled at the cardlock pump at {t_rh_cardlock}."
    )
    q_doc08_reason = "I held back the lot visit in my first interview because my attorney warned the dispute would look bad."

    q_doc09_in = f"{day0.isoformat()} {t_rh_in} — {corridor_name} Gantry Southbound (toward {venue_name}), plate {rh_plate} ({rh_veh_color} {rh_veh_model}, reg. {rh_name})."
    q_doc09_out = f"{day0.isoformat()} {t_rh_out} — {corridor_name} Gantry Northbound (away from {venue_name} into {county_adj}), plate {rh_plate}."
    q_doc09_pump = (
        f"{day0.isoformat()} {t_rh_cardlock} — {county_adj} Co-op Cardlock Pump #3 (16.2 road miles north of {venue_name}), "
        f"PIN-verified fuel purchase on card of {rh_name}, plate {rh_plate} captured on pump camera; zero southbound gantry hits thereafter through 06:00."
    )

    if not is_holdout:
        q_doc10_sms = (
            f"{day0.isoformat()} {t_sms} — Outgoing SMS from {victim_name}'s handset (recovered in {venue['office_name']}) "
            f"to sibling: \"still closing out in the office, {insider_name.split()[0]} is walking the corridor off-schedule, locking up shortly.\""
        )
    else:
        q_doc10_sms = (
            f"{day0.isoformat()} {t_sms} — Outgoing SMS from {victim_name}'s handset (recovered in {venue['office_name']}) "
            f"to sibling: \"still closing out the ledger in the office alone, locking up in twenty minutes.\""
        )

    if not is_holdout:
        q_doc11_meter = (
            f"AMI 5-minute interval telemetry on the {venue['circuit_name']} recorded continuous active draw (495W to 530W, "
            f"consistent with overhead luminaires and desktop workstation powered on) from 18:00 on {day0.isoformat()} until {t_meter_drop} "
            f"on {day1.isoformat()}, when load dropped abruptly to 18W standby."
        )
    else:
        q_doc11_meter = (
            f"Digital billing server retained monthly gross kWh totals only; 15-minute sub-circuit demand strip-chart roll for "
            f"{day0.isoformat()}–{day1.isoformat()} is stored in unindexed utility microfilm Box #UF-{310 + (case_index % 600)} and has not yet been pulled."
        )

    q_doc12_y1 = (
        f"I clocked out at {t_drift_y1}, called goodnight to {victim_name} through the closed {venue['office_name']} door while {victim_name.split()[0]} worked inside, "
        f"and drove straight home before 22:50."
    )
    q_doc13_y7 = (
        f"I left around 22:00, maybe ten past, and I stopped by the supply alcove where {victim_name} stepped out of the {venue['office_name']} "
        f"to talk for a minute about Tuesday's schedule before I headed home."
    )

    q_doc14_photo = (
        f"A passing patron showed {lead_inv} a smartphone photograph taken from the lot at {t_photo} on {day0.isoformat()} "
        f"depicting the {venue['office_name']} window illuminated behind closed blinds; as of this review the original digital image file "
        f"with raw EXIF metadata has never been received or booked into the evidence ledger."
    )
    q_doc14_spouse = (
        f"During the {day_cold.isoformat()} cold-case canvas, {drift_spouse} stated for the first time that {drift_name} arrived home prior to 23:00 on {day0.isoformat()}."
    )

    q_doc15_item1 = f"Item 1 (Seal S-{case_index % 900 + 100}-01): Crime scene digital exposure set (18 frames), {venue['office_name']}, logged by {resp_officer}."
    q_doc15_item2 = f"Item 2 (Seal S-{case_index % 900 + 100}-02): Victim's mobile handset, recovered from {venue['office_name']} desk, logged by {resp_officer}."
    q_doc15_item3 = (
        f"Item 3 (Seal S-{case_index % 900 + 100}-03): Sealed biological trace swab from interior {venue['office_name']} door lever and {venue['weapon_short']}, "
        f"preserved in cold evidence vault (untested for STR/touch DNA)."
    )
    q_doc15_item4 = f"Item 4 (Seal S-{case_index % 900 + 100}-04): {venue['disc_one']} (no receipt or entry exists for marker 5)."

    q_doc16_insp = (
        f"County Public Safety Inspection Docket #INSP-{day_insp.year}-{220 + (case_index % 700)} ({day_insp.isoformat()}, posted on public county web portal): "
        f"Citation 7 notes that at {venue_name}, {venue['latch_defect']}; repair ordered, re-inspection pending."
    )
    q_doc16_press = (
        f"County Herald clipping ({day_news.isoformat()}): An unnamed tipster told reporters \"only a current employee would know the {venue['office_name']} latch fails to catch.\""
    )

    # Assemble 16 documents with realistic agency header chrome & Bates footers
    raw_docs: list[tuple[str, str, str, str, str, str]] = [
        (
            "doc01",
            f"Scene report: {victim_name} at {venue_name}",
            "report",
            day1.isoformat(),
            resp_officer,
            f"{county_main.upper()} SHERIFF'S OFFICE — HOMICIDE BUREAU\n"
            f"INITIAL SCENE & RESPONDING OFFICER REPORT\n"
            f"Case: {case_num} | Location: {venue_name}, {scene_addr}\n"
            f"Incident Date: {day0.isoformat()}–{day1.isoformat()} | Prepared: {day1.isoformat()} 08:15 hrs by {resp_officer}\n\n"
            f"At {t_disc} hrs on {day1.isoformat()}, I responded to {venue_name}, {scene_addr}, on a 911 report of an unresponsive employee. "
            f"{q_doc01_victim}\n{q_doc01_weapon}\n{q_doc01_disc}\n"
            f"{q_doc01_latch} {q_doc01_blinds}\n"
            f"No forced entry was observed at exterior doors. {q_doc01_cam}\n"
            f"Received: {day1.isoformat()} 09:40 hrs · Records Clerk {prop_clerk}\n{_bates(case_num, 1)}",
        ),
        (
            "doc02",
            f"ME autopsy summary: {victim_name} ({me_start_24} to {me_end_24})",
            "report",
            day_me.isoformat(),
            me_doctor,
            f"OFFICE OF THE COUNTY MEDICAL EXAMINER — {county_main.upper()}\n"
            f"AUTOPSY SUMMARY REPORT | Case: {case_num} | Decedent: {victim_name} (Age {victim_age})\n"
            f"Examined: {day_me.isoformat()} by {me_doctor}, Deputy Chief Medical Examiner\n\n"
            f"{q_doc02_cause}\n{q_doc02_manner}\n{q_doc02_window}\n"
            f"Gastric examination reflects a shift meal consumed approximately two hours prior to the window start. "
            f"{q_doc02_annex}\n{_bates(case_num, 2)}",
        ),
        (
            "doc03",
            f"Statement of {insider_name} ({venue['insider_role']})",
            "statement",
            day1.isoformat(),
            insider_name,
            f"{county_main.upper()} HOMICIDE — SWORN WITNESS STATEMENT\n"
            f"Case: {case_num} | Deponent: {insider_name}, age {insider_age}, {venue['insider_role']}\n"
            f"Date: {day1.isoformat()} | Started: 11:10 hrs | Ended: 11:52 hrs | Interviewer: {lead_inv}\n"
            f"Rights Advisement: Voluntary witness interview, read back and signed.\n\n"
            f"Q: Walk us through your rounds on the night of {day0.isoformat()}.\n"
            f"A: I came on at 21:00 and walked hourly checks. {q_doc03_never}\n"
            f"Q: What did you notice around 23:00?\n"
            f"A: {q_doc03_dark}\n"
            f"Q: Any recent schedule changes between you and {victim_name}?\n"
            f"A: {q_doc03_hours} I wasn't happy about the cut, sure, but I did my job.\n"
            f"Signed: {insider_name} · Witnessed: {lead_inv}\n{_bates(case_num, 3)}",
        ),
        (
            "doc04",
            f"Shift logbook page of {insider_name}, {day0.isoformat()}",
            "record",
            day0.isoformat(),
            insider_name,
            f"CERTIFIED TRUE COPY — FACILITY NIGHT SHIFT LOGBOOK\n"
            f"Case: {case_num} | Facility: {venue_name} | Shift Date: {day0.isoformat()}–{day1.isoformat()}\n"
            f"Handwriting verified as {insider_name}.\n\n"
            f"21:00 — On duty. Perimeter secure.\n"
            f"22:00 — Corridor round completed. All normal.\n"
            f"{q_doc04_2300}\n"
            f"{q_doc04_check}\n"
            f"{t_ins_round2} — Corridor round completed. Quiet.\n"
            f"06:00 — Shift relieved.\n"
            f"{q_doc04_margin}\n{_bates(case_num, 4)}",
        ),
        (
            "doc05",
            f"Electronic keypad log and PIN roster, {venue['office_name']}",
            "record",
            day1.isoformat(),
            "Access Control System Export",
            f"CERTIFIED TECHNICAL EXPORT — DOOR ACCESS CONTROLLER & ROSTER\n"
            f"Case: {case_num} | Door: {venue_name} — {venue['office_name']}\n"
            f"Exported: {day1.isoformat()} 10:20 hrs | {q_doc05_header}\n\n"
            f"{q_doc05_codes}\n{q_doc05_collision}\n\n"
            f"Event Audit ({day0.isoformat()}–{day1.isoformat()}):\n"
            f"{q_doc05_drift}\n"
            f"{q_doc05_relief}\n"
            f"{doc05_tail}\n{_bates(case_num, 5)}",
        ),
        (
            "doc06",
            f"Statement of {relief_name} ({venue['relief_role']})",
            "statement",
            day1.isoformat(),
            relief_name,
            f"{county_main.upper()} HOMICIDE — VOLUNTARY WALK-IN STATEMENT\n"
            f"Case: {case_num} | Deponent: {relief_name} ({venue['relief_role']}) | Date: {day1.isoformat()} 14:05 hrs\n"
            f"Interviewer: {lead_inv} | Statement read back: Yes.\n\n"
            f"I wanted to come in before anyone had to track me down. {q_doc06_visit} "
            f"I never shared PIN {code_relief} with anyone.\n"
            f"Signed: {relief_name}\n{_bates(case_num, 6)}",
        ),
        (
            "doc07",
            f"First statement of {rh_name}, {day_me.isoformat()}",
            "statement",
            day_me.isoformat(),
            rh_name,
            f"{county_main.upper()} HOMICIDE — INTERVIEW TRANSCRIPT (YEAR 1)\n"
            f"Case: {case_num} | Subject: {rh_name} ({venue['rh_role']}) | Date: {day_me.isoformat()} 15:30 hrs\n"
            f"Interviewer: {lead_inv} | Rights advised & waived: Yes.\n\n"
            f"Q: Where were you on the night of {day0.isoformat()}?\n"
            f"A: {q_doc07_lie} Yes, {victim_name} and I had an ugly legal dispute, everybody knows that, "
            f"but I stayed in {county_adj} all evening.\n"
            f"Signed: {rh_name}\n{_bates(case_num, 7)}",
        ),
        (
            "doc08",
            f"Second statement of {rh_name}, {day_rh2.isoformat()}",
            "statement",
            day_rh2.isoformat(),
            rh_name,
            f"{county_main.upper()} HOMICIDE — SUPPLEMENTAL INTERVIEW (COUNSEL PRESENT)\n"
            f"Case: {case_num} | Subject: {rh_name} | Date: {day_rh2.isoformat()} 10:15 hrs | Interviewer: {lead_inv}\n\n"
            f"Subject was shown certified gantry and fuel cardlock record (Doc 09).\n"
            f"A: {q_doc08_admit} {q_doc08_reason}\n"
            f"Signed: {rh_name}\n{_bates(case_num, 8)}",
        ),
        (
            "doc09",
            f"ALPR gantry and fuel cardlock record for {rh_name}",
            "record",
            day0.isoformat(),
            f"{corridor_name} Toll & Co-op Authority",
            f"SUBPOENA RETURN — AUTOMATED PLATE READER & CARDLOCK TELEMETRY\n"
            f"Case: {case_num} | Custodian Certification #ALPR-{inc_year}-882\n\n"
            f"{q_doc09_in}\n{q_doc09_out}\n{q_doc09_pump}\n{_bates(case_num, 9)}",
        ),
        (
            "doc10",
            f"Carrier telecom summary for {victim_name}'s handset",
            "record",
            day0.isoformat(),
            "Regional Wireless Subpoena Compliance",
            f"CERTIFIED CARRIER CALL & SMS DETAIL SUMMARY\n"
            f"Case: {case_num} | Subscriber: {victim_name} | Handset recovered on scene (Item 2)\n\n"
            f"{day0.isoformat()} 19:40 — Incoming voice call from sibling, duration 248s.\n"
            f"{q_doc10_sms}\n"
            f"No outgoing user-initiated calls or texts occurred after {t_sms}.\n{_bates(case_num, 10)}",
        ),
        (
            "doc11",
            f"Electric utility sub-meter record, {venue_name}",
            "record",
            day1.isoformat(),
            f"{county_main} Power & Light Custodian",
            f"UTILITY METERING COMPLIANCE RECORD — {county_main.upper()} POWER & LIGHT\n"
            f"Case: {case_num} | Service Address: {venue_name}, {scene_addr}\n\n"
            f"{q_doc11_meter}\n{_bates(case_num, 11)}",
        ),
        (
            "doc12",
            f"First statement of {drift_name}, {day1.isoformat()}",
            "statement",
            day1.isoformat(),
            drift_name,
            f"{county_main.upper()} HOMICIDE — WITNESS STATEMENT (INITIAL)\n"
            f"Case: {case_num} | Witness: {drift_name} ({venue['drift_role']}) | Date: {day1.isoformat()} 16:10 hrs\n\n"
            f"{q_doc12_y1} I did owe {victim_name} $300 on a payroll advance, which was coming out of Friday's check.\n"
            f"Signed: {drift_name}\n{_bates(case_num, 12)}",
        ),
        (
            "doc13",
            f"Cold-case follow-up statement of {drift_name}, {day_cold.isoformat()}",
            "statement",
            day_cold.isoformat(),
            drift_name,
            f"{county_main.upper()} COLD CASE UNIT — RE-INTERVIEW STATEMENT\n"
            f"Case: {case_num} | Witness: {drift_name} | Date: {day_cold.isoformat()} 13:20 hrs | Interviewer: {lead_inv}\n\n"
            f"It has been years, so I am doing my best on exact minutes. {q_doc13_y7} I never came back that night.\n"
            f"Signed: {drift_name}\n{_bates(case_num, 13)}",
        ),
        (
            "doc14",
            f"Cold-case investigative memo: uncollected {t_photo} photo & canvass",
            "report",
            day_cold.isoformat(),
            lead_inv,
            f"{county_main.upper()} COLD CASE UNIT — CASE FILE AUDIT MEMORANDUM\n"
            f"Case: {case_num} | Prepared: {day_cold.isoformat()} by {lead_inv} (incorporating {day_memo.isoformat()} note)\n\n"
            f"1. Uncollected Witness Photograph: {q_doc14_photo}\n"
            f"2. Late Spousal Canvass: {q_doc14_spouse}\n"
            f"3. Exterior Camera Audit: The exterior camera noted in Doc 01 ({q_doc01_cam}) has no subpoena return in the binder.\n"
            f"{_bates(case_num, 14)}",
        ),
        (
            "doc15",
            f"Property clerk evidence ledger, {case_num}",
            "ledger",
            day1.isoformat(),
            prop_clerk,
            f"PROPERTY CLERK MASTER EVIDENCE LEDGER & CHAIN OF CUSTODY\n"
            f"Case: {case_num} | Custodian: {prop_clerk} | Opened: {day1.isoformat()}\n\n"
            f"{q_doc15_item1}\n{q_doc15_item2}\n{q_doc15_item3}\n{q_doc15_item4}\n"
            f"End of booked items. No digital patron photograph or exterior camera media booked.\n{_bates(case_num, 15)}",
        ),
        (
            "doc16",
            f"Public county safety inspection ({day_insp.year}) and press clipping",
            "report",
            day_news.isoformat(),
            "County Archives / County Herald",
            f"PUBLIC RECORD & MEDIA ATTACHMENT — CASE {case_num}\n\n"
            f"Part A — Prior Public Docket:\n{q_doc16_insp}\n\n"
            f"Part B — Press Rumor Attachment:\n{q_doc16_press}\n{_bates(case_num, 16)}",
        ),
    ]

    documents: list[dict[str, Any]] = [
        {
            "id": did,
            "file": f"{did}.txt",
            "title": title,
            "type": dtype,
            "date": ddate,
            "author": dauthor,
            "text": dtext,
        }
        for (did, title, dtype, ddate, dauthor, dtext) in raw_docs
    ]
    docs_by_id = {d["id"]: d for d in documents}

    # ---------------- Build 11 Verified Chair Outputs ----------------
    custody_out = {
        "documents": [
            {
                "doc_id": d["id"],
                "type": d["type"],
                "legible": True,
                "custody_note": f"{d['type'].capitalize()} '{d['title']}' authored by {d['author']}, dated {d['date']} ({case_num}).",
            }
            for d in documents
        ]
    }

    records_out = {
        "subject": victim_name,
        "starter_items": [
            {"item": f"State vital-statistics death index entry for {victim_name} around {day1.isoformat()}", "source_class": "death index", "label": "UNVERIFIED"},
            {"item": f"Published obituary and next-of-kin notices for {victim_name} in {county_main}", "source_class": "obituary and funeral notices", "label": "UNVERIFIED"},
            {"item": f"County Herald archive clippings covering {venue_name} ({day_news.isoformat()})", "source_class": "newspaper archives", "label": "UNVERIFIED"},
            {"item": f"{county_main} and {county_adj} civil/family docket filings involving {victim_name} and {rh_name} (maintaining separation between {departed_emp} and {collision_stranger})", "source_class": "court portals", "label": "UNVERIFIED"},
            {"item": f"Public address and household enumeration history for {victim_name} (age {victim_age})", "source_class": "census schedules", "label": "UNVERIFIED"},
        ],
        "request_next": [
            f"Certified county death certificate and full autopsy toxicology annex for {victim_name} (referenced in doc02).",
            f"Civil dispute docket between {victim_name} and {rh_name} in {county_adj} (referenced in doc07 and doc08).",
            f"Separate identity verification confirming former employee {departed_emp} is distinct from {collision_stranger} (doc05).",
        ],
    }

    coroner_out = {
        "cause": venue["cause"],
        "manner": "homicide",
        "death_window": {
            "start": me_iso_start,
            "end": me_iso_end,
            "quote": q_doc02_window,
            "doc_id": "doc02",
        },
        "medical_facts": [
            {"fact": f"Decedent {victim_name} (age {victim_age}) was found unresponsive on the floor of the {venue['office_name']}.", "quote": q_doc01_victim, "doc_id": "doc01"},
            {"fact": f"Cause of death was determined to be {venue['cause']}.", "quote": q_doc02_cause, "doc_id": "doc02"},
            {"fact": "Manner of death is classified as homicide.", "quote": q_doc02_manner, "doc_id": "doc02"},
            {"fact": f"Medical Examiner set the time-of-death window from {me_start_24} on {day0.isoformat()} to {me_end_24} on {day1.isoformat()}.", "quote": q_doc02_window, "doc_id": "doc02"},
            {"fact": "Biological trace swab Item 3 was sealed for laboratory submission while toxicology annex remained pending.", "quote": q_doc02_annex, "doc_id": "doc02"},
        ],
        "medical_flags": [],
    }

    csi_out = {
        "ledger": [
            {"item_no": 1, "description": f"Crime scene digital exposure set (18 frames), {venue['office_name']}", "quote": q_doc15_item1, "doc_id": "doc15"},
            {"item_no": 2, "description": f"Victim's mobile handset recovered from {venue['office_name']} desk", "quote": q_doc15_item2, "doc_id": "doc15"},
            {"item_no": 3, "description": f"Sealed biological trace swab from interior door lever and {venue['weapon_short']} (untested)", "quote": q_doc15_item3, "doc_id": "doc15"},
            {"item_no": 4, "description": venue["disc_one"], "quote": q_doc15_item4, "doc_id": "doc15"},
        ],
        "gaps": [
            {
                "item": f"Second {venue['disc_label']} at marker 5 (count discrepancy: 2 observed vs. 1 logged)",
                "mentioned_in": ["doc01", "doc15"],
                "problem": f"Scene report doc01 observes two {venue['disc_label']} at markers 4 and 5, whereas Property Clerk ledger doc15 logs only one (1) at marker 4; marker 5 never entered custody.",
                "quote": q_doc01_disc,
                "doc_id": "doc01",
            },
            {
                "item": f"Patron's {t_photo} original digital photograph file with EXIF metadata",
                "mentioned_in": ["doc14", "doc15"],
                "problem": "Shown to investigator on a handset in Year 1 showing the office window lit behind closed blinds, but original digital file and EXIF metadata were never collected or logged in doc15.",
                "quote": q_doc14_photo,
                "doc_id": "doc14",
            },
            {
                "item": f"Scene object ({venue['weapon_short']}) standalone property receipt",
                "mentioned_in": ["doc01", "doc15"],
                "problem": f"Observed beside the desk in doc01 and swabbed under Item 3 in doc15, but the physical {venue['weapon_short']} itself has no separate item entry in doc15.",
                "quote": q_doc01_weapon,
                "doc_id": "doc01",
            },
        ],
    }

    # Intake
    intake_claims = [
        {"person": insider_name, "claim": f"Never entered the {venue['office_name']} that night and only checked the handle from the corridor.", "quote": q_doc03_never, "doc_id": "doc03", "kind": "whereabouts"},
        {"person": insider_name, "claim": f"At 23:00 the {venue['office_name']} was dark and quiet, and no vehicles entered the lot after 22:00.", "quote": q_doc03_dark, "doc_id": "doc03", "kind": "observation"},
        {"person": insider_name, "claim": f"Logged checking the {venue['office_name']} door from the corridor as secure at {t_ins_entry}.", "quote": q_doc04_check, "doc_id": "doc04", "kind": "action"},
        {"person": relief_name, "claim": f"Returned around {t_relief_code} using PIN {code_relief}, saw {victim_name} alive at the desk, and left after two minutes.", "quote": q_doc06_visit, "doc_id": "doc06", "kind": "whereabouts"},
        {"person": rh_name, "claim": f"In Year 1 claimed playing cards in {county_adj} from 20:30 to 01:15 and never going near {venue_name}.", "quote": q_doc07_lie, "doc_id": "doc07", "kind": "whereabouts"},
        {"person": rh_name, "claim": f"In Year 2 admitted sitting in {venue_name} lot around 23:02–23:14, seeing dark blinds, crossing back into {county_adj}, and fueling at {t_rh_cardlock}.", "quote": q_doc08_admit, "doc_id": "doc08", "kind": "whereabouts"},
        {"person": drift_name, "claim": f"In Year 1 stated clocking out at {t_drift_y1} and saying goodnight through the closed door before driving home.", "quote": q_doc12_y1, "doc_id": "doc12", "kind": "whereabouts"},
        {"person": drift_name, "claim": "In cold-case review stated leaving around 22:00 and speaking with the victim outside the office by the supply alcove.", "quote": q_doc13_y7, "doc_id": "doc13", "kind": "action"},
        {"person": drift_spouse, "claim": f"First interviewed in {day_cold.year}, stated {drift_name} arrived home before 23:00.", "quote": q_doc14_spouse, "doc_id": "doc14", "kind": "whereabouts"},
    ]

    intake_events = [
        {"what": f"Public county safety inspection documented that {venue['latch_defect']}.", "when_text": day_insp.isoformat(), "when_window": day_insp.isoformat(), "where": venue_name, "who": [], "quote": q_doc16_insp, "doc_id": "doc16"},
        {"what": f"Keypad unlock with {drift_name}'s PIN {code_drift}.", "when_text": f"{day0.isoformat()} {t_drift_code}", "when_window": f"{day0.isoformat()}T{t_drift_code}", "where": venue["office_name"], "who": [drift_name], "quote": q_doc05_drift, "doc_id": "doc05"},
        {"what": f"{drift_name} initial departure account ({t_drift_y1} through closed door) vs. later ~22:00 supply-alcove account.", "when_text": t_drift_y1, "when_window": f"{day0.isoformat()}T22:00/{day0.isoformat()}T22:15", "where": venue_name, "who": [drift_name, victim_name], "quote": q_doc12_y1, "doc_id": "doc12"},
        {"what": f"Medical Examiner time-of-death window ({me_start_24} to {me_end_24}).", "when_text": f"between {me_start_24} ({me_start_12}) on {day0.isoformat()} and {me_end_24} ({me_end_12}) on {day1.isoformat()}", "when_window": f"{me_iso_start}/{me_iso_end}", "where": venue["office_name"], "who": [victim_name], "quote": q_doc02_window, "doc_id": "doc02"},
        {"what": f"{relief_name} unlocked {venue['office_name']} with PIN {code_relief} and spoke briefly with {victim_name} alive.", "when_text": f"{day0.isoformat()} {t_relief_code}", "when_window": f"{day0.isoformat()}T{t_relief_code}", "where": venue["office_name"], "who": [relief_name, victim_name], "quote": q_doc05_relief, "doc_id": "doc05"},
        {"what": f"ALPR logged {rh_name}'s {rh_veh_model} ({rh_plate}) southbound toward {venue_name}.", "when_text": f"{day0.isoformat()} {t_rh_in}", "when_window": f"{day0.isoformat()}T{t_rh_in}", "where": corridor_name, "who": [rh_name], "quote": q_doc09_in, "doc_id": "doc09"},
        {"what": f"{insider_name} logged 23:00 round claiming {venue['office_name']} was dark.", "when_text": "23:00", "when_window": f"{day0.isoformat()}T23:00", "where": venue_name, "who": [insider_name], "quote": q_doc04_2300, "doc_id": "doc04"},
        {"what": f"ALPR logged {rh_name}'s {rh_veh_model} northbound away from {venue_name}, followed by {t_rh_cardlock} fuel purchase 16.2 miles north.", "when_text": f"{day0.isoformat()} {t_rh_out}", "when_window": f"{day0.isoformat()}T{t_rh_out}/{day0.isoformat()}T{t_rh_cardlock}", "where": f"{corridor_name} / {county_adj}", "who": [rh_name], "quote": q_doc09_out, "doc_id": "doc09"},
        {"what": f"Uncollected patron phone photo taken at {t_photo} described as showing {venue['office_name']} lit behind closed blinds.", "when_text": f"{t_photo} on {day0.isoformat()}", "when_window": f"{day0.isoformat()}T{t_photo}", "where": venue_name, "who": [], "quote": q_doc14_photo, "doc_id": "doc14"},
        {"what": f"Outgoing SMS transmitted from {victim_name}'s handset to sibling at {t_sms}.", "when_text": f"{day0.isoformat()} {t_sms}", "when_window": f"{day0.isoformat()}T{t_sms}", "where": venue["office_name"], "who": [victim_name], "quote": q_doc10_sms, "doc_id": "doc10"},
    ]
    if not is_holdout:
        intake_events.extend([
            {"what": f"Keypad unlock at {venue['office_name']} using {victim_name}'s PIN {code_victim}.", "when_text": f"{day0.isoformat()} {t_vic_code}", "when_window": f"{day0.isoformat()}T{t_vic_code}", "where": venue["office_name"], "who": [victim_name], "quote": q_doc05_vic, "doc_id": "doc05"},
            {"what": f"Keypad unlock at {venue['office_name']} using master PIN {code_master} (issued to {insider_name}) at same minute {insider_name} logged corridor-only door check.", "when_text": f"{day1.isoformat()} {t_ins_entry}", "when_window": f"{day1.isoformat()}T{t_ins_entry}", "where": venue["office_name"], "who": [insider_name], "quote": q_doc05_ins, "doc_id": "doc05"},
            {"what": f"AMI sub-meter active load on {venue['circuit_name']} dropped to 18W standby at {t_meter_drop}.", "when_text": f"{t_meter_drop} on {day1.isoformat()}", "when_window": f"{day1.isoformat()}T{t_meter_drop}", "where": venue["office_name"], "who": [], "quote": q_doc11_meter, "doc_id": "doc11"},
        ])
    else:
        intake_events.extend([
            {"what": f"Door access controller suffered CMOS battery fault 0x04 at {t_batt_fault}; subsequent events on unpulled vendor archive reel.", "when_text": f"{day0.isoformat()} {t_batt_fault}", "when_window": f"{day0.isoformat()}T{t_batt_fault}", "where": venue["office_name"], "who": [], "quote": q_doc05_fault, "doc_id": "doc05"},
            {"what": f"{insider_name} logged checking {venue['office_name']} door handle from corridor at {t_ins_entry}.", "when_text": t_ins_entry, "when_window": f"{day1.isoformat()}T{t_ins_entry}", "where": venue["office_name"], "who": [insider_name], "quote": q_doc04_check, "doc_id": "doc04"},
        ])
    intake_events.append(
        {"what": f"{resp_officer} responded to 911 report and found {victim_name} in {venue['office_name']}.", "when_text": f"{t_disc} hrs on {day1.isoformat()}", "when_window": f"{day1.isoformat()}T{t_disc}", "where": venue_name, "who": [resp_officer, victim_name], "quote": q_doc01_victim, "doc_id": "doc01"}
    )

    intake_out = {
        "persons": [
            {"name": victim_name, "aliases": [], "role": f"Victim; {venue['victim_role']} at {venue_name}"},
            {"name": insider_name, "aliases": [], "role": f"{venue['insider_role'].capitalize()} on night duty (assigned master PIN {code_master})"},
            {"name": relief_name, "aliases": [], "role": f"{venue['relief_role'].capitalize()} (assigned PIN {code_relief})"},
            {"name": rh_name, "aliases": [], "role": f"{venue['rh_role'].capitalize()} of the victim"},
            {"name": drift_name, "aliases": [], "role": f"{venue['drift_role'].capitalize()} at {venue_name} (assigned PIN {code_drift})"},
            {"name": drift_spouse, "aliases": [], "role": f"Spouse of {drift_name}, interviewed in {day_cold.year}"},
            {"name": resp_officer, "aliases": [], "role": "Responding sheriff's officer"},
            {"name": lead_inv, "aliases": [], "role": "Investigating homicide detective"},
            {"name": me_doctor, "aliases": [], "role": "Deputy Chief Medical Examiner"},
        ],
        "claims": intake_claims,
        "events": intake_events,
        "evidence_items": [
            {"description": "18 crime scene digital exposures", "doc_id": "doc15", "status": "logged"},
            {"description": f"Victim's mobile handset recovered from {venue['office_name']} desk", "doc_id": "doc15", "status": "logged"},
            {"description": "Sealed biological trace swab from interior door lever and scene artifact (Item 3)", "doc_id": "doc15", "status": "logged"},
            {"description": venue["disc_one"], "doc_id": "doc15", "status": "logged"},
            {"description": f"Second {venue['disc_label']} observed at marker 5", "doc_id": "doc01", "status": "mentioned"},
            {"description": venue["weapon_short"], "doc_id": "doc01", "status": "mentioned"},
            {"description": f"Uncollected {t_photo} patron smartphone photograph of lit {venue['office_name']} window", "doc_id": "doc14", "status": "mentioned"},
        ],
    }

    # Analyst
    analyst_events = []
    for idx, ev in enumerate(intake_events, start=1):
        in_win = any(
            tok in ev["when_window"]
            for tok in (me_iso_start, f"T{t_relief_code}", f"T{t_rh_in}", "T23:00", f"T{t_rh_out}", f"T{t_photo}", f"T{t_sms}", f"T{t_vic_code}", f"T{t_ins_entry}", f"T{t_meter_drop}", f"T{t_batt_fault}")
        )
        analyst_events.append({
            "id": f"evt_{idx:02d}",
            "what": ev["what"],
            "window": ev["when_window"],
            "where": ev["where"],
            "who": ev["who"],
            "in_window": in_win,
            "sources": [{"quote": ev["quote"], "doc_id": ev["doc_id"]}],
        })

    analyst_collisions = [
        {
            "event_ids": ["evt_06", "evt_08"],
            "who_or_what": f"{rh_name} ({rh_veh_color} {rh_veh_model}, plate {rh_plate})",
            "explanation": f"{rh_name}'s Year-1 statement places him in {county_adj} all evening away from {venue_name}, colliding with {corridor_name} ALPR crossings at {t_rh_in} and {t_rh_out} and his Year-2 admission.",
            "quotes": [
                {"quote": q_doc07_lie, "doc_id": "doc07"},
                {"quote": q_doc09_in, "doc_id": "doc09"},
                {"quote": q_doc09_out, "doc_id": "doc09"},
                {"quote": q_doc08_admit, "doc_id": "doc08"},
            ],
        },
        {
            "event_ids": ["evt_03"],
            "who_or_what": f"{drift_name} departure sequence",
            "explanation": f"{drift_name}'s Year-1 statement places departure at {t_drift_y1} speaking through the closed door, whereas the {day_cold.year} interview shifts departure to around 22:00 speaking face-to-face by the supply alcove.",
            "quotes": [
                {"quote": q_doc12_y1, "doc_id": "doc12"},
                {"quote": q_doc13_y7, "doc_id": "doc13"},
            ],
        },
    ]
    if not is_holdout:
        analyst_collisions.append({
            "event_ids": ["evt_12", "evt_13"],
            "who_or_what": f"{insider_name} / Master PIN {code_master} and {venue['circuit_name']}",
            "explanation": f"{insider_name} states he never entered the {venue['office_name']} and logged it dark at 23:00 and hallway-checked at {t_ins_entry}, colliding with master PIN {code_master} unlocking the door at {t_ins_entry} and active sub-circuit power draw until {t_meter_drop}.",
            "quotes": [
                {"quote": q_doc03_never, "doc_id": "doc03"},
                {"quote": q_doc04_check, "doc_id": "doc04"},
                {"quote": q_doc05_ins, "doc_id": "doc05"},
                {"quote": q_doc11_meter, "doc_id": "doc11"},
            ],
        })
    analyst_out = {"events": analyst_events, "collisions": analyst_collisions}

    # Digital
    machine_events = [
        {"what": f"Keypad PIN {code_relief} unlock ({relief_name})", "when_text": f"{day0.isoformat()} {t_relief_code}", "proves": f"Proves PIN {code_relief} unlocked the {venue['office_name']} strike at {t_relief_code}; cannot prove exit time because the controller does not log exits.", "quote": q_doc05_relief, "doc_id": "doc05"},
        {"what": f"ALPR southbound & northbound gantry hits + {county_adj} cardlock fuel swipe for {rh_plate}", "when_text": f"{day0.isoformat()} {t_rh_in} to {t_rh_cardlock}", "proves": f"Proves {rh_name}'s {rh_veh_model} crossed toward {venue_name} at {t_rh_in}, exited north at {t_rh_out}, and fueled 16.2 miles north at {t_rh_cardlock} with zero return crossings.", "quote": q_doc09_pump, "doc_id": "doc09"},
        {"what": f"Outgoing SMS from {victim_name}'s handset", "when_text": f"{day0.isoformat()} {t_sms}", "proves": f"Proves {victim_name}'s handset sent an outgoing SMS at {t_sms}, establishing survival floor 28 minutes after {rh_name} crossed north; carrier summary alone cannot prove physical typist without handset lock analysis.", "quote": q_doc10_sms, "doc_id": "doc10"},
    ]
    record_checks = [
        {"claim": f"{rh_name} claimed in doc07 he never left {county_adj} on {day0.isoformat()}.", "record_says": f"Doc09 ALPR logs plate {rh_plate} crossing toward {venue_name} at {t_rh_in} and back into {county_adj} at {t_rh_out}, while fueling 16.2 miles north at {t_rh_cardlock} prior to {victim_name}'s {t_sms} SMS.", "quote": q_doc09_in, "doc_id": "doc09"},
        {"claim": f"{relief_name} volunteered entering on PIN {code_relief} around {t_relief_code}.", "record_says": f"Doc05 confirms PIN {code_relief} unlocked the door at {t_relief_code}, though no exit timestamp is logged.", "quote": q_doc05_relief, "doc_id": "doc05"},
    ]
    if not is_holdout:
        machine_events.extend([
            {"what": f"Keypad PIN {code_victim} unlock ({victim_name})", "when_text": f"{day0.isoformat()} {t_vic_code}", "proves": f"Proves PIN {code_victim} unlocked the {venue['office_name']} door at {t_vic_code}, narrowing the survival floor inside the ME window.", "quote": q_doc05_vic, "doc_id": "doc05"},
            {"what": f"Master PIN {code_master} unlock ({insider_name})", "when_text": f"{day1.isoformat()} {t_ins_entry}", "proves": f"Proves master PIN {code_master} unlocked the {venue['office_name']} door at {t_ins_entry}; does not by itself prove footsteps across threshold if someone keyed code from corridor.", "quote": q_doc05_ins, "doc_id": "doc05"},
            {"what": f"AMI 5-minute load drop on {venue['circuit_name']}", "when_text": f"{day1.isoformat()} {t_meter_drop}", "proves": f"Proves office circuit drew 495W–530W continuously until {t_meter_drop} drop to 18W standby.", "quote": q_doc11_meter, "doc_id": "doc11"},
        ])
        record_checks.extend([
            {"claim": f"{insider_name} claimed in doc03 he never entered the {venue['office_name']} and only checked the exterior handle.", "record_says": f"Doc05 records master PIN {code_master} (issued to {insider_name}) unlocking the door strike at {t_ins_entry}.", "quote": q_doc05_ins, "doc_id": "doc05"},
            {"claim": f"{insider_name} claimed in doc03/doc04 the {venue['office_name']} was dark at 23:00.", "record_says": f"Doc11 AMI telemetry shows continuous 495W–530W load until {t_meter_drop}, though closed blinds (doc01) could block exterior light bleed.", "quote": q_doc11_meter, "doc_id": "doc11"},
        ])
    else:
        machine_events.extend([
            {"what": f"Access controller CMOS battery fault 0x04 at {t_batt_fault}", "when_text": f"{day0.isoformat()} {t_batt_fault}", "proves": f"Proves local buffer lost entries after {t_batt_fault}; post-{t_batt_fault} door activity sits on unpulled off-site vendor reel.", "quote": q_doc05_fault, "doc_id": "doc05"},
            {"what": "Utility sub-meter microfilm archival notice", "when_text": f"{day0.isoformat()}–{day1.isoformat()}", "proves": "Proves digital server kept monthly gross totals only; 15-minute interval strip chart remains unpulled in utility microfilm archive.", "quote": q_doc11_meter, "doc_id": "doc11"},
        ])

    digital_out = {
        "machine_events": machine_events,
        "record_checks": record_checks,
        "camera_gaps": [
            {"camera": "Unpulled municipal/adjacent exterior camera facing facility entrance/lot", "mentioned_in": "doc01 and doc14", "quote": q_doc01_cam, "doc_id": "doc01"},
            {"camera": f"Uncollected original {t_photo} patron smartphone photograph file (EXIF unverified)", "mentioned_in": "doc14", "quote": q_doc14_photo, "doc_id": "doc14"},
        ],
    }

    # Cross-Examiner
    contradictions = [
        {
            "a_quote": q_doc07_lie,
            "a_doc": "doc07",
            "b_quote": q_doc09_in,
            "b_doc": "doc09",
            "kind": "alibi_vs_record",
            "severity": "high",
            "innocent_alternative": f"{rh_name} later acknowledged in doc08 concealing his brief 23:02–23:14 lot visit out of concern over his ongoing legal dispute, while doc09 and doc10 corroborate his departure prior to {t_sms}.",
        },
        {
            "a_quote": q_doc12_y1,
            "a_doc": "doc12",
            "b_quote": q_doc13_y7,
            "b_doc": "doc13",
            "kind": "statement_drift",
            "severity": "medium",
            "innocent_alternative": f"Ordinary episodic memory decay and telescoping across the {day_cold.year - inc_year}-year gap between initial and cold-case interviews.",
        },
    ]
    if not is_holdout:
        contradictions.insert(
            0,
            {
                "a_quote": q_doc03_never,
                "a_doc": "doc03",
                "b_quote": q_doc05_ins,
                "b_doc": "doc05",
                "kind": "action_vs_record",
                "severity": "high",
                "innocent_alternative": f"{insider_name} may have keyed master PIN {code_master} at {t_ins_entry} to test the defective latch from the corridor without crossing into the room, or another person knew the master PIN.",
            },
        )
        contradictions.insert(
            1,
            {
                "a_quote": q_doc03_dark,
                "a_doc": "doc03",
                "b_quote": q_doc11_meter,
                "b_doc": "doc11",
                "kind": "observation_vs_record",
                "severity": "high",
                "innocent_alternative": f"Closed window blinds (doc01) may have blocked interior light from the corridor while workstation equipment continued drawing power until {t_meter_drop}.",
            },
        )
        contradictions.append(
            {
                "a_quote": q_doc04_2300,
                "a_doc": "doc04",
                "b_quote": q_doc10_sms,
                "b_doc": "doc10",
                "kind": "logbook_vs_record",
                "severity": "medium",
                "innocent_alternative": f"{insider_name} may have walked near the corridor at {t_sms} between logged hourly entries without recording an interim pass.",
            }
        )

    narrowed_label = (
        f"Narrowed survival window {t_vic_code}–{me_end_24} (within ME window {me_start_24}–{me_end_24})"
        if not is_holdout
        else f"Narrowed survival window {t_sms}–{me_end_24} (within ME window {me_start_24}–{me_end_24})"
    )

    insider_alibi = (
        {
            "person": insider_name,
            "window": narrowed_label,
            "rating": "contradicted",
            "reasons": [
                {"quote": q_doc03_never, "doc_id": "doc03"},
                {"quote": q_doc04_check, "doc_id": "doc04"},
                {"quote": q_doc05_ins, "doc_id": "doc05"},
                {"quote": q_doc05_codes, "doc_id": "doc05"},
                {"quote": q_doc11_meter, "doc_id": "doc11"},
            ],
        }
        if not is_holdout
        else {
            "person": insider_name,
            "window": narrowed_label,
            "rating": "uncorroborated",
            "reasons": [
                {"quote": q_doc03_never, "doc_id": "doc03"},
                {"quote": q_doc04_check, "doc_id": "doc04"},
                {"quote": q_doc05_fault, "doc_id": "doc05"},
                {"quote": q_doc11_meter, "doc_id": "doc11"},
            ],
        }
    )

    alibis = [
        insider_alibi,
        {
            "person": rh_name,
            "window": narrowed_label,
            "rating": "corroborated",
            "reasons": [
                {"quote": q_doc09_out, "doc_id": "doc09"},
                {"quote": q_doc09_pump, "doc_id": "doc09"},
                {"quote": q_doc10_sms, "doc_id": "doc10"},
                {"quote": q_doc08_admit, "doc_id": "doc08"},
            ],
        },
        {
            "person": drift_name,
            "window": narrowed_label,
            "rating": "uncorroborated",
            "reasons": [
                {"quote": q_doc12_y1, "doc_id": "doc12"},
                {"quote": q_doc13_y7, "doc_id": "doc13"},
                {"quote": q_doc14_spouse, "doc_id": "doc14"},
            ],
        },
        {
            "person": relief_name,
            "window": narrowed_label,
            "rating": "uncorroborated",
            "reasons": [
                {"quote": q_doc06_visit, "doc_id": "doc06"},
                {"quote": q_doc05_relief, "doc_id": "doc05"},
            ],
        },
    ]

    ce_gaps = [
        {"item": f"Second {venue['disc_label']} at marker 5", "mentioned_in": ["doc01", "doc15"], "problem": "Observed in doc01 at marker 5 but omitted from Property Clerk ledger doc15."},
        {"item": f"Original {t_photo} patron digital photograph & EXIF metadata", "mentioned_in": ["doc14", "doc15"], "problem": "Never collected or booked into evidence ledger doc15."},
        {"item": "Exterior camera archive & untested biological swab Item 3", "mentioned_in": ["doc01", "doc14", "doc15"], "problem": "Exterior camera never subpoenaed; preserved swab Item 3 never submitted for STR/touch DNA."},
    ]
    if is_holdout:
        ce_gaps.insert(0, {
            "item": "Off-site alarm vendor serial audit backup reel & utility sub-meter microfilm",
            "mentioned_in": ["doc05", "doc11"],
            "problem": f"Local keypad CMOS battery failed at {t_batt_fault} and utility digital billing omitted interval data; archival backups were never pulled.",
        })

    cross_examiner_out = {"contradictions": contradictions, "alibis": alibis, "evidence_gaps": ce_gaps}

    # Interviewer
    next_qs = [
        {
            "person": insider_name,
            "question": (
                f"Your logbook notes checking the {venue['office_name']} door at {t_ins_entry} while doc05 records master PIN {code_master} unlocking the strike at {t_ins_entry}; why was your master PIN entered if you only checked the handle from the corridor?"
                if not is_holdout
                else f"Your logbook records checking the {venue['office_name']} handle at {t_ins_entry}; which corridor route did you walk between 23:30 and {t_ins_round2}, and did anyone else have access to master PIN {code_master}?"
            ),
            "anchored_quote": q_doc05_ins if not is_holdout else q_doc04_check,
            "doc_id": "doc05" if not is_holdout else "doc04",
        },
        {
            "person": drift_name,
            "question": f"In {inc_year} you stated you called goodnight through the closed door at {t_drift_y1}, whereas in {day_cold.year} you recalled speaking with {victim_name} outside the supply alcove around 22:00; what prompted that added recollection?",
            "anchored_quote": q_doc13_y7,
            "doc_id": "doc13",
        },
        {
            "person": rh_name,
            "question": f"When you parked in the {venue_name} lot between {t_rh_in} and {t_rh_out} before crossing back to fuel at {t_rh_cardlock}, did you see any other vehicles or movement near the {venue['office_name']} corridor?",
            "anchored_quote": q_doc08_admit,
            "doc_id": "doc08",
        },
        {
            "person": relief_name,
            "question": f"When you unlocked the {venue['office_name']} with PIN {code_relief} at {t_relief_code}, were the window blinds already drawn shut and did the door latch catch when you exited?",
            "anchored_quote": q_doc06_visit,
            "doc_id": "doc06",
        },
    ]

    interviewer_out = {
        "histories": [
            {
                "person": rh_name,
                "changes": [
                    {
                        "topic": f"Presence at {venue_name} on the night of {day0.isoformat()}",
                        "earlier_quote": q_doc07_lie,
                        "earlier_doc": "doc07",
                        "later_quote": q_doc08_admit,
                        "later_doc": "doc08",
                    }
                ],
            },
            {
                "person": drift_name,
                "changes": [
                    {
                        "topic": "Departure timing and whether victim exited office to speak near supply alcove",
                        "earlier_quote": q_doc12_y1,
                        "earlier_doc": "doc12",
                        "later_quote": q_doc13_y7,
                        "later_doc": "doc13",
                    }
                ],
            },
        ],
        "next_questions": next_qs,
    }

    # Prosecutor
    vetoes = [
        {"phrase": "murder weapon", "reason": "No lab report establishes which physical object inflicted fatal injuries."},
        {"phrase": "killed the victim", "reason": "Names or assumes culpability beyond documentary findings."},
        {"phrase": "stepped inside the office", "reason": "Keypad unlock logs PIN entry at the strike, not footsteps across the threshold."},
        {"phrase": "photo proves", "reason": "Doc14 patron photograph was never collected or authenticated via EXIF."},
        {"phrase": "insider only defect", "reason": "Doc16 public county inspection docket published the latch defect months earlier."},
        {"phrase": "caught lying", "reason": "Characterizes intent rather than stating documentary conflict."},
    ]
    prosecutor_out = {
        "sufficiency": [
            {
                "subject": (
                    f"Master PIN {code_master} unlock at {t_ins_entry} and {t_meter_drop} sub-meter drop vs. {insider_name}'s corridor-only account"
                    if not is_holdout
                    else f"Unverified post-{t_batt_fault} access window due to CMOS battery fault and unpulled vendor archive"
                ),
                "rating": "workable" if not is_holdout else "weak",
                "missing": (
                    "Controller clock calibration, mechanical latch testing, and DNA results from preserved Item 3 swab."
                    if not is_holdout
                    else "Off-site alarm vendor serial audit reel (#doc05), utility 15-minute microfilm strip chart (#doc11), and STR testing on preserved swab Item 3 (#doc15)."
                ),
            },
            {
                "subject": f"{rh_name} narrowed-window exclusion ({t_rh_out} northbound gantry + {t_rh_cardlock} cardlock vs. {t_sms} victim SMS)",
                "rating": "strong",
                "missing": "Handset forensic unlock/auth log confirming victim personally sent the outgoing SMS at doc10.",
            },
            {
                "subject": f"Public latch defect rumor neutralized by {day_insp.year} County Inspection Docket (doc16)",
                "rating": "strong",
                "missing": "None; certified county portal docket predates the incident by nearly one year, defeating any insider-knowledge inference.",
            },
            {
                "subject": f"Physical evidence chain: marker 5 count discrepancy and uncollected {t_photo} photo",
                "rating": "weak",
                "missing": "Property clerk audit accounting for marker 5 and seizure/EXIF verification of original patron image file.",
            },
        ],
        "vetoes": vetoes,
        "corroboration_needed": [
            f"Laboratory STR/touch-DNA profiling of preserved biological swab Item 3 in doc15.",
            f"Original digital file and EXIF timestamp verification for the {t_photo} patron photograph in doc14.",
            f"Property Clerk reconciliation for the unlogged marker 5 item observed in doc01.",
        ] + (
            [f"Subpoena pull of off-site alarm vendor serial audit reel (doc05) and utility 15-minute microfilm strip chart (doc11)."]
            if is_holdout else []
        ),
    }

    # Lead Detective
    if not is_holdout:
        raw_leads = [
            {
                "action": f"Have the detective re-interview {insider_name} in person and ask why master PIN {code_master} unlocked the {venue['office_name']} strike at {t_ins_entry} (doc05) while doc03 denies entering and doc04 logs only a corridor handle check.",
                "arithmetic": "40 + 25 + 15 = 80",
                "reason": f"Directly works the high-severity contradiction between doc03/doc04 and doc05 inside the narrowed {t_vic_code}–{me_end_24} window, and {insider_name} remains reachable.",
                "components": {"cites_high_contradiction": True, "in_window": True, "closes_gap": False, "still_reachable": True},
            },
            {
                "action": f"Have the detective re-interview {insider_name} in person regarding the high-severity contradiction between his 23:00 dark-office claim (doc03) and the AMI sub-meter load continuing until {t_meter_drop} (doc11).",
                "arithmetic": "40 + 25 + 15 = 80",
                "reason": f"Directly works the high-severity contradiction between doc03 and doc11 inside the {me_start_24}–{me_end_24} death window with a reachable witness.",
                "components": {"cites_high_contradiction": True, "in_window": True, "closes_gap": False, "still_reachable": True},
            },
            {
                "action": f"Submit preserved biological trace swab Item 3 from Property Clerk ledger doc15 to the state forensic laboratory for STR and touch-DNA testing.",
                "arithmetic": "25 + 20 + 15 = 60",
                "reason": "Produces the missing forensic lab profile from scene evidence tied to the fatal window, and the sealed item sits in custody.",
                "components": {"cites_high_contradiction": False, "in_window": True, "closes_gap": True, "still_reachable": True},
            },
            {
                "action": f"Obtain from the patron referenced in doc14 the original digital image file and EXIF metadata for the {t_photo} window photograph and book it into doc15.",
                "arithmetic": "25 + 20 + 15 = 60",
                "reason": f"Closes the uncollected {t_photo} photograph gap inside the {me_start_24}–{me_end_24} ME window via a reachable witness record.",
                "components": {"cites_high_contradiction": False, "in_window": True, "closes_gap": True, "still_reachable": True},
            },
            {
                "action": f"Audit Property Clerk custody records and scene exposure frames (doc01 vs. doc15) to locate or account for the second {venue['disc_label']} observed at marker 5.",
                "arithmetic": "20 + 15 = 35",
                "reason": "Closes the CSI marker 5 count discrepancy against a reachable agency property room.",
                "components": {"cites_high_contradiction": False, "in_window": False, "closes_gap": True, "still_reachable": True},
            },
        ]
    else:
        raw_leads = [
            {
                "action": f"Subpoena and pull the off-site alarm vendor's serial audit backup reel referenced in doc05 covering {t_batt_fault} through {me_end_24} to recover post-battery-fault PIN unlocks.",
                "arithmetic": "25 + 20 + 15 = 60",
                "reason": f"Directly closes the post-{t_batt_fault} door-access gap inside the narrowed {t_sms}–{me_end_24} death window from a reachable vendor archive.",
                "components": {"cites_high_contradiction": False, "in_window": True, "closes_gap": True, "still_reachable": True},
            },
            {
                "action": "Submit preserved biological trace swab Item 3 from Property Clerk ledger doc15 to the state forensic laboratory for modern STR and touch-DNA profiling.",
                "arithmetic": "25 + 20 + 15 = 60",
                "reason": "Closes the untested physical DNA gap on Item 3 from the crime scene inside the death window using sealed vault evidence.",
                "components": {"cites_high_contradiction": False, "in_window": True, "closes_gap": True, "still_reachable": True},
            },
            {
                "action": f"Pull unindexed utility microfilm Box referenced in doc11 to obtain 15-minute sub-circuit load strip charts across {me_start_24}–{me_end_24}.",
                "arithmetic": "25 + 20 + 15 = 60",
                "reason": "Closes the missing interval power-draw gap inside the death window from reachable municipal utility archives.",
                "components": {"cites_high_contradiction": False, "in_window": True, "closes_gap": True, "still_reachable": True},
            },
            {
                "action": f"Obtain from the patron referenced in doc14 the original {t_photo} digital photograph file with raw EXIF metadata and book it into doc15.",
                "arithmetic": "25 + 20 + 15 = 60",
                "reason": f"Closes the uncollected {t_photo} photo gap inside the ME window.",
                "components": {"cites_high_contradiction": False, "in_window": True, "closes_gap": True, "still_reachable": True},
            },
            {
                "action": f"Reconcile Property Clerk ledger doc15 against scene report doc01 to account for the unlogged second {venue['disc_label']} at marker 5.",
                "arithmetic": "20 + 15 = 35",
                "reason": "Closes the marker 5 count discrepancy via the reachable property clerk archive.",
                "components": {"cites_high_contradiction": False, "in_window": False, "closes_gap": True, "still_reachable": True},
            },
        ]

    for ld in raw_leads:
        ld["score"] = recompute_score(ld["components"])
    raw_leads.sort(key=lambda x: x["score"], reverse=True)

    lead_gaps = [
        {"gap": f"Marker 5 count discrepancy: two {venue['disc_label']} observed in scene report but only one booked in Property Clerk ledger.", "proven_by": f"doc01 (\"{q_doc01_disc}\") vs. doc15 (\"{q_doc15_item4}\")"},
        {"gap": f"Original digital file and EXIF metadata for the {t_photo} patron photograph were never collected or booked.", "proven_by": f"doc14 (\"{q_doc14_photo}\")"},
        {"gap": "Exterior municipal/commercial camera facing the property was never pulled.", "proven_by": f"doc01 (\"{q_doc01_cam}\")"},
        {"gap": "Preserved biological swab Item 3 remains sealed and untested for STR/touch DNA.", "proven_by": f"doc15 (\"{q_doc15_item3}\")"},
    ]
    if is_holdout:
        lead_gaps.insert(0, {
            "gap": f"Post-{t_batt_fault} door-access serial backup reel and 15-minute utility sub-meter microfilm were never pulled.",
            "proven_by": f"doc05 (\"{q_doc05_fault}\") and doc11 (\"{q_doc11_meter}\")",
        })

    strongest_block = (
        f"STRONGEST CONTRADICTION\n"
        f"{insider_name}'s denial of unlocking or entering the {venue['office_name']} conflicts with the keypad export:\n"
        f"- doc03: \"{q_doc03_never}\"\n"
        f"- doc05: \"{q_doc05_ins}\" (paired with doc05 PIN schedule assigning {code_master} to {insider_name}, and doc11 load drop at {t_meter_drop})."
        if not is_holdout
        else f"STRONGEST CONTRADICTION\n"
        f"No suspect's alibi inside the narrowed {t_sms}–{me_end_24} window is contradicted yet because local keypad memory failed at {t_batt_fault} (doc05). "
        f"The strongest pre-window conflict is {rh_name}'s Year-1 denial vs. ALPR telemetry (resolved in doc08 and cleared of the post-{t_sms} window by doc09/doc10):\n"
        f"- doc07: \"{q_doc07_lie}\"\n"
        f"- doc09: \"{q_doc09_in}\""
    )

    ins_rating_upper = "CONTRADICTED" if not is_holdout else "UNCORROBORATED"
    brief_text = (
        f"THE CASE IN FIVE LINES\n"
        f"1. {victim_name}, {victim_age}, {venue['victim_role']} at {venue_name}, was found unresponsive in the {venue['office_name']} on {day1.isoformat()}; manner is homicide from {venue['cause']} (doc01, doc02).\n"
        f"2. Medical Examiner set the wide window at {me_start_24}–{me_end_24} (doc02), while {victim_name}'s {t_sms} outgoing SMS (doc10)"
        + (f" and {t_vic_code} PIN {code_victim} unlock (doc05) narrow the survival floor to {t_vic_code}–{me_end_24}.\n" if not is_holdout else f" narrows the working survival window to {t_sms}–{me_end_24}.\n")
        + f"3. {rh_name} gave a false Year-1 alibi (doc07) refuted by {t_rh_in}–{t_rh_out} ALPR crossings (doc09), but his {t_rh_out} northbound exit and {t_rh_cardlock} cardlock swipe 16.2 miles away precede {victim_name}'s {t_sms} SMS, corroborating his absence during the narrowed window.\n"
        + f"4. {drift_name}'s departure account shows medium {day_cold.year - inc_year}-year drift (doc12 vs. doc13), and the press rumor regarding the defective latch is neutralized by {day_insp.year} public inspection docket doc16.\n"
        + (
            f"5. Master PIN {code_master} (assigned to {insider_name}) unlocked the {venue['office_name']} at {t_ins_entry} (doc05) and circuit load ran until {t_meter_drop} (doc11), while CSI notes a 2-vs-1 marker 5 discrepancy, an uncollected {t_photo} photo, and an unpulled exterior camera.\n\n"
            if not is_holdout
            else f"5. Local keypad memory failed at {t_batt_fault} (doc05) and utility interval microfilm (doc11) remains unpulled, leaving narrowed-window access uncorroborated alongside a 2-vs-1 CSI discrepancy, uncollected {t_photo} photo, and untested DNA Item 3.\n\n"
        )
        + f"{strongest_block}\n\n"
        + f"ALIBI TABLE ({narrowed_label})\n"
        + f"- {insider_name}: {ins_rating_upper}\n"
        + f"- {rh_name}: CORROBORATED (cleared of narrowed window by doc09 + doc10)\n"
        + f"- {drift_name}: UNCORROBORATED (MEDIUM multi-year drift, doc12 vs. doc13)\n"
        + f"- {relief_name}: UNCORROBORATED ({t_relief_code} entry confirmed by doc05; no exit log)\n\n"
        + f"TOP THREE LEADS\n"
        + f"1. ({raw_leads[0]['score']} pts, {raw_leads[0]['arithmetic']}) {raw_leads[0]['action']}\n"
        + f"2. ({raw_leads[1]['score']} pts, {raw_leads[1]['arithmetic']}) {raw_leads[1]['action']}\n"
        + f"3. ({raw_leads[2]['score']} pts, {raw_leads[2]['arithmetic']}) {raw_leads[2]['action']}\n\n"
        + f"GAP LIST\n"
        + "\n".join(f"- {g['gap']}" for g in lead_gaps)
        + f"\n\n{STANDING_BRIEF_CLOSER}"
    )

    lead_detective_out = {"leads": raw_leads, "gaps": lead_gaps, "brief": brief_text}

    outputs: dict[str, dict[str, Any]] = {
        "custody": custody_out,
        "records": records_out,
        "coroner": coroner_out,
        "csi": csi_out,
        "intake": intake_out,
        "analyst": analyst_out,
        "digital": digital_out,
        "cross_examiner": cross_examiner_out,
        "interviewer": interviewer_out,
        "prosecutor": prosecutor_out,
        "lead_detective": lead_detective_out,
    }

    _assert_zero_drops(docs_by_id, outputs)

    # Build step user inputs matching app/app.js pipeline handoffs (with full statement coverage for Interviewer)
    step_inputs: dict[str, str] = {
        "custody": f"THE REGISTRY:\n{registry_text_block(documents)}\n\nTHE DOCUMENTS:\n{docs_text_block(documents)}",
        "records": f"THE REGISTRY:\n{registry_text_block(documents)}",
        "coroner": docs_text_block(documents, ["doc01", "doc02"]),
        "csi": docs_text_block(documents),
        "intake": docs_text_block(documents),
        "analyst": (
            "INTAKE OUTPUT:\n"
            + json.dumps({"events": intake_out["events"], "claims": intake_out["claims"]}, indent=1, ensure_ascii=False)
            + "\n\nDEATH WINDOW:\n"
            + json.dumps(coroner_out["death_window"], indent=1, ensure_ascii=False)
        ),
        "digital": docs_text_block(documents),
        "cross_examiner": (
            f"THE DOCUMENTS:\n{docs_text_block(documents)}\n\nINTAKE CLAIMS:\n"
            + json.dumps(intake_out["claims"], indent=1, ensure_ascii=False)
            + "\n\nDEATH WINDOW:\n"
            + json.dumps(coroner_out["death_window"], indent=1, ensure_ascii=False)
        ),
        "interviewer": (
            f"THE STATEMENTS:\n{docs_text_block(documents)}\n\nCONTRADICTIONS FOUND:\n"
            + json.dumps(cross_examiner_out["contradictions"], indent=1, ensure_ascii=False)
        ),
        "prosecutor": (
            "THE BOARD:\n"
            + json.dumps(
                {
                    "contradictions": cross_examiner_out["contradictions"],
                    "alibis": cross_examiner_out["alibis"],
                    "csi_gaps": csi_out["gaps"],
                    "ce_gaps": cross_examiner_out["evidence_gaps"],
                    "collisions": analyst_out["collisions"],
                },
                indent=1,
                ensure_ascii=False,
            )
        ),
        "lead_detective": (
            "THE BOARD:\n"
            + json.dumps(
                {
                    "coroner": {
                        "cause": coroner_out["cause"],
                        "manner": coroner_out["manner"],
                        "death_window": coroner_out["death_window"],
                    },
                    "contradictions": cross_examiner_out["contradictions"],
                    "alibis": cross_examiner_out["alibis"],
                    "csi_gaps": csi_out["gaps"],
                    "ce_gaps": cross_examiner_out["evidence_gaps"],
                    "collisions": analyst_out["collisions"],
                    "timeline": analyst_out["events"],
                    "sufficiency": prosecutor_out["sufficiency"],
                    "vetoes": prosecutor_out["vetoes"],
                },
                indent=1,
                ensure_ascii=False,
            )
        ),
    }

    registry = {
        "case_id": case_id,
        "case_number": case_num,
        "case_title": f"The {venue_name} File ({inc_year}) — {venue['label']}",
        "venue_archetype": venue["key"],
        "case_mode": case_mode,
        "documents": [
            {"id": d["id"], "file": d["file"], "title": d["title"], "type": d["type"], "date": d["date"], "author": d["author"]}
            for d in documents
        ],
    }

    ground_truth = {
        "track": "track1_now",
        "domain": DOMAIN,
        "case_id": case_id,
        "case_number": case_num,
        "case_mode": case_mode,
        "venue_archetype": venue["key"],
        "victim": victim_name,
        "insider_poi": insider_name,
        "red_herring": rh_name,
        "drift_witness": drift_name,
        "self_placed_witness": relief_name,
        "collision_pair_do_not_merge": [departed_emp, collision_stranger],
        "me_death_window": {"start": me_iso_start, "end": me_iso_end},
        "death_window": {"start": me_iso_start, "end": me_iso_end},
        "narrowed_working_window": {
            "start": f"{day0.isoformat()}T{t_vic_code if not is_holdout else t_sms}:00",
            "end": me_iso_end,
        },
        "alibi_ratings": {a["person"]: a["rating"] for a in alibis},
        "alibis": {a["person"]: a["rating"] for a in alibis},
        "sufficiency": {s["subject"]: s["rating"] for s in prosecutor_out["sufficiency"]},
        "vetoes": prosecutor_out["vetoes"],
        "expected_lead_scores": [ld["score"] for ld in raw_leads],
        "docs_by_id": {d["id"]: d["text"] for d in documents},
        "public_inspection_neutralizer_doc": "doc16",
        "csi_count_discrepancy_docs": ["doc01", "doc15"],
        "uncollected_exif_photo_doc": "doc14",
        "unpulled_camera_doc": "doc01",
        "top_lead_score": raw_leads[0]["score"],
        "top_lead_action": raw_leads[0]["action"],
        "quote_check_drops": 0,
        "prosecutor_veto_hits": 0,
    }

    return {
        "case_id": case_id,
        "case_title": registry["case_title"],
        "split": split,
        "case_index": case_index,
        "case_mode": case_mode,
        "venue_archetype": venue["key"],
        "documents": documents,
        "registry": registry,
        "outputs": outputs,
        "step_inputs": step_inputs,
        "ground_truth": ground_truth,
    }


def _assert_zero_drops(docs_by_id: dict[str, dict[str, Any]], outputs: dict[str, dict[str, Any]]) -> None:
    """Verify 100% quote_ok pass across all 11 chairs, exact rubric scores, standing closer, and zero vetoes."""
    for step_id, _ in MB_STEPS:
        if step_id not in outputs:
            raise AssertionError(f"Missing step output: {step_id}")

    # 1. custody
    cust_docs = outputs["custody"]["documents"]
    assert len(cust_docs) == len(docs_by_id), "Custody doc count mismatch"
    for d in cust_docs:
        assert d["doc_id"] in docs_by_id, f"Unknown custody doc_id {d['doc_id']}"

    # 2. records
    rec = outputs["records"]
    assert rec["subject"] and rec["starter_items"] and rec["request_next"]
    for it in rec["starter_items"]:
        assert it["label"] == "UNVERIFIED"

    # 3. coroner
    cor = outputs["coroner"]
    dw = cor["death_window"]
    assert quote_ok(dw["quote"], dw["doc_id"], docs_by_id), "Coroner death_window quote failed"
    assert cor["medical_facts"]
    for mf in cor["medical_facts"]:
        assert quote_ok(mf["quote"], mf["doc_id"], docs_by_id), f"Coroner fact quote failed: {mf}"
    for fl in cor.get("medical_flags", []):
        assert quote_ok(fl["claim_quote"], fl["claim_doc"], docs_by_id)
        assert quote_ok(fl["finding_quote"], fl["finding_doc"], docs_by_id)

    # 4. csi
    csi = outputs["csi"]
    assert csi["ledger"] and csi["gaps"]
    for it in csi["ledger"]:
        assert quote_ok(it["quote"], it["doc_id"], docs_by_id), f"CSI ledger quote failed: {it}"
    for g in csi["gaps"]:
        assert quote_ok(g["quote"], g["doc_id"], docs_by_id), f"CSI gap quote failed: {g}"

    # 5. intake
    intake = outputs["intake"]
    assert intake["persons"] and intake["claims"] and intake["events"] and intake["evidence_items"]
    for c in intake["claims"]:
        assert quote_ok(c["quote"], c["doc_id"], docs_by_id), f"Intake claim quote failed: {c}"
    for e in intake["events"]:
        assert quote_ok(e["quote"], e["doc_id"], docs_by_id), f"Intake event quote failed: {e}"

    # 6. analyst
    an = outputs["analyst"]
    assert an["events"] and an["collisions"]
    for e in an["events"]:
        assert e["sources"]
        for s in e["sources"]:
            assert quote_ok(s["quote"], s["doc_id"], docs_by_id), f"Analyst event source quote failed: {s}"
    for col in an["collisions"]:
        assert col["quotes"]
        for q in col["quotes"]:
            assert quote_ok(q["quote"], q["doc_id"], docs_by_id), f"Analyst collision quote failed: {q}"

    # 7. digital
    dig = outputs["digital"]
    for key in ("machine_events", "record_checks", "camera_gaps"):
        assert dig[key], f"Digital {key} empty"
        for it in dig[key]:
            assert quote_ok(it["quote"], it["doc_id"], docs_by_id), f"Digital {key} quote failed: {it}"

    # 8. cross_examiner
    ce = outputs["cross_examiner"]
    assert ce["contradictions"] and ce["alibis"] and ce["evidence_gaps"]
    for c in ce["contradictions"]:
        assert quote_ok(c["a_quote"], c["a_doc"], docs_by_id), f"CE a_quote failed: {c}"
        assert quote_ok(c["b_quote"], c["b_doc"], docs_by_id), f"CE b_quote failed: {c}"
        assert c.get("innocent_alternative", "").strip(), "Missing innocent_alternative"
    for a in ce["alibis"]:
        assert a["rating"] in ("contradicted", "corroborated", "uncorroborated")
        assert a["reasons"]
        for r in a["reasons"]:
            assert quote_ok(r["quote"], r["doc_id"], docs_by_id), f"CE alibi quote failed: {r}"

    # 9. interviewer
    iv = outputs["interviewer"]
    assert iv["histories"] and iv["next_questions"]
    for h in iv["histories"]:
        assert h["changes"]
        for ch in h["changes"]:
            assert quote_ok(ch["earlier_quote"], ch["earlier_doc"], docs_by_id), f"IV earlier_quote failed: {ch}"
            assert quote_ok(ch["later_quote"], ch["later_doc"], docs_by_id), f"IV later_quote failed: {ch}"
    for nq in iv["next_questions"]:
        assert quote_ok(nq["anchored_quote"], nq["doc_id"], docs_by_id), f"IV next_question quote failed: {nq}"

    # 10. prosecutor
    pros = outputs["prosecutor"]
    assert pros["sufficiency"] and pros["vetoes"] and pros["corroboration_needed"]

    # 11. lead_detective
    ld = outputs["lead_detective"]
    assert ld["leads"] and ld["gaps"] and ld["brief"]
    scores = []
    for lead in ld["leads"]:
        expected = recompute_score(lead["components"])
        assert lead["score"] == expected, f"Rubric mismatch: {lead['score']} != {expected}"
        scores.append(lead["score"])
        veto_hits_lead = check_prosecutor_vetoes(f"{lead['action']} {lead['reason']}", pros["vetoes"])
        assert veto_hits_lead == [], f"Prosecutor veto hit in lead: {veto_hits_lead}"
    assert scores == sorted(scores, reverse=True), "Leads not sorted descending by score"
    assert ld["brief"].strip().endswith(STANDING_BRIEF_CLOSER), "Brief missing STANDING_BRIEF_CLOSER"
    veto_hits = check_prosecutor_vetoes(ld["brief"], pros["vetoes"])
    assert veto_hits == [], f"Prosecutor veto hits in brief: {veto_hits}"


@lru_cache(maxsize=64)
def _cached_bundle(split: str, case_index: int, salt: str) -> dict[str, Any]:
    return generate_murder_board_case_bundle(split=split, case_index=case_index, salt=salt)


def generate_murder_board_example(
    split: str,
    index: int,
    salt: str = "mb-spec7-v1",
) -> dict[str, Any]:
    """Map `index // 11` (case) and `index % 11` (chair) into a verified SFT/RLVR training row."""
    prompts = load_mb_agent_prompts()
    case_index = index // len(MB_STEPS)
    step_idx = index % len(MB_STEPS)
    step_id, prompt_file = MB_STEPS[step_idx]

    bundle = _cached_bundle(split, case_index, salt)
    sys_prompt = prompts[prompt_file]
    user_content = bundle["step_inputs"][step_id]
    step_output = copy.deepcopy(bundle["outputs"][step_id])

    gt = copy.deepcopy(bundle["ground_truth"])
    gt["subtask"] = step_id
    gt["step_id"] = step_id
    gt["step_index"] = step_idx
    gt["prompt_file"] = prompt_file
    gt["expected_output"] = step_output
    gt["quote_check_drops"] = 0

    return {
        "id": f"mb_{split}_{index:06d}_{step_id}",
        "track": "track1_now",
        "domain": DOMAIN,
        "subtask": step_id,
        "split": split,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": json.dumps(step_output, indent=2, ensure_ascii=False)},
        ],
        "ground_truth": gt,
    }


def export_playable_cases(
    out_dir: Path,
    count: int,
    salt: str = "mb-spec7-v1",
) -> list[Path]:
    """Export standalone `case_syn_XXXX/` directories (`doc01..doc16.txt`, `registry.json`, `golden_outputs.json`)."""
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    written_dirs: list[Path] = []

    for idx in range(count):
        bundle = generate_murder_board_case_bundle(split="eval_sim", case_index=idx, salt=salt)
        cdir = base / f"case_syn_{idx:04d}"
        cdir.mkdir(parents=True, exist_ok=True)

        for doc in bundle["documents"]:
            (cdir / doc["file"]).write_text(doc["text"] + "\n", encoding="utf-8")

        (cdir / "registry.json").write_text(
            json.dumps(bundle["registry"], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        golden = {
            "case_id": bundle["case_id"],
            "case_mode": bundle["case_mode"],
            "venue_archetype": bundle["venue_archetype"],
            "dropped": 0,
            "outputs": bundle["outputs"],
            "ground_truth": bundle["ground_truth"],
        }
        (cdir / "golden_outputs.json").write_text(
            json.dumps(golden, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        written_dirs.append(cdir)

    return written_dirs
