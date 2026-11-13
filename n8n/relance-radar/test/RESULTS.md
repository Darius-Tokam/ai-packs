# Résultats du test : relance-radar sur une boîte reconstituée

Test du 13 novembre 2026. Rejouable avec Python 3.10 ou plus et Node.js :

```bash
python build_threads.py /tmp/relance-cases
python run_checks.py /tmp/relance-cases
```

`run_checks.py` exécute le nœud **Choisir les relances** tel qu'il est dans [workflow.json](../workflow.json), grâce à [harness.js](harness.js). La sortie complète du dernier passage est dans [run_output.txt](run_output.txt).

## D'où vient le cas

Le sujet vient d'une tâche de l'auteur : relancer les prospects restés sans réponse. Ses notes de septembre 2026 disent : 22 courriels de prospection partis du 19 août au 2 septembre, 0 réponse, le lot le plus ancien à 15 jours ; et, le 7 septembre, un brouillon de relance préparé pour un prospect qu'il avait perdu. La boîte de test reprend cette forme au 3 septembre 2026 : 22 fils envoyés en 4 lots (19 août : 8, 26 août : 7, 31 août : 4, 2 septembre : 3), aucune réponse, et le prospect perdu sur la liste d'exclusion. 5 fils sont ajoutés, un par filtre : une réponse, une adresse en erreur, un fil déjà relancé deux fois, un fil relancé une fois, un fil qui a déjà son brouillon. Tous les noms et adresses sont inventés (domaines `.example`).

Réglages du test : délai de 5 jours, 2 relances au plus, date du jour 2026-09-03.

## Résultats mesurés

| Mesure | Résultat |
|---|---|
| Fils lus | 27 (33 messages) |
| Brouillons préparés | 15 : 14 relances n°1 (lots du 19 et du 26 août) et 1 relance n°2 |
| Fils ignorés | 12 : 7 trop récents, 1 sur la liste d'exclusion, 1 a répondu, 1 adresse en erreur, 1 maximum atteint, 1 brouillon déjà prêt |
| Décision attendue, fil par fil | 27 sur 27 |
| Brouillon vers un prospect exclu, une personne qui a répondu, une adresse en erreur, un fil au maximum ou un fil qui a déjà son brouillon | 0 |
| Brouillons avec salutation, 3 phrases, objet « Re: » propre et date du premier message | 15 sur 15 |
| Relance n°2 avec l'autre formulation | 1 sur 1 |
| Second passage, brouillons déjà en place | 0 nouveau brouillon |
| Tirets longs ou moyens dans le pack | 0 |

Dans n8n (version 2.47.4, instance de l'auteur), le même workflow, lancé en test avec les mêmes 27 fils en données simulées (exécution 14 du 13 novembre 2026), a rendu les mêmes 27 décisions : 15 fils passent le filtre **À relancer**, 12 sont écartés. Le nœud **Créer le brouillon** était simulé : aucun vrai brouillon n'a été créé.

## Limite du test

Le même agent a écrit le workflow, construit la boîte de test et lancé les contrôles : la boîte n'est pas à l'aveugle. Les nœuds Gmail étaient simulés : la forme des données suit la documentation du nœud Gmail de n8n (lecture d'un fil, en-têtes `From`, `To`, `Subject`, `internalDate` et étiquettes), elle n'a pas été lue sur une vraie boîte. À vérifier au premier lancement réel : qu'un brouillon existant apparaît bien avec l'étiquette `DRAFT` dans le fil (c'est ce qui empêche les doublons), et que le brouillon se range dans le bon fil. Les jours se comptent en dates UTC. Une réponse automatique (absence du bureau) compte comme une réponse : le fil est ignoré. Le workflow ne lit pas le corps des courriels, donc il ne sait pas si ta proposition a été refusée ailleurs (téléphone, autre adresse) : c'est le rôle de la liste d'exclusion. La qualité des trois phrases n'est pas mesurée, seulement leur forme.
