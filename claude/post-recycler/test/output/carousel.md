8 agents Claude Code relisent ta PR avant ton lead.
Pour les devs qui veulent merger sans surprise.
---
Le piège : une app Django de facturation.
Une branche « ajouter une remise aux factures ».
8 défauts cachés dedans.
---
Secrets
Une clé Stripe en dur, ligne 24 de settings.py.
---
Dépendances et migrations
PyYAML 5.3.1, faille PYSEC-2021-142, importé nulle part.
Une migration qui casse sur une base remplie.
---
Tests et bugs
4 tests écrits, 2 échouent.
Une remise de 150 % donne un total de -500.
---
Requêtes
41 requêtes pour afficher 20 factures.
2 après correction.
---
Verdict : SHIP: STOP
4 défauts bloquants, 4 à corriger, avant le merge.
---
Commente SHIP et je t'envoie le lien en DM.
Gratuit, open source, licence MIT.
