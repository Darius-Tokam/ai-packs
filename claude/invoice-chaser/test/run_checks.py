"""Replay the invoice-chaser test.

    python build_dataset.py /tmp/books
    python run_checks.py /tmp/books

1. runs chase.py check on the test books and compares its findings with the
   8 planted defects of expected.json;
2. runs chase.py verify on the 4 drafted reminders of emails/ (expected: 0 problems);
3. runs chase.py verify on trap_emails/, the same reminders with 4 planted
   mistakes (expected: 4 problems).
Standard library only. Exit code 1 if any expectation fails.
"""
import json
import subprocess
import sys
from pathlib import Path

BOOKS = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/books").resolve()
HERE = Path(__file__).resolve().parent
CHASE = HERE.parent / "scripts" / "chase.py"
OUT = BOOKS / "out"
ok = True


def run(*args):
    res = subprocess.run([sys.executable, str(CHASE), *args], capture_output=True, text=True)
    return res.returncode, res.stdout + res.stderr


print("=== chase.py check ===")
code, report = run("check", "--invoices", str(BOOKS / "invoices.csv"), "--bank", str(BOOKS / "bank.csv"),
                   "--as-of", "2026-11-12", "--taxes", "TPS:5,TVQ:9.975", "--out", str(OUT))
print(report.split("## Aging")[0].strip())
plan = json.loads((OUT / "plan.json").read_text(encoding="utf-8"))
expected = json.loads((BOOKS / "expected.json").read_text(encoding="utf-8"))

print("\n=== planted defects ===")
found = 0
for e in expected:
    hit = [f for f in plan["findings"] if f["agent"] == e["agent"] and f["invoice"] == e["invoice"]]
    found += bool(hit)
    print(f"{'FOUND' if hit else 'MISSED'} | {e['id']} | {e['agent']} | {e['defect']}")
planted_ids = {(e["agent"], e["invoice"]) for e in expected}
extra = [f for f in plan["findings"] if (f["agent"], f["invoice"]) not in planted_ids]
print(f"{found}/{len(expected)} planted defects found; {len(extra)} other findings:")
for f in extra:
    print(f"  {f['severity']} | {f['agent']} | {f['invoice']} | {f['message']}")
ok &= found == len(expected)

avoided = [p for p in plan["findings"] if p["agent"] == "bank-match" and p["severity"] == "FIX" and "partial" not in p["message"]]
print("\n=== money ===")
print(f"to recover: {plan['to_recover']} on {sum(1 for p in plan['plan'] if p['action'] == 'chase')} invoices, "
      f"{len(plan['emails'])} emails; on hold: {plan['held']}")
inv_total = {p["number"]: p for p in plan["plan"]}
print("reminders avoided on invoices already paid:", ", ".join(f["invoice"] for f in avoided))

print("\n=== verify: drafted reminders ===")
code, out = run("verify", "--plan", str(OUT / "plan.json"), "--emails", str(HERE / "emails"))
print(out.strip())
ok &= code == 0

print("\n=== verify: trap reminders (4 planted mistakes) ===")
code, out = run("verify", "--plan", str(OUT / "plan.json"), "--emails", str(HERE / "trap_emails"))
print(out.strip())
ok &= out.count("PROBLEM") == 4

print("\n=== dashes in the pack ===")
pack = HERE.parent
bad = [str(p.relative_to(pack)) for p in pack.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json"}
       and (chr(0x2014) in p.read_text(encoding="utf-8") or chr(0x2013) in p.read_text(encoding="utf-8"))]
print("files with a long or medium dash:", bad or "none")
ok &= not bad

print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
