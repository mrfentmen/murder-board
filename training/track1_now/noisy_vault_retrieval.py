"""Multi-Hop Noisy Vault, Entity Graph & Almanac Retrieval Simulator (`noisy_vault_retrieval.py`).

Trains a desk-bound AI Detective (which cannot interrogate humans directly) to interrogate:
  1. A noisy 80-to-120-document cold-case murder vault (mostly dead-end tips, negative canvasses,
     uninvolved shift cards, and unrelated dispatch logs),
  2. A multi-hop Entity Graph (`Scene -> Vehicle -> Shell LLC / PO Box -> Burner Phone / Alias -> Person`)
     with strict same-name collision warnings (`Records` law), and
  3. A certified Historical Almanac (`almanac_for_night`) exposing peripheral witness premise traps
     (e.g., bright-moonlight visibility claims on 6%-crescent dense-fog nights, or false ballgame /
     last-bus timestamps), alongside Murder-Board public-inspection traps.

Covers both 80% actionable evidence chains and 20% archival-hold cases where a critical subpoenaed
record is missing from the vault and the agent stops cleanly with an exact subpoena pull list.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from typing import Any

from training.common import (
    ALIAS_NICKNAMES,
    COUNTIES,
    HOUSE_RULES_HEADER,
    SHELL_PREFIXES,
    SHELL_SUFFIXES,
    STANDING_BRIEF_CLOSER,
    VEHICLES,
    almanac_for_night,
    check_prosecutor_vetoes,
    fmt_clock,
    make_rng,
    norm_ws,
    quote_ok,
    random_address,
    random_plate,
    sample_unique_names,
)

DOMAIN = "cold_case_vault_retrieval"

TOOLS_VAULT: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_vault",
            "description": (
                "Search the 80–120 document cold-case archive by keywords and optional document type. "
                "Returns top matching document IDs, metadata, and short lexical preview snippets."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Keywords, names, plates, or record terms to search."},
                    "doc_type": {
                        "type": "string",
                        "enum": ["all", "report", "statement", "record", "canvass", "tip", "telecom"],
                        "description": "Optional document category filter (default 'all').",
                    },
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 15, "description": "Max hits to return (default 6)."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_document",
            "description": (
                "Read the full verbatim Bates-stamped text of one primary vault document (plus up to 5 "
                "related document IDs discovered in search or graph results) so exact quotes can be verified."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string", "description": "Primary vault document ID (e.g., 'doc19')."},
                    "additional_doc_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional related document IDs already surfaced by search_vault or query_entity_graph.",
                    },
                },
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_entity_graph",
            "description": (
                "Traverse documented 1-to-3-hop links in the cross-county investigative Entity Graph "
                "(Person <-> Alias/Phone <-> Shell LLC/PO Box <-> Vehicle <-> Scene). Always surfaces "
                "collision_warnings for same-name unlinked residents who must never be merged."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Plate, LLC name, phone number, alias, or person name."},
                    "max_hops": {"type": "integer", "enum": [1, 2, 3], "description": "Graph hop radius (default 3)."},
                },
                "required": ["entity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_almanac",
            "description": (
                "Query certified historical Almanac telemetry for a given night (weather/visibility, lunar "
                "phase & illumination %, sunset, last municipal bus departure, regional ballgame broadcast end)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Incident date in YYYY-MM-DD format."},
                    "category": {
                        "type": "string",
                        "enum": ["all", "astronomy_weather", "transit_schedule", "broadcast_log"],
                        "description": "Almanac slice to check (default 'all').",
                    },
                },
                "required": ["date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "diff_statements",
            "description": (
                "Compare two longitudinal statements from the same witness by document ID, returning "
                "verbatim passages and timestamp/detail shifts across years."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "earlier_doc_id": {"type": "string", "description": "Initial statement doc_id."},
                    "later_doc_id": {"type": "string", "description": "Follow-up cold-case statement doc_id."},
                },
                "required": ["earlier_doc_id", "later_doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_findings",
            "description": (
                "Conclude the desk archive investigation with verbatim-quoted findings, Almanac premise checks, "
                "entity resolution chain, alibi statuses, missing subpoena records (if archival hold), and "
                "a structured proxy_interrogation_funnel question sequence for the human detective."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "case_posture": {
                        "type": "string",
                        "enum": ["ACTIONABLE_EVIDENCE_CHAIN", "ARCHIVAL_HOLD_MISSING_RECORDS"],
                    },
                    "narrowed_working_window": {
                        "type": "object",
                        "properties": {
                            "me_window": {"type": "string"},
                            "working_window": {"type": "string"},
                            "anchor_doc_id": {"type": "string"},
                            "anchor_quote": {"type": "string"},
                        },
                        "required": ["me_window", "working_window", "anchor_doc_id", "anchor_quote"],
                    },
                    "entity_chain": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source": {"type": "string"},
                                "relation": {"type": "string"},
                                "target": {"type": "string"},
                                "doc_id": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                            "required": ["source", "relation", "target", "doc_id", "quote"],
                        },
                    },
                    "almanac_premise_checks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "witness": {"type": "string"},
                                "claim_doc": {"type": "string"},
                                "claim_quote": {"type": "string"},
                                "almanac_fact": {"type": "string"},
                                "status": {"type": "string", "enum": ["REFUTED", "SUPPORTED"]},
                                "innocent_alternative": {"type": "string"},
                            },
                            "required": ["witness", "claim_doc", "claim_quote", "almanac_fact", "status", "innocent_alternative"],
                        },
                    },
                    "contradictions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "a_doc": {"type": "string"},
                                "a_quote": {"type": "string"},
                                "b_doc": {"type": "string"},
                                "b_quote": {"type": "string"},
                                "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                                "innocent_alternative": {"type": "string"},
                            },
                            "required": ["a_doc", "a_quote", "b_doc", "b_quote", "severity", "innocent_alternative"],
                        },
                    },
                    "alibis": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "person": {"type": "string"},
                                "rating": {"type": "string", "enum": ["contradicted", "corroborated", "uncorroborated"]},
                                "doc_id": {"type": "string"},
                                "quote": {"type": "string"},
                            },
                            "required": ["person", "rating", "doc_id", "quote"],
                        },
                    },
                    "missing_subpoena_records": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "record_needed": {"type": "string"},
                                "custodian": {"type": "string"},
                                "proven_by_doc_id": {"type": "string"},
                                "proven_by_quote": {"type": "string"},
                                "what_it_resolves": {"type": "string"},
                            },
                            "required": ["record_needed", "custodian", "proven_by_doc_id", "proven_by_quote", "what_it_resolves"],
                        },
                    },
                    "proxy_interrogation_funnel": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "step_order": {"type": "integer"},
                                "phase": {
                                    "type": "string",
                                    "enum": ["PEACE_OPEN_ACCOUNT", "PERIPHERAL_LOCK", "RECORD_OR_ALMANAC_DISCREPANCY", "INNOCENT_ALTERNATIVE_TEST"],
                                },
                                "target_person": {"type": "string"},
                                "question_for_detective": {"type": "string"},
                                "doc_id": {"type": "string"},
                                "anchored_quote": {"type": "string"},
                                "purpose": {"type": "string"},
                            },
                            "required": ["step_order", "phase", "target_person", "question_for_detective", "doc_id", "anchored_quote", "purpose"],
                        },
                    },
                    "brief_summary": {"type": "string"},
                },
                "required": [
                    "case_posture",
                    "narrowed_working_window",
                    "entity_chain",
                    "almanac_premise_checks",
                    "contradictions",
                    "alibis",
                    "missing_subpoena_records",
                    "proxy_interrogation_funnel",
                    "brief_summary",
                ],
            },
        },
    },
]

VAULT_SYSTEM_PROMPT = f"""{HOUSE_RULES_HEADER}

## Desk Archive & Almanac Investigator (No-Contact Doctrine)

Asking is CONTACT; checking is DESK. You cannot interview witnesses or leave the squad room. Instead, you interrogate the 80–120 document cold-case vault, the cross-county Entity Graph, and the certified Historical Almanac using your tools:
1. Think step-by-step inside `<think>...</think>` before emitting each JSON `{{"tool_call": ...}}`.
2. Decompose dramatic tips and witness accounts into checkable peripheral premises (visibility, lunar phase, weather, broadcast end times, transit schedules, prior public inspections).
3. Never merge same-name residents flagged in `collision_warnings`.
4. Never cite a quote unless you read that exact document during this session. If a critical subpoenaed record was never returned to the vault, stop cleanly, mark `ARCHIVAL_HOLD_MISSING_RECORDS`, and list the exact missing subpoena pulls.
5. End `brief_summary` with the standing line: "{STANDING_BRIEF_CLOSER}"."""

_VENUES = (
    ("Riverside Cold-Chain Annex", "manifest cage"),
    ("Kestrel Dockside Warehouse", "dispatch office"),
    ("Foundry Street Metal Exchange", "settlement office"),
    ("Timberline Freight Transfer", "billing cage"),
    ("Harborview Marine Supply", "inventory office"),
    ("Old Mill Textile Depot", "supervisor office"),
)


def _tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower())}


def _search_vault_exec(
    docs: list[dict[str, Any]],
    query: str,
    doc_type: str = "all",
    top_k: int = 6,
) -> dict[str, Any]:
    q_tokens = _tokenize(query)
    q_low = query.lower().strip()
    scored: list[tuple[float, dict[str, Any]]] = []
    for d in docs:
        if d["id"] == "doc01":
            continue
        if doc_type != "all" and d["type"] != doc_type:
            continue
        hay = f"{d['title']} {d['author']} {d['text']}"
        d_tokens = _tokenize(hay)
        overlap = len(q_tokens & d_tokens)
        phrase_bonus = 3.0 if (len(q_low) >= 5 and q_low in hay.lower()) else 0.0
        title_overlap = len(q_tokens & _tokenize(d["title"])) * 1.6
        score = overlap + title_overlap + phrase_bonus
        if score > 0:
            scored.append((score, d))

    scored.sort(key=lambda x: (-x[0], x[1]["id"]))
    hits = []
    for sc, d in scored[:top_k]:
        body_lines = [ln.strip() for ln in d["text"].splitlines() if ln.strip() and not ln.startswith("[Bates")]
        snippet = " ".join(body_lines[2:4])[:220]
        hits.append({
            "doc_id": d["id"],
            "title": d["title"],
            "type": d["type"],
            "date": d["date"],
            "relevance_score": round(sc, 2),
            "snippet": snippet,
        })
    return {"query": query, "doc_type": doc_type, "total_vault_docs": len(docs), "hits": hits}


def _query_graph_exec(
    edges: list[dict[str, str]],
    collisions: list[dict[str, str]],
    entity: str,
    max_hops: int = 3,
) -> dict[str, Any]:
    frontier = {entity.lower()}
    visited_edges: list[dict[str, str]] = []
    seen_idx: set[int] = set()
    for _ in range(max_hops):
        next_frontier: set[str] = set()
        for idx, e in enumerate(edges):
            s_low, t_low = e["source"].lower(), e["target"].lower()
            if any(f in s_low or s_low in f or f in t_low or t_low in f for f in frontier):
                if idx not in seen_idx:
                    seen_idx.add(idx)
                    visited_edges.append(e)
                next_frontier.add(s_low)
                next_frontier.add(t_low)
        frontier |= next_frontier

    rel_collisions = [
        c for c in collisions
        if any(tok in c["warning"].lower() for f in frontier for tok in f.split() if len(tok) >= 4)
    ] or collisions
    return {
        "queried_entity": entity,
        "max_hops": max_hops,
        "edges": visited_edges,
        "collision_warnings": rel_collisions,
    }


def _assistant_tool_msg(
    call_id: str,
    thought: str,
    name: str,
    arguments: dict[str, Any],
    extra_top_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    call_obj: dict[str, Any] = {"tool_call": {"id": call_id, "name": name, "arguments": arguments}}
    if extra_top_fields:
        call_obj.update(extra_top_fields)
    return {
        "role": "assistant",
        "content": f"<think>\n{thought.strip()}\n</think>\n{json.dumps(call_obj, ensure_ascii=False)}",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
            }
        ],
    }


def _tool_obs_msg(call_id: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": name,
        "content": json.dumps(payload, ensure_ascii=False),
    }


def generate_vault_retrieval_example(
    split: str,
    index: int,
    salt: str = "mb-spec7-v1",
) -> dict[str, Any]:
    """Generate a complete 80–120 doc cold-case vault + 5-to-6 hop investigative trajectory."""
    rng = make_rng(split, DOMAIN, index, salt)
    is_archival_hold = (index % 5) == 4
    use_diff_hop = (index % 3) != 2  # ~67% 6-hop (with diff_statements), ~33% 5-hop (both inside 4..6 hops!)

    vault_size = rng.randint(84, 118)
    venue_name, room_name = _VENUES[(index + len(split)) % len(_VENUES)]
    county_main, county_adj, corridor = COUNTIES[index % len(COUNTIES)]
    scene_addr = random_address(rng)

    inc_year = rng.randint(2015, 2020)
    day0 = _dt.date(inc_year, rng.randint(2, 11), rng.randint(3, 25))
    day1 = day0 + _dt.timedelta(days=1)
    day_insp = day0 - _dt.timedelta(days=rng.randint(250, 390))
    day_cold = _dt.date(inc_year + rng.randint(5, 6), rng.randint(3, 10), rng.randint(4, 24))
    case_num = f"MB-V{inc_year}-{2000 + (index % 7900):04d}"

    almanac = almanac_for_night(rng, day0.isoformat())

    # Cast + disjoint noise names (prevents unintended name collisions outside the explicit collision guard)
    all_people = sample_unique_names(rng, 42)
    cast = all_people[:10]
    used_tokens = {part for full in cast for part in full.split()}
    noise_names = [nm for nm in all_people[10:] if not (set(nm.split()) & used_tokens)] or all_people[10:]
    victim_name = cast[0]
    insider_name = cast[1]
    rival_name = cast[2]         # Red-herring rival blamed by witness, cleared by hard records
    witness_almanac = cast[3]    # Witness whose peripheral observation fights the Almanac
    drift_witness = cast[4]      # Multi-year drift witness
    tip_deadend_name = cast[5]   # Dramatic anonymous tip suspect -> realistic dead-end query!
    resp_ofc = f"Ofc. {cast[6]}"
    det_name = f"Det. {cast[7]}"
    me_doc_author = f"Dr. {cast[8]}"

    insider_first, insider_last = insider_name.split()
    nicks = ALIAS_NICKNAMES.get(insider_first, (f"{insider_first[0]}.J.",))
    insider_alias = f"{nicks[0]} {insider_last}"
    collision_civilian = f"{insider_first} {insider_last} Sr."
    collision_dob = "1949-04-12"
    insider_dob = f"{inc_year - rng.randint(33, 46)}-09-18"

    shell_llc = f"{rng.choice(SHELL_PREFIXES)} {rng.choice(SHELL_SUFFIXES)}"
    po_box = f"PO Box {rng.randint(210, 890)}, {county_adj}"
    burner_phone = f"555-01{rng.randint(12, 97)}"
    scene_veh_model, scene_veh_color, _ = VEHICLES[index % len(VEHICLES)]
    scene_plate = random_plate(rng)
    rival_veh_model, rival_veh_color, _ = VEHICLES[(index + 7) % len(VEHICLES)]
    rival_plate = random_plate(rng)

    # Assign shuffled non-sequential document IDs in doc02..doc{vault_size}
    available_nums = list(range(2, vault_size + 1))
    rng.shuffle(available_nums)
    sig_nums = sorted(available_nums[:11])
    (
        n_tip_deadend,
        n_tip_custody,
        n_me,
        n_survival,
        n_almanac_wit,
        n_rival_clear,
        n_corp_graph,
        n_insider_stmt,
        n_decisive_or_sub,
        n_pub_insp,
        n_collision,
    ) = sig_nums
    n_drift_early = available_nums[11]
    n_drift_late = available_nums[12]

    def did(num: int) -> str:
        return f"doc{num:02d}"

    id_tip_deadend = did(n_tip_deadend)
    id_tip_custody = did(n_tip_custody)
    id_me = did(n_me)
    id_survival = did(n_survival)
    id_almanac_wit = did(n_almanac_wit)
    id_rival_clear = did(n_rival_clear)
    id_corp_graph = did(n_corp_graph)
    id_insider_stmt = did(n_insider_stmt)
    id_decisive = did(n_decisive_or_sub)
    id_pub_insp = did(n_pub_insp)
    id_collision = did(n_collision)
    id_drift_early = did(n_drift_early)
    id_drift_late = did(n_drift_late)

    # Timeline anchors
    me_window_str = f"{day0.isoformat()} 22:00 to {day1.isoformat()} 00:30"
    t_survival = "23:34"
    t_decisive = "23:52"

    # Build Almanac peripheral premise trap guaranteed to conflict with almanac_for_night()
    sky = almanac["sky_mode"]
    if sky in ("heavy_overcast_fog", "clear_new_moon_dark"):
        trap_kind = "lunar_visibility_trap"
        q_wit_trap = (
            f"At 23:12 on {day0.isoformat()}, standing 185 feet across the unlit gravel lot at {venue_name}, I clearly recognized "
            f"{rival_name}'s {rival_veh_color} {rival_veh_model} under bright full moonlight beside the {room_name}."
        )
        almanac_refutation = (
            f"Almanac for {day0.isoformat()} records sky_mode={sky}, moon_illumination_pct={almanac['moon_illumination_pct']}% "
            f"({almanac['moon_phase']}), and unlit_visibility_feet={almanac['unlit_visibility_feet']} ft (< 185 ft claimed)."
        )
        trap_innocent_alt = (
            f"{witness_almanac} may have seen an unidentified vehicle silhouette under a momentary headlamp sweep or confused another clear night with {day0.isoformat()}."
        )
    elif sky == "steady_freezing_rain":
        trap_kind = "precipitation_and_broadcast_trap"
        q_wit_trap = (
            f"Right after the regional ballgame broadcast wrapped up at 20:50 on {day0.isoformat()}, I walked six blocks "
            f"in a dry cotton shirt across bone-dry pavement and saw {rival_name}'s {rival_veh_model} idling outside {venue_name}."
        )
        almanac_refutation = (
            f"Almanac for {day0.isoformat()} records precipitation='{almanac['precipitation']}' (wet freezing rain from 20:15 onward) "
            f"and regional_broadcast_game_end={almanac['regional_broadcast_game_end']} (not 20:50)."
        )
        trap_innocent_alt = (
            f"{witness_almanac} likely conflated a different dry game night with {day0.isoformat()} when recalling the evening."
        )
    else:  # clear_full_moon -> use broadcast + last municipal bus schedule trap!
        trap_kind = "broadcast_and_bus_schedule_trap"
        q_wit_trap = (
            f"I stepped out five minutes after the regional ballgame broadcast ended at 20:45 on {day0.isoformat()} and later "
            f"caught the 23:50 outbound municipal bus past {venue_name}, seeing {rival_name}'s {rival_veh_model} at the curb."
        )
        almanac_refutation = (
            f"Almanac for {day0.isoformat()} proves regional_broadcast_game_end={almanac['regional_broadcast_game_end']} (not 20:45) "
            f"and last_municipal_bus_departure={almanac['last_municipal_bus_departure']} (no 23:50 municipal bus ran that night)."
        )
        trap_innocent_alt = (
            f"{witness_almanac} may have watched a recorded replay or confused private shuttle/ride timing with municipal bus service."
        )

    # Exact verbatim sentences for signal documents
    q_doc01_scene = (
        f"On {day1.isoformat()} at 06:45 hrs, {resp_ofc} responded to {venue_name}, {scene_addr}, where {victim_name} "
        f"was found deceased inside the {room_name}; patrol noted commercial plate {scene_plate} logged on a torn gate slip "
        f"and a street rumor naming {tip_deadend_name}, while an anonymous caller claimed only an insider knew the rear strike latch stuck."
    )
    q_me_win = (
        f"Autopsy Summary ({me_doc_author}): Cause of death is blunt force cranial trauma; manner is homicide; "
        f"estimated death window is {me_window_str} based on core temperature and lividity."
    )
    q_survival = (
        f"Verified Carrier & Terminal Closeout ({day0.isoformat()} {t_survival}): {victim_name}'s authenticated workstation "
        f"and handset transmitted batch closeout #BC-904 and SMS confirmation at {t_survival}, proving {victim_name} was alive at {t_survival}."
    )
    q_rival_clear = (
        f"{corridor} Toll & Hospital Intake Log ({day0.isoformat()}): {rival_name} (plate {rival_plate}) crossed into {county_adj} "
        f"at 22:18 and signed into {county_adj} Urgent Care triage at 22:41 through 01:10, 19 miles from {venue_name}."
    )
    q_corp_chain = (
        f"Commercial Fleet & Corporate Registry Return: Plate {scene_plate} ({scene_veh_color} {scene_veh_model}) is leased to {shell_llc} "
        f"({po_box}), whose billing contact phone {burner_phone} is subscribed under alias '{insider_alias}', verified via W-2 payroll "
        f"as contractor {insider_name} (DOB {insider_dob})."
    )
    q_collision_note = (
        f"County Assessor & Voter File: {collision_civilian} (DOB {collision_dob}), retired postal clerk residing at 412 Birch Ct, "
        f"has no connection to {shell_llc} or {venue_name}; distinct DOB from {insider_name} (DOB {insider_dob})."
    )
    q_insider_denial = (
        f"Sworn Statement of {insider_name} (DOB {insider_dob}): \"I parked the {shell_llc} {scene_veh_model} ({scene_plate}) at my apartment "
        f"by 21:30 on {day0.isoformat()}, stayed home asleep all night, and never entered {venue_name} or used contractor fob #F-774.\""
    )
    if not is_archival_hold:
        q_decisive = (
            f"Certified Security & Gate Telemetry ({venue_name}): At {day0.isoformat()} {t_decisive}, contractor fob #F-774 "
            f"(issued to {insider_name} / {shell_llc}) unlocked the {room_name} inner strike while dock LPR captured plate {scene_plate} exiting at 00:11."
        )
    else:
        q_decisive = (
            f"Subpoena Compliance Ledger (#SUB-{inc_year}-449): Off-site security vendor serial audit tape for contractor fob #F-774 "
            f"and cellular tower dump for {burner_phone} covering {day0.isoformat()} 23:00–00:30 remain PENDING / NEVER RETURNED by custodian "
            f"Apex Alarm Archives Inc. prior to cold-case suspension."
        )
    q_pub_insp = (
        f"County Fire Marshal Public Inspection Docket ({day_insp.isoformat()}, posted on public county website): "
        f"Item 9 cites {venue_name} rear {room_name} strike latch failing to engage automatically; public record predates homicide by {((day0 - day_insp).days)} days."
    )
    q_drift_1 = (
        f"Initial Statement of {drift_witness} ({day1.isoformat()}): \"I finished loading at 21:45, waved to {victim_name} through the glass, and drove straight home.\""
    )
    q_drift_2 = (
        f"Cold-Case Re-Interview of {drift_witness} ({day_cold.isoformat()}): \"I clocked out around 21:25 and spoke briefly with {victim_name} near the breakroom vending machine before leaving.\""
    )

    # Assemble full 80..120 vault
    docs_map: dict[str, dict[str, Any]] = {}
    docs_map["doc01"] = {
        "id": "doc01",
        "title": f"Initial responding officer scene report — {venue_name}",
        "type": "report",
        "date": day1.isoformat(),
        "author": resp_ofc,
        "text": (
            f"{county_main.upper()} SHERIFF — INITIAL SCENE REPORT | Case {case_num}\n"
            f"Prepared: {day1.isoformat()} 07:30 hrs by {resp_ofc}\n\n"
            f"{q_doc01_scene}\n"
            f"All autopsy protocols, telecom returns, witness transcripts, corporate registrations, and canvass cards "
            f"are indexed separately in Murder Book Vault ({vault_size} total documents).\n"
            f"[Bates {case_num}-DOC001 · LAW ENFORCEMENT SENSITIVE]"
        ),
    }

    signal_specs = {
        id_tip_deadend: (
            f"Anonymous tip sheet naming {tip_deadend_name}",
            "tip",
            day1.isoformat(),
            "Tip Line Desk",
            f"ANONYMOUS TIP SHEET | Case {case_num}\nCaller claimed {tip_deadend_name} bragged at a tavern two months ago about a grudge against {venue_name}. No corroborating detail provided.\n[Bates {case_num}-{id_tip_deadend.upper()}]",
        ),
        id_tip_custody: (
            f"State Department of Corrections custody verification for {tip_deadend_name}",
            "record",
            day1.isoformat(),
            "DOC Records Unit",
            f"CERTIFIED CUSTODY VERIFICATION | Case {case_num}\nState prison count logs confirm {tip_deadend_name} was continuously incarcerated at Central Correctional Facility from {inc_year - 1}-08-14 through {inc_year + 1}-02-01, including {day0.isoformat()}.\n[Bates {case_num}-{id_tip_custody.upper()}]",
        ),
        id_me: (
            f"Medical Examiner autopsy summary — {victim_name}",
            "report",
            (day0 + _dt.timedelta(days=2)).isoformat(),
            me_doc_author,
            f"OFFICE OF THE MEDICAL EXAMINER | Case {case_num}\n{q_me_win}\n[Bates {case_num}-{id_me.upper()}]",
        ),
        id_survival: (
            f"Carrier SMS and workstation closeout telemetry — {victim_name}",
            "telecom",
            day1.isoformat(),
            "Telecom & IT Compliance",
            f"CERTIFIED TELECOM & TERMINAL LOG | Case {case_num}\n{q_survival}\n[Bates {case_num}-{id_survival.upper()}]",
        ),
        id_almanac_wit: (
            f"Witness statement of {witness_almanac} regarding {rival_name}'s vehicle",
            "statement",
            (day0 + _dt.timedelta(days=3)).isoformat(),
            witness_almanac,
            f"SWORN WITNESS STATEMENT — {witness_almanac.upper()} | Case {case_num}\nInterviewed by {det_name}.\n\"{q_wit_trap}\"\n[Bates {case_num}-{id_almanac_wit.upper()}]",
        ),
        id_rival_clear: (
            f"Toll gantry and {county_adj} Urgent Care intake record — {rival_name}",
            "record",
            day1.isoformat(),
            f"{county_adj} Records Custodian",
            f"CERTIFIED ALPR & MEDICAL INTAKE RECORD | Case {case_num}\n{q_rival_clear}\n[Bates {case_num}-{id_rival_clear.upper()}]",
        ),
        id_corp_graph: (
            f"Fleet registration & corporate billing return — {shell_llc} / plate {scene_plate}",
            "record",
            (day0 + _dt.timedelta(days=6)).isoformat(),
            "Secretary of State & DMV Subpoena Unit",
            f"CORPORATE & FLEET SUBPOENA RETURN | Case {case_num}\n{q_corp_chain}\n[Bates {case_num}-{id_corp_graph.upper()}]",
        ),
        id_insider_stmt: (
            f"Sworn interview statement of contractor {insider_name}",
            "statement",
            (day0 + _dt.timedelta(days=5)).isoformat(),
            insider_name,
            f"WITNESS / CONTRACTOR INTERVIEW — {insider_name.upper()} | Case {case_num}\n{q_insider_denial}\n[Bates {case_num}-{id_insider_stmt.upper()}]",
        ),
        id_decisive: (
            (
                f"Certified fob #F-774 door controller and dock LPR log — {venue_name}"
                if not is_archival_hold
                else f"Subpoena compliance status log (#SUB-{inc_year}-449) — {venue_name}"
            ),
            "record",
            (day0 + _dt.timedelta(days=8)).isoformat(),
            "Security Custodian" if not is_archival_hold else "Subpoena Control Clerk",
            f"TECHNICAL RECORD CUSTODY ENTRY | Case {case_num}\n{q_decisive}\n[Bates {case_num}-{id_decisive.upper()}]",
        ),
        id_pub_insp: (
            f"County Fire Marshal public inspection docket ({day_insp.year}) — {venue_name}",
            "record",
            day_insp.isoformat(),
            "County Fire Marshal",
            f"PUBLIC SAFETY DOCKET | Case {case_num}\n{q_pub_insp}\n[Bates {case_num}-{id_pub_insp.upper()}]",
        ),
        id_collision: (
            f"Public voter & assessor identity sheet — {collision_civilian}",
            "record",
            day1.isoformat(),
            "County Records Clerk",
            f"NAME COLLISION CHECK | Case {case_num}\n{q_collision_note}\n[Bates {case_num}-{id_collision.upper()}]",
        ),
        id_drift_early: (
            f"Initial shift statement of {drift_witness} ({inc_year})",
            "statement",
            day1.isoformat(),
            drift_witness,
            f"INITIAL EMPLOYEE STATEMENT | Case {case_num}\n{q_drift_1}\n[Bates {case_num}-{id_drift_early.upper()}]",
        ),
        id_drift_late: (
            f"Cold-case follow-up statement of {drift_witness} ({day_cold.year})",
            "statement",
            day_cold.isoformat(),
            drift_witness,
            f"COLD-CASE FOLLOW-UP STATEMENT | Case {case_num}\n{q_drift_2}\n[Bates {case_num}-{id_drift_late.upper()}]",
        ),
    }

    for k, (title, dtype, ddate, author, text) in signal_specs.items():
        docs_map[k] = {"id": k, "title": title, "type": dtype, "date": ddate, "author": author, "text": text}

    # Fill remaining 70–105 slots with realistic cold-case murder-book noise
    noise_templates = (
        ("canvass", "Neighborhood door-to-door canvass card", "Canvass Team", "Resident at {addr} stated household slept with bedroom AC running from 21:15 to 06:10 on {d0} and observed zero pedestrians or vehicles."),
        ("record", "Day-shift employee timecard batch", "Payroll Clerk", "Morning shift employee {person} clocked in at 07:30 the day prior and was off-schedule throughout the evening of {d0}."),
        ("report", "County CAD unrelated dispatch summary", "Communications Bureau", "Unit 42 cleared false commercial burglar alarm at {addr} ({plate}) at 20:12 on {d0}; unrelated to {county} homicide scene."),
        ("tip", "Unverified telephone tip log entry", "Tip Desk", "Caller reported a {plate} sedan parked near a grocery store 9 miles west on {d0}; patrol check confirmed local baker on routine shift."),
        ("telecom", "Payphone & lobby extension zero-traffic return", "Carrier Desk", "Lobby courtesy line at {addr} recorded zero outgoing or incoming connections between 19:00 on {d0} and 07:00 on {d1}."),
        ("canvass", "Adjacent business CCTV retention negative note", "Canvass Team", "Dry cleaner at {addr} confirmed analog VHS recorder had no tape inserted during the week of {d0}; checked negative."),
    )
    for num in range(2, vault_size + 1):
        k = did(num)
        if k in docs_map:
            continue
        ntype, ntitle_base, nauthor, nbody_t = noise_templates[num % len(noise_templates)]
        nperson = noise_names[num % len(noise_names)]
        naddr = random_address(rng)
        nplate = random_plate(rng)
        docs_map[k] = {
            "id": k,
            "title": f"{ntitle_base} #{num:03d} ({naddr})",
            "type": ntype,
            "date": day1.isoformat(),
            "author": nauthor,
            "text": (
                f"{county_main.upper()} ARCHIVE FILE | Case {case_num} | Doc {k}\n"
                + nbody_t.format(addr=naddr, d0=day0.isoformat(), d1=day1.isoformat(), person=nperson, plate=nplate, county=county_main)
                + f"\n[Bates {case_num}-{k.upper()}]"
            ),
        }

    vault_docs = [docs_map[did(i)] for i in range(1, vault_size + 1)]
    all_docs_by_id = {d["id"]: d for d in vault_docs}

    # 3-Hop Entity Graph edges (`Scene -> Vehicle -> Shell LLC / PO Box -> Burner Phone / Alias -> Person`)
    graph_edges = [
        {"source": f"Scene ({venue_name})", "relation": "gate_slip_vehicle", "target": f"Vehicle ({scene_plate}, {scene_veh_color} {scene_veh_model})", "doc_id": "doc01"},
        {"source": f"Vehicle ({scene_plate}, {scene_veh_color} {scene_veh_model})", "relation": "leased_to_entity", "target": f"LLC ({shell_llc}, {po_box})", "doc_id": id_corp_graph},
        {"source": f"LLC ({shell_llc}, {po_box})", "relation": "billing_contact_phone", "target": f"Phone ({burner_phone})", "doc_id": id_corp_graph},
        {"source": f"Phone ({burner_phone})", "relation": "registered_alias", "target": f"Alias ({insider_alias})", "doc_id": id_corp_graph},
        {"source": f"Alias ({insider_alias})", "relation": "w2_verified_person", "target": f"Person ({insider_name}, DOB {insider_dob})", "doc_id": id_corp_graph},
        {"source": f"Person ({insider_name}, DOB {insider_dob})", "relation": "sworn_statement_on_file", "target": id_insider_stmt, "doc_id": id_insider_stmt},
        {"source": f"Person ({insider_name}, DOB {insider_dob})", "relation": "fob_or_subpoena_record", "target": id_decisive, "doc_id": id_decisive},
    ]
    collision_warnings = [
        {
            "entity_a": f"{insider_name} (DOB {insider_dob})",
            "entity_b": f"{collision_civilian} (DOB {collision_dob})",
            "doc_id": id_collision,
            "warning": f"COLLISION GUARD: {collision_civilian} (DOB {collision_dob}, {id_collision}) is a retired postal clerk distinct from contractor {insider_name} (DOB {insider_dob}). Never merge.",
        }
    ]

    # Turn 0 User message: ONLY doc01 + unsearched vault metadata
    type_counts: dict[str, int] = {}
    for d in vault_docs:
        type_counts[d["type"]] = type_counts.get(d["type"], 0) + 1

    user_turn0 = (
        f"CASE VAULT INITIALIZATION — {case_num}\n"
        f"Incident Night: {day0.isoformat()} into {day1.isoformat()} | Venue: {venue_name}\n"
        f"Catalogued Vault Size: {vault_size} documents ({json.dumps(type_counts, sort_keys=True)})\n"
        f"Status: Unsearched cold-case archive. Only Initial Scene Report (doc01) is open on desk.\n\n"
        f"===== doc01 ({docs_map['doc01']['title']}, {docs_map['doc01']['date']}) =====\n"
        f"{docs_map['doc01']['text']}"
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": VAULT_SYSTEM_PROMPT},
        {"role": "user", "content": user_turn0},
    ]
    discovered_ids: set[str] = {"doc01"}
    retrieved_docs: dict[str, dict[str, Any]] = {"doc01": docs_map["doc01"]}

    # --- HOP 1: Realistic Dead-End Query on `tip_deadend_name` from doc01 ---
    h1_args = {"query": f"{tip_deadend_name} grudge tip custody", "doc_type": "all", "top_k": 5}
    h1_obs = _search_vault_exec(vault_docs, **h1_args)
    for h in h1_obs["hits"]:
        discovered_ids.add(h["doc_id"])
    messages.append(_assistant_tool_msg(
        "call_01",
        f"doc01 notes three initial leads at {venue_name}: a street rumor naming {tip_deadend_name}, commercial plate {scene_plate} on a gate slip, and a claim about a stuck rear strike latch. First, let's check the vault for {tip_deadend_name} so we do not tunnel-vision on or ignore the street rumor.",
        "search_vault",
        h1_args,
    ))
    messages.append(_tool_obs_msg("call_01", "search_vault", h1_obs))

    # --- HOP 2: 3-Hop Entity Graph Traversal from `scene_plate` ---
    h2_args = {"entity": scene_plate, "max_hops": 3}
    h2_obs = _query_graph_exec(graph_edges, collision_warnings, **h2_args)
    for e in h2_obs["edges"]:
        discovered_ids.add(e["doc_id"])
        if e["target"].startswith("doc"):
            discovered_ids.add(e["target"])
    for c in h2_obs["collision_warnings"]:
        discovered_ids.add(c["doc_id"])
    messages.append(_assistant_tool_msg(
        "call_02",
        f"Search results on {tip_deadend_name} ({id_tip_deadend}, {id_tip_custody}) show an uncorroborated tavern rumor refuted by certified DOC prison logs proving {tip_deadend_name} was incarcerated on {day0.isoformat()}—that rumor is a dead end. Next, let's traverse the Entity Graph around gate-slip plate {scene_plate} up to 3 hops to resolve ownership, shell entities, aliases, and any name-collision warnings.",
        "query_entity_graph",
        h2_args,
    ))
    messages.append(_tool_obs_msg("call_02", "query_entity_graph", h2_obs))

    # --- HOP 3: Targeted Vault Search Using Only Known Scene Entities (`victim_name`, `venue_name`, `strike latch`) ---
    h3_query = f"{victim_name} {venue_name} autopsy closeout witness statement toll intake inspection strike latch"
    h3_args = {"query": h3_query, "doc_type": "all", "top_k": 12}
    h3_obs = _search_vault_exec(vault_docs, **h3_args)
    for h in h3_obs["hits"]:
        discovered_ids.add(h["doc_id"])
    messages.append(_assistant_tool_msg(
        "call_03",
        f"The Entity Graph resolves plate {scene_plate} -> {shell_llc} ({po_box}) -> phone {burner_phone} -> alias '{insider_alias}' -> contractor {insider_name} (with linked docs {id_corp_graph}, {id_insider_stmt}, {id_decisive}), while flagging {collision_civilian} ({id_collision}) as a distinct retired postal clerk we must never merge. Next, let's search the vault around {victim_name} and {venue_name} for the autopsy window, closeout telemetry, witness statements, and any inspection docket on the rear strike latch.",
        "search_vault",
        h3_args,
    ))
    messages.append(_tool_obs_msg("call_03", "search_vault", h3_obs))

    # --- HOP 4: Read Full Verbatim Documents Discovered in Hops 2 & 3 ---
    to_read = [id_me, id_survival, id_almanac_wit, id_rival_clear, id_corp_graph, id_insider_stmt, id_decisive, id_pub_insp]
    for r_id in to_read:
        assert r_id in discovered_ids, f"Causal violation: {r_id} not yet discovered!"
    h4_args = {"doc_id": to_read[0], "additional_doc_ids": to_read[1:]}
    h4_obs = {
        "documents": [
            {"doc_id": rid, "title": all_docs_by_id[rid]["title"], "date": all_docs_by_id[rid]["date"], "text": all_docs_by_id[rid]["text"]}
            for rid in to_read
        ]
    }
    for rid in to_read:
        retrieved_docs[rid] = all_docs_by_id[rid]
    messages.append(_assistant_tool_msg(
        "call_04",
        f"Both search_vault and query_entity_graph surfaced the core load-bearing records ({', '.join(to_read)}). Let's read their full verbatim texts before checking any peripheral witness claims against the Almanac.",
        "read_document",
        h4_args,
    ))
    messages.append(_tool_obs_msg("call_04", "read_document", h4_obs))

    # --- HOP 5: Check Almanac against Witness Peripheral Premise ---
    h5_args = {"date": day0.isoformat(), "category": "all"}
    h5_obs = almanac
    messages.append(_assistant_tool_msg(
        "call_05",
        f"In {id_almanac_wit}, {witness_almanac} makes specific environmental/schedule claims placing {rival_name}'s {rival_veh_model} at the scene, even though {id_rival_clear} logs {rival_name} in {county_adj} Urgent Care from 22:41 to 01:10 and {id_survival} proves {victim_name} was alive at {t_survival}. Let's run check_almanac for {day0.isoformat()} to test {witness_almanac}'s peripheral premise directly.",
        "check_almanac",
        h5_args,
    ))
    messages.append(_tool_obs_msg("call_05", "check_almanac", h5_obs))

    # --- OPTIONAL HOP 6 (~67%): Longitudinal Statement Diff (`diff_statements`) ---
    contradictions_out: list[dict[str, str]] = []
    if use_diff_hop and id_drift_early in discovered_ids and id_drift_late in discovered_ids:
        h6_args = {"earlier_doc_id": id_drift_early, "later_doc_id": id_drift_late}
        retrieved_docs[id_drift_early] = all_docs_by_id[id_drift_early]
        retrieved_docs[id_drift_late] = all_docs_by_id[id_drift_late]
        h6_obs = {
            "earlier_doc_id": id_drift_early,
            "earlier_date": all_docs_by_id[id_drift_early]["date"],
            "earlier_text": all_docs_by_id[id_drift_early]["text"],
            "later_doc_id": id_drift_late,
            "later_date": all_docs_by_id[id_drift_late]["date"],
            "later_text": all_docs_by_id[id_drift_late]["text"],
            "summary_delta": "Departure shifted from 21:45 (wave through glass) to ~21:25 (conversation near breakroom vending machine).",
        }
        messages.append(_assistant_tool_msg(
            "call_06",
            f"The Almanac refutes {witness_almanac}'s peripheral observation ({almanac_refutation}). Before concluding, let's run diff_statements on {drift_witness}'s {inc_year} and {day_cold.year} statements ({id_drift_early} vs. {id_drift_late}) surfaced in Hop 3 to evaluate statement drift.",
            "diff_statements",
            h6_args,
        ))
        messages.append(_tool_obs_msg("call_06", "diff_statements", h6_obs))
        contradictions_out.append({
            "a_doc": id_drift_early,
            "a_quote": q_drift_1,
            "b_doc": id_drift_late,
            "b_quote": q_drift_2,
            "severity": "medium",
            "innocent_alternative": f"Normal episodic memory drift across {day_cold.year - inc_year} years prior to the {t_survival} survival floor.",
        })

    # Assemble verified submit_findings arguments
    contradictions_out.insert(
        0,
        {
            "a_doc": id_almanac_wit,
            "a_quote": q_wit_trap,
            "b_doc": id_rival_clear,
            "b_quote": q_rival_clear,
            "severity": "high",
            "innocent_alternative": trap_innocent_alt,
        },
    )
    if not is_archival_hold:
        contradictions_out.insert(
            0,
            {
                "a_doc": id_insider_stmt,
                "a_quote": q_insider_denial,
                "b_doc": id_decisive,
                "b_quote": q_decisive,
                "severity": "high",
                "innocent_alternative": f"Another individual with access to {shell_llc} vehicle {scene_plate} and fob #F-774 may have entered at {t_decisive} without {insider_name}'s participation.",
            },
        )

    posture = "ARCHIVAL_HOLD_MISSING_RECORDS" if is_archival_hold else "ACTIONABLE_EVIDENCE_CHAIN"
    insider_rating = "uncorroborated" if is_archival_hold else "contradicted"

    missing_subs = (
        [
            {
                "record_needed": f"Off-site vendor serial audit tape for contractor fob #F-774 and cellular tower dump for {burner_phone} ({day0.isoformat()} 23:00–00:30)",
                "custodian": "Apex Alarm Archives Inc. & Regional Wireless Subpoena Compliance",
                "proven_by_doc_id": id_decisive,
                "proven_by_quote": q_decisive,
                "what_it_resolves": f"Tests whether fob #F-774 or phone {burner_phone} accessed {venue_name} inside the narrowed {t_survival}–00:30 survival window.",
            }
        ]
        if is_archival_hold
        else []
    )

    funnel = [
        {
            "step_order": 1,
            "phase": "PEACE_OPEN_ACCOUNT",
            "target_person": insider_name,
            "question_for_detective": f"Walk through your complete evening routine and movements from 20:00 on {day0.isoformat()} until 01:00 on {day1.isoformat()} in your own words.",
            "doc_id": id_insider_stmt,
            "anchored_quote": q_insider_denial,
            "purpose": "Establish an uncontaminated free-recall timeline before introducing corporate or electronic records.",
        },
        {
            "step_order": 2,
            "phase": "PERIPHERAL_LOCK",
            "target_person": insider_name,
            "question_for_detective": f"Who held physical custody of the {shell_llc} {scene_veh_model} ({scene_plate}), contractor fob #F-774, and billing phone {burner_phone} that night?",
            "doc_id": id_corp_graph,
            "anchored_quote": q_corp_chain,
            "purpose": "Lock exclusive possession or identify any third-party user before disclosing scene logs.",
        },
        {
            "step_order": 3,
            "phase": "RECORD_OR_ALMANAC_DISCREPANCY",
            "target_person": insider_name if not is_archival_hold else witness_almanac,
            "question_for_detective": (
                f"Gate and door telemetry ({id_decisive}) records fob #F-774 unlocking the {room_name} at {t_decisive} and plate {scene_plate} exiting at 00:11; how do you account for those logs alongside your {id_insider_stmt} statement?"
                if not is_archival_hold
                else f"Certified Almanac records for {day0.isoformat()} document those exact visibility/schedule conditions; what specific cue led you to identify that vehicle in {id_almanac_wit}?"
            ),
            "doc_id": id_decisive if not is_archival_hold else id_almanac_wit,
            "anchored_quote": q_decisive if not is_archival_hold else q_wit_trap,
            "purpose": "Present verified machine or Almanac fact neutrally without accusation.",
        },
        {
            "step_order": 4,
            "phase": "INNOCENT_ALTERNATIVE_TEST",
            "target_person": insider_name,
            "question_for_detective": f"Was there any authorized maintenance callout, shared fob cabinet, or dispatch handoff involving {shell_llc} between {t_survival} and 00:30?",
            "doc_id": "doc01",
            "anchored_quote": q_doc01_scene,
            "purpose": "Explicitly test innocent explanations for the vehicle slip and fob record.",
        },
    ]

    brief_summary = (
        f"Vault review ({vault_size} docs, case {case_num}) narrows the ME window ({me_window_str}, {id_me}) to {day0.isoformat()} {t_survival}–00:30 via {victim_name}'s authenticated {t_survival} closeout ({id_survival}). "
        f"Witness {witness_almanac}'s statement ({id_almanac_wit}) is refuted by the Historical Almanac ({almanac_refutation}), and {rival_name} is corroborated outside the narrowed window by {county_adj} Urgent Care and toll records ({id_rival_clear}). "
        f"Prior public inspection {id_pub_insp} neutralizes the 'insider-only' latch rumor, and {collision_civilian} ({id_collision}) remains strictly separated from contractor {insider_name}. "
        + (
            f"Multi-hop graph resolution links scene plate {scene_plate} -> {shell_llc} -> {burner_phone} -> '{insider_alias}' -> {insider_name} ({id_corp_graph}), whose home-asleep alibi ({id_insider_stmt}) conflicts with fob #F-774 unlocking the {room_name} at {t_decisive} ({id_decisive}). "
            if not is_archival_hold
            else f"While graph resolution links plate {scene_plate} -> {shell_llc} -> {insider_name} ({id_corp_graph}), subpoenaed fob #F-774 and tower records ({id_decisive}) were never returned, requiring an archival hold and subpoena enforcement before any narrowed-window alibi is rated contradicted. "
        )
        + STANDING_BRIEF_CLOSER
    )

    submit_args: dict[str, Any] = {
        "case_posture": posture,
        "narrowed_working_window": {
            "me_window": me_window_str,
            "working_window": f"{day0.isoformat()} {t_survival} to {day1.isoformat()} 00:30",
            "anchor_doc_id": id_survival,
            "anchor_quote": q_survival,
        },
        "entity_chain": [
            {"source": f"Scene ({venue_name})", "relation": "gate_slip_plate", "target": scene_plate, "doc_id": "doc01", "quote": q_doc01_scene},
            {"source": scene_plate, "relation": "leased_to_shell_and_alias_phone", "target": f"{shell_llc} / {burner_phone} / {insider_alias} -> {insider_name}", "doc_id": id_corp_graph, "quote": q_corp_chain},
        ],
        "almanac_premise_checks": [
            {
                "witness": witness_almanac,
                "claim_doc": id_almanac_wit,
                "claim_quote": q_wit_trap,
                "almanac_fact": almanac_refutation,
                "status": "REFUTED",
                "innocent_alternative": trap_innocent_alt,
            }
        ],
        "contradictions": contradictions_out,
        "alibis": [
            {"person": insider_name, "rating": insider_rating, "doc_id": id_decisive if not is_archival_hold else id_insider_stmt, "quote": q_decisive if not is_archival_hold else q_insider_denial},
            {"person": rival_name, "rating": "corroborated", "doc_id": id_rival_clear, "quote": q_rival_clear},
        ],
        "missing_subpoena_records": missing_subs,
        "proxy_interrogation_funnel": funnel,
        "brief_summary": brief_summary,
    }

    quoted_doc_ids = sorted({
        "doc01",
        id_survival,
        id_corp_graph,
        id_almanac_wit,
        id_rival_clear,
        id_insider_stmt,
        id_decisive,
        *([id_drift_early, id_drift_late] if len(contradictions_out) >= (3 if not is_archival_hold else 2) else []),
    })
    final_ans_str = (
        f"insufficient archival records: enforce Subpoena #SUB-{inc_year}-449 for fob #F-774 and phone {burner_phone}"
        if is_archival_hold
        else f"{insider_name} ({insider_alias} / {shell_llc}) contradicted in post-{t_survival} window; {rival_name} corroborated"
    )
    final_call_id = "call_07" if len(contradictions_out) >= (3 if not is_archival_hold else 2) else "call_06"
    messages.append(_assistant_tool_msg(
        final_call_id,
        (
            f"All peripheral premises, multi-hop entity links, collision guards, and machine records are verified across the retrieved documents. "
            + (
                f"Because {id_decisive} documents that subpoenaed fob/tower telemetry was never returned, we must declare ARCHIVAL_HOLD_MISSING_RECORDS, keep {insider_name} uncorroborated, and output the exact missing subpoena list."
                if is_archival_hold
                else f"Fob #F-774 and plate {scene_plate} at {t_decisive}–00:11 ({id_decisive}) directly contradict {insider_name}'s statement ({id_insider_stmt}) inside the post-{t_survival} survival window while {rival_name} is cleared."
            )
        ),
        "submit_findings",
        submit_args,
        extra_top_fields={
            "case_posture": posture,
            "sufficiency_reached": not is_archival_hold,
            "retrieved_doc_ids": quoted_doc_ids,
            "final_answer": final_ans_str,
            "innocent_alternative": contradictions_out[0]["innocent_alternative"],
        },
    ))

    subtask = "vault_multihop_retrieval"
    ground_truth = {
        "track": "track1_now",
        "domain": DOMAIN,
        "subtask": subtask,
        "case_number": case_num,
        "vault_size": vault_size,
        "case_posture": posture,
        "sufficiency_reached": not is_archival_hold,
        "answerable": not is_archival_hold,
        "required_doc_ids": quoted_doc_ids,
        "final_answer": final_ans_str,
        "docs_by_id": {k: v["text"] for k, v in retrieved_docs.items()},
        "trap_kind": trap_kind,
        "victim": victim_name,
        "insider_poi": insider_name,
        "insider_alias": insider_alias,
        "shell_llc": shell_llc,
        "scene_plate": scene_plate,
        "cleared_red_herring": rival_name,
        "dead_end_tip_person": tip_deadend_name,
        "collision_do_not_merge": [insider_name, collision_civilian],
        "signal_doc_ids": {
            "me": id_me,
            "survival": id_survival,
            "almanac_witness": id_almanac_wit,
            "rival_clear": id_rival_clear,
            "corp_graph": id_corp_graph,
            "insider_stmt": id_insider_stmt,
            "decisive_or_subpoena": id_decisive,
            "public_inspection": id_pub_insp,
            "collision": id_collision,
        },
        "almanac": almanac,
        "pre_submit_hops": sum(1 for m in messages if m["role"] == "tool"),
        "quote_check_drops": 0,
    }

    _verify_vault_example(vault_docs, retrieved_docs, messages, submit_args, ground_truth)

    return {
        "id": f"vault_{split}_{index:06d}",
        "track": "track1_now",
        "domain": DOMAIN,
        "subtask": "archival_hold_subpoena_stop" if is_archival_hold else f"multihop_{trap_kind}",
        "split": split,
        "tools": TOOLS_VAULT,
        "messages": messages,
        "ground_truth": ground_truth,
    }


def _verify_vault_example(
    vault_docs: list[dict[str, Any]],
    retrieved_docs: dict[str, dict[str, Any]],
    messages: list[dict[str, Any]],
    submit_args: dict[str, Any],
    ground_truth: dict[str, Any],
) -> None:
    """Verify vault size, Turn-0 isolation, 4..6 pre-submit hops, 0 quote drops against retrieved_docs, and veto safety."""
    assert 80 <= len(vault_docs) <= 120, f"Vault size {len(vault_docs)} outside 80..120"
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert messages[-1]["role"] == "assistant"

    # Turn 0 contains ONLY doc01
    u0 = messages[1]["content"]
    assert "===== doc01 " in u0
    for d in vault_docs[1:]:
        assert f"===== {d['id']} " not in u0, f"Turn 0 leaked {d['id']}"

    tool_turns = [m for m in messages if m["role"] == "tool"]
    assert 4 <= len(tool_turns) <= 6, f"Expected 4..6 pre-submit hops, got {len(tool_turns)}"

    # Verify every assistant message has <think>...</think> + valid JSON tool_call
    for m in messages:
        if m["role"] == "assistant":
            c = m["content"]
            assert c.startswith("<think>\n") and "\n</think>\n" in c
            json_part = c.split("\n</think>\n", 1)[1]
            parsed = json.loads(json_part)
            assert "tool_call" in parsed and "name" in parsed["tool_call"]

    # Zero-drop quote verification strictly against retrieved_docs (cannot quote unread docs!)
    nw = submit_args["narrowed_working_window"]
    assert quote_ok(nw["anchor_quote"], nw["anchor_doc_id"], retrieved_docs), "Window anchor quote failed"

    for link in submit_args["entity_chain"]:
        assert quote_ok(link["quote"], link["doc_id"], retrieved_docs), f"Entity chain quote failed: {link}"

    for ap in submit_args["almanac_premise_checks"]:
        assert quote_ok(ap["claim_quote"], ap["claim_doc"], retrieved_docs), f"Almanac quote failed: {ap}"
        assert ap["innocent_alternative"].strip()

    for c in submit_args["contradictions"]:
        assert quote_ok(c["a_quote"], c["a_doc"], retrieved_docs), f"Contradiction a_quote failed: {c}"
        assert quote_ok(c["b_quote"], c["b_doc"], retrieved_docs), f"Contradiction b_quote failed: {c}"
        assert c["innocent_alternative"].strip()

    for al in submit_args["alibis"]:
        assert quote_ok(al["quote"], al["doc_id"], retrieved_docs), f"Alibi quote failed: {al}"

    for ms in submit_args["missing_subpoena_records"]:
        assert quote_ok(ms["proven_by_quote"], ms["proven_by_doc_id"], retrieved_docs), f"Subpoena quote failed: {ms}"

    assert len(submit_args["proxy_interrogation_funnel"]) >= 3
    for q in submit_args["proxy_interrogation_funnel"]:
        assert quote_ok(q["anchored_quote"], q["doc_id"], retrieved_docs), f"Funnel quote failed: {q}"

    brief = submit_args["brief_summary"]
    assert brief.strip().endswith(STANDING_BRIEF_CLOSER), "Vault brief missing STANDING_BRIEF_CLOSER"
    assert check_prosecutor_vetoes(brief, []) == [], f"Veto hit in vault brief: {check_prosecutor_vetoes(brief, [])}"
    assert ground_truth["quote_check_drops"] == 0
