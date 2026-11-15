1/6 Mon agent a piégé une PR avec 8 défauts. 8 agents Claude Code les ont tous trouvés avant le merge. Voici ce que chacun a vu.
---
2/6 Le piège : une app Django de facturation et une branche « ajouter une remise aux factures ». Une seule commande pour tout vérifier : /pr-squad:ship
---
3/6 Secrets : une clé Stripe en dur, ligne 24 de settings.py.
Dépendances : PyYAML 5.3.1, faille PYSEC-2021-142, importé nulle part.
Migrations : rejouée sur une base remplie, IntegrityError.
---
4/6 Tests : 4 tests écrits, 2 échouent.
Bugs : une remise de 150 % donne un total de -500.
Requêtes : 41 pour afficher 20 factures, 2 après correction.
---
5/6 Verdict : SHIP: STOP. 4 défauts bloquants, 4 à corriger. Ta PR arrive chez ton lead sans clé en dur et avec ses tests.
---
6/6 Gratuit, open source, licence MIT. Le dépôt piège et le script de test sont inclus : github.com/Darius-Tokam/ai-packs
