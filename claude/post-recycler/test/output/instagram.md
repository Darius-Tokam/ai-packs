Une PR piégée avec 8 défauts. Les 8 trouvés avant le merge.

Une app Django de facturation, une branche « ajouter une remise aux factures », et 8 agents Claude Code lancés avec une seule commande.
→ une clé Stripe en dur, ligne 24
→ PyYAML 5.3.1 avec une faille connue
→ une migration qui casse sur une base remplie
→ une remise de 150 % qui donne -500
→ 41 requêtes pour 20 factures, 2 après correction

Verdict : SHIP: STOP.
Gratuit et open source. Commente SHIP et je t'envoie le lien en DM.

#claudecode #django #codereview #pullrequest #devtools
