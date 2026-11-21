#!/usr/bin/env node
// Live pipeline harness: runs the app's own runner in Node, with the
// Gemini transport routed through the connector helper (the API key
// never enters this process; the helper carries a surrogate).
// Writes the fallback cache: cache/delgado-2019.json and
// app/cache-data.js. Run from the repo root: node tools/run_live.js
"use strict";
const { spawnSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const ROOT = path.dirname(__dirname);
global.window = global;
require(path.join(ROOT, "app", "case-data.js"));
require(path.join(ROOT, "app", "agents-data.js"));
const CASE_ID = process.env.MB_CASE_ID || "delgado-2019";
const chosen = (global.CASES || []).filter((c) => c.case_id === CASE_ID)[0];
if (!chosen) { console.error("unknown case", CASE_ID); process.exit(1); }
global.CASES = [chosen];
global.CASE_DOCS = chosen.documents;
global.MB_CONFIG = { apiKey: "", reasoningModel: "gemini-4-argon", fastModel: "gemini-4-carbon", worldModel: "gemini-4-hydrogen", fieldModel: "gemini-4-neon" };

const HELPER = path.join(process.env.HOME, "workspace/custom-connectors/custom.gemini-api/bin/gemini_api.py");

global.__MB_TRANSPORT = function (model, systemText, userText) {
  const payload = JSON.stringify({
    systemInstruction: { parts: [{ text: systemText }] },
    contents: [{ parts: [{ text: userText }] }],
    generationConfig: { responseMimeType: "application/json", temperature: 0.2, maxOutputTokens: 16384 }
  });
  const r = spawnSync("python3", [HELPER, "generate", model], { input: payload, maxBuffer: 16 * 1024 * 1024, timeout: 300000 });
  if (r.status !== 0) throw new Error("helper failed for " + model + ": " + String(r.stderr || r.stdout).slice(0, 300));
  const data = JSON.parse(r.stdout);
  const parts = (data.candidates && data.candidates[0] && data.candidates[0].content.parts) || [];
  return parts.map((p) => p.text || "").join("");
};

const MB = require(path.join(ROOT, "app", "app.js"));

(async () => {
  const t0 = Date.now();
  const book = await MB.runAll({
    chair: (id, state, count) => console.log("chair", id, state, count == null ? "" : count),
    status: (s) => console.log("status", s)
  }, null);
  const secs = ((Date.now() - t0) / 1000).toFixed(0);
  console.log("=== RUN DONE in " + secs + "s ===");
  console.log("failed steps:", JSON.stringify(book.failed_steps));
  console.log("dropped by quote check:", book.dropped);
  console.log("contradictions:", book.contradictions.map((c) => c.severity + " " + c.a_doc + "v" + c.b_doc).join(" | "));
  console.log("alibis:", book.alibis.map((a) => a.person + "=" + a.rating).join(" | "));
  console.log("csi gaps:", book.csi_gaps.length, "| ce gaps:", book.ce_gaps.length);
  console.log("leads:", book.leads.map((l) => l.score + " " + l.action).join(" | "));
  console.log("log:", book.log.join(" ; "));
  const cache = { created_at: new Date().toISOString(), outputs: book.outputs, dropped: book.dropped, run_log: book.log };
  fs.mkdirSync(path.join(ROOT, "cache"), { recursive: true });
  fs.writeFileSync(path.join(ROOT, "cache", CASE_ID + ".json"), JSON.stringify(cache, null, 1));
  console.log("cache written: cache/" + CASE_ID + ".json (run tools/merge_cache.py next)");
})().catch((e) => { console.error("HARNESS ERROR", e); process.exit(1); });
