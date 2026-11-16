"""Replay the post-autopsy test.

    python build_history.py /tmp/post-history
    python run_checks.py /tmp/post-history

Runs scripts/autopsy.py on the rebuilt history and recomputes every expected
number from truth.json (the labels build_history.py gave each post), without
importing autopsy.py. Checks: each post's classification; every group's n,
median, gap and reading; every group of fewer than 5 posts flagged and absent
from the conclusions; the conclusions are exactly the groups of 5 posts or more
that differ by 25 % or more; the planted effects are among them; the posts
without impressions are excluded and counted; the JSON input and a French
spreadsheet export (semicolons, French headers, day-first dates) give the same
report; 3 posts give no conclusion; input errors exit 2; the pack has no long
or medium dash. Prints a results table and RESULT: PASS or RESULT: FAIL.
Standard library only. Exit 1 on failure.
"""
import csv
import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

CASE = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/post-history").resolve()
HERE = Path(__file__).resolve().parent
PACK = HERE.parent
SCRIPT = PACK / "scripts" / "autopsy.py"
MIN_N, MIN_GAP = 5, 25

# The output contract of the report: section title and short name of each dimension
DIMS = {
    "hook": ("Accroche (première ligne)", "Accroche"),
    "length": ("Longueur", "Longueur"),
    "arrows": ("Liste à flèches", "Liste à flèches"),
    "cta": ("Mot-clé à commenter (« Commente MOT »)", "Mot-clé à commenter"),
    "weekday": ("Jour de publication", "Jour"),
    "hour": ("Heure de publication", "Heure"),
}
READING = {"small": "échantillon trop petit", "above": "au-dessus", "below": "en dessous", "near": "proche de l'ensemble"}

truth = json.loads((CASE / "truth.json").read_text(encoding="utf-8"))
measured = [p for p in truth["posts"] if p["measured"]]
rows = []
ok = True


def check(name, expected, got, good):
    global ok
    ok &= bool(good)
    rows.append(f"| {name} | {expected} | {got} | {'PASS' if good else 'FAIL'} |")


def num(s):
    return float(s.replace(",", "."))


def fmt(x):
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}".replace(".", ",")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)


def sections(md):
    out, cur = {}, None
    for line in md.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return out


# Expected values, from the ground truth only
om = statistics.median(p["impressions"] for p in measured)
expected = {}
for key in DIMS:
    groups = {}
    for p in measured:
        groups.setdefault(p["labels"][key], []).append(p["impressions"])
    for label, vals in groups.items():
        gm = statistics.median(vals)
        if len(vals) < MIN_N:
            st = "small"
        elif 100 * (gm - om) >= MIN_GAP * om:
            st = "above"
        elif 100 * (om - gm) >= MIN_GAP * om:
            st = "below"
        else:
            st = "near"
        gap = None if st == "small" else math.floor((gm - om) * 100 / om + 0.5)
        expected[(key, label)] = {"n": len(vals), "median": gm, "status": st, "gap": gap}
exp_conclusions = {(DIMS[k][1], lab) for (k, lab), g in expected.items() if g["status"] in ("above", "below")}
exp_small = {(DIMS[k][1], lab) for (k, lab), g in expected.items() if g["status"] == "small"}

# History shape
vals = [p["impressions"] for p in measured]
in_core = sum(20 <= v <= 120 for v in vals)
tail = sorted(v for v in vals if 300 <= v <= 650)
check("forme de l'historique", "médiane proche de 90, la plupart entre 20 et 120, quelques-uns entre 300 et 600",
      f"médiane {fmt(om)}, {in_core}/{len(vals)} entre 20 et 120, {len(tail)} entre 300 et 600 ({', '.join(map(str, tail))})",
      80 <= om <= 100 and in_core > len(vals) / 2 and 3 <= len(tail) <= 6)

# Run on the history
res = run(CASE / "posts.csv")
md = res.stdout
if res.returncode not in (0, 1):
    rows.append(f"| autopsy.py s'arrête en erreur | | {res.stderr.strip().splitlines()[-1] if res.stderr.strip() else ''} | FAIL |")
    ok = False
sec = sections(md)
head = re.search(r"Lignes lues : (\d+) · posts analysés : (\d+) · exclus : (\d+)(?: \(.*?n° ([\d, ]+)\))?", md)
unmeasured = [p["post"] for p in truth["posts"] if not p["measured"]]
got_counts = f"{head.group(1)} / {head.group(2)} / {head.group(3)}" if head else "absent"
check("lignes lues / posts analysés / exclus", f"{truth['rows']} / {len(measured)} / {len(unmeasured)}", got_counts,
      got_counts == f"{truth['rows']} / {len(measured)} / {len(unmeasured)}")
got_excl = head.group(4).strip() if head and head.group(4) else "aucun"
check("posts sans impressions nommés", "n° " + ", ".join(map(str, unmeasured)), "n° " + got_excl,
      got_excl == ", ".join(map(str, unmeasured)))
m = re.search(r"Médiane de l'ensemble : (\S+) impressions", md)
check("médiane de l'ensemble", fmt(om), m.group(1) if m else "absente", bool(m) and num(m.group(1)) == om)
er = statistics.median(p["reactions"] for p in measured)
ec = statistics.median(p["comments"] for p in measured)
m = re.search(r"Réactions médianes : (\S+) · commentaires médians : (\S+)", md)
check("réactions / commentaires médians", f"{fmt(er)} / {fmt(ec)}", f"{m.group(1)} / {m.group(2)}" if m else "absents",
      bool(m) and num(m.group(1)) == er and num(m.group(2)) == ec)

# Per-post classification, from the JSON output
try:
    js = json.loads(run(CASE / "posts.csv", "--json").stdout)
except json.JSONDecodeError:
    js = {"posts": []}
check("sortie JSON lisible", "oui", "oui" if js["posts"] else "non", bool(js["posts"]))
by_post = {p["post"]: p for p in js["posts"]}
good_labels = total_labels = 0
wrong = []
for p in measured:
    got = by_post.get(p["post"], {})
    for key, want in p["labels"].items():
        total_labels += 1
        if got.get(key) == want:
            good_labels += 1
        else:
            wrong.append(f"post {p['post']} {key}: {got.get(key)} != {want}")
check(f"classement de chaque post ({len(measured)} posts x 6 critères)", f"{total_labels}/{total_labels}",
      f"{good_labels}/{total_labels}" + (f" ({'; '.join(wrong[:3])})" if wrong else ""), good_labels == total_labels)
bp = next(p for p in truth["posts"] if p["boundary"])
got_bp = by_post.get(bp["post"], {})
check(f"post à la limite ({bp['time']}, post n° {bp['post']})", bp["labels"]["hour"], got_bp.get("hour"),
      got_bp.get("hour") == bp["labels"]["hour"] and got_bp.get("time") == bp["time"])

# Group tables of the Markdown report
table = {}
for key, (title, _short) in DIMS.items():
    for line in sec.get(title, []):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[1].isdigit():
            table[(key, cells[0])] = cells
good_groups = 0
bad_groups = []
for k, g in expected.items():
    c = table.get(k)
    gap = "" if g["gap"] is None else f"{g['gap']:+d} %"
    if c and int(c[1]) == g["n"] and num(c[2]) == g["median"] and c[3] == gap and c[4] == READING[g["status"]]:
        good_groups += 1
    else:
        bad_groups.append(f"{k[1]}: {c}")
extra = [k for k in table if k not in expected]
check("groupes : n, médiane, écart, lecture", f"{len(expected)}/{len(expected)}, aucun en trop",
      f"{good_groups}/{len(expected)}" + (f", {len(extra)} en trop" if extra else ", aucun en trop")
      + (f" ({'; '.join(bad_groups[:2])})" if bad_groups else ""), good_groups == len(expected) and not extra)

# Conclusions section
bullets = {}
rx = re.compile(r"^- \*\*(.+?) : (.+?)\*\* : médiane (\S+) impressions sur (\d+) posts, contre (\S+) pour l'ensemble \(([+-]\d+) %\)\.$")
for line in sec.get("Ce que les chiffres permettent de dire", []):
    mm = rx.match(line)
    if mm:
        bullets[(mm.group(1), mm.group(2))] = mm
    elif line.startswith("- "):
        bullets[("?", line)] = None
flagged = {(DIMS[k][1], k2) for (k, k2), c in table.items() if c[4] == READING["small"]}
check("groupes de moins de 5 posts marqués « échantillon trop petit »", len(exp_small),
      f"{len(flagged & exp_small)} ({', '.join(f'{d} : {g}' for d, g in sorted(flagged))})", flagged == exp_small)
small_in = [k for k in bullets if k in exp_small]
check("groupes de moins de 5 posts dans les conclusions", 0, len(small_in), not small_in)
listed_small = {tuple(x.strip() for x in re.match(r"- (.+?) : (.+?) \(", ln).groups())
                for ln in sec.get("Groupes trop petits pour conclure", []) if ln.startswith("- ")}
check("groupes de moins de 5 posts listés à part", len(exp_small), len(listed_small & exp_small), listed_small == exp_small)
numbers_ok = all(
    mm is not None and k in exp_conclusions
    and num(mm.group(3)) == expected[(next(key for key, v in DIMS.items() if v[1] == k[0]), k[1])]["median"]
    and int(mm.group(4)) == expected[(next(key for key, v in DIMS.items() if v[1] == k[0]), k[1])]["n"]
    and num(mm.group(5)) == om
    for k, mm in bullets.items())
check(f"conclusions (n >= {MIN_N} et écart >= {MIN_GAP} %)", f"{len(exp_conclusions)}, avec n et les deux médianes",
      f"{len(bullets)}, " + ("identiques" if set(bullets) == exp_conclusions and numbers_ok else "différentes"),
      set(bullets) == exp_conclusions and numbers_ok)
for pl in truth["planted"]:
    key = next(k for k, v in DIMS.items() if v[1] == pl["dimension"])
    g = expected[(key, pl["group"])]
    mm = bullets.get((pl["dimension"], pl["group"]))
    sign_ok = mm is not None and (int(mm.group(6)) > 0) == (pl["direction"] == "above")
    word = "au-dessus" if pl["direction"] == "above" else "en dessous"
    check(f"effet planté : {pl['dimension']} {pl['group']}, {word}", f"{fmt(g['median'])} sur {g['n']} posts",
          f"{mm.group(3)} sur {mm.group(4)} posts, contre {mm.group(5)} ({mm.group(6)} %)" if mm else "absent",
          sign_ok and g["status"] == pl["direction"])
st = truth["small_trap"]
tk = next(k for k, v in DIMS.items() if v[1] == st["dimension"])
g = expected[(tk, st["group"])]
c = table.get((tk, st["group"]))
trap_ok = c is not None and c[4] == READING["small"] and (st["dimension"], st["group"]) not in bullets
check(f"piège : {st['dimension']} {st['group']} ({g['n']} posts, médiane {fmt(g['median'])})",
      "marqué, jamais conclu", f"médiane {c[2] if c else '?'}, " + ("marqué, jamais conclu" if trap_ok else "conclu ou non marqué"),
      trap_ok and g["median"] >= 3 * om)
check("code de sortie sur l'historique", 0, res.returncode, res.returncode == 0)

# JSON input gives the same report
rj = run(CASE / "posts.json")
same = [ln for ln in rj.stdout.splitlines() if not ln.startswith("- Fichier :")] == \
       [ln for ln in md.splitlines() if not ln.startswith("- Fichier :")]
check("entrée JSON : même rapport", "identique", "identique" if same else "différent", same and rj.returncode == res.returncode)

# The same history as a French spreadsheet export: semicolons, BOM, French headers, day-first dates, 8h00
fr = CASE / "export_fr.csv"
with (CASE / "posts.csv").open(encoding="utf-8", newline="") as f_in, fr.open("w", encoding="utf-8-sig", newline="") as f_out:
    w = csv.writer(f_out, delimiter=";", lineterminator="\r\n")
    w.writerow(["Date de publication", "Heure", "Texte", "Impressions", "Réactions", "Commentaires"])
    for r in csv.DictReader(f_in):
        y, mo, d = r["date"].split("-")
        hh, mm_ = r["time"].split(":")
        w.writerow([f"{d}/{mo}/{y}", f"{int(hh)}h{mm_}", r["text"], r["impressions"], r["reactions"], r["comments"]])
rf = run(fr)
same_fr = [ln for ln in rf.stdout.splitlines() if not ln.startswith("- Fichier :")] == \
          [ln for ln in md.splitlines() if not ln.startswith("- Fichier :")]
check("export de tableur français (; en-têtes français, 12/11/2026, 8h00)", "même rapport",
      "même rapport" if same_fr else "différent", same_fr and rf.returncode == res.returncode)

# 3 posts only: no conclusion
r3 = run(CASE / "posts_3.csv")
s3 = sections(r3.stdout)
n3 = sum(1 for ln in s3.get("Ce que les chiffres permettent de dire", []) if ln.startswith("- "))
refused = r3.returncode == 1 and n3 == 0 and "rien ne peut être conclu" in r3.stdout
check("fichier de 3 posts : refuse de conclure", "code 1, 0 conclusion", f"code {r3.returncode}, {n3} conclusion", refused)

# Input errors
r = run(CASE / "absent.csv")
check("fichier absent", "code 2", f"code {r.returncode}", r.returncode == 2)
bad = CASE / "sans_impressions.csv"
with bad.open("w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    w.writerow(["date", "time", "text"])
    w.writerow(["2026-11-12", "08:00", "Je teste."])
r = run(bad)
check("colonne impressions absente", "code 2", f"code {r.returncode}", r.returncode == 2 and "impressions" in r.stderr)

# No long or medium dash anywhere in the pack
dashes = []
for p in sorted(PACK.rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts:
        try:
            t = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if chr(0x2014) in t or chr(0x2013) in t:
            dashes.append(str(p.relative_to(PACK)))
check("tiret long ou moyen dans le pack", "aucun", ", ".join(dashes) or "aucun", not dashes)

print(f"post-autopsy : test sur {truth['rows']} posts reconstitués (graine {truth['seed']})")
print()
print("| Contrôle | Attendu | Mesuré | Résultat |")
print("|---|---|---|---|")
print("\n".join(rows))
print()
print("Conclusions écrites par autopsy.py sur l'historique :")
for line in sec.get("Ce que les chiffres permettent de dire", []):
    if line.startswith("- "):
        print(line)
print()
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
