# Résultats du test : crash-triage sur 21 événements

Test du 14 novembre 2026. Rejouable avec Python 3.10 ou plus et Node.js (jq en plus pour le contrôle de la commande du guide) :

```bash
python build_events.py /tmp/crash-cases
python run_checks.py /tmp/crash-cases
```

`run_checks.py` exécute les nœuds **Lire l'entrée**, **Lignes Railway** et **Nommer la cause** tels qu'ils sont dans [workflow.json](../workflow.json), grâce à [harness.js](harness.js). La sortie complète du dernier passage est dans [run_output.txt](run_output.txt).

## D'où viennent les cas

Le sujet vient d'une tâche qui revient chez l'auteur : lire les logs d'un déploiement qui a « planté ». En juillet 2026, Railway lui envoyait un mail « Deployment crashed » à chaque redéploiement de son serveur MCP, alors que l'app s'arrêtait normalement : npm, lancé en PID 1, transformait le SIGTERM en échec. Le skill deploy-doctor nomme la cause quand on le lui demande ; ce workflow fait le tri au moment où l'alerte arrive.

Les 11 logs sont ceux du test de deploy-doctor ([claude/deploy-doctor/test](../../../claude/deploy-doctor/test)). Quatre reconstituent des incidents de l'auteur, d'après ses notes, avec des noms inventés : npm en PID 1 (juillet 2026), un cron qui appelle `python` (juin 2026), `ALLOWED_HOSTS` absent et une prod Django en réglages de développement (juin 2026).

- **Entrée Railway, 15 cas** : les 11 logs envoyés comme des pannes annoncées par Railway (l'événement suit la forme documentée par Railway : `type`, `details`, `resource`, `severity`, `timestamp` ; les lignes suivent la réponse de la requête GraphQL `deploymentLogs`), plus un déploiement réussi, un projet absent de `projets_suivis`, une panne au log vide et un jeton refusé par l'API (`Not Authorized`).
- **Entrée générique, 6 cas** : ce qu'enverrait une CI, un script ou Docker. Un log en texte (npm en PID 1), un log en liste de lignes (module manquant), un arrêt propre de gunicorn, un log sain sans explication, une requête sans log, et un projet non suivi.

## Résultats mesurés

| Mesure | Résultat |
|---|---|
| Pannes dont la cause est l'une des 8 connues (les deux entrées) | 10 sur 10 nommées, chacune avec la ligne du log qui la prouve, le correctif et la vérification |
| Variable ou module nommé dans le correctif (`ALLOWED_HOSTS`, `whitenoise`) | 3 sur 3 |
| Arrêts normaux sur SIGTERM (Node, gunicorn) | 3 sur 3 sans courriel |
| Log sain sans preuve d'arrêt normal | 2 sur 2 en « cause non reconnue », avec les dernières lignes, aucune cause inventée |
| Log vide, côté Railway et côté générique | 2 sur 2 en « aucune ligne de log », avec ce qu'il faut vérifier |
| Jeton refusé par l'API Railway | courriel « Railway a refusé la lecture des logs », qui nomme le nœud à vérifier |
| Déploiement réussi, projets non suivis | 3 sur 3 ignorés, aucun appel à l'API |
| Cas réussis par entrée | Railway 15 sur 15, générique 6 sur 6 |
| Même cause que le script de deploy-doctor | 15 sur 15 (contrôle fait dans un dépôt qui contient les deux packs) |
| Commande `jq` du guide, rejouée sur le log du cas npm | le corps produit passe par l'entrée générique et donne la même cause |
| Identifiants ou ID d'instance dans `workflow.json` | aucun |
| Tirets longs ou moyens dans le pack | 0 |

Dans n8n (version 2.47.4, instance de l'auteur), avec des données simulées pour les webhooks, l'API Railway et Gmail :

| Exécution | Version | Entrée | Cas | Branche suivie |
|---|---|---|---|---|
| 16 | Railway seul | Railway | npm en PID 1 | **M'envoyer la cause**, cause `npm-pid1-sigterm`, preuve ligne 8 |
| 17 | Railway seul | Railway | arrêt propre de Node | **Arrêt normal, rien à envoyer** |
| 18 | Railway seul | Railway | jeton refusé | **M'envoyer la cause**, « Railway a refusé la lecture des logs » |
| 19 | deux entrées | générique | module manquant, log en liste | **M'envoyer la cause**, cause `missing-dependency`, preuve ligne 3 |
| 20 | deux entrées | générique | arrêt propre de gunicorn | **Arrêt normal, rien à envoyer** |
| 21 | deux entrées | Railway | npm en PID 1 | **Lignes Railway**, puis **M'envoyer la cause** |

Aucun vrai courriel n'est parti : le nœud Gmail était simulé.

## Limite du test

Le même agent a écrit le workflow, construit les cas et lancé les contrôles : les cas ne sont pas à l'aveugle, et 10 sur 10 dit seulement que les signatures reconnaissent les pannes pour lesquelles elles ont été écrites. Aucune vraie requête n'a été reçue : ni webhook Railway, ni envoi depuis une vraie CI. Côté Railway, l'événement suit l'exemple de la documentation (qui ne montre que le type `Deployment.failed` ; le nom `Deployment.crashed` des cas de test est une hypothèse, et le filtre accepte aussi le statut `CRASHED` ou `FAILED`), et la requête `deploymentLogs` vient d'une réponse du forum de Railway, pas de la référence de l'API. Côté générique, le format (`service`, `log` ou `lines`) est celui du pack : la commande `jq` du guide a été rejouée, l'étape GitHub Actions et la commande Docker n'ont pas tourné dans une vraie CI. À vérifier au premier branchement réel : la forme exacte de l'événement d'une panne chez Railway, l'ordre des lignes rendues par `deploymentLogs`, et qu'un jeton d'équipe suffit. Le workflow ne lit pas le log de build de Railway. Un log sain sans preuve d'arrêt normal déclenche un courriel : c'est voulu, le workflow ne se tait que sur une preuve. Les logs de test sont courts ; un vrai log mélange démarrage et requêtes, et sa première erreur n'est pas toujours la cause.
