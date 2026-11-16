#!/usr/bin/env python3
"""Find which hooks, formats, weekdays and hours go with more impressions in your own posts.

    python3 autopsy.py posts.csv [--json] [--min-gap 25] [--date-order dmy|mdy]

Input: a CSV file (comma, semicolon or tab separated, UTF-8) or a JSON list of
objects, one post per row, with these columns (header names are matched
without case or accents, French and English aliases accepted):

    date         required  2026-11-12, 2026-11-12 08:00, 12/11/2026 (day first,
                           or month first with --date-order mdy)
    impressions  required  a whole number (1 234 and 1,234 are read as 1234);
                           empty or unreadable: the post is excluded and counted
    time         optional  08:00, 8h, 8h30, 8:00 PM (else taken from the date)
    text         optional  the full text of the post (without it, hook and
                           format are not analysed)
    reactions    optional  a whole number
    comments     optional  a whole number

Each post is classified with fixed rules (printed at the end of the report):
hook angle from the first line (question, chiffre, je, tu, autre), length,
arrow list, keyword call to action in capitals ("Commente GUIDE"), weekday,
hour bucket. For each group: n and the median impressions, against the
median of all posts. A group of fewer than 5 posts is marked "échantillon
trop petit" and never appears in the conclusions. The conclusions list only
groups of 5 posts or more whose median differs from the overall median by at
least --min-gap percent (25 by default). The report is Markdown, in French.

Exit codes:
    0  report printed, with at least one conclusion
    1  report printed, nothing can be concluded (no group of 5 posts or more
       differs enough from the overall median, or too few posts)
    2  input error: file missing or unreadable, required column missing, or no
       post with impressions

Standard library only (tested with Python 3.11, 3.12 and 3.13).
"""
import argparse
import csv
import io
import json
import math
import re
import statistics
import sys
import unicodedata
from datetime import date
from pathlib import Path

MIN_N = 5  # a group below this size is never concluded on

ALIASES = {
    "date": ["date", "publish date", "post publish date", "date de publication", "published", "publie le", "created at"],
    "time": ["time", "heure", "hour", "publish time", "heure de publication"],
    "text": ["text", "texte", "post", "contenu", "content", "post text", "commentary", "texte du post"],
    "impressions": ["impressions", "impression", "vues", "views"],
    "reactions": ["reactions", "reaction", "likes"],
    "comments": ["comments", "commentaires", "comment"],
}

# Hook angle: words looked for in the first line, first one met wins.
FIRST_PERSON = {"je", "moi", "me", "mon", "ma", "mes", "i", "i'm", "i've", "i'd", "i'll", "my"}
FIRST_PERSON_PREFIX = ("j'", "m'")
READER = {"tu", "toi", "te", "ton", "ta", "tes", "vous", "votre", "vos", "you", "your", "you're", "you've", "yours"}
READER_PREFIX = ("t'",)
WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")

ARROWS = ("\u2192", "->", "\u27a1", "\U0001f449")  # right arrow, ->, heavy arrow, pointing hand
# Keyword call to action: a verb, then a word of 3 capitals or more ("Commente GUIDE").
# The English verbs need an ending after the keyword, so that the French "Comment SEO marche"
# (comment = how) is not read as a call to action.
_KEYWORD = r"\s*[:\u00ab\"\u201c'(]*\s*([A-Z\u00c0-\u00dd\u0152][A-Z0-9\u00c0-\u00dd\u0152]{2,})(?![\w])"
CTA = re.compile(
    r"(?i:\b(?:commente|commentez|[ée]cris|[ée]crivez|tape|tapez|r[ée]ponds|r[ée]pondez)\b)" + _KEYWORD
    + r"|(?i:\b(?:comment|reply|type)\b)" + _KEYWORD
    + r"(?=\s*[\u00bb\"\u201d')]*\s*(?:$|[.!,:;]|(?i:below|and|to|for|if|in|&)\b))",
    re.M,
)

LENGTHS = [(0, 500, "moins de 500 caractères"), (500, 1300, "500 à 1299 caractères"), (1300, None, "1300 caractères et plus")]
HOURS = [(0, 7, "0h à 6h59"), (7, 10, "7h à 9h59"), (10, 13, "10h à 12h59"), (13, 18, "13h à 17h59"), (18, 24, "18h à 23h59")]
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NO_DATE = "date illisible"
NO_HOUR = "heure inconnue"
UNKNOWN = {NO_DATE, NO_HOUR}
ALIASES_LOOKUP = {n: c for c, names in ALIASES.items() for n in names}

# key, table title, short name used in conclusions, group order, needs the text column
DIMENSIONS = [
    ("hook", "Accroche (première ligne)", "Accroche", ["je", "tu", "chiffre", "question", "autre"], True),
    ("length", "Longueur", "Longueur", [b[2] for b in LENGTHS], True),
    ("arrows", "Liste à flèches", "Liste à flèches", ["oui", "non"], True),
    ("cta", "Mot-clé à commenter (« Commente MOT »)", "Mot-clé à commenter", ["oui", "non"], True),
    ("weekday", "Jour de publication", "Jour", DAYS + [NO_DATE], False),
    ("hour", "Heure de publication", "Heure", [b[2] for b in HOURS] + [NO_HOUR], False),
]

RULES = """## Règles de classement

- Accroche : la première ligne non vide du texte, testée dans cet ordre. « question » si elle finit par « ? ». « chiffre » si elle commence par un chiffre (emoji et guillemets du début ignorés). Sinon le premier mot de personne rencontré : je, j', m', me, moi, mon, ma, mes (ou I, my) donnent « je » ; tu, t', te, toi, ton, ta, tes, vous, votre, vos (ou you, your) donnent « tu ». Sinon « autre ».
- Longueur : nombre de caractères du texte, espaces et retours à la ligne compris, blancs du début et de la fin retirés.
- Liste à flèches : au moins 2 lignes qui commencent par \u2192, ->, \u27a1 ou \U0001f449.
- Mot-clé à commenter : Commente, Commentez, Écris, Tape, Réponds suivi d'un mot en capitales d'au moins 3 lettres, par exemple « Commente GUIDE ». En anglais, Comment, Reply ou Type suivi du mot en capitales, puis d'une fin de phrase ou de below, and, to, for, if, in.
- Jour et heure : ceux écrits dans le fichier, sans conversion de fuseau horaire.
- Médiane : la valeur du milieu (la moyenne des deux du milieu pour un nombre pair de posts). L'écart est celui de la médiane du groupe à la médiane de l'ensemble, arrondi à l'entier."""


class InputError(Exception):
    pass


def norm_key(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("_", " ").split())


def canon_row(row):
    out = {}
    for k, v in row.items():
        if k is None:
            continue
        c = ALIASES_LOOKUP.get(norm_key(k))
        if c and c not in out:
            out[c] = v
    return out


def read_posts(path):
    if not path.is_file():
        raise InputError(f"fichier introuvable : {path}")
    raw = path.read_bytes()
    text = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if path.suffix.lower() == ".json" or text.lstrip().startswith(("[", "{")):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise InputError(f"JSON illisible : {e}")
        if isinstance(data, dict):
            data = data.get("posts")
        if not isinstance(data, list):
            raise InputError("JSON : une liste de posts est attendue")
        rows = [r for r in data if isinstance(r, dict)]
        columns = {norm_key(k) for r in rows for k in r}
    else:
        lines = text.splitlines()
        header = lines[0] if lines else ""
        delim = max([",", ";", "\t"], key=header.count)
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=delim)
        rows = list(reader)
        columns = {norm_key(k) for k in (reader.fieldnames or [])}
    found = {ALIASES_LOOKUP[c] for c in columns if c in ALIASES_LOOKUP}
    missing = [c for c in ("date", "impressions") if c not in found]
    if missing:
        raise InputError("colonne obligatoire absente : " + ", ".join(missing)
                         + " (colonnes trouvées : " + (", ".join(sorted(columns)) or "aucune") + ")")
    return [canon_row(r) for r in rows], found



def parse_count(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value >= 0 and float(value).is_integer() else None
    s = str(value).strip()
    for sp in ("\u00a0", "\u202f", " "):
        s = s.replace(sp, "")
    if re.fullmatch(r"\d{1,3}(?:[,.]\d{3})+", s):
        s = re.sub(r"[,.]", "", s)
    m = re.fullmatch(r"(\d+)(?:[.,]0+)?", s)
    return int(m.group(1)) if m else None


TIME_RX = re.compile(r"^(\d{1,2})\s*(?:[:h]\s*(\d{2})?)?(?::\d{2}(?:\.\d+)?)?\s*([ap])?\.?\s*(?:m\.?)?$", re.I)


def parse_time(value):
    if value is None:
        return None
    s = str(value).strip()
    m = TIME_RX.match(s)
    if not s or not m:
        return None
    h, mins = int(m.group(1)), int(m.group(2) or 0)
    ampm = (m.group(3) or "").lower()
    if ampm == "p" and h < 12:
        h += 12
    if ampm == "a" and h == 12:
        h = 0
    if h > 23 or mins > 59:
        return None
    return h, mins


def parse_date(value, order):
    """Return (date or None, (h, m) or None)."""
    if value is None:
        return None, None
    s = str(value).strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ]+(.+))?$", s)
    if m:
        y, mo, d, rest = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
    else:
        m = re.match(r"^(\d{1,2})[/.](\d{1,2})[/.](\d{4})(?:[ ,T]+(.+))?$", s)
        if not m:
            return None, None
        a, b, y, rest = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        d, mo = (a, b) if order == "dmy" else (b, a)
    try:
        day = date(y, mo, d)
    except ValueError:
        return None, None
    t = None
    if rest:
        t = parse_time(re.sub(r"(?:Z|[+-]\d{2}:?\d{2})$", "", rest.strip()))
    return day, t


def first_line(text):
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def classify_hook(text):
    line = first_line(text)
    if re.sub(r"[^\w?]+$", "", line).endswith("?"):
        return "question"
    if re.sub(r"^[^\w]+", "", line)[:1].isdigit():
        return "chiffre"
    for tok in WORD.findall(line.lower().replace("\u2019", "'")):
        if tok in FIRST_PERSON or tok.startswith(FIRST_PERSON_PREFIX):
            return "je"
        if tok in READER or tok.startswith(READER_PREFIX):
            return "tu"
    return "autre"


def bucket(value, buckets):
    for lo, hi, label in buckets:
        if value >= lo and (hi is None or value < hi):
            return label
    return buckets[-1][2]


def classify(post, order):
    text = str(post.get("text") or "")
    day, t = parse_date(post.get("date"), order)
    t = parse_time(post.get("time")) or t
    stripped = text.strip()
    arrow_lines = sum(1 for ln in text.splitlines() if ln.strip().startswith(ARROWS))
    return {
        "hook": classify_hook(text),
        "length": bucket(len(stripped), LENGTHS),
        "arrows": "oui" if arrow_lines >= 2 else "non",
        "cta": "oui" if CTA.search(text) else "non",
        "weekday": DAYS[day.weekday()] if day else NO_DATE,
        "hour": bucket(t[0], HOURS) if t else NO_HOUR,
        "_date": day.isoformat() if day else None,
        "_time": f"{t[0]:02d}:{t[1]:02d}" if t else None,
        "_chars": len(stripped),
        "_first_line": first_line(text),
    }


def median(values):
    m = statistics.median(values)
    return int(m) if float(m).is_integer() else float(m)


def fmt(x):
    return str(int(x)) if float(x).is_integer() else f"{x:.1f}".replace(".", ",")


def gap_pct(gm, om):
    return math.floor((gm - om) * 100 / om + 0.5) if om else None


def status(n, label, gm, om, min_gap):
    if n < MIN_N:
        return "small"
    if label in UNKNOWN or not om:
        return "unclassified"
    if 100 * (gm - om) >= min_gap * om:
        return "above"
    if 100 * (om - gm) >= min_gap * om:
        return "below"
    return "near"


STATUS_FR = {"small": "échantillon trop petit", "unclassified": "non classé, hors conclusions",
             "above": "au-dessus", "below": "en dessous", "near": "proche de l'ensemble"}


def analyse(path, min_gap, order):
    rows, found = read_posts(path)
    posts, excluded = [], []
    for i, row in enumerate(rows, 1):
        imp = parse_count(row.get("impressions"))
        if imp is None:
            raw = row.get("impressions")
            excluded.append({"post": i, "value": "" if raw is None else str(raw).strip()})
            continue
        c = classify(row, order)
        c.update({"post": i, "impressions": imp,
                  "reactions": parse_count(row.get("reactions")), "comments": parse_count(row.get("comments"))})
        posts.append(c)
    if not posts:
        raise InputError(f"aucun post avec des impressions lisibles ({len(rows)} lignes lues)")
    om = median([p["impressions"] for p in posts])
    has_text = "text" in found
    dims = []
    for key, title, short, order_labels, needs_text in DIMENSIONS:
        if needs_text and not has_text:
            continue
        groups = []
        for label in order_labels:
            vals = [p["impressions"] for p in posts if p[key] == label]
            if not vals:
                continue
            gm = median(vals)
            st = status(len(vals), label, gm, om, min_gap)
            groups.append({"label": label, "n": len(vals), "median": gm,
                           "gap_pct": gap_pct(gm, om) if st != "small" else None, "status": st})
        dims.append({"key": key, "title": title, "short": short, "groups": groups})
    conclusions = []
    for d in dims:
        for g in d["groups"]:
            if g["status"] in ("above", "below"):
                conclusions.append({"dimension": d["short"], "group": g["label"], "n": g["n"],
                                    "median": g["median"], "overall_median": om, "gap_pct": g["gap_pct"],
                                    "direction": g["status"]})
    conclusions.sort(key=lambda c: (c["direction"] != "above", -c["gap_pct"] if c["direction"] == "above" else c["gap_pct"]))
    small = [{"dimension": d["short"], "group": g["label"], "n": g["n"]}
             for d in dims for g in d["groups"] if g["status"] == "small"]
    dates = sorted(p["_date"] for p in posts if p["_date"])
    reac = [p["reactions"] for p in posts if p["reactions"] is not None]
    comm = [p["comments"] for p in posts if p["comments"] is not None]
    return {
        "source": path.name,
        "rows_read": len(rows),
        "analysed": len(posts),
        "excluded": excluded,
        "has_text": has_text,
        "period": [dates[0], dates[-1]] if dates else None,
        "overall": {"n": len(posts), "median": om,
                    "min": min(p["impressions"] for p in posts), "max": max(p["impressions"] for p in posts),
                    "median_reactions": median(reac) if reac else None,
                    "median_comments": median(comm) if comm else None},
        "min_n": MIN_N,
        "min_gap_pct": min_gap,
        "dimensions": dims,
        "conclusions": conclusions,
        "too_small": small,
        "posts": [{**{k: p[k] for k in ("post", "impressions", "hook", "length", "arrows", "cta", "weekday", "hour")},
                   "date": p["_date"], "time": p["_time"], "chars": p["_chars"], "first_line": p["_first_line"]}
                  for p in posts],
    }


def cell(s, width=70):
    s = " ".join(str(s).split()).replace("|", "\\|")
    return s if len(s) <= width else s[: width - 3].rstrip() + "..."


def markdown(r):
    o = r["overall"]
    out = ["# Autopsie de tes posts", ""]
    out.append(f"- Fichier : {r['source']}")
    exc = r["excluded"]
    line = f"- Lignes lues : {r['rows_read']} · posts analysés : {r['analysed']} · exclus : {len(exc)}"
    if exc:
        line += " (impressions vides ou illisibles : post" + ("s" if len(exc) > 1 else "") + " n° " + ", ".join(str(e["post"]) for e in exc) + ")"
    out.append(line)
    if r["period"]:
        out.append(f"- Période : du {r['period'][0]} au {r['period'][1]}")
    out.append(f"- Médiane de l'ensemble : {fmt(o['median'])} impressions (de {o['min']} à {o['max']})")
    extra = []
    if o["median_reactions"] is not None:
        extra.append(f"réactions médianes : {fmt(o['median_reactions'])}")
    if o["median_comments"] is not None:
        extra.append(f"commentaires médians : {fmt(o['median_comments'])}")
    if extra:
        out.append("- " + (" · ".join(extra)).capitalize())
    if not r["has_text"]:
        out.append("- Colonne du texte absente : l'accroche et le format ne sont pas analysés.")
    out += ["", f"Règle : un groupe de moins de {r['min_n']} posts est marqué « échantillon trop petit » et n'entre jamais "
                f"dans les conclusions. Un groupe compte comme différent quand sa médiane s'écarte d'au moins "
                f"{r['min_gap_pct']} % de la médiane de l'ensemble."]
    if r["analysed"] < r["min_n"]:
        out += ["", f"Avec {r['analysed']} post{'s' if r['analysed'] > 1 else ''} analysé{'s' if r['analysed'] > 1 else ''}, "
                    f"aucun groupe ne peut atteindre {r['min_n']} posts : rien ne peut être conclu."]
    for d in r["dimensions"]:
        out += ["", f"## {d['title']}", "", "| Groupe | n | Médiane | Écart | Lecture |", "|---|---|---|---|---|"]
        for g in d["groups"]:
            gap = "" if g["gap_pct"] is None else f"{g['gap_pct']:+d} %"
            out.append(f"| {g['label']} | {g['n']} | {fmt(g['median'])} | {gap} | {STATUS_FR[g['status']]} |")
    out += ["", "## Ce que les chiffres permettent de dire", ""]
    if r["conclusions"]:
        out += [f"Seuls les groupes d'au moins {r['min_n']} posts dont la médiane s'écarte d'au moins {r['min_gap_pct']} % "
                f"de la médiane de l'ensemble ({fmt(o['median'])}) apparaissent ici. Ce sont des corrélations dans ton "
                "historique, pas des causes : le sujet, l'actualité ou un autre facteur peuvent jouer.", ""]
        for c in r["conclusions"]:
            out.append(f"- **{c['dimension']} : {c['group']}** : médiane {fmt(c['median'])} impressions sur {c['n']} posts, "
                       f"contre {fmt(c['overall_median'])} pour l'ensemble ({c['gap_pct']:+d} %).")
    else:
        out.append(f"Rien pour l'instant : aucun groupe d'au moins {r['min_n']} posts ne s'écarte de {r['min_gap_pct']} % "
                   f"de la médiane de l'ensemble. Publie au moins {r['min_n']} posts dans chaque variante que tu veux "
                   "comparer, puis relance l'analyse.")
    if r["too_small"]:
        out += ["", "## Groupes trop petits pour conclure", ""]
        for s in r["too_small"]:
            out.append(f"- {s['dimension']} : {s['group']} ({s['n']} post{'s' if s['n'] > 1 else ''}, "
                       f"il en faut au moins {r['min_n']})")
    ranked = sorted(r["posts"], key=lambda p: (-p["impressions"], p["post"]))
    k = min(3, len(ranked))
    for title, sel in ((f"Tes {k} posts les plus vus", ranked[:k]), (f"Tes {k} posts les moins vus", list(reversed(ranked))[:k])):
        out += ["", f"## {title}", "", "| Post | Date | Heure | Impressions | Première ligne |", "|---|---|---|---|---|"]
        for p in sel:
            out.append(f"| {p['post']} | {p['date'] or ''} | {p['time'] or ''} | {p['impressions']} | {cell(p['first_line'])} |")
    out += ["", RULES]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Which hooks, formats, days and hours go with more impressions in your posts.")
    ap.add_argument("file", help="CSV or JSON export of your posts")
    ap.add_argument("--json", action="store_true", help="print the analysis as JSON instead of Markdown")
    ap.add_argument("--min-gap", type=int, default=25, help="minimum gap to the overall median, in percent (default 25)")
    ap.add_argument("--date-order", choices=["dmy", "mdy"], default="dmy", help="order of slash dates (default dmy: 12/11/2026 is 12 November)")
    a = ap.parse_args(argv)
    if not 1 <= a.min_gap <= 500:
        print("erreur : --min-gap doit être entre 1 et 500", file=sys.stderr)
        return 2
    try:
        r = analyse(Path(a.file), a.min_gap, a.date_order)
    except (InputError, OSError) as e:
        print(f"erreur : {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(markdown(r))
    return 0 if r["conclusions"] else 1


if __name__ == "__main__":
    sys.exit(main())
