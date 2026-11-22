# Guide : oss-watch

## Importer sur n8n Cloud ou sur son serveur

Importer workflow.json depuis le menu de l'éditeur. Il contient [Codex] oss-watch, laissé inactif, sans compte, secret ni identifiant d'instance. Un nœud AI Agent et deux outils sont intégrés. Le modèle suggéré est gpt-5-mini ; le modifier dans Modèle à configurer selon son compte et son budget. Aucun service de courriel n'est nécessaire.

Dans le même projet n8n, créer une Data Table nommée Codex_oss_watch_registre avec trois colonnes texte : key, kind, payload. Sélectionner cette table dans Lire le suivi et Conserver le brouillon et le suivi si l'import ne résout pas son nom. key distingue l'état et les brouillons. Les données sont conservées sur votre instance.

## Configurer les accès

Sur Cloud, créer le credential OpenAI depuis Modèle à configurer et saisir sa propre clé dans n8n. Dans Recevoir les données, choisir Header Auth, créer un secret aléatoire et le conserver dans le gestionnaire de secrets du client qui appellera le webhook. Le même en-tête sera envoyé à chaque requête. Ne pas copier ce secret dans un JSON, une note ou ce guide.

Sur un serveur personnel, mêmes credentials dans l'interface. Exposer le webhook uniquement en HTTPS et protéger la clé de chiffrement de n8n et ses sauvegardes. Les registres PyPI et npm ne demandent aucun credential. Le message générique du créateur MCP sur les HTTP Request ne signifie pas qu'un compte est nécessaire : ces nœuds utilisent authentication none.

Aucun compte Gmail, Slack, Stripe ou autre n'est à connecter. La sortie est un brouillon interne soumis à validation humaine, jamais un message envoyé.

## Entrées et réglages

Le webhook reçoit un POST. La forme recommandée est celle de test/cases.json, champ entree. usage vaut perso, interne, saas ou redistribution. deps contient ecosystem (pypi ou npm), name et version. Une liste JSON nue est aussi acceptée. La limite est de 50 dépendances, avec versions exactes.

Autres formes :

- Corps texte de requirements.txt, une dépendance nom==version par ligne. Commentaires autorisés. Extras, URL, marqueurs et plages de versions refusés.
- Corps JSON de package.json avec dependencies et devDependencies. ^, ~, latest, git et chemins locaux sont refusés ; exporter les versions installées exactes avant l'appel.
- Objet contenant requirements ou packageJson pour joindre usage et scope.
- Objet avec csv : texte CSV dont les colonnes sont ecosystem,name,version. Cette variante est implémentée mais n'a pas été rejouée sur l'instance dans cette série.

Le scope par défaut est principal. Le calendrier du lundi à 7h, fuseau America/Toronto, ne relit que ce scope. Pour un autre projet, appeler le webhook avec son scope depuis son propre calendrier. Il faut modifier explicitement l'entrée du calendrier pour surveiller un autre scope. Une nouvelle liste remplace la liste précédente du même scope. Les autres réglages, notamment usage, sont conservés s'ils sont absents ; les préciser pour les changer.

Le champ testNow sert aux tests. Le retirer pour un usage réel. Ne pas ajouter de client, de secret, ni de données personnelles : seule la liste des paquets est utile.

## Premier lancement manuel avec les cas simulés

1. Laisser le workflow inactif. Sélectionner les credentials dans l'éditeur.
2. Épingler Recevoir les données avec un item dont json.body vaut l'objet entree de test/cases.json. Utiliser un scope de test neuf si l'on veut rejouer les mêmes alertes.
3. Épingler Lire les sources publiques avec les 24 items semaine1. Chaque entrée est déjà enveloppée dans json. Ne pas épingler le modèle ni les outils.
4. Lancer manuellement. Résultat attendu : 12 dépendances et 0 alerte.
5. Remplacer les réponses HTTP par semaine2, garder le même scope, puis relancer. Attendu : 4 nouvelles alertes, 1 brouillon contenant 4 propositions. L'agent consulte les preuves et les procédures. Le contrôle exige des références complètes, des actions compatibles, des chiffres et des URL présents dans les preuves.
6. Relancer avec semaine2 sans modification. Attendu : 0 nouvelle alerte et aucun nouveau brouillon. Les 4 anomalies restent visibles dans mesures.
7. Lire les brouillons dans la Data Table, lignes kind=brouillon. Le texte du modèle reste à relire, même lorsque controle.accepted vaut true.

Pour rejouer les cas complémentaires, utiliser requirements.txt et package.json avec leurs réponses respectives de cases.json. Les tests 109 et 110 illustrent les refus attendus. Aucun script d'installation ou commande de réseau externe n'est nécessaire pour ces tests manuels.

## Tester ensuite un webhook réel

Retirer les données épinglées et cliquer Listen for test event. Envoyer une petite liste de paquets publics vers l'URL de test copiée dans votre éditeur, avec l'en-tête défini dans le credential. Contrôler séparément qu'une requête sans en-tête est refusée. Ce contrôle d'authentification n'a pas été réalisé dans les tests MCP livrés.

Ne pas utiliser les noms inventés des fixtures avec les registres réels : ils serviront seulement à vérifier la gestion des paquets introuvables. Les données épinglées simulent les registres ; elles ne prouvent pas leur disponibilité.

## Activation, seulement par le propriétaire

Le rendu reste inactif. Après vos essais, retirer tous les épinglages, saisir la vraie liste dans le scope principal, confirmer usage, horaire et fuseau. Vous pourrez ensuite activer depuis votre interface si vous le décidez. Le calendrier relira la dernière liste validée. Aucune action d'envoi n'est incluse, même après activation.

## Comprendre les résultats

SANS_NOUVELLE_ALERTE signifie qu'aucun brouillon neuf n'est utile, pas que toutes les licences sont sans contrainte. BROUILLON_A_VALIDER contient les propositions de l'agent. A_REPRENDRE signifie que le garde a refusé sa sortie ; les événements ne sont pas consommés, un nouveau lancement peut les retraiter.

Les métadonnées installées et récentes sont comparées à l'observation précédente. Une nouvelle licence ne modifie pas automatiquement celle d'une version déjà installée. AGPL avec usage SaaS, expressions composites, licences inconnues ou conditions spécifiques demandent une revue, sans conclusion juridique automatisée.

## Erreurs fréquentes

- Aucune liste enregistrée : envoyer une liste au scope principal avant le calendrier.
- Versions avec ^ ou ~ : transmettre les versions exactes installées, pas une plage.
- Table introuvable : créer la table dans le même projet et la sélectionner dans les deux nœuds.
- Licence inconnue : retrouver le LICENSE de la version concernée. Une absence n'est pas une permission.
- HTTP 404, 429 ou 503 : l'agent prépare une vérification. Réduire la liste, attendre et relancer. Le workflow n'efface pas la dernière licence connue sur une erreur réseau. Il n'installe rien et n'épingle aucune version.
- Modèle sans crédit ou trop lent : renseigner votre clé, vérifier les quotas et choisir un modèle capable d'utiliser des outils. Le délai modèle est de 90 secondes, le workflow de 300 secondes.
- A_REPRENDRE : consulter controle.errors. Une sortie sans preuves, sans procédure consultée ou avec une référence inventée est refusée. Retester, puis relire avant tout usage.
- Appels simultanés : les sérialiser par scope. La Data Table ne fournit pas une réservation transactionnelle pour cette déduplication.

Les traces sont désactivées dans le fichier livré. Pour déboguer des données simulées, activer temporairement la conservation des exécutions manuelles dans les réglages, puis la désactiver. Aucun secret ne doit apparaître dans les données de test.

## Sources officielles lues le 22 novembre 2026

- https://docs.n8n.io/data/data-tables/ : persistance et marqueurs.
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/ : URL de test, réponse et authentification.
- https://docs.pypi.org/api/json/ : métadonnées d'un projet et d'une version.
- https://github.com/npm/registry/blob/main/docs/REGISTRY-API.md : endpoints du registre npm.

Les schémas des nœuds et le code SDK ont également été validés par le MCP n8n avant création. Les instructions d'activation décrivent une action future du propriétaire, non effectuée par Codex.
