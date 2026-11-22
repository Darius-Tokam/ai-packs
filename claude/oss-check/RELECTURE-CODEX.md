# Relecture Codex du 22 novembre 2026

## Compatibilité Python

Utilise Python 3.12 pour cette version du pack. Avec Python 3.10.0, la relecture a obtenu 36 verdicts corrects sur 36, mais 55 contrôles réussis sur 56 : le lecteur TOML de secours ne retrouve pas les dépendances lourdes de l'extra `all` dans le cas simulé `piege-extra-lourd`. Le code utilise le lecteur standard `tomllib` à partir de Python 3.11 ; le cas ciblé a été vérifié avec Python 3.12.13.

Sous Windows, lancer les tests avec `PYTHONUTF8=1` et `PYTHONIOENCODING=utf-8` dans l'environnement pour que les sous-processus utilisent le même encodage.

Les fichiers de Claude ont été conservés. Cette note signale la limite constatée et ne remplace pas son rapport d'origine. Les données de test sont reconstituées ; aucune installation de vrais outils ni exécution des agents par un modèle n'est revendiquée.

## Rejeu complet avec Python 3.12.13

56 contrôles sur 56 réussis, 36 verdicts sur 36 corrects, 10 copies du script comportant volontairement un bug sur 10 rejetées. Exécution sous Windows avec les variables UTF-8 ci-dessus. La limite de Python 3.10 reste valable.
