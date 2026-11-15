Mon agent a piégé une PR avec 8 défauts.
8 agents Claude Code les ont tous trouvés avant le merge.

Le piège : une app Django de facturation et une branche « ajouter une remise aux factures ». Dedans, une clé Stripe en dur, une migration qui casse sur une base remplie, une dépendance avec une faille connue, une requête N+1 et 4 autres pièges.

Une seule commande : /pr-squad:ship

Ce que chaque agent a trouvé :
→ Secrets : la clé Stripe, ligne 24 de settings.py
→ Dépendances : PyYAML 5.3.1, faille PYSEC-2021-142, importé nulle part
→ Migrations : rejouée sur une base qui a des factures, IntegrityError
→ Périmètre : un export CSV de tous les clients, sans rapport avec la remise
→ Tests : 4 tests écrits pour la nouvelle fonction, 2 échouent
→ Bugs : une remise de 150 % donne un total de -500
→ Requêtes : 41 requêtes pour afficher 20 factures, 2 après correction
→ Description de PR : écrite depuis le diff, DO NOT MERGE en première ligne

Verdict : SHIP: STOP. 4 défauts bloquants, 4 à corriger.

Ce que tu y gagnes : ta PR arrive chez ton lead sans clé en dur, sans migration qui casse en prod, avec ses tests. Tu corriges avant qu'on te le signale.

Dans le pack :
✅ les 8 agents, installés en 2 commandes dans Claude Code
✅ la commande /ship qui les lance dans l'ordre et rend un verdict
✅ le dépôt piège et le script de test, pour vérifier toi-même
✅ gratuit, open source, licence MIT

Commente SHIP et je t'envoie le lien en DM.

PS : les agents ne modifient jamais ton code. Seuls les tests qu'ils écrivent restent dans ton dépôt. Le détail du test, et sa limite, est dans le dépôt.
