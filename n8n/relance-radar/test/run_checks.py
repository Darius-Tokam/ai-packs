"""Replay the relance-radar test on the Code node shipped in workflow.json.

    python build_threads.py /tmp/relance-cases
    python run_checks.py /tmp/relance-cases

Needs Python 3.10+ and Node.js. Runs the "Choisir les relances" node through
harness.js on the 27 test threads, then checks: the decision for every thread,
no draft for an excluded, answered, bounced, maxed-out or already drafted
thread, 3 sentences per draft, a clean "Re:" subject, the original date in
the text, the second-follow-up wording, and a second run that drafts nothing
once the drafts exist. Exit 1 on failure.
"""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

CASES = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/relance-cases").resolve()
HERE = Path(__file__).resolve().parent
WF = HERE.parent / "workflow.json"
REASONS = {"exclusion": "exclusion", "recent": "trop récent", "replied": "a répondu", "bounce": "adresse en erreur",
           "max": "maximum atteint", "draft": "brouillon", "relance1": "relance n°1", "relance2": "relance n°2"}


def run(items_path):
    res = subprocess.run(["node", str(HERE / "harness.js"), str(WF), str(items_path), str(CASES / "settings.json")],
                         capture_output=True, text=True)
    if res.returncode:
        sys.exit(res.stderr)
    return json.loads(res.stdout)


expected = {e["thread"]: e for e in json.loads((CASES / "expected.json").read_text(encoding="utf-8"))}
out = {d["threadId"]: d for d in run(CASES / "threads.json")}
ok = len(out) == len(expected)
print("| Fil | Attendu | Décision | Raison | Résultat |\n|---|---|---|---|---|")
for tid, e in expected.items():
    d = out.get(tid, {})
    good = d.get("action") == e["action"] and REASONS[e["reason"]] in d.get("raison", "")
    ok &= good
    print(f"| {tid} | {e['action']} ({e['reason']}) | {d.get('action')} | {d.get('raison')} | {'PASS' if good else 'FAIL'} |")

drafts = [d for d in out.values() if d["action"] == "relancer"]
skipped = Counter(e["reason"] for e in expected.values() if e["action"] == "ignorer")
print(f"\nthreads: {len(out)}; drafts: {len(drafts)}; skipped: {sum(skipped.values())} {dict(skipped)}")
blocked = {e["to"].split("<")[1].rstrip(">") for e in expected.values() if e["reason"] in ("exclusion", "replied", "bounce", "max", "draft")}
wrong = [d["a"] for d in drafts if d["a"] in blocked]
print("drafts to an excluded, answered, bounced, maxed-out or already drafted thread:", wrong or "none")
ok &= not wrong

shape_bad = []
for d in drafts:
    lines = d["message"].split("\n")
    body = lines[2:lines.index("", 2)]
    sentences = [s for s in body if s.strip()]
    if not (lines[0].startswith("Bonjour") and len(sentences) == 3 and d["objet"].startswith("Re: ")
            and not re.match(r"Re: (re|tr|fwd?)\s*:", d["objet"], re.I) and re.search(r"\d{1,2} \w+", sentences[0])
            and chr(0x2014) not in d["message"] and chr(0x2013) not in d["message"]):
        shape_bad.append(d["threadId"])
second = [d["threadId"] for d in drafts if d["relance_numero"] == 2 and "ferme le dossier" in d["message"]]
print("drafts with greeting, 3 sentences, clean Re: subject and original date:", f"{len(drafts) - len(shape_bad)}/{len(drafts)}")
print("second follow-up uses the other wording:", second or "none")
ok &= not shape_bad and second == ["t26"]

# Second morning: every draft now exists in its thread. Nothing new must be drafted.
items = json.loads((CASES / "threads.json").read_text(encoding="utf-8"))
for d in drafts:
    items.append({"json": {"id": d["threadId"] + "-auto", "threadId": d["threadId"], "internalDate": "1788436800000",
                           "From": "Alex Demo <alex@demo-studio.example>", "To": d["a"], "Subject": d["objet"],
                           "labels": [{"id": "DRAFT", "name": "DRAFT"}]}})
(CASES / "threads_day2.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
again = [d for d in run(CASES / "threads_day2.json") if d["action"] == "relancer"]
print("second run, drafts already in place: new drafts =", len(again))
ok &= not again

pack = HERE.parent
bad = [str(p.relative_to(pack)) for p in pack.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json", ".js"}
       and (chr(0x2014) in p.read_text(encoding="utf-8") or chr(0x2013) in p.read_text(encoding="utf-8"))]
print("files with a long or medium dash:", bad or "none")
ok &= not bad
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
