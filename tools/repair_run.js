#!/usr/bin/env node
// Refresh a run archive with a complete live run. The app does not load it.
// Run from the repo root: node tools/repair_run.js
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
  const book = await MB.runAll({ chair: () => {}, status: (s) => console.log("status", s) });
  console.log("failed steps:", JSON.stringify(book.failed_steps));
  console.log("leads:", book.leads.map((l) => l.score + " " + l.action).join(" | "));
  console.log("gaps order (csi):", book.csi_gaps.slice(0, 3).map((g) => g.item).join(" | "));
  console.log("brief chars:", book.brief.length);
  console.log("log:", book.log.join(" ; "));
  const out = { created_at: new Date().toISOString(), outputs: book.outputs, dropped: book.dropped, run_log: book.log };
  fs.writeFileSync(path.join(ROOT, "cache", CASE_ID + ".json"), JSON.stringify(out, null, 1));
  console.log("live-run archive written with", Object.keys(book.outputs).length, "steps");
})().catch((e) => { console.error("REPAIR ERROR", e); process.exit(1); });
