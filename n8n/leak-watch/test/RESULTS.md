# Tests de leak-watch

Séance du 21 novembre 2026 à Toronto, exécutions horodatées le 22 novembre en UTC. Mode manual, données inventées, workflow inactif. Modèle réel : gpt-5-mini. Aucune réponse d’agent épinglée pour les cas fonctionnels. Les essais n’ont envoyé aucun message.

| Exécution | Cas | Mesuré | Statut |
|---|---|---|---|
| 88 | Premier essai de compatibilité | Module crypto refusé par le moteur n8n ; aucune action visible | Corrigé par un SHA-256 autonome |
| 89 | Deux formes de secrets sur trois lignes | 2 fuites, preuves consultées, procédure choisie, brouillon accepté | PASS |
| 90 | Même clé fictive répétée sur 150 lignes | 150 occurrences, 1 fuite distincte, 1 brouillon, 2 outils consultés | PASS |
| 91 | Rejeu exact de 90 | 0 nouvel événement, 0 brouillon, 0 appel d’outil IA | PASS |
| 92 | Journal propre et pièges | 12 lignes, 0 fuite, 0 brouillon, 0 appel d’outil IA | PASS |
| 93 | Sortie d’agent volontairement invalide, simulée pour éprouver le contrôle | statut ENVOYE refusé, absence de consultation des outils refusée, 0 brouillon | PASS |

Les mesures détaillées, les durées et les sorties masquées sont dans mesures.json. Les cas sont produits par cases.py. Les registres ont réellement été lus et écrits : ils ne sont pas simulés. Les nœuds du modèle et des outils n’ont pas été épinglés pendant 89 et 90. Le test 93 concerne exclusivement la barrière de contrôle et ne constitue pas un test du modèle.

Durées complètes : 89 = 12894 ms ; 90 = 11409 ms ; 91 = 208 ms ; 92 = 257 ms ; 93 = 237 ms. Une seule mesure par cas, pas une garantie de performance.

## Chiffres du pack Claude utilisés dans le post

Source relue : miroir du dépôt ai-packs, branche stock/leak-scan, claude/leak-scan/test/RESULTS.md, test de Claude daté du 17 novembre 2026. Le script y mesure 10 fuites sur 10 dans un journal reconstitué de 2 021 lignes, 0 fausse alerte sur 102 lignes pièges. Ces chiffres appartiennent au script leak-scan. Ils ne sont pas présentés comme les résultats du workflow n8n.

## Limites

Le test manuel simule l’appel webhook ; le transport HTTP et Header Auth ne sont pas validés par ces exécutions. Aucun journal réel ni compte client n’a été utilisé. Les cas sont connus du développeur. Le bonus déduplique les valeurs par source et type ; le script Claude regroupe aussi certaines signatures par origine, donc leurs nombres de fuites ne sont pas interchangeables. L’intégralité des 2 021 lignes de référence n’a pas été rejouée dans n8n. Aucun test de charge, de concurrence, de panne du modèle ou de conservation du proxy n’a été fait. Le filtre ne garantit pas la détection de secrets encodés, multilignes ou inconnus. Le contrôle structurel ne garantit pas la qualité sémantique du correctif proposé. Le brouillon doit être relu.

Après les essais, la conservation des exécutions a été désactivée dans le workflow et dans l’export. Les données des essais étaient fictives.
