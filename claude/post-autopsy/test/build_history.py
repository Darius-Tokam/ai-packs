"""Rebuild the post-autopsy test case: a history of 42 LinkedIn posts with known effects.

    python build_history.py /tmp/post-history

Writes into the folder:
  posts.csv     the history as an export (date, time, text, impressions, reactions, comments)
  posts.json    the same history as a JSON list (same keys)
  posts_3.csv   3 posts only, to check that the script refuses to conclude
  truth.json    the ground truth: for each post, the labels it was built with,
                the planted effects and the traps

The history is shaped like the author's: 40 posts with impressions from
2026-08-29 to 2026-11-12, a median near 90, most posts between 20 and 120 and
a few between 300 and 600, plus 2 posts without impressions. All texts are
invented. Fixed seed: the same files on every run. Standard library only.

Planted effects (the script must report them):
  first-person hooks ("je") have a clearly higher median than reader hooks ("tu")
  posts at 7h to 9h59 beat posts at 18h to 23h59
Traps:
  3 question hooks with a spectacular median (must be "échantillon trop petit")
  2 posts without impressions (must be excluded and counted)
  1 post at 10:00 exactly, on the boundary of the 10h to 12h59 bucket
"""
import csv
import json
import math
import random
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/post-history")
SEED = 20261115
rng = random.Random(SEED)

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MORNING, MIDDAY, AFTERNOON, EVENING = "7h à 9h59", "10h à 12h59", "13h à 17h59", "18h à 23h59"
SHORT, MEDIUM, LONG = "moins de 500 caractères", "500 à 1299 caractères", "1300 caractères et plus"
LENGTH_RANGE = {SHORT: (0, 500), MEDIUM: (500, 1300), LONG: (1300, 3000)}
LENGTH_TARGET = {SHORT: (220, 470), MEDIUM: (560, 1230), LONG: (1360, 2100)}

# How many measured posts each (hook, hour bucket) cell holds: 40 in all.
DESIGN = {
    "je":       {MORNING: 6, MIDDAY: 4, AFTERNOON: 1, EVENING: 1},
    "tu":       {MORNING: 2, MIDDAY: 2, AFTERNOON: 2, EVENING: 4},
    "chiffre":  {MORNING: 3, MIDDAY: 2, AFTERNOON: 1, EVENING: 1},
    "question": {MORNING: 1, MIDDAY: 2},
    "autre":    {MORNING: 2, MIDDAY: 2, AFTERNOON: 2, EVENING: 2},
}
# Impressions = base of the hook x factor of the hour x noise. The 3 question posts are fixed.
BASE = {"je": 150, "tu": 48, "chiffre": 100, "autre": 92}
HOUR_FACTOR = {MORNING: 1.3, MIDDAY: 1.0, AFTERNOON: 0.85, EVENING: 0.55}
QUESTION_VALUES = [340, 470, 590]
TIMES = {
    MORNING: ["08:00", "08:00", "08:00", "08:00", "07:45", "08:15", "08:30", "09:10"],
    MIDDAY: ["12:00", "12:00", "11:30", "12:15", "10:45"],
    AFTERNOON: ["14:00", "15:30", "16:45", "13:20"],
    EVENING: ["21:00", "21:00", "21:00", "18:30", "20:15", "22:10"],
}

HOOKS = {
    "je": [
        "J'ai arrêté de publier pendant 40 jours. Voici ce que j'ai perdu.",
        "Je pensais que mon contenu était bon.",
        "Mon pire post de l'année m'a appris une chose.",
        "J’ai testé une routine d'écriture pendant un mois.",
        "Ma cliente m'a posé une question simple ce matin.",
        "Mes posts du lundi ne marchaient pas, j'ai cherché pourquoi.",
        "Je publie à 8h depuis septembre.",
        "J'ai compris pourquoi tu n'as pas de vues.",
        "Hier, j'ai supprimé la moitié de mon post avant de le publier.",
        "\U0001f680 J'ai lancé mon offre sans page de vente.",
        "Mon premier client est venu d'un commentaire.",
        "Je relis chaque première ligne à voix haute.",
        "J'ai refusé un projet bien payé la semaine dernière.",
    ],
    "tu": [
        "Tu publies tous les jours et personne ne réagit.",
        "Ton profil dit ce que tu fais, pas ce que tu règles.",
        "Ta première ligne décide de tout.",
        "Tes abonnés ne lisent pas la fin de tes posts.",
        "Ton audience ne voit pas ce que je vois.",
        "Tu écris pour tes pairs, pas pour tes clients.",
        "Vous confondez visibilité et ventes.",
        "Tu n'as pas besoin d'un nouvel outil.",
        "Ton calendrier éditorial est trop chargé.",
        "Tes meilleurs posts sont déjà écrits.",
        "Tu peux recycler ce post demain matin.",
    ],
    "chiffre": [
        "3 erreurs qui coûtent des clients aux freelances.",
        "40 posts en 75 jours : ce que j'ai appris.",
        "5 lignes qui changent une première ligne.",
        "90 impressions par post, le constat.",
        "« 12 heures » : le temps que me prend une semaine de contenu.",
        "7 jours pour tester une nouvelle accroche.",
        "2 phrases suffisent pour présenter une offre.",
        "10 minutes par jour pour répondre aux commentaires.",
    ],
    "question": [
        "Pourquoi tes posts plafonnent à 90 vues ?",
        "Combien de posts faut-il pour trouver ton format ? \U0001f914",
        "Et si ta meilleure accroche était ta première phrase ?",
    ],
    "autre": [
        "Le contenu éducatif ne se vend pas tout seul.",
        "Hier, un client a annulé son contrat.",
        "Un outil ne remplace pas une méthode.",
        "La régularité bat l'inspiration.",
        "Personne ne lit les hashtags.",
        "Le meilleur moment pour publier n'existe pas.",
        "Une offre claire tient en une phrase.",
        "Les commentaires valent plus que les réactions.",
        "Le dimanche soir, la semaine se prépare.",
    ],
}
SENTENCES = [
    "Pendant des semaines, le même schéma s'est répété sans que personne ne le remarque.",
    "Le premier jet faisait trois paragraphes, la version publiée en garde un seul.",
    "La plupart des lecteurs décident en deux secondes s'ils vont cliquer sur voir plus.",
    "Un post qui explique un problème précis attire plus de messages qu'un post qui donne dix conseils.",
    "Les chiffres de la semaine montrent un écart net entre deux formats pourtant proches.",
    "Le sujet était bon, l'angle ne l'était pas : personne ne s'y reconnaissait.",
    "Une phrase courte en ouverture, puis une promesse tenue dans les lignes suivantes.",
    "Le carnet de notes du dimanche contient toujours trois idées de plus que nécessaire.",
    "Ce qui marche chez un autre créateur ne marche pas forcément chez soi.",
    "Les questions posées en commentaire deviennent souvent le post suivant.",
    "Un exemple concret vaut mieux qu'une règle générale, surtout sur un sujet technique.",
    "La relecture à froid, le lendemain matin, coupe en moyenne un tiers du texte.",
    "Le visuel attire l'oeil, mais c'est la première ligne qui garde le lecteur.",
    "Publier moins souvent, mais avec un vrai sujet, change la qualité des échanges.",
    "Un client potentiel lit rarement un post en entier : il cherche un signe qu'on le comprend.",
    "Les posts trop polis passent inaperçus, les posts trop vendeurs font fuir.",
    "La dernière phrase doit dire au lecteur quoi faire, pas résumer ce qu'il vient de lire.",
    "Un tableau simple permet de voir en un coup d'oeil ce qui a changé d'une semaine à l'autre.",
    "Le temps passé à écrire ne dit rien de la portée d'un post.",
    "Les sujets qui touchent au quotidien du lecteur reviennent dans les messages privés.",
]
ARROW_ITEMS = [
    "une idée par post", "une première ligne qui nomme le problème", "un exemple tiré du terrain",
    "une phrase de conclusion utile", "un seul appel à l'action", "des paragraphes de deux lignes au plus",
    "un chiffre vérifiable", "une réponse à chaque commentaire",
]
CTA_LINES = [
    "Commente GUIDE et je t'envoie la checklist.",
    "Commente « AUDIT » pour recevoir la grille.",
    "Écris MÉTHODE en commentaire, je t'envoie le modèle.",
    "Commente PACK si tu veux le fichier.",
]
NO_CTA_ENDINGS = [
    "Commente si tu veux la suite.",
    "Dis-moi en commentaire ce que tu en penses.",
    "",
    "",
]


def make_text(first, length_label, arrows, cta):
    """First line, filler sentences, optional arrow list and call to action, inside the length bucket."""
    lo, hi = LENGTH_RANGE[length_label]
    target = rng.randint(*LENGTH_TARGET[length_label])
    tail = []
    if arrows:
        tail.append("\n".join("→ " + item for item in rng.sample(ARROW_ITEMS, 3)))
    elif rng.random() < 0.3:
        tail.append("→ " + rng.choice(ARROW_ITEMS))  # a single arrow line is not a list
    ending = rng.choice(CTA_LINES) if cta else rng.choice(NO_CTA_ENDINGS)
    if ending:
        tail.append(ending)
    body = []

    def assemble():
        return "\n\n".join([first] + body + tail).strip()

    pool = SENTENCES[:]
    rng.shuffle(pool)
    i = 0
    while len(assemble()) < target:
        body.append(pool[i % len(pool)])
        i += 1
        if len(assemble()) >= hi:
            body.pop()
            break
    text = assemble()
    while len(text) < lo:  # still under the bucket: add short sentences
        body.append("Une ligne de plus.")
        text = assemble()
    assert lo <= len(text) < hi, (length_label, len(text))
    return text


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cells = [(hook, hour) for hook, row in DESIGN.items() for hour, k in row.items() for _ in range(k)]
    assert len(cells) == 40
    measured = []
    q = iter(QUESTION_VALUES)
    for hook, hour in cells:
        if hook == "question":
            imp = next(q)
        else:
            imp = round(BASE[hook] * HOUR_FACTOR[hour] * math.exp(rng.gauss(0, 0.4)))
        measured.append({"hook": hook, "hour": hour, "impressions": imp})
    # 2 posts without impressions: an empty cell and "n/a"
    unmeasured = [{"hook": "autre", "hour": MIDDAY, "impressions": ""},
                  {"hook": "je", "hour": MORNING, "impressions": "n/a"}]
    posts = measured + unmeasured

    # Formats, assigned at random with fixed counts (no planted effect)
    lengths = [SHORT] * 16 + [MEDIUM] * 18 + [LONG] * 8
    arrows = [True] * 14 + [False] * 28
    ctas = [True] * 13 + [False] * 29
    for lst in (lengths, arrows, ctas):
        rng.shuffle(lst)

    # 42 distinct days from 2026-08-29 to 2026-11-12, both ends included
    start, end = date(2026, 8, 29), date(2026, 11, 12)
    span = (end - start).days
    days = sorted([start, end] + rng.sample([start + timedelta(d) for d in range(1, span)], len(posts) - 2))
    order = list(range(len(posts)))
    rng.shuffle(order)

    hook_pool = {h: rng.sample(v, len(v)) for h, v in HOOKS.items()}
    hook_used = {h: 0 for h in HOOKS}
    time_pool = {h: v[:] for h, v in TIMES.items()}
    boundary_done = False
    for k, p in enumerate(posts):
        p["date"] = days[order[k]]
        if p["hour"] == MIDDAY and not boundary_done and p["impressions"] != "":
            p["time"] = "10:00"
            p["boundary"] = True
            boundary_done = True
        else:
            p["time"] = rng.choice(time_pool[p["hour"]])
            p["boundary"] = False
        pool = hook_pool[p["hook"]]
        p["first"] = pool[hook_used[p["hook"]] % len(pool)]
        hook_used[p["hook"]] += 1
        p["length"], p["arrows"], p["cta"] = lengths[k], arrows[k], ctas[k]
        p["text"] = make_text(p["first"], p["length"], p["arrows"], p["cta"])
        if isinstance(p["impressions"], int):
            p["reactions"] = max(0, round(p["impressions"] * rng.uniform(0.01, 0.04)))
            p["comments"] = max(0, round(p["reactions"] * rng.uniform(0.1, 0.5)) + (2 if p["cta"] else 0))
        else:
            p["reactions"], p["comments"] = "", ""

    posts.sort(key=lambda p: (p["date"], p["time"]))

    # Shape and planted effects must hold, or the case is wrong
    values = [p["impressions"] for p in posts if isinstance(p["impressions"], int)]
    overall = statistics.median(values)

    def med(**kw):
        return statistics.median([p["impressions"] for p in posts if isinstance(p["impressions"], int)
                                  and all(p[k] == v for k, v in kw.items())])

    assert len(values) == 40 and 80 <= overall <= 100, overall
    assert sum(20 <= v <= 120 for v in values) >= 24, "most posts between 20 and 120"
    assert 3 <= sum(300 <= v <= 650 for v in values) <= 6, "a few posts between 300 and 600"
    assert med(hook="je") >= 1.25 * overall and med(hook="tu") <= 0.75 * overall
    assert med(hour=MORNING) >= 1.25 * overall and med(hour=EVENING) <= 0.75 * overall
    assert med(hook="question") >= 3 * overall

    fields = ["date", "time", "text", "impressions", "reactions", "comments"]
    with (OUT / "posts.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for p in posts:
            w.writerow([p["date"].isoformat(), p["time"], p["text"], p["impressions"], p["reactions"], p["comments"]])
    as_json = [{k: (p[k].isoformat() if k == "date" else p[k]) for k in fields} for p in posts]
    (OUT / "posts.json").write_text(json.dumps(as_json, ensure_ascii=False, indent=1), encoding="utf-8")
    three = [p for p in posts if p["hook"] == "question"]
    with (OUT / "posts_3.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(fields)
        for p in three:
            w.writerow([p["date"].isoformat(), p["time"], p["text"], p["impressions"], p["reactions"], p["comments"]])

    truth = {
        "seed": SEED,
        "rows": len(posts),
        "posts": [{
            "post": i,
            "measured": isinstance(p["impressions"], int),
            "impressions": p["impressions"] if isinstance(p["impressions"], int) else None,
            "reactions": p["reactions"] if isinstance(p["impressions"], int) else None,
            "comments": p["comments"] if isinstance(p["impressions"], int) else None,
            "date": p["date"].isoformat(),
            "time": p["time"],
            "boundary": p["boundary"],
            "labels": {
                "hook": p["hook"],
                "length": p["length"],
                "arrows": "oui" if p["arrows"] else "non",
                "cta": "oui" if p["cta"] else "non",
                "weekday": DAYS[p["date"].weekday()],
                "hour": p["hour"],
            },
        } for i, p in enumerate(posts, 1)],
        "planted": [
            {"dimension": "Accroche", "group": "je", "direction": "above"},
            {"dimension": "Accroche", "group": "tu", "direction": "below"},
            {"dimension": "Heure", "group": MORNING, "direction": "above"},
            {"dimension": "Heure", "group": EVENING, "direction": "below"},
        ],
        "small_trap": {"dimension": "Accroche", "group": "question"},
    }
    (OUT / "truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(posts)} posts written to {OUT} ({len(values)} with impressions, median {overall:g})")


if __name__ == "__main__":
    main()
