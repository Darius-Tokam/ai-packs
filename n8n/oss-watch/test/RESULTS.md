# Résultats : oss-watch

Tests manuels du 22 novembre 2026. Workflow livré inactif. Exécutions finales 103 à 111, exécutions de mise au point 101 et 102 conservées dans ce rapport.

## Cas et résultats observés

12 dépendances inventées, 6 PyPI et 6 npm. Première semaine : licences stables. Deuxième semaine : 8 dépendances stables et 4 changements introduits : MIT vers BUSL-1.1, Apache-2.0 vers proprietary, licence absente et AGPL-3.0-only en contexte SaaS. Chaque dépendance produit deux requêtes, version installée et version récente. Les réponses HTTP sont simulées.

| Exécution | Cas | Dépendances | Alertes présentes | Nouveaux événements | Brouillons sauvegardés | Temps observé |
|---|---|---:|---:|---:|---:|---:|
| 101 | Premier contrôle avant renforcement du garde | 12 | 0 | 0 | 0 | 299 ms |
| 102 | Quatre alertes, garde initial | 12 | 4 | 4 | 1 | 14437 ms |
| 103 | État initial final | 12 | 0 | 0 | 0 | 265 ms |
| 104 | Deuxième semaine, quatre anomalies | 12 | 4 | 4 | 1 | 11260 ms |
| 105 | Même état relu, aucun nouveau brouillon | 12 | 4 | 0 | 0 | 282 ms |
| 106 | requirements.txt brut | 6 | 0 | 0 | 0 | 292 ms |
| 107 | package.json brut avec paquet npm à portée | 6 | 0 | 0 | 0 | 269 ms |
| 108 | Calendrier manuel, liste persistée relue | 6 | 0 | 0 | 0 | 256 ms |
| 109 | Sortie IA invalide épinglée | 12 | 4 | 4 | 0 | 302 ms |
| 110 | Version npm non exacte | 0 | 0 | 0 | 0 | 43 ms |
| 111 | Registre indisponible, HTTP 503 | 1 | 1 | 1 | 1 | 8610 ms |

Le passage 104 détecte les 4 anomalies prévues et aucune parmi les 8 dépendances stables. Un brouillon contient 4 propositions. Le modèle réel a appelé Consulter_les_preuves une fois et Choisir_une_correction deux fois, pour examiner et clarifier. Le passage 105 garde 4 anomalies dans le diagnostic mais 0 nouvelle alerte et 0 appel IA.

Le contrôle 109 refuse le statut ENVOYE, les références absentes et l'absence d'outils. Il rend A_REPRENDRE, sans enregistrer de brouillon ni consommer les empreintes. Le passage 110 est une erreur attendue dès l'entrée. Le passage 111 produit une proposition de vérification, pas un faux diagnostic de licence autorisée.

## Mise au point

101 et 102 validaient les premières règles. L'exécution 102 consultait la procédure examiner, mais pas clarifier pour l'élément qui en avait besoin. Le garde a été renforcé : il vérifie désormais les observations des outils pour chaque preuve et chaque action choisie. 103 à 111 portent sur ce garde. Dans 104, le modèle écrit « proprietay » une fois dans sa proposition : erreur de forme non bloquée, qui illustre le besoin de relecture humaine. Les faits structurés conservent proprietary. Le contrôle mécanique ne garantit pas la qualité éditoriale.

## Nombre d'éléments par nœud et sortie

Les listes donnent les sorties principales dans l'ordre n8n. Pour le IF : [vrai, faux]. Une liste vide à l'exécution 110 indique que l'entrée a échoué avant de produire des éléments.

| Nœud | 103 | 104 | 105 | 106 | 107 | 108 | 109 | 110 | 111 |
|---|---|---|---|---|---|---|---|---|---|
| Recevoir les données | [1] | [1] | [1] | [1] | [1] | non exécuté | [1] | [1] | [1] |
| Vérifier les dépendances | [1] | [1] | [1] | [1] | [1] | [1] | [1] | [] | [1] |
| Lire le suivi | [1] | [1] | [1] | [1] | [1] | [1] | [1] | non exécuté | [1] |
| Préparer le contexte | [1] | [1] | [1] | [1] | [1] | [1] | [1] | non exécuté | [1] |
| Préparer les requêtes | [24] | [24] | [24] | [12] | [12] | [12] | [24] | non exécuté | [2] |
| Lire les sources publiques | [24] | [24] | [24] | [12] | [12] | [12] | [24] | non exécuté | [2] |
| Évaluer les faits | [1] | [1] | [1] | [1] | [1] | [1] | [1] | non exécuté | [1] |
| Un nouveau brouillon est utile | [0,1] | [1,0] | [0,1] | [0,1] | [0,1] | [0,1] | [1,0] | non exécuté | [1,0] |
| Préparer l’enregistrement | [1] | [2] | [1] | [1] | [1] | [1] | [1] | non exécuté | [2] |
| Conserver le brouillon et le suivi | [1] | [2] | [1] | [1] | [1] | [1] | [1] | non exécuté | [2] |
| Rendre le résultat | [1] | [1] | [1] | [1] | [1] | [1] | [1] | non exécuté | [1] |
| Modèle à configurer | non exécuté | [] | non exécuté | non exécuté | non exécuté | non exécuté | non exécuté | non exécuté | [] |
| Consulter_les_preuves | non exécuté | [] | non exécuté | non exécuté | non exécuté | non exécuté | non exécuté | non exécuté | [] |
| Choisir_une_correction | non exécuté | [] | non exécuté | non exécuté | non exécuté | non exécuté | non exécuté | non exécuté | [] |
| Agent : Préparer la revue des licences | non exécuté | [1] | non exécuté | non exécuté | non exécuté | non exécuté | [1] | non exécuté | [1] |
| Contrôler le brouillon | non exécuté | [1] | non exécuté | non exécuté | non exécuté | non exécuté | [1] | non exécuté | [1] |
| Contrôler au calendrier | non exécuté | non exécuté | non exécuté | non exécuté | non exécuté | [1] | non exécuté | non exécuté | non exécuté |

Les sous-nœuds IA sont décrits par les traces d'outils, pas comme des sorties main. Passage 104 : modèle non épinglé, 3 appels d'outils. Passage 111 : modèle non épinglé, 2 appels d'outils. Passage 109 : réponse de l'agent volontairement épinglée, aucun appel modèle.

## Chiffres du post et du visuel

Le pack Claude oss-check comporte 2 agents. Source : README.md et test/RESULTS.md du pack Claude construit le 19 novembre 2026, bundle 08-auto/flux-linkedin/stock/oss-check.bundle. Son script retrouve 36 verdicts attendus sur 36 sur 9 dépôts reconstitués. Ces mesures proviennent du test de Claude, pas de ces exécutions n8n. Elles ne sont ni une mesure d'exactitude juridique ni un test des agents Claude sur des projets réels. Les poids de certains dépôts sont reproduits par construction et ne sont pas utilisés dans le post.

## Limite du test

- Registres HTTP simulés, aucune dépendance réelle installée. Les appels réseau publics et leurs quotas ne sont pas mesurés.
- Le modèle configuré sur l'instance a réellement exécuté 104 et 111. La qualité n'est évaluée que sur ces cas inventés.
- Le webhook est configuré avec headerAuth. Les tests MCP épinglent le déclencheur : le refus HTTP sans en-tête n'a pas été testé. Il reste à vérifier après configuration locale du secret.
- Le calendrier a été déclenché manuellement en 108. Aucun déclenchement automatique réel, workflow toujours inactif.
- Le JSON, requirements.txt et package.json ont été exécutés. CSV implémenté mais pas rejoué sur l'instance dans cette série.
- Les métadonnées des auteurs peuvent être fausses ou incomplètes. Les licences composites et inconnues sont à clarifier. Aucune conclusion juridique automatisée.
- Les fichiers verrouillant les versions et les dépendances transitives ne sont pas résolus. Versions exactes seulement, maximum 50 dépendances par liste.
- Déduplication limitée aux 10000 empreintes conservées. Les appels concurrents d'un même scope ne sont pas transactionnels : les sérialiser.
- Tests et workflow conçus par Codex ; aucune revue indépendante. Les durées sont ponctuelles, pas une promesse de performance.
- Les traces sont désactivées pour les prochaines exécutions. Les anciennes exécutions simulées restent disponibles sur l'instance pour relecture.

Les cas complets et les comptes de sorties sont fournis dans cases.json et mesures.json.
