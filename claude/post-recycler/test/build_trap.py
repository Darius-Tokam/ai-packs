"""Build the post-recycler trap: the 10 tested formats with 8 planted defects.

    python build_trap.py /tmp/recycle-trap

Copies output/ and source.md, then breaks 8 formats, one defect each.
video-script and story stay clean: the guard must pass them (no false alarm).
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/recycle-trap").resolve()
if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(HERE / "output", OUT / "formats")
shutil.copy(HERE / "source.md", OUT / "source.md")
F = OUT / "formats"


def edit(name, fn):
    p = F / f"{name}.md"
    p.write_text(fn(p.read_text(encoding="utf-8")), encoding="utf-8")


# 1. X post over 280 characters
edit("x-post", lambda t: t.replace("Une commande : /pr-squad:ship",
     "Une commande : /pr-squad:ship. Le dépôt piège, le script de test et les 8 agents sont dedans, "
     "installés en 2 commandes dans Claude Code, licence MIT"))
# 2. one thread post over 280 characters
edit("x-thread", lambda t: t.replace("Requêtes : 41 pour afficher 20 factures, 2 après correction.",
     "Requêtes : 41 pour afficher 20 factures, 2 après correction. Périmètre : un export CSV de tous les clients, "
     "sans rapport avec la remise. Description de PR : écrite depuis le diff, DO NOT MERGE en première ligne."))
# 3. Threads post under 500 characters but over 500 UTF-8 bytes (accents count double)
threads = ("Une PR Django piégée avec 8 défauts : clé Stripe écrite en dur, migration qui échoue dès qu'une base a déjà "
           "des factures, dépendance périmée et fragile, requête N+1 répétée à chaque écran, périmètre élargi à un "
           "export CSV étranger à la remise, tests créés à la hâte et déjà rouges, remise à 150 % générée sans contrôle. "
           "Les 8 agents Claude Code ont tout relevé avant le merge, dépôt piège à l'appui.\n"
           "Toi, tu fais relire ta branche avant la PR, ou tu laisses ton lead trouver ?")
assert len(threads) <= 500 < len(threads.encode("utf-8")), (len(threads), len(threads.encode("utf-8")))
(F / "threads.md").write_text(threads + "\n", encoding="utf-8")
# 4. Bluesky with an invented number
edit("bluesky", lambda t: t.replace("8 défauts plantés, 8 trouvés.",
     "8 défauts plantés, 8 trouvés, 73 % plus vite qu'une review humaine."))
# 5. a carousel slide over 30 words
edit("carousel", lambda t: t.replace("8 défauts cachés dedans.",
     "8 défauts cachés dedans, de la clé Stripe écrite en dur jusqu'à la migration qui casse sur une base remplie, "
     "en passant par une requête N+1 et une dépendance avec une faille connue."))
# 6. Instagram with 9 hashtags
edit("instagram", lambda t: t.replace("#devtools", "#devtools #python #coding #developer #programming"))
# 7. newsletter subject over 60 characters
edit("newsletter", lambda t: t.replace("Objet : Ce que 8 agents ont trouvé dans une PR piégée",
     "Objet : Ce que 8 agents Claude Code ont trouvé dans une pull request Django piégée"))
# 8. quote card with a long dash
edit("quote-card", lambda t: t.replace("-500. Un agent", "-500 " + chr(0x2014) + " un agent"))

expected = {
    "x-post": "X limit is 280", "x-thread": "X limit is 280", "threads": "UTF-8 bytes",
    "bluesky": "numbers not in the source: 73", "carousel": "the pack allows 30",
    "instagram": "9 hashtags", "newsletter": "subject", "quote-card": "long or medium dash",
}
(OUT / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"wrote {OUT}/formats (10 formats, 8 planted defects), source.md, expected.json")
