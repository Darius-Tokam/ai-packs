Objet : Ce que 8 agents ont trouvé dans une PR piégée

Cette semaine, mon agent a piégé une pull request : une app Django de facturation et une branche « ajouter une remise aux factures », avec 8 défauts cachés dedans.

J'ai lancé 8 agents Claude Code avec une seule commande, /pr-squad:ship. Ce qu'ils ont trouvé :

- une clé Stripe en dur, ligne 24 de settings.py ;
- PyYAML 5.3.1, faille PYSEC-2021-142, importé nulle part ;
- une migration qui casse sur une base qui a des factures ;
- une remise de 150 % qui donne un total de -500 ;
- 41 requêtes pour afficher 20 factures, 2 après correction.

Verdict : SHIP: STOP, 4 défauts bloquants et 4 à corriger.

Lance-le sur ta prochaine branche avant de demander une review. Les agents ne modifient jamais ton code : seuls les tests qu'ils écrivent restent dans ton dépôt.

Le pack est gratuit et open source : github.com/Darius-Tokam/ai-packs

Réponds à ce courriel avec ce qu'il a trouvé chez toi.
