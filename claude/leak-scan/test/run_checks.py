"""Replay the leak-scan test.

    python build_cases.py /tmp/leak-cases
    python run_checks.py /tmp/leak-cases

Runs scripts/leak_scan.py as a command (it never imports or reads its code)
and compares what it outputs with truth.json, written by build_cases.py:
each planted leak is found once, on exactly its lines, with its form; the
partial leak is flagged partial; no trap line and no line of the clean log is
flagged; in formats.log exactly the leaking lines are flagged; no planted secret appears in full in the Markdown or the JSON report;
--redact changes exactly the leaking lines and a new scan of the copy finds
nothing; the filter printed by --filter python, put on a logging handler,
masks every line like --redact and masks the traceback of logger.exception;
the module printed by --filter node does the same when node is installed;
stdin gives the same result as the file; exit codes 0, 1 and 2; median
runtime; no long or medium dash in the pack.
Prints a table, then RESULT: PASS or RESULT: FAIL. Standard library only.
Exit 1 on failure.
"""
import importlib.util
import io
import json
import logging
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/leak-cases").resolve()
HERE = Path(__file__).resolve().parent
PACK = HERE.parent
SCRIPT = PACK / "scripts" / "leak_scan.py"
truth = json.loads((CASE / "truth.json").read_text(encoding="utf-8"))
APP, CLEAN = CASE / "app.log", CASE / "clean.log"
rows, ok = [], True


def check(name, expected, got, good):
    global ok
    ok &= bool(good)
    rows.append("| %s | %s | %s | %s |" % (name, expected, got, "PASS" if good else "FAIL"))


def run(*args, stdin=None):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", input=stdin)


def lines_of(finding):
    return {loc["line"] for loc in finding["lines"]}


def fr(n):
    return "{:,}".format(n).replace(",", " ")


# ---------------------------------------------------------------- the planted leaks
res = run(APP, "--json")
report = json.loads(res.stdout)
findings = report["findings"]
leaks = truth["leaks"]
matched, exact, forms_ok, partial_ok = {}, 0, 0, True
for leak in leaks:
    want = set(leak["lines"])
    hits = [f for f in findings if lines_of(f) & want]
    if len(hits) == 1:
        matched[leak["id"]] = hits[0]
        exact += lines_of(hits[0]) == want
        forms_ok += hits[0]["form"] == leak["form"]
        partial_ok &= hits[0]["partial"] == leak["partial"]
used = {id(f) for f in matched.values()}
extra = [f for f in findings if id(f) not in used]
check("fuites distinctes trouvées", "10/10, chacune une seule fois", "%d/%d" % (len(matched), len(leaks)),
      len(matched) == len(leaks) == 10)
check("lignes signalées pour chaque fuite", "10/10 identiques à la vérité", "%d/10" % exact, exact == 10)
check("forme de chaque fuite", "10/10", "%d/10" % forms_ok, forms_ok == 10)
loop = next(x for x in leaks if x["id"] == "L01")
f1 = matched.get("L01", {})
check("boucle de 429 : clé Gemini", "1 fuite, %d lignes, l. %d à %d" % (len(loop["lines"]), loop["lines"][0], loop["lines"][-1]),
      "%d fuite, %s lignes, l. %s à %s" % (int(bool(f1)), f1.get("count"), f1.get("first", {}).get("line"),
                                          f1.get("last", {}).get("line")),
      f1 and f1["count"] == len(loop["lines"]) and f1["first"]["line"] == loop["lines"][0]
      and f1["last"]["line"] == loop["lines"][-1] and f1["distinct_values"] == 1)
cut = next(x for x in leaks if x["id"] == "L02")
f2 = matched.get("L02", {})
md_app = run(APP).stdout
check("clé coupée par la troncature", "1 fuite partielle (« fuite partielle »), %d lignes, aucune autre partielle" % len(cut["lines"]),
      "partielle : %s, %s lignes, %s car. visibles sur %s, autres partielles : %d" % (
          "oui" if f2.get("partial") else "non", f2.get("count"), " à ".join(map(str, f2.get("visible_chars") or [])),
          f2.get("expected_length"),
          sum(f["partial"] for f in findings) - bool(f2.get("partial"))),
      f2.get("partial") is True and f2.get("status") == "fuite partielle" and partial_ok
      and sum(f["partial"] for f in findings) == 1 and "fuite partielle" in md_app)
s3, gcs = matched.get("L03", {}), matched.get("L04", {})
check("URL présignées regroupées par signataire", "S3 : 1 fuite, 5 signatures ; GCS : 1 fuite, 4 signatures",
      "S3 : %s signatures ; GCS : %s signatures" % (s3.get("distinct_values"), gcs.get("distinct_values")),
      s3.get("distinct_values") == 5 and gcs.get("distinct_values") == 4)
check("fuites en trop (faux positifs)", "0", "%d" % len(extra), not extra)
trap_lines = {n for t in truth["traps"] for n in t["lines"]}
flagged = {n for f in findings for n in lines_of(f)}
bad_traps = sorted({t["id"] for t in truth["traps"] if set(t["lines"]) & flagged})
check("pièges signalés", "0 sur %d lignes pièges (%d sortes)" % (len(trap_lines), len(truth["traps"])),
      "%d ligne(s)%s" % (len(trap_lines & flagged), " : " + ", ".join(bad_traps) if bad_traps else ""),
      not trap_lines & flagged)
check("cause, correctif et rotation pour chaque fuite", "10/10",
      "%d/10" % sum(bool(f["cause"]) and bool(f["fix"]) and "il n'efface pas ce qui est déjà dans les logs" in f["after"]
                   for f in findings),
      all(f["cause"] and f["fix"] and "il n'efface pas ce qui est déjà dans les logs" in f["after"] for f in findings))
check("code de sortie, log qui fuit", "1", res.returncode, res.returncode == 1)

# ---------------------------------------------------------------- the clean log
cres = run(CLEAN, "--json")
clean = json.loads(cres.stdout)
check("log propre", "0 fuite, code 0 (%d lignes, %d lignes pièges)" % (
    truth["clean_log"]["lines"], sum(len(t["lines"]) for t in truth["clean_traps"])),
      "%d fuite, code %d" % (len(clean["findings"]), cres.returncode), not clean["findings"] and cres.returncode == 0)

# ---------------------------------------------------------------- other log formats, one line each
fm = truth["formats"]
fres_ = run(CASE / fm["file"], "--json")
fflag = {n for f in json.loads(fres_.stdout)["findings"] for n in lines_of(f)}
check("autres formats (nginx, curl, Stripe, Sentry, Kubernetes, CI, systemd)",
      "%d/%d lignes qui fuient signalées, 0/%d autres" % (len(fm["leak_lines"]), len(fm["leak_lines"]), len(fm["clean_lines"])),
      "%d/%d signalées, %d/%d autres" % (len(fflag & set(fm["leak_lines"])), len(fm["leak_lines"]),
                                         len(fflag & set(fm["clean_lines"])), len(fm["clean_lines"])),
      fflag == set(fm["leak_lines"]))

# ---------------------------------------------------------------- no full secret in the reports
secrets = sorted({s for x in leaks for s in x["secrets"] if len(s) >= 8})
in_md = [s[:4] for s in secrets if s in md_app]
in_json = [s[:4] for s in secrets if s in res.stdout]
check("aucun secret complet dans le rapport Markdown", "0 sur %d valeurs plantées" % len(secrets), len(in_md), not in_md)
check("aucun secret complet dans le rapport JSON", "0 sur %d valeurs plantées" % len(secrets), len(in_json), not in_json)

# ---------------------------------------------------------------- --redact
tmp = Path(tempfile.mkdtemp(prefix="leak-scan-check-"))
red_path = tmp / "app.redacted.log"
rres = run(APP, "--redact", red_path, "--json")
orig = APP.read_text(encoding="utf-8").split("\n")
red = red_path.read_text(encoding="utf-8").split("\n")
changed = {i + 1 for i, (a, b) in enumerate(zip(orig, red)) if a != b}
leak_lines = {n for x in leaks for n in x["lines"]}
rescan = run(red_path, "--json")
check("--redact puis nouveau scan", "0 fuite, code 0", "%d fuite, code %d" % (
    len(json.loads(rescan.stdout)["findings"]), rescan.returncode),
      not json.loads(rescan.stdout)["findings"] and rescan.returncode == 0)
check("--redact : lignes modifiées", "exactement les %d lignes qui fuient, même nombre de lignes" % len(leak_lines),
      "%d modifiées, %d hors fuite, %d lignes" % (len(changed), len(changed - leak_lines), len(red) - 1),
      changed == leak_lines and len(red) == len(orig))
check("--redact : secrets dans la copie", "0", sum(s in red_path.read_text(encoding="utf-8") for s in secrets),
      not any(s in red_path.read_text(encoding="utf-8") for s in secrets))

# ---------------------------------------------------------------- --filter python on a logging handler
fres = run("--filter", "python")
(tmp / "leak_filter.py").write_text(fres.stdout, encoding="utf-8")
spec = importlib.util.spec_from_file_location("leak_filter", tmp / "leak_filter.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
buf = io.StringIO()
handler = logging.StreamHandler(buf)
handler.setFormatter(logging.Formatter("%(message)s"))
handler.addFilter(mod.RedactSecretsFilter())
logger = logging.getLogger("leak-scan-check")
logger.propagate, logger.level = False, logging.DEBUG
logger.addHandler(handler)
body = orig[:-1] if orig[-1] == "" else orig
for line in body:
    logger.info("%s", line)
out = buf.getvalue().split("\n")[:-1]
same = sum(a == b for a, b in zip(out, red))
check("--filter python, chaque ligne passée par logging", "%s lignes identiques à --redact" % fr(len(body)),
      "%s/%s identiques" % (fr(same), fr(len(body))), len(out) == len(body) and same == len(body))
buf.truncate(0)
buf.seek(0)
gem = truth["gemini"]


class HTTPError(IOError):
    pass


try:
    raise HTTPError("429 Client Error: Too Many Requests for url: %s?key=%s" % (gem["url"], gem["key"]))
except HTTPError:
    logger.exception("Gemini call failed")
trace = buf.getvalue()
check("--filter python sur logger.exception (la chaîne Gemini)", "clé absente de la trace, [REDACTED] présent",
      "clé absente : %s, [REDACTED] : %s" % ("oui" if gem["key"] not in trace else "non", "oui" if "key=[REDACTED]" in trace else "non"),
      gem["key"] not in trace and "key=[REDACTED]" in trace and "Traceback" in trace)

# ---------------------------------------------------------------- --filter node
node = shutil.which("node")
if node:
    (tmp / "redact.js").write_text(run("--filter", "node").stdout, encoding="utf-8")
    js = ("const {redactSecrets}=require(%s);const fs=require('fs');"
          "process.stdout.write(redactSecrets(fs.readFileSync(%s,'utf8')))") % (
        json.dumps(str(tmp / "redact.js")), json.dumps(str(APP)))
    nres = subprocess.run([node, "-e", js], capture_output=True, text=True, encoding="utf-8")
    nout = nres.stdout.split("\n")
    nsame = sum(a == b for a, b in zip(nout, red))
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip()
    check("--filter node (%s), même log" % version, "%s lignes identiques à --redact" % fr(len(body)),
          "%s/%s identiques" % (fr(min(nsame, len(body))), fr(len(body))), nres.returncode == 0 and nout == red)
else:
    rows.append("| --filter node | identique à --redact | node absent, non lancé | SKIP |")

# ---------------------------------------------------------------- stdin, exit codes, runtime
sres = run("--json", stdin=APP.read_text(encoding="utf-8"))
sig = lambda r: [(f["form"], f["count"], f["first"]["line"], f["last"]["line"]) for f in json.loads(r.stdout)["findings"]]
check("log lu sur l'entrée standard", "même résultat que le fichier", "identique" if sig(sres) == sig(res) else "différent",
      sig(sres) == sig(res) and sres.returncode == 1)
missing = run(tmp / "absent.log")
badopt = run(APP, "--filter", "ruby")
check("codes de sortie", "fuite 1, propre 0, fichier absent 2, option inconnue 2",
      "fuite %d, propre %d, fichier absent %d, option inconnue %d" % (
          res.returncode, cres.returncode, missing.returncode, badopt.returncode),
      (res.returncode, cres.returncode, missing.returncode, badopt.returncode) == (1, 0, 2, 2))
times = []
for _ in range(7):
    t0 = time.perf_counter()
    run(APP, "--json")
    times.append((time.perf_counter() - t0) * 1000)
med = statistics.median(times)
check("temps médian sur %s lignes (7 passages, démarrage de Python compris)" % fr(truth["app_log"]["lines"]),
      "moins de 1 000 ms", "%d ms" % round(med), med < 1000)

bad = [str(p.relative_to(PACK)) for p in PACK.rglob("*") if p.is_file() and p.suffix in {".md", ".py", ".json", ".txt"}
       and (chr(0x2014) in p.read_text(encoding="utf-8") or chr(0x2013) in p.read_text(encoding="utf-8"))]
check("tiret long ou moyen dans le pack", "aucun", ", ".join(bad) or "aucun", not bad)
shutil.rmtree(tmp, ignore_errors=True)

print("leak-scan : test sur un log de production reconstitué de %s lignes (graine %d), un log propre de %s lignes "
      "et %d lignes d'autres formats\n" % (fr(truth["app_log"]["lines"]), truth["seed"], fr(truth["clean_log"]["lines"]),
                                           len(truth["formats"]["leak_lines"]) + len(truth["formats"]["clean_lines"])))
print("| Contrôle | Attendu | Mesuré | Résultat |")
print("|---|---|---|---|")
print("\n".join(rows))
print()
print("Python %s, %s : %s lignes lues, %d fuites, %d lignes signalées." % (
    sys.version.split()[0], APP.name, fr(report["lines_read"]), report["leaks_found"], report["lines_flagged"]))
for f in findings:
    print("  %2d. %-34s %-46s %4d ligne(s)  %s" % (f["id"], f["form"], f["what"][:46], f["count"],
                                                  f["status"]))
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
