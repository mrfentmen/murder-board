#!/usr/bin/env python3
"""Generate app/case-data.js and app/agents-data.js from the sources.

Sources of truth: ../case/*.txt + registry.json, ../agents/*.md.
Run from the repo root: python3 tools/build_data.py
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_case(folder):
    registry = json.load(open(os.path.join(ROOT, folder, "registry.json")))
    docs = []
    for entry in registry["documents"]:
        path = os.path.join(ROOT, folder, entry["file"])
        docs.append({**entry, "text": open(path).read()})
    return {"case_id": registry["case_id"], "case_title": registry["case_title"], "documents": docs}

cases = [load_case("case"), load_case("case2")]
docs = cases[0]["documents"]

agents = []
for path in sorted(glob.glob(os.path.join(ROOT, "agents", "*.md"))):
    agents.append({
        "file": os.path.basename(path),
        "prompt": open(path).read(),
    })

with open(os.path.join(ROOT, "app", "case-data.js"), "w") as f:
    f.write("window.CASE_DOCS = ")
    json.dump(docs, f, indent=1)
    f.write(";\n")

with open(os.path.join(ROOT, "app", "case-data.js"), "a") as f:
    f.write("window.CASES = ")
    json.dump(cases, f, indent=1)
    f.write(";\n")

with open(os.path.join(ROOT, "app", "agents-data.js"), "w") as f:
    f.write("window.AGENT_PROMPTS = ")
    json.dump(agents, f, indent=1)
    f.write(";\n")

print(f"case-data.js: {len(docs)} documents, {len(cases)} cases")
print(f"agents-data.js: {len(agents)} agent prompts")
