"""Replay the quote-check test.

    python build_case.py /tmp/quote-cases
    python run_checks.py /tmp/quote-cases

For each case, runs scripts/quote_check.py with the case's tax rates and
checks: the findings are exactly the planted ones (nothing missed, nothing
added), each "missing" finding quotes a real sentence of the brief, each
"hidden" finding points at a real quote line, the hours and the hours range,
and the verdict. Standard library only. Exit 1 on failure.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

CASES = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/quote-cases").resolve()
HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "quote_check.py"
ok = True
planted = found_planted = extra_total = clean_total = clean_ok = 0

print("| Cas | Défauts plantés | Trouvés | En trop | Heures | Fourchette | Verdict | Résultat |")
print("|---|---|---|---|---|---|---|---|")
for e in json.loads((CASES / "expected.json").read_text(encoding="utf-8")):
    d = CASES / e["case"]
    args = [sys.executable, str(SCRIPT), str(d / "quote.md"), str(d / "brief.md"), "--json"]
    for k, v in e["taxes"].items():
        args += ["--tax", f"{k}={v}"]
    res = subprocess.run(args, capture_output=True, text=True)
    out = json.loads(res.stdout)
    ids = [f["id"] for f in out["findings"]]
    want = e["expected"]
    hit = [i for i in want if i in ids]
    extra = [i for i in ids if i not in want]
    brief = (d / "brief.md").read_text(encoding="utf-8")
    quote_lines = (d / "quote.md").read_text(encoding="utf-8").splitlines()
    quotes_ok = True
    for f in out["findings"]:
        if f["kind"] == "missing":
            m = re.search(r"« (.+?) »", f["what"])
            quotes_ok &= bool(m) and m.group(1)[:60] in brief
        if f["kind"] == "hidden":
            n = int(f["where"].split(":")[1])
            item = re.search(r"« (.+?) »", f["what"]).group(1)
            quotes_ok &= item in quote_lines[n - 1]
    rng = out["hours_range"]
    good = (not extra and len(hit) == len(want) and quotes_ok and out["hours"] == e["hours"]
            and (rng == e["hours_range"] or (rng and e["hours_range"] and list(rng) == e["hours_range"]))
            and res.returncode == (1 if want else 0))
    planted += len(want)
    found_planted += len(hit)
    extra_total += len(extra)
    if not want:
        clean_total += 1
        clean_ok += good
    ok &= bool(good)
    verdict = "SEND" if not ids else f"FIX FIRST ({len(ids)})"
    print(f"| {e['case']} | {len(want)} | {len(hit)} | {len(extra)} {extra if extra else ''} | {out['hours']:g} | "
          f"{'-' if not rng else f'{rng[0]:g} à {rng[1]:g} h'} | {verdict} | {'PASS' if good else 'FAIL'} |")

print(f"\nplanted defects: {found_planted}/{planted} found, {extra_total} extra finding(s)")
print(f"clean quotes: {clean_ok}/{clean_total} reported SEND (0 false alarm)" if clean_ok == clean_total
      else f"clean quotes: {clean_total - clean_ok} with a false alarm")
pack = HERE.parent
bad = [str(p.relative_to(pack)) for p in pack.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json"}
       and (chr(0x2014) in p.read_text(encoding="utf-8") or chr(0x2013) in p.read_text(encoding="utf-8"))]
print("files with a long or medium dash:", bad or "none")
ok &= not bad
old = [str(p.relative_to(pack)) for p in pack.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json"}
       and ("Tok" + "Dar24") in p.read_text(encoding="utf-8")]
print("files with the old account name:", old or "none")
ok &= not old
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
