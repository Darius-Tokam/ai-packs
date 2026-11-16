"""Replay the deploy-doctor test.

    python build_cases.py /tmp/deploy-cases
    python run_checks.py /tmp/deploy-cases

For each case, runs scripts/diagnose.py on deploy.log with --project and checks:
the named cause is the expected one, nothing else is named, the evidence line
is a real line of the log, the fix and the verification step are there, and,
when the case ships start files, the cause is backed by a line of code.
Healthy cases must come out CLEAN. Standard library only. Exit 1 on failure.
"""
import json
import subprocess
import sys
from pathlib import Path

CASES = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/deploy-cases").resolve()
HERE = Path(__file__).resolve().parent
DIAG = HERE.parent / "scripts" / "diagnose.py"
expected = json.loads((CASES / "expected.json").read_text(encoding="utf-8"))
ok = True
fail_found = fail_total = clean_ok = clean_total = code_backed = code_total = 0

print("| Case | Expected | Named | Evidence | In the code | Result |")
print("|---|---|---|---|---|---|")
for e in expected:
    d = CASES / e["case"]
    res = subprocess.run([sys.executable, str(DIAG), str(d / "deploy.log"), "--project", str(d / "project"), "--json"],
                         capture_output=True, text=True)
    out = json.loads(res.stdout)
    names = [f["id"] for f in out["findings"]]
    log_lines = (d / "deploy.log").read_text(encoding="utf-8").splitlines()
    if e["expected"] is None:
        clean_total += 1
        good = not names and res.returncode == 0
        clean_ok += good
        ev = out["clean_shutdown"][0].split(": ", 1)[1][:40] if out["clean_shutdown"] else "-"
        print(f"| {e['case']} | CLEAN | {', '.join(names) or 'CLEAN'} | {ev} | - | {'PASS' if good else 'FAIL'} |")
    else:
        fail_total += 1
        f = out["findings"][0] if out["findings"] else {}
        line_no = int(f.get("evidence", "x:0:").split(":")[1]) if f else 0
        real_line = 0 < line_no <= len(log_lines) and log_lines[line_no - 1].strip()[:40] in f["evidence"]
        good = (names == [e["expected"]] and real_line and f["fix"] and f["verify"]
                and (not e["var"] or f["var"] == e["var"]) and res.returncode == 1)
        fail_found += bool(good)
        backed = "-"
        if e["has_project"]:
            code_total += 1
            code_backed += bool(f.get("code"))
            backed = f["code"][0].split(" (")[0][:45] if f.get("code") else "none"
            good = good and bool(f.get("code"))
        print(f"| {e['case']} | {e['expected']} | {', '.join(names) or 'CLEAN'} | line {line_no} | {backed} | {'PASS' if good else 'FAIL'} |")
    ok &= bool(good)

print(f"\nfailed deployments: {fail_found}/{fail_total} causes named, nothing else named")
print(f"healthy deployments: {clean_ok}/{clean_total} reported CLEAN (0 false alarm)" if clean_ok == clean_total
      else f"healthy deployments: {clean_total - clean_ok} false alarm(s)")
print(f"causes backed by a line of code: {code_backed}/{code_total} cases that ship start files")

pack = HERE.parent
bad = [str(p.relative_to(pack)) for p in pack.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json"}
       and (chr(0x2014) in p.read_text(encoding="utf-8") or chr(0x2013) in p.read_text(encoding="utf-8"))]
print("files with a long or medium dash:", bad or "none")
ok &= not bad
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
