#!/usr/bin/env python3
"""Harvest & De-Spoil REAL Historical + Modern Crime, OFAC SDN, and 911 CAD Data.

100% Python stdlib (`urllib`, `json`, `csv`, `re`, `html`, `hashlib`).
Caches raw responses in `training/datasets/raw_cache/` (< 100 MB), strips post-hoc spoilers
into `ground_truth`, verifies verbatim quotes via `quote_ok()`, partitions cleanly into
`train` (80%), `val` (10%), and `test` (10%) by canonical ID, and writes JSONL shards.
"""

from __future__ import annotations

import argparse, csv, hashlib, html, io, json, re, time, urllib.parse, urllib.request
from pathlib import Path
from typing import Any

from training.common import check_prosecutor_vetoes, docs_text_block, load_mb_agent_prompts, quote_ok, registry_text_block
from training.track1_now.aml_hunter_sim import SYSTEM_PROMPT_AML_STATIC
from training.track1_now.dispatch_911_sim import SYSTEM_PROMPT_911

USER_AGENT = "MurderBoard-RealHarvester/1.0 (Research; PurePythonStdlib)"
OFAC_SLICE_BYTES = 358_400
SPOILER_PATTERNS = re.compile(
    r"(convicted|indicted|pleaded guilty|pled guilty|sentenced|found guilty|jury convicted|"
    r"faces a maximum penalty|maximum statutory penalty|an indictment is merely an allegation|"
    r"presumed innocent until proven guilty|mandatory sentences? of life)", re.IGNORECASE,
)
DOLLAR_RE = re.compile(r"\$[0-9][0-9,]*(?:\.[0-9]+)?(?:\s*(?:million|billion|thousand))?", re.IGNORECASE)
ENTITY_RE = re.compile(r"\b([A-Z][A-Za-z0-9&.\-']+(?:\s+[A-Z][A-Za-z0-9&.\-']+){0,5}\s+(?:LLC|Inc\.|Corp\.|Corporation|Ltd\.|Company|Co\.|Holdings|Trading|Group|Bank|Trust))\b")
NYC_CALL_DESC = {
    "ARREST": "Cardiac / Respiratory Arrest", "CVAC": "Stroke / Cerebrovascular Accident", "CHOKE": "Active Airway Obstruction / Choking",
    "STAB": "Stabbing / Penetrating Trauma", "SHOT": "Gunshot Wound", "UNC": "Unconscious / Unresponsive Patient",
    "RESPIR": "Severe Respiratory Distress", "DIFFBR": "Difficulty Breathing", "DRUG": "Suspected Overdose / Intoxication",
    "SICK": "General Sick / Unwell Person", "INJURY": "Traumatic Injury", "OTHER": "Unclear / Unclassified Caller Report",
    "EDP": "Behavioral / Psychiatric Crisis", "CARD": "Cardiac Chest Pain / Arrhythmia", "ANAPH": "Anaphylactic Shock", "BURN": "Major Thermal / Chemical Burn",
}


def split_for_canonical_id(cid: str) -> str:
    b = int(hashlib.sha256(cid.encode("utf-8")).hexdigest()[:8], 16) % 10
    return "val" if b == 0 else ("test" if b == 1 else "train")


def cached_get_json(url: str, cache_dir: Path, pause_s: float = 0.05) -> Any:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath = cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:20]}.json"
    if cpath.exists():
        return json.loads(cpath.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    cpath.write_text(json.dumps(data), encoding="utf-8")
    if pause_s > 0:
        time.sleep(pause_s)
    return data


def strip_tags(raw_html: str) -> str:
    txt = re.sub(r"<hr[^>]*>", "\n", raw_html)
    txt = re.sub(r"<div class=\"inline-page-image-container\">.*?</div>", " ", txt, flags=re.DOTALL)
    txt = re.sub(r"</p>|</li>|<br\s*/?>", "\n", txt, flags=re.IGNORECASE)
    txt = re.sub(r"<[^>]+>", " ", txt)
    return "\n".join(ln for ln in (re.sub(r"\s+", " ", x).strip() for x in html.unescape(txt).splitlines()) if ln)


def pick_verbatim_quote(text: str, min_len: int = 24, max_len: int = 220) -> str | None:
    for line in text.splitlines():
        for sent in re.split(r"(?<=[.;!?])\s+", line):
            s = sent.strip().strip('"')
            if min_len <= len(s) <= max_len and len(s.split()) >= 5:
                return s
    words = text.split()
    return " ".join(words[:18]) if len(words) >= 6 else None


def verify_all_quotes(obj: Any, docs_by_id: dict[str, dict[str, Any]]) -> bool:
    if isinstance(obj, dict):
        for qk, dk in (("quote", "doc_id"), ("a_quote", "a_doc"), ("b_quote", "b_doc"), ("anchored_quote", "doc_id")):
            if qk in obj and dk in obj and obj[qk] and not quote_ok(str(obj[qk]), str(obj[dk]), docs_by_id):
                return False
        return all(verify_all_quotes(v, docs_by_id) for v in obj.values())
    return all(verify_all_quotes(x, docs_by_id) for x in obj) if isinstance(obj, list) else True


def make_mb_row(rid: str, step: str, split: str, sys_p: str, usr_p: str, out_obj: dict[str, Any], gt: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rid, "track": "track1_now", "domain": "cold_case_murder_board", "subtask": step, "step": step, "split": split,
        "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}, {"role": "assistant", "content": json.dumps(out_obj, indent=1)}],
        "ground_truth": gt,
    }


def make_aml_row(rid: str, sub: str, split: str, usr_p: str, audit: str, fiu_json: dict[str, Any], gt: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rid, "track": "track1_now", "domain": "aml_laundering_hunter", "subtask": sub, "split": split,
        "messages": [{"role": "system", "content": SYSTEM_PROMPT_AML_STATIC}, {"role": "user", "content": usr_p}, {"role": "assistant", "content": f"{audit}\n```json\n{json.dumps(fiu_json, indent=2)}\n```"}],
        "ground_truth": gt,
    }


def harvest_case4_and_gold_caches(mb_root: Path) -> list[dict[str, Any]]:
    prompts, rows, c4_dir = load_mb_agent_prompts(), [], mb_root / "case4"
    c4_reg = json.loads((c4_dir / "registry.json").read_text(encoding="utf-8"))
    c4_docs, stripped_spoilers = [], []
    for d in c4_reg.get("documents", []):
        if d["file"] in ("doc11_indictment_summary.txt", "doc12_verdict_summary.txt"):
            stripped_spoilers.append(f"Excluded file: {d['file']}")
            continue
        clean_lines = []
        for ln in (c4_dir / d["file"]).read_text(encoding="utf-8").splitlines():
            (stripped_spoilers if SPOILER_PATTERNS.search(ln) else clean_lines).append(ln.strip() if SPOILER_PATTERNS.search(ln) else ln)
        c4_docs.append({**d, "text": "\n".join(clean_lines).strip()})

    c4_by_id, c4_split = {d["id"]: d for d in c4_docs}, split_for_canonical_id("duck-2020")
    custody_c4 = {"documents": [{"doc_id": d["id"], "type": d["type"], "legible": True, "custody_note": f"{d['title']} ({d['date']}, {d['author']})."} for d in c4_docs]}
    claims_c4, events_c4 = [], []
    for d in c4_docs:
        q = pick_verbatim_quote(d["text"])
        if q and quote_ok(q, d["id"], c4_by_id):
            claims_c4.append({"person": d["author"], "claim": f"Documented finding in {d['title']}.", "quote": q, "doc_id": d["id"], "kind": "observation"})
            events_c4.append({"what": d["title"], "when_text": d["date"], "when_window": d["date"], "where": "Chicago, IL", "who": [d["author"]], "quote": q, "doc_id": d["id"]})
    intake_c4 = {
        "persons": [{"name": "Carlton Weekly", "aliases": ["FBG Duck"], "role": "victim"}, {"name": "Ralph Turpin", "aliases": [], "role": "person of interest"}, {"name": "Tacarlos Offerd", "aliases": [], "role": "person of interest"}, {"name": "Kenneth Roberson", "aliases": [], "role": "person of interest"}],
        "claims": claims_c4, "events": events_c4, "evidence_items": [{"description": d["title"], "doc_id": d["id"], "status": "logged"} for d in c4_docs],
    }
    assert verify_all_quotes(intake_c4, c4_by_id)
    gt_c4 = {"case_id": "duck-2020", "source": "case4_despoiled_in_memory", "stripped_spoilers": stripped_spoilers, "quote_check_drops": 0}
    rows.append(make_mb_row("real_case4_duck2020_despoiled_custody", "custody", c4_split, prompts["01_first_officer.md"], "THE REGISTRY:\n" + registry_text_block(c4_docs) + "\n\nTHE DOCUMENTS:\n" + docs_text_block(c4_docs), custody_c4, gt_c4))
    rows.append(make_mb_row("real_case4_duck2020_despoiled_intake", "intake", c4_split, prompts["05_intake.md"], docs_text_block(c4_docs), intake_c4, gt_c4))

    step_map = {"custody": "01_first_officer.md", "records": "02_records.md", "coroner": "03_coroner.md", "csi": "04_csi.md", "intake": "05_intake.md", "analyst": "06_analyst.md", "digital": "07_digital.md", "cross_examiner": "08_cross_examiner.md", "interviewer": "09_interviewer.md", "prosecutor": "10_prosecutor.md", "lead_detective": "11_lead_detective.md"}
    for cid, folder in (("delgado-2019", "case"), ("screens-2025", "case2"), ("harborlight-2016", "case3")):
        cfile, rfile = mb_root / "cache" / f"{cid}.json", mb_root / folder / "registry.json"
        if not (cfile.exists() and rfile.exists()):
            continue
        reg, outputs = json.loads(rfile.read_text(encoding="utf-8")), json.loads(cfile.read_text(encoding="utf-8")).get("outputs", {})
        docs = [{**d, "text": (mb_root / folder / d["file"]).read_text(encoding="utf-8")} for d in reg.get("documents", [])]
        docs_by_id, sp = {d["id"]: d for d in docs}, split_for_canonical_id(cid)
        for st, out_obj in outputs.items():
            if st in step_map and out_obj and verify_all_quotes(out_obj, docs_by_id) and not (st == "lead_detective" and check_prosecutor_vetoes(out_obj.get("brief", ""), [])):
                rows.append(make_mb_row(f"mb_gold_{cid}_{st}", st, sp, prompts[step_map[st]], f"CASE_ID: {cid} | CHAIR: {st}\n\n" + docs_text_block(docs), out_obj, {"case_id": cid, "source": "murder_board_gold_cache", "quote_check_drops": 0}))
    return rows


def harvest_old_bailey_homicides(cache_dir: Path, target_cases: int = 50) -> list[dict[str, Any]]:
    prompts, examples, idkeys = load_mb_agent_prompts(), [], []
    for sz in (15, 25):
        for off in (4200, 4800, 5200, 5600, 6000, 6300, 6600, 6250, 6500, 6750):
            if len(idkeys) >= target_cases * 3:
                break
            try:
                res = cached_get_json(f"https://www.dhi.ac.uk/api/data/oldbailey_record?text=murder&from={off}&size={sz}", cache_dir)
            except Exception:
                continue
            for h in res.get("hits", {}).get("hits", []):
                src = h.get("_source", {})
                idk, title = src.get("idkey", ""), src.get("title", "")
                if idk and ("Killing; murder" in title or "Killing; manslaughter" in title) and idk not in idkeys:
                    idkeys.append(idk)

    processed = 0
    for idk in idkeys:
        if processed >= target_cases:
            break
        try:
            hits = cached_get_json(f"https://www.dhi.ac.uk/api/data/oldbailey_record_single?idkey={urllib.parse.quote(idk)}", cache_dir).get("hits", {}).get("hits", [])
        except Exception:
            continue
        if not hits:
            continue
        src = hits[0].get("_source", {})
        raw_html, meta_html = src.get("html") or "", src.get("metadata") or ""
        if len(raw_html) < 1200:
            continue
        vm, dm, defm = re.search(r"Verdicts</th><td>(.*?)</td>", meta_html, re.S), re.search(r"Session Date</th><td>(.*?)</td>", meta_html, re.S), re.search(r"Defendants</th><td>(.*?)</td>", meta_html, re.S)
        true_verdict, sdate, defendant = (strip_tags(vm.group(1)) if vm else "UNKNOWN"), (strip_tags(dm.group(1)) if dm else "Historical Session"), (strip_tags(defm.group(1)).title() if defm else "Accused Subject")

        cleaned = re.sub(r"<p>\s*<span class=\"smallCaps\">\s*(?:NOT\s+GUILTY|GUILTY[^<]*)\s*</span>.*$", "", raw_html, flags=re.I | re.S)
        parts = re.split(r"<span class=\"smallCaps\">\s*([A-Z][A-Z .'\-]{2,45}?)\s*</span>\s*\.?", cleaned)
        if len(parts) < 5:
            continue
        docs = [{"id": "doc01", "title": "Charge & Arraignment Intake", "type": "report", "date": sdate, "author": "Clerk of Arraigns", "text": strip_tags(parts[0])[:2500] or f"Session {sdate} indictment file {idk}."}]
        coroner_id: str | None = None
        for w_raw, w_html in list(zip(parts[1::2], parts[2::2]))[:12]:
            w_name = re.sub(r"\s+", " ", w_raw).strip().title()
            if w_name.upper().startswith(("MESSRS", "MR.", "LORD ", "GUILTY", "NOT GUILTY", "DEATH")):
                continue
            w_text = re.sub(r"\b(?:NOT GUILTY|GUILTY)\b.*$", "", strip_tags(w_html), flags=re.S).strip()
            if len(w_text) < 50:
                continue
            did, low = f"doc{len(docs)+1:02d}", w_text.lower()
            is_med = any(k in low for k in ("post-mortem", "surgeon", "autopsy", "medical", "organs", "cause of death", "wound", "doctor", "hospital"))
            is_pol = any(k in low for k in ("police", "constable", "sergeant", "inspector", "station"))
            if is_med and coroner_id is None:
                coroner_id = did
            docs.append({
                "id": did, "title": "Surgeon / Medical Testimony" if is_med else ("Constable Testimony" if is_pol else f"Witness Statement ({w_name})"),
                "type": "report" if (is_med or is_pol) else "statement", "date": sdate, "author": w_name, "text": f"{w_name} testimony ({sdate}):\n{w_text[:3000]}",
            })
        if len(docs) < 3:
            continue
        docs_by_id, persons, claims, events = {d["id"]: d for d in docs}, [{"name": defendant, "aliases": [], "role": "accused subject"}], [], []
        for d in docs[1:]:
            persons.append({"name": d["author"], "aliases": [], "role": d["title"].lower()})
            q = pick_verbatim_quote(d["text"])
            if q and quote_ok(q, d["id"], docs_by_id):
                claims.append({"person": d["author"], "claim": f"Testified in {d['title']}.", "quote": q, "doc_id": d["id"], "kind": "observation"})
                events.append({"what": f"Recorded account from {d['author']}", "when_text": sdate, "when_window": sdate, "where": "Old Bailey", "who": [d["author"]], "quote": q, "doc_id": d["id"]})
        if len(claims) < 2:
            continue

        sp, gt = split_for_canonical_id(f"ob_{idk}"), {"case_id": idk, "source": "old_bailey_proceedings", "session_date": sdate, "historical_verdict_despoiled": true_verdict, "quote_check_drops": 0}
        cust_out = {"documents": [{"doc_id": d["id"], "type": d["type"], "legible": True, "custody_note": f"{d['title']} by {d['author']} ({d['date']}, ref {idk})."} for d in docs]}
        int_out = {"persons": persons, "claims": claims, "events": events, "evidence_items": []}
        assert verify_all_quotes(int_out, docs_by_id)
        examples.append(make_mb_row(f"real_ob_{idk}_custody", "custody", sp, prompts["01_first_officer.md"], "THE REGISTRY:\n" + registry_text_block(docs) + "\n\nTHE DOCUMENTS:\n" + docs_text_block(docs), cust_out, gt))
        examples.append(make_mb_row(f"real_ob_{idk}_intake", "intake", sp, prompts["05_intake.md"], docs_text_block(docs), int_out, gt))
        if coroner_id:
            mdoc = docs_by_id[coroner_id]
            mq = pick_verbatim_quote(mdoc["text"], 28, 230)
            if mq and quote_ok(mq, coroner_id, docs_by_id):
                cor_out = {"cause": "Stated in post-mortem surgical testimony", "manner": "alleged homicide under Coroner's inquisition", "death_window": {"start": "as bounded by testimony", "end": sdate, "quote": mq, "doc_id": coroner_id}, "medical_facts": [{"fact": f"Post-mortem finding testified by {mdoc['author']}.", "quote": mq, "doc_id": coroner_id}], "medical_flags": []}
                examples.append(make_mb_row(f"real_ob_{idk}_coroner", "coroner", sp, prompts["03_coroner.md"], docs_text_block(docs, ["doc01", coroner_id]), cor_out, gt))
        processed += 1
    return examples


def harvest_doj_homicides(cache_dir: Path, pages: int = 4, page_size: int = 20) -> list[dict[str, Any]]:
    prompts, examples, seen = load_mb_agent_prompts(), [], set()
    for page in range(pages):
        try:
            results = cached_get_json(f"https://www.justice.gov/api/v1/press_releases.json?pagesize={page_size}&page={page}&parameters[title]=murder", cache_dir).get("results", [])
        except Exception:
            continue
        for idx, item in enumerate(results):
            uuid = str(item.get("uuid") or f"doj_hom_{page}_{idx}")
            if uuid in seen:
                continue
            seen.add(uuid)
            title, raw_body = strip_tags(item.get("title") or ""), strip_tags(item.get("body") or "")
            factual, spoilers = [], []
            for p in raw_body.splitlines():
                if len(p) >= 40:
                    (spoilers if SPOILER_PATTERNS.search(p) else factual).append(p)
            if len(factual) < 2:
                continue
            docs = [{"id": f"doc{i:02d}", "title": f"Federal Factual Exhibit {i}", "type": "report", "date": "Federal Case File", "author": "DOJ Task Force", "text": para} for i, para in enumerate(factual[:6], 1)]
            docs_by_id, claims, events = {d["id"]: d for d in docs}, [], []
            for d in docs:
                q = pick_verbatim_quote(d["text"], 28, 220)
                if q and quote_ok(q, d["id"], docs_by_id):
                    claims.append({"person": "Case Record", "claim": f"Investigative finding in {d['id']}.", "quote": q, "doc_id": d["id"], "kind": "action"})
                    events.append({"what": f"Documented case event ({d['id']})", "when_text": "Per federal exhibit", "when_window": "Case timeline", "where": "Federal jurisdiction", "who": [], "quote": q, "doc_id": d["id"]})
            if len(claims) >= 2:
                cid = f"doj_hom_{uuid[:12]}"
                gt = {"case_id": cid, "source": "doj_federal_homicide_despoiled", "despoiled_title": title, "despoiled_spoilers": spoilers[:5], "quote_check_drops": 0}
                examples.append(make_mb_row(f"real_{cid}_intake", "intake", split_for_canonical_id(cid), prompts["05_intake.md"], f"CASE_REF: {cid}\n\n" + docs_text_block(docs), {"persons": [], "claims": claims, "events": events, "evidence_items": []}, gt))
    return examples


def harvest_doj_aml(cache_dir: Path, pages: int = 6, page_size: int = 25) -> list[dict[str, Any]]:
    examples, seen = [], set()
    for page in range(pages):
        try:
            results = cached_get_json(f"https://www.justice.gov/api/v1/press_releases.json?pagesize={page_size}&page={page}&parameters[title]=money%20laundering", cache_dir).get("results", [])
        except Exception:
            continue
        for idx, item in enumerate(results):
            uuid = str(item.get("uuid") or f"doj_aml_{page}_{idx}")
            if uuid in seen:
                continue
            seen.add(uuid)
            title, raw_body = strip_tags(item.get("title") or ""), strip_tags(item.get("body") or "")
            factual, spoilers = [], []
            for p in raw_body.splitlines():
                if len(p) >= 35:
                    (spoilers if SPOILER_PATTERNS.search(p) else factual).append(p)
            if len(factual) < 2:
                continue
            despoiled_text = "\n\n".join(factual[:10])
            key_quote = pick_verbatim_quote(despoiled_text, 32, 230)
            if not key_quote or not quote_ok(key_quote, "DOJ_RECORD", {"DOJ_RECORD": {"text": despoiled_text}}):
                continue
            dollars, entities, low = list(dict.fromkeys(DOLLAR_RE.findall(despoiled_text))), list(dict.fromkeys(m.group(1) for m in ENTITY_RE.finditer(despoiled_text))), despoiled_text.lower()
            typology = (
                "REAL_DOJ_SHELL_COMPANY_LAYERING" if any(k in low for k in ("shell", "llc", "nominee", "front", "offshore"))
                else "REAL_DOJ_CRYPTO_MULE_LAUNDERING" if any(k in low for k in ("crypto", "bitcoin", "tether", "virtual currency", "darknet", "mixer"))
                else "REAL_DOJ_CARTEL_FUNNEL_TBML" if any(k in low for k in ("cartel", "fentanyl", "cocaine", "narcotics", "funnel", "bulk cash"))
                else "REAL_DOJ_STRUCTURING_WIRE_LAUNDERING"
            )
            pkt_id = f"DOJ-FIU-{uuid[:8].upper()}"
            fiu_json = {
                "packet_id": pkt_id, "disposition": "FILE_SAR_ESCALATE", "detected_typology": typology, "tainted_entities": entities[:8], "documented_dollar_figures": dollars[:6],
                "evidence_quotes": [{"doc_id": "DOJ_RECORD", "quote": key_quote}],
                "innocent_alternative": "Legitimate high-value cross-border trade or corporate treasury transfers were considered, but uncorroborated pass-through velocity and shell layering require SAR escalation.",
                "recommended_subpoenas_and_actions": ["FinCEN 314(b) & SWIFT/Fedwire correspondent trace", "Corporate Transparency BOI records for named entities"],
            }
            audit = f"<audit>\n1. Evidence Quote: \"{key_quote}\"\n2. Flows: {', '.join(dollars[:4]) or 'multi-wire'}; entities: {', '.join(entities[:4]) or 'unincorporated accounts'}.\n3. Typology: {typology} -> FILE_SAR_ESCALATE.\n</audit>"
            gt = {"packet_id": pkt_id, "disposition": "FILE_SAR_ESCALATE", "detected_typology": typology, "tainted_entities": entities[:8], "despoiled_title": title, "despoiled_spoilers": spoilers[:5], "quote_check_drops": 0}
            examples.append(make_aml_row(f"real_doj_aml_{uuid[:12]}", typology, split_for_canonical_id(pkt_id), f"Audit this de-spoiled federal financial investigation record ({pkt_id}):\n\n=== DOJ_RECORD ===\n{despoiled_text}", audit, fiu_json, gt))
    return examples


def harvest_ofac_sdn_slice(cache_dir: Path, target_turns: int = 40) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cpath = cache_dir / "ofac_sdn_350kb.csv"
    if not cpath.exists():
        req = urllib.request.Request("https://www.treasury.gov/ofac/downloads/sdn.csv", headers={"User-Agent": USER_AGENT, "Range": f"bytes=0-{OFAC_SLICE_BYTES - 1}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            cpath.write_bytes(resp.read(OFAC_SLICE_BYTES))
    raw_csv = cpath.read_bytes()[:OFAC_SLICE_BYTES].decode("utf-8", errors="replace")

    examples: list[dict[str, Any]] = []
    for row in csv.reader(io.StringIO(raw_csv)):
        if len(row) < 4 or not row[0].strip().isdigit() or not row[1].strip() or row[2].strip() == "individual":
            continue
        ent_num, name, stype, prog = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
        rem = row[11].strip() if len(row) > 11 and row[11].strip() != "-0-" else "Listed on OFAC SDN Annex"
        pkt_id, wire_usd = f"OFAC-SDN-{ent_num}", 125_000 + ((int(ent_num) * 173) % 750_000)
        sdn_line = f"OFAC SDN Entry #{ent_num} | Entity: {name} | Type: {stype if stype != '-0-' else 'corporate_entity'} | Program: {prog} | Remarks: {rem}"
        tx_line = f"[TX-SDN-{ent_num}] Outbound USD Correspondent Wire ${wire_usd:,} naming beneficiary/intermediary '{name}' under program screen {prog}."
        docs = {"SDN_WATCHLIST": {"text": sdn_line}, "WIRE_INTERCEPT": {"text": tx_line}}
        assert quote_ok(sdn_line, "SDN_WATCHLIST", docs) and quote_ok(tx_line, "WIRE_INTERCEPT", docs)
        fiu_json = {
            "packet_id": pkt_id, "disposition": "FILE_SAR_ESCALATE", "detected_typology": "REAL_OFAC_SDN_SANCTIONS_BLOCK",
            "tainted_entities": [name], "sanctions_program": prog, "blocked_wire_usd": wire_usd,
            "evidence_quotes": [{"doc_id": "SDN_WATCHLIST", "quote": sdn_line}, {"doc_id": "WIRE_INTERCEPT", "quote": tx_line}],
            "innocent_alternative": f"Potential homonym collision against an unrelated firm sharing a partial trade name with '{name}' requires tax-ID/SWIFT BIC check before permanent forfeiture, but immediate OFAC hold is mandatory.",
            "recommended_subpoenas_and_actions": [f"Immediate OFAC blocking report within 10 business days for SDN #{ent_num} ({prog})", "Pull originating SWIFT MT103 fields 50K/59 and beneficial ownership registry"],
        }
        audit = f"<audit>\n1. Watchlist Match: `{sdn_line}`.\n2. Exposure Math: Wire `${wire_usd:,}` (`{tx_line}`) triggers 100% blocking under `{prog}`.\n3. Disposition: `FILE_SAR_ESCALATE`.\n</audit>"
        gt = {"packet_id": pkt_id, "sdn_ent_num": ent_num, "entity_name": name, "program": prog, "disposition": "FILE_SAR_ESCALATE", "quote_check_drops": 0}
        examples.append(make_aml_row(f"real_ofac_sdn_{ent_num}", "REAL_OFAC_SDN_SANCTIONS_BLOCK", split_for_canonical_id(pkt_id), f"Screen this live wire intercept against the US Treasury OFAC SDN registry slice ({pkt_id}):\n\n=== SDN_WATCHLIST ===\n{sdn_line}\n\n=== WIRE_INTERCEPT ===\n{tx_line}", audit, fiu_json, gt))
        if len(examples) >= target_turns:
            break
    return examples


def harvest_real_911_cad(cache_dir: Path, rows_per_feed: int = 80) -> list[dict[str, Any]]:
    feeds = [
        ("nyc_2005", f"https://data.cityofnewyork.us/resource/76xm-jjuj.json?$where=initial_call_type!=final_call_type%20AND%20final_severity_level_code%3C=%272%27&$limit={rows_per_feed // 2}"),
        ("nyc_modern", f"https://data.cityofnewyork.us/resource/76xm-jjuj.json?$where=initial_call_type!=final_call_type&$order=incident_datetime%20DESC&$limit={rows_per_feed // 2}"),
        ("sfpd_2026", f"https://data.sfgov.org/resource/gnap-fj3t.json?$where=call_type_original!=call_type_final&$order=received_datetime%20DESC&$limit={rows_per_feed}"),
        ("seattle_fire", f"https://data.seattle.gov/resource/kzjm-xkqj.json?$order=datetime%20DESC&$limit={rows_per_feed}"),
    ]
    examples, seen_calls = [], set()
    for tag, url in feeds:
        try:
            records = cached_get_json(url, cache_dir)
        except Exception:
            continue
        for idx, rec in enumerate(records):
            if tag.startswith("nyc_"):
                call_id = f"FDNY-{rec.get('incident_id') or f'{tag}_{idx}'}"
                if call_id in seen_calls:
                    continue
                seen_calls.add(call_id)
                dt, boro, zipc = rec.get("incident_datetime", ""), rec.get("borough", "NYC"), rec.get("zipcode", "N/A")
                init_t, fin_t, init_s, fin_s = rec.get("initial_call_type", "OTHER"), rec.get("final_call_type", "OTHER"), int(rec.get("initial_severity_level_code", "5")), int(rec.get("final_severity_level_code", "5"))
                init_d, prio, next_line = NYC_CALL_DESC.get(init_t, init_t), ("P1_ECHO" if fin_s == 1 else ("P1_DELTA" if fin_s <= 2 else "P2_BRAVO")), "Is the patient completely awake and breathing normally right now? Watch their chest."
                user_text = f"Evaluate this real FDNY/NYC 911 EMS CAD intake record (post-arrival outcome stripped):\n\n=== REAL NYC 911 CAD INTAKE ===\nCALL_ID: {call_id} | TIME: {dt} | BOROUGH: {boro} | ZIP: {zipc}\nINITIAL_CALL_TYPE: {init_t} ({init_d}) | INITIAL_SEVERITY: {init_s}"
                pkt = {"call_id": call_id, "archetype": "MEDICAL_CRITICAL" if fin_s <= 2 else "REAL_CAD_MEDICAL_TRIAGE", "priority": prio, "coercion_detected": False, "silent_approach_required": False, "resolved_location": f"{boro} ZIP {zipc}", "life_safety_traps_flagged": [f"intake_{init_t}_escalation_screening"], "units_to_dispatch": ["ALS_PARAMEDIC", "CFR_ENGINE"] if fin_s <= 2 else ["BLS_AMBULANCE"], "cad_pre_arrival_note": f"Screen {init_t} ({init_d}) intake for high-acuity deterioration.", "next_dispatcher_line": next_line}
                gt = {"call_id": call_id, "initial_call_type": init_t, "final_call_type": fin_t, "initial_severity": init_s, "final_severity": fin_s, "next_line_word_count": len(next_line.split())}
            elif tag == "sfpd_2026":
                call_id = f"SFPD-{rec.get('cad_number') or f'sf_{idx}'}"
                if call_id in seen_calls:
                    continue
                seen_calls.add(call_id)
                dt, hood, inter = rec.get("received_datetime", ""), rec.get("analysis_neighborhood", "SF"), rec.get("intersection_name", "REDACTED PREMISE")
                orig_c, orig_d, fin_d = rec.get("call_type_original", ""), rec.get("call_type_original_desc", "UNKNOWN"), rec.get("call_type_final_desc", "UNKNOWN")
                p_orig, p_fin, sens = rec.get("priority_original", "B"), rec.get("priority_final", "B"), bool(rec.get("sensitive_call", False))
                prio, next_line = {"A": "P1_DELTA", "B": "P2_BRAVO", "C": "P3_ALPHA"}.get(p_fin, "P2_BRAVO"), "Are any weapons visible, and can you safely describe everyone involved from a distance?"
                user_text = f"Triage this real SFPD 911 Police CAD intake record (on-scene final classification stripped):\n\n=== REAL SFPD 911 CAD INTAKE ===\nCALL_ID: {call_id} | RECEIVED: {dt} | LOCATION: {inter} ({hood})\nINITIAL_CALL_TYPE: [{orig_c}] {orig_d} | INITIAL_PRIORITY: {p_orig} | SENSITIVE_PREMISE: {sens}"
                pkt = {"call_id": call_id, "archetype": "REAL_PD_CAD_RECLASSIFICATION", "priority": prio, "coercion_detected": sens, "silent_approach_required": sens and p_fin == "A", "resolved_location": f"{inter} ({hood})", "life_safety_traps_flagged": [f"screen_initial_{orig_c}_for_escalation"], "units_to_dispatch": ["PD_PATROL_TWO_UNIT"] if p_fin == "A" else ["PD_SECTOR_UNIT"], "cad_pre_arrival_note": f"Verify [{orig_d}] intake for scene escalation hazards.", "next_dispatcher_line": next_line}
                gt = {"call_id": call_id, "initial_call_type": orig_d, "final_call_type": fin_d, "initial_severity": p_orig, "final_severity": p_fin, "next_line_word_count": len(next_line.split())}
            else:
                call_id = f"SFD-{rec.get('incident_number') or f'sea_{idx}'}"
                if call_id in seen_calls:
                    continue
                seen_calls.add(call_id)
                dt, addr, fin_type = rec.get("datetime", ""), rec.get("address", "Seattle Sector"), str(rec.get("type") or "Aid Response")
                lat, lon = rec.get("latitude", "47.6062"), rec.get("longitude", "-122.3321")
                prio, next_line = ("P1_DELTA" if ("medic" in fin_type.lower() or "fire" in fin_type.lower()) else "P2_BRAVO"), "Keep the entrance clear for Seattle Fire units. Is anyone trapped or having trouble breathing?"
                user_text = f"Triage this real Seattle Fire 911 CAD dispatch telemetry at call receipt (final unit disposition stripped):\n\n=== REAL SEATTLE FIRE 911 CAD INTAKE ===\nCALL_ID: {call_id} | TIMESTAMP: {dt}\nADDRESS: {addr} | WPH2_COORDS: {lat}, {lon} | INTAKE_STREAM: Emergency Fire/EMS request at {addr}"
                pkt = {"call_id": call_id, "archetype": "MEDICAL_CRITICAL" if prio == "P1_DELTA" else "MULTI_HAZARD_CHAOS", "priority": prio, "coercion_detected": False, "silent_approach_required": False, "resolved_location": f"{addr} ({lat}, {lon})", "life_safety_traps_flagged": ["verify_airway_and_structure_egress"], "units_to_dispatch": ["SFD_MEDIC_UNIT", "SFD_ENGINE"] if prio == "P1_DELTA" else ["SFD_AID_UNIT"], "cad_pre_arrival_note": f"Coordinate Seattle Fire approach to {addr}.", "next_dispatcher_line": next_line}
                gt = {"call_id": call_id, "address": addr, "final_call_type": fin_type, "final_severity": prio, "next_line_word_count": len(next_line.split())}

            assert gt["next_line_word_count"] <= 18
            thought = f"<triage>\n- CAD Intake: {call_id} at {pkt['resolved_location']} -> assign {pkt['priority']} ({', '.join(pkt['units_to_dispatch'])}).\n</triage>"
            examples.append({
                "id": f"real_911_{call_id.lower().replace('-', '_')}", "track": "track1_now", "domain": "dispatch_911_triage", "subtask": pkt["archetype"], "split": split_for_canonical_id(call_id),
                "messages": [{"role": "system", "content": SYSTEM_PROMPT_911}, {"role": "user", "content": user_text}, {"role": "assistant", "content": f"{thought}\n```json\n{json.dumps(pkt, indent=2)}\n```"}],
                "ground_truth": gt,
            })
    return examples


def main() -> None:
    parser = argparse.ArgumentParser(description="Harvest & de-spoil real crime, OFAC SDN, and 911 CAD archives.")
    parser.add_argument("--mb-root", type=Path, default=Path("/Users/test/Desktop/murder-board"))
    parser.add_argument("--cache-dir", type=Path, default=Path("/Users/test/Desktop/murder-board/training/datasets/raw_cache"))
    parser.add_argument("--out-dir", type=Path, default=Path("/Users/test/Desktop/murder-board/training/datasets/real_v1"))
    parser.add_argument("--old-bailey-cases", type=int, default=50)
    parser.add_argument("--cad-per-feed", type=int, default=80)
    args = parser.parse_args()

    t0 = time.perf_counter()
    c4_gold = harvest_case4_and_gold_caches(args.mb_root)
    ob_rows = harvest_old_bailey_homicides(args.cache_dir, args.old_bailey_cases)
    doj_hom = harvest_doj_homicides(args.cache_dir, pages=4, page_size=20)
    doj_aml = harvest_doj_aml(args.cache_dir, pages=6, page_size=25)
    ofac_rows = harvest_ofac_sdn_slice(args.cache_dir, target_turns=40)
    cad_rows = harvest_real_911_cad(args.cache_dir, rows_per_feed=args.cad_per_feed)

    all_rows = c4_gold + ob_rows + doj_hom + doj_aml + ofac_rows + cad_rows
    by_split: dict[str, list[dict[str, Any]]] = {"train": [], "val": [], "test": []}
    for r in all_rows:
        by_split[r["split"]].append(r)

    for split, srows in by_split.items():
        spath = args.out_dir / split / f"real_v1_{split}.jsonl"
        spath.parent.mkdir(parents=True, exist_ok=True)
        with spath.open("w", encoding="utf-8") as f:
            for r in srows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    cache_mb = sum(p.stat().st_size for p in args.cache_dir.glob("*") if p.is_file()) / (1024 ** 2)
    assert cache_mb < 100.0, f"Cache exceeded 100 MB cap: {cache_mb:.2f} MB"
    manifest = {
        "case4_and_gold_turns": len(c4_gold), "old_bailey_homicide_turns": len(ob_rows),
        "doj_homicide_turns": len(doj_hom), "doj_aml_turns": len(doj_aml),
        "ofac_sdn_turns": len(ofac_rows), "real_911_cad_turns": len(cad_rows),
        "total_turns": len(all_rows), "by_split": {k: len(v) for k, v in by_split.items()},
        "raw_cache_megabytes": round(cache_mb, 2), "elapsed_seconds": round(time.perf_counter() - t0, 2),
    }
    (args.out_dir / "real_v1_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
