"""Rebuild the quote-check test: one quote with planted defects, two clean quotes.

    python build_case.py /tmp/quote-cases

a-platform-booking rebuilds the shape of the author's case (a platform with a
booking module estimated at 12 h, a 40 h quote at 75 $/h, a client abroad);
every name, amount and line of the brief is invented. b-platform-fixed is the
same brief with a corrected quote. c-studio-en is a clean quote in English.
expected.json lists the findings the script must return. Standard library only.
"""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/quote-cases")

BRIEF_A = """Bonjour Alex,

Je lance une plateforme pour mes ateliers en ligne. Voici ce dont j'ai besoin :

- Mes clientes doivent pouvoir s'inscrire et avoir leur espace client.
- Elles réservent leurs séances en ligne. J'ai des clientes au Québec et en France.
- Une séance peut être annulée ou reportée jusqu'à 48 h avant, avec remboursement.
- Le paiement se fait en ligne par carte de crédit.
- Un courriel de rappel automatique part 24 h avant chaque séance.
- Mes deux animatrices doivent avoir leur propre accès pour voir leurs séances.
- J'ai besoin d'un tableau de bord pour gérer les réservations.
- Le site doit être en français et en anglais.
- Il faut reprendre mes 300 clientes de mon fichier Excel.
- La mise en ligne est comprise, sur mon nom de domaine.

Mon budget est d'environ 3 000 $. Merci !
Camille
"""

QUOTE_A = """# Devis : plateforme d'ateliers en ligne

| Poste | Heures | Taux | Montant |
|---|---|---|---|
| Maquettes et intégration des pages | 10 | 75 | 750,00 |
| Inscription et espace client | 8 | 75 | 650,00 |
| Module de réservation | 12 | 75 | 900,00 |
| Tableau de bord | 6 | 75 | 450,00 |
| Mise en ligne | 4 | 75 | 300,00 |

Sous-total : 3 050,00 $
TPS (5 %) : 152,50 $
TVQ (9,975 %) : 289,75 $
Total : 3 492,25 $
"""

QUOTE_B = """# Devis : plateforme d'ateliers en ligne (corrigé)

| Poste | Heures | Taux | Montant |
|---|---|---|---|
| Maquettes et intégration des pages | 10 | 75 | 750,00 |
| Inscription, espace client et accès séparés pour les animatrices (rôles) | 10 | 75 | 750,00 |
| Module de réservation (fuseaux horaires Québec et France, annulation et report jusqu'à 48 h) | 24 | 75 | 1 800,00 |
| Paiement en ligne par carte, avec remboursement à l'annulation | 10 | 75 | 750,00 |
| Courriels de rappel automatiques 24 h avant | 4 | 75 | 300,00 |
| Tableau de bord | 6 | 75 | 450,00 |
| Site bilingue, en français et en anglais | 8 | 75 | 600,00 |
| Import des 300 clientes depuis le fichier Excel | 4 | 75 | 300,00 |
| Mise en ligne sur le nom de domaine | 4 | 75 | 300,00 |

Sous-total : 6 000,00 $
TPS (5 %) : 300,00 $
TVQ (9,975 %) : 598,50 $
Total : 6 898,50 $
"""

BRIEF_C = """Hi Alex,

I run a small yoga studio. I need a website where students can book a class online and pay online with Stripe.
The site must be in French and English. Please include hosting on my domain name.

Thanks,
Jordan
"""

QUOTE_C = """# Quote: studio website

| Item | Hours | Rate | Amount |
|---|---|---|---|
| Website design and pages | 12 | 90 | 1,080.00 |
| Class booking calendar | 10 | 90 | 900.00 |
| Stripe checkout | 6 | 90 | 540.00 |
| French and English versions | 6 | 90 | 540.00 |
| Hosting setup and go live | 3 | 90 | 270.00 |

Subtotal: 3,330.00
Total: 3,330.00
"""

CASES = {
    "a-platform-booking": {"brief": BRIEF_A, "quote": QUOTE_A, "taxes": {"TPS": 5, "TVQ": 9.975},
                           "expected": ["math-line", "math-tax", "missing-payment", "missing-notifications",
                                        "missing-multilingual", "missing-import", "hidden-booking-fuseaux",
                                        "hidden-booking-annulation", "hidden-accounts-rôles"],
                           "hours": 40, "hours_range": [44.0, 60.0]},
    "b-platform-fixed": {"brief": BRIEF_A, "quote": QUOTE_B, "taxes": {"TPS": 5, "TVQ": 9.975},
                         "expected": [], "hours": 80, "hours_range": None},
    "c-studio-en": {"brief": BRIEF_C, "quote": QUOTE_C, "taxes": {}, "expected": [], "hours": 37, "hours_range": None},
}

ROOT.mkdir(parents=True, exist_ok=True)
expected = []
for name, c in CASES.items():
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "brief.md").write_text(c["brief"], encoding="utf-8")
    (d / "quote.md").write_text(c["quote"], encoding="utf-8")
    expected.append({"case": name, "taxes": c["taxes"], "expected": c["expected"],
                     "hours": c["hours"], "hours_range": c["hours_range"]})
(ROOT / "expected.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"{len(CASES)} cases written to {ROOT}")
