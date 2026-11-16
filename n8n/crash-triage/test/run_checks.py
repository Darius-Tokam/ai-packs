"""Replay the crash-triage test on the two Code nodes shipped in workflow.json.

    python build_events.py /tmp/crash-cases
    python run_checks.py /tmp/crash-cases

Needs Python 3.10+ and Node.js. Runs the Code nodes "Lire l'entrée",
"Lignes Railway" and "Nommer la cause" through harness.js on 21 events (15
through the Railway entry, 6 through the generic entry any host or CI can
call), then checks for each one: followed or ignored, the verdict, the cause
named, that the evidence is a real line of the log, that an alert carries a
cause, a fix and a check (or the last lines when the cause is unknown), and
that a clean stop sends nothing. When the deploy-doctor pack sits next to
this one in the repo, the causes are also compared with its script.
Exit 1 on failure.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CASES = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/crash-cases").resolve()
HERE = Path(__file__).resolve().parent
PACK = HERE.parent
WF = PACK / "workflow.json"
DOCTOR = PACK.parent.parent / "claude" / "deploy-doctor" / "scripts" / "diagnose.py"

res = subprocess.run(["node", str(HERE / "harness.js"), str(WF), str(CASES / "cases.json"), str(CASES / "settings.json")],
                     capture_output=True, text=True)
if res.returncode:
    sys.exit(res.stderr)
results = {r["case"]: r for r in json.loads(res.stdout)}
cases = json.loads((CASES / "cases.json").read_text(encoding="utf-8"))
ok = True
alerts = silenced = ignored = named = 0

print("| Cas | Entrée | Attendu | Suivi | Verdict | Cause nommée | Alerte | Résultat |")
print("|---|---|---|---|---|---|---|---|")
by_entry = {"railway": [0, 0], "direct": [0, 0]}
for c in cases:
    e, r = c["expected"], results[c["case"]]
    ev, cause = r["entree"], r.get("cause") or {}
    good = ev["suivre"] == e["suivre"] and ev["source"] == c["entry"]
    if e["suivre"]:
        good &= cause.get("verdict") == e["verdict"] and cause.get("cause_id", "") == e["cause_id"]
        good &= cause.get("a_alerter") == e["alerte"]
        texte = cause.get("texte", "")
        if e["verdict"] == "panne":
            m = re.search(r"Preuve, ligne (\d+) du log : (.+)", texte)
            lines = r.get("lignes") or []
            good &= bool(m) and lines[int(m.group(1)) - 1].strip()[:40] in m.group(2)
            good &= all(k in texte for k in ("Cause : ", "Pourquoi : ", "Correctif : ", "Pour vérifier : "))
            good &= not e["var"] or (e["var"] in texte)
            named += good
        elif e["verdict"] == "inconnue":
            good &= "deploy-doctor" in texte and ("dernières lignes" in texte or "aucune ligne" in texte or "refusé" in texte)
        prefix = "Railway : panne annoncée sur " if c["entry"] == "railway" else "Déploiement : panne annoncée sur "
        good &= cause.get("sujet", "").startswith(prefix)
        alerts += bool(cause.get("a_alerter"))
        silenced += cause.get("verdict") == "arret-normal"
    else:
        good &= "cause" not in r
        ignored += 1
    ok &= bool(good)
    by_entry[c["entry"]][0] += bool(good)
    by_entry[c["entry"]][1] += 1
    want = "ignoré" if not e["suivre"] else (e["cause_id"] or e["verdict"])
    print(f"| {c['case']} | {c['entry']} | {want} | {'oui' if ev['suivre'] else 'non'} | {cause.get('verdict', '-')} | "
          f"{cause.get('cause_id') or '-'} | {'oui' if cause.get('a_alerter') else 'non'} | {'PASS' if good else 'FAIL'} |")

failures = sum(1 for c in cases if c["expected"]["verdict"] == "panne")
print(f"\nfailures in the logs (both entries): {named}/{failures} causes named, with evidence line, fix and check")
print(f"clean stops on SIGTERM: {silenced} silenced, 0 alert")
print(f"alerts sent: {alerts}; events ignored: {ignored} (not a failure, project not followed)")
print(f"cases passed by entry: Railway {by_entry['railway'][0]}/{by_entry['railway'][1]}, generic {by_entry['direct'][0]}/{by_entry['direct'][1]}")

if DOCTOR.is_file():
    same = 0
    total = 0
    with tempfile.TemporaryDirectory() as tmp:
        for c in cases:
            lines = results[c["case"]].get("lignes")
            if not lines or "cause" not in results[c["case"]]:
                continue
            log = Path(tmp) / f"{c['case']}.log"
            log.write_text("\n".join(lines) + "\n", encoding="utf-8")
            out = json.loads(subprocess.run([sys.executable, str(DOCTOR), str(log), "--json"], capture_output=True, text=True).stdout)
            doc = out["findings"][0]["id"] if out["findings"] else ""
            total += 1
            same += doc == (results[c["case"]]["cause"].get("cause_id") or "")
    print(f"same cause as deploy-doctor's script: {same}/{total}")
    ok &= same == total
else:
    print("same cause as deploy-doctor's script: skipped (claude/deploy-doctor not in this checkout)")

# The jq command of GUIDE.md, replayed on one log: its body must go through the generic entry.
if shutil.which("jq"):
    a1 = results["a1-npm-sigterm"]["lignes"]
    with tempfile.TemporaryDirectory() as tmp:
        log = Path(tmp) / "deploy.log"
        log.write_text("\n".join(a1) + "\n", encoding="utf-8")
        body = json.loads(subprocess.run(f"tail -n 300 '{log}' | jq -Rs --arg s web '{{service: $s, log: .}}'",
                                         shell=True, capture_output=True, text=True).stdout)
        case = Path(tmp) / "case.json"
        case.write_text(json.dumps([{"case": "jq", "settings": {}, "body": body}]), encoding="utf-8")
        r = json.loads(subprocess.run(["node", str(HERE / "harness.js"), str(WF), str(case), str(CASES / "settings.json")],
                                      capture_output=True, text=True).stdout)[0]
    jq_ok = r["entree"]["source"] == "direct" and (r.get("cause") or {}).get("cause_id") == "npm-pid1-sigterm"
    print("jq command of the guide, replayed on the a1 log:", "same cause through the generic entry" if jq_ok else "FAILED")
    ok &= jq_ok
else:
    print("jq command of the guide: skipped (jq not installed)")

wf_text = WF.read_text(encoding="utf-8")
leaks = [k for k in ('"credentials"', '"webhookId"', '"versionId"') if k in wf_text]
print("credentials or instance ids in workflow.json:", leaks or "none")
ok &= not leaks
bad = [str(p.relative_to(PACK)) for p in PACK.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json", ".js"}
       and (chr(0x2014) in p.read_text(encoding="utf-8") or chr(0x2013) in p.read_text(encoding="utf-8"))]
print("files with a long or medium dash:", bad or "none")
ok &= not bad
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
