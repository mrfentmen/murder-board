"""Deterministic RLVR / GRPO Verifiable Reward Suite for Murder Board (SPEC 7).

Compatible out-of-the-box with:
  - Direct Python evaluation: `compute_investigator_reward(prompt_messages, completion_text, ground_truth, docs_by_id=None)`
  - HuggingFace TRL `GRPOTrainer`: `trl_grpo_reward_fn(prompts, completions, ground_truth=..., **kwargs)`
  - ByteDance `verl`: `verl_compute_score(data_source, solution_str, ground_truth, extra_info=None)`
  - `OpenRLHF`: `openrlhf_reward_func(queries, prompts, labels)`

Domain Verifiers Implemented (100% Python 3.15 stdlib, deterministic, zero network):
  1. Murder Board 11 Chairs & Multi-Hop Vault Retrieval
     - Strict JSON + `quote_ok()` across all emitted quotes (`0` hallucinated quotes required for full `+0.35`)
     - Exact alibi / legal sufficiency / Lead Detective `recompute_score()` rubric arithmetic
     - Mandatory `STANDING_BRIEF_CLOSER` on `lead_detective`
     - Hard `-0.5` penalty on any `check_prosecutor_vetoes()` violation
  2. Forensic Micro-Skills (Temporal, NLI, GraphRAG + Collision Guard, Pathology/Re-Test, Tournament)
     - Skew-corrected `iso_windows` & `collision_detected`
     - Strict `SUPPORTED | REFUTED | NOT_ENOUGH_INFORMATION` NLI label
     - GraphRAG `(head, relation, tail)` triples F1 + `DO_NOT_MERGE_COLLISION` homonym safety
     - Pathology / Era-Forensics modern re-test selection (`M-VAC`, `STRmix`, `IGG`, `NIBIN`, etc.)
     - Hypothesis tournament ranking & bias immunity
  3. 911 Panicked & Coerced-Caller Triage
     - Priority match, `coercion_detected` & `silent_approach_required` recall, life-safety trap recall
     - Strict penalty if `next_dispatcher_line` exceeds `18` words
  4. Cartel, TBML & Shell-Company AML Hunter
     - `disposition` (`FILE_SAR_ESCALATE` vs `CLEAR_NO_SAR` false-positive business clearance)
     - Typology match, `tainted_entities` F1, and `cleared_entities` precision
  5. Track 2 Future Room Biometric & Cognitive-Load Co-Pilot (Chair 12)
     - `baseline_adjusted_pattern` accuracy + mandatory `innocent_physiological_alternative`
     - **Othello-Error Cliff (`reward = -1.0`)** if `ground_truth["subject_state"]` is an innocent
       Othello/trauma subject and the completion claims deception/lying/guilt or omits the
       innocent physiological explanation.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any

from training.common.core import (
    STANDING_BRIEF_CLOSER,
    check_prosecutor_vetoes,
    norm_ws,
    quote_ok,
    recompute_score,
)

FORBIDDEN_POLYGRAPH_CLAIMS: tuple[str, ...] = (
    "sweat proves lying",
    "sweat confirms guilt",
    "heartbeat confirms guilt",
    "biometrics prove guilt",
    "heart rate proves he is lying",
    "heart rate proves she is lying",
    "physiological spike proves deception",
    "arousal confirms guilt",
)

_REASONING_BLOCK_RE = re.compile(
    r"<(?:think|triage|reasoning|analysis|audit|scratchpad)>.*?</(?:think|triage|reasoning|analysis|audit|scratchpad)>",
    re.DOTALL | re.IGNORECASE,
)
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL | re.IGNORECASE)
_MB_DOC_BLOCK_RE = re.compile(
    r"=====\s*([^\s(]+)\s*(?:\([^)]*\))?\s*=====\n(.*?)(?=\n=====\s*[^\s(]+|\n### |\Z)",
    re.DOTALL,
)
_TRIPLE_EQ_DOC_BLOCK_RE = re.compile(
    r"===\s*([A-Za-z0-9_.-]+)(?:\s*\([^)]*\))?\s*===\n(.*?)(?=\n===\s*[A-Za-z0-9_.-]+|\n### |\Z)",
    re.DOTALL,
)

_DECEPTION_ASSERTION_RE = re.compile(
    r"\b("
    r"is\s+deceptive|are\s+deceptive|deception\s+detected|deception\s+confirmed|"
    r"indicates?\s+deception|confirms?\s+deception|shows?\s+deception|proves?\s+deception|"
    r"indicates?\s+lying|confirms?\s+lying|shows?\s+guilt|proves?\s+guilt|"
    r"(?:subject|suspect|witness|caller|interviewee|he|she)\s+is\s+lying|"
    r"concealing\s+guilt|hiding\s+guilt|guilty\s+of\s+the"
    r")\b",
    re.IGNORECASE,
)
_NEGATION_GUARD_RE = re.compile(
    r"\b("
    r"not|never|no|neither|nor|cannot|can't|do\s+not|does\s+not|doesn't|"
    r"prohibit\w*|avoid\w*|false|mistak\w*|error|othello|rather\s+than|instead\s+of|without"
    r")\b",
    re.IGNORECASE,
)

_QUOTE_REQUIRED_CHAIRS = frozenset({
    "coroner",
    "03_coroner",
    "csi",
    "04_csi",
    "intake",
    "05_intake",
    "analyst",
    "06_analyst",
    "digital",
    "07_digital",
    "cross_examiner",
    "08_cross_examiner",
    "interviewer",
    "09_interviewer",
    "vault_retrieval",
    "noisy_vault_retrieval",
    "vault_multihop_retrieval",
    "detectiveqa_deduction",
})


# ============================================================================
# Parsing & Normalization Utilities
# ============================================================================


def _coerce_dict(val: Any) -> dict[str, Any]:
    if isinstance(val, dict):
        return val
    if isinstance(val, str) and val.strip():
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


def _unwrap_tool_call_dict(obj: dict[str, Any]) -> dict[str, Any]:
    """If an assistant turn is serialized as a ChatML tool-call dict, unwrap function.arguments."""
    tcs = obj.get("tool_calls")
    if isinstance(tcs, list) and tcs:
        fn = tcs[0].get("function") if isinstance(tcs[0], dict) else None
        if isinstance(fn, dict):
            args = fn.get("arguments")
            if isinstance(args, dict):
                return args
            if isinstance(args, str) and args.strip():
                try:
                    parsed_args = json.loads(args)
                    if isinstance(parsed_args, dict):
                        return parsed_args
                except json.JSONDecodeError:
                    pass
    return obj


def _extract_json_object(completion_text: str | dict[str, Any]) -> dict[str, Any] | None:
    """Extract JSON payload after stripping optional <think>/<triage>/<analysis> tags or ```json fences."""
    if isinstance(completion_text, dict):
        return _unwrap_tool_call_dict(completion_text)
    if not completion_text or not str(completion_text).strip():
        return None
    stripped = _REASONING_BLOCK_RE.sub("", str(completion_text)).strip()
    if not stripped:
        return None

    # 1. Direct strict JSON parse
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return _unwrap_tool_call_dict(obj)
    except json.JSONDecodeError:
        pass

    # 2. Markdown ```json ... ``` block
    m = _FENCED_JSON_RE.search(stripped)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return _unwrap_tool_call_dict(obj)
        except json.JSONDecodeError:
            pass

    # 3. Balanced JSON object scan via JSONDecoder.raw_decode
    decoder = json.JSONDecoder()
    first_brace = stripped.find("{")
    while first_brace != -1:
        try:
            obj, _ = decoder.raw_decode(stripped[first_brace:])
            if isinstance(obj, dict):
                return _unwrap_tool_call_dict(obj)
        except json.JSONDecodeError:
            pass
        first_brace = stripped.find("{", first_brace + 1)

    return None


def _prompt_to_text(prompt_messages: list[dict[str, Any]] | str | None) -> str:
    if prompt_messages is None:
        return ""
    if isinstance(prompt_messages, str):
        return prompt_messages
    chunks: list[str] = []
    for m in prompt_messages:
        if isinstance(m, dict):
            role = str(m.get("role", ""))
            if role in ("user", "tool", "system", ""):
                chunks.append(str(m.get("content", "")))
        else:
            chunks.append(str(m))
    return "\n\n".join(chunks)


def _harvest_docs_from_json_tree(node: Any, out: dict[str, dict[str, Any]]) -> None:
    """Extract {"id"|"doc_id": ..., "text": ...} objects from tool-observation JSON payloads."""
    if isinstance(node, dict):
        d_id = node.get("id") or node.get("doc_id")
        txt = node.get("text")
        if isinstance(d_id, str) and isinstance(txt, str) and len(txt) >= 8:
            out[d_id] = {"id": d_id, "text": txt}
        for v in node.values():
            _harvest_docs_from_json_tree(v, out)
    elif isinstance(node, list):
        for elem in node:
            _harvest_docs_from_json_tree(elem, out)


def _resolve_docs_by_id(
    prompt_messages: list[dict[str, Any]] | str | None,
    ground_truth: dict[str, Any],
    docs_by_id: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    """Resolve document lookup map from explicit arg, ground_truth, tool observations, or prompt blocks."""
    resolved: dict[str, dict[str, Any]] = {}

    source_map = docs_by_id if docs_by_id is not None else ground_truth.get("docs_by_id")
    if isinstance(source_map, str):
        source_map = _coerce_dict(source_map)

    if isinstance(source_map, dict) and source_map:
        for k, v in source_map.items():
            if isinstance(v, dict) and "text" in v:
                resolved[str(k)] = v
            else:
                resolved[str(k)] = {"id": str(k), "text": str(v)}
        return resolved

    doc_list = ground_truth.get("documents") or ground_truth.get("docs")
    if isinstance(doc_list, list) and doc_list:
        for d in doc_list:
            if isinstance(d, dict) and ("id" in d or "doc_id" in d) and "text" in d:
                did = str(d.get("id") or d.get("doc_id"))
                resolved[did] = {"id": did, "text": str(d["text"])}
        if resolved:
            return resolved

    # Fallback: parse ===== docXX (...) =====, === DOC_ID ===, and tool JSON results from prompt_messages
    user_chunks: list[str] = []
    if isinstance(prompt_messages, list):
        for m in prompt_messages:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            content = str(m.get("content", ""))
            if role in ("user", "tool"):
                user_chunks.append(content)
            if role == "tool" and content.strip().startswith("{"):
                try:
                    _harvest_docs_from_json_tree(json.loads(content), resolved)
                except json.JSONDecodeError:
                    pass
    elif isinstance(prompt_messages, str):
        user_chunks.append(prompt_messages)

    user_only = "\n\n".join(user_chunks)
    for m in _MB_DOC_BLOCK_RE.finditer(user_only):
        doc_id, body = m.group(1).strip(), m.group(2).strip()
        if doc_id in resolved:
            resolved[doc_id]["text"] += "\n" + body
        else:
            resolved[doc_id] = {"id": doc_id, "text": body}

    for m in _TRIPLE_EQ_DOC_BLOCK_RE.finditer(user_only):
        doc_id, body = m.group(1).strip(), m.group(2).strip()
        if doc_id in resolved:
            resolved[doc_id]["text"] += "\n" + body
        else:
            resolved[doc_id] = {"id": doc_id, "text": body}

    return resolved


def _collect_all_quotes(parsed: dict[str, Any]) -> list[tuple[str, str]]:
    """Extract all (quote, doc_id) pairs emitted across Murder Board & specialist schemas."""
    pairs: list[tuple[str, str]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if "a_quote" in node or "a_doc" in node:
                pairs.append((str(node.get("a_quote") or ""), str(node.get("a_doc") or "")))
            if "b_quote" in node or "b_doc" in node:
                pairs.append((str(node.get("b_quote") or ""), str(node.get("b_doc") or "")))
            if "claim_quote" in node and ("claim_doc" in node or "claim_doc_id" in node):
                pairs.append((str(node.get("claim_quote") or ""), str(node.get("claim_doc") or node.get("claim_doc_id") or "")))
            if "finding_quote" in node and ("finding_doc" in node or "finding_doc_id" in node):
                pairs.append((str(node.get("finding_quote") or ""), str(node.get("finding_doc") or node.get("finding_doc_id") or "")))
            if "anchor_quote" in node and ("anchor_doc_id" in node or "anchor_doc" in node):
                pairs.append((str(node.get("anchor_quote") or ""), str(node.get("anchor_doc_id") or node.get("anchor_doc") or "")))
            if "earlier_quote" in node or "earlier_doc" in node:
                pairs.append((str(node.get("earlier_quote") or ""), str(node.get("earlier_doc") or "")))
            if "later_quote" in node or "later_doc" in node:
                pairs.append((str(node.get("later_quote") or ""), str(node.get("later_doc") or "")))
            if "anchored_quote" in node and "doc_id" in node:
                pairs.append((str(node.get("anchored_quote") or ""), str(node.get("doc_id") or "")))
            elif "quote" in node and "doc_id" in node:
                q_val = node.get("quote")
                d_val = node.get("doc_id")
                if q_val is not None and (str(q_val).strip() != "" or str(d_val or "").strip() != ""):
                    pairs.append((str(q_val or ""), str(d_val or "")))

            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for elem in node:
                _walk(elem)

    _walk(parsed)
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for item in pairs:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def _grade_quotes(
    parsed: dict[str, Any],
    docs_by_id: dict[str, dict[str, Any]],
    *,
    max_credit: float = 0.35,
    require_non_empty: bool = False,
) -> tuple[float, int, int, list[str]]:
    """Grade all emitted quotes with quote_ok(). Full credit requires ZERO dropped/hallucinated quotes."""
    pairs = _collect_all_quotes(parsed)
    violations: list[str] = []
    if not docs_by_id:
        return (max_credit if pairs or not require_non_empty else 0.0), len(pairs), 0, violations

    if not pairs:
        if require_non_empty:
            violations.append("missing_required_quotes")
            return 0.0, 0, 0, violations
        return max_credit, 0, 0, violations

    dropped = 0
    for q_str, doc_id in pairs:
        if not quote_ok(q_str, doc_id, docs_by_id):
            dropped += 1
            violations.append(f"hallucinated_or_dropped_quote:{doc_id}")

    if dropped == 0:
        return max_credit, len(pairs), 0, violations

    valid_ratio = (len(pairs) - dropped) / len(pairs)
    penalized = max(-0.25, round(0.10 * valid_ratio - 0.15 * dropped, 4))
    return penalized, len(pairs), dropped, violations


def _normalize_vetoes_input(raw_vetoes: Any) -> list[dict[str, str]]:
    if not isinstance(raw_vetoes, list):
        return []
    out: list[dict[str, str]] = []
    for v in raw_vetoes:
        if isinstance(v, dict) and v.get("phrase"):
            out.append({"phrase": str(v["phrase"]), "reason": str(v.get("reason", ""))})
        elif isinstance(v, str) and v.strip():
            out.append({"phrase": v.strip(), "reason": ""})
    return out


def _set_prf1(pred_iter: list[Any], gold_iter: list[Any]) -> tuple[float, float, float]:
    pred_set = {norm_ws(str(x)) for x in pred_iter if norm_ws(str(x))}
    gold_set = {norm_ws(str(x)) for x in gold_iter if norm_ws(str(x))}
    if not gold_set and not pred_set:
        return 1.0, 1.0, 1.0
    if not gold_set and pred_set:
        return 0.0, 1.0, 0.0
    if gold_set and not pred_set:
        return 0.0, 0.0, 0.0
    tp = len(pred_set & gold_set)
    prec = tp / len(pred_set)
    rec = tp / len(gold_set)
    f1 = (2.0 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return prec, rec, f1


def _norm_iso_ts(s: str) -> str:
    """Normalize ISO-8601 strings to YYYY-MM-DDTHH:MM for consistent comparison."""
    txt = str(s or "").strip().replace(" ", "T")
    if txt.endswith("Z"):
        txt = txt[:-1]
    m = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})", txt)
    if m:
        return m.group(1)
    m_hm = re.match(r"^(\d{2}:\d{2})", txt)
    if m_hm:
        return m_hm.group(1)
    return norm_ws(txt)


# ============================================================================
# Domain Routing
# ============================================================================


def _detect_domain_route(
    ground_truth: dict[str, Any],
    parsed: dict[str, Any] | None,
    prompt_messages: list[dict[str, Any]] | str | None,
) -> str:
    track = norm_ws(ground_truth.get("track", ""))
    domain = norm_ws(ground_truth.get("domain", ""))
    subtask = norm_ws(ground_truth.get("subtask") or ground_truth.get("step") or ground_truth.get("chair") or "")
    p_keys = set(parsed.keys()) if isinstance(parsed, dict) else set()

    # 1. Track 2 Biometric Co-Pilot
    if (
        track in ("track2_future", "track_2", "track2")
        or any(tok in domain for tok in ("biometric", "future_room", "room_copilot"))
        or any(tok in subtask for tok in ("biometric", "chair12", "chair_12", "wesad", "homicide_interview", "aml_customs_secondary"))
        or "subject_state" in ground_truth
        or "baseline_adjusted_pattern" in ground_truth
        or "innocent_physiological_alternative" in p_keys
    ):
        return "biometric_copilot"

    # 2. 911 Panicked & Coerced Triage
    if (
        any(tok in domain for tok in ("911", "dispatch", "psap"))
        or any(tok in subtask for tok in ("911", "coerced_caller", "medical_critical", "unknown_location", "multi_hazard", "silent_or_open", "swatting"))
        or "coercion_detected" in ground_truth
        or "silent_approach_required" in ground_truth
        or "next_dispatcher_line" in p_keys
    ):
        return "911_triage"

    # 3. AML / TBML / Shell-Company Hunter
    if (
        any(tok in domain for tok in ("aml", "laundering", "tbml", "fincen"))
        or any(tok in subtask for tok in ("aml", "tbml", "sar", "smurfing", "shell", "crypto_peel", "cash_front", "real_estate_nominee"))
        or ground_truth.get("disposition") in ("FILE_SAR_ESCALATE", "CLEAR_NO_SAR", "HOLD_FOR_RECORDS")
        or "tainted_entities" in ground_truth
        or ("disposition" in p_keys and "tainted_entities" in p_keys)
    ):
        return "aml_hunter"

    # 4. Forensic Micro-Skills
    if (
        "forensic_micro" in domain
        or any(
            tok in subtask
            for tok in (
                "temporal",
                "clock",
                "torque",
                "forensic_nli",
                "entity_graph",
                "entity_resolution_graph",
                "name_collision_guard",
                "docred",
                "graph_resolution",
                "collision_guard",
                "pathology",
                "ballistics",
                "era_forensics",
                "digital_machine_literacy",
                "fake_insider_knowledge",
                "retest",
                "re_test",
                "hypothesis_tournament",
                "musr",
            )
        )
        or any(
            k in ground_truth
            for k in (
                "iso_windows",
                "nli_label",
                "triples",
                "recommended_retest",
                "recommended_modern_test",
                "retest_pick",
                "expected_ranking",
                "ranked_hypothesis_ids",
            )
        )
    ):
        return "forensic_micro_skills"

    # 5. Default: Murder Board 11 Chairs & Vault Retrieval
    prompt_txt = norm_ws(_prompt_to_text(prompt_messages))
    if "911 emergency triage" in prompt_txt or "next_dispatcher_line" in prompt_txt:
        return "911_triage"
    return "murder_board_and_vault"


# ============================================================================
# Verifier 1: Murder Board 11 Chairs & Vault Retrieval
# ============================================================================


def _verify_murder_board_and_vault(
    completion_text: str,
    parsed: dict[str, Any] | None,
    ground_truth: dict[str, Any],
    docs_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    violations: list[str] = []
    components: dict[str, float] = {}

    chair = norm_ws(ground_truth.get("subtask") or ground_truth.get("step") or ground_truth.get("chair") or ground_truth.get("step_id") or "")
    if ("case_posture" in ground_truth or "signal_doc_ids" in ground_truth) and "vault" not in chair:
        chair = "noisy_vault_retrieval"
    if not chair and isinstance(parsed, dict):
        if "leads" in parsed and "brief" in parsed:
            chair = "lead_detective"
        elif "contradictions" in parsed and "alibis" in parsed:
            chair = "cross_examiner"
        elif "sufficiency" in parsed and "vetoes" in parsed:
            chair = "prosecutor"

    # Hard -0.5 prosecutor veto check (excluding Prosecutor's own `vetoes` definition array)
    veto_list = _normalize_vetoes_input(ground_truth.get("vetoes", []))
    if chair in ("prosecutor", "10_prosecutor") and isinstance(parsed, dict):
        prosecutor_non_veto_blob = json.dumps(
            {k: v for k, v in parsed.items() if k != "vetoes"},
            ensure_ascii=False,
        )
        veto_hits = check_prosecutor_vetoes(prosecutor_non_veto_blob, veto_list)
    else:
        veto_hits = check_prosecutor_vetoes(str(completion_text), veto_list)

    if veto_hits:
        components["prosecutor_veto_penalty"] = -0.50
        for h in veto_hits:
            violations.append(f"prosecutor_veto_violation:{h}")
    else:
        components["prosecutor_veto_penalty"] = 0.0

    if parsed is None:
        violations.append("invalid_json")
        components["valid_json"] = -0.50
        total = round(max(-1.0, sum(components.values())), 4)
        return {"reward": total, "components": components, "violations": violations}

    # 1. Quote Verification Slot (+0.35 — requires 0 hallucinated/dropped quotes)
    is_unanswerable_vault = (
        chair in ("vault_retrieval", "noisy_vault_retrieval", "vault_multihop_retrieval")
        and (
            ground_truth.get("answerable") is False
            or ground_truth.get("sufficiency_reached") is False
            or ground_truth.get("case_posture") == "ARCHIVAL_HOLD_MISSING_RECORDS"
        )
    )
    require_quotes = (chair in _QUOTE_REQUIRED_CHAIRS) and not is_unanswerable_vault and bool(docs_by_id)
    q_score, n_quotes, _, q_violations = _grade_quotes(
        parsed,
        docs_by_id,
        max_credit=0.35,
        require_non_empty=require_quotes,
    )
    violations.extend(q_violations)

    if chair in ("custody", "01_first_officer") and n_quotes == 0:
        docs_arr = parsed.get("documents")
        if isinstance(docs_arr, list) and docs_arr:
            unknown_ids = [
                str(d.get("doc_id"))
                for d in docs_arr
                if isinstance(d, dict) and docs_by_id and str(d.get("doc_id")) not in docs_by_id
            ]
            if not unknown_ids and (not docs_by_id or len(docs_arr) == len(docs_by_id)):
                q_score = 0.35
            else:
                q_score = 0.0
                violations.append("custody_doc_registry_mismatch")
        else:
            q_score = 0.0
            violations.append("missing_custody_documents")
    elif chair in ("records", "02_records") and n_quotes == 0:
        starters = parsed.get("starter_items")
        if isinstance(starters, list) and starters and all(
            isinstance(it, dict) and str(it.get("label", "")).upper() == "UNVERIFIED" for it in starters
        ):
            q_score = 0.35
        else:
            q_score = 0.0
            violations.append("records_starter_items_must_be_unverified")
    elif chair in ("prosecutor", "10_prosecutor") and n_quotes == 0:
        suff = parsed.get("sufficiency")
        if isinstance(suff, list) and suff:
            q_score = 0.35
        else:
            q_score = 0.0
            violations.append("missing_prosecutor_sufficiency")
    elif chair in ("lead_detective", "11_lead_detective") and n_quotes == 0 and docs_by_id:
        cited_doc_refs = re.findall(r"\bdoc\d+\b", json.dumps(parsed.get("gaps", [])))
        bad_refs = [r for r in cited_doc_refs if r not in docs_by_id]
        if bad_refs:
            q_score = 0.0
            violations.append(f"unknown_gap_doc_ref:{bad_refs[0]}")
        else:
            q_score = 0.35

    components["quote_verification"] = q_score

    # 2. Chair-Specific Ground-Truth (+0.25), Rubric/Logic (+0.20), Restraint/InnocentAlt (+0.20)
    if chair in ("cross_examiner", "08_cross_examiner"):
        gt_alibis_raw = ground_truth.get("alibis") or ground_truth.get("alibi_ratings") or {}
        gt_alibis: dict[str, str] = {}
        if isinstance(gt_alibis_raw, dict):
            gt_alibis = {norm_ws(k): norm_ws(v) for k, v in gt_alibis_raw.items()}
        elif isinstance(gt_alibis_raw, list):
            for item in gt_alibis_raw:
                if isinstance(item, dict) and item.get("person"):
                    gt_alibis[norm_ws(item["person"])] = norm_ws(item.get("rating", ""))

        pred_alibis_list = parsed.get("alibis") if isinstance(parsed.get("alibis"), list) else []
        pred_alibis = {
            norm_ws(a.get("person", "")): norm_ws(a.get("rating", ""))
            for a in pred_alibis_list
            if isinstance(a, dict) and a.get("person")
        }
        if gt_alibis:
            matches = sum(1 for p, r in gt_alibis.items() if pred_alibis.get(p) == r)
            alibi_acc = matches / len(gt_alibis)
            components["alibi_match"] = round(0.25 * alibi_acc, 4)
            if matches < len(gt_alibis):
                violations.append("alibi_rating_mismatch")
        else:
            valid_ratings = {"contradicted", "corroborated", "uncorroborated"}
            ok = bool(pred_alibis) and all(v in valid_ratings for v in pred_alibis.values())
            components["alibi_match"] = 0.25 if ok else 0.0

        contras = parsed.get("contradictions") if isinstance(parsed.get("contradictions"), list) else []
        expect_contra = ground_truth.get("expect_contradictions", True)
        if expect_contra and not contras:
            components["contradiction_structure"] = 0.0
            violations.append("missing_contradictions")
        else:
            valid_struct = all(
                isinstance(c, dict)
                and norm_ws(c.get("a_quote", "")) != norm_ws(c.get("b_quote", ""))
                and norm_ws(c.get("severity", "")) in ("high", "medium", "low")
                for c in contras
            )
            components["contradiction_structure"] = 0.20 if valid_struct else 0.05

        if contras and all(
            isinstance(c, dict) and len(norm_ws(c.get("innocent_alternative", ""))) >= 10
            for c in contras
        ):
            components["innocent_alternative"] = 0.20
        elif not contras and not expect_contra:
            components["innocent_alternative"] = 0.20
        else:
            components["innocent_alternative"] = 0.0
            violations.append("missing_innocent_alternative")

    elif chair in ("lead_detective", "11_lead_detective"):
        leads = parsed.get("leads") if isinstance(parsed.get("leads"), list) else []
        if not leads:
            components["lead_rubric_match"] = 0.0
            violations.append("missing_leads")
        else:
            rubric_exact = True
            computed_scores: list[int] = []
            for ld in leads:
                if not isinstance(ld, dict):
                    rubric_exact = False
                    break
                comp = ld.get("components") if isinstance(ld.get("components"), dict) else {}
                expected_s = recompute_score(comp)
                computed_scores.append(expected_s)
                if ld.get("score") != expected_s:
                    rubric_exact = False
                    violations.append(f"lead_score_rubric_mismatch:{ld.get('score')}!={expected_s}")
            sorted_ok = computed_scores == sorted(computed_scores, reverse=True)
            if not sorted_ok:
                violations.append("leads_not_sorted_descending")

            gt_scores = ground_truth.get("expected_lead_scores")
            top_gt_score = ground_truth.get("top_lead_score")
            gt_scores_ok = True
            if gt_scores is not None and computed_scores[: len(gt_scores)] != list(gt_scores):
                gt_scores_ok = False
                violations.append("expected_lead_scores_mismatch")
            if top_gt_score is not None and computed_scores and computed_scores[0] != int(top_gt_score):
                gt_scores_ok = False
                violations.append("top_lead_score_mismatch")

            gt_target = norm_ws(ground_truth.get("primary_lead_target", ""))
            target_ok = (not gt_target) or (gt_target in norm_ws(json.dumps(leads[0], ensure_ascii=False)))

            if rubric_exact and sorted_ok and gt_scores_ok and target_ok:
                components["lead_rubric_match"] = 0.25
            elif rubric_exact and sorted_ok:
                components["lead_rubric_match"] = 0.15
            else:
                components["lead_rubric_match"] = 0.0

        brief = str(parsed.get("brief") or "").strip()
        if norm_ws(brief).endswith(norm_ws(STANDING_BRIEF_CLOSER)):
            components["standing_brief_closer"] = 0.20
        else:
            components["standing_brief_closer"] = -0.15
            violations.append("missing_standing_brief_closer")

        gaps = parsed.get("gaps") if isinstance(parsed.get("gaps"), list) else []
        has_arithmetic = bool(leads) and all(
            isinstance(ld, dict) and bool(str(ld.get("arithmetic") or "").strip()) and bool(str(ld.get("reason") or "").strip())
            for ld in leads
        )
        components["desk_discipline_and_gaps"] = 0.20 if (has_arithmetic and isinstance(gaps, list)) else 0.05

    elif chair in ("prosecutor", "10_prosecutor"):
        gt_suff_raw = ground_truth.get("sufficiency") or {}
        gt_suff: dict[str, str] = {}
        if isinstance(gt_suff_raw, dict):
            gt_suff = {norm_ws(k): norm_ws(v) for k, v in gt_suff_raw.items()}
        elif isinstance(gt_suff_raw, list):
            for it in gt_suff_raw:
                if isinstance(it, dict) and it.get("subject"):
                    gt_suff[norm_ws(it["subject"])] = norm_ws(it.get("rating", ""))

        pred_suff_list = parsed.get("sufficiency") if isinstance(parsed.get("sufficiency"), list) else []
        pred_suff = {
            norm_ws(s.get("subject", "")): norm_ws(s.get("rating", ""))
            for s in pred_suff_list
            if isinstance(s, dict) and s.get("subject")
        }
        if gt_suff:
            acc = sum(1 for k, v in gt_suff.items() if pred_suff.get(k) == v) / len(gt_suff)
            components["sufficiency_match"] = round(0.25 * acc, 4)
            if acc < 1.0:
                violations.append("sufficiency_rating_mismatch")
        else:
            valid = bool(pred_suff) and all(r in ("strong", "workable", "weak") for r in pred_suff.values())
            components["sufficiency_match"] = 0.25 if valid else 0.0

        corrob = parsed.get("corroboration_needed")
        components["corroboration_list"] = 0.20 if (isinstance(corrob, list) and len(corrob) > 0) else 0.0
        vetoes_out = parsed.get("vetoes") if isinstance(parsed.get("vetoes"), list) else []
        veto_len_ok = bool(vetoes_out) and all(
            isinstance(v, dict) and 1 <= len(str(v.get("phrase", "")).split()) <= 6
            for v in vetoes_out
        )
        components["veto_craft"] = 0.20 if veto_len_ok else 0.05

    elif chair in ("vault_retrieval", "noisy_vault_retrieval", "vault_multihop_retrieval"):
        gt_docs = list(ground_truth.get("required_doc_ids") or ground_truth.get("clue_doc_ids") or [])
        pred_docs = list(parsed.get("retrieved_doc_ids") or [])
        for hop in parsed.get("hop_chain") or []:
            if isinstance(hop, dict) and hop.get("doc_id") and hop["doc_id"] not in pred_docs:
                pred_docs.append(hop["doc_id"])
        for _, d_id in _collect_all_quotes(parsed):
            if d_id and d_id not in pred_docs:
                pred_docs.append(d_id)

        if gt_docs:
            _, _, doc_f1 = _set_prf1(pred_docs, gt_docs)
            components["vault_doc_f1"] = round(0.25 * doc_f1, 4)
            if doc_f1 < 1.0:
                violations.append("incomplete_vault_hop_retrieval")
        else:
            components["vault_doc_f1"] = 0.25 if pred_docs else 0.0

        if "case_posture" in ground_truth:
            suff_match = norm_ws(parsed.get("case_posture")) == norm_ws(ground_truth.get("case_posture"))
            ans_match = True
        else:
            gt_suff_bool = ground_truth.get("sufficiency_reached", ground_truth.get("answerable", True))
            pred_suff_bool = parsed.get("sufficiency_reached", True)
            suff_match = bool(pred_suff_bool) == bool(gt_suff_bool)
            gt_ans = norm_ws(ground_truth.get("final_answer", ""))
            pred_ans = norm_ws(parsed.get("final_answer", ""))
            ans_match = (not gt_ans) or (gt_ans in pred_ans or pred_ans in gt_ans)

        components["sufficiency_and_answer_match"] = 0.20 if (suff_match and ans_match) else (0.10 if suff_match else 0.0)
        if not suff_match:
            violations.append("vault_sufficiency_decision_mismatch")

        has_restraint = bool(
            parsed.get("innocent_alternative")
            or parsed.get("archival_gap_note")
            or parsed.get("contradictions")
            or parsed.get("almanac_premise_checks")
            or parsed.get("sufficiency_reached") is False
        )
        components["restraint_and_innocent_alt"] = 0.20 if has_restraint else 0.05

    elif chair == "detectiveqa_deduction":
        gt_opt = norm_ws(ground_truth.get("gold_option", ""))
        pred_opt = norm_ws(parsed.get("selected_option", ""))
        opt_ok = bool(gt_opt) and (pred_opt == gt_opt)
        components["option_accuracy"] = 0.25 if opt_ok else 0.0
        if not opt_ok:
            violations.append("wrong_deductive_option")

        gt_clues = ground_truth.get("clue_doc_ids") or []
        pred_clues = [c.get("doc_id") for c in (parsed.get("cited_clues") or []) if isinstance(c, dict)]
        _, clue_rec, _ = _set_prf1(pred_clues, gt_clues)
        components["clue_recall"] = round(0.20 * clue_rec, 4)

        has_inno = len(norm_ws(parsed.get("innocent_alternative", ""))) >= 10
        components["innocent_alternative"] = 0.20 if has_inno else 0.0
        if not has_inno:
            violations.append("missing_innocent_alternative")

    else:
        gt_match_score = 0.25
        gt_dw = ground_truth.get("death_window") or ground_truth.get("me_death_window")
        if chair in ("coroner", "03_coroner") and isinstance(gt_dw, dict):
            p_dw = parsed.get("death_window") if isinstance(parsed.get("death_window"), dict) else {}
            if _norm_iso_ts(p_dw.get("start", "")) != _norm_iso_ts(gt_dw.get("start", "")) or _norm_iso_ts(
                p_dw.get("end", "")
            ) != _norm_iso_ts(gt_dw.get("end", "")):
                gt_match_score = 0.0
                violations.append("death_window_mismatch")
        elif chair in ("csi", "04_csi") and "expected_gap_items" in ground_truth:
            pred_gaps = " ".join(norm_ws(g.get("item", "")) for g in (parsed.get("gaps") or []) if isinstance(g, dict))
            hits = sum(1 for it in ground_truth["expected_gap_items"] if norm_ws(it) in pred_gaps)
            gt_match_score = round(0.25 * (hits / max(1, len(ground_truth["expected_gap_items"]))), 4)
        elif chair in ("digital", "07_digital") and "expected_camera_gaps" in ground_truth:
            pred_cams = " ".join(norm_ws(c.get("camera", "")) for c in (parsed.get("camera_gaps") or []) if isinstance(c, dict))
            hits = sum(1 for it in ground_truth["expected_camera_gaps"] if norm_ws(it) in pred_cams)
            gt_match_score = round(0.25 * (hits / max(1, len(ground_truth["expected_camera_gaps"]))), 4)

        components["chair_ground_truth_match"] = gt_match_score
        components["schema_completeness"] = 0.20 if len(parsed) >= 1 else 0.0
        components["conservative_restraint"] = 0.20 if not veto_hits else 0.0

    total = round(max(-1.0, min(1.0, sum(components.values()))), 4)
    return {"reward": total, "components": components, "violations": violations}


# ============================================================================
# Verifier 2: Forensic Micro-Skills
# ============================================================================


def _verify_forensic_micro_skills(
    completion_text: str,
    parsed: dict[str, Any] | None,
    ground_truth: dict[str, Any],
    docs_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    violations: list[str] = []
    components: dict[str, float] = {}

    veto_hits = check_prosecutor_vetoes(str(completion_text), _normalize_vetoes_input(ground_truth.get("vetoes", [])))
    if veto_hits:
        components["prosecutor_veto_penalty"] = -0.50
        for h in veto_hits:
            violations.append(f"prosecutor_veto_violation:{h}")
    else:
        components["prosecutor_veto_penalty"] = 0.0

    if parsed is None:
        violations.append("invalid_json")
        components["valid_json"] = -0.50
        return {"reward": round(max(-1.0, sum(components.values())), 4), "components": components, "violations": violations}

    subtask = norm_ws(ground_truth.get("subtask") or "")
    exp_json = ground_truth.get("expected_json") if isinstance(ground_truth.get("expected_json"), dict) else {}

    q_score, _, _, q_violations = _grade_quotes(parsed, docs_by_id, max_credit=0.20, require_non_empty=False)
    violations.extend(q_violations)
    components["format_and_quotes"] = q_score

    # 2A. Temporal & Clock-Skew Math
    if "temporal" in subtask or "clock" in subtask or "torque" in subtask or "iso_windows" in ground_truth:
        gt_wins = ground_truth.get("iso_windows") or exp_json.get("iso_windows") or []
        pred_wins = parsed.get("iso_windows") if isinstance(parsed.get("iso_windows"), list) else []

        def _extract_win_pairs(items: Any) -> list[tuple[str, str]]:
            if isinstance(items, dict):
                return [(_norm_iso_ts(v[0]), _norm_iso_ts(v[-1])) for v in items.values() if isinstance(v, (list, tuple)) and v]
            out: list[tuple[str, str]] = []
            for w in (items or []):
                if isinstance(w, dict):
                    s_ts = w.get("start_iso") or w.get("iso_start") or w.get("start") or ""
                    e_ts = w.get("end_iso") or w.get("iso_end") or w.get("end") or s_ts
                    out.append((_norm_iso_ts(s_ts), _norm_iso_ts(e_ts)))
            return out

        gt_pairs = _extract_win_pairs(gt_wins)
        pred_pairs = _extract_win_pairs(pred_wins)

        if gt_pairs:
            matched = sum(1 for gp in gt_pairs if gp in pred_pairs)
            win_acc = matched / len(gt_pairs)
            components["iso_windows_accuracy"] = round(0.40 * win_acc, 4)
            if win_acc < 1.0:
                violations.append("iso_windows_mismatch")
        else:
            components["iso_windows_accuracy"] = 0.40 if pred_pairs else 0.0

        gt_col = bool(ground_truth.get("collision_detected", exp_json.get("collision_detected", False)))
        pred_col = parsed.get("collision_detected")
        if isinstance(pred_col, bool) and pred_col == gt_col:
            components["collision_detected_match"] = 0.25
        else:
            components["collision_detected_match"] = 0.0
            violations.append("collision_detected_mismatch")

        has_inno = len(norm_ws(parsed.get("innocent_alternative", ""))) >= 8 or "ordered_events" in parsed
        components["ordering_and_drift_note"] = 0.15 if has_inno else 0.05

    # 2B. Strict Forensic NLI (SUPPORTED | REFUTED | NOT_ENOUGH_INFORMATION)
    elif "nli" in subtask or "nli_label" in ground_truth or ground_truth.get("label") in (
        "SUPPORTED",
        "REFUTED",
        "NOT_ENOUGH_INFORMATION",
    ):
        gt_lbl = str(ground_truth.get("nli_label") or ground_truth.get("label") or "").strip().upper()
        pred_lbl = str(parsed.get("nli_label") or parsed.get("label") or parsed.get("verdict") or "").strip().upper()
        valid_labels = {"SUPPORTED", "REFUTED", "NOT_ENOUGH_INFORMATION"}

        if pred_lbl == gt_lbl and pred_lbl in valid_labels:
            components["nli_label_match"] = 0.55
        else:
            components["nli_label_match"] = 0.0
            violations.append(f"nli_label_mismatch:{pred_lbl}!={gt_lbl}")
            if gt_lbl == "NOT_ENOUGH_INFORMATION" and pred_lbl in ("SUPPORTED", "REFUTED"):
                components["nli_overclaim_penalty"] = -0.25
                violations.append("overclaimed_nli_on_insufficient_evidence")

        has_conservative = bool(
            parsed.get("conservative_reading_note")
            or parsed.get("innocent_alternative")
            or parsed.get("missing_to_prove")
            or parsed.get("reasoning_note")
            or len(parsed) >= 2
        )
        components["conservative_reading"] = 0.25 if (pred_lbl in valid_labels and has_conservative) else 0.05

    # 2C. Entity Resolution & Collision Guard (GraphRAG + DO_NOT_MERGE_COLLISION)
    elif (
        "graph" in subtask
        or "entity" in subtask
        or "collision_guard" in subtask
        or "docred" in subtask
        or "triples" in ground_truth
        or ground_truth.get("decision") == "DO_NOT_MERGE_COLLISION"
    ):
        if subtask == "name_collision_guard" or (
            ground_truth.get("decision") == "DO_NOT_MERGE_COLLISION" and "triples" not in ground_truth
        ):
            pred_dec = str(parsed.get("decision") or parsed.get("action") or "").strip().upper()
            if pred_dec == "DO_NOT_MERGE_COLLISION" or "DO_NOT_MERGE_COLLISION" in json.dumps(parsed).upper():
                components["collision_guard_safety"] = 0.55
                components["distinguishing_evidence"] = 0.25 if len(parsed) >= 2 else 0.10
            else:
                components["collision_guard_safety"] = -0.50
                violations.append("unsafe_homonym_merge_violation")
        else:
            def _canon_triples(items: Any) -> list[str]:
                out: list[str] = []
                if not isinstance(items, list):
                    return out
                for t in items:
                    if isinstance(t, dict):
                        h = norm_ws(t.get("head") or t.get("subject") or t.get("source") or "")
                        r = norm_ws(t.get("relation") or t.get("edge") or t.get("predicate") or "")
                        ta = norm_ws(t.get("tail") or t.get("object") or t.get("target") or "")
                        if h and r and ta:
                            out.append(f"{h}|{r}|{ta}")
                    elif isinstance(t, (list, tuple)) and len(t) >= 3:
                        out.append(f"{norm_ws(t[0])}|{norm_ws(t[1])}|{norm_ws(t[2])}")
                return out

            gt_triples = _canon_triples(ground_truth.get("triples") or exp_json.get("triples") or [])
            pred_triples = _canon_triples(parsed.get("triples") or parsed.get("edges") or [])
            _, _, triple_f1 = _set_prf1(pred_triples, gt_triples)
            components["graph_triples_f1"] = round(0.45 * triple_f1, 4)
            if gt_triples and triple_f1 < 1.0:
                violations.append("incomplete_or_inaccurate_graph_triples")

            gt_collisions = ground_truth.get("collision_guards") or ground_truth.get("do_not_merge") or []
            dnm_required = bool(ground_truth.get("do_not_merge_required") or len(gt_collisions) > 0)
            pred_guards = parsed.get("collision_guards") or parsed.get("do_not_merge") or []
            raw_dump_upper = json.dumps(parsed, ensure_ascii=False).upper()

            illegal_merge = False
            for t in (parsed.get("triples") or []):
                if isinstance(t, dict):
                    rel_u = str(t.get("relation") or "").upper()
                    if any(bad in rel_u for bad in ("SAME_AS", "MERGED_WITH", "IDENTICAL_TO")) and dnm_required:
                        illegal_merge = True

            if illegal_merge:
                components["collision_guard_safety"] = -0.50
                violations.append("unsafe_homonym_merge_violation")
            elif dnm_required:
                has_dnm_flag = ("DO_NOT_MERGE_COLLISION" in raw_dump_upper) and bool(pred_guards)
                if has_dnm_flag:
                    components["collision_guard_safety"] = 0.35
                else:
                    components["collision_guard_safety"] = -0.35
                    violations.append("missing_do_not_merge_collision_guard")
            else:
                components["collision_guard_safety"] = 0.35

    # 2D. Pathology, Ballistics & Era-Forensics Re-Test Pick
    elif any(k in subtask for k in ("pathology", "ballistics", "era_forensics", "retest", "re_test")) or any(
        k in ground_truth for k in ("recommended_retest", "recommended_modern_test", "retest_pick", "gold_retest")
    ):
        gt_retest = norm_ws(
            ground_truth.get("recommended_retest")
            or ground_truth.get("recommended_modern_test")
            or ground_truth.get("retest_pick")
            or ground_truth.get("gold_retest")
            or ""
        )
        pred_retest = norm_ws(
            parsed.get("recommended_retest")
            or parsed.get("recommended_modern_test")
            or parsed.get("retest_pick")
            or parsed.get("modern_retest")
            or ""
        )
        retest_match = bool(gt_retest) and (gt_retest in pred_retest or pred_retest in gt_retest)
        if not retest_match and gt_retest:
            key_tokens = [tok for tok in re.split(r"[\s/_-]+", gt_retest) if len(tok) >= 3]
            if key_tokens and all(tok in pred_retest for tok in key_tokens[:2]):
                retest_match = True

        components["forensic_retest_pick"] = 0.45 if retest_match else 0.0
        if not retest_match:
            violations.append("wrong_forensic_retest_pick")

        constraint_ok = True
        for flag_key in ("postmortem_movement_flag", "postmortem_repositioning_flag", "pinpoint_fallacy_avoided"):
            if flag_key in ground_truth and parsed.get(flag_key) != ground_truth[flag_key]:
                constraint_ok = False
                violations.append(f"mismatch_{flag_key}")
        components["forensic_constraints"] = 0.20 if constraint_ok else 0.0
        has_inno = len(
            norm_ws(parsed.get("innocent_alternative") or parsed.get("contamination_caveat") or json.dumps(parsed))
        ) >= 15
        components["innocent_or_transfer_caveat"] = 0.15 if has_inno else 0.05

    # 2E. Digital Machine Literacy / Fake Insider Knowledge micro-drills
    elif subtask in ("digital_machine_literacy", "fake_insider_knowledge"):
        match_hits = 0
        match_total = 0
        for k, v in exp_json.items():
            if isinstance(v, (bool, str, int)):
                match_total += 1
                if norm_ws(str(parsed.get(k))) == norm_ws(str(v)):
                    match_hits += 1
        acc = (match_hits / match_total) if match_total else 1.0
        components["drill_accuracy"] = round(0.60 * acc, 4)
        components["restraint_note"] = 0.20 if len(parsed) >= 2 else 0.05

    # 2F. Hypothesis Tournament & Bias Immunity
    else:
        gt_ranking = [
            norm_ws(x)
            for x in (ground_truth.get("expected_ranking") or ground_truth.get("ranked_hypothesis_ids") or [])
        ]
        gt_top = norm_ws(ground_truth.get("top_hypothesis") or (gt_ranking[0] if gt_ranking else ""))

        ranked_list = (
            parsed.get("ranked_hypotheses")
            or parsed.get("ranked_hypothesis_ids")
            or parsed.get("hypotheses")
            or []
        )
        pred_ranking: list[str] = []
        if isinstance(ranked_list, list):
            for item in ranked_list:
                if isinstance(item, dict):
                    pred_ranking.append(
                        norm_ws(item.get("hypothesis_id") or item.get("id") or item.get("subject") or item.get("title") or "")
                    )
                    # Also handle subject-based tournament rankings when gt_ranking uses subject names
                else:
                    pred_ranking.append(norm_ws(str(item)))

        # If gt_ranking used `subject` while items had both `hypothesis_id` and `subject`, check `subject` too
        if gt_ranking and pred_ranking != gt_ranking and isinstance(parsed.get("ranked_hypotheses"), list):
            subj_ranking = [
                norm_ws(it.get("subject", ""))
                for it in parsed["ranked_hypotheses"]
                if isinstance(it, dict) and it.get("subject")
            ]
            if subj_ranking == gt_ranking:
                pred_ranking = subj_ranking

        pred_top = norm_ws(parsed.get("top_hypothesis") or (pred_ranking[0] if pred_ranking else ""))

        top_ok = bool(gt_top) and (pred_top == gt_top or gt_top in pred_top)
        exact_order_ok = (not gt_ranking) or (pred_ranking == gt_ranking)
        if top_ok and exact_order_ok:
            components["tournament_ranking"] = 0.45
        elif top_ok:
            components["tournament_ranking"] = 0.25
            violations.append("partial_hypothesis_ranking_order_mismatch")
        else:
            components["tournament_ranking"] = 0.0
            violations.append("wrong_top_hypothesis")

        multi_eval_ok = isinstance(ranked_list, list) and len(ranked_list) >= 2
        components["competing_theories_coverage"] = 0.20 if multi_eval_ok else 0.05

        inno_ok = "innocent" in norm_ws(json.dumps(parsed, ensure_ascii=False)) or "alternative" in norm_ws(
            json.dumps(parsed, ensure_ascii=False)
        )
        components["innocent_alternative"] = 0.15 if inno_ok else 0.0

    total = round(max(-1.0, min(1.0, sum(components.values()))), 4)
    return {"reward": total, "components": components, "violations": violations}


# ============================================================================
# Verifier 3: 911 Panicked & Coerced-Caller Triage
# ============================================================================


def _verify_911_triage(
    completion_text: str,
    parsed: dict[str, Any] | None,
    ground_truth: dict[str, Any],
    docs_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    violations: list[str] = []
    components: dict[str, float] = {}

    veto_hits = check_prosecutor_vetoes(str(completion_text), _normalize_vetoes_input(ground_truth.get("vetoes", [])))
    if veto_hits:
        components["prosecutor_veto_penalty"] = -0.50
        for h in veto_hits:
            violations.append(f"prosecutor_veto_violation:{h}")
    else:
        components["prosecutor_veto_penalty"] = 0.0

    if parsed is None:
        violations.append("invalid_json")
        components["valid_json"] = -0.50
        return {"reward": round(max(-1.0, sum(components.values())), 4), "components": components, "violations": violations}

    # 1. Priority match (+0.25)
    gt_prio = norm_ws(ground_truth.get("priority") or ground_truth.get("priority_level") or "")
    pred_prio = norm_ws(parsed.get("priority") or parsed.get("priority_level") or "")
    if gt_prio and pred_prio == gt_prio:
        components["priority_match"] = 0.25
    elif gt_prio and pred_prio[:2] == gt_prio[:2] and pred_prio.startswith("p"):
        components["priority_match"] = 0.12
        violations.append(f"priority_subtier_mismatch:{pred_prio}!={gt_prio}")
    else:
        components["priority_match"] = 0.0
        violations.append(f"priority_mismatch:{pred_prio}!={gt_prio}")

    # 2. Coercion & Silent Approach recall (+0.30, with critical safety miss penalty)
    gt_coerced = bool(ground_truth.get("coercion_detected", False))
    gt_silent = bool(ground_truth.get("silent_approach_required", False))
    pred_coerced = parsed.get("coercion_detected")
    pred_silent = parsed.get("silent_approach_required")

    c_ok = isinstance(pred_coerced, bool) and (pred_coerced == gt_coerced)
    s_ok = isinstance(pred_silent, bool) and (pred_silent == gt_silent)
    components["coercion_match"] = 0.15 if c_ok else 0.0
    components["silent_approach_match"] = 0.15 if s_ok else 0.0

    if (gt_coerced and not c_ok) or (gt_silent and not s_ok):
        components["critical_coercion_safety_penalty"] = -0.35
        violations.append("missed_coercion_or_silent_approach")
    elif not c_ok or not s_ok:
        violations.append("coercion_or_silent_flag_mismatch")

    # 3. Life-safety trap identification (+0.25)
    gt_traps_raw = ground_truth.get("life_safety_traps_flagged") or ground_truth.get("life_safety_trap") or []
    gt_traps = [gt_traps_raw] if isinstance(gt_traps_raw, str) else list(gt_traps_raw)

    pred_traps_raw = parsed.get("life_safety_traps_flagged") or parsed.get("life_safety_trap") or []
    if isinstance(pred_traps_raw, str):
        pred_traps = [pred_traps_raw]
    elif isinstance(pred_traps_raw, list):
        pred_traps = [str(x) for x in pred_traps_raw]
    else:
        pred_traps = []

    if gt_traps:
        _, trap_rec, trap_f1 = _set_prf1(pred_traps, gt_traps)
        if trap_f1 < 1.0:
            gt_tokens = {tok for t in gt_traps for tok in re.split(r"[\s_-]+", norm_ws(t)) if len(tok) >= 4}
            pred_tokens = {tok for t in pred_traps for tok in re.split(r"[\s_-]+", norm_ws(t)) if len(tok) >= 4}
            tok_rec = (len(gt_tokens & pred_tokens) / len(gt_tokens)) if gt_tokens else 0.0
            score_ratio = max(trap_rec, tok_rec)
        else:
            score_ratio = 1.0
        components["life_safety_trap_recall"] = round(0.25 * score_ratio, 4)
        if score_ratio < 0.75:
            violations.append("missed_life_safety_trap")
    else:
        components["life_safety_trap_recall"] = 0.25

    # 4. Strict <= 18-word next_dispatcher_line gate (+0.20 or -0.45 penalty!)
    next_line = str(parsed.get("next_dispatcher_line") or "").strip()
    words = next_line.split()
    word_count = len(words)
    if word_count == 0:
        components["dispatcher_line_brevity"] = 0.0
        violations.append("empty_next_dispatcher_line")
    elif word_count <= 18:
        components["dispatcher_line_brevity"] = 0.20
    else:
        components["dispatcher_line_brevity"] = 0.0
        components["dispatcher_word_limit_penalty"] = -0.45
        violations.append(f"next_dispatcher_line_exceeds_18_words:{word_count}")

    if docs_by_id and parsed.get("evidence_quotes"):
        _, _, dropped_q, q_viol = _grade_quotes(parsed, docs_by_id, max_credit=0.0, require_non_empty=False)
        if dropped_q > 0:
            components["quote_hallucination_penalty"] = round(-0.15 * dropped_q, 4)
            violations.extend(q_viol)

    total = round(max(-1.0, min(1.0, sum(components.values()))), 4)
    return {"reward": total, "components": components, "violations": violations}


# ============================================================================
# Verifier 4: AML, TBML & Shell-Company Hunter
# ============================================================================


def _verify_aml_hunter(
    completion_text: str,
    parsed: dict[str, Any] | None,
    ground_truth: dict[str, Any],
    docs_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    violations: list[str] = []
    components: dict[str, float] = {}

    veto_hits = check_prosecutor_vetoes(str(completion_text), _normalize_vetoes_input(ground_truth.get("vetoes", [])))
    if veto_hits:
        components["prosecutor_veto_penalty"] = -0.50
        for h in veto_hits:
            violations.append(f"prosecutor_veto_violation:{h}")
    else:
        components["prosecutor_veto_penalty"] = 0.0

    if parsed is None:
        violations.append("invalid_json")
        components["valid_json"] = -0.50
        return {"reward": round(max(-1.0, sum(components.values())), 4), "components": components, "violations": violations}

    # 1. Disposition match: FILE_SAR_ESCALATE vs CLEAR_NO_SAR (+0.35, heavy false-SAR penalty!)
    gt_disp = str(ground_truth.get("disposition") or "").strip().upper()
    pred_disp = str(parsed.get("disposition") or "").strip().upper()

    if pred_disp == gt_disp and gt_disp:
        components["disposition_match"] = 0.35
    else:
        components["disposition_match"] = 0.0
        if gt_disp == "CLEAR_NO_SAR" and pred_disp == "FILE_SAR_ESCALATE":
            components["false_positive_sar_penalty"] = -0.50
            violations.append("false_positive_sar_on_clean_business")
        elif gt_disp == "FILE_SAR_ESCALATE" and pred_disp != "FILE_SAR_ESCALATE":
            violations.append("missed_sar_escalation")
        else:
            violations.append(f"disposition_mismatch:{pred_disp}!={gt_disp}")

    # 2. Typology match (+0.20)
    gt_typ_raw = (
        ground_truth.get("typologies")
        or ground_truth.get("typology")
        or ground_truth.get("detected_typology")
        or []
    )
    gt_typs = [gt_typ_raw] if isinstance(gt_typ_raw, str) else list(gt_typ_raw)
    pred_typ_raw = (
        parsed.get("typologies")
        or parsed.get("typology")
        or parsed.get("detected_typology")
        or []
    )
    pred_typs = [pred_typ_raw] if isinstance(pred_typ_raw, str) else list(pred_typ_raw)

    if gt_typs:
        _, _, typ_f1 = _set_prf1(pred_typs, gt_typs)
        components["typology_match"] = round(0.20 * typ_f1, 4)
        if typ_f1 < 1.0:
            violations.append("typology_mismatch")
    else:
        components["typology_match"] = 0.20 if not pred_typs else 0.0

    # 3. Tainted-entity F1 (+0.25)
    gt_tainted = list(ground_truth.get("tainted_entities") or [])
    pred_tainted = list(parsed.get("tainted_entities") or [])
    _, _, tainted_f1 = _set_prf1(pred_tainted, gt_tainted)
    components["tainted_entity_f1"] = round(0.25 * tainted_f1, 4)
    if tainted_f1 < 1.0:
        violations.append("tainted_entities_mismatch")

    # 4. Cleared-entity precision (+0.20)
    gt_cleared = list(ground_truth.get("cleared_entities") or ground_truth.get("cleared_false_positive_entities") or [])
    pred_cleared = list(parsed.get("cleared_entities") or parsed.get("cleared_false_positive_entities") or [])
    c_prec, c_rec, _ = _set_prf1(pred_cleared, gt_cleared)
    if gt_cleared:
        cleared_score = (0.75 * c_prec + 0.25 * c_rec) if pred_cleared else 0.0
        components["cleared_entity_precision"] = round(0.20 * cleared_score, 4)
        if c_prec < 1.0 or not pred_cleared:
            violations.append("cleared_entities_imprecise_or_missing")
    else:
        components["cleared_entity_precision"] = 0.20 if not pred_cleared else 0.0

    if docs_by_id and _collect_all_quotes(parsed):
        _, _, dropped_q, q_viol = _grade_quotes(parsed, docs_by_id, max_credit=0.0, require_non_empty=False)
        if dropped_q > 0:
            components["quote_hallucination_penalty"] = round(-0.15 * dropped_q, 4)
            violations.extend(q_viol)

    total = round(max(-1.0, min(1.0, sum(components.values()))), 4)
    return {"reward": total, "components": components, "violations": violations}


# ============================================================================
# Verifier 5: Track 2 Future Room Biometric Co-Pilot (Othello-Error Hardened)
# ============================================================================


def _detect_biometric_deception_overclaims(
    raw_text: str,
    parsed: dict[str, Any] | None,
    is_innocent_or_trauma: bool,
) -> list[str]:
    """Detect forbidden polygraph / deception / lying / guilt claims on physiological telemetry."""
    hits: list[str] = []
    low_all = norm_ws(raw_text)

    for phrase in FORBIDDEN_POLYGRAPH_CLAIMS:
        if phrase in low_all:
            hits.append(f"forbidden_polygraph_claim:{phrase}")

    for veto in check_prosecutor_vetoes(raw_text, []):
        hits.append(f"prosecutor_veto:{veto}")

    if isinstance(parsed, dict):
        for bool_k in ("deception_detected", "is_deceptive", "is_lying", "guilty", "polygraph_deceptive"):
            if parsed.get(bool_k) is True:
                hits.append(f"structured_deception_flag:{bool_k}=True")

        for field_k in ("baseline_adjusted_pattern", "subject_state_assessment"):
            val_up = str(parsed.get(field_k) or "").upper()
            if any(bad in val_up for bad in ("DECEPTIVE", "LYING", "GUILTY_VERDICT", "POLYGRAPH_FAIL")):
                hits.append(f"accusatory_pattern_label:{val_up}")
            if is_innocent_or_trauma and any(
                bad in val_up for bad in ("GUILTY_KNOWLEDGE", "DECEPTION_DETECTED", "CONCEALING_CASE_FACT", "LIAR")
            ):
                hits.append(f"false_cit_hit_on_innocent_subject:{val_up}")

    for clause in re.split(r"[.!?\n;]+", str(raw_text or "")):
        c_strip = clause.strip()
        if not c_strip:
            continue
        m = _DECEPTION_ASSERTION_RE.search(c_strip)
        if m and not _NEGATION_GUARD_RE.search(c_strip):
            hits.append(f"unnegated_deception_claim:{m.group(0).lower()}")

    return hits


def _verify_biometric_copilot(
    completion_text: str,
    parsed: dict[str, Any] | None,
    ground_truth: dict[str, Any],
    docs_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    violations: list[str] = []
    components: dict[str, float] = {}

    subj_state = str(ground_truth.get("subject_state") or "").upper()
    is_innocent_or_trauma = bool(ground_truth.get("othello_trap")) or any(
        tok in subj_state
        for tok in (
            "OTHELLO",
            "INNOCENT",
            "TRAUMA",
            "DISTRESSED",
            "EMBARRASSED",
            "ANXIOUS_CONTROL",
            "COOPERATIVE",
        )
    )

    raw_str = json.dumps(completion_text) if isinstance(completion_text, dict) else str(completion_text)
    deception_hits = _detect_biometric_deception_overclaims(raw_str, parsed, is_innocent_or_trauma)
    innocent_phys = ""
    if isinstance(parsed, dict):
        innocent_phys = str(parsed.get("innocent_physiological_alternative") or "").strip()
    has_innocent_phys = len(norm_ws(innocent_phys)) >= 15

    # OTHELLO-ERROR CLIFF: Hard reward = -1.0 on innocent Othello/trauma subject if completion
    # claims deception/lying/guilt OR omits `innocent_physiological_alternative`!
    if is_innocent_or_trauma and (deception_hits or not has_innocent_phys):
        violations.append("othello_error_cliff_triggered")
        violations.extend(deception_hits)
        if not has_innocent_phys:
            violations.append("missing_innocent_physiological_alternative_on_othello_or_trauma_subject")
        components["othello_error_cliff"] = -1.0
        return {"reward": -1.0, "components": components, "violations": violations}

    if parsed is None:
        violations.append("invalid_json")
        components["valid_json"] = -0.50
        return {"reward": -0.50, "components": components, "violations": violations}

    components["valid_json"] = 0.15

    if deception_hits:
        components["polygraph_overclaim_penalty"] = -0.75
        violations.extend(deception_hits)

    # 1. baseline_adjusted_pattern / subject_state_assessment accuracy (+0.35)
    gt_pat = norm_ws(ground_truth.get("baseline_adjusted_pattern") or "")
    pred_pat = norm_ws(parsed.get("baseline_adjusted_pattern") or "")
    gt_assess = norm_ws(ground_truth.get("expected_subject_state_assessment") or "")
    pred_assess = norm_ws(parsed.get("subject_state_assessment") or "")

    if gt_pat:
        if pred_pat == gt_pat:
            components["baseline_adjusted_pattern_accuracy"] = 0.35
        elif (gt_pat in pred_pat or pred_pat in gt_pat) and pred_pat:
            components["baseline_adjusted_pattern_accuracy"] = 0.25
        else:
            components["baseline_adjusted_pattern_accuracy"] = 0.0
            violations.append(f"baseline_adjusted_pattern_mismatch:{pred_pat}!={gt_pat}")
    elif gt_assess:
        if pred_assess == gt_assess and len(pred_pat) >= 10:
            components["baseline_adjusted_pattern_accuracy"] = 0.35
        elif pred_assess == gt_assess:
            components["baseline_adjusted_pattern_accuracy"] = 0.20
        else:
            components["baseline_adjusted_pattern_accuracy"] = 0.0
            violations.append("subject_state_assessment_mismatch")
    else:
        components["baseline_adjusted_pattern_accuracy"] = 0.35 if len(pred_pat) >= 8 else 0.0

    # 2. Mandatory innocent_physiological_alternative (+0.25)
    if has_innocent_phys:
        components["innocent_physiological_alternative"] = 0.25
    else:
        components["innocent_physiological_alternative"] = -0.25
        violations.append("missing_innocent_physiological_alternative")

    # 3. PEACE-compliant interview steering & optional quote checks (+0.25)
    action_txt = norm_ws(
        parsed.get("recommended_interview_action")
        or parsed.get("next_room_protocol_move")
        or parsed.get("next_interview_action")
        or parsed.get("protocol_action_code")
        or ""
    )
    action_ok = len(action_txt) >= 10
    if "TRAUMA" in subj_state and action_ok:
        if not any(
            w in action_txt
            for w in ("peace", "open", "cognitive", "free recall", "non-leading", "unhurried", "rapport", "support", "sensory")
        ):
            action_ok = False
            violations.append("trauma_witness_requires_peace_open_recall")

    components["interview_steering"] = 0.25 if action_ok else 0.05

    if docs_by_id and _collect_all_quotes(parsed):
        _, _, dropped_q, q_viol = _grade_quotes(parsed, docs_by_id, max_credit=0.0, require_non_empty=False)
        if dropped_q > 0:
            components["quote_hallucination_penalty"] = round(-0.15 * dropped_q, 4)
            violations.extend(q_viol)

    total = round(max(-1.0, min(1.0, sum(components.values()))), 4)
    return {"reward": total, "components": components, "violations": violations}


# ============================================================================
# Public Entrypoint & RL Framework Adapters (TRL GRPOTrainer / verl / OpenRLHF)
# ============================================================================


def compute_investigator_reward(
    prompt_messages: list[dict[str, Any]] | str,
    completion_text: str,
    ground_truth: dict[str, Any],
    docs_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute deterministic verifiable reward across all SPEC 7 investigator domains.

    Returns:
        {"reward": float, "components": dict[str, float], "violations": list[str]}
    """
    gt = _coerce_dict(ground_truth)
    parsed = _extract_json_object(completion_text)
    resolved_docs = _resolve_docs_by_id(prompt_messages, gt, docs_by_id)
    route = _detect_domain_route(gt, parsed, prompt_messages)

    if route == "biometric_copilot":
        return _verify_biometric_copilot(str(completion_text), parsed, gt, resolved_docs)
    if route == "911_triage":
        return _verify_911_triage(str(completion_text), parsed, gt, resolved_docs)
    if route == "aml_hunter":
        return _verify_aml_hunter(str(completion_text), parsed, gt, resolved_docs)
    if route == "forensic_micro_skills":
        return _verify_forensic_micro_skills(str(completion_text), parsed, gt, resolved_docs)
    return _verify_murder_board_and_vault(str(completion_text), parsed, gt, resolved_docs)


def _assistant_turn_to_completion_str(turn: Any) -> str:
    if isinstance(turn, dict):
        if turn.get("tool_calls"):
            return json.dumps(turn, ensure_ascii=False)
        return str(turn.get("content", ""))
    return str(turn)


def trl_grpo_reward_fn(
    prompts: list[Any],
    completions: list[Any],
    ground_truth: list[Any] | None = None,
    docs_by_id: list[Any] | None = None,
    **kwargs: Any,
) -> list[float]:
    """Drop-in reward function for HuggingFace TRL `GRPOTrainer(reward_funcs=[trl_grpo_reward_fn])`."""
    gt_list = ground_truth if ground_truth is not None else kwargs.get("ground_truths", [{}] * len(completions))
    docs_list = docs_by_id if docs_by_id is not None else [None] * len(completions)

    rewards: list[float] = []
    for idx, comp in enumerate(completions):
        if isinstance(comp, list) and comp:
            comp_str = _assistant_turn_to_completion_str(comp[-1])
        else:
            comp_str = _assistant_turn_to_completion_str(comp)

        prompt_item = prompts[idx] if idx < len(prompts) else ""
        gt_item = gt_list[idx] if idx < len(gt_list) else {}
        doc_item = docs_list[idx] if idx < len(docs_list) else None

        res = compute_investigator_reward(prompt_item, comp_str, _coerce_dict(gt_item), doc_item)
        rewards.append(float(res["reward"]))
    return rewards


def verl_compute_score(
    data_source: str,
    solution_str: str,
    ground_truth: dict[str, Any] | str,
    extra_info: dict[str, Any] | None = None,
) -> float:
    """Drop-in reward scorer for `verl` (`compute_score` signature)."""
    gt = _coerce_dict(ground_truth)
    if data_source and "domain" not in gt:
        gt = {**gt, "domain": data_source}
    prompt_msgs = (extra_info or {}).get("prompt_messages", "")
    docs_map = (extra_info or {}).get("docs_by_id")
    return float(compute_investigator_reward(prompt_msgs, solution_str, gt, docs_map)["reward"])


compute_score = verl_compute_score


def openrlhf_reward_func(
    queries: list[str],
    prompts: list[str],
    labels: list[str | dict[str, Any]],
) -> dict[str, list[float]]:
    """Drop-in batch reward function for OpenRLHF remote/local reward shaping."""
    scores: list[float] = []
    for q, p, lbl in zip(queries, prompts, labels):
        comp_text = q[len(p):] if q.startswith(p) else q
        res = compute_investigator_reward(p, comp_text, _coerce_dict(lbl))
        scores.append(float(res["reward"]))
    return {"rewards": scores, "kl_rewards": [0.0] * len(scores), "scores": scores}


# ============================================================================
# Self-Test Suite (`python3 -m training.rlvr_rewards --self-test`)
# ============================================================================


def run_self_test() -> dict[str, Any]:
    """Verify gold completions score >= 0.95 across every SPEC 7 domain and corruptions get penalized."""
    checks_passed = 0
    report_cases: list[dict[str, Any]] = []

    def _record(label: str, res: dict[str, Any], cond: bool, expectation: str) -> None:
        nonlocal checks_passed
        if not cond:
            raise AssertionError(f"Self-test failed on '{label}' (expected {expectation}): {res}")
        checks_passed += 1
        report_cases.append({
            "case": label,
            "reward": res["reward"],
            "violations": res["violations"],
        })

    # 1. Murder Board Cross-Examiner & Lead Detective (Gold vs Hallucinated Quote & Veto)
    mb_docs = {
        "doc01": {"id": "doc01", "text": "Scene report notes two 9mm brass casings beside the loading dock door at 00:14."},
        "doc02": {"id": "doc02", "text": "Marcus Vance stated he stayed home asleep from 22:00 until 06:00 without driving."},
        "doc03": {"id": "doc03", "text": "Harbor Bridge ALPR photographed Marcus Vance's pickup crossing southbound at 23:49."},
    }
    mb_ce_gt = {
        "domain": "cold_case_murder_board",
        "subtask": "cross_examiner",
        "alibis": {"Marcus Vance": "contradicted"},
        "vetoes": [{"phrase": "killed him", "reason": "unsupported conclusion"}],
    }
    gold_ce = json.dumps({
        "contradictions": [
            {
                "a_quote": "stayed home asleep from 22:00 until 06:00 without driving",
                "a_doc": "doc02",
                "b_quote": "Harbor Bridge ALPR photographed Marcus Vance's pickup crossing southbound at 23:49",
                "b_doc": "doc03",
                "kind": "statement_vs_record",
                "severity": "HIGH",
                "innocent_alternative": "Another household member may have driven the registered pickup while Vance slept.",
            }
        ],
        "alibis": [
            {
                "person": "Marcus Vance",
                "window": "23:30-00:15",
                "rating": "contradicted",
                "reasons": [
                    {"quote": "stayed home asleep from 22:00 until 06:00 without driving", "doc_id": "doc02"},
                    {"quote": "Harbor Bridge ALPR photographed Marcus Vance's pickup crossing southbound at 23:49", "doc_id": "doc03"},
                ],
            }
        ],
        "evidence_gaps": [],
    })
    r_ce_gold = compute_investigator_reward([], gold_ce, mb_ce_gt, mb_docs)
    _record("mb_cross_examiner_gold", r_ce_gold, r_ce_gold["reward"] >= 0.95 and not r_ce_gold["violations"], ">= 0.95")

    bad_ce_hallucinated = json.dumps({
        "contradictions": [
            {
                "a_quote": "I fabricated this quote out of thin air at midnight",
                "a_doc": "doc02",
                "b_quote": "Harbor Bridge ALPR photographed Marcus Vance's pickup crossing southbound at 23:49",
                "b_doc": "doc03",
                "kind": "statement_vs_record",
                "severity": "HIGH",
                "innocent_alternative": "Someone else drove the pickup.",
            }
        ],
        "alibis": [{"person": "Marcus Vance", "window": "23:30-00:15", "rating": "contradicted", "reasons": []}],
        "evidence_gaps": [],
    })
    r_ce_bad = compute_investigator_reward([], bad_ce_hallucinated, mb_ce_gt, mb_docs)
    _record(
        "mb_cross_examiner_hallucinated_quote",
        r_ce_bad,
        r_ce_bad["reward"] < 0.65 and any("hallucinated_or_dropped_quote" in v for v in r_ce_bad["violations"]),
        "quote drop penalty",
    )

    mb_ld_gt = {
        "domain": "cold_case_murder_board",
        "subtask": "lead_detective",
        "expected_lead_scores": [80],
    }
    gold_ld = json.dumps({
        "leads": [
            {
                "action": "For the detective: ask Marcus Vance who operated his pickup during the 23:49 ALPR capture.",
                "score": 80,
                "arithmetic": "40 + 25 + 15 = 80",
                "reason": "Addresses high contradiction in window and Vance remains reachable.",
                "components": {
                    "cites_high_contradiction": True,
                    "in_window": True,
                    "closes_gap": False,
                    "still_reachable": True,
                },
            }
        ],
        "gaps": [{"gap": "Missing second 9mm casing from property ledger", "proven_by": "doc01"}],
        "brief": f"Summary of file discrepancies between doc02 and doc03.\n\n{STANDING_BRIEF_CLOSER}",
    })
    r_ld_gold = compute_investigator_reward([], gold_ld, mb_ld_gt, mb_docs)
    _record("mb_lead_detective_gold", r_ld_gold, r_ld_gold["reward"] >= 0.95, ">= 0.95")

    bad_ld_veto = json.dumps({
        "leads": [
            {
                "action": "Arrest Vance",
                "score": 100,
                "arithmetic": "100",
                "reason": "Marcus Vance is guilty and is lying.",
                "components": {"cites_high_contradiction": True, "in_window": False, "closes_gap": False, "still_reachable": False},
            }
        ],
        "gaps": [],
        "brief": "Marcus Vance is guilty and is lying about the bridge.",
    })
    r_ld_bad = compute_investigator_reward([], bad_ld_veto, mb_ld_gt, mb_docs)
    _record(
        "mb_lead_detective_veto_and_bad_rubric",
        r_ld_bad,
        r_ld_bad["reward"] <= 0.0
        and r_ld_bad["components"]["prosecutor_veto_penalty"] == -0.5
        and "missing_standing_brief_closer" in r_ld_bad["violations"],
        "<= 0.0 with -0.5 veto penalty",
    )

    # 2. Forensic Micro-Skills (All 5: Temporal, NLI, GraphRAG+Collision, Re-Test, Tournament)
    gt_temp = {
        "domain": "forensic_micro_skills",
        "subtask": "temporal_clock_skew",
        "iso_windows": [{"event": "gate_exit", "start_iso": "2025-02-14T22:45:00", "end_iso": "2025-02-14T22:50:00"}],
        "collision_detected": True,
    }
    gold_temp = json.dumps({
        "iso_windows": [{"event": "gate_exit", "start_iso": "2025-02-14T22:45:00", "end_iso": "2025-02-14T22:50:00"}],
        "ordered_events": ["gate_exit"],
        "collision_detected": True,
        "innocent_alternative": "DVR quartz clock drift of +47 minutes.",
    })
    r_temp = compute_investigator_reward([], gold_temp, gt_temp)
    _record("micro_temporal_gold", r_temp, r_temp["reward"] >= 0.95, ">= 0.95")

    gt_nli = {"domain": "forensic_micro_skills", "subtask": "forensic_nli", "nli_label": "NOT_ENOUGH_INFORMATION"}
    gold_nli = json.dumps({
        "nli_label": "NOT_ENOUGH_INFORMATION",
        "evidence_quotes": [],
        "conservative_reading_note": "Log confirms arrival time but omits container contents.",
    })
    r_nli = compute_investigator_reward([], gold_nli, gt_nli)
    _record("micro_nli_gold", r_nli, r_nli["reward"] >= 0.95, ">= 0.95")

    gt_graph = {
        "domain": "forensic_micro_skills",
        "subtask": "entity_graph_resolution",
        "triples": [{"head": "Marcus Mercer", "relation": "REGISTERED_AGENT_OF", "tail": "Cobalt Nexus LLC"}],
        "do_not_merge_required": True,
    }
    gold_graph = json.dumps({
        "triples": [{"head": "Marcus Mercer", "relation": "REGISTERED_AGENT_OF", "tail": "Cobalt Nexus LLC"}],
        "collision_guards": [{"surface_name": "Marcus Mercer", "action": "DO_NOT_MERGE_COLLISION"}],
    })
    r_graph_gold = compute_investigator_reward([], gold_graph, gt_graph)
    _record("micro_graphrag_gold", r_graph_gold, r_graph_gold["reward"] >= 0.95, ">= 0.95")

    bad_graph_merge = json.dumps({
        "triples": [
            {"head": "Marcus Mercer", "relation": "REGISTERED_AGENT_OF", "tail": "Cobalt Nexus LLC"},
            {"head": "Marcus Mercer (DE)", "relation": "SAME_AS", "tail": "Marcus Mercer (Omaha)"},
        ],
        "collision_guards": [],
    })
    r_graph_bad = compute_investigator_reward([], bad_graph_merge, gt_graph)
    _record(
        "micro_graphrag_unsafe_merge",
        r_graph_bad,
        r_graph_bad["reward"] < 0.30 and "unsafe_homonym_merge_violation" in r_graph_bad["violations"],
        "penalized for unsafe homonym merge",
    )

    gt_retest = {
        "domain": "forensic_micro_skills",
        "subtask": "pathology_era_forensics",
        "recommended_retest": "M-VAC Touch DNA + STRmix probabilistic genotyping",
        "postmortem_movement_flag": True,
    }
    gold_retest = json.dumps({
        "recommended_retest": "M-VAC Touch DNA + STRmix probabilistic genotyping",
        "postmortem_movement_flag": True,
        "innocent_alternative": "Trace alleles on rope may include prior handler secondary transfer.",
    })
    r_retest = compute_investigator_reward([], gold_retest, gt_retest)
    _record("micro_retest_gold", r_retest, r_retest["reward"] >= 0.95, ">= 0.95")

    gt_tour = {
        "domain": "forensic_micro_skills",
        "subtask": "hypothesis_tournament",
        "expected_ranking": ["H2", "H1", "H3"],
        "top_hypothesis": "H2",
    }
    gold_tour = json.dumps({
        "top_hypothesis": "H2",
        "ranked_hypotheses": [
            {"hypothesis_id": "H2", "innocent_alternative": "Prior lawful delivery overlap."},
            {"hypothesis_id": "H1", "innocent_alternative": "Clock estimation variance."},
            {"hypothesis_id": "H3", "innocent_alternative": "Cleared by verified transit gate."},
        ],
    })
    r_tour = compute_investigator_reward([], gold_tour, gt_tour)
    _record("micro_tournament_gold", r_tour, r_tour["reward"] >= 0.95, ">= 0.95")

    # 3. 911 Triage (Gold <=18w vs Corrupted >18w)
    gt_911 = {
        "domain": "dispatch_911_triage",
        "priority": "P1_DELTA",
        "coercion_detected": True,
        "silent_approach_required": True,
        "life_safety_traps_flagged": ["coerced_caller_pizza_order_ruse", "edged_weapon_present"],
    }
    gold_911 = (
        "<triage>Caller ordering pizza to 911 with domestic history.</triage>\n"
        + json.dumps({
            "priority": "P1_DELTA",
            "coercion_detected": True,
            "silent_approach_required": True,
            "life_safety_traps_flagged": ["coerced_caller_pizza_order_ruse", "edged_weapon_present"],
            "next_dispatcher_line": "Police are coming silently. Say 'yes' if anyone is bleeding right now.",
        })
    )
    r_911_gold = compute_investigator_reward([], gold_911, gt_911)
    _record("triage_911_gold", r_911_gold, r_911_gold["reward"] >= 0.95, ">= 0.95")

    bad_911_wordy = json.dumps({
        "priority": "P1_DELTA",
        "coercion_detected": True,
        "silent_approach_required": True,
        "life_safety_traps_flagged": ["coerced_caller_pizza_order_ruse", "edged_weapon_present"],
        "next_dispatcher_line": (
            "Ma'am please listen carefully to me right now because I am dispatching several police patrol cars "
            "with lights and sirens to your apartment building immediately so stay on the phone."
        ),
    })
    r_911_wordy = compute_investigator_reward([], bad_911_wordy, gt_911)
    _record(
        "triage_911_exceeds_18_words",
        r_911_wordy,
        r_911_wordy["reward"] < 0.40
        and any("next_dispatcher_line_exceeds_18_words" in v for v in r_911_wordy["violations"]),
        "strict >18-word penalty",
    )

    # 4. AML Hunter (Gold SAR + Gold Clean Business vs False SAR on Clean Business)
    gt_aml_sar = {
        "domain": "aml_laundering_hunter",
        "disposition": "FILE_SAR_ESCALATE",
        "typology": "TBML_OVER_INVOICING",
        "tainted_entities": ["Apex Meridian Holdings LLC", "Solstice Global Ltd."],
        "cleared_entities": ["Harborview Family Dental PLLC"],
    }
    gold_aml_sar = json.dumps({
        "disposition": "FILE_SAR_ESCALATE",
        "typology": "TBML_OVER_INVOICING",
        "tainted_entities": ["Apex Meridian Holdings LLC", "Solstice Global Ltd."],
        "cleared_entities": ["Harborview Family Dental PLLC"],
        "innocent_alternative": "Verify whether specialty medical-grade polymer resin explains invoice price prior to enforcement.",
    })
    r_aml_sar = compute_investigator_reward([], gold_aml_sar, gt_aml_sar)
    _record("aml_sar_gold", r_aml_sar, r_aml_sar["reward"] >= 0.95, ">= 0.95")

    gt_aml_clean = {
        "domain": "aml_laundering_hunter",
        "disposition": "CLEAR_NO_SAR",
        "typology": "LEGITIMATE_COMMERCIAL_ACTIVITY",
        "tainted_entities": [],
        "cleared_entities": ["Redwood Grading & Excavation Inc."],
    }
    gold_aml_clean = json.dumps({
        "disposition": "CLEAR_NO_SAR",
        "typology": "LEGITIMATE_COMMERCIAL_ACTIVITY",
        "tainted_entities": [],
        "cleared_entities": ["Redwood Grading & Excavation Inc."],
    })
    r_aml_clean = compute_investigator_reward([], gold_aml_clean, gt_aml_clean)
    _record("aml_clean_business_gold", r_aml_clean, r_aml_clean["reward"] >= 0.95, ">= 0.95")

    bad_aml_false_sar = json.dumps({
        "disposition": "FILE_SAR_ESCALATE",
        "typology": "SMURFING_STRUCTURING",
        "tainted_entities": ["Redwood Grading & Excavation Inc."],
        "cleared_entities": [],
    })
    r_aml_false = compute_investigator_reward([], bad_aml_false_sar, gt_aml_clean)
    _record(
        "aml_false_sar_on_clean_business",
        r_aml_false,
        r_aml_false["reward"] < 0.0 and "false_positive_sar_on_clean_business" in r_aml_false["violations"],
        "< 0.0 false-SAR penalty",
    )

    # 5. Track 2 Future Room Biometric Co-Pilot (Gold vs Othello-Error -1.0 Cliff)
    gt_bio_othello = {
        "track": "track2_future",
        "domain": "future_room_biometric_copilot",
        "subject_state": "OTHELLO_INNOCENT_ANXIOUS",
        "baseline_adjusted_pattern": "GENERALIZED_ANXIETY_NON_SPECIFIC",
    }
    gold_bio_othello = json.dumps({
        "baseline_adjusted_pattern": "GENERALIZED_ANXIETY_NON_SPECIFIC",
        "innocent_physiological_alternative": (
            "Sustained HR (124 BPM) and EDA (8.1 uS) across both neutral control and case prompts "
            "reflect generalized fear of wrongful suspicion (Othello Error), not concealed offense memory."
        ),
        "recommended_interview_action": "De-escalate pressure, maintain neutral PEACE rapport, and verify alibi via desk records.",
    })
    r_bio_gold = compute_investigator_reward([], gold_bio_othello, gt_bio_othello)
    _record("track2_biometric_othello_gold", r_bio_gold, r_bio_gold["reward"] >= 0.95, ">= 0.95")

    bad_bio_false_accuse = json.dumps({
        "baseline_adjusted_pattern": "GENERALIZED_ANXIETY_NON_SPECIFIC",
        "innocent_physiological_alternative": "Subject might be nervous.",
        "recommended_interview_action": "Press harder; elevated sweat indicates deception and subject is lying.",
    })
    r_bio_cliff_1 = compute_investigator_reward([], bad_bio_false_accuse, gt_bio_othello)
    _record(
        "track2_othello_cliff_false_deception_claim",
        r_bio_cliff_1,
        r_bio_cliff_1["reward"] == -1.0 and "othello_error_cliff_triggered" in r_bio_cliff_1["violations"],
        "exact -1.0 Othello-Error Cliff",
    )

    gt_bio_trauma = {
        "track": "track2_future",
        "domain": "future_room_biometric_copilot",
        "subject_state": "TRAUMA_WITNESS",
        "baseline_adjusted_pattern": "TRAUMA_SENSORY_AFFECT_RECALL",
    }
    bad_bio_missing_inno = json.dumps({
        "baseline_adjusted_pattern": "TRAUMA_SENSORY_AFFECT_RECALL",
        "innocent_physiological_alternative": "",
        "recommended_interview_action": "Use PEACE open free recall.",
    })
    r_bio_cliff_2 = compute_investigator_reward([], bad_bio_missing_inno, gt_bio_trauma)
    _record(
        "track2_othello_cliff_omitted_innocent_alternative",
        r_bio_cliff_2,
        r_bio_cliff_2["reward"] == -1.0 and "othello_error_cliff_triggered" in r_bio_cliff_2["violations"],
        "exact -1.0 Othello-Error Cliff on omitted innocent_physiological_alternative",
    )

    # 6. Cross-check all 9 External Adapter Gold Outputs + Framework Wrappers
    from training.external_adapters.chunked_10gb_adapters import _synthetic_mock_fixtures

    for conv_name, conv_fn, mock_raw in _synthetic_mock_fixtures():
        adapted = conv_fn(mock_raw, "train", 0)
        res_adapted = compute_investigator_reward(
            adapted["messages"][:-1],
            adapted["messages"][-1]["content"],
            adapted["ground_truth"],
        )
        _record(f"external_adapter_gold_{conv_name}", res_adapted, res_adapted["reward"] >= 0.95, ">= 0.95")

    trl_scores = trl_grpo_reward_fn(
        prompts=[[], []],
        completions=[[{"role": "assistant", "content": gold_bio_othello}], [{"role": "assistant", "content": bad_bio_false_accuse}]],
        ground_truth=[gt_bio_othello, gt_bio_othello],
    )
    assert trl_scores[0] >= 0.95 and trl_scores[1] == -1.0, f"Unexpected TRL scores: {trl_scores}"
    assert verl_compute_score("aml_laundering_hunter", gold_aml_clean, gt_aml_clean) >= 0.95
    orl = openrlhf_reward_func(["PROMPT\n" + gold_911], ["PROMPT\n"], [gt_911])
    assert orl["rewards"][0] >= 0.95
    checks_passed += 3

    return {
        "status": "PASS",
        "total_assertions_passed": checks_passed,
        "cases": report_cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SPEC 7 Deterministic RLVR / GRPO Reward Verifier Suite.")
    parser.add_argument("--self-test", action="store_true", help="Run comprehensive gold & adversarial reward self-tests.")
    args = parser.parse_args(argv)

    if args.self_test:
        t0 = time.perf_counter()
        summary = run_self_test()
        summary["elapsed_sec"] = round(time.perf_counter() - t0, 4)
        print(json.dumps(summary, indent=2))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
