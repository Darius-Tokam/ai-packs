#!/usr/bin/env python3
"""oss-check: before you install an open source tool, what its licence lets you do
and what the install costs (packages, megabytes, outbound network calls).

    oss_check.py license <repo> [--json]
    oss_check.py weigh <site-packages | venv | node_modules | repo> [--baseline DIR] [--compare DIR] [--json]
    oss_check.py network <repo> [--json]
    oss_check.py report <repo> --usage perso|interne|saas|redistribution [--env DIR] [--baseline DIR] [--json]

Python 3 standard library only, offline and deterministic: nothing is installed,
executed or downloaded. Every file is read as text.

- license: every licence file (LICENSE*, COPYING*, per directory licences, SPDX
  headers, the licence field of package.json, pyproject.toml, setup.cfg,
  Cargo.toml), the carve-outs, one status per usage with a quote of 15 words or
  less and its path. It quotes files; it is not legal advice.
- weigh: packages and bytes of an installed environment (Python: the files listed
  in each *.dist-info/RECORD; Node: node_modules/*/package.json and their files),
  minus a baseline, the heaviest, the known heavy packages, and a comparison with
  another environment. On a source repo: the declared dependencies and the heavy
  ones hidden behind an optional extra. Sizes are apparent sizes (os.stat
  st_size) and 1 Mo = 1 000 000 bytes.
- network: a static search of the code for calls that fetch something outside
  (model hubs, licence services, telemetry, update checks), split into first
  launch and dormant (behind a key or an option), with the setting that cuts them.
- report: the three, then one line:
  OSS-CHECK: <OK|ATTENTION|STOP> pour <usage> : licence <...>, <n> paquets, <taille>, <n> appels réseau au démarrage

Exit codes: 0 done (report: OK), 1 report ATTENTION, 2 report STOP, 3 bad input.
"""
import argparse
import configparser
import csv
import json
import os
import re
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None

USAGES = ("perso", "interne", "saas", "redistribution")
RANK = {"OK": 0, "ATTENTION": 1, "STOP": 2}
SKIP_DIRS = {".git", ".hg", ".svn", "node_modules", ".venv", "venv", "site-packages", "__pycache__",
             ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", "target", ".next"}
DOC_TEST_PARTS = {"test", "tests", "testing", "__tests__", "spec", "specs", "e2e", "docs", "doc",
                  "documentation", "examples", "example", "samples", "fixtures", "benchmarks"}
CODE_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".vue", ".svelte", ".java", ".kt",
            ".go", ".rs", ".rb", ".php", ".cs", ".swift", ".scala", ".sh"}
HASH_COMMENT_EXT = {".py", ".rb", ".sh"}
DOC_EXT = {".md", ".rst", ".txt", ".adoc"}
LICENSE_NAME = re.compile(r"^(licen[cs]e|copying|unlicense)([._-].*)?$", re.I)
NOTICE_NAME = re.compile(r"^notice([._-].*)?$", re.I)
README_NAME = re.compile(r"^readme([._-].*)?$", re.I)
MAX_WORDS = 15


class InputError(Exception):
    pass


# ---------------------------------------------------------------- helpers

def read_text(path, limit=2_000_000):
    try:
        with open(path, "rb") as f:
            data = f.read(limit)
    except OSError:
        return ""
    if b"\0" in data[:4096]:
        return ""
    return data.decode("utf-8", errors="replace")


def norm_ws(text):
    return " ".join(text.split())


def worst(*statuses):
    return max(statuses, key=lambda s: RANK[s])


def fmt_mb(n_bytes):
    return f"{n_bytes / 1e6:,.1f}".replace(",", " ").replace(".", ",") + " Mo"


def fmt_pct(x):
    return f"{x:.1f}".replace(".", ",") + " %"


def norm_name(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def quote(text, rx=None, lead=0):
    """A contiguous excerpt of the file, MAX_WORDS words or less, from `lead` words before the match."""
    paras = [norm_ws(p) for p in re.split(r"\n\s*\n", text) if p.strip()]
    norm, starts = " ".join(paras), []
    for p in paras:
        starts.append(sum(len(x) + 1 for x in paras[:len(starts)]))
    m = rx.search(norm) if rx else None
    if not m:
        for line in text.splitlines():
            if line.strip():
                return " ".join(line.split()[:MAX_WORDS])
        return ""
    p = norm.rfind(". ", 0, m.start())
    s = max(p + 2 if p >= 0 else 0, max(x for x in starts if x <= m.start()))
    e = norm.find(". ", m.end())
    e = e + 1 if e >= 0 else len(norm)
    e = min([e] + [x - 1 for x in starts if x > m.end()])
    words = norm[s:e].split()
    idx = max(0, len(norm[s:m.start()].split()) - lead)
    return " ".join(words[idx:idx + MAX_WORDS])


def walk(root):
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")
                         and not d.endswith((".dist-info", ".egg-info")))
        for f in sorted(files):
            p = Path(dirpath) / f
            yield p, p.relative_to(root)


def is_doc_or_test(rel):
    parts = [x.lower() for x in rel.parts[:-1]]
    name = rel.name.lower()
    return (any(x in DOC_TEST_PARTS for x in parts) or name.startswith("test_") or name == "conftest.py"
            or re.search(r"(_test\.\w+|\.(test|spec)\.\w+)$", name) is not None)


def load_toml(path):
    text = read_text(path)
    if tomllib:
        try:
            return tomllib.loads(text)
        except Exception:
            return {}
    data = {}  # minimal fallback: [sections] and key = "string" | ["array", ...]
    cur = data
    for m in re.finditer(r'^\s*\[([^\]]+)\]\s*$|^\s*([\w.-]+)\s*=\s*("[^"]*"|\[[^\]]*\])', text, re.M):
        if m.group(1):
            cur = data
            for part in m.group(1).split("."):
                cur = cur.setdefault(part.strip().strip('"'), {})
        else:
            v = m.group(3)
            cur[m.group(2)] = re.findall(r'"([^"]*)"', v) if v.startswith("[") else v.strip('"')
    return data


# ---------------------------------------------------------------- licences

TEXT_IDS = [  # (id, family, regex on whitespace-normalised text), first match wins
    ("AGPL", "reseau", r"GNU AFFERO GENERAL PUBLIC LICENSE"),
    ("LGPL", "copyleft-faible", r"GNU LESSER GENERAL PUBLIC LICENSE|GNU LIBRARY GENERAL PUBLIC LICENSE"),
    ("GPL", "copyleft", r"GNU GENERAL PUBLIC LICENSE"),
    ("MPL-2.0", "copyleft-faible", r"Mozilla Public License,? (Version )?2\.0"),
    ("EPL-2.0", "copyleft-faible", r"Eclipse Public License"),
    ("BUSL-1.1", "source-disponible", r"Business Source License"),
    ("SSPL-1.0", "source-disponible", r"Server Side Public License"),
    ("Elastic-2.0", "source-disponible", r"Elastic License"),
    ("Commons-Clause", "source-disponible", r"Commons Clause"),
    ("Apache-2.0", "permissive", r"Apache License,? Version 2\.0"),
    ("OFL-1.1", "permissive", r"SIL OPEN FONT LICENSE"),
    ("MIT", "permissive", r"Permission is hereby granted, free of charge, to any person obtaining a copy"),
    ("ISC", "permissive", r"Permission to use, copy, modify, and/or distribute this software for any purpose"),
    ("BSD-3-Clause", "permissive", r"Redistribution and use in source and binary forms(?=.*Neither the name)"),
    ("BSD-2-Clause", "permissive", r"Redistribution and use in source and binary forms"),
    ("Unlicense", "permissive", r"This is free and unencumbered software released into the public domain"),
    ("CC0-1.0", "permissive", r"CC0 1\.0 Universal"),
]
TEXT_IDS = [(i, f, re.compile(r, re.I)) for i, f, r in TEXT_IDS]
CLAUSES = [
    ("production", re.compile(r"production use[^.]{0,120}?(only permitted|is permitted only|requires?|subject to)"
                              r"|non-production use|(may|must|shall) not (be )?used? in production", re.I)),
    ("commercial", re.compile(r"non-?commercial (use|purposes?) only|commercial (use|purposes?)[^.]{0,80}?"
                              r"(requires?|prohibited|not permitted|only)", re.I)),
    ("service", re.compile(r"as a (hosted|managed) service|offer(ing)? the (program|software)[^.]{0,80}?as a service",
                           re.I)),
    ("sell", re.compile(r"the right to Sell", re.I)),
]
CARVE_RX = re.compile(r"portions of this software|resides? under the following director|retains? (its|their) own "
                      r"licen|with the exception of|except for the (files|director|content)|licensed under the "
                      r"license defined in|excluding the (files|director)", re.I)
DUAL_RX = re.compile(r"dual[- ]licen[cs]ed|available under (two|either)|at your option|alternatively,? (you may|"
                     r"under)|commercial licen[cs]e (is )?(also )?available", re.I)
FAMILY_LABEL = {"permissive": "permissive", "copyleft-faible": "copyleft faible", "copyleft": "copyleft",
                "reseau": "copyleft réseau", "source-disponible": "source disponible, non libre",
                "commerciale": "commerciale payante", "inconnue": "non reconnue"}
BASE_MATRIX = {"permissive": "OOOO", "copyleft-faible": "OOOA", "copyleft": "OOOA", "reseau": "OOAA",
               "commerciale": "SSSS", "inconnue": "AAAA"}
WHY = {
    "permissive": "permissive : aucune restriction d'usage, garde l'avis de copyright si tu redistribues",
    "copyleft-faible": "copyleft faible : si tu redistribues, les fichiers modifiés restent sous la même licence",
    "copyleft": "copyleft : si tu redistribues, le programme dérivé suit la même licence, sources comprises",
    "reseau": "copyleft réseau : si tu modifies et sers le logiciel par le réseau, tu publies tes sources",
    "commerciale": "licence commerciale : usage contre une licence payante",
    "inconnue": "licence non reconnue : lis le fichier",
}
CLASSIFIERS = {"MIT License": "MIT", "Apache Software License": "Apache-2.0", "BSD License": "BSD",
               "ISC License (ISCL)": "ISC", "GNU Affero General Public License v3": "AGPL-3.0",
               "GNU General Public License v3 (GPLv3)": "GPL-3.0", "GNU General Public License v2 (GPLv2)": "GPL-2.0",
               "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0",
               "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0", "Other/Proprietary License": "LicenseRef-Proprietary"}


def spdx_family(ident):
    u = ident.strip().upper()
    if u in ("UNLICENSED", "PROPRIETARY") or "COMMERCIAL" in u or "PROPRIETARY" in u:
        return "commerciale"
    if u.startswith("AGPL"):
        return "reseau"
    if u.startswith(("LGPL", "MPL", "EPL", "CDDL")):
        return "copyleft-faible"
    if u.startswith("GPL"):
        return "copyleft"
    if u.startswith(("BUSL", "SSPL", "ELASTIC", "COMMONS-CLAUSE", "CC-BY-NC", "POLYFORM")):
        return "source-disponible"
    if u.startswith(("MIT", "BSD", "APACHE", "ISC", "0BSD", "UNLICENSE", "ZLIB", "PSF", "PYTHON", "CC0", "OFL",
                     "BSL-1.0", "ZPL", "WTFPL")):
        return "permissive"
    return "inconnue"


def classify_text(text, path):
    norm = norm_ws(text)
    head = norm[:400]
    lid = fam = None
    id_rx = None
    for i, f, rx in TEXT_IDS:
        if rx.search(norm):
            lid, fam, id_rx = i, f, rx
            break
    if lid in ("AGPL", "LGPL", "GPL"):
        v = re.search(r"Version (\d)", norm)
        lid = f"{lid}-{v.group(1)}.0" if v else lid
    clauses = [(name, rx) for name, rx in CLAUSES if rx.search(norm)]
    if not lid and re.search(r"commercial licen[cs]e", head, re.I) and not clauses:
        lid, fam = "commerciale", "commerciale"
    elif not lid and (re.search(r"\bproprietary\b", head, re.I) or clauses or (
            re.search(r"all rights reserved", norm, re.I) and not re.search(r"hereby grants?", norm, re.I))):
        lid, fam = "proprietary", "source-disponible"
    elif clauses and fam not in ("source-disponible", "commerciale"):
        lid, fam = f"{lid or 'texte libre'} + restriction", "source-disponible"
    if not lid:
        lid, fam = "inconnue", "inconnue"
    grant = lid == "BUSL-1.1" and re.search(r"Additional Use Grant:", norm, re.I) is not None \
        and re.search(r"Additional Use Grant:\s*None", norm, re.I) is None
    return {"id": lid, "family": fam, "family_label": FAMILY_LABEL[fam], "clauses": [c for c, _ in clauses],
            "grant": grant, "path": path,
            "quote": quote(text, clauses[0][1], lead=6) if clauses else quote(text, id_rx)}


def lic_status(lic, usage):
    fam, cl = lic["family"], set(lic["clauses"])
    if fam in BASE_MATRIX:
        code = BASE_MATRIX[fam][USAGES.index(usage)]
        return {"O": "OK", "A": "ATTENTION", "S": "STOP"}[code], WHY[fam]
    st, why = "OK", []
    hard = "ATTENTION" if lic.get("grant") else "STOP"
    if usage == "perso" and "production" in cl:
        why.append("usage hors production autorisé")
    if usage != "perso" and "production" in cl:
        st = worst(st, hard)
        why.append("usage en production réservé à une licence payante")
    if usage != "perso" and "commercial" in cl:
        st = worst(st, "STOP")
        why.append("usage commercial réservé")
    if usage == "saas" and cl & {"service", "sell"}:
        st = worst(st, "STOP")
        why.append("interdit de le proposer comme service ou de le vendre")
    if usage == "redistribution" and "sell" in cl:
        st = worst(st, "STOP")
        why.append("interdit de le vendre")
    elif usage == "redistribution" and "service" in cl:
        st = worst(st, "ATTENTION")
        why.append("conditions de redistribution à lire")
    if not cl:
        st = "ATTENTION" if usage == "perso" else "STOP"
        why.append("non libre, aucune autorisation d'usage trouvée")
    return st, "; ".join(why) or "source disponible : aucune clause ne vise cet usage"


def manifest_licenses(root):
    out = []
    pj = root / "package.json"
    if pj.is_file():
        try:
            lic = json.loads(read_text(pj)).get("license")
        except ValueError:
            lic = None
        if isinstance(lic, str):
            out.append(("package.json", lic))
    pp = root / "pyproject.toml"
    if pp.is_file():
        proj = load_toml(pp).get("project", {})
        lic = proj.get("license")
        if isinstance(lic, dict):
            lic = lic.get("text")
        if isinstance(lic, str) and lic:
            out.append(("pyproject.toml", lic))
        for c in proj.get("classifiers", []) or []:
            name = c.split("::")[-1].strip()
            if c.startswith("License ::") and name in CLASSIFIERS:
                out.append(("pyproject.toml (classifier)", CLASSIFIERS[name]))
    sc = root / "setup.cfg"
    if sc.is_file():
        cp = configparser.ConfigParser()
        try:
            cp.read_string(read_text(sc))
            if cp.has_option("metadata", "license"):
                out.append(("setup.cfg", cp.get("metadata", "license").strip()))
        except configparser.Error:
            pass
    ct = root / "Cargo.toml"
    if ct.is_file():
        lic = load_toml(ct).get("package", {}).get("license")
        if isinstance(lic, str):
            out.append(("Cargo.toml", lic))
    return out


def spdx_alternatives(expr):
    expr = expr.strip().strip("()")
    return [x.strip().strip("()") for x in re.split(r"\s+OR\s+", expr) if x.strip()]


def analyze_license(root):
    root = Path(root)
    if not root.is_dir():
        raise InputError(f"dossier introuvable : {root}")
    rootfiles = sorted(p for p in root.iterdir() if p.is_file() and LICENSE_NAME.match(p.name))
    texts = {p.name: read_text(p) for p in rootfiles}
    roots = [classify_text(texts[p.name], p.name) for p in rootfiles]
    notices = sorted(p.name for p in root.iterdir() if p.is_file() and NOTICE_NAME.match(p.name))
    manifests = [{"file": f, "license": v, "family": spdx_family(spdx_alternatives(v)[0])}
                 for f, v in manifest_licenses(root)]
    readme = " ".join(read_text(p) for p in sorted(root.iterdir()) if p.is_file() and README_NAME.match(p.name))
    dual = any(" OR " in m["license"] for m in manifests) or any(DUAL_RX.search(norm_ws(t)) for t in texts.values()) \
        or bool(DUAL_RX.search(norm_ws(readme)))
    if not roots and manifests:
        alts = spdx_alternatives(manifests[0]["license"])
        roots = [{"id": a, "family": spdx_family(a), "family_label": FAMILY_LABEL[spdx_family(a)], "clauses": [],
                  "grant": False, "path": manifests[0]["file"], "quote": f'"license": "{manifests[0]["license"]}"'}
                 for a in alts]
        dual = dual or len(alts) > 1
    if dual and len(roots) == 1 and any(" OR " in m["license"] for m in manifests):
        for a in spdx_alternatives(next(m["license"] for m in manifests if " OR " in m["license"])):
            if spdx_family(a) == "commerciale" and all(r["family"] != "commerciale" for r in roots):
                roots.append({"id": "commerciale", "family": "commerciale", "family_label": FAMILY_LABEL["commerciale"],
                              "clauses": [], "grant": False, "path": "package.json", "quote": a})
    mode = "alternatives" if dual and len(roots) > 1 else "cumul"

    # carve-outs: directories listed in a root licence, licence files below the root, SPDX headers
    carves, listed = {}, []
    carve_quote = None
    for name, t in texts.items():
        if CARVE_RX.search(norm_ws(t)):
            carve_quote = {"path": name, "quote": quote(t, CARVE_RX)}
            for tok in re.findall(r"(?<![\w/.:])([A-Za-z0-9_.@-]+(?:/[A-Za-z0-9_.@-]+)*/?)", t):
                tok = tok.rstrip(".")
                if "/" in tok and (root / tok).is_dir():
                    d = tok.rstrip("/") + "/"
                    if d not in listed:
                        listed.append(d)
    for d in listed:
        lf = sorted(p for p in (root / d).iterdir() if p.is_file() and LICENSE_NAME.match(p.name))
        lic = classify_text(read_text(lf[0]), str(lf[0].relative_to(root))) if lf else {
            "id": "non trouvée", "family": "inconnue", "family_label": FAMILY_LABEL["inconnue"], "clauses": [],
            "grant": False, "path": carve_quote["path"], "quote": carve_quote["quote"]}
        carves[d] = {"dir": d, "listed": True, "license": lic}
    root_ids = {r["id"] for r in roots}
    spdx_counts, spdx_other = {}, {}
    for p, rel in walk(root):
        if is_doc_or_test(rel):
            continue
        if LICENSE_NAME.match(p.name):
            if rel.parent == Path("."):
                continue
            d = rel.parent.as_posix() + "/"
            if not any(d.startswith(c) for c in carves):
                lic = classify_text(read_text(p), rel.as_posix())
                if lic["id"] not in root_ids or lic["clauses"]:
                    carves[d] = {"dir": d, "listed": False, "license": lic}
        elif p.suffix.lower() in CODE_EXT:
            head = "\n".join(read_text(p, 4000).splitlines()[:10])
            m = re.search(r"SPDX-License-Identifier:\s*([\w.+-]+(?:\s+(?:OR|AND|WITH)\s+[\w.+-]+)*)", head)
            if m:
                ident = m.group(1)
                spdx_counts[ident] = spdx_counts.get(ident, 0) + 1
                if spdx_alternatives(ident)[0] not in root_ids and spdx_family(ident) != "permissive" \
                        and not any(rel.as_posix().startswith(c) for c in carves):
                    spdx_other.setdefault(ident, []).append(rel.as_posix())
    for ident, files in sorted(spdx_other.items()):
        key = f"SPDX {ident}"
        carves[key] = {"dir": key, "listed": False, "files": files[:5], "license": {
            "id": ident, "family": spdx_family(ident), "family_label": FAMILY_LABEL[spdx_family(ident)],
            "clauses": [], "grant": False, "path": files[0], "quote": f"SPDX-License-Identifier: {ident}"}}
    carve_list = [carves[k] for k in sorted(carves)]

    usages = {}
    for u in USAGES:
        reasons = []
        if not roots:
            st = "ATTENTION" if u == "perso" else "STOP"
            reasons.append({"path": "", "quote": "", "why": "aucune licence trouvée : sans licence, tous droits réservés"})
        else:
            evals = [(lic_status(r, u), r) for r in roots]
            if mode == "alternatives":
                opts = [e for e in evals if e[1]["family"] != "commerciale"] or evals
                (st, why), r = min(opts, key=lambda e: RANK[e[0][0]])
                if st != "OK" and any(e[1]["family"] == "commerciale" for e in evals):
                    why += " ; sinon, la licence commerciale payante"
            else:
                (st, why), r = max(evals, key=lambda e: RANK[e[0][0]])
            reasons.append({"path": r["path"], "quote": r["quote"], "why": f"{r['id']} ({why})"})
        for c in carve_list:
            cs, cw = lic_status(c["license"], u)
            if cs != "OK":
                st = worst(st, "ATTENTION")
                reasons.append({"path": c["license"]["path"], "quote": c["license"]["quote"],
                                "why": f"découpage {c['dir']} : {c['license']['id']} ({cw})"})
        usages[u] = {"status": st, "reasons": reasons}

    nonfree = sum(1 for c in carve_list if c["license"]["family"] in ("source-disponible", "commerciale"))
    if not roots:
        label = "absente"
    else:
        ids = []
        for r in roots:
            if r["id"] not in ids:
                ids.append(r["id"])
        label = (" ou " if mode == "alternatives" else " + ").join(ids)
    if carve_list:
        dirs = sum(1 for c in carve_list if not c["dir"].startswith("SPDX"))
        label += f" avec découpage ({dirs} répertoire{'s' * (dirs > 1)}, {nonfree} non libre{'s' * (nonfree > 1)})"
    if len(roots) == 1 and not carve_quote:
        spdx_global = roots[0]["id"]
    elif mode == "alternatives" and not carve_quote:
        spdx_global = " OR ".join(r["id"] for r in roots)
    else:
        spdx_global = "NOASSERTION"
    mism = [m for m in manifests if roots and spdx_alternatives(m["license"])[0] not in root_ids
            and m["family"] != roots[0]["family"]]
    return {"path": str(root), "root": roots, "mode": mode, "dual": mode == "alternatives", "label": label,
            "spdx_global": spdx_global, "carve_text": carve_quote, "carve_outs": carve_list, "nonfree_carve_outs": nonfree,
            "manifests": manifests, "manifest_mismatch": mism, "spdx_headers": spdx_counts, "notices": notices,
            "usages": usages}


def text_license(r):
    out = [f"Licences de {r['path']}", ""]
    if not r["root"]:
        out.append("Licence du projet : aucune trouvée (sans licence, tous droits réservés)")
    for x in r["root"]:
        tag = "option" if r["dual"] else "licence du projet"
        out.append(f"{tag.capitalize()} : {x['id']} ({x['family_label']}) : {x['path']}")
        out.append(f"  « {x['quote']} »")
    if r["dual"]:
        out.append("Double licence : tu choisis l'une des options ci-dessus")
    out.append(f"Identifiant global : {r['spdx_global']}")
    for m in r["manifests"]:
        out.append(f"Champ de manifeste : {m['file']} : {m['license']}")
    for m in r["manifest_mismatch"]:
        out.append(f"Écart : {m['file']} annonce {m['license']}, le fichier de licence dit autre chose")
    if r["carve_text"]:
        out.append(f"Découpage annoncé dans {r['carve_text']['path']} : « {r['carve_text']['quote']} »")
    out.append(f"Découpages : {len(r['carve_outs'])}, dont {r['nonfree_carve_outs']} non libre"
               + "s" * (r["nonfree_carve_outs"] > 1))
    for c in r["carve_outs"]:
        lic = c["license"]
        out.append(f"  {c['dir']} : {lic['id']} ({lic['family_label']}) : {lic['path']}")
        out.append(f"    « {lic['quote']} »")
    if r["spdx_headers"]:
        out.append("En-têtes SPDX : " + ", ".join(f"{k} x {v}" for k, v in sorted(r["spdx_headers"].items())))
    if r["notices"]:
        out.append("Fichiers NOTICE (à garder si tu redistribues) : " + ", ".join(r["notices"]))
    out += ["", "Usage           Statut      Pourquoi"]
    for u in USAGES:
        e = r["usages"][u]
        for i, why in enumerate(e["reasons"]):
            out.append(f"{u if i == 0 else '':15} {e['status'] if i == 0 else '':11} {why['why']}")
            if why["quote"]:
                out.append(f"{'':28}« {why['quote']} » ({why['path']})")
    out += ["", "Ceci cite les fichiers du dépôt ; ce n'est pas un avis juridique."]
    return "\n".join(out)


# ---------------------------------------------------------------- weight

KNOWN_HEAVY = {norm_name(n) for n in (
    "torch", "tensorflow", "tensorflow-cpu", "jax", "jaxlib", "transformers", "onnxruntime", "onnxruntime-gpu",
    "pandas", "numpy", "scipy", "sympy", "scikit-learn", "SpeechRecognition", "opencv-python",
    "opencv-python-headless", "pyarrow", "matplotlib", "triton", "llvmlite", "numba", "polars", "playwright",
    "puppeteer", "electron", "@tensorflow/tfjs-node", "onnxruntime-node")}
HEAVY_MIN_BYTES = 5_000_000


def find_site_packages(p):
    if any(c.name.endswith((".dist-info", ".egg-info")) for c in p.iterdir()):
        return p
    for cand in sorted(p.glob("lib/python*/site-packages")) + sorted(p.glob("Lib/site-packages")):
        if cand.is_dir():
            return cand
    return None


def python_packages(sp):
    pkgs = []
    for d in sorted(sp.iterdir()):
        if not d.is_dir() or not d.name.endswith((".dist-info", ".egg-info")):
            continue
        meta = read_text(d / ("METADATA" if d.name.endswith(".dist-info") else "PKG-INFO"), 20000)
        name = re.search(r"^Name:\s*(.+)$", meta, re.M)
        ver = re.search(r"^Version:\s*(.+)$", meta, re.M)
        stem = d.name.rsplit(".", 1)[0]
        name = name.group(1).strip() if name else stem.split("-")[0]
        ver = ver.group(1).strip() if ver else (stem.split("-")[1] if "-" in stem else "")
        size, seen = 0, set()
        rec = d / "RECORD"
        if rec.is_file():
            for row in csv.reader(read_text(rec).splitlines()):
                if not row or not row[0]:
                    continue
                fp = os.path.normpath(os.path.join(sp, row[0]))
                if fp in seen:
                    continue
                seen.add(fp)
                if os.path.isfile(fp):
                    size += os.stat(fp).st_size
                elif len(row) > 2 and row[2].isdigit():
                    size += int(row[2])
        else:
            tops = read_text(d / "top_level.txt").split() + [d.name]
            for t in tops:
                for base in (sp / t, sp / f"{t}.py"):
                    if base.is_file():
                        size += base.stat().st_size
                    elif base.is_dir():
                        size += sum(f.stat().st_size for f in base.rglob("*") if f.is_file())
        pkgs.append({"name": name, "version": ver, "bytes": size})
    return pkgs


def node_packages(nm):
    pkgs = []

    def visit(nmdir):
        for e in sorted(nmdir.iterdir()):
            if not e.is_dir() or e.name.startswith("."):
                continue
            for pkg in (sorted(x for x in e.iterdir() if x.is_dir()) if e.name.startswith("@") else [e]):
                pj = pkg / "package.json"
                if not pj.is_file():
                    continue
                try:
                    data = json.loads(read_text(pj))
                except ValueError:
                    data = {}
                size = 0
                for dp, dirs, files in os.walk(pkg):
                    dirs[:] = [x for x in dirs if x != "node_modules"]
                    size += sum(os.lstat(os.path.join(dp, f)).st_size for f in files)
                pkgs.append({"name": data.get("name", pkg.name), "version": data.get("version", ""), "bytes": size,
                             "path": str(pkg.relative_to(nm))})
                if (pkg / "node_modules").is_dir():
                    visit(pkg / "node_modules")
    visit(nm)
    return pkgs


def env_packages(path):
    p = Path(path)
    if not p.is_dir():
        raise InputError(f"dossier introuvable : {p}")
    sp = find_site_packages(p)
    if sp:
        return "python", sp, python_packages(sp)
    if p.name == "node_modules":
        return "node", p, node_packages(p)
    return None, p, None


def req_name(req):
    m = re.match(r"\s*([A-Za-z0-9@][A-Za-z0-9._/@-]*)(\[([^\]]*)\])?", req)
    return (m.group(1), [x.strip() for x in (m.group(3) or "").split(",") if x.strip()]) if m else (None, [])


def declared(root):
    root = Path(root)
    base, extras, manifests, project = [], {}, [], None
    pp = root / "pyproject.toml"
    if pp.is_file():
        data = load_toml(pp)
        proj = data.get("project", {})
        project = proj.get("name")
        base += list(proj.get("dependencies", []) or [])
        for k, v in (proj.get("optional-dependencies", {}) or {}).items():
            extras.setdefault(k, []).extend(v or [])
        manifests.append("pyproject.toml")
    sc = root / "setup.cfg"
    if sc.is_file():
        cp = configparser.ConfigParser()
        try:
            cp.read_string(read_text(sc))
            project = project or (cp.get("metadata", "name") if cp.has_option("metadata", "name") else None)
            if cp.has_option("options", "install_requires"):
                base += [x for x in cp.get("options", "install_requires").splitlines() if x.strip()]
            if cp.has_section("options.extras_require"):
                for k, v in cp.items("options.extras_require"):
                    extras.setdefault(k, []).extend(x for x in v.splitlines() if x.strip())
            manifests.append("setup.cfg")
        except configparser.Error:
            pass
    pj = root / "package.json"
    if pj.is_file():
        try:
            data = json.loads(read_text(pj))
        except ValueError:
            data = {}
        project = project or data.get("name")
        base += list((data.get("dependencies") or {}).keys())
        for k in ("optionalDependencies", "peerDependencies"):
            if data.get(k):
                extras.setdefault(k, []).extend(data[k].keys())
        manifests.append("package.json")
    base_names = sorted({req_name(r)[0] for r in base if req_name(r)[0]}, key=str.lower)
    resolved = {}
    for k in extras:
        names, todo, seen = set(), [k], set()
        while todo:
            e = todo.pop()
            if e in seen:
                continue
            seen.add(e)
            for r in extras.get(e, []):
                n, sub = req_name(r)
                if n and project and norm_name(n) == norm_name(project):
                    todo += sub
                elif n:
                    names.add(n)
        resolved[k] = sorted(names - set(base_names), key=str.lower)
    heavy_extras = {k: [n for n in v if norm_name(n) in KNOWN_HEAVY] for k, v in resolved.items()}
    return {"kind": "declare", "path": str(root), "manifests": manifests, "project": project, "base": base_names,
            "count": len(base_names), "extras": resolved,
            "heavy_base": [n for n in base_names if norm_name(n) in KNOWN_HEAVY],
            "heavy_extras": {k: v for k, v in heavy_extras.items() if v}}


def weigh(path, baseline=None, compare=None):
    kind, where, pkgs = env_packages(path)
    if pkgs is None:
        d = declared(where)
        if not d["manifests"]:
            raise InputError(f"ni site-packages, ni node_modules, ni manifeste dans {where}")
        return d
    removed = []
    if baseline:
        bk, _, bp = env_packages(baseline)
        if bp is None:
            raise InputError(f"témoin illisible : {baseline}")
        bnames = {norm_name(x["name"]) for x in bp}
        removed = sorted(x["name"] for x in pkgs if norm_name(x["name"]) in bnames)
        pkgs = [x for x in pkgs if norm_name(x["name"]) not in bnames]
    pkgs.sort(key=lambda x: (-x["bytes"], x["name"].lower()))
    total = sum(x["bytes"] for x in pkgs)
    heavy = [x for x in pkgs if norm_name(x["name"]) in KNOWN_HEAVY and x["bytes"] >= HEAVY_MIN_BYTES]
    hb = sum(x["bytes"] for x in heavy)
    res = {"kind": kind, "path": str(where), "count": len(pkgs), "bytes": total, "size": fmt_mb(total),
           "baseline_removed": removed, "packages": pkgs, "top": [x["name"] for x in pkgs[:5]],
           "heavy": [x["name"] for x in heavy], "heavy_bytes": hb, "heavy_size": fmt_mb(hb),
           "heavy_share": fmt_pct(100 * hb / total) if total else fmt_pct(0)}
    if compare:
        ck, _, cp = env_packages(compare)
        if cp is None:
            raise InputError(f"environnement à comparer illisible : {compare}")
        if baseline:
            cp = [x for x in cp if norm_name(x["name"]) not in bnames]
        mine = {norm_name(x["name"]): x["name"] for x in pkgs}
        other = {norm_name(x["name"]) for x in cp}
        res["compare"] = {"path": str(compare), "shared": sorted((mine[n] for n in mine if n in other), key=str.lower),
                          "missing_there": sorted((mine[n] for n in mine if n not in other), key=str.lower),
                          "only_there": len(other - set(mine)), "count_there": len(other)}
    return res


def text_weigh(r):
    if r["kind"] == "declare" and not r["manifests"]:
        return f"Dépendances de {r['path']} : aucun manifeste lu (pyproject.toml, setup.cfg, package.json)"
    if r["kind"] == "declare":
        out = [f"Dépendances déclarées de {r['path']} ({', '.join(r['manifests'])}), rien d'installé",
               f"{r['count']} paquets de base : " + (", ".join(r["base"]) or "aucun")]
        for k, v in sorted(r["extras"].items()):
            out.append(f"Extra [{k}] : {len(v)} paquets en plus : " + (", ".join(v) or "aucun"))
        out.append("Lourds connus dans la base : " + (", ".join(r["heavy_base"]) or "aucun"))
        for k, v in sorted(r["heavy_extras"].items()):
            out.append(f"Lourds connus cachés derrière l'extra [{k}] : " + ", ".join(v))
        return "\n".join(out)
    out = [f"Poids de {r['path']} ({r['kind']})"]
    if r["baseline_removed"]:
        out.append(f"Témoin soustrait : {len(r['baseline_removed'])} paquets ({', '.join(r['baseline_removed'])})")
    out.append(f"{r['count']} paquets, {r['size']} (taille apparente, 1 Mo = 1 000 000 octets)")
    out.append("Les plus lourds :")
    for x in r["packages"][:5]:
        out.append(f"  {x['name']} {x['version']} : {fmt_mb(x['bytes'])}")
    out.append("Lourds connus, rarement utiles au but annoncé : " + (
        f"{', '.join(r['heavy'])} = {r['heavy_size']} ({r['heavy_share']})" if r["heavy"] else "aucun"))
    c = r.get("compare")
    if c:
        out.append(f"Comparaison avec {c['path']} : {len(c['shared'])} des {r['count']} paquets d'ici y sont aussi ; "
                   f"absents là-bas : {', '.join(c['missing_there']) or 'aucun'} ; "
                   f"{c['only_there']} paquets de là-bas absents d'ici")
    return "\n".join(out)


# ---------------------------------------------------------------- network

NET_PATTERNS = [(c, re.compile(r), h) for c, r, h in [
    ("modele", r"huggingface\.co|\bhf\.co/", None),
    ("modele", r"\b(hf_hub_download|snapshot_download|from_pretrained|SentenceTransformer|CrossEncoder)\s*\(",
     "huggingface.co"),
    ("modele", r"\btorch\.hub\.load\s*\(", "github.com"),
    ("licence", r"api\.keygen\.sh|https?://[\w.-]*licen[cs]\w*\.[\w.-]+", None),
    ("telemetrie", r"posthog\.com|sentry\.io|api\.segment\.io|api\.mixpanel\.com|scarf\.sh|api\.amplitude\.com|"
                   r"google-analytics\.com|plausible\.io", None),
    ("telemetrie", r"\bposthog\.(capture|init|identify)\s*\(|\bPosthog\s*\(", "posthog"),
    ("telemetrie", r"\bsentry_sdk\.init\s*\(|\bSentry\.init\s*\(", "sentry"),
    ("telemetrie", r"\b(mixpanel|amplitude|analytics)\.(track|init|identify)\s*\(", "analytics"),
    ("telemetrie", r"\b(send|report|post|upload|track)_?[Tt]elemetry\w*\s*\(", "télémétrie"),
    ("mise-a-jour", r"\b(check_for_updates?|checkForUpdates?|check_update|checkUpdate)\s*\(", "mise à jour"),
    ("mise-a-jour", r"api\.github\.com/repos/[^\"'\s]*releases|pypi\.org/pypi/|registry\.npmjs\.org", None),
]]
CATEGORY_LABEL = {"modele": "modèle", "licence": "licence", "telemetrie": "télémétrie", "mise-a-jour": "mise à jour"}
SWITCH_FOR = {"modele": r"OFFLINE|^HF_", "telemetrie": r"TELEMETRY|DO_NOT_TRACK|ANALYTICS|SCARF|POSTHOG|SENTRY",
              "mise-a-jour": r"UPDATE|OFFLINE", "licence": r"$^"}
KILL_RX = re.compile(r"OFFLINE|DO_NOT_TRACK|NO_ANALYTICS|TELEMETRY|DISABLE|OPT_OUT|NO_UPDATE|SKIP_UPDATE")
ENV_RX = re.compile(r"(?:getenv|environ\.get|environ\.setdefault)\s*\(\s*[\"']([A-Z][A-Z0-9_]+)|environ\[\s*[\"']"
                    r"([A-Z][A-Z0-9_]+)|process\.env\.([A-Z][A-Z0-9_]+)|process\.env\[\s*[\"']([A-Z][A-Z0-9_]+)|"
                    r"System\.getenv\(\s*\"([A-Z][A-Z0-9_]+)")
CONST_RX = re.compile(r"\b([A-Za-z_]\w*)\s*[:=]\s*[\"'`](https?://[^\"'`\s]+)")
DECL_RX = re.compile(r"^\s*(def|async\s+def|function|class|public|private|protected|static|export\s+function|fun)\b")
IF_RX = re.compile(r"^\s*(\}\s*)?(if|elif|else\s+if)\b")
ELSE_RX = re.compile(r"^\s*(\}\s*)?else\b(?!\s+if)")
FUNC_RX = re.compile(r"^\s*(async\s+def|def|function|fun|func)\s+\w+|^\s*(public|private|protected|static|async|"
                     r"export)\b[^=;]*\(.*\)\s*(throws[\w\s,.]+)?\{?\s*$")
EXIT_RX = re.compile(r"\b(return|raise|throw)\b")
KEY_RX = re.compile(r"licen[cs]e_?key|licenseKey|LICENSE_KEY|api_?key|apiKey|API_KEY|\btoken\b|_token\b", re.I)
PROMISE_RX = re.compile(r"(does not|doesn't|never) makes? any external connections?|no external connections?|"
                        r"(works|runs) (fully |completely |entirely )?offline|100 ?% (local|offline)|nothing ever "
                        r"(leaves|uploads)|never leaves your|aucune connexion (externe|sortante)|fonctionne hors ligne|"
                        r"air-?gapped", re.I)
ANNOUNCE_RX = re.compile(r"(first|initial) (run|launch|start)|premier (lancement|démarrage)|"
                         r"downloads? (the |an? )?(embedding )?models?|télécharge", re.I)


def code_lines(text, ext):
    """Lines with comments, docstrings and block comments blanked; string contents kept."""
    hash_c = ext in HASH_COMMENT_EXT
    out, block = [], None
    for line in text.splitlines():
        res, i, q = [], 0, None
        while i < len(line):
            if block:
                j = line.find("*/" if block == "/*" else block, i)
                if j < 0:
                    break
                i, block = j + (2 if block == "/*" else 3), None
                continue
            ch = line[i]
            if q:
                res.append(ch)
                if ch == "\\" and i + 1 < len(line):
                    res.append(line[i + 1])
                    i += 2
                    continue
                q = None if ch == q else q
                i += 1
                continue
            if ext == ".py" and line.startswith(('"""', "'''"), i):
                block, i = line[i:i + 3], i + 3
                continue
            if (hash_c and ch == "#") or (not hash_c and line.startswith("//", i)):
                break
            if not hash_c and line.startswith("/*", i):
                block, i = "/*", i + 2
                continue
            if ch in "\"'`":
                q = ch
            res.append(ch)
            i += 1
        out.append("".join(res).rstrip())
    return out


def indent(s):
    return len(s) - len(s.lstrip())


def guards(lines, i):
    ind = cur = indent(lines[i])
    conds, else_at = [], None
    for j in range(i - 1, max(-1, i - 80), -1):
        s = lines[j]
        if not s.strip():
            continue
        k = indent(s)
        if IF_RX.match(s) and (k < cur or (else_at is not None and k == else_at)):
            conds.append(("NOT " if else_at is not None and k == else_at else "") + s.strip())
            cur, else_at = k, None
            continue
        if IF_RX.match(s) and k == ind:
            nxt = next((x for x in lines[j + 1:i] if x.strip()), "")
            if EXIT_RX.search(s.split(")", 1)[-1] if "(" in s else s) or (indent(nxt) > k and EXIT_RX.search(nxt)):
                conds.append(s.strip())
            continue
        if k < cur and ELSE_RX.match(s):
            cur, else_at = k, k
            continue
        if k < cur and FUNC_RX.match(s):
            break
        if k < cur:
            cur = k
    return conds


def option_default(name, defaults):
    short = name.split(".")[-1]
    return defaults.get(short)


def truthy(rhs):
    m = re.search(r"(?:getenv|environ\.get)\s*\(\s*[\"']\w+[\"']\s*(?:,\s*[\"']?([^\"')]*))?", rhs)
    if m:
        return (m.group(1) or "").strip().lower() in ("true", "1", "yes", "on")
    lit = rhs.strip().rstrip(",;):").strip()
    if lit in ("True", "true", "1"):
        return True
    if lit in ("False", "false", "0", "None", "null", "undefined", '""', "''"):
        return False
    return None


def classify_call(conds, defaults):
    for c in conds:
        neg = c.startswith("NOT ") or re.search(r"\bif\s*\(?\s*(not\b|!)", c) is not None
        if KEY_RX.search(c):
            return "dormant", "derrière une clé (licence ou API)", None
        for ident in re.findall(r"[A-Za-z_][\w.]*", c):
            last = ident.split(".")[-1]
            if re.search(r"enable|opt_?in|optin", last, re.I) or re.match(r"use_", last, re.I):
                d = option_default(ident, defaults)
                active = (d is True) != neg
                if not active:
                    lab = {True: "true", False: "false", None: "inconnu"}[d]
                    return "dormant", f"derrière l'option {last} (défaut : {lab})", last
                break
    return "premier lancement", "", None


def analyze_network(root):
    root = Path(root)
    if not root.is_dir():
        raise InputError(f"dossier introuvable : {root}")
    files, ignored_doc, ignored_comment, env_names, defaults = [], 0, 0, set(), {}
    for p, rel in walk(root):
        ext = p.suffix.lower()
        if is_doc_or_test(rel):
            if ext in CODE_EXT | DOC_EXT:
                t = read_text(p)
                ignored_doc += sum(1 for ln in t.splitlines() if any(rx.search(ln) for _, rx, _ in NET_PATTERNS))
            continue
        if ext not in CODE_EXT:
            continue
        raw = read_text(p)
        lines = code_lines(raw, ext)
        files.append((rel, ext, raw.splitlines(), lines))
        for ln in lines:
            for g in ENV_RX.findall(ln):
                env_names.update(x for x in g if x)
            m = re.search(r"(?:^|[\s,(])(?:self\.|this\.)?([A-Za-z_]\w*)\s*(?::\s*\w+\s*)?=(?!=)\s*(.+)", ln)
            if m and defaults.get(m.group(1)) is None:
                defaults[m.group(1)] = truthy(m.group(2))
    found = {}
    for rel, ext, raw, lines in files:
        for i, ln in enumerate(lines):
            hit_raw = any(rx.search(raw[i]) for _, rx, _ in NET_PATTERNS) if i < len(raw) else False
            hits = [(c, rx.search(ln), h) for c, rx, h in NET_PATTERNS]
            hits = [x for x in hits if x[1]]
            if hit_raw and not hits:
                ignored_comment += 1
            if not hits:
                continue
            cat, m, host = hits[0]
            host = host or re.search(r"(?:[\w-]+\.)+[a-z]{2,}", m.group(0)).group(0)
            cm = CONST_RX.search(ln)
            sites = []
            if cm and cm.group(2) in ln and any(rx.search(cm.group(2)) for _, rx, _ in NET_PATTERNS):
                name = cm.group(1)
                sites = [j for j, x in enumerate(lines) if j != i and re.search(rf"\b{re.escape(name)}\b", x)]
                if not sites:
                    key = (rel.as_posix(), i + 1)
                    found[key] = {"category": cat, "file": rel.as_posix(), "line": i + 1, "host": host,
                                  "code": ln.strip()[:120], "when": "dormant", "why": "URL déclarée, jamais appelée ici",
                                  "option": None}
                    continue
            elif DECL_RX.match(ln):
                continue
            else:
                sites = [i]
            for j in sites:
                when, why, opt = classify_call(guards(lines, j), defaults)
                found[(rel.as_posix(), j + 1)] = {"category": cat, "file": rel.as_posix(), "line": j + 1,
                                                  "host": host, "code": lines[j].strip()[:120], "when": when,
                                                  "why": why, "option": opt}
    calls = [found[k] for k in sorted(found)]
    switches = sorted(n for n in env_names if KILL_RX.search(n))
    for c in calls:
        sw = [n for n in switches if re.search(SWITCH_FOR[c["category"]], n)]
        if c["option"]:
            sw.append(c["option"])
        c["switches"] = sw
    readme_files = sorted(p for p in root.iterdir() if p.is_file() and README_NAME.match(p.name))
    readme = " ".join(norm_ws(read_text(p)) for p in readme_files)
    pm = PROMISE_RX.search(readme)
    first = [c for c in calls if c["when"] == "premier lancement"]
    hosts = {c["host"] for c in first}
    announced = bool(first) and not pm and (bool(ANNOUNCE_RX.search(readme)) or any(h in readme for h in hosts))
    return {"path": str(root), "calls": calls, "first_launch": len(first), "dormant": len(calls) - len(first),
            "switches": switches, "promise": quote(readme, PROMISE_RX) if pm else None,
            "promise_broken": bool(pm) and bool(first), "announced": announced,
            "ignored_doc_test": ignored_doc, "ignored_comments": ignored_comment}


def text_network(r):
    out = [f"Appels réseau trouvés dans le code de {r['path']} (lecture statique, rien n'est exécuté)"]
    for when, n in (("premier lancement", r["first_launch"]), ("dormant", r["dormant"])):
        out.append(f"{'Premier lancement' if when == 'premier lancement' else 'Dormants'} : {n}")
        for c in r["calls"]:
            if c["when"] == when:
                extra = f" : {c['why']}" if c["why"] else ""
                out.append(f"  {CATEGORY_LABEL[c['category']]} : {c['file']}:{c['line']} : {c['host']}{extra}")
                out.append(f"    {c['code']}")
                if c["switches"]:
                    out.append(f"    réglage qui coupe : {', '.join(c['switches'])}")
    out.append("Variables qui coupent, trouvées dans le code : " + (", ".join(r["switches"]) or "aucune"))
    if r["promise"]:
        state = (f"contredite par {r['first_launch']} appels au premier lancement" if r["promise_broken"]
                 else "pas contredite par la lecture du code")
        out.append(f"Promesse du README : « {r['promise']} » : {state}")
    if r["first_launch"]:
        out.append("Appels au premier lancement annoncés dans le README : " + ("oui" if r["announced"] else "non"))
    out.append(f"Ignorés : {r['ignored_doc_test']} dans les tests ou la doc, {r['ignored_comments']} dans des commentaires")
    return "\n".join(out)


# ---------------------------------------------------------------- report

def report(root, usage, env=None, baseline=None):
    lic = analyze_license(root)
    net = analyze_network(root)
    if env:
        w = weigh(env, baseline)
        if w["kind"] == "declare":
            raise InputError(f"--env doit être un site-packages, un venv ou un node_modules : {env}")
        n, size = w["count"], w["size"]
    else:
        w = declared(root)
        n, size = (w["count"] if w["manifests"] else "?"), "taille non mesurée"
    u = lic["usages"][usage]
    status, reasons = u["status"], [x for x in u["reasons"] if u["status"] != "OK" or x is u["reasons"][0]]
    if net["first_launch"] and not net["announced"]:
        status = worst(status, "ATTENTION")
        why = f"{net['first_launch']} appels réseau au premier lancement, non annoncés"
        if net["promise_broken"]:
            why += f", alors que le README promet « {net['promise']} »"
        reasons.append({"path": "", "quote": "", "why": why})
    line = (f"OSS-CHECK: {status} pour {usage} : licence {lic['label']}, {n} paquets, {size}, "
            f"{net['first_launch']} appels réseau au démarrage")
    return {"usage": usage, "status": status, "reasons": reasons, "license": lic, "network": net, "weight": w,
            "verdict_line": line}


def text_report(r):
    parts = [text_license(r["license"]), text_network(r["network"]), text_weigh(r["weight"]), "",
             f"Verdict pour l'usage « {r['usage']} » :"]
    for x in r["reasons"]:
        q = f" : « {x['quote']} » ({x['path']})" if x["quote"] else ""
        parts.append(f"- {x['why']}{q}")
    parts.append(r["verdict_line"])
    return "\n\n".join(parts[:3]) + "\n\n" + "\n".join(parts[3:])


# ---------------------------------------------------------------- CLI

class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"oss_check.py: erreur : {message}", file=sys.stderr)
        sys.exit(3)


def main(argv=None):
    ap = Parser(prog="oss_check.py", description="Licence, poids et appels réseau d'un outil open source, hors ligne.")
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=Parser)
    s = sub.add_parser("license", help="licences, découpages et statut par usage")
    s.add_argument("repo")
    s = sub.add_parser("weigh", help="paquets et octets d'un environnement installé, ou dépendances déclarées")
    s.add_argument("env")
    s.add_argument("--baseline")
    s.add_argument("--compare")
    s = sub.add_parser("network", help="appels réseau trouvés dans le code")
    s.add_argument("repo")
    s = sub.add_parser("report", help="les trois, puis la ligne OSS-CHECK")
    s.add_argument("repo")
    s.add_argument("--usage", required=True, choices=USAGES)
    s.add_argument("--env")
    s.add_argument("--baseline")
    for p in sub.choices.values():
        p.add_argument("--json", action="store_true", help="sortie JSON")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "license":
            r, txt = analyze_license(a.repo), text_license
        elif a.cmd == "weigh":
            r, txt = weigh(a.env, a.baseline, a.compare), text_weigh
        elif a.cmd == "network":
            r, txt = analyze_network(a.repo), text_network
        else:
            r, txt = report(a.repo, a.usage, a.env, a.baseline), text_report
    except InputError as e:
        print(f"oss_check.py: erreur : {e}", file=sys.stderr)
        return 3
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else txt(r))
    return {"OK": 0, "ATTENTION": 1, "STOP": 2}[r["status"]] if a.cmd == "report" else 0


if __name__ == "__main__":
    sys.exit(main())
