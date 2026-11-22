"""Replay the oss-check test, offline.

    python build_case.py /tmp/oss-check-cases
    python run_checks.py /tmp/oss-check-cases

Runs scripts/oss_check.py as a command on every case written by build_case.py
and checks: the verdict per case and per usage, the gap between the script's
figures and the author's published figures (packages and Mo, tolerance 0,1 Mo),
the carve-outs, the network calls and their class (first launch or dormant),
false alerts on the clean repos and the traps, every quote (15 words or less,
copied from the file), JSON output identical to text output, exit codes,
determinism, and the median time of 5 runs. Then it replays itself on broken
copies of the script (one bug each) and checks that every copy fails the test.
Standard library only. Ends with RESULT: PASS or RESULT: FAIL (exit 1).
"""
import os
import shutil
import json
import re
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = Path(os.environ.get("OSS_CHECK_SCRIPT", HERE.parent / "scripts" / "oss_check.py"))
MUTANT_RUN = "OSS_CHECK_SCRIPT" in os.environ
# one bug per broken copy: (what it breaks, text in the script, replacement)
MUTANTS = [
    ("témoin non soustrait", 'pkgs = [x for x in pkgs if norm_name(x["name"]) not in bnames]', "pkgs = pkgs"),
    ("Mo comptés en Mio", 'f"{n_bytes / 1e6:,.1f}"', 'f"{n_bytes / 1048576:,.1f}"'),
    ("découpage du LICENSE ignoré", "if CARVE_RX.search(norm_ws(t)):", "if False:"),
    ("découpage jugé comme la licence du projet", 'if cs != "OK":\n                st = worst(st, "ATTENTION")',
     'if cs != "OK":\n                st = worst(st, cs)'),
    ("double licence lue comme un cumul", 'mode = "alternatives" if dual and len(roots) > 1 else "cumul"',
     'mode = "cumul"'),
    ("commentaires lus comme du code", 'if (hash_c and ch == "#") or (not hash_c and line.startswith("//", i)):',
     "if False:"),
    ("tests et doc lus comme du code", "    parts = [x.lower() for x in rel.parts[:-1]]", "    return False"),
    ("garde par clé ignorée", 'return "dormant", "derrière une clé (licence ou API)", None',
     'return "premier lancement", "", None'),
    ("promesse du README ignorée", "announced = bool(first) and not pm and", "announced = bool(first) or"),
    ("extras comptés dans la base", '"heavy_base": [n for n in base_names if',
     '"heavy_base": [n for n in base_names + sum(resolved.values(), []) if'),
]
CASES = Path(sys.argv[1] if len(sys.argv) > 1 else Path(tempfile.gettempdir()) / "oss-check-cases").resolve()
# LinkedIn post of Darius Tokam, 2026-08-29: three fresh Python environments, an empty baseline to subtract pip
PUBLISHED = {"a-la-carte": (13, 39.5), "markitdown": (25, 147.7), "markitdown-all": (56, 319.7)}
PUBLISHED_TOP = [("pandas", 52.6), ("sympy", 48.6), ("numpy", 48.6), ("speech_recognition", 42.7),
                 ("onnxruntime", 33.7)]
TOL_MB = 0.1
CODE = {"OK": 0, "ATTENTION": 1, "STOP": 2}
rows, ok = [], True


def run(args, as_json=False):
    return subprocess.run([sys.executable, str(SCRIPT)] + args + (["--json"] if as_json else []),
                          capture_output=True, text=True, cwd=CASES)


def js(args):
    return json.loads(run(args, True).stdout)


def check(section, label, expected, measured, good=None):
    global ok
    good = (expected == measured) if good is None else bool(good)
    ok &= good
    rows.append((section, label, expected, measured, "PASS" if good else "FAIL"))
    return good


def fr(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",")


def key(n):
    return re.sub(r"[^a-z0-9]", "", n.lower())


def env_args(e):
    a = []
    if e.get("env"):
        a += ["--env", e["env"]]
    if e.get("baseline"):
        a += ["--baseline", e["baseline"]]
    return a


expected = json.loads((CASES / "expected.json").read_text(encoding="utf-8"))

# 1. verdict per case and usage, JSON = text, exit codes -------------------------------------------
print("## Verdicts par cas et par usage\n")
print("| Cas | Type | Usage | Attendu | Mesuré | Ligne finale | Résultat |")
print("|---|---|---|---|---|---|---|")
n_verdicts = good_verdicts = same_text = good_codes = 0
reports = {}
for e in expected:
    for u, want in e["verdicts"].items():
        args = ["report", e["case"], "--usage", u] + env_args(e)
        rj, rt = run(args, True), run(args)
        j = json.loads(rj.stdout)
        reports[(e["case"], u)] = j
        last = rt.stdout.strip().splitlines()[-1]
        n_verdicts += 1
        good_verdicts += j["status"] == want
        same_text += last == j["verdict_line"]
        good_codes += rj.returncode == rt.returncode == CODE[j["status"]]
        res = "PASS" if j["status"] == want else "FAIL"
        ok &= res == "PASS"
        print(f"| {e['case']} | {e['kind']} | {u} | {want} | {j['status']} | `{j['verdict_line']}` | {res} |")
print("\n| Cas | Type | perso | interne | saas | redistribution |\n|---|---|---|---|---|---|")
for e in expected:
    cells = [reports[(e["case"], u)]["status"] + ("" if reports[(e["case"], u)]["status"] == w else f" (attendu {w})")
             for u, w in e["verdicts"].items()]
    print(f"| {e['case']} | {e['kind']} | " + " | ".join(cells) + " |")
check("verdict", "verdicts justes (cas x usage)", f"{n_verdicts}/{n_verdicts}", f"{good_verdicts}/{n_verdicts}")
check("sortie", "ligne finale du texte identique au JSON", f"{n_verdicts}/{n_verdicts}", f"{same_text}/{n_verdicts}")
check("sortie", "code de sortie = verdict (0 OK, 1 ATTENTION, 2 STOP)", f"{n_verdicts}/{n_verdicts}",
      f"{good_codes}/{n_verdicts}")
fmt_ok = sum(1 for j in reports.values() if re.fullmatch(
    r"OSS-CHECK: (OK|ATTENTION|STOP) pour (perso|interne|saas|redistribution) : licence .+, (\d+|\?) paquets, "
    r"(\d[\d ]*,\d Mo|taille non mesurée), \d+ appels réseau au démarrage", j["verdict_line"]))
check("sortie", "ligne finale au format OSS-CHECK exact", f"{len(reports)}/{len(reports)}", f"{fmt_ok}/{len(reports)}")

# 2. the author's figures (case 1) -----------------------------------------------------------------
envs = "darius-1-markitdown/envs"
print("\n## Chiffres publiés par l'auteur face au script (cas 1)\n")
print("| Environnement | Publié | Mesuré par le script | Écart | Résultat |")
print("|---|---|---|---|---|")
for name, (n, mb) in PUBLISHED.items():
    args = ["weigh", f"{envs}/{name}", "--baseline", f"{envs}/temoin"]
    j, txt = js(args), run(args).stdout
    got = j["bytes"] / 1e6
    good = (j["count"] == n and abs(got - mb) <= TOL_MB + 1e-9 and j["size"] == f"{fr(mb)} Mo"
            and f"{j['count']} paquets, {j['size']}" in txt)
    ok &= good
    print(f"| {name} | {n} paquets, {fr(mb)} Mo | {j['count']} paquets, {j['size']} | "
          f"{j['count'] - n:+d} paquet, {fr(got - mb, 2)} Mo | {'PASS' if good else 'FAIL'} |")
    rows.append(("poids", f"{name} : paquets et Mo (tolérance {fr(TOL_MB)} Mo), texte = JSON",
                 f"{n}, {fr(mb)} Mo", f"{j['count']}, {j['size']}", "PASS" if good else "FAIL"))
j = js(["weigh", f"{envs}/markitdown-all", "--baseline", f"{envs}/temoin"])
top = [(x["name"], x["bytes"] / 1e6) for x in j["packages"][:5]]
print("\n| Rang | Publié | Mesuré | Écart |\n|---|---|---|---|")
top_ok = 0
for i, ((pn, pm), (gn, gm)) in enumerate(zip(PUBLISHED_TOP, top), 1):
    good = key(pn) == key(gn) and abs(gm - pm) <= TOL_MB + 1e-9
    top_ok += good
    print(f"| {i} | {pn} {fr(pm)} Mo | {gn} {fr(gm)} Mo | {fr(gm - pm, 2)} Mo |")
check("poids", "les 5 plus lourds de markitdown[all], noms et Mo", "5/5", f"{top_ok}/5")
check("poids", "lourds connus signalés dans markitdown[all]", "les 5 publiés",
      "les 5 publiés" if sorted(key(n) for n, _ in PUBLISHED_TOP) == sorted(key(n) for n in j["heavy"])
      else ", ".join(j["heavy"]))
check("poids", "part des lourds connus dans markitdown[all]", "mesurée", f"{j['heavy_size']} ({j['heavy_share']})",
      True)
jb = js(["weigh", f"{envs}/markitdown", "--baseline", f"{envs}/temoin"])
check("poids", "lourds connus dans markitdown seul", "mesurés",
      f"{', '.join(jb['heavy'])} = {jb['heavy_size']} ({jb['heavy_share']})", True)
c = js(["weigh", f"{envs}/a-la-carte", "--baseline", f"{envs}/temoin", "--compare", f"{envs}/markitdown-all"])["compare"]
check("poids", "pile à la carte contenue dans markitdown[all]", "11 des 13", f"{len(c['shared'])} des 13")
check("poids", "les 2 absents de markitdown[all]", "pypdf, typing-extensions", ", ".join(c["missing_there"]))
check("poids", "paquets de markitdown[all] absents de la pile à la carte", "56 - 11 = 45", f"56 - 11 = {c['only_there']}",
      c["only_there"] == 45)
check("poids", "témoin soustrait", "pip, setuptools", ", ".join(j["baseline_removed"]))
nj = js(["weigh", "piege-double-licence/node_modules"])
check("poids", "Node : node_modules (dont 1 paquet à portée @ et 1 imbriqué)", "4 paquets, 4,5 Mo",
      f"{nj['count']} paquets, {nj['size']}")

# 3. licences and carve-outs -----------------------------------------------------------------------
lic = {e["case"]: js(["license", e["case"]]) for e in expected}
for e in expected:
    check("licence", f"{e['case']} : étiquette", e["label"], lic[e["case"]]["label"])
s3 = lic["darius-3-stirling-pdf"]
check("licence", "cas 3 : répertoires découpés trouvés", 6, len(s3["carve_outs"]))
check("licence", "cas 3 : dont non libres (proprietary)", 2, s3["nonfree_carve_outs"])
check("licence", "cas 3 : identifiant global (GitHub affiche NOASSERTION)", "NOASSERTION", s3["spdx_global"])
prod = [c["license"]["quote"] for c in s3["carve_outs"] if c["license"]["id"] == "proprietary"]
check("licence", "cas 3 : clause citée", "2 x « Production use ... »",
      f"{sum(q.startswith('Production use') for q in prod)} x « Production use ... »",
      len(prod) == 2 and all(q.startswith("Production use") for q in prod))
d = lic["piege-double-licence"]
check("licence", "double licence : options trouvées", "AGPL-3.0, commerciale", ", ".join(r["id"] for r in d["root"]))
ap = lic["propre-apache"]
check("licence", "Apache-2.0 : NOTICE et en-têtes SPDX", "NOTICE ; Apache-2.0 x 3",
      f"{', '.join(ap['notices'])} ; " + ", ".join(f"{k} x {v}" for k, v in ap["spdx_headers"].items()))
x = js(["weigh", "piege-extra-lourd"])
check("poids", "extra : dépendances de base", "pypdf, requests", ", ".join(x["base"]))
check("poids", "extra : lourds cachés derrière [ocr] et [all]", "ocr : torch, transformers ; all : pandas, torch, "
      "transformers", " ; ".join(f"{k} : {', '.join(v)}" for k, v in sorted(x["heavy_extras"].items(), reverse=True)))
check("poids", "extra : lourds dans la base", "aucun", ", ".join(x["heavy_base"]) or "aucun")

# 4. network ---------------------------------------------------------------------------------------
net = {e["case"]: js(["network", e["case"]]) for e in expected}
print("\n## Appels réseau trouvés\n")
print("| Cas | Premier lancement (attendu / trouvé) | Dormants (attendu / trouvé) | Détail | Résultat |")
print("|---|---|---|---|---|")
for e in expected:
    n = net[e["case"]]
    first = [c["category"] for c in n["calls"] if c["when"] == "premier lancement"]
    dorm = [c["category"] for c in n["calls"] if c["when"] == "dormant"]
    good = (len(first) == e["first_launch"] and len(dorm) == e["dormant"]
            and first == e.get("first_categories", first) and dorm == e.get("dormant_categories", dorm))
    ok &= good
    detail = "; ".join(f"{c['host']} {c['file'].split('/')[-1]}:{c['line']}, {c['why'] or 'sans garde'}"
                       for c in n["calls"]) or "aucun"
    print(f"| {e['case']} | {e['first_launch']} / {len(first)} | {e['dormant']} / {len(dorm)} | {detail} | "
          f"{'PASS' if good else 'FAIL'} |")
n2, n3 = net["darius-2-open-webui"], net["darius-3-stirling-pdf"]
check("réseau", "cas 2 : réglages qui coupent trouvés dans le code", "HF_HUB_OFFLINE, OFFLINE_MODE",
      ", ".join(n2["switches"]))
check("réseau", "cas 2 : promesse du README contredite", "oui", "oui" if n2["promise_broken"] else "non")
check("réseau", "cas 2 : télémétrie derrière une option désactivée par défaut", "ENABLE_POSTHOG",
      ", ".join(c["option"] for c in n2["calls"] if c["option"]))
check("réseau", "cas 3 : service de clés, dormant derrière la clé", "api.keygen.sh x 2",
      f"{', '.join(sorted({c['host'] for c in n3['calls']}))} x {len(n3['calls'])}")
check("réseau", "cas 3 : promesse du README non contredite", "non contredite",
      "contredite" if n3["promise_broken"] else "non contredite")

# 5. false alerts on the clean repos and the traps -------------------------------------------------
print("\n## Fausses alertes\n")
print("| Cas | Type | Alertes attendues | Alertes trouvées | Fausses | Manquées |")
print("|---|---|---|---|---|---|")
fp_total = fn_total = 0
for e in expected:
    L, N = lic[e["case"]], net[e["case"]]
    exp_calls = e["first_launch"] + e["dormant"]
    found = {u: CODE[reports[(e["case"], u)]["status"]] for u in e["verdicts"]}
    want = e["carve_outs"] + exp_calls + sum(v != "OK" for v in e["verdicts"].values())
    got_items = len(L["carve_outs"]) + len(N["calls"]) + len(L["manifest_mismatch"]) + sum(v > 0 for v in found.values())
    fp = (max(0, len(L["carve_outs"]) - e["carve_outs"]) + max(0, len(N["calls"]) - exp_calls)
          + len(L["manifest_mismatch"]) + sum(found[u] > CODE[w] for u, w in e["verdicts"].items()))
    fn = (max(0, e["carve_outs"] - len(L["carve_outs"])) + max(0, exp_calls - len(N["calls"]))
          + sum(found[u] < CODE[w] for u, w in e["verdicts"].items()))
    if e["kind"] in ("propre", "piège"):
        fp_total += fp
        fn_total += fn
    print(f"| {e['case']} | {e['kind']} | {want} | {got_items} | {fp} | {fn} |")
check("fausses alertes", "sur les 3 propres et les 2 pièges", 0, fp_total)
check("fausses alertes", "alertes manquées sur les pièges", 0, fn_total)
check("piège", "« proprietary » dans un commentaire et une chaîne (propre-mit)", "aucune licence proprietary",
      "aucune licence proprietary" if not lic["propre-mit"]["carve_outs"]
      and [r["id"] for r in lic["propre-mit"]["root"]] == ["MIT"] else "proprietary vu")
check("piège", "huggingface.co dans docs/ et tests/ (propre-apache)", "0 appel, 3 lignes ignorées",
      f"{len(net['propre-apache']['calls'])} appel, {net['propre-apache']['ignored_doc_test']} lignes ignorées")
check("piège", "GPL-3.0 cité dans le CHANGELOG (propre-bsd)", "BSD-3-Clause seule",
      " + ".join(r["id"] for r in lic["propre-bsd"]["root"]) + (" seule" if not lic["propre-bsd"]["carve_outs"] else ""))
check("piège", "check_for_updates() dans une docstring (propre-bsd)", "0 appel, 1 ignoré",
      f"{len(net['propre-bsd']['calls'])} appel, {net['propre-bsd']['ignored_comments']} ignoré")
check("piège", "URL huggingface.co en commentaire, docs/ et tests/ (cas 2)", "1 commentaire, 2 doc ou test ignorés",
      f"{n2['ignored_comments']} commentaire, {n2['ignored_doc_test']} doc ou test ignorés")

# 6. quotes: 15 words or less, copied from the file -------------------------------------------------
quotes = []
for case, L in lic.items():
    items = L["root"] + [c["license"] for c in L["carve_outs"]]
    items += [r for u in L["usages"].values() for r in u["reasons"] if r["path"]]
    for it in items:
        quotes.append((CASES / case / it["path"], it["quote"]))
for case, N in net.items():
    if N["promise"]:
        quotes.append((CASES / case / "README.md", N["promise"]))
q_ok = sum(1 for p, q in quotes if q and len(q.split()) <= 15
           and " ".join(q.split()) in " ".join(p.read_text(encoding="utf-8").split()))
check("citation", "citations de 15 mots au plus, copiées du fichier", f"{len(quotes)}/{len(quotes)}",
      f"{q_ok}/{len(quotes)}")

# 7. JSON = text on the other subcommands, determinism, bad input ---------------------------------
same = 0
for e in expected:
    t = run(["network", e["case"]]).stdout
    n = net[e["case"]]
    same += f"Premier lancement : {n['first_launch']}" in t and f"Dormants : {n['dormant']}" in t
    t = run(["license", e["case"]]).stdout
    same += f"Découpages : {len(lic[e['case']]['carve_outs'])}, dont {lic[e['case']]['nonfree_carve_outs']}" in t
check("sortie", "network et license : chiffres du texte = JSON", f"{2 * len(expected)}/{2 * len(expected)}",
      f"{same}/{2 * len(expected)}")
a, b = run(["report", "darius-3-stirling-pdf", "--usage", "saas", "--json"]), \
    run(["report", "darius-3-stirling-pdf", "--usage", "saas", "--json"])
check("sortie", "deux lancements identiques", "identiques", "identiques" if a.stdout == b.stdout else "différents")
check("sortie", "dossier absent : code 3", 3, run(["license", "dossier-absent"]).returncode)
check("sortie", "usage inconnu : code 3", 3, run(["report", "propre-mit", "--usage", "revente"]).returncode)

# 8. broken copies of the script must fail ---------------------------------------------------------
if not MUTANT_RUN:
    src = SCRIPT.read_text(encoding="utf-8")
    work = Path(tempfile.mkdtemp(prefix="oss-check-mutants-"))
    procs = []
    for i, (what, old, new) in enumerate(MUTANTS):
        if src.count(old) != 1:
            check("copies cassées", f"bug introuvable dans le script : {what}", "1 occurrence", src.count(old))
            continue
        copy = work / f"mutant_{i}.py"
        copy.write_text(src.replace(old, new), encoding="utf-8")
        procs.append((what, subprocess.Popen([sys.executable, __file__, str(CASES)], stdout=subprocess.PIPE,
                                             stderr=subprocess.STDOUT, text=True,
                                             env={**os.environ, "OSS_CHECK_SCRIPT": str(copy)})))
    caught = []
    print("\n## Copies cassées du script\n")
    for what, pr in procs:
        out = pr.communicate()[0]
        fails = [ln.split("|")[2].strip() for ln in out.split("## Contrôles")[-1].splitlines()
                 if ln.endswith("| FAIL |")]
        caught.append(pr.returncode == 1)
        print(f"copie cassée « {what} » : {'rejetée' if pr.returncode == 1 else 'ACCEPTÉE'}"
              + (f" ({len(fails)} contrôle{'s' * (len(fails) > 1)} en échec, dont : {fails[0]})" if fails else ""))
    shutil.rmtree(work, ignore_errors=True)
    check("copies cassées", "copies du script avec un bug, rejetées par le test", f"{len(MUTANTS)}/{len(MUTANTS)}",
          f"{sum(caught)}/{len(MUTANTS)}")

# 9. time ------------------------------------------------------------------------------------------
times = {}
for label, args in () if MUTANT_RUN else (("report cas 1 avec markitdown[all] (56 paquets)",
                     ["report", "darius-1-markitdown/repo", "--usage", "saas", "--env", f"{envs}/markitdown-all",
                      "--baseline", f"{envs}/temoin"]),
                    ("report cas 3 (Stirling PDF reconstitué)", ["report", "darius-3-stirling-pdf", "--usage", "saas"])):
    ms = []
    for _ in range(5):
        t0 = time.perf_counter()
        run(args)
        ms.append((time.perf_counter() - t0) * 1000)
    times[label] = statistics.median(ms)
    rows.append(("temps", f"médiane de 5 lancements : {label}", "mesuré", f"{times[label]:.0f} ms", "PASS"))

# 10. pack hygiene ----------------------------------------------------------------------------------
pack = HERE.parent
texts = [(p, p.read_text(encoding="utf-8")) for p in pack.rglob("*")
         if p.is_file() and p.suffix in {".md", ".py", ".json", ".txt"}]
bad = [str(p.relative_to(pack)) for p, t in texts if chr(0x2014) in t or chr(0x2013) in t]
check("hygiène", "fichiers avec un tiret long ou moyen", "aucun", ", ".join(bad) or "aucun")
old = [str(p.relative_to(pack)) for p, t in texts if ("Tok" + "Dar24") in t]
check("hygiène", "fichiers avec l'ancien nom du compte", "aucun", ", ".join(old) or "aucun")

print("\n## Contrôles\n")
print("| Section | Contrôle | Attendu | Mesuré | Résultat |")
print("|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join(str(x) for x in r) + " |")
print(f"\ncontrôles : {sum(r[4] == 'PASS' for r in rows)}/{len(rows)} PASS ; verdicts : {good_verdicts}/{n_verdicts}")
print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
