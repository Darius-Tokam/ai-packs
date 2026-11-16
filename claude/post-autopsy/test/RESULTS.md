# Résultats du test : post-autopsy sur un historique de 40 posts

Test du 15 novembre 2026, lancé avec Python 3.13 (et repassé avec Python 3.11 et 3.12). Rejouable sans dépendance :

```bash
python build_history.py /tmp/post-history
python run_checks.py /tmp/post-history
```

La sortie complète du dernier passage est dans [run_output.txt](run_output.txt). Le rapport que le script écrit sur cet historique est dans [sample_report.md](sample_report.md).

## D'où vient le cas

Le sujet vient d'une tâche que l'auteur fait chaque dimanche : relire les impressions de ses posts pour décider quoi changer. Ses chiffres : une médiane d'environ 90 impressions sur ses 40 posts du 29 août au 12 novembre 2026, contre 10 750 en moyenne en mars 2026 ; ses posts récents, mesurés le 15 novembre 2026, font 23, 23, 65, 71, 310 et 608 impressions. Une leçon qu'il a notée le 28 mai 2026 : les créateurs veulent des impressions, et ce qui leur sert est de diagnostiquer leurs anciens posts pour trouver ce qui fait les impressions, sans promesse magique.

`build_history.py` reconstitue, avec une graine fixe, un historique de cette forme : 40 posts mesurés du 29 août au 12 novembre 2026, une médiane de 88, 25 posts sur 40 entre 20 et 120 impressions, une longue traîne de 5 posts entre 300 et 600 (300, 340, 416, 470, 590). Ce ne sont pas ses posts : les textes, les heures, les dates et chaque nombre d'impressions sont inventés.

Ce qui est planté :

| Planté | Ce que le script doit faire |
|---|---|
| les accroches à la première personne (« je ») ont une médiane nettement plus haute que les accroches qui parlent au lecteur (« tu ») | sortir les deux dans les conclusions, dans le bon sens |
| les posts de 7h à 9h59 battent ceux de 18h à 23h59 | sortir les deux dans les conclusions, dans le bon sens |
| piège : 3 posts qui commencent par une question, à une médiane spectaculaire | les marquer « échantillon trop petit », ne jamais en conclure |
| piège : 2 posts sans impressions (une case vide, une case « n/a ») | les exclure et les compter |
| piège : 1 post publié à 10:00 pile, sur la limite entre deux tranches | le classer dans 10h à 12h59 |
| pièges de classement : « J’ai » avec une apostrophe typographique, « 40 posts en 75 jours : ce que j'ai appris » (chiffre avant je), « Ton audience ne voit pas ce que je vois » (tu avant je), une seule ligne fléchée (pas une liste), « Commente si tu veux la suite » (pas de mot-clé) | les classer selon les règles écrites |

`run_checks.py` ne lit pas le code du script : il recalcule chaque n, chaque médiane, chaque écart et la liste des conclusions à partir des étiquettes que `build_history.py` a données à chaque post (`truth.json`), puis compare au rapport.

## Résultats mesurés

Copiés de la sortie de `run_checks.py` :

| Contrôle | Attendu | Mesuré | Résultat |
|---|---|---|---|
| forme de l'historique | médiane proche de 90, la plupart entre 20 et 120, quelques-uns entre 300 et 600 | médiane 88, 25/40 entre 20 et 120, 5 entre 300 et 600 (300, 340, 416, 470, 590) | PASS |
| lignes lues / posts analysés / exclus | 42 / 40 / 2 | 42 / 40 / 2 | PASS |
| posts sans impressions nommés | n° 3, 7 | n° 3, 7 | PASS |
| médiane de l'ensemble | 88 | 88 | PASS |
| réactions / commentaires médians | 2 / 1 | 2 / 1 | PASS |
| sortie JSON lisible | oui | oui | PASS |
| classement de chaque post (40 posts x 6 critères) | 240/240 | 240/240 | PASS |
| post à la limite (10:00, post n° 40) | 10h à 12h59 | 10h à 12h59 | PASS |
| groupes : n, médiane, écart, lecture | 23/23, aucun en trop | 23/23, aucun en trop | PASS |
| groupes de moins de 5 posts marqués « échantillon trop petit » | 3 | 3 (Accroche : question, Jour : lundi, Jour : samedi) | PASS |
| groupes de moins de 5 posts dans les conclusions | 0 | 0 | PASS |
| groupes de moins de 5 posts listés à part | 3 | 3 | PASS |
| conclusions (n >= 5 et écart >= 25 %) | 7, avec n et les deux médianes | 7, identiques | PASS |
| effet planté : Accroche je, au-dessus | 150 sur 12 posts | 150 sur 12 posts, contre 88 (+70 %) | PASS |
| effet planté : Accroche tu, en dessous | 37,5 sur 10 posts | 37,5 sur 10 posts, contre 88 (-57 %) | PASS |
| effet planté : Heure 7h à 9h59, au-dessus | 150 sur 14 posts | 150 sur 14 posts, contre 88 (+70 %) | PASS |
| effet planté : Heure 18h à 23h59, en dessous | 48,5 sur 8 posts | 48,5 sur 8 posts, contre 88 (-45 %) | PASS |
| piège : Accroche question (3 posts, médiane 470) | marqué, jamais conclu | médiane 470, marqué, jamais conclu | PASS |
| code de sortie sur l'historique | 0 | 0 | PASS |
| entrée JSON : même rapport | identique | identique | PASS |
| export de tableur français (; en-têtes français, 12/11/2026, 8h00) | même rapport | même rapport | PASS |
| fichier de 3 posts : refuse de conclure | code 1, 0 conclusion | code 1, 0 conclusion | PASS |
| fichier absent | code 2 | code 2 | PASS |
| colonne impressions absente | code 2 | code 2 | PASS |
| tiret long ou moyen dans le pack | aucun | aucun | PASS |

**240 classements sur 240 justes. Les 4 effets plantés sortent dans les conclusions, dans le bon sens. Les 3 groupes de moins de 5 posts sont marqués et aucun n'entre dans les conclusions, dont les 3 questions à 470 de médiane, plus de cinq fois la médiane de 88. Les 2 posts sans impressions sont exclus et nommés. Analysés seuls, les 3 posts en question ne donnent aucune conclusion (code 1).**

Les 7 conclusions écrites par le script :

- **Accroche : je** : médiane 150 impressions sur 12 posts, contre 88 pour l'ensemble (+70 %).
- **Heure : 7h à 9h59** : médiane 150 impressions sur 14 posts, contre 88 pour l'ensemble (+70 %).
- **Jour : jeudi** : médiane 135,5 impressions sur 6 posts, contre 88 pour l'ensemble (+54 %).
- **Accroche : tu** : médiane 37,5 impressions sur 10 posts, contre 88 pour l'ensemble (-57 %).
- **Heure : 13h à 17h59** : médiane 40 impressions sur 6 posts, contre 88 pour l'ensemble (-55 %).
- **Heure : 18h à 23h59** : médiane 48,5 impressions sur 8 posts, contre 88 pour l'ensemble (-45 %).
- **Jour : mardi** : médiane 51 impressions sur 7 posts, contre 88 pour l'ensemble (-42 %).

Trois de ces lignes ne viennent pas d'un effet planté. Les dates ont été tirées au hasard, sans aucun effet sur les jours : le jeudi (6 posts) et le mardi (7 posts) passent pourtant le seuil, parce que le tirage a mis au jeudi plus de posts du matin et l'un des 3 posts en question, et au mardi plus de posts en « tu ». La tranche 13h à 17h59 (6 posts) sort à -55 % alors que le modèle de génération ne lui donnait qu'un petit désavantage (un facteur 0,85, contre 1,3 le matin et 0,55 le soir) : sur 6 posts, le bruit pèse lourd. Le script les rapporte, parce qu'elles respectent la règle ; c'est pour ça que le skill préfère les groupes les plus gros et présente un groupe de 5 à 9 posts comme une piste à tester.

Pendant la construction, des copies volontairement cassées du script ont été passées au test : limite de 10h déplacée à 11h, seuil de 5 posts abaissé à 3, règle « échantillon trop petit » retirée, impressions vides lues comme 0, règle de la question retirée, valeur basse du milieu au lieu de la médiane, une seule ligne fléchée comptée comme une liste, script qui plante. Chacune a fait sortir `RESULT: FAIL`.

## Limite du test

Le même agent a écrit le script, construit l'historique et lancé les contrôles : les cas ne sont pas à l'aveugle, et 240 sur 240 dit seulement que le script applique les règles pour lesquelles il a été écrit, sur des textes écrits pour elles. Le classement par règles est grossier : une accroche qui raconte une histoire sans « je » dans sa première ligne sort en « autre », « a ton of » en anglais compte comme « tu », un appel à commenter formulé autrement que « Commente MOT » n'est pas vu. Un écart de médiane sur 40 posts est une corrélation, pas une cause : le sujet, l'actualité ou le moment de l'année peuvent jouer, et le test montre que le hasard seul fait passer des groupes de 6 ou 7 posts au-dessus du seuil de 25 %. L'historique est synthétique : il a la forme de celui de l'auteur, pas ses posts, et aucun vrai export LinkedIn n'a été lu ; le format de cet export n'est donc pas testé. Le déclenchement du skill par le modèle, à partir d'une phrase comme « analyse mes posts LinkedIn », n'a pas été testé, ni les recommandations que le modèle écrit à partir du rapport : seul le script l'a été.
