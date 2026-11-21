// Murder Board config. Copy this file to config.js and fill in the key.
// config.js is gitignored and must never be committed: a leaked key gets
// every key on the project killed automatically.
// Two Gemini 4 models, two clear jobs (event rule):
// Argon reasons: Cross-Examiner and Lead Detective, the judging.
// Carbon builds: every other step, extraction and board building.
window.MB_CONFIG = {
  apiKey: "",
  reasoningModel: "gemini-4-argon",
  fastModel: "gemini-4-carbon",
  worldModel: "gemini-4-hydrogen",
  fieldModel: "gemini-4-neon"
};
