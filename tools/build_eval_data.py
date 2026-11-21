import json, os
rows = []
p = "live-eval/results.jsonl"
if os.path.exists(p):
    for line in open(p):
        line = line.strip()
        if line: rows.append(json.loads(line))
with open("app/eval-data.js", "w") as f:
    f.write("window.EVAL_LIVE = " + json.dumps(rows) + ";\n")
print("eval-data.js:", len(rows), "rows")
