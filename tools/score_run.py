import json, sys, os
path = sys.argv[1]
c = json.load(open(path))
o = c.get("outputs", {})
case = os.path.basename(path).split("-2")[0]
# recover case id from filename pattern <case>-<ts>.json
base = os.path.basename(path)
case = base.rsplit("-", 2)[0] if base.count("-") >= 2 else base
steps = ["custody","records","coroner","csi","intake","analyst","digital","cross_examiner","interviewer","prosecutor","lead_detective"]
present = sum(1 for s in steps if s in o)
ce = o.get("cross_examiner", {})
ld = o.get("lead_detective", {})
alibis = {str(a.get("person","")).lower(): str(a.get("rating","")).lower() for a in ce.get("alibis", [])}
def alibi(name):
    for k, v in alibis.items():
        if name in k: return v
    return None
cons = ce.get("contradictions", [])
def pair(d1, d2, sev=None):
    return any({x.get("a_doc"), x.get("b_doc")} == {d1, d2} and (sev is None or str(x.get("severity","")).lower() == sev) for x in cons)
high = sum(1 for x in cons if str(x.get("severity","")).lower() == "high")
gaps = " ".join([str(g) for g in ld.get("gaps", [])] + [str(g) for g in ce.get("evidence_gaps", [])]).lower()
leads = ld.get("leads", [])
top = leads[0] if leads else {}
checks = []
if case == "delgado-2019":
    checks = [("HIGH present", high >= 1), ("Webb CONTRADICTED", alibi("webb") == "contradicted"),
              ("Whitfield UNCORROBORATED", alibi("whitfield") == "uncorroborated"), ("top lead 80", top.get("score") == 80)]
elif case == "screens-2025":
    checks = [("HIGH present", high >= 1), ("Reed CONTRADICTED", alibi("reed") == "contradicted"),
              ("deleted story is a gap", "deleted" in gaps)]
elif case == "harborlight-2016":
    checks = [("HIGH present", high >= 1), ("Herrera CONTRADICTED", alibi("herrera") == "contradicted"),
              ("keypad pair doc03/doc05", pair("doc03", "doc05")), ("top lead names Herrera", "herrera" in str(top.get("action","")).lower())]
elif case == "duck-2020":
    checks = [("HIGH present", high >= 1), ("Offerd CONTRADICTED", alibi("offerd") == "contradicted"),
              ("star pair doc06/doc06 HIGH", pair("doc06", "doc06", "high"))]
passed = sum(1 for _, ok in checks if ok)
failed_names = [n for n, ok in checks if not ok]
row = {"file": base, "case": case, "created_at": c.get("created_at"), "steps": present, "dropped": c.get("dropped"),
       "checks_passed": passed, "checks_total": len(checks), "failed_checks": failed_names}
print(json.dumps(row))
with open(os.path.join(os.path.dirname(path), "..", "results.jsonl"), "a") as f:
    f.write(json.dumps(row) + "\n")
md = "| {created} | {case} | {steps}/11 | {dropped} | {p}/{t} | {fails} |\n".format(
    created=str(c.get("created_at", ""))[11:19], case=case, steps=present, dropped=c.get("dropped"),
    p=passed, t=len(checks), fails=", ".join(failed_names) if failed_names else "none")
with open(os.path.join(os.path.dirname(path), "..", "..", "EVAL_LIVE.md"), "a") as f:
    f.write(md)
