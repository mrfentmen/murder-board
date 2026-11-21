#!/usr/bin/env python3
"""Merge cache/*.json into app/cache-data.js as window.CACHE_BY_CASE."""
import glob, json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
by_case = {}
for path in sorted(glob.glob(os.path.join(ROOT, "cache", "*.json"))):
    data = json.load(open(path))
    case_id = os.path.basename(path).replace(".json", "")
    by_case[case_id] = data
with open(os.path.join(ROOT, "app", "cache-data.js"), "w") as f:
    f.write("window.CACHE_BY_CASE = ")
    json.dump(by_case, f)
    f.write(";\n")
print("cache-data.js cases:", ", ".join(by_case.keys()))
