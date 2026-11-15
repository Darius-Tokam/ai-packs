"""Replay the post-recycler test.

    python build_trap.py /tmp/recycle-trap
    python run_checks.py /tmp/recycle-trap

1. runs the guard on output/, the 10 formats written from source.md (expected: 10/10 PASS);
2. runs the guard on the trap (expected: exactly the 8 planted defects, video-script and story PASS);
3. checks the pack has no long or medium dash.
Standard library only. Exit code 1 if any expectation fails.
"""
import json
import subprocess
import sys
from pathlib import Path

TRAP = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/recycle-trap").resolve()
HERE = Path(__file__).resolve().parent
GUARD = HERE.parent / "scripts" / "check_formats.py"
ALLOW = "github.com/Darius-Tokam/ai-packs"
ok = True


def guard(source, folder):
    res = subprocess.run([sys.executable, str(GUARD), "--source", str(source), "--dir", str(folder), "--allow", ALLOW],
                         capture_output=True, text=True)
    return res.returncode, res.stdout + res.stderr


print("=== guard on the 10 recycled formats ===")
code, out = guard(HERE / "source.md", HERE / "output")
print(out.strip())
ok &= code == 0

print("\n=== guard on the trap (8 planted defects) ===")
code, out = guard(TRAP / "source.md", TRAP / "formats")
print(out.strip())
expected = json.loads((TRAP / "expected.json").read_text(encoding="utf-8"))
rows = {l.split("|")[1].strip(): l for l in out.splitlines() if l.startswith("| ") and not l.startswith("| Format")}
caught = 0
for fmt, reason in expected.items():
    hit = "FAIL" in rows.get(fmt, "") and reason in rows.get(fmt, "")
    caught += hit
    print(f"{'CAUGHT' if hit else 'MISSED'} | {fmt} | {reason}")
false_alarms = [f for f in rows if f not in expected and "FAIL" in rows[f]]
print(f"{caught}/{len(expected)} planted defects caught, {len(false_alarms)} false alarms {false_alarms or ''}")
ok &= caught == len(expected) and not false_alarms

print("\n=== dashes in the pack ===")
pack = HERE.parent
bad = [str(p.relative_to(pack)) for p in pack.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json"}
       and (chr(0x2014) in p.read_text(encoding="utf-8") or chr(0x2013) in p.read_text(encoding="utf-8"))]
print("files with a long or medium dash:", bad or "none")
ok &= not bad

print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
