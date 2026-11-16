# Résultats du test : quote-check sur 3 devis

Test du 14 novembre 2026. Rejouable avec Python 3.10 ou plus, sans dépendance :

```bash
python build_case.py /tmp/quote-cases
python run_checks.py /tmp/quote-cases
```

La sortie complète du dernier passage est dans [run_output.txt](run_output.txt).

## D'où vient le cas

Le sujet vient d'une tâche de l'auteur : chiffrer le projet d'un client à partir de son courriel. Il en a parlé deux fois sur LinkedIn. Le 13 septembre 2026, sur LinkedIn : un devis écrit par Claude et envoyé sans relecture, pour une cliente qui avait décrit sa plateforme dans un courriel du 8 avril 2026. Le 14 septembre 2026 : « 40 h estimées, 122 h réelles », payé 26 $ de l'heure au lieu de 75 $, parce qu'un « module de réservation » valait 12 h pour lui et un système complet avec fuseaux horaires pour sa cliente ; sa correction depuis, une marge de x1,2 à x2,0 selon le client.

Le cas `a-platform-booking` reprend cette forme : une plateforme, un module de réservation à 12 h, un devis de 40 h à 75 $/h, une cliente qui a des clientes au Québec et en France. Le brief, les noms, les montants et les autres postes sont inventés : ce n'est pas le courriel de la vraie cliente.

9 défauts y sont plantés :

| Défaut planté | Type |
|---|---|
| paiement en ligne demandé, aucune ligne | demandé, pas chiffré |
| courriel de rappel 24 h avant, aucune ligne | demandé, pas chiffré |
| site en français et en anglais, aucune ligne | demandé, pas chiffré |
| reprise de 300 clientes depuis un fichier Excel, aucune ligne | demandé, pas chiffré |
| clientes dans deux pays, la ligne de réservation ne prévoit pas les fuseaux horaires | travail caché |
| annulation et report jusqu'à 48 h avant, la ligne ne les prévoit pas | travail caché |
| deux animatrices avec leur propre accès, la ligne d'inscription ne prévoit pas de rôles | travail caché |
| 8 h x 75 $ écrit 650 $ au lieu de 600 $ | calcul |
| TVQ calculée à 9,5 % au lieu de 9,975 % | calcul |

Deux devis propres servent de témoins : `b-platform-fixed`, le même brief avec un devis corrigé de 80 h, et `c-studio-en`, un brief et un devis en anglais qui nomment les postes autrement (« Class booking calendar », « Stripe checkout »).

## Résultats mesurés

| Cas | Défauts plantés | Trouvés | En trop | Heures | Fourchette | Verdict | Résultat |
|---|---|---|---|---|---|---|---|
| a-platform-booking | 9 | 9 | 0 | 40 | 44 à 60 h | FIX FIRST (9) | PASS |
| b-platform-fixed | 0 | 0 | 0 | 80 | | SEND | PASS |
| c-studio-en | 0 | 0 | 0 | 37 | | SEND | PASS |

**9 défauts plantés sur 9 trouvés, 0 en trop. 0 fausse alerte sur les 2 devis propres.** Chaque demande non chiffrée cite la phrase exacte du brief, chaque travail caché pointe la ligne du devis concernée.

La fourchette du cas a (44 à 60 h) applique la marge de l'auteur aux 2 lignes à travail caché (20 h). Elle ne compte pas les 4 demandes non chiffrées. Dans le vrai cas, le projet a pris 122 h : la marge seule ne l'aurait pas couvert, ce sont les demandes oubliées et les questions posées avant de signer qui comptent.

Pendant la construction du test, le script a aussi relevé une erreur que l'agent avait laissée par mégarde dans le total du devis corrigé (7 198,50 $ au lieu de 6 898,50 $). Le total du témoin a été corrigé.

## Limite du test

Le même agent a écrit le script, construit les 3 devis et lancé les contrôles : les cas ne sont pas à l'aveugle, et 9 sur 9 dit seulement que le script trouve les défauts pour lesquels sa liste de mots a été écrite. Le script reconnaît les demandes par une liste de mots en français et en anglais (12 familles : réservation, paiement, comptes, tableau de bord, langues, notifications, import, recherche, mobile, intégrations, mise en ligne, maintenance) : une demande nommée autrement lui échappe, et une ligne nommée autrement peut sortir en « demandé, pas chiffré ». C'est le rôle de quote-auditor de confirmer chaque constat contre le brief ; cette partie, comme la lecture du brief par brief-reader, est faite par le modèle et n'est pas mesurée ici. Le déclenchement du skill d'entrée `check-my-quote` par le modèle, à partir d'une phrase comme « vérifie mon devis », n'a pas été testé. Le devis doit être un tableau markdown ; un PDF ou un tableur est d'abord recopié par l'agent, une étape non mesurée. Le script ne dit rien du prix juste : il dit ce que le devis ne couvre pas.
