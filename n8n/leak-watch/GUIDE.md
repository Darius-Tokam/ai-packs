# Installer leak-watch

## Import sur n8n Cloud

1. Créer un workflow vide, utiliser Import from file et choisir workflow.json. Garder le workflow désactivé.
2. Dans le même projet, créer une Data Table nommée Codex_leak_watch_registre, avec trois colonnes texte : key, kind, payload. Les colonnes techniques sont ajoutées par n8n.
3. Ouvrir Lire le suivi et Conserver le brouillon et le suivi. La sélection utilise le nom de table. Si nécessaire, sélectionner cette table dans la liste.
4. Dans Modèle à configurer, créer ou sélectionner sa propre connexion OpenAI. La clé se saisit uniquement dans les Credentials de n8n. Le modèle testé est gpt-5-mini, Chat Completions, effort faible, sans température imposée. Une autre version doit être retestée avec les outils.
5. Dans Recevoir les données, garder Header Auth et créer une connexion Header Auth. Choisir un nom d’en-tête, par exemple X-Webhook-Key, et une valeur aléatoire propre à son instance. Ne mettre cette valeur ni dans le workflow JSON ni dans un dépôt.

## Installation sur serveur

Utiliser une version de n8n offrant AI Agent 3.1, Code Tool 1.3, OpenAI Chat Model 1.3 et Data Table 1.1. Le workflow a été créé et exécuté sur ces versions de nœuds. Créer la table et les connexions dans le même projet comme sur Cloud. Le code de calcul SHA-256 n’exige aucun module externe, accès disque ou variable d’environnement. Le serveur doit pouvoir joindre le fournisseur du modèle en HTTPS. Une URL publique HTTPS et les réglages habituels de reverse proxy de n8n sont nécessaires pour recevoir les webhooks externes.

## Premier lancement manuel

1. Générer une entrée fictive avec python test/cases.py boucle. Le programme écrit le JSON sur la sortie standard. Ne pas utiliser un journal réel pour ce premier essai.
2. Ouvrir Recevoir les données, cliquer Listen for test event. Utiliser la Test URL affichée dans son instance, en POST, Content-Type application/json, avec l’en-tête configuré. Aucune activation n’est nécessaire pour ce test.
3. Copier le JSON généré dans le corps de la requête. Le workflow doit produire un brouillon à valider. Lire le résultat et la ligne brouillon dans la table.
4. Rejouer exactement le même corps : le résultat attendu est SANS_NOUVELLE_ALERTE, sans appel au modèle.
5. Essayer propre : aucune fuite attendue. Changer scope permet un espace de test distinct. Conserver un scope stable pour la déduplication quotidienne.

Les tests enregistrés dans RESULTS.md ont utilisé le mode manuel MCP, avec l’entrée webhook simulée. Ils ont réellement exécuté le code, la table, les outils et le modèle. Le listener HTTP et Header Auth restent à vérifier sur chaque installation.

## Entrées acceptées

Un objet JSON avec source et lines, lines étant un texte ou un tableau de chaînes ; un tableau d’objets ayant message ; un corps texte brut. scope est optionnel, principal par défaut, lettres/chiffres/tiret/souligné, au plus 60 caractères. Maximum 1,5 Mo de texte par entrée ; découper les gros journaux en lots en gardant le même source et scope. Aucune intégration Railway, Gmail ou Google Sheets n’est obligatoire.

## Réglages et sortie

Le masquage intervient avant le modèle et les écritures du suivi. La clé de regroupement est l’empreinte SHA-256 de source, type et valeur détectée. Une même valeur répétée dans ce même contexte ne crée qu’une entrée. Deux applications ou deux types différents restent distincts. Le suivi conserve les 10 000 dernières empreintes au maximum ; une très ancienne fuite peut donc réapparaître.

L’agent choisit une procédure parmi masquer, révoquer, vérifier. Il doit lire les preuves et une procédure. Le contrôle exige un JSON de brouillon, les références exactes, une action autorisée et rejette un chiffre ou une URL absent des preuves. Il ne prouve pas la justesse de chaque phrase : la relecture humaine reste nécessaire.

Les lignes brouillon contiennent des propositions, jamais des actions exécutées. Les lignes etat mémorisent uniquement les empreintes et la source masquée. Aucun journal brut n’y est écrit. Les deux nœuds de table utilisent un upsert : relancer un même lot n’ajoute pas de ligne identique. Des appels simultanés peuvent néanmoins appeler le modèle deux fois avant l’écriture ; sérialiser les entrées si nécessaire.

Les sorties d’exécution manuelles, réussies et échouées sont désactivées dans l’export pour éviter de conserver les journaux bruts reçus au webhook. Le corps circule nécessairement en mémoire avant masquage. Désactiver aussi les logs du proxy qui recopient les corps, ainsi que tout épinglage de données réelles. Les essais conservés sur l’instance de construction utilisent seulement des données inventées.

## Activation, à décider par l’utilisateur

Après les tests et la validation des réglages, l’utilisateur peut publier/activer le workflow dans son interface puis employer sa Production URL et le même Header Auth. Ce guide explique l’étape ; le workflow livré reste désactivé. L’activation ne change pas sa sortie : uniquement des brouillons dans la table.

## Erreurs fréquentes

- Table introuvable : créer la table dans le projet du workflow, vérifier son nom et les colonnes texte.
- Connexion absente : sélectionner ses propres Credentials sur le modèle et sur le webhook.
- Appel au modèle refusé : vérifier la facturation du fournisseur, le modèle et son accès aux outils.
- A_REPRENDRE : lire controle.errors ; aucun brouillon n’est conservé, le lot reste rejouable.
- Aucun brouillon au deuxième passage : c’est le suivi des doublons. Utiliser un scope de test neuf pour recommencer un essai.
- Secret non reconnu : une règle de détection ne couvre pas tous les formats. PEM, secrets multilignes et données encodées ne sont pas garantis. Installer aussi le filtre du pack dans l’application avant l’écriture.
- Valeur déjà exposée : le masquage ne remplace pas la révocation et le renouvellement chez son fournisseur.

## Sources officielles consultées

- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.datatable/
- https://docs.n8n.io/integrations/builtin/cluster-nodes/root-nodes/n8n-nodes-langchain.agent/
- https://docs.n8n.io/workflows/settings/

Références lues pendant la séance du 21 novembre 2026, heure de Toronto.
