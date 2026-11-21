// Murder Board: runner, validation, and screens.
// The runner is the product's spine: agents propose, code disposes.
// Every finding that carries a quote is checked against its document
// in this file, not trusted from the model. Lead scores are
// recomputed from the rubric. Screens render only from the book.
(function () {
"use strict";

var G = typeof window !== "undefined" ? window : globalThis;
var DOCS = G.CASE_DOCS || [];
var PROMPTS = {};
(G.AGENT_PROMPTS || []).forEach(function (a) { PROMPTS[a.file] = a.prompt; });
var DOC_BY_ID = {};
DOCS.forEach(function (d) { DOC_BY_ID[d.id] = d; });

// Cases: the file can be a police file or a feed of public posts.
// setCase swaps the document set the whole squad works from.
var CASES = G.CASES || [{ case_id: "delgado-2019", case_title: "", documents: DOCS }];
var CURRENT_CASE = CASES[0].case_id;
function setCase(caseId) {
  for (var i = 0; i < CASES.length; i++) {
    if (CASES[i].case_id === caseId) {
      CURRENT_CASE = caseId;
      DOCS = CASES[i].documents;
      DOC_BY_ID = {};
      DOCS.forEach(function (d) { DOC_BY_ID[d.id] = d; });
      return true;
    }
  }
  return false;
}

function cfg() { return G.MB_CONFIG || { reasoningModel: "gemini-4-argon", fastModel: "gemini-4-carbon", worldModel: "gemini-4-hydrogen", fieldModel: "gemini-4-neon", apiKey: "" }; }
function modelNameFor(step) {
  var c = cfg();
  return step.model === "reasoning" ? c.reasoningModel
    : step.model === "world" ? (c.worldModel || c.fastModel)
    : step.model === "field" ? (c.fieldModel || c.fastModel)
    : c.fastModel;
}

// ---------- transport ----------
async function callGemini(model, systemText, userText) {
  if (typeof G.__MB_TRANSPORT === "function") {
    return G.__MB_TRANSPORT(model, systemText, userText);
  }
  var res = await fetch("https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent", {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-goog-api-key": cfg().apiKey },
    body: JSON.stringify({
      systemInstruction: { parts: [{ text: systemText }] },
      contents: [{ parts: [{ text: userText }] }],
      generationConfig: { responseMimeType: "application/json", temperature: 0.2, maxOutputTokens: 16384 }
    })
  });
  if (!res.ok) throw new Error("Gemini HTTP " + res.status);
  var data = await res.json();
  var parts = (data.candidates && data.candidates[0] && data.candidates[0].content.parts) || [];
  return parts.map(function (p) { return p.text || ""; }).join("");
}

// ---------- validation: the quote check is code ----------
function norm(s) { return String(s || "").toLowerCase().replace(/\s+/g, " ").trim(); }
function quoteOk(quote, docId) {
  var doc = DOC_BY_ID[docId];
  if (!doc || !quote || norm(quote).length < 8) return false;
  return norm(doc.text).indexOf(norm(quote)) !== -1;
}
function docKnown(id) { return Object.prototype.hasOwnProperty.call(DOC_BY_ID, id); }

// Each validator returns the output with bad findings removed and
// counts the drops. A finding whose quote is not in its document
// never reaches the book.
var VALIDATORS = {
  custody: function (o, drop) {
    o.documents = (o.documents || []).filter(function (d) {
      if (!docKnown(d.doc_id)) { drop.n++; return false; } return true;
    });
    return o;
  },
  records: function (o) { return o; },
  coroner: function (o, drop) {
    if (o.death_window && o.death_window.quote && !quoteOk(o.death_window.quote, o.death_window.doc_id)) {
      drop.n++; o.death_window.quote = "";
    }
    o.medical_facts = (o.medical_facts || []).filter(function (f) {
      if (!quoteOk(f.quote, f.doc_id)) { drop.n++; return false; } return true;
    });
    o.medical_flags = (o.medical_flags || []).filter(function (f) {
      if (!quoteOk(f.claim_quote, f.claim_doc) || !quoteOk(f.finding_quote, f.finding_doc)) { drop.n++; return false; } return true;
    });
    return o;
  },
  csi: function (o, drop) {
    o.ledger = (o.ledger || []).filter(function (it) {
      if (it.quote && !quoteOk(it.quote, it.doc_id)) { drop.n++; return false; } return true;
    });
    o.gaps = (o.gaps || []).filter(function (g) {
      if (g.quote && !quoteOk(g.quote, g.doc_id)) { drop.n++; return false; } return true;
    });
    return o;
  },
  intake: function (o, drop) {
    o.claims = (o.claims || []).filter(function (c) {
      if (!quoteOk(c.quote, c.doc_id)) { drop.n++; return false; } return true;
    });
    o.events = (o.events || []).filter(function (e) {
      if (!quoteOk(e.quote, e.doc_id)) { drop.n++; return false; } return true;
    });
    return o;
  },
  analyst: function (o, drop) {
    o.collisions = (o.collisions || []).filter(function (c) {
      var ok = (c.quotes || []).every(function (q) { return quoteOk(q.quote, q.doc_id); });
      if (!ok) { drop.n++; return false; } return true;
    });
    return o;
  },
  digital: function (o, drop) {
    ["machine_events", "record_checks", "camera_gaps"].forEach(function (k) {
      o[k] = (o[k] || []).filter(function (it) {
        if (!quoteOk(it.quote, it.doc_id)) { drop.n++; return false; } return true;
      });
    });
    return o;
  },
  cross_examiner: function (o, drop) {
    o.contradictions = (o.contradictions || []).filter(function (c) {
      if (!quoteOk(c.a_quote, c.a_doc) || !quoteOk(c.b_quote, c.b_doc)) { drop.n++; return false; } return true;
    });
    (o.alibis || []).forEach(function (a) {
      a.reasons = (a.reasons || []).filter(function (r) {
        if (!quoteOk(r.quote, r.doc_id)) { drop.n++; return false; } return true;
      });
    });
    return o;
  },
  interviewer: function (o, drop) {
    (o.histories || []).forEach(function (h) {
      h.changes = (h.changes || []).filter(function (c) {
        if (!quoteOk(c.earlier_quote, c.earlier_doc) || !quoteOk(c.later_quote, c.later_doc)) { drop.n++; return false; } return true;
      });
    });
    o.next_questions = (o.next_questions || []).filter(function (q) {
      if (!quoteOk(q.anchored_quote, q.doc_id)) { drop.n++; return false; } return true;
    });
    return o;
  },
  prosecutor: function (o) { return o; },
  lead_detective: function (o, drop, log) {
    (o.leads || []).forEach(function (l) {
      var recomputed = recomputeScore(l.components || {});
      if (typeof l.score === "number" && l.score !== recomputed) {
        log.push("Lead score corrected by runner: model said " + l.score + ", rubric says " + recomputed + " (" + l.action + ")");
      }
      l.score = recomputed;
    });
    o.leads = (o.leads || []).sort(function (a, b) { return b.score - a.score; });
    return o;
  }
};

// ---------- the rubric, in code ----------
function recomputeScore(c) {
  return (c.cites_high_contradiction ? 40 : 0)
       + (c.in_window ? 25 : 0)
       + (c.closes_gap ? 20 : 0)
       + (c.still_reachable ? 15 : 0);
}

// ---------- the book ----------
function newBook() {
  return {
    documents: DOCS, custody: null, records: null, coroner: null, door2: null,
    ledger: [], csi_gaps: [], persons: [], claims: [], intake_events: [],
    evidence_items: [], timeline: [], collisions: [], machine: null,
    contradictions: [], alibis: [], ce_gaps: [], histories: [],
    next_questions: [], sufficiency: [], vetoes: [], corroboration_needed: [],
    leads: [], gaps: [], brief: "",
    dropped: 0, log: [], outputs: {}, failed_steps: [], squad_notes: []
  };
}

// Records simulation: the Door 2 census, run against bundled
// fixtures for the fictional cases. Deterministic, no model call,
// no outside lookup. Quotes are checked against the fixture text
// itself, the same law as the case file: no quote, no item.
var FIXTURES = G.RECORDS_FIXTURES || [];
var LIVE_FIXTURE = null;
function setLiveFixture(fx) { LIVE_FIXTURE = fx; }
function normName(s) { return String(s || "").toLowerCase().replace(/\s+/g, " ").trim(); }
function findFixture(name) {
  var n = normName(name);
  if (!n) return null;
  if (LIVE_FIXTURE) {
    var ln = [LIVE_FIXTURE.subject.name].concat(LIVE_FIXTURE.subject.aliases || []);
    for (var k = 0; k < ln.length; k++) if (normName(ln[k]) === n) return LIVE_FIXTURE;
  }
  for (var i = 0; i < FIXTURES.length; i++) {
    var names = [FIXTURES[i].subject.name].concat(FIXTURES[i].subject.aliases || []);
    for (var j = 0; j < names.length; j++) if (normName(names[j]) === n) return FIXTURES[i];
  }
  return null;
}
function fixtureQuoteOk(quote, text) {
  return norm(text).indexOf(norm(quote)) !== -1;
}
function buildRecordsFromFixture(fx) {
  var items = [];
  fx.items.forEach(function (it) {
    if (!fixtureQuoteOk(it.quote, it.text)) return;
    items.push({
      item: it.title + ": " + it.quote,
      source_class: it.type + " / " + it.source_name,
      label: it.label,
      quote: it.quote,
      fixture_ref: "fixture:" + fx.case_id
    });
  });
  return {
    subject: fx.subject.name,
    starter_items: items,
    collisions: fx.collisions.map(function (c) { return { name: c.name, note: c.note }; }),
    request_next: fx.live ? ["Widen the subreddit set and pull the subject's own posts and comments by author."] : ["Live census sources are off in this simulation build."],
    notes: fx.live
      ? "LIVE census for " + fx.subject.name + ": pulled from public sources at " + (fx.pulled_at || "") + " (Reddit via the Arctic Shift archive; social posts via public search). Public posts only, desk work only, nothing contacted. Summary-sourced items are labeled UNVERIFIED."
      : "Simulation census for " + fx.subject.name + ": pulled from the bundled fixtures for this fictional case, not from live sources."
  };
}

function docsText(ids) {  return DOCS.filter(function (d) { return !ids || ids.indexOf(d.id) !== -1; })
    .map(function (d) { return "===== " + d.id + " (" + d.title + ", " + d.date + ") =====\n" + d.text; })
    .join("\n\n");
}
function registryText() {
  return JSON.stringify(DOCS.map(function (d) {
    return { id: d.id, title: d.title, type: d.type, date: d.date, author: d.author };
  }), null, 1);
}

// ---------- steps, in the SPEC4 hand-off order ----------
var CHAIRS = [
  { id: "first_officer", name: "First Officer" },
  { id: "records", name: "Records" },
  { id: "coroner", name: "Coroner" },
  { id: "csi", name: "CSI" },
  { id: "analyst", name: "Analyst" },
  { id: "digital", name: "Digital" },
  { id: "cross_examiner", name: "Cross-Examiner" },
  { id: "interviewer", name: "Interviewer" },
  { id: "prosecutor", name: "Prosecutor" },
  { id: "lead_detective", name: "Lead Detective" }
];

var STEPS = [
  { id: "custody", chair: "first_officer", file: "01_first_officer.md", model: "fast",
    required: ["documents"],
    input: function () { return "THE REGISTRY:\n" + registryText() + "\n\nTHE DOCUMENTS:\n" + docsText(); },
    apply: function (b, o) { b.custody = o; } },
  { id: "records", chair: "records", file: "02_records.md", model: "fast",
    required: ["subject", "starter_items"],
    handoff: function () { return { from: ["custody"], detail: "document registry and the First Officer's custody note" }; },
    input: function (b) { return "THE REGISTRY:\n" + registryText() + "\n\nCUSTODY NOTE:\n" + JSON.stringify(b.custody || {}, null, 1); },
    apply: function (b, o) { b.records = o; } },
  { id: "coroner", chair: "coroner", file: "03_coroner.md", model: "fast",
    required: ["cause", "manner", "death_window"],
    handoff: function () { return { from: ["custody"], detail: "medical records and the First Officer's custody note" }; },
    input: function (b) { return docsText(["doc01", "doc02"]) + "\n\nCUSTODY NOTE:\n" + JSON.stringify(b.custody || {}, null, 1); },
    apply: function (b, o) { b.coroner = o; } },
  { id: "csi", chair: "csi", file: "04_csi.md", model: "fast",
    required: ["ledger", "gaps"],
    handoff: function () { return { from: ["custody"], detail: "case documents and the First Officer's custody note" }; },
    input: function (b) { return docsText() + "\n\nCUSTODY NOTE:\n" + JSON.stringify(b.custody || {}, null, 1); },
    apply: function (b, o) { b.ledger = o.ledger || []; b.csi_gaps = o.gaps || []; } },
  { id: "intake", chair: "first_officer", file: "05_intake.md", model: "fast",
    required: ["persons", "claims", "events"],
    handoff: function () { return { from: ["custody", "coroner"], detail: "custody note and medical findings" }; },
    input: function (b) { return docsText() + "\n\nCUSTODY NOTE:\n" + JSON.stringify(b.custody || {}, null, 1) + "\n\nCORONER FINDINGS:\n" + JSON.stringify(b.coroner || {}, null, 1); },
    apply: function (b, o) {
      b.persons = o.persons || []; b.claims = o.claims || [];
      b.intake_events = o.events || []; b.evidence_items = o.evidence_items || [];
    } },
  { id: "analyst", chair: "analyst", file: "06_analyst.md", model: "world",
    required: ["events"],
    handoff: function (b) { return {
      from: ["intake", "coroner"],
      detail: (b.intake_events || []).length + " events, " + (b.claims || []).length + " quote-checked claims, and " + (b.coroner && b.coroner.death_window ? "the examiner's death window" : "no usable examiner window")
    }; },
    input: function (b) {
      return "INTAKE OUTPUT:\n" + JSON.stringify({ events: b.intake_events, claims: b.claims }, null, 1)
        + "\n\nDEATH WINDOW:\n" + JSON.stringify(b.coroner ? b.coroner.death_window : {}, null, 1);
    },
    apply: function (b, o) { b.timeline = o.events || []; b.collisions = o.collisions || []; } },
  { id: "digital", chair: "digital", file: "07_digital.md", model: "field",
    required: ["machine_events"],
    handoff: function () { return { from: ["intake"], detail: "quote-checked claims and event inventory from intake" }; },
    input: function (b) { return docsText() + "\n\nINTAKE CLAIMS AND EVENTS:\n" + JSON.stringify({ claims: b.claims, events: b.intake_events }, null, 1); },
    apply: function (b, o) { b.machine = o; } },
  { id: "cross_examiner", chair: "cross_examiner", file: "08_cross_examiner.md", model: "reasoning",
    required: ["contradictions", "alibis"],
    handoff: function (b) { return {
      from: ["intake", "coroner", "analyst", "digital"],
      detail: "intake claims, analyst timeline, digital records, and " + (b.coroner && b.coroner.death_window ? "the examiner's death window" : "no usable examiner window")
    }; },
    input: function (b) {
      return "THE DOCUMENTS:\n" + docsText()
        + "\n\nINTAKE CLAIMS:\n" + JSON.stringify(b.claims, null, 1)
        + "\n\nDIGITAL RECORDS:\n" + JSON.stringify(b.machine || {}, null, 1)
        + "\n\nANALYST TIMELINE AND COLLISIONS:\n" + JSON.stringify({ timeline: b.timeline, collisions: b.collisions }, null, 1)
        + "\n\nDEATH WINDOW:\n" + JSON.stringify(b.coroner ? b.coroner.death_window : {}, null, 1);
    },
    apply: function (b, o) {
      b.contradictions = o.contradictions || []; b.alibis = o.alibis || []; b.ce_gaps = o.evidence_gaps || [];
    } },
  { id: "interviewer", chair: "interviewer", file: "09_interviewer.md", model: "fast",
    required: ["histories", "next_questions"],
    handoff: function (b) { return {
      from: ["cross_examiner"],
      detail: (b.contradictions || []).length + " quote-checked contradiction finding(s) to compare against the statements"
    }; },
    input: function (b) {
      return "THE STATEMENTS:\n" + docsText(["doc03", "doc04", "doc05", "doc06", "doc07", "doc08", "doc09", "doc10"])
        + "\n\nCONTRADICTIONS FOUND:\n" + JSON.stringify(b.contradictions, null, 1);
    },
    apply: function (b, o) { b.histories = o.histories || []; b.next_questions = o.next_questions || []; } },
  { id: "prosecutor", chair: "prosecutor", file: "10_prosecutor.md", model: "fast",
    required: ["sufficiency", "vetoes"],
    handoff: function (b) { return {
      from: ["csi", "analyst", "digital", "cross_examiner", "interviewer"],
      detail: (b.contradictions || []).length + " contradictions, " + (b.alibis || []).length + " alibis, " + ((b.csi_gaps || []).length + (b.ce_gaps || []).length) + " evidence gaps, and " + (b.collisions || []).length + " timeline collision(s)"
    }; },
    input: function (b) {
      return "THE BOARD:\n" + JSON.stringify({
        contradictions: b.contradictions, alibis: b.alibis,
        csi_gaps: b.csi_gaps, ce_gaps: b.ce_gaps, collisions: b.collisions,
        csi_ledger: b.ledger, timeline: b.timeline, machine_records: b.machine,
        interviews: b.histories, next_questions: b.next_questions
      }, null, 1);
    },
    apply: function (b, o) {
      b.sufficiency = o.sufficiency || []; b.vetoes = o.vetoes || [];
      b.corroboration_needed = o.corroboration_needed || [];
    } },
  { id: "lead_detective", chair: "lead_detective", file: "11_lead_detective.md", model: "reasoning",
    required: ["leads", "gaps", "brief"],
    handoff: function (b) { return {
      from: ["coroner", "csi", "analyst", "digital", "cross_examiner", "interviewer", "prosecutor"],
      detail: "current board: " + (b.contradictions || []).length + " contradictions, " + (b.alibis || []).length + " alibis, " + ((b.csi_gaps || []).length + (b.ce_gaps || []).length) + " evidence gaps, " + (b.collisions || []).length + " timeline collision(s), and " + (b.sufficiency || []).length + " court-review item(s)"
    }; },
    input: function (b) {
      return "THE BOARD:\n" + JSON.stringify({
        coroner: b.coroner ? { cause: b.coroner.cause, manner: b.coroner.manner, death_window: b.coroner.death_window } : null,
        contradictions: b.contradictions, alibis: b.alibis,
        csi_ledger: b.ledger, csi_gaps: b.csi_gaps, ce_gaps: b.ce_gaps,
        collisions: b.collisions, timeline: b.timeline, digital: b.machine,
        interviews: b.histories, next_questions: b.next_questions,
        sufficiency: b.sufficiency, prosecutor_vetoes: b.vetoes,
        corroboration_needed: b.corroboration_needed
      }, null, 1);
    },
    apply: function (b, o) { b.leads = o.leads || []; b.gaps = o.gaps || []; b.brief = o.brief || ""; } }
];

function countFindings(o) {
  var n = 0;
  Object.keys(o || {}).forEach(function (k) { if (k !== "squad_note" && Array.isArray(o[k])) n += o[k].length; });
  return n;
}

function parseModelJson(text) {
  var t = String(text || "").trim();
  var start = t.indexOf("{"), end = t.lastIndexOf("}");
  if (start === -1 || end === -1) throw new Error("no JSON object in model reply");
  return JSON.parse(t.slice(start, end + 1));
}

function schemaErrors(step, o) {
  var errs = [];
  (step.required || []).forEach(function (k) {
    if (!(k in o)) errs.push("missing key: " + k);
  });
  if (!validSquadNote(o.squad_note)) errs.push("missing or invalid quote-backed squad note");
  return errs;
}

// ---------- the runner ----------
function chairName(id) {
  var c = CHAIRS.filter(function (x) { return x.id === id; })[0];
  return c ? c.name : id;
}
function noteRecipients(step, book) {
  return STEPS.filter(function (target) {
    return target.handoff && target.handoff(book).from.indexOf(step.id) !== -1;
  });
}
async function runStep(step, book, hooks) {
  hooks.chair(step.chair, "running", null);
  var ev = hooks.event || function () {};
  try {
    var output;
    {
      var model = modelNameFor(step);
      ev(chairName(step.chair), step.id + ": " + model + " took the file");
      var prompt = PROMPTS[step.file];
      if (!prompt) throw new Error("prompt file missing: " + step.file);
      var recipients = noteRecipients(step, book);
      var targetNames = recipients.map(function (target) { return chairName(target.chair); }).join(", ") || "the squad room";
      prompt += "\n\nSQUAD ROOM NOTE: Add a top-level `squad_note` object to your JSON: {\"message\":\"...\",\"evidence\":[{\"doc_id\":\"doc01\",\"quote\":\"exact quote from that document\"}]}. Write one short note in your own chair's voice to " + targetNames + ". Use only your findings. Every case fact in the note must be backed by an exact quote in evidence. Use at most two quotes. Do not add conclusions or facts that are absent from your structured findings. If the file cannot support a useful note, return exactly {\"message\":\"No quote-backed handoff.\",\"evidence\":[]} for squad_note.";
      var userText = step.input(book);
      var incomingNotes = (book.squad_notes || []).filter(function (note) { return note.toStepId === step.id; });
      if (incomingNotes.length) userText += "\n\nVERIFIED SQUAD HANDOFF NOTES:\n" + JSON.stringify(incomingNotes, null, 1);
      var models = [model];
      if ((step.model === "world" || step.model === "field") && cfg().fastModel !== model) models.push(cfg().fastModel);
      var output = null, lastErr = null;
      for (var mi = 0; mi < models.length && !output; mi++) {
        if (mi > 0) book.log.push(step.id + ": " + models[0] + " gave no usable output in two attempts; " + models[mi] + " covered the step (fallback, logged)");
        for (var attempt = 0; attempt < 2 && !output; attempt++) {
          var raw;
          try {
            raw = await callGemini(models[mi], prompt, attempt === 0 ? userText
              : userText + "\n\nYour previous reply failed validation: " + lastErr + ". Reply again with the full JSON only, all required keys present, and every quote inside string values properly escaped.");
          } catch (ce) { lastErr = "call failed (" + (ce && ce.message ? ce.message : String(ce)) + ")"; continue; }
          try {
            var parsed = parseModelJson(raw);
            var errs = schemaErrors(step, parsed);
            if (errs.length) { lastErr = errs.join("; "); continue; }
            output = parsed;
          } catch (pe) { lastErr = "reply was not valid JSON (" + pe.message + ")"; }
        }
      }
      if (!output) throw new Error("validation: " + lastErr);
    }
    var drop = { n: 0 };
    var validator = VALIDATORS[step.id];
    if (validator) output = validator(output, drop, book.log);
    var recipients = noteRecipients(step, book);
    if (output.squad_note.message !== "No quote-backed handoff.") {
      recipients.forEach(function (recipient) {
        book.squad_notes.push({
          fromChair: step.chair, toChair: recipient.chair,
          fromStepId: step.id, toStepId: recipient.id,
          message: output.squad_note.message,
          evidence: output.squad_note.evidence
        });
      });
      if (hooks.note) hooks.note(step, output.squad_note, recipients);
    }
    book.dropped += drop.n;
    if (drop.n) book.log.push(step.id + ": " + drop.n + " finding(s) dropped by the quote check");
    step.apply(book, output);
    book.outputs[step.id] = output;
    hooks.chair(step.chair, "done", countFindings(output));
    ev(chairName(step.chair), step.id + ": posted " + countFindings(output) + " finding(s)");
    return true;
  } catch (e) {
    book.failed_steps.push(step.id + ": " + (e && e.message ? e.message : String(e)));
    hooks.chair(step.chair, "failed", null);
    ev(chairName(step.chair), step.id + ": FAILED, " + (e && e.message ? e.message : String(e)));
    return false;
  }
}

function validSquadNote(note) {
  if (!note || typeof note.message !== "string" || !note.message.trim() || note.message.length > 500
    || !Array.isArray(note.evidence) || note.evidence.length > 2) return false;
  if (!note.evidence.length) return note.message === "No quote-backed handoff.";
  return note.evidence.every(function (item) { return item && quoteOk(item.quote, item.doc_id); });
}

async function runAll(hooks, opts) {
  var book = newBook();
  if (opts && opts.door2) book.door2 = opts.door2;
  hooks = hooks || {};
  hooks.chair = hooks.chair || function () {};
  hooks.status = hooks.status || function () {};
  hooks.event = hooks.event || function () {};
  hooks.step = hooks.step || function () {};
  for (var i = 0; i < STEPS.length; i++) {
    hooks.status("Working: " + STEPS[i].id.replace(/_/g, " "));
    await runStep(STEPS[i], book, hooks);
    hooks.step(book);
    if (i < STEPS.length - 1 && hooks.pause) await hooks.pause();
  }
  hooks.status(book.failed_steps.length ? "Done, with failed steps: " + book.failed_steps.join("; ") : "Done" + (book.dropped ? " — quote check dropped " + book.dropped + " finding(s)" : ""));
  return book;
}

async function askAgent(chairId, question, currentBook, activeStep) {
  var step = STEPS.filter(function (x) { return x.chair === chairId; })[0] || STEPS[STEPS.length - 1];
  var chair = CHAIRS.filter(function (x) { return x.id === chairId; })[0] || CHAIRS[CHAIRS.length - 1];
  var reply = await callGemini(modelNameFor(step),
    "You are " + chair.name + ", a member of the Murder Board squad. Answer the user's question directly in 2 to 4 short sentences. Use only the provided case documents and posted agent findings. Do not decide guilt, call anyone a liar, or turn a lead into proof. If the current run is incomplete, say that. Every factual statement about the case must be backed by an exact document quote in the evidence array. Return JSON only: {\"reply\":\"...\",\"evidence\":[{\"doc_id\":\"doc01\",\"quote\":\"verbatim quote from that document\"}]}. Keep evidence to at most three quotes. If the file cannot answer, say so and return an empty evidence array.",
    "CASE: " + CURRENT_CASE + "\nCHAIR: " + chair.name + "\nCURRENT RUN STEP: " + (activeStep || "complete") + "\nUSER: " + question + "\n\nPOSTED AGENT FINDINGS:\n" + JSON.stringify({
      custody: currentBook.custody,
      records: currentBook.records,
      coroner: currentBook.coroner,
      csi_ledger: (currentBook.ledger || []).slice(0, 40),
      claims: (currentBook.claims || []).slice(0, 80),
      csi_gaps: (currentBook.csi_gaps || []).slice(0, 12),
      timeline: (currentBook.timeline || []).slice(0, 20),
      collisions: (currentBook.collisions || []).slice(0, 12),
      contradictions: (currentBook.contradictions || []).slice(0, 12),
      alibis: currentBook.alibis,
      interviews: (currentBook.histories || []).slice(0, 12),
      sufficiency: (currentBook.sufficiency || []).slice(0, 12),
      leads: (currentBook.leads || []).slice(0, 8),
      gaps: (currentBook.gaps || []).slice(0, 12),
      brief: currentBook.brief || "",
      squad_notes: (currentBook.squad_notes || []).slice(-12),
      failed_steps: currentBook.failed_steps || []
    }, null, 1) + "\n\nCASE DOCUMENTS:\n" + docsText());
  var parsed = parseModelJson(reply);
  if (typeof parsed.reply !== "string" || !parsed.reply.trim() || !Array.isArray(parsed.evidence)) throw new Error("reply did not include an answer and source list");
  var evidence = parsed.evidence.filter(function (item) {
    return item && docKnown(item.doc_id) && quoteOk(item.quote, item.doc_id);
  }).slice(0, 3);
  if (evidence.length !== parsed.evidence.length) throw new Error("one or more cited quotes did not match the case file");
  return { reply: parsed.reply.slice(0, 900), evidence: evidence };
}

G.MB = {
  runAll: runAll, newBook: newBook, recomputeScore: recomputeScore, modelFor: modelNameFor,
  quoteOk: quoteOk, VALIDATORS: VALIDATORS, STEPS: STEPS, CHAIRS: CHAIRS,
  DOC_BY_ID: DOC_BY_ID, CASES: CASES, setCase: setCase,
  findFixture: findFixture, buildRecordsFromFixture: buildRecordsFromFixture, setLiveFixture: setLiveFixture,
  askAgent: askAgent,
  currentCase: function () { return CURRENT_CASE; },
  docById: function (id) { return DOC_BY_ID[id]; }
};
if (typeof module !== "undefined" && module.exports) module.exports = G.MB;
})();

// ---------- screens (browser only) ----------
(function () {
"use strict";
if (typeof document === "undefined") return;
var MB = window.MB;
var DOCS = window.CASE_DOCS || [];
var book = MB.newBook();
var chairEls = {};
var quoteReturnFocus = null;
var profileReturnFocus = null;
var runInProgress = false;
var activeStepId = null;
var questionInProgress = false;

function el(id) { return document.getElementById(id); }
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}
function docTitle(id) {
  var d = MB.docById(id);
  return d ? d.title + " (" + d.date + ")" : id;
}
function docCitation(id) {
  var d = MB.docById(id);
  return d ? id + " · " + d.title + " · " + d.date + " · " + d.author : id;
}
function selectedCase() {
  return MB.CASES.filter(function (c) { return c.case_id === MB.currentCase(); })[0];
}
function entityKey(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}
function phraseInText(text, phrase) {
  return (" " + entityKey(text) + " ").indexOf(" " + entityKey(phrase) + " ") !== -1;
}
function identityNamedIn(text, person) {
  if (phraseInText(text, person.name)) return true;
  var parts = entityKey(person.name).split(" ").filter(function (part) { return part.length > 1; });
  return parts.length > 1 && phraseInText(text, parts[0]) && phraseInText(text, parts[parts.length - 1]);
}
function verifiedAliases(person) {
  var current = selectedCase();
  var docs = current ? current.documents : [];
  return (person.aliases || []).map(function (alias) {
    if (entityKey(alias).length < 3) return null;
    var match = null;
    docs.some(function (item) {
      if (!identityNamedIn(item.text, person) && !identityNamedIn(item.author, person)) return false;
      var line = String(item.text || "").split(/\r?\n/).filter(function (text) { return phraseInText(text, alias); })[0];
      if (line) { match = { name: alias, doc_id: item.id, quote: line }; return true; }
      return false;
    });
    return match;
  }).filter(Boolean);
}
function personForms(person) {
  return [person.name].concat(verifiedAliases(person).map(function (alias) { return alias.name; }))
    .filter(function (name) { return entityKey(name).length >= 3; });
}
function mentionsPerson(value, person) {
  var haystack = " " + entityKey(value) + " ";
  return personForms(person).some(function (form) { return haystack.indexOf(" " + entityKey(form) + " ") !== -1; });
}
function matchesPersonName(value, person) {
  if (mentionsPerson(value, person)) return true;
  var name = entityKey(person.name).split(" ").filter(function (part) { return part.length > 1; });
  var candidate = entityKey(value).split(" ");
  return name.length > 1 && candidate.indexOf(name[0]) !== -1 && candidate.indexOf(name[name.length - 1]) !== -1;
}
function personProfileData(person) {
  var current = selectedCase();
  var docs = current ? current.documents : [];
  var claims = book.claims.filter(function (claim) {
    return matchesPersonName(claim.person, person) || mentionsPerson(claim.claim, person) || mentionsPerson(claim.quote, person);
  });
  var events = book.intake_events.filter(function (event) {
    var who = Array.isArray(event.who) ? event.who : [event.who];
    return who.some(function (name) { return matchesPersonName(name, person); })
      || mentionsPerson([event.what, event.where, event.quote].join(" "), person);
  });
  var alibis = book.alibis.filter(function (alibi) { return matchesPersonName(alibi.person, person); });
  var histories = (book.histories || []).filter(function (history) { return matchesPersonName(history.person, person); });
  var medicalFacts = /victim/i.test(person.role || "") && book.coroner ? (book.coroner.medical_facts || []) : [];
  var relatedDocIds = [];
  function addDoc(id) { if (id && relatedDocIds.indexOf(id) < 0) relatedDocIds.push(id); }
  claims.forEach(function (claim) { addDoc(claim.doc_id); });
  docs.filter(function (doc) { return matchesPersonName(doc.author, person); }).forEach(function (doc) { addDoc(doc.id); });
  events.forEach(function (event) { addDoc(event.doc_id); });
  verifiedAliases(person).forEach(function (alias) { addDoc(alias.doc_id); });
  alibis.forEach(function (alibi) { (alibi.reasons || []).forEach(function (reason) { addDoc(reason.doc_id); }); });
  histories.forEach(function (history) {
    (history.changes || []).forEach(function (change) { addDoc(change.earlier_doc); addDoc(change.later_doc); });
  });
  medicalFacts.forEach(function (fact) { addDoc(fact.doc_id); });
  var contradictions = book.contradictions.filter(function (item) {
    return mentionsPerson(item.a_quote, person) || mentionsPerson(item.b_quote, person)
      || relatedDocIds.indexOf(item.a_doc) !== -1 || relatedDocIds.indexOf(item.b_doc) !== -1;
  });
  contradictions.forEach(function (item) { addDoc(item.a_doc); addDoc(item.b_doc); });
  return {
    aliases: verifiedAliases(person), claims: claims, events: events, alibis: alibis, histories: histories,
    medicalFacts: medicalFacts,
    contradictions: contradictions,
    documents: docs.filter(function (doc) { return relatedDocIds.indexOf(doc.id) !== -1; })
  };
}
function sourceButton(docId) {
  if (!docId) return "";
  var doc = MB.docById(docId);
  return '<details class="source-details"><summary>Open ' + esc(docId) + ' source</summary>' +
    (doc ? '<pre class="detail-document">' + esc(doc.text) + '</pre>' : '<p>Source document is not in this case file.</p>') + '</details>';
}
function quoteCard(label, quote, docId) {
  return '<article class="source-quote"><h5>' + esc(label) + '</h5><blockquote>&ldquo;' + esc(quote || "") + '&rdquo;</blockquote><cite>' + esc(docCitation(docId)) + '</cite>' + sourceButton(docId) + '</article>';
}
function supportedEventField(value, quote, docId) {
  if (!value) return "";
  var doc = MB.docById(docId);
  return phraseInText(quote, value) || (doc && phraseInText(doc.text, value)) ? value : "";
}
function supportedWindow(alibi) {
  return (alibi.reasons || []).some(function (reason) {
    return supportedEventField(alibi.window, reason.quote, reason.doc_id);
  }) ? alibi.window : "";
}

function setQuotePanel(title, quoteA, quoteB, alt, focusTarget) {
  quoteReturnFocus = focusTarget || document.activeElement;
  el("modalTitle").textContent = title;
  el("quoteA").textContent = quoteA.text || "";
  el("quoteACite").innerHTML = esc(quoteA.source || "") + (quoteA.docId ? '<br>' + sourceButton(quoteA.docId) : "");
  el("quoteB").textContent = quoteB.text || "";
  el("quoteBCite").innerHTML = esc(quoteB.source || "") + (quoteB.docId ? '<br>' + sourceButton(quoteB.docId) : "");
  el("quotePair").hidden = false;
  el("sourceBody").hidden = true;
  el("sourceBody").innerHTML = "";
  el("modalAlt").textContent = alt || "";
  el("quoteModal").hidden = false;
  el("quoteModal").classList.remove("hidden");
  el("modalClose").focus();
}

function closeQuotePanel() {
  el("quoteModal").hidden = true;
  el("quoteModal").classList.add("hidden");
  if (quoteReturnFocus && document.contains(quoteReturnFocus)) quoteReturnFocus.focus();
}

function showProfile(title, body, focusTarget) {
  profileReturnFocus = focusTarget || document.activeElement;
  el("profileContent").innerHTML = '<h2 id="profileName">' + esc(title) + '</h2>' + body;
  el("profileBackdrop").hidden = false;
  el("profileDrawer").hidden = false;
  el("profileClose").focus();
}

function closeProfile() {
  el("profileBackdrop").hidden = true;
  el("profileDrawer").hidden = true;
  if (profileReturnFocus && document.contains(profileReturnFocus)) profileReturnFocus.focus();
}

function openProfile(person, focusTarget) {
  if (!person) return;
  var data = personProfileData(person);
  var body = '<div class="profile-portrait">' + photoHtml(person.name) + '</div><p class="detail-role"><strong>Role in the case file:</strong> ' + esc(person.role || "Not stated in the case file.") + '</p>';
  body += '<section class="detail-section"><h3>Aliases</h3>';
  body += data.aliases.length ? data.aliases.map(function (alias) {
    return quoteCard("Recorded alias: " + alias.name, alias.quote, alias.doc_id);
  }).join("") : '<p>No aliases are supported by a source in this file.</p>';
  body += '</section><section class="detail-section"><h3>Sourced claims</h3>';
  body += data.claims.length ? data.claims.map(function (claim) {
    return '<article class="detail-item"><h4>' + esc(claim.kind || "Claim") + '</h4><p>' + esc(claim.claim) + '</p>' + quoteCard("Source quote", claim.quote, claim.doc_id) + '</article>';
  }).join("") : '<p>No sourced claims for this person.</p>';
  body += data.medicalFacts.length ? data.medicalFacts.map(function (fact) {
    return '<article class="detail-item"><h4>Medical finding</h4><p>' + esc(fact.fact) + '</p>' + quoteCard("Examiner source", fact.quote, fact.doc_id) + '</article>';
  }).join("") : "";
  body += '</section><section class="detail-section"><h3>Events</h3>';
  body += data.events.length ? data.events.map(function (event) {
    var when = supportedEventField(event.when_text, event.quote, event.doc_id);
    var where = supportedEventField(event.where, event.quote, event.doc_id);
    return '<article class="detail-item"><h4>' + esc(event.what) + '</h4>' + (when || where ? '<p>' + esc(when || "") + (when && where ? ' · ' : "") + esc(where || "") + '</p>' : "") + quoteCard("Source quote", event.quote, event.doc_id) + '</article>';
  }).join("") : '<p>No sourced events for this person.</p>';
  body += '</section><section class="detail-section"><h3>Alibi assessment</h3>';
  body += data.alibis.length ? data.alibis.map(function (alibi) {
    return '<article class="detail-item"><p><strong>' + esc(alibi.rating) + '</strong>' + (supportedWindow(alibi) ? ' · ' + esc(supportedWindow(alibi)) : "") + '</p>' +
      ((alibi.reasons || []).map(function (reason) { return quoteCard("Alibi source", reason.quote, reason.doc_id); }).join("") || '<p>No sourced reasons recorded.</p>') + '</article>';
  }).join("") : '<p>No alibi assessment for this person.</p>';
  body += '</section><section class="detail-section"><h3>Statement history</h3>';
  body += data.histories.length ? data.histories.map(function (history) {
    return (history.changes || []).map(function (change) {
      return '<article class="detail-item"><h4>' + esc(change.topic) + '</h4>' + quoteCard("Earlier statement", change.earlier_quote, change.earlier_doc)
        + quoteCard("Later statement", change.later_quote, change.later_doc) + '</article>';
    }).join("");
  }).join("") : '<p>No sourced statement changes for this person.</p>';
  body += '</section><section class="detail-section"><h3>Contradictions</h3>';
  body += data.contradictions.length ? data.contradictions.map(function (item) {
    return '<article class="detail-item"><h4>' + esc(item.kind) + ' · ' + esc(item.severity) + '</h4>' +
      quoteCard("Side A", item.a_quote, item.a_doc) + quoteCard("Side B", item.b_quote, item.b_doc) +
      '<p class="innocent">The innocent reading: ' + esc(item.innocent_alternative) + '</p></article>';
  }).join("") : '<p>No sourced contradictions for this person.</p>';
  body += '</section><section class="detail-section"><h3>Related documents</h3>';
  body += data.documents.length ? data.documents.map(function (doc) {
    return '<p><span class="detail-source">' + esc(doc.id) + ' · ' + esc(doc.title) + '</span>' + sourceButton(doc.id) + '</p>';
  }).join("") : '<p>No related source documents were identified.</p>';
  body += '</section><p class="portrait-note">Portrait is illustrative, not evidence.</p>';
  showProfile(person.name, body, focusTarget);
}

function openDocument(docId, focusTarget) {
  var doc = MB.docById(docId);
  if (!doc) return;
  showProfile(doc.title, '<p class="detail-source">' + esc(doc.id + " · " + doc.date + " · " + doc.author) + '</p><pre class="detail-document">' + esc(doc.text) + '</pre>', focusTarget);
}

function openEvidence(item, focusTarget) {
  if (!item) return;
  var docId = item.doc_id || "";
  if (!docId && item.quote) {
    var current = selectedCase();
    var source = current && current.documents.filter(function (doc) { return entityKey(doc.text).indexOf(entityKey(item.quote)) !== -1; })[0];
    docId = source ? source.id : "";
  }
  var body = '<p><strong>Item:</strong> ' + esc(item.item_no || "Evidence") + '</p><p>' + esc(item.description || "No description recorded.") + '</p>';
  if (item.status) body += '<p><strong>Status:</strong> ' + esc(item.status) + '</p>';
  if (item.quote) body += quoteCard("Evidence ledger quote", item.quote, docId);
  else body += '<p class="detail-source">No exact quote is attached to this item. The cited file document appears below.</p>';
  var sourceDoc = docId && MB.docById(docId);
  body += sourceDoc ? '<h3>Source document</h3><pre class="detail-document">' + esc(sourceDoc.text) + '</pre>' : '<p>No source document is recorded for this item.</p>';
  showProfile("Evidence detail", body, focusTarget);
}

function documentedLinks() {
  var links = [];
  book.persons.forEach(function (person, personIndex) {
    personProfileData(person).documents.forEach(function (doc) {
      links.push({ person: person, personIndex: personIndex, doc_id: doc.id });
    });
  });
  return links;
}
function documentedPeople() {
  var links = documentedLinks();
  return book.persons.map(function (person, idx) {
    return { person: person, index: idx, count: links.filter(function (link) { return link.person === person; }).length };
  }).filter(function (entry) { return entry.count > 0; });
}

function openDocumentLink(link, focusTarget) {
  var doc = link && MB.docById(link.doc_id);
  if (!doc) return;
  var data = personProfileData(link.person), body = '<p class="detail-source">' + esc(doc.id + " · " + doc.title + " · " + doc.date) + '</p>';
  data.claims.filter(function (claim) { return claim.doc_id === doc.id; }).forEach(function (claim) {
    body += quoteCard("Claim: " + claim.claim, claim.quote, doc.id);
  });
  data.aliases.filter(function (alias) { return alias.doc_id === doc.id; }).forEach(function (alias) {
    body += quoteCard("Recorded alias: " + alias.name, alias.quote, doc.id);
  });
  data.events.filter(function (event) { return event.doc_id === doc.id; }).forEach(function (event) {
    body += quoteCard("Event: " + event.what, event.quote, doc.id);
  });
  data.alibis.forEach(function (alibi) {
    (alibi.reasons || []).filter(function (reason) { return reason.doc_id === doc.id; }).forEach(function (reason) {
      body += quoteCard("Alibi source: " + alibi.rating, reason.quote, doc.id);
    });
  });
  data.histories.forEach(function (history) {
    (history.changes || []).forEach(function (change) {
      if (change.earlier_doc === doc.id) body += quoteCard("Earlier statement: " + change.topic, change.earlier_quote, doc.id);
      if (change.later_doc === doc.id) body += quoteCard("Later statement: " + change.topic, change.later_quote, doc.id);
    });
  });
  data.medicalFacts.filter(function (fact) { return fact.doc_id === doc.id; }).forEach(function (fact) {
    body += quoteCard("Medical finding: " + fact.fact, fact.quote, doc.id);
  });
  data.contradictions.forEach(function (item) {
    if (item.a_doc === doc.id) body += quoteCard("Contradiction: " + item.kind, item.a_quote, doc.id);
    if (item.b_doc === doc.id) body += quoteCard("Contradiction: " + item.kind, item.b_quote, doc.id);
  });
  body += '<h3>Full document</h3><pre class="detail-document">' + esc(doc.text) + '</pre>';
  setSourcePanel("Documented link: " + link.person.name, body, "", focusTarget);
}

function setSourcePanel(title, body, alt, focusTarget) {
  quoteReturnFocus = focusTarget || document.activeElement;
  el("modalTitle").textContent = title;
  el("quotePair").hidden = true;
  el("sourceBody").innerHTML = body;
  el("sourceBody").hidden = false;
  el("modalAlt").textContent = alt || "";
  el("quoteModal").hidden = false;
  el("quoteModal").classList.remove("hidden");
  el("modalClose").focus();
}

function buildStrip() {
  var strip = el("squadStrip");
  strip.innerHTML = "";
  MB.CHAIRS.forEach(function (c) {
    var d = document.createElement("div");
    d.className = "chair agent-" + c.id; d.id = "chair-" + c.id;
    var st = MB.STEPS.filter(function (x) { return x.chair === c.id; })[0];
    var mn = st ? String(MB.modelFor(st)).replace("gemini-4-", "").toUpperCase() : "";
    d.innerHTML = '<span class="agent">' + esc(agentOf(c.id).replace("Dr. ", "").split(" ").pop().toUpperCase()) + '</span>' + esc(c.name) + '<span class="model">' + esc(mn) + '</span><span class="count"></span>';
    strip.appendChild(d);
    chairEls[c.id] = d;
  });
}
function setChair(id, state, count) {
  var d = chairEls[id];
  if (!d) return;
  d.classList.remove("running", "done", "failed");
  if (state !== "idle") d.classList.add(state);
  if (count != null) d.querySelector(".count").textContent = count + " posted";
  if (state === "running") {
    setFeedActivity(agentOf(id) + " is reviewing the assigned packet\u2026");
    try {
      var st = (MB.STEPS || []).filter(function (x) { return x.id === activeStepId; })[0];
      if (st && st.handoff && typeof book !== "undefined" && book) {
        var h = st.handoff(book);
        (h.from || []).forEach(function (f) {
          if (f !== id) chatBubble(f, "Handing to " + agentOf(id) + " \u00b7 " + chairNameOf(id) + ": " + h.detail + ".", "note", { recipients: [{ chair: id }] });
        });
      }
    } catch (e) {}
  }
}

function renderRegistry() {
  var current = MB.CASES.filter(function (c) { return c.case_id === MB.currentCase(); })[0];
  el("caseTitle").textContent = current ? current.case_title : "";
  var es = el("evidenceStatus");
  if (es) {
    var n = current ? current.documents.length : 0;
    var claims = (typeof book !== "undefined" && book && book.claims) ? book.claims.length : 0;
    var pulledN = (typeof book !== "undefined" && book && book.records && book.records.starter_items) ? book.records.starter_items.length : 0;
    es.textContent = n + " documents in evidence." + (claims ? " Intake has extracted " + claims + " quote-checked claims from them so far." : " Not yet worked — work the case and Intake extracts the claims.") + (pulledN ? " Records has pulled " + pulledN + " items from the public trail into evidence." : "");
  }
  var docs = current ? current.documents : [];
  var pulledItems = (typeof book !== "undefined" && book && book.records && book.records.starter_items) ? book.records.starter_items : [];
  var rowsHtml = docs.map(function (d) {
    return "<tr data-doc='" + d.id + "'><td>" + d.id + "</td><td>" + esc(d.title) + "</td><td>" + esc(d.type) + "</td><td>" + esc(d.date) + "</td><td>" + esc(d.author) + "</td><td>view</td></tr>";
  }).join("");
  rowsHtml += pulledItems.map(function (it, ix) {
    return "<tr class='pulled' data-pull='" + ix + "'><td>PULLED</td><td>" + esc(it.item) + "</td><td>pulled · census</td><td></td><td>" + esc(it.source_class || "public trail") + "</td><td>view</td></tr>";
  }).join("");
  el("registryBody").innerHTML = rowsHtml;
  Array.prototype.forEach.call(document.querySelectorAll("#registryBody tr"), function (tr) {
    tr.addEventListener("click", function () {
      var d = MB.docById(tr.getAttribute("data-doc"));
      el("docViewer").textContent = d ? d.text : "";
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll("#registryBody tr.pulled"), function (tr) {
    tr.addEventListener("click", function () {
      var it = pulledItems[Number(tr.getAttribute("data-pull"))];
      el("docViewer").textContent = it ? (it.item + "\n\n" + (it.label || "UNVERIFIED") + " · " + (it.source_class || "") + "\nPulled by Records from the public trail during this run and added to the evidence.") : "";
    });
  });
}

function tiltFor(seed) {
  var h = 0;
  for (var i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 997;
  return ((h % 5) - 2) * 1.1;
}
function pinCard(cls, pinKey, inner, seed, kind, idx, label) {
  var t = tiltFor(seed || pinKey);
  return '<div role="button" tabindex="0" class="' + cls + '" data-pin="' + esc(pinKey) + '" data-tilt="' + t + '" data-open-kind="' + kind + '" data-open-idx="' + idx + '" aria-label="' + esc(label) + '" style="transform: rotate(' + t + 'deg)">' + inner + '</div>';
}
function photoHtml(name) {
  var map = (window.PERSON_PHOTOS || {})[MB.currentCase()] || {};
  var key = String(name || "").toLowerCase().replace(/[^a-z ]/g, "").replace(/\s+/g, " ").trim();
  var src = map[key];
  if (!src) { // surname fallback when the file uses a fuller or shorter name
    var sur = key.split(" ").pop();
    for (var k in map) { if (k.split(" ").pop() === sur) { src = map[k]; break; } }
  }
  if (src) return '<img class="photo" src="' + src + '" alt=""><span class="portrait-caption">Illustrative portrait · not evidence</span>';
  return '<div class="photo">' + esc(initialsOf(name)) + '</div>';
}

function initialsOf(name) {
  return String(name).replace(/["']/g, "").split(/\s+/).map(function (w) { return w.charAt(0); }).join("").slice(0, 2).toUpperCase();
}
function renderBoard() {
  var layer = el("pinLayer");
  if (!layer) return;
  var current = selectedCase();
  var docs = current ? current.documents : [];
  var html = '<div class="pin-title" data-pin="title" data-tilt="0" id="caseQuestion" title="The question before the board"><div class="qmark">?</div><div class="who">WHO DID IT</div><div class="case-name">' + esc(current ? current.case_title : "") + '</div></div>';
  html += book.persons.map(function (p, i) {
    var claims = book.claims.filter(function (c) { return matchesPersonName(c.person, p); });
    var isVictim = /victim/i.test(p.role || "");
    var alibi = book.alibis.filter(function (a) { return matchesPersonName(a.person, p); })[0];
    return pinCard("pin-card person" + (isVictim ? " victim" : ""), "person:" + p.name,
      photoHtml(p.name) + '<h4>' + esc(p.name) + '</h4><p class="role">' + esc(p.role) + '</p>' +
      (alibi ? '<p class="alibi-chip rate-' + esc(String(alibi.rating).toLowerCase().replace(/\s+/g, "-")) + '">' + esc(alibi.rating) + '</p>' : "") +
      claims.slice(0, 2).map(function (c) { return '<p class="q">&ldquo;' + esc(c.quote) + '&rdquo;</p>'; }).join(""),
      p.name, "person", i, "Open profile: " + p.name);
  }).join("");
  html += docs.map(function (d, i) {
    return pinCard("pin-card docslip", "doc:" + d.id,
      '<h5>' + esc(d.id) + ' &middot; ' + esc(d.type) + '</h5><p>' + esc(d.title) + '</p><p class="role">' + esc(d.date) + ' &middot; ' + esc(d.author) + '</p>', d.id, "doc", i, "Open document " + d.id + ": " + d.title);
  }).join("");
  var items = book.ledger.length ? book.ledger : book.evidence_items;
  html += items.slice(0, 8).map(function (it, i) {
    return pinCard("pin-card evidence", "ev:" + i,
      '<h5>' + esc(it.item_no ? "Item " + it.item_no : "Evidence") + '</h5><p>' + esc(it.description || "") + '</p>', "ev" + i, "evidence", i, "Open evidence details: " + (it.description || "evidence item"));
  }).join("");
  var gaps = book.csi_gaps.concat(book.ce_gaps);
  html += gaps.slice(0, 6).map(function (g, i) {
    return '<article class="pin-note" data-pin="gap:' + i + '" data-tilt="' + tiltFor("gap" + i) + '" style="transform: rotate(' + tiltFor("gap" + i) + 'deg)"><p class="note-q">' + esc(g.item) + '</p><p>' + esc(g.problem) + '</p></article>';
  }).join("");
  html += legendHtml();
  layer.innerHTML = html;
  var qc = el("caseQuestion");
  if (qc) {
    qc.setAttribute("role", "button"); qc.setAttribute("tabindex", "0"); qc.setAttribute("aria-label", "Open case question and death window");
    qc.addEventListener("click", function () { openCaseQuestion(qc); });
    qc.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openCaseQuestion(qc); }
    });
  }
  Array.prototype.forEach.call(layer.querySelectorAll("[data-open-kind]"), function (card) {
    card.addEventListener("click", function () {
      var idx = +card.getAttribute("data-open-idx");
      var kind = card.getAttribute("data-open-kind");
      if (kind === "person") openProfile(book.persons[idx], card);
      if (kind === "doc") openDocument(docs[idx].id, card);
      if (kind === "evidence") openEvidence(items[idx], card);
    });
    card.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); card.click(); }
    });
  });
  var threads = book.contradictions.map(function (c, i) {
    return '<button class="thread red" data-kind="contra" data-idx="' + i + '"><span class="sev sev-' + esc(c.severity) + '">' + esc(c.severity) + '</span>' + esc(c.kind) + ": " + esc(c.a_doc) + " vs " + esc(c.b_doc) + "</button>";
  });
  threads = threads.concat(book.collisions.map(function (c, i) {
    return '<button class="thread collision" data-kind="collision" data-idx="' + i + '">Timeline collision: ' + esc(c.who_or_what) + "</button>";
  }));
  threads = documentedPeople().map(function (entry, i) {
    return '<button class="thread documented" data-kind="profile" data-idx="' + i + '">Documented links: ' + esc(entry.person.name) + ' · ' + entry.count + ' sources</button>';
  }).concat(threads);
  el("threadList").innerHTML = threads.join("") || '<p class="hint">No threads yet.</p>';
  Array.prototype.forEach.call(document.querySelectorAll(".thread"), function (t) {
    t.addEventListener("click", function () { openThread(t.getAttribute("data-kind"), +t.getAttribute("data-idx"), t); });
  });
  scheduleYarn();
}

function scheduleYarn() { requestAnimationFrame(drawYarn); setTimeout(drawYarn, 400); }
function drawYarn() {
  var svg = el("yarnSvg"), board = el("corkboard"), layer = el("pinLayer");
  if (!svg || !board || !layer) return;
  if (!board.clientWidth) return;
  var pts = {};
  Array.prototype.forEach.call(layer.querySelectorAll("[data-pin]"), function (n) {
    var cx = layer.offsetLeft + n.offsetLeft + n.offsetWidth / 2;
    var cy = layer.offsetTop + n.offsetTop + n.offsetHeight / 2;
    var th = parseFloat(n.getAttribute("data-tilt") || "0") * Math.PI / 180;
    var r = n.offsetHeight / 2 - 2;
    pts[n.getAttribute("data-pin")] = { x: cx + r * Math.sin(th), y: cy - r * Math.cos(th) };
  });
  var W = board.clientWidth, H = board.clientHeight;
  svg.setAttribute("width", W); svg.setAttribute("height", H);
  svg.setAttribute("viewBox", "0 0 " + W + " " + H);
  function yarn(a, b, cls, kind, idx) {
    if (!a || !b) return "";
    var mx = (a.x + b.x) / 2, my = Math.max(a.y, b.y) + 14 + Math.abs(b.x - a.x) * 0.05;
    var d = "M " + a.x + " " + a.y + " Q " + mx + " " + my + " " + b.x + " " + b.y;
    var line = '<path class="yarn-line ' + cls + '" d="' + d + '"/>';
    if (!kind) return line;
    return line + '<path class="yarn-hit" data-kind="' + kind + '" data-idx="' + idx + '" d="' + d + '"><title>Open the thread</title></path>';
  }
  var out = "";
  documentedLinks().forEach(function (link, i) {
    out += yarn(pts["person:" + link.person.name], pts["doc:" + link.doc_id], "yarn-related", "source", i);
  });
  book.contradictions.forEach(function (c, i) {
    out += yarn(pts["doc:" + c.a_doc], pts["doc:" + c.b_doc], "yarn-contradiction yarn-" + String(c.severity).toLowerCase(), "contra", i);
  });
  book.collisions.forEach(function (c, i) {
    var ds = [];
    (c.quotes || []).forEach(function (q) { if (ds.indexOf(q.doc_id) < 0) ds.push(q.doc_id); });
    if (ds.length >= 2) out += yarn(pts["doc:" + ds[0]], pts["doc:" + ds[1]], "yarn-collision", "collision", i);
  });
  svg.innerHTML = out;
  Array.prototype.forEach.call(svg.querySelectorAll(".yarn-hit"), function (p) {
    var kind = p.getAttribute("data-kind"), idx = +p.getAttribute("data-idx");
    p.setAttribute("role", "button"); p.setAttribute("tabindex", "0");
    p.setAttribute("aria-label", kind === "contra" ? "Open contradiction quotes" : kind === "source" ? "Open documented source quotes" : "Open timeline collision quotes");
    p.addEventListener("click", function () { openThread(kind, idx, p); });
    p.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openThread(kind, idx, p); }
    });
  });
}

function legendHtml() {
  function row(cls, label) {
    return '<div class="key-row"><svg class="key-line" viewBox="0 0 40 8" preserveAspectRatio="none"><path class="yarn-line ' + cls + '" d="M1 4 Q 20 9 39 4"/></svg><span>' + label + "</span></div>";
  }
  return '<div class="pin-legend"><div class="key-title">STRING KEY</div>' +
    row("yarn-related", "Documented link") +
    row("yarn-contradiction", "Contradiction") +
    row("yarn-collision", "Timeline collision") +
    '<div class="key-note">Tap a colored string to read the two quotes it joins.</div></div>';
}

function openCaseQuestion(focusTarget) {
  var current = selectedCase();
  var victim = book.persons.filter(function (p) { return /victim/i.test(p.role || ""); })[0];
  var question = victim ? "Who killed " + victim.name + "?" : "Who did it?";
  var win = "";
  if (book.coroner && book.coroner.death_window) win = "Death window: " + book.coroner.death_window.start + " to " + book.coroner.death_window.end + ".";
  setQuotePanel("The question before the board",
    { text: question, source: current ? current.case_title : "" },
    { text: win, source: win ? "The Coroner's window, from the file" : "" },
    "This board judges the file. The detective does the detecting.", focusTarget);
}

function openThread(kind, idx, focusTarget) {
  if (kind === "source") { openDocumentLink(documentedLinks()[idx], focusTarget); return; }
  if (kind === "profile") { openProfile(documentedPeople()[idx].person, focusTarget); return; }
  var title, qa, qb, alt = "";
  if (kind === "contra") {
    var c = book.contradictions[idx];
    title = "Contradiction: " + c.kind + " (" + c.severity + ")";
    qa = { q: c.a_quote, cite: docCitation(c.a_doc), doc: c.a_doc };
    qb = { q: c.b_quote, cite: docCitation(c.b_doc), doc: c.b_doc };
    alt = "The innocent reading: " + c.innocent_alternative;
  } else {
    var col = book.collisions[idx];
    title = "Collision: " + col.who_or_what;
    var collisionBody = (col.quotes || []).map(function (quote, i) {
      return quoteCard("Supporting quote " + (i + 1), quote.quote, quote.doc_id);
    }).join("");
    setSourcePanel(title, collisionBody + '<p>' + esc(col.explanation || "") + '</p>', "", focusTarget);
    return;
  }
  setQuotePanel(title, { text: qa.q, source: qa.cite, docId: qa.doc }, { text: qb.q, source: qb.cite, docId: qb.doc }, alt, focusTarget);
}

function renderClock() {
  var band = "";
  if (book.coroner && book.coroner.death_window) {
    band = '<p class="death-band">DEATH WINDOW: ' + esc(book.coroner.death_window.start) + " to " + esc(book.coroner.death_window.end) + "</p>";
  }
  el("clockStrip").innerHTML = band + book.timeline.map(function (e) {
    return '<div class="clock-event' + (e.in_window ? " in-window" : "") + '"><span class="when">' + esc(e.window) + '</span> ' + esc(e.what) + (e.where ? " <span class='when'>" + esc(e.where) + "</span>" : "") + "</div>";
  }).join("") || '<p class="hint">Run the case to build the clock.</p>';
  el("collisionList").innerHTML = book.collisions.map(function (c) {
    return '<div class="collision"><strong>Collision:</strong> ' + esc(c.who_or_what) + ". " + esc(c.explanation) + "</div>";
  }).join("");
}

function renderJudgments() {
  el("dropCount").textContent = book.dropped
    ? book.dropped + " finding(s) dropped by validation: no quote in the file. They never reached the board."
    : "Validation dropped 0 findings on this run.";
  el("contradictionList").innerHTML = book.contradictions.map(function (c) {
    return '<div class="finding red"><span class="sev sev-' + esc(c.severity) + '">' + esc(c.severity) + '</span> <strong>' + esc(c.kind) + '</strong>' +
      '<blockquote>&ldquo;' + esc(c.a_quote) + '&rdquo;</blockquote><cite>' + esc(docTitle(c.a_doc)) + '</cite>' +
      '<blockquote>&ldquo;' + esc(c.b_quote) + '&rdquo;</blockquote><cite>' + esc(docTitle(c.b_doc)) + '</cite>' +
      '<p class="innocent">The innocent reading: ' + esc(c.innocent_alternative) + "</p></div>";
  }).join("");
  el("alibiBody").innerHTML = book.alibis.map(function (a) {
    var why = (a.reasons || []).map(function (r) { return "&ldquo;" + esc(r.quote) + "&rdquo; (" + esc(docTitle(r.doc_id)) + ")"; }).join("<br>");
    return "<tr><td>" + esc(a.person) + '</td><td><span class="rating rating-' + esc(String(a.rating).toLowerCase()) + '">' + esc(a.rating) + "</span></td><td>" + why + "</td></tr>";
  }).join("");
  var gaps = book.csi_gaps.map(function (g) { return { item: g.item, problem: g.problem }; })
    .concat(book.ce_gaps.map(function (g) { return { item: g.item, problem: g.problem }; }))
    .concat((book.machine && book.machine.camera_gaps || []).map(function (g) { return { item: g.camera, problem: "Camera mentioned in the file, never pulled." }; }));
  el("gapList").innerHTML = gaps.map(function (g) {
    return '<div class="finding"><strong>' + esc(g.item) + "</strong><p>" + esc(g.problem) + "</p></div>";
  }).join("");
  el("leadList").innerHTML = book.leads.map(function (l) {
    return '<div class="finding"><span class="score">' + l.score + "</span> <strong>" + esc(l.action) + '</strong><p class="arith">' + esc(l.arithmetic) + "</p><p>" + esc(l.reason) + "</p></div>";
  }).join("");
  el("questionList").innerHTML = book.next_questions.map(function (q) {
    return '<div class="finding"><strong>' + esc(q.person) + ":</strong> " + esc(q.question) + '<p class="innocent">Anchored to: &ldquo;' + esc(q.anchored_quote) + '&rdquo; (' + esc(docTitle(q.doc_id)) + ")</p></div>";
  }).join("");
  el("sufficiencyList").innerHTML = book.sufficiency.map(function (s) {
    return '<div class="finding"><strong>' + esc(s.subject) + '</strong> <span class="rating">' + esc(s.rating) + "</span><p>Missing: " + esc(s.missing) + "</p></div>";
  }).join("");
}

var CASE_META = {
  "delgado-2019": { no: "MB-2019-1014", victim: "Raymond Delgado, 58", window: "Sun Oct 13, 2019, 9:00 PM to midnight", place: "Delgado Auto Body, Fifth Avenue", stamp: "COLD CASE", stampCls: "stamp-cold" },
  "screens-2025": { no: "MB-2025-1012", victim: "Treyvon Ellis, 19", window: "Sun Oct 12, 2025, 11:00 PM to midnight", place: "Brooklyn, New York", stamp: "OPEN", stampCls: "stamp-open" },
  "harborlight-2016": { no: "MB-2016-1010", victim: "Elena Marsh, 41", window: "Mon Oct 10, 2016, 10:30 PM to 12:30 AM", place: "Harborlight Restaurant and Marina", stamp: "COLD CASE", stampCls: "stamp-cold" },
  "starlite-2017": { no: "MB-2017-1104", victim: "Carla Ibanez, 47", window: "Sat Nov 4, 2017, 11:30 PM to 1:30 AM", place: "Starlite Lanes, Meridian Avenue", stamp: "COLD CASE", stampCls: "stamp-cold" }
};
function caseShortTitle(id) {
  var c = MB.CASES.filter(function (x) { return x.case_id === id; })[0];
  return c ? c.case_title.split(/[:\u2014]/)[0].trim() : id;
}
function renderCaseFolder() {
  var id = MB.currentCase();
  var m = CASE_META[id];
  if (!m || !el("folderTab")) return;
  el("folderTab").textContent = "CASE FILE " + m.no;
  el("folderFields").innerHTML =
    '<div class="ff"><span>Case</span><strong>' + esc(caseShortTitle(id)) + "</strong></div>" +
    '<div class="ff"><span>Victim</span><strong>' + esc(m.victim) + "</strong></div>" +
    '<div class="ff"><span>Death window</span><strong>' + esc(m.window) + "</strong></div>" +
    '<div class="ff"><span>Place</span><strong>' + esc(m.place) + "</strong></div>";
  var st = el("folderStamp");
  st.textContent = m.stamp;
  st.className = "folder-stamp " + m.stampCls;
}
function renderBriefHead() {
  var id = MB.currentCase();
  var m = CASE_META[id];
  if (!el("briefHead")) return;
  el("briefHead").innerHTML =
    '<div class="bh-org">MURDER BOARD</div><div class="bh-title">Case brief</div>' +
    '<div class="bh-meta">' + (m ? "Case file " + m.no + " \u00b7 " : "") + esc(caseShortTitle(id)) +
    "<br>Prepared by the Lead Detective chair (Argon). Every claim in this brief carries a quote from the file.</div>";
}

function renderBrief() {
  renderBriefHead();
  var text = book.brief || "Run the case to write the brief.";
  if (el("vetoToggle").checked && book.vetoes.length) {
    var needles = book.vetoes.map(function (v) { return v.phrase.toLowerCase(); });
    el("briefPage").innerHTML = text.split(/(?<=[.!?])\s+/).map(function (sentence) {
      var hit = needles.some(function (n) { return sentence.toLowerCase().indexOf(n) !== -1; });
      return hit ? '<span class="struck">' + esc(sentence) + "</span>" : esc(sentence);
    }).join(" ");
  } else {
    el("briefPage").textContent = text;
  }
}

function renderRecords() {
  var box = el("door2Results");
  if (!box) return;
  if (!book.records || !book.records.starter_items) { box.innerHTML = ""; return; }
  var h = "<h3>Starter file from the census: " + esc(book.records.subject || "") + "</h3>";
  h += book.records.starter_items.map(function (it) {
    return "<div class='finding'><span class='sev " + (it.label === "SOURCED" ? "low" : "medium") + "'>" + esc(it.label || "UNVERIFIED") + "</span> <b>" + esc(it.item) + "</b><div class='docref'>" + esc(it.source_class || "") + "</div></div>";
  }).join("");
  (book.records.collisions || []).forEach(function (c) {
    h += "<div class='finding'><span class='sev high'>name collision</span> <b>" + esc(c.name) + "</b><p>" + esc(c.note) + "</p></div>";
  });
  if (book.records.notes) h += "<p class='hint'>" + esc(book.records.notes) + "</p>";
  box.innerHTML = h;
}

function renderEval() {
  var rows = window.EVAL_LIVE || [];
  if (!rows.length) return;
  el("evalLiveBody").innerHTML = rows.slice().reverse().map(function (r) {
    var t = r.created_at ? String(r.created_at).replace("T", " ").slice(0, 19) : "";
    return "<tr><td>" + esc(t) + "</td><td>" + esc(r.case) + "</td><td>" + r.steps + "/11</td><td>" + r.dropped + "</td><td>" + r.checks_passed + "/" + r.checks_total + "</td><td>" + esc((r.failed_checks || []).join(", ") || "none") + "</td></tr>";
  }).join("");
}
function renderReddit() {
  var feed = el("redditFeed");
  if (!feed) return;
  var current = MB.CASES.filter(function (c) { return c.case_id === MB.currentCase(); })[0];
  var docs = current ? current.documents.filter(function (d) { return d.type === "post" || d.type === "thread"; }) : [];
  if (!docs.length) {
    feed.innerHTML = '<p class="reddit-empty">No public posts in this file. The Reddit fills when a case has a public trail — work the Screens case to see it full.</p>';
    return;
  }
  feed.innerHTML = docs.map(function (d) {
    var h = 0; for (var i = 0; i < d.id.length; i++) h = (h * 31 + d.id.charCodeAt(i)) % 997;
    var votes = 40 + (h * 7) % 2200;
    var comments = 3 + h % 180;
    var sub = d.author.indexOf("r/") === 0 ? d.author : "r/SquadRoomSim";
    var user = d.author.indexOf("r/") === 0 ? "u/sim_desk" : d.author;
    return '<article class="reddit-card"><div class="reddit-rail"><span class="rv-up">\u25b2</span><span class="rv-count">' + votes + '</span><span class="rv-dn">\u25bc</span></div>' +
      '<div class="reddit-main"><div class="reddit-meta"><b>' + esc(sub) + '</b> \u00b7 Posted by ' + esc(user) + ' \u00b7 ' + esc(d.date) + ' \u00b7 <span class="reddit-doc">' + esc(d.id) + ' \u00b7 EVIDENCE</span></div>' +
      '<h3 class="reddit-title">' + esc(d.title) + '</h3><p class="reddit-body">' + esc(d.text) + '</p>' +
      '<div class="reddit-actions">' + comments + ' comments \u00b7 Share \u00b7 <button type="button" data-doc-id="' + esc(d.id) + '">Open in the evidence</button></div></div></article>';
  }).join("");
  Array.prototype.forEach.call(feed.querySelectorAll("button[data-doc-id]"), function (b) {
    b.addEventListener("click", function () { showScreen("intake"); openDocument(b.getAttribute("data-doc-id"), b); });
  });
}
function renderAll() { renderRegistry(); renderBoard(); renderClock(); renderJudgments(); renderBrief(); renderRecords(); renderEval(); renderReddit(); }

function showScreen(name) {
  Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
    t.classList.toggle("active", t.getAttribute("data-screen") === name);
  });
  Array.prototype.forEach.call(document.querySelectorAll(".screen"), function (s) {
    s.classList.toggle("active", s.id === "screen-" + name);
  });
  if (name === "board") scheduleYarn();
}

var AGENT_NAMES = {
  first_officer: "Mara Voss", records: "Elias Renn", coroner: "Dr. Ines Halden",
  csi: "Kojo Mensah", analyst: "Lucia Ibarra", digital: "Felix Quill",
  cross_examiner: "Adrian Vane", interviewer: "June Sorrel",
  prosecutor: "Petra Brandt", lead_detective: "Samuel Marrow"
};
function agentOf(chairId) { return AGENT_NAMES[chairId] || chairId; }
function chairIdByName(name) {
  var c = MB.CHAIRS.filter(function (x) { return x.name === name; })[0];
  return c ? c.id : null;
}
function modelOfChair(chairId) {
  var st = MB.STEPS.filter(function (x) { return x.chair === chairId; })[0];
  return st ? String(MB.modelFor(st)).replace("gemini-4-", "").toUpperCase() : "";
}
function trunc(t, n) { t = String(t == null ? "" : t); return t.length > n ? t.slice(0, n - 1) + "\u2026" : t; }

var STEP_ACTIVITY = {
  custody: "checking the document registry and custody lines",
  records: "checking the case's records leads",
  coroner: "setting the medical findings and death window",
  csi: "reconciling the evidence ledger",
  intake: "extracting people, claims, and events from the file",
  analyst: "placing events against the death window",
  digital: "checking records from phones and machines",
  cross_examiner: "testing claims against the documents",
  interviewer: "comparing statement changes",
  prosecutor: "stress testing the board for court",
  lead_detective: "ranking the next investigative steps"
};
function updateProgress() {
  var bar = el("runProgress"), label = el("runProgressLabel");
  if (!bar) return;
  var chairs = document.querySelectorAll("#squadStrip .chair");
  var total = chairs.length || 10, done = 0, failed = 0;
  for (var i = 0; i < chairs.length; i++) {
    if (chairs[i].classList.contains("done")) done++;
    if (chairs[i].classList.contains("failed")) failed++;
  }
  var pct = Math.round((done / total) * 100);
  bar.style.width = pct + "%";
  if (label) label.textContent = "SQUAD PROGRESS \u00b7 " + done + " of " + total + " chairs posted" + (failed ? " \u00b7 " + failed + " failed" : "") + " \u00b7 " + pct + "%";
  var q = el("runQueue");
  if (q) {
    var seen = {}, order = [];
    (MB.STEPS || []).forEach(function (st) { if (!seen[st.chair]) { seen[st.chair] = 1; order.push(st.chair); } });
    q.innerHTML = order.map(function (cid) {
      var ce = chairEls[cid];
      var st2 = ce ? (ce.classList.contains("done") ? "done" : ce.classList.contains("failed") ? "failed" : ce.classList.contains("running") ? "running" : "idle") : "idle";
      var label2 = agentOf(cid).replace("Dr. ", "").split(" ").pop();
      if (st2 === "done") return '<span class="q-done">\u2713 ' + esc(label2) + '</span>';
      if (st2 === "failed") return '<span class="q-failed">\u2717 ' + esc(label2) + '</span>';
      if (st2 === "running") return '<span class="q-running">\u25b8 ' + esc(label2) + ' \u00b7 ' + fmtClock(Date.now() - feedStart) + '</span>';
      return '<span class="q-idle">' + esc(label2) + '</span>';
    }).join(" \u00b7 ");
  }
  var rcEl = document.querySelector("#squadStrip .chair.running .count");
  if (rcEl) rcEl.textContent = "working " + fmtClock(Date.now() - feedStart);
}
var feedTimer = null, feedBase = "", feedStart = 0, runStart = 0;
var runTypingEl = null, lastTypingChair = null;
var typingPhraseTimer = null;
function fmtClock(ms) { var s = Math.floor(ms / 1000); return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2); }
function setFeedActivity(text) {
  var status = el("feedActivity");
  if (!status) return;
  feedBase = text;
  status.setAttribute("data-active", runInProgress ? "true" : "false");
  if (runInProgress) {
    if (!runStart) runStart = Date.now();
    feedStart = Date.now();
    status.textContent = text;
    if (!feedTimer) feedTimer = setInterval(function () {
      var st = el("feedActivity");
      if (st) st.textContent = feedBase + " \u00b7 " + fmtClock(Date.now() - feedStart);
      updateProgress();
      var runChair = document.querySelector("#squadStrip .chair.running");
      var runChairId = runChair ? runChair.id.replace("chair-", "") : null;
      if (runChairId !== lastTypingChair) {
        if (runTypingEl) { runTypingEl.remove(); runTypingEl = null; }
        if (typingPhraseTimer) { clearInterval(typingPhraseTimer); typingPhraseTimer = null; }
        if (runChairId) {
          runTypingEl = chatTyping(runChairId, STEP_ACTIVITY[activeStepId] || "reviewing the file");
          var phrases = [STEP_ACTIVITY[activeStepId] || "reviewing the file", "Gathering info", "Finding evidence", "Sifting through words", "Checking quotes against the file", "Cross-checking the statements"];
          var pi = 0;
          typingPhraseTimer = setInterval(function () {
            if (!runTypingEl) return;
            pi = (pi + 1) % phrases.length;
            var sp = runTypingEl.querySelector(".chat-text span");
            if (sp) sp.textContent = phrases[pi];
          }, 2200);
        }
        lastTypingChair = runChairId;
      }
    }, 1000);
  } else {
    updateProgress();
    if (runTypingEl) { runTypingEl.remove(); runTypingEl = null; }
    if (typingPhraseTimer) { clearInterval(typingPhraseTimer); typingPhraseTimer = null; }
    lastTypingChair = null;
    feedStart = 0;
    runStart = 0;
    if (feedTimer) { clearInterval(feedTimer); feedTimer = null; }
    status.textContent = text;
  }
}
function chatBubble(chairId, text, kind, extra) {
  var box = el("liveFeed");
  if (!box) return;
  extra = extra || {};
  var idle = box.querySelector(".feed-idle");
  if (idle) idle.remove();
  var d = document.createElement("div");
  var t = new Date().toLocaleTimeString([], { hour12: false });
  var sources = (extra.evidence || []).map(function (item) {
    return '<div class="chat-source"><button type="button" data-doc-id="' + esc(item.doc_id) + '">' + esc(item.doc_id + " · " + docTitle(item.doc_id)) + '</button><blockquote>' + esc(item.quote) + '</blockquote></div>';
  }).join("");
  var route = extra.recipients ? '<span class="chat-route">to ' + esc(extra.recipients.map(function (recipient) { return agentOf(recipient.chair) + " · " + chairNameOf(recipient.chair); }).join(", ") || "the squad room") + '</span>' : "";
  if (kind === "system" || kind === "runner") {
    d.className = "chat-line " + kind;
    d.innerHTML = '<span class="ft">' + t + '</span> ' + esc(text);
  } else if (kind === "summary") {
    d.className = "chat-line summary";
    d.innerHTML = '<div class="chat-head"><span class="chat-name">Board summary</span><span class="chat-role">Current board · no live model reply</span><span class="ft">' + t + "</span></div>" + '<div class="chat-text">' + esc(text) + "</div>" + sources;
  } else if (kind === "you") {
    d.className = "chat-line you";
    d.innerHTML = '<div class="chat-head"><span class="chat-name">You</span><span class="ft">' + t + '</span></div><div class="chat-text">' + esc(text) + "</div>";
  } else {
    d.className = "chat-line agent" + (kind === "fail" ? " fail" : "") + (kind === "note" ? " handoff" : "") + (chairId ? " agent-" + chairId : "");
    d.innerHTML = '<div class="chat-head">' + (kind === "note" ? '<span class="handoff-tag">HANDOFF</span>' : "") + '<span class="chat-name">' + esc(agentOf(chairId)) + '</span><span class="chat-role">' + esc(chairNameOf(chairId)) + " \u00b7 " + esc(modelOfChair(chairId)) + '</span>' + route + '<span class="ft">' + t + "</span></div>" +
      '<div class="chat-text">' + esc(text) + "</div>" + sources;
  }
  box.appendChild(d);
  Array.prototype.forEach.call(d.querySelectorAll(".chat-source button"), function (button) {
    button.addEventListener("click", function () { openDocument(button.getAttribute("data-doc-id"), button); });
  });
  while (box.children.length > 120) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
}
function chatTyping(chairId, text) {
  var box = el("liveFeed");
  if (!box) return null;
  var idle = box.querySelector(".feed-idle");
  if (idle) idle.remove();
  var d = document.createElement("div");
  d.className = "chat-line typing";
  d.innerHTML = '<div class="chat-head"><span class="chat-name">' + esc(agentOf(chairId)) + '</span><span class="chat-role">' + esc(chairNameOf(chairId)) + " \u00b7 " + esc(modelOfChair(chairId)) + '</span></div><div class="chat-text"><span>' + esc(text) + '</span><i class="typing-dots" aria-hidden="true"><b></b><b></b><b></b></i></div>';
  box.appendChild(d);
  box.scrollTop = box.scrollHeight;
  return d;
}
function chairNameOf(chairId) {
  var c = MB.CHAIRS.filter(function (x) { return x.id === chairId; })[0];
  return c ? c.name : chairId;
}
function feedLine(chair, text) {
  var cid = chairIdByName(chair);
  if (!cid) { chatBubble(null, text, chair === "Runner" ? "runner" : "system"); return; }
  var m;
  if ((m = String(text).match(/^(\S+): gemini-\S+ took the file$/))) {
    activeStepId = m[1];
    setFeedActivity(agentOf(cid) + " is " + (STEP_ACTIVITY[activeStepId] || "reviewing the file") + "…");
  } else if (/^\S+: posted \d+ finding/.test(String(text))) {
    setFeedActivity(agentOf(cid) + " posted a checked report to the squad room.");
  } else if ((m = String(text).match(/^(\S+): FAILED, (.*)$/))) {
    activeStepId = null;
    setFeedActivity(agentOf(cid) + " could not finish this step.");
    chatBubble(cid, "I couldn't finish this step: " + m[2], "fail");
  } else if ((m = String(text).match(/^\S+: (census answered.*)$/))) {
    setFeedActivity("Records is checking the bundled, labeled census fixture…");
  } else {
    chatBubble(cid, text);
  }
}
async function work() {
  if (runInProgress) {
    chatBubble("lead_detective", "The squad is already working this file. Ask me for a status update and I’ll tell you which step is active.");
    return;
  }
  if (!(window.MB_CONFIG && window.MB_CONFIG.apiKey)) {
    setFeedActivity("Live work needs a Gemini API key.");
    chatBubble("lead_detective", "I need a Gemini API key to work the file live. Paste it in the top bar, then start the case.");
    return;
  }
  runInProgress = true;
  el("workBtn").disabled = true;
  el("caseSelect").disabled = true;
  MB.CHAIRS.forEach(function (c) { setChair(c.id, "idle", null); });
  activeStepId = null;
  book = MB.newBook();
  renderAll();
  setFeedActivity("Live run: waiting for the first agent result.");
  chatBubble(null, "Run opened: " + caseShortTitle(MB.currentCase()) + ". Ten chairs, four models.", "system");
  var runT0 = performance.now();
  var runTimer = null;
  (function tickClock() {
    var ms = performance.now() - runT0;
    var m = Math.floor(ms / 60000), s2 = Math.floor(ms / 1000) % 60;
    var us = ("000000" + Math.floor((ms % 1000) * 1000)).slice(-6);
    var rc = el("runClock");
    if (rc) rc.textContent = m + ":" + ("0" + s2).slice(-2) + "." + us;
    runTimer = requestAnimationFrame(tickClock);
  })();
  el("dropChip").classList.add("hidden");
  var hooks = {
    chair: setChair,
    status: function (s) {
      el("runStatus").textContent = s;
      if (s.indexOf("Working: ") === 0) {
        activeStepId = s.slice(9).replace(/ /g, "_");
        var st = MB.STEPS.filter(function (x) { return x.id === activeStepId; })[0];
        if (st) setFeedActivity(agentOf(st.chair) + " is " + (STEP_ACTIVITY[activeStepId] || "reviewing the file") + "…");
      }
    },
    event: feedLine,
    note: function (step, note, recipients) {
      activeStepId = null;
      chatBubble(step.chair, note.message, "note", { evidence: note.evidence, recipients: recipients });
    },
    step: function (b) { book = b; renderAll();
      if (b.dropped > 0) { var dc = el("dropChip"); dc.textContent = "Quote check dropped: " + b.dropped; dc.classList.remove("hidden"); } },
    pause: function () { if (window.__mbAbort) throw new Error("run stopped by the detective"); return new Promise(function (r) { setTimeout(r, 700); }); }
  };
  var door2 = null;
  var d2name = el("door2Name");
  if (d2name && d2name.value.trim()) {
    door2 = { name: d2name.value.trim(), dob: el("door2Dob").value.trim(), state: el("door2State").value.trim() };
  }
  try {
    book = await MB.runAll(hooks, { door2: door2 });
  } catch (error) {
    el("runStatus").textContent = "Run stopped: " + (error && error.message ? error.message : String(error));
    chatBubble("lead_detective", "The runner stopped before the case was complete: " + (error && error.message ? error.message : String(error)), "fail");
  } finally {
    cancelAnimationFrame(runTimer);
    runInProgress = false;
    activeStepId = null;
    renderAll();
    el("workBtn").disabled = false;
    el("caseSelect").disabled = false;
    setFeedActivity(book.failed_steps.length ? "Run complete with a failed step. Check the run status above." : "Run complete. Ask about the findings or open the board, clock, judgments, or brief.");
  }
}

function answerChair(question) {
  var q = question.toLowerCase();
  if (/\b(death|medical|coroner|wound|cause of death|manner of death)\b/.test(q)) return "coroner";
  if (/\b(ledger|evidence|casing|shell|scene item|physical evidence)\b/.test(q)) return "csi";
  if (/\b(timeline|chronology|when did|where was|time window|clock)\b/.test(q)) return "analyst";
  if (/\b(alibi|contradict|conflict|innocent alternative)\b/.test(q)) return "cross_examiner";
  if (/\b(statement|interview|what changed|next question)\b/.test(q)) return "interviewer";
  if (/\b(court|prosecutor|sufficien|overclaim)\b/.test(q)) return "prosecutor";
  if (/\b(census|record|alias|same name|identity)\b/.test(q)) return "records";
  if (/\b(phone|camera|machine|call log|digital)\b/.test(q)) return "digital";
  return "lead_detective";
}

async function answerQuestion(question) {
  var chairId = answerChair(question);
  if (!(window.MB_CONFIG && window.MB_CONFIG.apiKey)) {
    chatBubble(null, "Add a Gemini API key in the top bar for a live answer.", "system");
    return;
  }
  if (questionInProgress) {
    chatBubble(null, "A live answer is still in progress. Try again in a moment.", "system");
    return;
  }
  questionInProgress = true;
  var typing = chatTyping(chairId, "Checking the current board and case documents");
  setFeedActivity(agentOf(chairId) + " is checking your question against the file…");
  try {
    var answer = await MB.askAgent(chairId, question, book, activeStepId);
    if (typing && typing.parentNode) typing.parentNode.removeChild(typing);
    chatBubble(chairId, answer.reply, null, { evidence: answer.evidence });
  } catch (error) {
    if (typing && typing.parentNode) typing.parentNode.removeChild(typing);
    chatBubble(null, "The live answer could not be verified: " + (error && error.message ? error.message : String(error)), "system");
  } finally {
    questionInProgress = false;
    setFeedActivity(runInProgress ? "The squad is still working. You can ask another question." : "Ask about the findings or open the board, clock, judgments, or brief.");
  }
}

function sendChat() {
  var inp = el("chatText");
  var text = (inp.value || "").trim();
  if (!text) return;
  inp.value = "";
  chatBubble(null, text, "you");
  var low = text.toLowerCase();
  var asksStatus = /\b(what(?:'s|s| is) going on|what(?:'s|s| is) happening|status|update|where are we|what have you found|how(?:'s|s| is) the case going)\b/.test(low);
  var caseHit = null;
  if (/delgado/.test(low)) caseHit = "delgado-2019";
  else if (/screens|trey/.test(low)) caseHit = "screens-2025";
  else if (/harborlight|marsh/.test(low)) caseHit = "harborlight-2016";
  else if (/starlite|ibanez|bowling|lanes/.test(low)) caseHit = "starlite-2017";
  var sel = el("caseSelect");
  if (runInProgress && caseHit && caseHit !== MB.currentCase()) {
    chatBubble("lead_detective", "The squad is working " + caseShortTitle(MB.currentCase()) + " now. I’ll finish this file before switching cases.");
    return;
  }
  if (caseHit && sel.value !== caseHit) {
    sel.value = caseHit;
    sel.dispatchEvent(new Event("change"));
    if (!/^(work|run|start|go)\b/.test(low)) {
      answerQuestion(text);
      return;
    }
    work();
    return;
  }
  if (/^(work|run|start|go)\b/.test(low)) { work(); return; }
  if (asksStatus) { answerQuestion(text); return; }
  var screens = { board: "board", clock: "clock", judgment: "judgments", brief: "brief", intake: "intake", file: "intake", eval: "eval", reddit: "reddit" };
  var hit = Object.keys(screens).filter(function (k) { return low.indexOf(k) !== -1; })[0];
  var wantsScreen = /^(show|open|take me|go to|pull up|bring up|see)\b/.test(low) || low.split(/\s+/).length <= 3;
  if (hit && wantsScreen) {
    showScreen(screens[hit]);
    chatBubble("lead_detective", screens[hit] === "board" ? "Board's up." : screens[hit] === "brief" ? "Brief's on the screen." : "On the screen.");
    return;
  }
  answerQuestion(text);
}

document.addEventListener("DOMContentLoaded", function () {
  buildStrip();
  var lk = el("liveKey");
  lk.addEventListener("input", function () {
    var v = lk.value.trim();
    if (v) {
      window.MB_CONFIG = { reasoningModel: "gemini-4-argon", fastModel: "gemini-4-carbon", worldModel: "gemini-4-hydrogen", fieldModel: "gemini-4-neon", apiKey: v };
      el("liveDot").classList.remove("hidden");
    } else {
      window.MB_CONFIG = undefined;
      el("liveDot").classList.add("hidden");
    }
  });
  el("chatSend").addEventListener("click", sendChat);
  el("chatText").addEventListener("keydown", function (e) { if (e.key === "Enter") sendChat(); });
  Array.prototype.forEach.call(document.querySelectorAll(".chip"), function (ch) {
    ch.addEventListener("click", function () { el("chatText").value = ch.getAttribute("data-say"); sendChat(); });
  });
  var sel = el("caseSelect");
  MB.CASES.forEach(function (c) {
    var o = document.createElement("option");
    var labels = { "delgado-2019": "The Delgado File (police file)", "screens-2025": "The Screens File (internet case)", "harborlight-2016": "The Harborlight File (the sim)", "starlite-2017": "The Starlite File (cold case)" };
    o.value = c.case_id; o.textContent = labels[c.case_id] || c.case_id;
    sel.appendChild(o);
  });
  sel.addEventListener("change", function () {
    if (!el("quoteModal").hidden) closeQuotePanel();
    if (!el("profileDrawer").hidden) closeProfile();
    MB.setCase(sel.value);
    book = MB.newBook();
    MB.CHAIRS.forEach(function (c) { setChair(c.id, "idle", null); });
    el("docViewer").textContent = "";
    renderCaseFolder();
    renderRegistry();
    renderAll();
  });
  renderRegistry();
  renderCaseFolder();
  Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
    t.addEventListener("click", function () { showScreen(t.getAttribute("data-screen")); });
  });
  el("workBtn").addEventListener("click", work);
  el("stopBtn").addEventListener("click", function () { window.__mbAbort = true; setTimeout(function () { location.reload(); }, 250); });
  el("modalClose").addEventListener("click", closeQuotePanel);
  el("profileClose").addEventListener("click", closeProfile);
  el("profileBackdrop").addEventListener("click", closeProfile);
  el("quoteModal").addEventListener("click", function (event) { if (event.target === el("quoteModal")) closeQuotePanel(); });
  function keepDialogFocus(event, dialog, close) {
    if (event.key === "Escape") { event.preventDefault(); close(); return; }
    if (event.key !== "Tab") return;
    var focusable = Array.prototype.slice.call(dialog.querySelectorAll("button:not([disabled]), a[href], summary, input:not([disabled]), [tabindex]:not([tabindex='-1'])"));
    if (!focusable.length) { event.preventDefault(); dialog.focus(); return; }
    var first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  }
  el("quoteModal").addEventListener("keydown", function (event) { keepDialogFocus(event, el("modal-card"), closeQuotePanel); });
  el("profileDrawer").addEventListener("keydown", function (event) { keepDialogFocus(event, el("profileDrawer"), closeProfile); });
  el("printBtn").addEventListener("click", function () { window.print(); });
  el("vetoToggle").addEventListener("change", renderBrief);
  window.addEventListener("resize", function () { scheduleYarn(); });
});
})();
