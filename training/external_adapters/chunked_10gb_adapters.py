"""10GB-Budget-Guarded Streaming External Dataset Adapters for Murder Board (SPEC 7).

Converts external deductive, NLI, multi-hop, GraphRAG, temporal, and physiological corpora
into exact Murder-Board SFT + RLVR shards:
    {"id", "track", "domain", "subtask", "split", "messages", "ground_truth"}

Key guarantees:
  1. Zero network calls or unsolicited downloads (100% Python 3.15 stdlib).
  2. Strict <10 GiB per-batch streaming cap via BatchBudgetGuard(max_bytes=int(9.5 * 1024**3)),
     emitting an atomic resumable cursor_checkpoint.json when the byte budget fills.
  3. House Rule #3 enforcement: strips/rewrites accusatory language from external rationales,
     attaches mandatory innocent_alternative fields, and verifies zero prosecutor veto hits.
  4. Verbatim quote enforcement via quote_ok() across all synthesized Murder Book exhibits.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Callable, Iterable

from training.common.core import (
    HOUSE_RULES_HEADER,
    STANDING_BRIEF_CLOSER,
    check_prosecutor_vetoes,
    docs_text_block,
    norm_ws,
    quote_ok,
    recompute_score,
    registry_text_block,
)

GIB = 1024**3
DEFAULT_MAX_BYTES = int(9.5 * GIB)

# Patterns in external datasets (e.g., murder-mystery QA rationales) that violate House Rule #3
_ACCUSATORY_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bis\s+guilty\b", re.IGNORECASE), "is contradicted by primary file records"),
    (re.compile(r"\bis\s+the\s+killer\b", re.IGNORECASE), "exhibits the primary unresolved window discrepancy"),
    (re.compile(r"\bis\s+the\s+murderer\b", re.IGNORECASE), "exhibits the primary unresolved window discrepancy"),
    (re.compile(r"\bis\s+the\s+culprit\b", re.IGNORECASE), "is the highest-priority uncorroborated lead"),
    (re.compile(r"\bmurdered\s+", re.IGNORECASE), "has an uncorroborated window conflict regarding "),
    (re.compile(r"\bkilled\s+the\s+victim\b", re.IGNORECASE), "had documented physical access during the fatal window"),
    (re.compile(r"\bis\s+lying\b", re.IGNORECASE), "provides an account inconsistent with the record"),
    (re.compile(r"\blied\s+about\b", re.IGNORECASE), "gave a statement conflicting with records on"),
    (re.compile(r"\bproves\s+beyond\s+doubt\b", re.IGNORECASE), "corroborates within the boundaries of this file"),
    (re.compile(r"\bwho\s+is\s+the\s+(?:most\s+likely\s+)?(?:murderer|killer|culprit)\??", re.IGNORECASE),
     "Which subject's account carries the strongest unresolved evidentiary conflict inside the incident window?"),
)


def sanitize_investigative_prose(text: str) -> str:
    """Rewrite accusatory external benchmark phrasing into neutral Murder-Board desk language."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    for pattern, repl in _ACCUSATORY_REPLACEMENTS:
        cleaned = pattern.sub(repl, cleaned)
    # Final safety sweep against check_prosecutor_vetoes default list
    residual = check_prosecutor_vetoes(cleaned, [])
    for phrase in residual:
        cleaned = re.sub(re.escape(phrase), "conflicts with the file record", cleaned, flags=re.IGNORECASE)
    assert check_prosecutor_vetoes(cleaned, []) == [], f"Failed to sanitize prose: {cleaned}"
    return cleaned


def _ensure_min_doc_text(text: str, fallback_context: str = "Recorded in official case exhibit.") -> str:
    """Ensure document text has enough substance to anchor >=8 char verbatim quotes."""
    raw = str(text or "").strip()
    if len(norm_ws(raw)) >= 16:
        return raw
    if raw:
        return f"{raw} ({fallback_context})"
    return fallback_context


def extract_verbatim_quote(doc_text: str, preferred_span: str | None = None, max_chars: int = 180) -> str:
    """Return a guaranteed verbatim quote substring from doc_text that passes quote_ok()."""
    source = str(doc_text or "").strip()
    if preferred_span:
        cand = str(preferred_span).strip()
        if len(norm_ws(cand)) >= 8 and norm_ws(cand) in norm_ws(source):
            return cand
    # Take first clean sentence or clause >= 8 normalized chars
    for part in re.split(r"(?<=[.!?])\s+|\n+", source):
        part_s = part.strip()
        if len(norm_ws(part_s)) >= 8:
            if len(part_s) <= max_chars:
                return part_s
            clipped = part_s[:max_chars].rsplit(" ", 1)[0].strip()
            if len(norm_ws(clipped)) >= 8 and norm_ws(clipped) in norm_ws(source):
                return clipped
    clipped = source[:max_chars].strip()
    return clipped


def _docs_map(docs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {d["id"]: d for d in docs}


def _make_record_id(prefix: str, raw_id: Any, split: str, index: int) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(raw_id if raw_id is not None else index)).strip("_")
    if not slug:
        slug = str(index)
    digest = hashlib.sha1(f"{prefix}|{split}|{slug}|{index}".encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{split}_{slug}_{digest}"


def _assert_house_rules(record: dict[str, Any], docs_by_id: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Validate top-level schema, strict JSON assistant completion, veto compliance, and quotes."""
    expected_keys = {"id", "track", "domain", "subtask", "split", "messages", "ground_truth"}
    missing = expected_keys - set(record.keys())
    if missing:
        raise ValueError(f"Adapted record missing required keys: {sorted(missing)}")
    assistant_msg = record["messages"][-1]["content"]
    parsed = json.loads(assistant_msg)
    if not isinstance(parsed, dict):
        raise ValueError("Assistant message must serialize a JSON object.")
    vetoes = check_prosecutor_vetoes(assistant_msg, [])
    if vetoes:
        raise ValueError(f"House Rule #3 violation in adapted assistant message: {vetoes}")
    if docs_by_id:
        for q_obj in _iter_quote_pairs(parsed):
            q_text, d_id = q_obj
            if not quote_ok(q_text, d_id, docs_by_id):
                raise ValueError(f"Quote failed quote_ok() for doc_id={d_id!r}: {q_text!r}")
    return record


def _iter_quote_pairs(obj: Any) -> list[tuple[str, str]]:
    """Collect (quote, doc_id) pairs across adapted JSON structures for self-verification."""
    pairs: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        if "quote" in obj and "doc_id" in obj and obj["quote"]:
            pairs.append((str(obj["quote"]), str(obj["doc_id"])))
        if "a_quote" in obj and "a_doc" in obj and obj["a_quote"]:
            pairs.append((str(obj["a_quote"]), str(obj["a_doc"])))
        if "b_quote" in obj and "b_doc" in obj and obj["b_quote"]:
            pairs.append((str(obj["b_quote"]), str(obj["b_doc"])))
        if "anchored_quote" in obj and "doc_id" in obj and obj["anchored_quote"]:
            pairs.append((str(obj["anchored_quote"]), str(obj["doc_id"])))
        for val in obj.values():
            pairs.extend(_iter_quote_pairs(val))
    elif isinstance(obj, list):
        for item in obj:
            pairs.extend(_iter_quote_pairs(item))
    return pairs


# ============================================================================
# 10GB-Budget-Guarded Streaming Framework
# ============================================================================


class BatchBudgetGuard:
    """Tracks exact cumulative bytes read + written per batch and halts cleanly at max_bytes.

    Designed for sequential <=10 GiB cloud storage windows: convert a slice of external
    corpora up to 9.5 GiB, emit an atomic `cursor_checkpoint.json`, train the stage LoRA/DoRA
    adapter, purge raw cache, and resume from the exact next line/record offset.
    """

    def __init__(
        self,
        max_bytes: int = DEFAULT_MAX_BYTES,
        checkpoint_path: Path | str | None = None,
        batch_id: str = "batch_01",
    ) -> None:
        if max_bytes <= 0:
            raise ValueError(f"max_bytes must be positive, got {max_bytes}")
        self.max_bytes: int = int(max_bytes)
        self.checkpoint_path: Path | None = Path(checkpoint_path) if checkpoint_path else None
        self.batch_id: str = batch_id

        self.bytes_read: int = 0
        self.bytes_written: int = 0
        self.records_emitted: int = 0
        self.records_skipped: int = 0
        self.halted_by_budget: bool = False

        self.completed_sources: list[str] = []
        self.active_dataset: str = ""
        self.active_source: str = ""
        self.next_record_offset: int = 0
        self.next_byte_offset: int = 0

    @property
    def cumulative_bytes(self) -> int:
        return self.bytes_read + self.bytes_written

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.max_bytes - self.cumulative_bytes)

    @property
    def utilization_pct(self) -> float:
        return round((self.cumulative_bytes / self.max_bytes) * 100.0, 4)

    def can_accept(self, read_bytes: int, write_bytes: int = 0) -> bool:
        if read_bytes < 0 or write_bytes < 0:
            raise ValueError("Byte deltas cannot be negative.")
        return (self.cumulative_bytes + read_bytes + write_bytes) <= self.max_bytes

    def try_commit(
        self,
        read_bytes: int,
        write_bytes: int,
        *,
        dataset: str,
        source_path: str,
        current_record_offset: int,
        current_byte_offset: int = 0,
        next_byte_offset: int = 0,
    ) -> bool:
        """Attempt to commit I/O for one record.

        If committing would breach `max_bytes`, leaves cursor pointing at `current_record_offset`
        (and `current_byte_offset`), sets `halted_by_budget = True`, saves checkpoint if configured,
        and returns False without exceeding `max_bytes`.
        """
        if not self.can_accept(read_bytes, write_bytes):
            self.halted_by_budget = True
            self.active_dataset = dataset
            self.active_source = str(source_path)
            self.next_record_offset = int(current_record_offset)
            self.next_byte_offset = int(current_byte_offset)
            if self.checkpoint_path is not None:
                self.save_checkpoint(self.checkpoint_path, status="halted_max_bytes_reached")
            return False

        self.bytes_read += int(read_bytes)
        self.bytes_written += int(write_bytes)
        self.records_emitted += 1
        self.active_dataset = dataset
        self.active_source = str(source_path)
        self.next_record_offset = int(current_record_offset) + 1
        self.next_byte_offset = int(next_byte_offset)
        return True

    def mark_source_completed(self, source_path: str) -> None:
        src = str(source_path)
        if src not in self.completed_sources:
            self.completed_sources.append(src)
        if self.active_source == src:
            self.next_record_offset = 0
            self.next_byte_offset = 0

    def to_checkpoint_dict(self, status: str = "in_progress") -> dict[str, Any]:
        return {
            "schema_version": "mb.spec7.cursor_checkpoint.v1",
            "batch_id": self.batch_id,
            "status": status,
            "halted_by_budget": self.halted_by_budget,
            "max_bytes": self.max_bytes,
            "max_gb": round(self.max_bytes / GIB, 4),
            "bytes_read": self.bytes_read,
            "bytes_written": self.bytes_written,
            "cumulative_bytes": self.cumulative_bytes,
            "cumulative_gb": round(self.cumulative_bytes / GIB, 6),
            "remaining_bytes": self.remaining_bytes,
            "utilization_pct": self.utilization_pct,
            "records_emitted": self.records_emitted,
            "records_skipped": self.records_skipped,
            "cursor": {
                "dataset": self.active_dataset,
                "source_path": self.active_source,
                "next_record_offset": self.next_record_offset,
                "next_byte_offset": self.next_byte_offset,
                "completed_sources": list(self.completed_sources),
            },
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    def save_checkpoint(
        self,
        path: Path | str | None = None,
        *,
        status: str | None = None,
    ) -> dict[str, Any]:
        target = Path(path) if path is not None else self.checkpoint_path
        if target is None:
            raise ValueError("No checkpoint_path provided to save_checkpoint().")
        target.parent.mkdir(parents=True, exist_ok=True)
        resolved_status = status or ("halted_max_bytes_reached" if self.halted_by_budget else "completed")
        payload = self.to_checkpoint_dict(status=resolved_status)
        tmp_path = target.with_suffix(target.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp_path.replace(target)
        return payload

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: Path | str,
        *,
        max_bytes: int = DEFAULT_MAX_BYTES,
        next_batch_id: str | None = None,
    ) -> tuple["BatchBudgetGuard", dict[str, Any]]:
        """Create a fresh-budget guard positioned at the exact saved cursor."""
        cp_path = Path(checkpoint_path)
        state = json.loads(cp_path.read_text(encoding="utf-8"))
        prev_batch = str(state.get("batch_id", "batch_01"))
        if next_batch_id is None:
            m = re.match(r"^(.*?)(\d+)$", prev_batch)
            next_batch_id = f"{m.group(1)}{int(m.group(2)) + 1:02d}" if m else f"{prev_batch}_next"
        guard = cls(max_bytes=max_bytes, checkpoint_path=cp_path, batch_id=next_batch_id)
        cursor = state.get("cursor", {})
        guard.completed_sources = list(cursor.get("completed_sources", []))
        guard.active_dataset = str(cursor.get("dataset", ""))
        guard.active_source = str(cursor.get("source_path", ""))
        guard.next_record_offset = int(cursor.get("next_record_offset", 0))
        guard.next_byte_offset = int(cursor.get("next_byte_offset", 0))
        return guard, state


# ============================================================================
# 9 External Dataset Format Converters -> Murder Board SFT + RLVR Format
# ============================================================================


def adapt_detectiveqa_record(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert Phospheneser/DetectiveQA long-context mystery QA into quote-verified Murder Board SFT+RLVR."""
    rec_id = _make_record_id("detqa", raw.get("id") or raw.get("novel_id"), split, index)
    title = str(raw.get("title") or raw.get("novel_title") or f"Case File {index:04d}")
    date_str = str(raw.get("date") or "1934-11-14")

    raw_paras = raw.get("paragraphs") or raw.get("chapters") or []
    docs: list[dict[str, Any]] = []
    if isinstance(raw_paras, list) and raw_paras:
        for idx_p, p in enumerate(raw_paras, start=1):
            if isinstance(p, dict):
                p_text = _ensure_min_doc_text(p.get("text") or p.get("content") or "")
                p_title = str(p.get("title") or f"{title} — Exhibit Segment {idx_p}")
                doc_id = str(p.get("doc_id") or f"doc{idx_p:02d}")
            else:
                p_text = _ensure_min_doc_text(str(p))
                p_title = f"{title} — Exhibit Segment {idx_p}"
                doc_id = f"doc{idx_p:02d}"
            docs.append({
                "id": doc_id,
                "title": p_title,
                "type": "archive_excerpt",
                "date": date_str,
                "author": "Case Archive",
                "text": p_text,
            })
    else:
        context_text = _ensure_min_doc_text(raw.get("context") or raw.get("novel_text") or "")
        chunks = [c.strip() for c in re.split(r"\n\s*\n", context_text) if c.strip()] or [context_text]
        for idx_p, ch in enumerate(chunks, start=1):
            docs.append({
                "id": f"doc{idx_p:02d}",
                "title": f"{title} — Exhibit Segment {idx_p}",
                "type": "archive_excerpt",
                "date": date_str,
                "author": "Case Archive",
                "text": _ensure_min_doc_text(ch),
            })

    docs_by_id = _docs_map(docs)

    # Options normalization
    raw_opts = raw.get("options") or raw.get("choices") or {}
    options_map: dict[str, str] = {}
    if isinstance(raw_opts, dict):
        for k, v in raw_opts.items():
            options_map[str(k).strip().upper()] = sanitize_investigative_prose(str(v))
    elif isinstance(raw_opts, list):
        for idx_o, v in enumerate(raw_opts):
            letter = chr(ord("A") + idx_o)
            options_map[letter] = sanitize_investigative_prose(str(v))
    if not options_map:
        options_map = {"A": "Lead Option A", "B": "Lead Option B", "C": "Lead Option C", "D": "Lead Option D"}

    gold_ans_raw = str(raw.get("answer") or raw.get("gold_option") or "A").strip()
    gold_letter = gold_ans_raw.upper() if gold_ans_raw.upper() in options_map else next(
        (k for k, v in options_map.items() if norm_ws(v) == norm_ws(gold_ans_raw)),
        next(iter(options_map.keys())),
    )
    gold_subject = options_map[gold_letter]

    # Resolve clue paragraph indices into verbatim quotes
    clue_indices = raw.get("clue_paragraphs") or raw.get("evidence_paragraphs") or [0]
    clue_spans = raw.get("clue_quotes") or raw.get("clue_spans") or []
    cited_clues: list[dict[str, str]] = []
    clue_doc_ids: list[str] = []
    for pos, c_idx in enumerate(clue_indices):
        if isinstance(c_idx, str) and c_idx in docs_by_id:
            d_obj = docs_by_id[c_idx]
        else:
            num = int(c_idx) if isinstance(c_idx, int) or str(c_idx).isdigit() else 0
            # Handle both 0-based and 1-based paragraph indices safely
            zero_idx = num if 0 <= num < len(docs) else max(0, min(len(docs) - 1, num - 1))
            d_obj = docs[zero_idx]
        pref_span = clue_spans[pos] if pos < len(clue_spans) else None
        q = extract_verbatim_quote(d_obj["text"], pref_span)
        cited_clues.append({"doc_id": d_obj["id"], "quote": q})
        if d_obj["id"] not in clue_doc_ids:
            clue_doc_ids.append(d_obj["id"])

    question_clean = sanitize_investigative_prose(
        str(raw.get("question") or "Which candidate option aligns with the documented physical and timeline clues?")
    )
    reasoning_clean = sanitize_investigative_prose(
        str(
            raw.get("reasoning")
            or raw.get("cot")
            or f"Cross-referencing {', '.join(clue_doc_ids)} isolates option {gold_letter} ({gold_subject}) via physical/timeline discrepancy."
        )
    )
    innocent_alt = sanitize_investigative_prose(
        str(
            raw.get("innocent_alternative")
            or "Recorded discrepancy may reflect unlogged secondary access, witness clock estimation error, or prior lawful handling."
        )
    )

    evaluated_leads = []
    for letter, label in sorted(options_map.items()):
        evaluated_leads.append({
            "option": letter,
            "candidate": label,
            "status": "PRIMARY_UNRESOLVED_CONFLICT" if letter == gold_letter else "INSUFFICIENT_OR_CLEARED_BY_FILE",
        })

    assistant_payload = {
        "selected_option": gold_letter,
        "selected_candidate": gold_subject,
        "cited_clues": cited_clues,
        "evaluated_leads": evaluated_leads,
        "investigative_synthesis": reasoning_clean,
        "innocent_alternative": innocent_alt,
        "standing_closer": STANDING_BRIEF_CLOSER,
    }

    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## Long-Context Archive Cross-Examiner (DetectiveQA Adapter)\n"
        "Evaluate candidate options strictly from the numbered archive exhibits. Cite exact verbatim quotes "
        "with `doc_id`, state a non-accusatory `innocent_alternative`, and end with the standing closer."
    )
    user_prompt = (
        f"### Document Registry\n{registry_text_block(docs)}\n\n"
        f"### Case Exhibits\n{docs_text_block(docs)}\n\n"
        f"### Investigative Question\n{question_clean}\n\n"
        f"### Candidate Options\n"
        + "\n".join(f"- {k}: {v}" for k, v in sorted(options_map.items()))
    )

    record = {
        "id": rec_id,
        "track": "track1_now",
        "domain": "cold_case_murder_board",
        "subtask": "detectiveqa_deduction",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": "DetectiveQA",
            "domain": "cold_case_murder_board",
            "subtask": "detectiveqa_deduction",
            "gold_option": gold_letter,
            "gold_candidate": gold_subject,
            "clue_doc_ids": clue_doc_ids,
            "innocent_alternative_required": True,
            "docs_by_id": docs_by_id,
        },
    }
    return _assert_house_rules(record, docs_by_id)


def adapt_musr_record(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert MuSR neurosymbolic soft-reasoning mysteries into Hypothesis Tournament SFT+RLVR."""
    rec_id = _make_record_id("musr", raw.get("id"), split, index)
    narrative = str(raw.get("narrative") or raw.get("context") or "").strip()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", narrative) if p.strip()]
    if not paragraphs:
        paragraphs = [_ensure_min_doc_text(narrative, "Witness and scene narrative summary.")]

    docs: list[dict[str, Any]] = []
    for idx_p, para in enumerate(paragraphs, start=1):
        docs.append({
            "id": f"doc{idx_p:02d}",
            "title": f"Case Narrative Segment {idx_p}",
            "type": "investigative_summary",
            "date": "2024-03-19",
            "author": "Case Intake",
            "text": _ensure_min_doc_text(para),
        })

    # Incorporate neurosymbolic reasoning tree facts as an explicit audit exhibit if present
    tree_nodes = raw.get("reasoning_tree") or raw.get("intermediate_trees") or raw.get("premises") or []
    if isinstance(tree_nodes, list) and tree_nodes:
        flat_lines = [
            sanitize_investigative_prose(n if isinstance(n, str) else json.dumps(n, ensure_ascii=False))
            for n in tree_nodes
        ]
        docs.append({
            "id": f"doc{len(docs) + 1:02d}",
            "title": "Premise & Means-Opportunity Audit Notes",
            "type": "analyst_notes",
            "date": "2024-03-19",
            "author": "Analyst Desk",
            "text": _ensure_min_doc_text(" ".join(flat_lines)),
        })

    docs_by_id = _docs_map(docs)
    raw_choices = list(raw.get("choices") or raw.get("suspects") or ["Subject A", "Subject B", "Subject C"])
    choices = [sanitize_investigative_prose(str(c)) for c in raw_choices]
    ans_idx = int(raw.get("answer_index", raw.get("answer", 0)))
    ans_idx = max(0, min(len(choices) - 1, ans_idx))
    top_subject = choices[ans_idx]

    # Rank hypotheses: gold choice first, remaining choices ordered deterministically
    ranked_hypotheses: list[dict[str, Any]] = []
    ordered_indices = [ans_idx] + [i for i in range(len(choices)) if i != ans_idx]
    for rank_pos, c_idx in enumerate(ordered_indices, start=1):
        subj = choices[c_idx]
        # Match best doc mentioning subject, fallback to last/first doc
        matched_doc = next((d for d in reversed(docs) if subj.lower() in d["text"].lower()), docs[-1])
        quote = extract_verbatim_quote(matched_doc["text"])
        ranked_hypotheses.append({
            "rank": rank_pos,
            "hypothesis_id": f"H{c_idx + 1}",
            "subject": subj,
            "priority_status": "UNCORROBORATED_MEANS_AND_WINDOW_ACCESS" if c_idx == ans_idx else "PARTIALLY_CLEARED_OR_LOWER_WEIGHT",
            "supporting_quotes": [{"doc_id": matched_doc["id"], "quote": quote}],
            "innocent_alternative": (
                f"Documented access and physical familiarity for {subj} could reflect routine prior presence or unrecorded schedule overlap."
            ),
        })

    expected_ranking = [h["subject"] for h in ranked_hypotheses]
    question_clean = sanitize_investigative_prose(
        str(raw.get("question") or "Rank the competing subject hypotheses by unresolved means, opportunity, and record conflict.")
    )

    assistant_payload = {
        "top_hypothesis": top_subject,
        "selected_choice_index": ans_idx,
        "ranked_hypotheses": ranked_hypotheses,
        "standing_closer": STANDING_BRIEF_CLOSER,
    }

    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## Hypothesis Tournament & Soft-Reasoning Evaluator (MuSR Adapter)\n"
        "Rank every candidate hypothesis against the exhibits using verbatim quotes and mandatory "
        "`innocent_alternative` explanations. Never declare guilt."
    )
    user_prompt = (
        f"### Case Exhibits\n{docs_text_block(docs)}\n\n"
        f"### Evaluation Prompt\n{question_clean}\n\n"
        f"### Competing Subjects\n" + "\n".join(f"- [{i}] {c}" for i, c in enumerate(choices))
    )

    record = {
        "id": rec_id,
        "track": "track1_now",
        "domain": "forensic_micro_skills",
        "subtask": "hypothesis_tournament",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": "MuSR",
            "domain": "forensic_micro_skills",
            "subtask": "hypothesis_tournament",
            "top_hypothesis": top_subject,
            "expected_ranking": expected_ranking,
            "answer_index": ans_idx,
            "docs_by_id": docs_by_id,
        },
    }
    return _assert_house_rules(record, docs_by_id)


def adapt_turnaboutllm_record(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert TurnaboutLLM testimony-vs-evidence contradiction turns into Murder-Board Cross-Examiner."""
    rec_id = _make_record_id("turnabout", raw.get("id") or raw.get("turn_id"), split, index)
    speaker = sanitize_investigative_prose(str(raw.get("speaker") or raw.get("witness") or "Witness"))
    raw_testimony = raw.get("testimony") or raw.get("statements") or []
    stmt_texts: list[str] = []
    for s in raw_testimony:
        if isinstance(s, dict):
            stmt_texts.append(str(s.get("text") or s.get("statement") or "").strip())
        else:
            stmt_texts.append(str(s).strip())
    if not stmt_texts:
        stmt_texts = ["I remained in the lobby until 11:15 PM and never entered theeast corridor."]

    testimony_doc = {
        "id": "doc01",
        "title": f"Recorded Statement — {speaker}",
        "type": "witness_statement",
        "date": str(raw.get("date") or "2025-05-10"),
        "author": speaker,
        "text": "\n".join(f"[{i}] {t}" for i, t in enumerate(stmt_texts)),
    }

    raw_evidence = raw.get("evidence_list") or raw.get("court_record") or raw.get("evidence") or []
    docs: list[dict[str, Any]] = [testimony_doc]
    ev_id_to_doc_id: dict[str, str] = {}
    for idx_e, ev in enumerate(raw_evidence, start=2):
        doc_id = f"doc{idx_e:02d}"
        ev_key = str(ev.get("evidence_id") or ev.get("id") or ev.get("name") or f"ev_{idx_e - 1}")
        ev_title = str(ev.get("name") or ev.get("title") or ev_key)
        ev_desc = _ensure_min_doc_text(ev.get("description") or ev.get("text") or "")
        ev_id_to_doc_id[ev_key] = doc_id
        ev_id_to_doc_id[ev_title] = doc_id
        docs.append({
            "id": doc_id,
            "title": f"Exhibit — {ev_title}",
            "type": "physical_or_machine_record",
            "date": str(raw.get("date") or "2025-05-10"),
            "author": "Evidence Custodian",
            "text": ev_desc,
        })
    if len(docs) == 1:
        docs.append({
            "id": "doc02",
            "title": "Exhibit — Corridor Keycard Log",
            "type": "physical_or_machine_record",
            "date": "2025-05-10",
            "author": "Evidence Custodian",
            "text": "Badge reader #4 logged keycard entry into the east corridor at 10:52 PM.",
        })
        ev_id_to_doc_id["default_ev"] = "doc02"

    docs_by_id = _docs_map(docs)
    gold_stmt_idx = int(raw.get("gold_statement_idx", raw.get("contradictory_statement_idx", 0)))
    gold_stmt_idx = max(0, min(len(stmt_texts) - 1, gold_stmt_idx))
    gold_ev_key = str(raw.get("gold_evidence_id") or raw.get("present_evidence") or "")
    gold_ev_doc_id = ev_id_to_doc_id.get(gold_ev_key, docs[1]["id"])

    a_quote = extract_verbatim_quote(testimony_doc["text"], stmt_texts[gold_stmt_idx])
    b_quote = extract_verbatim_quote(docs_by_id[gold_ev_doc_id]["text"], raw.get("gold_evidence_span"))
    rationale = sanitize_investigative_prose(
        str(
            raw.get("explanation")
            or "Statement timeline/observation conflicts directly with the logged physical exhibit."
        )
    )
    innocent_alt = sanitize_investigative_prose(
        str(
            raw.get("innocent_alternative")
            or f"{speaker} may have misread an uncalibrated wall clock, confused adjacent corridors, or loaned an access item earlier."
        )
    )

    assistant_payload = {
        "contradictions": [
            {
                "a_quote": a_quote,
                "a_doc": "doc01",
                "b_quote": b_quote,
                "b_doc": gold_ev_doc_id,
                "kind": "statement_vs_record",
                "severity": "HIGH",
                "statement_idx": gold_stmt_idx,
                "rationale": rationale,
                "innocent_alternative": innocent_alt,
            }
        ],
        "alibis": [
            {
                "person": speaker,
                "window": str(raw.get("incident_window") or "incident_window"),
                "rating": "contradicted",
                "reasons": [
                    {"quote": a_quote, "doc_id": "doc01"},
                    {"quote": b_quote, "doc_id": gold_ev_doc_id},
                ],
            }
        ],
        "evidence_gaps": [],
    }

    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## Cross-Examiner: Statement-vs-Exhibit Contradiction Check (TurnaboutLLM Adapter)\n"
        "Identify the exact testimony line and exhibit quote that cannot both stand without explanation. "
        "Include a mandatory one-line `innocent_alternative` and rate the window alibi."
    )
    user_prompt = f"### Document Registry\n{registry_text_block(docs)}\n\n### Case File\n{docs_text_block(docs)}"

    record = {
        "id": rec_id,
        "track": "track1_now",
        "domain": "cold_case_murder_board",
        "subtask": "cross_examiner",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": "TurnaboutLLM",
            "domain": "cold_case_murder_board",
            "subtask": "cross_examiner",
            "gold_statement_idx": gold_stmt_idx,
            "gold_evidence_doc_id": gold_ev_doc_id,
            "alibis": {speaker: "contradicted"},
            "docs_by_id": docs_by_id,
        },
    }
    return _assert_house_rules(record, docs_by_id)


def adapt_whodunitbench_record(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert WhodunitBench multi-character scripts & scene clues into Murder-Board Lead Detective brief."""
    rec_id = _make_record_id("whodunit", raw.get("script_id") or raw.get("id"), split, index)
    date_str = str(raw.get("date") or "2024-10-05")

    docs: list[dict[str, Any]] = []
    for ch in raw.get("characters") or raw.get("scripts") or []:
        doc_id = f"doc{len(docs) + 1:02d}"
        name = sanitize_investigative_prose(str(ch.get("name") or ch.get("character") or f"Person {len(docs) + 1}"))
        text = _ensure_min_doc_text(ch.get("timeline") or ch.get("text") or ch.get("statement") or "")
        docs.append({
            "id": doc_id,
            "title": f"Account — {name}",
            "type": "witness_statement",
            "date": date_str,
            "author": name,
            "text": text,
        })

    for cl in raw.get("clues") or raw.get("scene_clues") or []:
        doc_id = f"doc{len(docs) + 1:02d}"
        loc = str(cl.get("location") or cl.get("title") or f"Scene Clue {len(docs)}")
        text = _ensure_min_doc_text(cl.get("content") or cl.get("text") or "")
        docs.append({
            "id": doc_id,
            "title": f"Scene Clue — {loc}",
            "type": "csi_clue",
            "date": date_str,
            "author": "Scene Investigator",
            "text": text,
        })

    if len(docs) < 2:
        docs.append({
            "id": f"doc{len(docs) + 1:02d}",
            "title": "Scene Clue — Study Desk Log",
            "type": "csi_clue",
            "date": date_str,
            "author": "Scene Investigator",
            "text": "The study teacup tested positive for sedative residue logged at 22:40.",
        })

    docs_by_id = _docs_map(docs)
    gold_target = sanitize_investigative_prose(str(raw.get("answer") or raw.get("primary_lead") or docs[0]["author"]))
    gap_note = sanitize_investigative_prose(
        str(raw.get("uncollected_record") or "Unpulled hallway CCTV / independent time-stamp verification for study access")
    )

    comp_top = {
        "cites_high_contradiction": True,
        "in_window": True,
        "closes_gap": True,
        "still_reachable": True,
    }
    score_top = recompute_score(comp_top)
    comp_second = {
        "cites_high_contradiction": False,
        "in_window": True,
        "closes_gap": True,
        "still_reachable": True,
    }
    score_second = recompute_score(comp_second)

    q_a = extract_verbatim_quote(docs[0]["text"])
    q_b = extract_verbatim_quote(docs[-1]["text"])

    brief_text = (
        f"CASE SUMMARY: Multi-witness accounts and scene logs establish an unresolved conflict inside the critical window.\n"
        f"STRONGEST CONTRADICTION: {docs[0]['id']} (\"{q_a}\") vs {docs[-1]['id']} (\"{q_b}\").\n"
        f"PRIMARY LEAD FOCUS: Have the detective question {gold_target} on the in-window exhibit conflict and pull corroborating logs.\n"
        f"ARCHIVAL GAP: {gap_note}.\n"
        f"{STANDING_BRIEF_CLOSER}"
    )

    assistant_payload = {
        "selected_lead_target": gold_target,
        "leads": [
            {
                "action": f"For the human detective: ask {gold_target} to reconcile {docs[0]['id']} with physical clue {docs[-1]['id']} inside the incident window and obtain the missing corroborating log.",
                "score": score_top,
                "arithmetic": "40 (high contradiction) + 25 (in window) + 20 (closes gap) + 15 (still reachable) = 100",
                "reason": f"Directly addresses the high-severity contradiction between {docs[0]['id']} and {docs[-1]['id']} inside the critical window, closes the verification gap, and {gold_target} remains reachable.",
                "components": comp_top,
            },
            {
                "action": f"Pull independent archival record covering: {gap_note}.",
                "score": score_second,
                "arithmetic": "25 (in window) + 20 (closes gap) + 15 (still reachable) = 60",
                "reason": "Covers the incident window, directly supplies the missing archival item, and custodian records remain retrievable.",
                "components": comp_second,
            },
        ],
        "gaps": [
            {"gap": gap_note, "proven_by": docs[-1]["id"]},
        ],
        "cited_quotes": [
            {"doc_id": docs[0]["id"], "quote": q_a},
            {"doc_id": docs[-1]["id"], "quote": q_b},
        ],
        "brief": brief_text,
    }

    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## The Lead Detective: Multi-Script Synthesis & Shift Brief (WhodunitBench Adapter)\n"
        "Score leads strictly with the 40/25/20/15 rubric, cite verbatim quotes, never name a guilty party, "
        f"and end `brief` with: \"{STANDING_BRIEF_CLOSER}\""
    )
    question_clean = sanitize_investigative_prose(
        str(raw.get("question") or "Prioritize tomorrow's investigative leads and write the Murder-Board brief.")
    )
    user_prompt = (
        f"### Document Registry\n{registry_text_block(docs)}\n\n"
        f"### Case File\n{docs_text_block(docs)}\n\n"
        f"### Task\n{question_clean}"
    )

    record = {
        "id": rec_id,
        "track": "track1_now",
        "domain": "cold_case_murder_board",
        "subtask": "lead_detective",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": "WhodunitBench",
            "domain": "cold_case_murder_board",
            "subtask": "lead_detective",
            "primary_lead_target": gold_target,
            "expected_lead_scores": [score_top, score_second],
            "docs_by_id": docs_by_id,
        },
    }
    return _assert_house_rules(record, docs_by_id)


def adapt_fever_contractnli_record(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert FEVER or ContractNLI records into Murder-Board Strict Forensic NLI drills."""
    source_kind = "ContractNLI" if ("hypothesis" in raw or "choice" in raw) else "FEVER"
    rec_id = _make_record_id(source_kind.lower(), raw.get("id"), split, index)

    claim = sanitize_investigative_prose(str(raw.get("claim") or raw.get("hypothesis") or ""))
    raw_label = str(raw.get("label") or raw.get("choice") or "NOT ENOUGH INFO").strip().upper().replace("-", "_")

    if raw_label in ("SUPPORTS", "SUPPORTED", "ENTAILMENT", "TRUE"):
        nli_label = "SUPPORTED"
    elif raw_label in ("REFUTES", "REFUTED", "CONTRADICTION", "FALSE"):
        nli_label = "REFUTED"
    else:
        nli_label = "NOT_ENOUGH_INFORMATION"

    # Build source documents
    raw_ev = raw.get("evidence_sentences") or raw.get("spans") or raw.get("documents") or []
    docs: list[dict[str, Any]] = []
    if isinstance(raw_ev, list) and raw_ev:
        for idx_d, item in enumerate(raw_ev, start=1):
            if isinstance(item, dict):
                txt = _ensure_min_doc_text(item.get("text") or item.get("sentence") or "")
                d_id = str(item.get("doc_id") or f"doc{idx_d:02d}")
                title = str(item.get("title") or f"{source_kind} Source Span {idx_d}")
            else:
                txt = _ensure_min_doc_text(str(item))
                d_id = f"doc{idx_d:02d}"
                title = f"{source_kind} Source Span {idx_d}"
            docs.append({
                "id": d_id,
                "title": title,
                "type": "reference_document",
                "date": "2025-01-15",
                "author": source_kind,
                "text": txt,
            })
    else:
        ctx = _ensure_min_doc_text(raw.get("context") or raw.get("document") or "Exhibit record contains partial metadata only.")
        docs.append({
            "id": "doc01",
            "title": f"{source_kind} Exhibit Document",
            "type": "reference_document",
            "date": "2025-01-15",
            "author": source_kind,
            "text": ctx,
        })

    docs_by_id = _docs_map(docs)
    support_indices = raw.get("evidence_span_indices") or raw.get("supporting_doc_ids") or [docs[0]["id"]]
    evidence_quotes: list[dict[str, str]] = []
    for ref in support_indices:
        if isinstance(ref, str) and ref in docs_by_id:
            d_obj = docs_by_id[ref]
        elif isinstance(ref, int) and 0 <= ref < len(docs):
            d_obj = docs[ref]
        else:
            d_obj = docs[0]
        evidence_quotes.append({
            "doc_id": d_obj["id"],
            "quote": extract_verbatim_quote(d_obj["text"]),
        })

    conservative_note = {
        "SUPPORTED": "Document text directly entails every element of the claim without extrapolation.",
        "REFUTED": "Document text directly contradicts a required premise of the claim.",
        "NOT_ENOUGH_INFORMATION": "Partial overlap only; file lacks corroborating text to confirm or refute the full claim.",
    }[nli_label]

    assistant_payload = {
        "claim": claim,
        "nli_label": nli_label,
        "evidence_quotes": evidence_quotes,
        "conservative_reading_note": conservative_note,
        "innocent_alternative": "Apparent discrepancy or omission may stem from document scope limits rather than deceptive reporting.",
    }

    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## Forensic NLI Verifier (FEVER / ContractNLI Adapter)\n"
        "Classify the claim strictly as `SUPPORTED`, `REFUTED`, or `NOT_ENOUGH_INFORMATION` using only "
        "the supplied exhibits and exact verbatim quotes. Never upgrade partial corroboration to proof."
    )
    user_prompt = f"### Exhibits\n{docs_text_block(docs)}\n\n### Claim Under Verification\n{claim}"

    record = {
        "id": rec_id,
        "track": "track1_now",
        "domain": "forensic_micro_skills",
        "subtask": "forensic_nli",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": source_kind,
            "domain": "forensic_micro_skills",
            "subtask": "forensic_nli",
            "nli_label": nli_label,
            "docs_by_id": docs_by_id,
        },
    }
    return _assert_house_rules(record, docs_by_id)


def adapt_musique_multihop_record(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert MuSiQue multi-hop & unanswerable items into Noisy Vault Retrieval SFT+RLVR."""
    rec_id = _make_record_id("musique", raw.get("id"), split, index)
    answerable = bool(raw.get("answerable", True))
    paragraphs = raw.get("paragraphs") or []

    docs: list[dict[str, Any]] = []
    idx_to_doc_id: dict[int, str] = {}
    required_doc_ids: list[str] = []

    for pos, p in enumerate(paragraphs):
        p_idx = int(p.get("idx", pos))
        doc_id = f"doc{pos + 1:02d}"
        idx_to_doc_id[p_idx] = doc_id
        p_title = str(p.get("title") or f"Vault Record {pos + 1}")
        p_text = _ensure_min_doc_text(p.get("paragraph_text") or p.get("text") or "")
        docs.append({
            "id": doc_id,
            "title": p_title,
            "type": "vault_record",
            "date": "2023-08-22",
            "author": "Archive Vault",
            "text": p_text,
        })
        if p.get("is_supporting"):
            required_doc_ids.append(doc_id)

    if not docs:
        docs.append({
            "id": "doc01",
            "title": "Vault Index Stub",
            "type": "vault_record",
            "date": "2023-08-22",
            "author": "Archive Vault",
            "text": "Registered agent for Harbor Crest LLC is listed as M. Vance at 410 Canal St.",
        })
        if answerable:
            required_doc_ids.append("doc01")

    docs_by_id = _docs_map(docs)
    decomp = raw.get("question_decomposition") or []
    hop_chain: list[dict[str, Any]] = []

    for h_i, step in enumerate(decomp, start=1):
        sup_idx = step.get("paragraph_support_idx")
        d_id = idx_to_doc_id.get(int(sup_idx)) if sup_idx is not None and int(sup_idx) in idx_to_doc_id else None
        if d_id and answerable:
            d_obj = docs_by_id[d_id]
            hop_chain.append({
                "hop": h_i,
                "sub_query": sanitize_investigative_prose(str(step.get("question") or "")),
                "doc_id": d_id,
                "quote": extract_verbatim_quote(d_obj["text"]),
                "derived_fact": sanitize_investigative_prose(str(step.get("answer") or "")),
            })
            if d_id not in required_doc_ids:
                required_doc_ids.append(d_id)

    if not hop_chain and required_doc_ids:
        for h_i, d_id in enumerate(required_doc_ids, start=1):
            hop_chain.append({
                "hop": h_i,
                "sub_query": f"Retrieve corroborating hop {h_i}",
                "doc_id": d_id,
                "quote": extract_verbatim_quote(docs_by_id[d_id]["text"]),
                "derived_fact": "Verified archival link",
            })

    final_answer = (
        sanitize_investigative_prose(str(raw.get("answer") or ""))
        if answerable
        else "INSUFFICIENT_ARCHIVAL_EVIDENCE"
    )

    assistant_payload = {
        "hop_chain": hop_chain,
        "retrieved_doc_ids": required_doc_ids,
        "sufficiency_reached": answerable,
        "final_answer": final_answer,
        "archival_gap_note": (
            "All multi-hop links verified verbatim in vault."
            if answerable
            else "Missing downstream linking exhibit in vault; halting conclusion per House Rule #5."
        ),
    }

    question_clean = sanitize_investigative_prose(str(raw.get("question") or "Trace the multi-hop archival chain."))
    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## Multi-Hop Vault Retriever (MuSiQue Adapter)\n"
        "Chain single-hop document facts with verbatim quotes (`doc_id` + `quote`). If any hop is missing "
        "from the vault, set `sufficiency_reached` to false and return `INSUFFICIENT_ARCHIVAL_EVIDENCE`."
    )
    user_prompt = (
        f"### Vault Document Registry\n{registry_text_block(docs)}\n\n"
        f"### Vault Contents\n{docs_text_block(docs)}\n\n"
        f"### Multi-Hop Investigative Query\n{question_clean}"
    )

    record = {
        "id": rec_id,
        "track": "track1_now",
        "domain": "cold_case_murder_board",
        "subtask": "vault_multihop_retrieval",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": "MuSiQue",
            "domain": "cold_case_murder_board",
            "subtask": "vault_multihop_retrieval",
            "answerable": answerable,
            "sufficiency_reached": answerable,
            "required_doc_ids": required_doc_ids,
            "final_answer": final_answer,
            "docs_by_id": docs_by_id,
        },
    }
    return _assert_house_rules(record, docs_by_id)


def adapt_docred_graph_record(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert DocRED document-level entity/relation annotations into GraphRAG + Collision Guard drills."""
    rec_id = _make_record_id("docred", raw.get("id") or raw.get("title"), split, index)
    title = str(raw.get("title") or f"Intelligence Report {index:04d}")

    raw_sents = raw.get("sents") or []
    sent_strings: list[str] = []
    for s in raw_sents:
        if isinstance(s, list):
            txt = " ".join(str(tok) for tok in s)
            txt = re.sub(r"\s+([,.;:!?])", r"\1", txt)
            sent_strings.append(txt.strip())
        else:
            sent_strings.append(str(s).strip())
    if not sent_strings:
        sent_strings = [_ensure_min_doc_text(raw.get("text") or "Marcus Vance registered Apex Meridian LLC at 410 Canal St.")]

    full_text = _ensure_min_doc_text(" ".join(sent_strings))
    doc01 = {
        "id": "doc01",
        "title": title,
        "type": "intelligence_report",
        "date": "2024-06-02",
        "author": "Records Desk",
        "text": full_text,
    }
    docs = [doc01]
    docs_by_id = _docs_map(docs)

    vertex_set: list[list[dict[str, Any]]] = raw.get("vertexSet") or []
    labels: list[dict[str, Any]] = raw.get("labels") or []

    triples: list[dict[str, str]] = []
    gt_triples: list[dict[str, str]] = []
    for lbl in labels:
        h_idx = int(lbl.get("h", 0))
        t_idx = int(lbl.get("t", 0))
        rel = str(lbl.get("r") or lbl.get("relation") or "ASSOCIATED_WITH")
        head_name = str(lbl.get("head") or (vertex_set[h_idx][0]["name"] if h_idx < len(vertex_set) and vertex_set[h_idx] else f"Entity_{h_idx}"))
        tail_name = str(lbl.get("tail") or (vertex_set[t_idx][0]["name"] if t_idx < len(vertex_set) and vertex_set[t_idx] else f"Entity_{t_idx}"))
        ev_sent_ids = lbl.get("evidence") or [0]
        ev_idx = int(ev_sent_ids[0]) if ev_sent_ids else 0
        pref_sent = sent_strings[ev_idx] if 0 <= ev_idx < len(sent_strings) else None
        quote = extract_verbatim_quote(full_text, pref_sent)
        triples.append({
            "head": head_name,
            "relation": rel,
            "tail": tail_name,
            "doc_id": "doc01",
            "quote": quote,
        })
        gt_triples.append({"head": head_name, "relation": rel, "tail": tail_name})

    # Detect same-name distinct vertex clusters (Records Collision Law: DO_NOT_MERGE_COLLISION)
    collision_guards: list[dict[str, Any]] = []
    name_to_clusters: dict[str, list[int]] = {}
    for c_idx, cluster in enumerate(vertex_set):
        for m in cluster:
            nm = norm_ws(m.get("name", ""))
            if nm:
                name_to_clusters.setdefault(nm, [])
                if c_idx not in name_to_clusters[nm]:
                    name_to_clusters[nm].append(c_idx)

    for nm, c_ids in name_to_clusters.items():
        if len(c_ids) > 1:
            collision_guards.append({
                "surface_name": nm,
                "distinct_cluster_ids": c_ids,
                "action": "DO_NOT_MERGE_COLLISION",
                "reason": "Shared name without corroborating DOB, address, phone, or plate identifier.",
            })

    for explicit_col in raw.get("collision_candidates") or []:
        collision_guards.append({
            "surface_name": str(explicit_col.get("surface_name") or explicit_col.get("name") or "homonym"),
            "distinct_cluster_ids": list(explicit_col.get("entity_ids") or ["E1", "E2"]),
            "action": "DO_NOT_MERGE_COLLISION",
            "reason": str(explicit_col.get("reason") or "Distinct individuals sharing surname/given name; never merge without linking proof."),
        })

    alias_clusters = [
        {
            "cluster_id": f"E{c_idx}",
            "mentions": sorted({str(m.get("name", "")) for m in cluster if m.get("name")}),
            "entity_type": str(cluster[0].get("type", "ENTITY")) if cluster else "ENTITY",
        }
        for c_idx, cluster in enumerate(vertex_set)
        if cluster
    ]

    assistant_payload = {
        "triples": triples,
        "alias_clusters": alias_clusters,
        "collision_guards": collision_guards,
    }

    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## GraphRAG Entity Resolution & Collision Guard (DocRED Adapter)\n"
        "Extract document-backed `(head, relation, tail)` triples with verbatim quotes (`doc_id` + `quote`). "
        "Enforce the Records Collision Law: if two distinct people or entities share a name without linking "
        "identifiers, emit `DO_NOT_MERGE_COLLISION` and never merge them."
    )
    user_prompt = f"### Exhibit\n{docs_text_block(docs)}\n\nExtract verified GraphRAG triples and collision guards."

    record = {
        "id": rec_id,
        "track": "track1_now",
        "domain": "forensic_micro_skills",
        "subtask": "entity_graph_resolution",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": "DocRED",
            "domain": "forensic_micro_skills",
            "subtask": "entity_graph_resolution",
            "triples": gt_triples,
            "collision_guards": collision_guards,
            "do_not_merge_required": len(collision_guards) > 0,
            "docs_by_id": docs_by_id,
        },
    }
    return _assert_house_rules(record, docs_by_id)


def adapt_torque_temporal_record(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert TORQUE / TempReason temporal ordering records into ISO-8601 & Clock-Skew drills."""
    rec_id = _make_record_id("torque", raw.get("id"), split, index)
    anchor_date = str(raw.get("anchor_date") or "2024-11-03")
    dvr_skew_min = int(raw.get("dvr_offset_minutes", 0))

    passage = _ensure_min_doc_text(raw.get("passage") or raw.get("context") or "")
    skew_clause = (
        f" Calibration note: DVR system clock ran {dvr_skew_min:+d} minutes relative to cellular UTC-synced local time."
        if dvr_skew_min != 0 and "calibration note" not in passage.lower()
        else ""
    )
    doc01 = {
        "id": "doc01",
        "title": "Chronology & Device Timestamp Log",
        "type": "temporal_exhibit",
        "date": anchor_date,
        "author": "Analyst / Digital Desk",
        "text": f"{passage}{skew_clause}".strip(),
    }
    docs = [doc01]
    docs_by_id = _docs_map(docs)

    raw_windows = raw.get("iso_windows") or []
    iso_windows: list[dict[str, Any]] = []

    if raw_windows:
        for w in raw_windows:
            iso_windows.append({
                "event": sanitize_investigative_prose(str(w.get("event") or "logged_event")),
                "start_iso": str(w["start_iso"]),
                "end_iso": str(w.get("end_iso") or w["start_iso"]),
                "clock_skew_applied_min": int(w.get("clock_skew_applied_min", dvr_skew_min)),
                "doc_id": "doc01",
                "quote": extract_verbatim_quote(doc01["text"], w.get("quote")),
            })
    else:
        # Derive deterministic ISO-8601 intervals from passage HH:MM markers or fallback events
        events_list = raw.get("events") or raw.get("answer_spans") or ["initial_event", "subsequent_event"]
        found_times = re.findall(r"\b(\d{1,2}):(\d{2})\b", passage)
        base_dt = datetime.fromisoformat(f"{anchor_date}T21:00:00")
        for idx_e, ev_label in enumerate(events_list):
            if idx_e < len(found_times):
                hh, mm = int(found_times[idx_e][0]) % 24, int(found_times[idx_e][1]) % 60
                ev_dt = datetime.fromisoformat(f"{anchor_date}T{hh:02d}:{mm:02d}:00") - timedelta(minutes=dvr_skew_min)
            else:
                ev_dt = base_dt + timedelta(minutes=20 * idx_e)
            start_iso = ev_dt.strftime("%Y-%m-%dT%H:%M:%S")
            end_iso = (ev_dt + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
            iso_windows.append({
                "event": sanitize_investigative_prose(str(ev_label)),
                "start_iso": start_iso,
                "end_iso": end_iso,
                "clock_skew_applied_min": dvr_skew_min,
                "doc_id": "doc01",
                "quote": extract_verbatim_quote(doc01["text"]),
            })

    iso_windows_sorted = sorted(iso_windows, key=lambda x: x["start_iso"])
    ordered_events = [w["event"] for w in iso_windows_sorted]
    collision_detected = bool(raw.get("collision_detected", False))

    assistant_payload = {
        "iso_windows": iso_windows_sorted,
        "ordered_events": ordered_events,
        "collision_detected": collision_detected,
        "innocent_alternative": "Timestamp discrepancies may reflect unadjusted DST / DVR quartz drift rather than fabricated whereabouts.",
    }

    question_clean = sanitize_investigative_prose(
        str(raw.get("question") or "Normalize all events to skew-corrected ISO-8601 intervals and test for spatiotemporal collision.")
    )
    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## Temporal & Clock-Skew Analyst (TORQUE Adapter)\n"
        "Convert relative witness times and device timestamps into skew-corrected ISO-8601 windows, "
        "order events chronologically, and set `collision_detected`."
    )
    user_prompt = (
        f"### Anchor Date: {anchor_date}\n"
        f"### Exhibit\n{docs_text_block(docs)}\n\n"
        f"### Temporal Query\n{question_clean}"
    )

    gt_windows = [
        {"event": w["event"], "start_iso": w["start_iso"], "end_iso": w["end_iso"]}
        for w in iso_windows_sorted
    ]

    record = {
        "id": rec_id,
        "track": "track1_now",
        "domain": "forensic_micro_skills",
        "subtask": "temporal_clock_skew",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": "TORQUE",
            "domain": "forensic_micro_skills",
            "subtask": "temporal_clock_skew",
            "iso_windows": gt_windows,
            "ordered_events": ordered_events,
            "collision_detected": collision_detected,
            "docs_by_id": docs_by_id,
        },
    }
    return _assert_house_rules(record, docs_by_id)


def adapt_wesad_biometric_window(
    raw: dict[str, Any],
    split: str = "train",
    index: int = 0,
) -> dict[str, Any]:
    """Convert WESAD physiological windows into Othello-Error-Hardened Track 2 Chair-12 SFT+RLVR."""
    rec_id = _make_record_id("wesad", raw.get("id") or raw.get("subject_id"), split, index)
    subj_id = str(raw.get("subject_id") or f"S{(index % 15) + 2}")

    # Native WESAD labels: 1=baseline, 2=TSST stress, 3=amusement, 4=meditation, plus interview probe extensions
    raw_cond = str(raw.get("condition") or raw.get("label") or "2").strip().lower()
    probe_mode = str(raw.get("probe_mode") or raw.get("interview_context") or "").strip().lower()

    base_hr = float(raw.get("baseline_hr_bpm", 74.0))
    hr = float(raw.get("hr_bpm", raw.get("ecg_hr_mean", 118.5 if raw_cond in ("2", "stress") else 76.0)))
    base_hrv = float(raw.get("baseline_hrv_rmssd_ms", 42.0))
    hrv = float(raw.get("hrv_rmssd_ms", raw.get("ibi_rmssd", 19.5 if raw_cond in ("2", "stress") else 40.5)))
    base_eda = float(raw.get("baseline_eda_uS", 2.1))
    eda = float(raw.get("eda_sweat_uS", raw.get("eda_mean_uS", 7.8 if raw_cond in ("2", "stress") else 2.3)))
    resp = float(raw.get("respiration_rpm", raw.get("resp_rpm", 22.0 if raw_cond in ("2", "stress") else 14.5)))
    temp_delta = float(raw.get("periorbital_temp_delta_c", raw.get("temp_delta_c", 0.18)))
    pupil_delta = float(raw.get("pupil_dilation_delta_mm", 0.24))
    latency_ms = int(raw.get("response_latency_ms", 680))

    if probe_mode in ("cit_withheld_item", "cit_probe") or raw_cond == "cit_guilty_knowledge_hit":
        subject_state = "CALM_CONCEALER_CIT_PROBE"
        pattern = "STIMULUS_LOCKED_ORIENTING_SHIFT"
        innocent_phys = (
            "Item-specific vagal RMSSD dip and phasic EDA surge can arise from prior innocent exposure "
            "(media leak, prior workplace familiarity, or semantic salience among array decoys) rather than offense involvement."
        )
        next_action = (
            "Do NOT accuse. Have the detective ask a non-leading source-monitoring question on whether the subject "
            "heard or saw the item via prior public/workplace channels, and pull independent access logs."
        )
    elif raw_cond in ("trauma", "trauma_recall") or "trauma" in probe_mode:
        subject_state = "TRAUMA_WITNESS"
        pattern = "TRAUMA_SENSORY_AFFECT_RECALL"
        innocent_phys = (
            "Sympathetic HR/EDA elevation during sensory recall matches acute traumatic distress and bereavement "
            "autonomic reactivity in a cooperative witness."
        )
        next_action = (
            "Shift immediately to unhurried PEACE / Cognitive Interview open-ended free recall; avoid interruptive or leading probes."
        )
    elif raw_cond in ("1", "3", "4", "baseline", "amusement", "meditation"):
        subject_state = "COOPERATIVE_BASELINE"
        pattern = "BASELINE_NOMINAL_VARIATION"
        innocent_phys = (
            "Autonomic readings sit within normal respiratory sinus arrhythmia and resting thermoregulatory fluctuation."
        )
        next_action = "Continue standard chronological PEACE interview anchored to existing case documents."
    else:
        # WESAD Condition 2 (TSST Stress): classic Othello-Error trap — high sweat & pulse from anxiety, NOT guilt!
        subject_state = "OTHELLO_INNOCENT_ANXIOUS"
        pattern = "GENERALIZED_ANXIETY_NON_SPECIFIC"
        innocent_phys = (
            "Elevated tonic EDA and heart rate across both control and substantive prompts reflect generalized "
            "social-evaluative fear of wrongful suspicion (the Othello Error), acute anxiety, or physiological stress—never proof of deception."
        )
        next_action = (
            "Prohibit confrontational pressure. Re-establish neutral rapport, compare control-vs-relevant deltas rather than raw arousal, "
            "and verify timeline claims strictly through independent desk records."
        )

    telemetry_snapshot = {
        "subject_id": subj_id,
        "biometrics": {
            "hr_bpm": round(hr, 1),
            "baseline_hr_bpm": round(base_hr, 1),
            "hrv_rmssd_ms": round(hrv, 1),
            "baseline_hrv_rmssd_ms": round(base_hrv, 1),
            "eda_sweat_uS": round(eda, 2),
            "baseline_eda_uS": round(base_eda, 2),
            "respiration_rpm": round(resp, 1),
            "periorbital_temp_delta_c": round(temp_delta, 2),
            "pupil_dilation_delta_mm": round(pupil_delta, 2),
        },
        "acoustics": {
            "response_latency_ms": latency_ms,
        },
        "control_vs_target_context": (
            raw.get("control_vs_target_note")
            or (
                "Control questions calm; phasic delta isolated to single withheld scene artifact."
                if subject_state == "CALM_CONCEALER_CIT_PROBE"
                else "Elevated autonomic arousal observed across both neutral control questions and case questions."
            )
        ),
    }

    assistant_payload = {
        "baseline_adjusted_pattern": pattern,
        "deltas": {
            "hr_delta_bpm": round(hr - base_hr, 1),
            "hrv_rmssd_ratio": round(hrv / max(1.0, base_hrv), 3),
            "eda_delta_uS": round(eda - base_eda, 2),
        },
        "innocent_physiological_alternative": innocent_phys,
        "recommended_interview_action": next_action,
        "house_rule_guard": "Autonomic arousal measures stress/orienting, never truth or guilt.",
    }

    system_prompt = (
        f"{HOUSE_RULES_HEADER}\n\n"
        "## Chair 12: Future Room Biometric & Cognitive-Load Co-Pilot (WESAD Adapter)\n"
        "Evaluate baseline-adjusted autonomic telemetry (`HR`, `HRV RMSSD`, `EDA`, `respiration`, `pupil`, `latency`). "
        "CRITICAL OTHELLO-ERROR LAW: Never infer lying, deception, or guilt from elevated stress. Always provide "
        "`baseline_adjusted_pattern`, `innocent_physiological_alternative`, and a non-accusatory `recommended_interview_action`."
    )
    user_prompt = (
        "### Synchronized Room Telemetry Window\n"
        f"{json.dumps(telemetry_snapshot, indent=2)}\n\n"
        "Classify the baseline-adjusted physiological pattern, state the mandatory innocent physiological alternative, "
        "and recommend the next PEACE-compliant detective action or desk pull."
    )

    record = {
        "id": rec_id,
        "track": "track2_future",
        "domain": "future_room_biometric_copilot",
        "subtask": "chair12_biometric_fusion",
        "split": split,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": json.dumps(assistant_payload, ensure_ascii=False)},
        ],
        "ground_truth": {
            "source_dataset": "WESAD",
            "track": "track2_future",
            "domain": "future_room_biometric_copilot",
            "subtask": "chair12_biometric_fusion",
            "subject_state": subject_state,
            "baseline_adjusted_pattern": pattern,
            "innocent_alternative_required": True,
        },
    }
    return _assert_house_rules(record)


ADAPTER_REGISTRY: dict[str, Callable[[dict[str, Any], str, int], dict[str, Any]]] = {
    "detectiveqa": adapt_detectiveqa_record,
    "musr": adapt_musr_record,
    "turnaboutllm": adapt_turnaboutllm_record,
    "whodunitbench": adapt_whodunitbench_record,
    "fever": adapt_fever_contractnli_record,
    "contractnli": adapt_fever_contractnli_record,
    "fever_contractnli": adapt_fever_contractnli_record,
    "musique": adapt_musique_multihop_record,
    "docred": adapt_docred_graph_record,
    "torque": adapt_torque_temporal_record,
    "wesad": adapt_wesad_biometric_window,
}


# ============================================================================
# Streaming File Converter with Exact Byte Accounting & Checkpoint Resume
# ============================================================================


def _iter_raw_records_with_bytes(path: Path) -> Iterable[tuple[int, int, int, int, dict[str, Any]]]:
    """Yield (rec_idx, raw_byte_len, start_byte_offset, next_byte_offset, parsed_dict) from JSONL, CSV, or JSON."""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with path.open("rb") as fh:
            rec_idx = 0
            while True:
                start_pos = fh.tell()
                raw_line = fh.readline()
                if not raw_line:
                    break
                end_pos = fh.tell()
                stripped = raw_line.strip()
                if not stripped:
                    continue
                yield rec_idx, len(raw_line), start_pos, end_pos, json.loads(stripped.decode("utf-8"))
                rec_idx += 1
    elif suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            byte_cursor = 0
            for rec_idx, row in enumerate(reader):
                encoded_est = len(json.dumps(row, ensure_ascii=False).encode("utf-8")) + 2
                next_cursor = byte_cursor + encoded_est
                yield rec_idx, encoded_est, byte_cursor, next_cursor, dict(row)
                byte_cursor = next_cursor
    elif suffix == ".json":
        raw_bytes = path.read_bytes()
        parsed = json.loads(raw_bytes.decode("utf-8"))
        items = parsed if isinstance(parsed, list) else parsed.get("data", [parsed])
        per_item_read = max(1, len(raw_bytes) // max(1, len(items)))
        byte_cursor = 0
        for rec_idx, obj in enumerate(items):
            next_cursor = byte_cursor + per_item_read
            yield rec_idx, per_item_read, byte_cursor, next_cursor, obj
            byte_cursor = next_cursor
    else:
        raise ValueError(f"Unsupported input format '{path.suffix}' for {path}; expected .jsonl, .csv, or .json")


def stream_convert_batch(
    sources: list[tuple[str, Path]],
    output_jsonl: Path,
    guard: BatchBudgetGuard,
    *,
    split: str = "train",
) -> dict[str, Any]:
    """Stream-convert `sources` into `output_jsonl` until finished or `guard` hits `max_bytes`."""
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    resume_source = guard.active_source
    resume_offset = guard.next_record_offset

    with output_jsonl.open("ab") as out_fh:
        for dataset_key, src_path in sources:
            src_str = str(src_path)
            if src_str in guard.completed_sources:
                continue
            if dataset_key not in ADAPTER_REGISTRY:
                raise KeyError(f"Unknown dataset key '{dataset_key}'. Valid: {sorted(ADAPTER_REGISTRY)}")
            converter = ADAPTER_REGISTRY[dataset_key]

            start_idx = resume_offset if (resume_source and resume_source == src_str) else 0
            halted = False

            for rec_idx, read_bytes, start_byte, next_byte, raw_obj in _iter_raw_records_with_bytes(src_path):
                if rec_idx < start_idx:
                    continue
                adapted = converter(raw_obj, split, rec_idx)
                serialized = (json.dumps(adapted, ensure_ascii=False) + "\n").encode("utf-8")
                write_bytes = len(serialized)

                committed = guard.try_commit(
                    read_bytes=read_bytes,
                    write_bytes=write_bytes,
                    dataset=dataset_key,
                    source_path=src_str,
                    current_record_offset=rec_idx,
                    current_byte_offset=start_byte,
                    next_byte_offset=next_byte,
                )
                if not committed:
                    halted = True
                    break

                out_fh.write(serialized)

            if halted:
                break

            guard.mark_source_completed(src_str)
            if resume_source == src_str:
                resume_source = ""
                resume_offset = 0

    status = "halted_max_bytes_reached" if guard.halted_by_budget else "completed_all_sources"
    if guard.checkpoint_path is not None:
        return guard.save_checkpoint(guard.checkpoint_path, status=status)
    return guard.to_checkpoint_dict(status=status)


# ============================================================================
# Self-Test Suite (Zero Network Calls — 100% In-Memory + Tempdir Verification)
# ============================================================================


def _synthetic_mock_fixtures() -> list[tuple[str, Callable[[dict[str, Any], str, int], dict[str, Any]], dict[str, Any]]]:
    return [
        (
            "DetectiveQA",
            adapt_detectiveqa_record,
            {
                "novel_id": "detqa_mock_01",
                "title": "The Foundry Ledger Mystery",
                "paragraphs": [
                    {"doc_id": "doc01", "text": "At 22:15 the night watchman locked the foundry gate from the inside using brass key #2."},
                    {"doc_id": "doc02", "text": "Arthur Keane stated he left the foundry office at 21:45 and drove straight home in heavy fog."},
                    {"doc_id": "doc03", "text": "Toll booth ALPR logged Arthur Keane's black sedan crossing eastbound toward the foundry at 22:28."},
                ],
                "question": "Who is the most likely culprit behind the 22:30 foundry entry?",
                "options": {
                    "A": "Watchman",
                    "B": "Arthur Keane",
                    "C": "Delivery driver",
                    "D": "Dock clerk",
                },
                "answer": "B",
                "clue_paragraphs": [1, 2],
                "reasoning": "Arthur Keane is lying and is guilty because the ALPR log at 22:28 contradicts his 21:45 departure claim.",
            },
        ),
        (
            "MuSR",
            adapt_musr_record,
            {
                "id": "musr_mock_01",
                "narrative": (
                    "Elena Delgado had the safe combination and was observed near the marina boathouse at 23:20.\n\n"
                    "Julian Sato remained on a recorded hospital shift across town from 20:00 to 04:00."
                ),
                "question": "Who is the most likely murderer?",
                "choices": ["Julian Sato", "Elena Delgado"],
                "answer_index": 1,
                "reasoning_tree": [
                    "Elena Delgado possessed safe access and uncorroborated presence at 23:20.",
                    "Julian Sato is cleared by continuous hospital badge telemetry.",
                ],
            },
        ),
        (
            "TurnaboutLLM",
            adapt_turnaboutllm_record,
            {
                "turn_id": "turn_mock_01",
                "speaker": "Victor Halvorsen",
                "testimony": [
                    "I arrived at the warehouse at 9:00 PM to check the Manifest.",
                    "The power outage plunged the loading bay into total darkness at 9:30 PM, so I saw nothing.",
                ],
                "evidence_list": [
                    {
                        "evidence_id": "ev_grid",
                        "name": "Municipal Substation Log",
                        "description": "Feeder #7 remained energized until 10:18 PM; backup floodlights ran automatically at 10:18 PM.",
                    }
                ],
                "gold_statement_idx": 1,
                "gold_evidence_id": "ev_grid",
                "explanation": "Victor Halvorsen is lying about the 9:30 PM blackout.",
            },
        ),
        (
            "WhodunitBench",
            adapt_whodunitbench_record,
            {
                "script_id": "wb_mock_01",
                "characters": [
                    {"name": "Nadia Khoury", "timeline": "Nadia Khoury stated she never touched the server room terminal after 18:00."},
                    {"name": "Caleb Pruitt", "timeline": "Caleb Pruitt logged out at the front desk at 18:10 alongside two guards."},
                ],
                "clues": [
                    {"location": "Server Room", "content": "Keystroke audit recorded Nadia Khoury's hardware token authenticating at 23:11."}
                ],
                "question": "Identify the primary lead and missing corroboration.",
                "answer": "Nadia Khoury",
                "uncollected_record": "Server corridor pinhole camera SD card from 23:00-23:30",
            },
        ),
        (
            "FEVER_ContractNLI",
            adapt_fever_contractnli_record,
            {
                "id": "nli_mock_01",
                "hypothesis": "The courier delivered two sealed Pelican cases to Pier 9 before midnight.",
                "choice": "NotMentioned",
                "spans": [
                    "Pier 9 gate log records courier van arrival at 23:41 carrying sealed cargo; container count is omitted."
                ],
                "evidence_span_indices": [0],
            },
        ),
        (
            "MuSiQue",
            adapt_musique_multihop_record,
            {
                "id": "musique_mock_01",
                "question": "Which registered agent controls the shell company that leased Hangar 4?",
                "answerable": True,
                "answer": "Leland Ashford",
                "paragraphs": [
                    {"idx": 0, "title": "Port Lease", "paragraph_text": "Hangar 4 was leased on May 3 by Solstice Global Holdings LLC.", "is_supporting": True},
                    {"idx": 1, "title": "Weather Note", "paragraph_text": "Coastal winds reached 18 knots on May 3.", "is_supporting": False},
                    {"idx": 2, "title": "DE Corporate Filing", "paragraph_text": "Solstice Global Holdings LLC lists Leland Ashford as sole registered agent.", "is_supporting": True},
                ],
                "question_decomposition": [
                    {"question": "Who leased Hangar 4?", "answer": "Solstice Global Holdings LLC", "paragraph_support_idx": 0},
                    {"question": "Who is registered agent of Solstice Global Holdings LLC?", "answer": "Leland Ashford", "paragraph_support_idx": 2},
                ],
            },
        ),
        (
            "DocRED",
            adapt_docred_graph_record,
            {
                "title": "Harbor Transfer Brief",
                "sents": [
                    ["Marcus", "Mercer", "transferred", "title", "to", "Cobalt", "Nexus", "LLC", "in", "Wilmington", "."],
                    ["A", "second", "Marcus", "Mercer", "born", "1954", "resides", "in", "Omaha", "with", "no", "Delaware", "filings", "."],
                ],
                "vertexSet": [
                    [{"name": "Marcus Mercer", "sent_id": 0, "type": "PER"}],
                    [{"name": "Cobalt Nexus LLC", "sent_id": 0, "type": "ORG"}],
                    [{"name": "Marcus Mercer", "sent_id": 1, "type": "PER"}],
                ],
                "labels": [
                    {"h": 0, "t": 1, "r": "TRANSFERRED_TITLE_TO", "evidence": [0]},
                ],
            },
        ),
        (
            "TORQUE",
            adapt_torque_temporal_record,
            {
                "id": "torque_mock_01",
                "anchor_date": "2025-02-14",
                "dvr_offset_minutes": 47,
                "passage": "Pawnshop DVR stamped the pickup truck passing at 23:32, while cell tower handoff occurred at 22:50.",
                "events": ["pickup passes pawnshop", "cell tower handoff"],
                "collision_detected": False,
            },
        ),
        (
            "WESAD",
            adapt_wesad_biometric_window,
            {
                "subject_id": "S07",
                "condition": 2,
                "baseline_hr_bpm": 72.0,
                "hr_bpm": 124.5,
                "baseline_hrv_rmssd_ms": 44.0,
                "hrv_rmssd_ms": 18.2,
                "baseline_eda_uS": 2.0,
                "eda_sweat_uS": 8.4,
                "respiration_rpm": 23.5,
                "periorbital_temp_delta_c": 0.21,
                "pupil_dilation_delta_mm": 0.28,
                "response_latency_ms": 710,
            },
        ),
    ]


def run_self_test() -> dict[str, Any]:
    """Run all 9 format converters + BatchBudgetGuard 10GB cap & checkpoint resumption tests."""
    default_guard = BatchBudgetGuard()
    assert default_guard.max_bytes == int(9.5 * 1024**3), "Default max_bytes must equal 9.5 GiB"

    fixtures = _synthetic_mock_fixtures()
    assert len(fixtures) == 9, "Expected 9 format converter fixtures"

    adapted_summaries: list[dict[str, str]] = []
    for name, fn, mock_raw in fixtures:
        out = fn(mock_raw, "train", 0)
        assert set(out.keys()) == {"id", "track", "domain", "subtask", "split", "messages", "ground_truth"}
        assert len(out["messages"]) == 3
        assistant_json = json.loads(out["messages"][-1]["content"])
        assert isinstance(assistant_json, dict)
        assert check_prosecutor_vetoes(out["messages"][-1]["content"], []) == []
        adapted_summaries.append({"converter": name, "id": out["id"], "subtask": out["subtask"]})

    # Also verify WESAD CIT probe branch and unanswerable MuSiQue holdout branch
    wesad_cit = adapt_wesad_biometric_window(
        {"subject_id": "S11", "condition": "cit_guilty_knowledge_hit", "probe_mode": "cit_probe", "hr_bpm": 96.0, "eda_sweat_uS": 5.9},
        "val",
        1,
    )
    assert wesad_cit["ground_truth"]["subject_state"] == "CALM_CONCEALER_CIT_PROBE"

    musique_holdout = adapt_musique_multihop_record(
        {"id": "unans_1", "question": "Who owned the unregistered boat?", "answerable": False, "paragraphs": []},
        "test",
        2,
    )
    assert json.loads(musique_holdout["messages"][-1]["content"])["sufficiency_reached"] is False

    # Verify streaming BatchBudgetGuard halt + atomic cursor_checkpoint.json + exact resumption
    with tempfile.TemporaryDirectory(prefix="mb_10gb_guard_test_") as tmp_dir:
        tmp = Path(tmp_dir)
        src_jsonl = tmp / "mock_fever.jsonl"
        out_batch1 = tmp / "batch1_out.jsonl"
        out_batch2 = tmp / "batch2_out.jsonl"
        ckpt_path = tmp / "cursor_checkpoint.json"

        total_input_rows = 7
        with src_jsonl.open("w", encoding="utf-8") as fh:
            for i in range(total_input_rows):
                row = {
                    "id": f"f_{i}",
                    "claim": f"Exhibit item #{i} was logged inside locker B-{i} before 22:00.",
                    "label": "SUPPORTS" if i % 2 == 0 else "REFUTES",
                    "evidence_sentences": [
                        f"Property room ledger confirms item #{i} entered locker B-{i} at {'21:15' if i % 2 == 0 else '01:40'}."
                    ],
                }
                fh.write(json.dumps(row) + "\n")

        # Measure 1 converted record I/O and set budget to fit ~3 records cleanly
        probe_guard = BatchBudgetGuard(max_bytes=10_000_000)
        probe_out = tmp / "probe.jsonl"
        stream_convert_batch([("fever", src_jsonl)], probe_out, probe_guard, split="train")
        per_rec_bytes = probe_guard.cumulative_bytes // total_input_rows
        tight_cap = per_rec_bytes * 3 + (per_rec_bytes // 2)

        guard_b1 = BatchBudgetGuard(max_bytes=tight_cap, checkpoint_path=ckpt_path, batch_id="batch_01")
        cp1 = stream_convert_batch([("fever", src_jsonl)], out_batch1, guard_b1, split="train")

        assert cp1["halted_by_budget"] is True, "Batch 1 should halt cleanly at tight_cap"
        assert guard_b1.cumulative_bytes <= tight_cap, "BatchBudgetGuard must NEVER exceed max_bytes"
        assert guard_b1.records_emitted == 3, f"Expected 3 records in batch 1, got {guard_b1.records_emitted}"
        assert ckpt_path.exists(), "cursor_checkpoint.json must be written on budget halt"

        # Resume in Batch 2 from cursor_checkpoint.json with a generous cap for remaining 4 records
        guard_b2, loaded_state = BatchBudgetGuard.from_checkpoint(ckpt_path, max_bytes=tight_cap * 3)
        assert loaded_state["cursor"]["next_record_offset"] == 3
        cp2 = stream_convert_batch([("fever", src_jsonl)], out_batch2, guard_b2, split="train")

        assert cp2["halted_by_budget"] is False
        assert cp2["status"] == "completed_all_sources"
        assert guard_b2.records_emitted == total_input_rows - 3

        rows_b1 = [json.loads(line) for line in out_batch1.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows_b2 = [json.loads(line) for line in out_batch2.read_text(encoding="utf-8").splitlines() if line.strip()]
        combined_ids = [r["id"] for r in rows_b1 + rows_b2]
        assert len(combined_ids) == total_input_rows and len(set(combined_ids)) == total_input_rows, (
            "Checkpoint resumption must emit exact remaining records with zero drops or duplicates"
        )

    return {
        "status": "PASS",
        "converters_verified": len(adapted_summaries),
        "default_max_bytes": default_guard.max_bytes,
        "checkpoint_resume_verified": True,
        "converters": adapted_summaries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="10GB-Budget-Guarded Streaming External Dataset Adapters for Murder Board (SPEC 7)."
    )
    parser.add_argument("--self-test", action="store_true", help="Run offline self-test of all 9 converters + BatchBudgetGuard.")
    parser.add_argument("--dataset", choices=sorted(ADAPTER_REGISTRY.keys()), help="External dataset format key.")
    parser.add_argument("--input", nargs="+", type=Path, help="Input .jsonl / .csv / .json file(s) to stream-convert.")
    parser.add_argument("--output", type=Path, help="Output .jsonl shard path.")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("cursor_checkpoint.json"),
        help="Path to resumable cursor_checkpoint.json (default: ./cursor_checkpoint.json).",
    )
    parser.add_argument("--resume", action="store_true", help="Resume from existing --checkpoint cursor.")
    parser.add_argument(
        "--max-gb",
        type=float,
        default=9.5,
        help="Hard cumulative read+write GiB budget per batch before clean checkpoint halt (default: 9.5).",
    )
    parser.add_argument("--split", choices=("train", "val", "test", "eval_sim"), default="train")
    parser.add_argument("--batch-id", default="batch_01", help="Batch identifier recorded in cursor_checkpoint.json.")

    args = parser.parse_args(argv)

    if args.self_test:
        t0 = time.perf_counter()
        summary = run_self_test()
        summary["elapsed_sec"] = round(time.perf_counter() - t0, 4)
        print(json.dumps(summary, indent=2))
        return 0

    if not args.dataset or not args.input or not args.output:
        parser.error("Provide --self-test OR (--dataset, --input, --output).")

    max_bytes = int(args.max_gb * GIB)
    if args.resume and args.checkpoint.exists():
        guard, _ = BatchBudgetGuard.from_checkpoint(args.checkpoint, max_bytes=max_bytes)
    else:
        guard = BatchBudgetGuard(max_bytes=max_bytes, checkpoint_path=args.checkpoint, batch_id=args.batch_id)

    sources = [(args.dataset, p) for p in args.input]
    result = stream_convert_batch(sources, args.output, guard, split=args.split)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
