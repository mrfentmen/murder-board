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
    dropped: 0, log: [], outputs: {}, failed_steps: []
  };
}

// Records simulation: the Door 2 census, run against bundled
// fixtures for the fictional cases. Deterministic, no model call,
// no outside lookup. Quotes are checked against the fixture text
// itself, the same law as the case file: no quote, no item.
var FIXTURES = G.RECORDS_FIXTURES || [];
function normName(s) { return String(s || "").toLowerCase().replace(/\s+/g, " ").trim(); }
function findFixture(name) {
  var n = normName(name);
  if (!n) return null;
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
    request_next: ["Live census sources are off in this simulation build."],
    notes: "Simulation census for " + fx.subject.name + ": pulled from the bundled fixtures for this fictional case, not from live sources."
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
    input: function () { return "THE REGISTRY:\n" + registryText(); },
    apply: function (b, o) { b.records = o; } },
  { id: "coroner", chair: "coroner", file: "03_coroner.md", model: "fast",
    required: ["cause", "manner", "death_window"],
    input: function () { return docsText(["doc01", "doc02"]); },
    apply: function (b, o) { b.coroner = o; } },
  { id: "csi", chair: "csi", file: "04_csi.md", model: "fast",
    required: ["ledger", "gaps"],
    input: function () { return docsText(); },
    apply: function (b, o) { b.ledger = o.ledger || []; b.csi_gaps = o.gaps || []; } },
  { id: "intake", chair: "first_officer", file: "05_intake.md", model: "fast",
    required: ["persons", "claims", "events"],
    input: function () { return docsText(); },
    apply: function (b, o) {
      b.persons = o.persons || []; b.claims = o.claims || [];
      b.intake_events = o.events || []; b.evidence_items = o.evidence_items || [];
    } },
  { id: "analyst", chair: "analyst", file: "06_analyst.md", model: "world",
    required: ["events"],
    input: function (b) {
      return "INTAKE OUTPUT:\n" + JSON.stringify({ events: b.intake_events, claims: b.claims }, null, 1)
        + "\n\nDEATH WINDOW:\n" + JSON.stringify(b.coroner ? b.coroner.death_window : {}, null, 1);
    },
    apply: function (b, o) { b.timeline = o.events || []; b.collisions = o.collisions || []; } },
  { id: "digital", chair: "digital", file: "07_digital.md", model: "field",
    required: ["machine_events"],
    input: function () { return docsText(); },
    apply: function (b, o) { b.machine = o; } },
  { id: "cross_examiner", chair: "cross_examiner", file: "08_cross_examiner.md", model: "reasoning",
    required: ["contradictions", "alibis"],
    input: function (b) {
      return "THE DOCUMENTS:\n" + docsText()
        + "\n\nINTAKE CLAIMS:\n" + JSON.stringify(b.claims, null, 1)
        + "\n\nDEATH WINDOW:\n" + JSON.stringify(b.coroner ? b.coroner.death_window : {}, null, 1);
    },
    apply: function (b, o) {
      b.contradictions = o.contradictions || []; b.alibis = o.alibis || []; b.ce_gaps = o.evidence_gaps || [];
    } },
  { id: "interviewer", chair: "interviewer", file: "09_interviewer.md", model: "fast",
    required: ["histories", "next_questions"],
    input: function (b) {
      return "THE STATEMENTS:\n" + docsText(["doc03", "doc04", "doc05", "doc06", "doc07", "doc08", "doc09", "doc10"])
        + "\n\nCONTRADICTIONS FOUND:\n" + JSON.stringify(b.contradictions, null, 1);
    },
    apply: function (b, o) { b.histories = o.histories || []; b.next_questions = o.next_questions || []; } },
  { id: "prosecutor", chair: "prosecutor", file: "10_prosecutor.md", model: "fast",
    required: ["sufficiency", "vetoes"],
    input: function (b) {
      return "THE BOARD:\n" + JSON.stringify({
        contradictions: b.contradictions, alibis: b.alibis,
        csi_gaps: b.csi_gaps, ce_gaps: b.ce_gaps, collisions: b.collisions
      }, null, 1);
    },
    apply: function (b, o) {
      b.sufficiency = o.sufficiency || []; b.vetoes = o.vetoes || [];
      b.corroboration_needed = o.corroboration_needed || [];
    } },
  { id: "lead_detective", chair: "lead_detective", file: "11_lead_detective.md", model: "reasoning",
    required: ["leads", "gaps", "brief"],
    input: function (b) {
      return "THE BOARD:\n" + JSON.stringify({
        coroner: b.coroner ? { cause: b.coroner.cause, manner: b.coroner.manner, death_window: b.coroner.death_window } : null,
        contradictions: b.contradictions, alibis: b.alibis,
        csi_gaps: b.csi_gaps, ce_gaps: b.ce_gaps, collisions: b.collisions,
        timeline: b.timeline, sufficiency: b.sufficiency
      }, null, 1);
    },
    apply: function (b, o) { b.leads = o.leads || []; b.gaps = o.gaps || []; b.brief = o.brief || ""; } }
];

function countFindings(o) {
  var n = 0;
  Object.keys(o || {}).forEach(function (k) { if (Array.isArray(o[k])) n += o[k].length; });
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
  return errs;
}

// ---------- the runner ----------
async function runStep(step, book, hooks, cachedOutputs) {
  hooks.chair(step.chair, "running", null);
  try {
    var output;
    if (step.id === "records" && book.door2 && book.door2.name && findFixture(book.door2.name)) {
      // The census is a pull, not a judgment: when the Door 2 name
      // matches a bundled fixture, the sim answers from the fixture
      // — ahead of both the cache and the model.
      output = buildRecordsFromFixture(findFixture(book.door2.name));
      var ferrs = schemaErrors(step, output);
      if (ferrs.length) throw new Error("fixture schema: " + ferrs.join("; "));
      if (hooks.delay) await hooks.delay();
    } else if (cachedOutputs && cachedOutputs[step.id]) {
      output = cachedOutputs[step.id];
      if (hooks.delay) await hooks.delay();
    } else {
      var model = modelNameFor(step);
      var prompt = PROMPTS[step.file];
      if (!prompt) throw new Error("prompt file missing: " + step.file);
      var userText = step.input(book);
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
    book.dropped += drop.n;
    if (drop.n) book.log.push(step.id + ": " + drop.n + " finding(s) dropped by the quote check");
    step.apply(book, output);
    book.outputs[step.id] = output;
    hooks.chair(step.chair, "done", countFindings(output));
    return true;
  } catch (e) {
    book.failed_steps.push(step.id + ": " + (e && e.message ? e.message : String(e)));
    hooks.chair(step.chair, "failed", null);
    return false;
  }
}

async function runAll(hooks, cachedOutputs, opts) {
  var book = newBook();
  if (opts && opts.door2) book.door2 = opts.door2;
  hooks = hooks || {};
  hooks.chair = hooks.chair || function () {};
  hooks.status = hooks.status || function () {};
  for (var i = 0; i < STEPS.length; i++) {
    hooks.status("Working: " + STEPS[i].id.replace(/_/g, " "));
    await runStep(STEPS[i], book, hooks, cachedOutputs);
  }
  hooks.status(book.failed_steps.length ? "Done, with failed steps: " + book.failed_steps.join("; ") : "Done");
  return book;
}

G.MB = {
  runAll: runAll, newBook: newBook, recomputeScore: recomputeScore, modelFor: modelNameFor,
  quoteOk: quoteOk, VALIDATORS: VALIDATORS, STEPS: STEPS, CHAIRS: CHAIRS,
  DOC_BY_ID: DOC_BY_ID, CASES: CASES, setCase: setCase,
  findFixture: findFixture, buildRecordsFromFixture: buildRecordsFromFixture,
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

function buildStrip() {
  var strip = el("squadStrip");
  strip.innerHTML = "";
  MB.CHAIRS.forEach(function (c) {
    var d = document.createElement("div");
    d.className = "chair"; d.id = "chair-" + c.id;
    var st = MB.STEPS.filter(function (x) { return x.chair === c.id; })[0];
    var mn = st ? String(MB.modelFor(st)).replace("gemini-4-", "").toUpperCase() : "";
    d.innerHTML = esc(c.name) + '<span class="model">' + esc(mn) + '</span><span class="count"></span>';
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
}

function renderRegistry() {
  var current = MB.CASES.filter(function (c) { return c.case_id === MB.currentCase(); })[0];
  el("caseTitle").textContent = current ? current.case_title : "";
  var docs = current ? current.documents : [];
  el("registryBody").innerHTML = docs.map(function (d) {
    return "<tr data-doc='" + d.id + "'><td>" + d.id + "</td><td>" + esc(d.title) + "</td><td>" + esc(d.type) + "</td><td>" + esc(d.date) + "</td><td>" + esc(d.author) + "</td><td>view</td></tr>";
  }).join("");
  Array.prototype.forEach.call(document.querySelectorAll("#registryBody tr"), function (tr) {
    tr.addEventListener("click", function () {
      var d = MB.docById(tr.getAttribute("data-doc"));
      el("docViewer").textContent = d ? d.text : "";
    });
  });
}

function tiltFor(seed) {
  var h = 0;
  for (var i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 997;
  return ((h % 5) - 2) * 1.1;
}
function pinCard(cls, pinKey, inner, seed) {
  var t = tiltFor(seed || pinKey);
  return '<div class="' + cls + '" data-pin="' + esc(pinKey) + '" data-tilt="' + t + '" style="transform: rotate(' + t + 'deg)">' + inner + '</div>';
}
function photoHtml(name) {
  var map = (window.PERSON_PHOTOS || {})[MB.currentCase()] || {};
  var key = String(name || "").toLowerCase().replace(/[^a-z ]/g, "").replace(/\s+/g, " ").trim();
  var src = map[key];
  if (!src) { // surname fallback when the file uses a fuller or shorter name
    var sur = key.split(" ").pop();
    for (var k in map) { if (k.split(" ").pop() === sur) { src = map[k]; break; } }
  }
  if (src) return '<img class="photo" src="' + src + '" alt="">';
  return '<div class="photo">' + esc(initialsOf(name)) + '</div>';
}

function initialsOf(name) {
  return String(name).replace(/["']/g, "").split(/\s+/).map(function (w) { return w.charAt(0); }).join("").slice(0, 2).toUpperCase();
}
function renderBoard() {
  var layer = el("pinLayer");
  if (!layer) return;
  var current = MB.CASES.filter(function (c) { return c.case_id === MB.currentCase(); })[0];
  var docs = current ? current.documents : [];
  var html = '<div class="pin-title" data-pin="title" data-tilt="0" id="caseQuestion" title="The question before the board"><div class="qmark">?</div><div class="who">WHO DID IT</div><div class="case-name">' + esc(current ? current.case_title : "") + '</div></div>';
  html += book.persons.map(function (p) {
    var claims = book.claims.filter(function (c) { return c.person === p.name; });
    var isVictim = /victim/i.test(p.role || "");
    var alibi = book.alibis.filter(function (a) { return a.person === p.name; })[0];
    return pinCard("pin-card person" + (isVictim ? " victim" : ""), "person:" + p.name,
      photoHtml(p.name) + '<h4>' + esc(p.name) + '</h4><p class="role">' + esc(p.role) + '</p>' +
      (alibi ? '<p class="alibi-chip rate-' + esc(String(alibi.rating).toLowerCase().replace(/\s+/g, "-")) + '">' + esc(alibi.rating) + '</p>' : "") +
      claims.slice(0, 2).map(function (c) { return '<p class="q">&ldquo;' + esc(c.quote) + '&rdquo;</p>'; }).join(""),
      p.name);
  }).join("");
  html += docs.map(function (d) {
    return pinCard("pin-card docslip", "doc:" + d.id,
      '<h5>' + esc(d.id) + ' &middot; ' + esc(d.type) + '</h5><p>' + esc(d.title) + '</p><p class="role">' + esc(d.date) + ' &middot; ' + esc(d.author) + '</p>', d.id);
  }).join("");
  var items = book.ledger.length ? book.ledger : book.evidence_items;
  html += items.slice(0, 8).map(function (it, i) {
    return pinCard("pin-card evidence", "ev:" + i,
      '<h5>' + esc(it.item_no ? "Item " + it.item_no : "Item") + '</h5><p>' + esc(it.description || "") + '</p>', "ev" + i);
  }).join("");
  var gaps = book.csi_gaps.concat(book.ce_gaps);
  html += gaps.slice(0, 6).map(function (g, i) {
    return pinCard("pin-note", "gap:" + i,
      '<p class="note-q">' + esc(g.item) + '</p><p>' + esc(g.problem) + '</p>', "gap" + i);
  }).join("");
  html += legendHtml();
  layer.innerHTML = html;
  var qc = el("caseQuestion");
  if (qc) qc.addEventListener("click", openCaseQuestion);
  var threads = book.contradictions.map(function (c, i) {
    return '<button class="thread red" data-kind="contra" data-idx="' + i + '"><span class="sev sev-' + esc(c.severity) + '">' + esc(c.severity) + '</span>' + esc(c.kind) + ": " + esc(c.a_doc) + " vs " + esc(c.b_doc) + "</button>";
  });
  threads = threads.concat(book.collisions.map(function (c, i) {
    return '<button class="thread" data-kind="collision" data-idx="' + i + '">Collision: ' + esc(c.who_or_what) + "</button>";
  }));
  el("threadList").innerHTML = threads.join("") || '<p class="hint">No threads yet.</p>';
  Array.prototype.forEach.call(document.querySelectorAll(".thread"), function (t) {
    t.addEventListener("click", function () { openThread(t.getAttribute("data-kind"), +t.getAttribute("data-idx")); });
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
  book.persons.forEach(function (p) { out += yarn(pts.title, pts["person:" + p.name], "yarn-gray", "", ""); });
  book.contradictions.forEach(function (c, i) {
    out += yarn(pts["doc:" + c.a_doc], pts["doc:" + c.b_doc], "yarn-" + String(c.severity).toLowerCase(), "contra", i);
  });
  book.collisions.forEach(function (c, i) {
    var ds = [];
    (c.quotes || []).forEach(function (q) { if (ds.indexOf(q.doc_id) < 0) ds.push(q.doc_id); });
    if (ds.length >= 2) out += yarn(pts["doc:" + ds[0]], pts["doc:" + ds[1]], "yarn-collision", "collision", i);
  });
  svg.innerHTML = out;
  Array.prototype.forEach.call(svg.querySelectorAll(".yarn-hit"), function (p) {
    p.addEventListener("click", function () { openThread(p.getAttribute("data-kind"), +p.getAttribute("data-idx")); });
  });
}

function legendHtml() {
  function row(cls, label) {
    return '<div class="key-row"><svg class="key-line" viewBox="0 0 40 8" preserveAspectRatio="none"><path class="yarn-line ' + cls + '" d="M1 4 Q 20 9 39 4"/></svg><span>' + label + "</span></div>";
  }
  return '<div class="pin-legend"><div class="key-title">STRING KEY</div>' +
    row("yarn-gray", "On the board: a person pinned to the question") +
    row("yarn-high", "Contradiction, high: two documents that cannot both be true") +
    row("yarn-medium", "Contradiction, medium") +
    row("yarn-low", "Contradiction, low") +
    row("yarn-collision", "Timeline collision: two events that clash") +
    '<div class="key-note">Tap a colored string to read the two quotes it joins.</div></div>';
}

function openCaseQuestion() {
  var current = MB.CASES.filter(function (c) { return c.case_id === MB.currentCase(); })[0];
  var victim = book.persons.filter(function (p) { return /victim/i.test(p.role || ""); })[0];
  var question = victim ? "Who killed " + victim.name + "?" : "Who did it?";
  el("modalTitle").textContent = "The question before the board";
  el("quoteA").textContent = question;
  el("quoteACite").textContent = current ? current.case_title : "";
  var win = "";
  if (book.coroner && book.coroner.death_window) win = "Death window: " + book.coroner.death_window.start + " to " + book.coroner.death_window.end + ".";
  el("quoteB").textContent = win;
  el("quoteBCite").textContent = win ? "The Coroner's window, from the file" : "";
  el("modalAlt").textContent = "This board judges the file. The detective does the detecting.";
  el("quoteModal").classList.remove("hidden");
}

function openThread(kind, idx) {
  var title, qa, qb, alt = "";
  if (kind === "contra") {
    var c = book.contradictions[idx];
    title = "Contradiction: " + c.kind + " (" + c.severity + ")";
    qa = { q: c.a_quote, cite: docTitle(c.a_doc) };
    qb = { q: c.b_quote, cite: docTitle(c.b_doc) };
    alt = "The innocent reading: " + c.innocent_alternative;
  } else {
    var col = book.collisions[idx];
    title = "Collision: " + col.who_or_what;
    qa = { q: col.quotes[0] ? col.quotes[0].quote : "", cite: col.quotes[0] ? docTitle(col.quotes[0].doc_id) : "" };
    qb = { q: col.quotes[1] ? col.quotes[1].quote : "", cite: col.quotes[1] ? docTitle(col.quotes[1].doc_id) : "" };
    alt = col.explanation;
  }
  el("modalTitle").textContent = title;
  el("quoteA").textContent = qa.q; el("quoteACite").textContent = qa.cite;
  el("quoteB").textContent = qb.q; el("quoteBCite").textContent = qb.cite;
  el("modalAlt").textContent = alt;
  el("quoteModal").classList.remove("hidden");
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
  "duck-2020": { no: "MB-2020-0804", victim: "Carlton Weekly, 26", window: "Tue Aug 4, 2020, about 4:26 PM", place: "East Oak Street, Gold Coast, Chicago", stamp: "SOLVED 2024", stampCls: "stamp-solved" }
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

function renderAll() { renderBoard(); renderClock(); renderJudgments(); renderBrief(); renderRecords(); }

function showScreen(name) {
  Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
    t.classList.toggle("active", t.getAttribute("data-screen") === name);
  });
  Array.prototype.forEach.call(document.querySelectorAll(".screen"), function (s) {
    s.classList.toggle("active", s.id === "screen-" + name);
  });
  if (name === "board") scheduleYarn();
}

function cacheForCurrentCase() {
  return (window.CACHE_BY_CASE || {})[MB.currentCase()] || null;
}
function updateCacheAvailability() {
  var c = cacheForCurrentCase();
  el("cacheToggle").disabled = !c;
  el("cacheLabel").textContent = c ? "" : "no cached run saved for this case yet";
}

async function work() {
  var cached = cacheForCurrentCase();
  var useCache = el("cacheToggle").checked && cached;
  el("workBtn").disabled = true;
  MB.CHAIRS.forEach(function (c) { setChair(c.id, "idle", null); });
  var hooks = {
    chair: setChair,
    status: function (s) { el("runStatus").textContent = s; },
    delay: function () { return new Promise(function (r) { setTimeout(r, 650); }); }
  };
  var door2 = null;
  var d2name = el("door2Name");
  if (d2name && d2name.value.trim()) {
    door2 = { name: d2name.value.trim(), dob: el("door2Dob").value.trim(), state: el("door2State").value.trim() };
  }
  if (useCache) {
    var when = cached.created_at ? new Date(cached.created_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "this morning";
    el("cacheLabel").textContent = "cached run from " + when;
    book = await MB.runAll(hooks, cached.outputs, { door2: door2 });
    if (cached.dropped) book.dropped = cached.dropped;
  } else {
    el("cacheLabel").textContent = "";
    if (!(window.MB_CONFIG && window.MB_CONFIG.apiKey)) {
      el("runStatus").textContent = "No API key in config.js. Copy config.example.js to config.js and add the key.";
      el("workBtn").disabled = false;
      return;
    }
    book = await MB.runAll(hooks, null, { door2: door2 });
  }
  renderAll();
  el("workBtn").disabled = false;
}

document.addEventListener("DOMContentLoaded", function () {
  buildStrip();
  var sel = el("caseSelect");
  MB.CASES.forEach(function (c) {
    var o = document.createElement("option");
    var labels = { "delgado-2019": "The Delgado File (police file)", "screens-2025": "The Screens File (internet case)", "harborlight-2016": "The Harborlight File (the sim)", "duck-2020": "The Duck File (real case, public record)" };
    o.value = c.case_id; o.textContent = labels[c.case_id] || c.case_id;
    sel.appendChild(o);
  });
  sel.addEventListener("change", function () {
    MB.setCase(sel.value);
    book = MB.newBook();
    MB.CHAIRS.forEach(function (c) { setChair(c.id, "idle", null); });
    el("docViewer").textContent = "";
    renderCaseFolder();
    renderRegistry();
    renderAll();
    updateCacheAvailability();
    if (cacheForCurrentCase()) { el("cacheToggle").checked = true; work(); }
  });
  renderRegistry();
  renderCaseFolder();
  Array.prototype.forEach.call(document.querySelectorAll(".tab"), function (t) {
    t.addEventListener("click", function () { showScreen(t.getAttribute("data-screen")); });
  });
  el("workBtn").addEventListener("click", work);
  el("modalClose").addEventListener("click", function () { el("quoteModal").classList.add("hidden"); });
  el("printBtn").addEventListener("click", function () { window.print(); });
  el("vetoToggle").addEventListener("change", renderBrief);
  window.addEventListener("resize", function () { scheduleYarn(); });
  updateCacheAvailability();
  if (cacheForCurrentCase()) { el("cacheToggle").checked = true; work(); }
});
})();
