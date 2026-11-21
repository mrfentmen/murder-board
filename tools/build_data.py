#!/usr/bin/env python3
"""Generate app/case-data.js and app/agents-data.js from the sources.

Sources of truth: ../case/*.txt + registry.json, ../agents/*.md.
Run from the repo root: python3 tools/build_data.py
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

registry = json.load(open(os.path.join(ROOT, "case", "registry.json")))
docs = []
for entry in registry["documents"]:
    path = os.path.join(ROOT, "case", entry["file"])
    docs.append({**entry, "text": open(path).read()})

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

with open(os.path.join(ROOT, "app", "agents-data.js"), "w") as f:
    f.write("window.AGENT_PROMPTS = ")
    json.dump(agents, f, indent=1)
    f.write(";\n")

print(f"case-data.js: {len(docs)} documents")
print(f"agents-data.js: {len(agents)} agent prompts")
