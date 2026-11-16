# post-autopsy : un skill Claude Code qui te dit ce qui fait tes impressions LinkedIn

Tu exportes tes posts LinkedIn et tu demandes à Claude Code « analyse mes posts LinkedIn ». Le skill mesure, sur ton propre historique, quelles accroches, quels formats, quels jours et quelles heures vont avec plus d'impressions : pour chaque groupe, le nombre de posts et la médiane. Il refuse de conclure sur moins de 5 posts, même quand 3 posts font cinq fois ta médiane.

Un seul skill et un script Python, parce qu'il n'y a qu'une étape : classer tes posts et comparer les chiffres.

| Ce que le script mesure | Comment il classe chaque post | Groupes |
|---|---|---|
| Accroche | la première ligne du post | question (finit par « ? »), chiffre (commence par un chiffre), je (je, j', mon, ma, mes), tu (tu, ton, ta, tes, vous), autre |
| Longueur | les caractères du texte | moins de 500, 500 à 1299, 1300 et plus |
| Liste à flèches | au moins 2 lignes qui commencent par une flèche (→, ->) | oui, non |
| Mot-clé à commenter | un appel du type « Commente GUIDE » (mot en capitales) | oui, non |
| Jour | la date de publication | lundi à dimanche |
| Heure | l'heure de publication | 0h à 6h59, 7h à 9h59, 10h à 12h59, 13h à 17h59, 18h à 23h59 |

Pour chaque groupe, le rapport donne le nombre de posts (n) et la médiane des impressions, face à la médiane de tous tes posts. La médiane plutôt que la moyenne : un seul post à 600 impressions ne fait pas passer tout un format pour gagnant.

La section « Ce que les chiffres permettent de dire » ne garde que les groupes d'au moins 5 posts dont la médiane s'écarte d'au moins 25 % de la tienne. Un groupe plus petit est marqué « échantillon trop petit » et n'y entre jamais. Les posts sans impressions sont exclus et comptés. Les règles exactes sont écrites à la fin de chaque rapport. Un exemple de rapport complet est dans [test/sample_report.md](test/sample_report.md).

## Installer

```bash
claude plugin marketplace add Darius-Tokam/ai-packs
claude plugin install post-autopsy@ai-packs
```

## Sans taper de commande

Dis simplement à Claude Code « analyse mes posts LinkedIn », « qu'est-ce qui marche dans mes posts ? » ou, en anglais, « which of my LinkedIn posts worked » ou « audit my post performance ». Le skill te demande ton fichier s'il ne l'a pas, lance le script, te montre le rapport, puis te donne au plus 3 recommandations. Chacune vient d'un groupe d'au moins 5 posts et cite son n et sa médiane : c'est une observation sur ton historique, pas une promesse.

Tu peux aussi lancer le script seul, sans Claude : `python3 scripts/autopsy.py posts.csv` (Python 3, sans dépendance). Ajoute `--json` pour une sortie JSON.

## Le fichier de tes posts

Une ligne par post, en CSV :

```csv
date,time,text,impressions,reactions,comments
2026-11-12,08:00,"J'ai testé une nouvelle accroche.
Voici ce que ça a donné.",310,9,4
```

| Colonne | Obligatoire | Ce qu'elle contient |
|---|---|---|
| date | oui | 2026-11-12, ou 12/11/2026 (jour d'abord ; `--date-order mdy` pour un export américain) |
| impressions | oui | un nombre entier ; une case vide ou illisible exclut le post, qui est compté à part |
| time | non | 08:00, 8h, 8h30 ; sans elle, pas d'analyse par heure |
| text | non | le texte complet du post ; sans lui, pas d'analyse de l'accroche ni du format |
| reactions, comments | non | des nombres entiers, pour les médianes de réactions et de commentaires |

Le script accepte aussi la virgule, le point-virgule ou la tabulation comme séparateur, des en-têtes en français (Date de publication, Heure, Texte, Impressions, Réactions, Commentaires) et une liste JSON avec les mêmes clés.

Pour construire le fichier : l'export des statistiques LinkedIn (un fichier .xlsx) donne selon les versions la date et les impressions de tes posts, mais pas toujours le texte ni l'heure. Ajoute ces colonnes, puis enregistre la feuille en CSV. Sinon, remplis le fichier à la main avec les impressions affichées sous chaque post.

Codes de sortie du script : 0, rapport avec au moins une conclusion ; 1, rapport sans rien à conclure (trop peu de posts ou aucun écart assez grand) ; 2, fichier absent ou illisible, ou colonne obligatoire absente.

## Testé sur 40 posts reconstitués

Un historique de 42 posts reconstitué sur la forme de celui de l'auteur (médiane de 88 impressions, 25 posts sur 40 entre 20 et 120, 5 entre 300 et 600), avec des effets plantés et des pièges. Les 40 posts sont classés comme prévu sur les 6 critères (240 sur 240). Les 4 effets plantés sortent dans les conclusions : accroche « je » à 150 impressions de médiane sur 12 posts, accroche « tu » à 37,5 sur 10 posts, contre 88 pour l'ensemble ; 150 sur 14 posts à 7h à 9h59, 48,5 sur 8 posts à 18h à 23h59. Les 3 posts en question, à 470 de médiane, sont marqués « échantillon trop petit » et jamais conclus. Les 2 posts sans impressions sont exclus et comptés. Analysés seuls, ces 3 posts ne donnent aucune conclusion.

Le test montre aussi la limite de l'outil : le jeudi (+54 %, 6 posts) et le mardi (-42 %, 7 posts) passent le seuil alors qu'aucun effet n'était planté sur les jours. Sur 40 posts, le hasard suffit à créer ces écarts. C'est pour ça que le skill préfère les groupes les plus gros et te dit de tester avant de changer ta routine.

Le détail, les mesures et la limite du test sont dans [test/RESULTS.md](test/RESULTS.md). Tu peux rejouer le test :

```bash
python test/build_history.py /tmp/post-history
python test/run_checks.py /tmp/post-history
```

## Ce qu'il ne fait pas

- Il ne promet aucun nombre d'impressions. Il dit ce qui est allé avec plus d'impressions dans ton historique : une corrélation, pas une cause.
- Il ne lit pas ton compte LinkedIn tout seul : tu lui donnes le fichier.
- Il ne publie, ne programme et ne modifie aucun post.

## Langues

Le skill répond dans ta langue. Ses instructions sont en anglais (Claude les exécute mieux ainsi), le rapport du script et ce guide sont en français. Le script reconnaît les accroches et les appels à commenter en français et en anglais.

---

Fait par [Darius Tokam](https://tokamdarius.ca) · Arivex · Licence MIT
