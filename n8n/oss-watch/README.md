# oss-watch : suivre les licences des dépendances

Bonus n8n du pack Claude oss-check. Le pack examine un dépôt avant adoption ; ce workflow compare dans le temps les licences déclarées des dépendances déjà utilisées.

Entrée : liste JSON, requirements.txt ou package.json avec versions exactes. Lecture : registres publics PyPI et npm. Sortie : diagnostic JSON et brouillon interne, sans envoi. Un AI Agent consulte les preuves, choisit les procédures de revue et formule une proposition pour chaque anomalie. Un contrôle précède toute sauvegarde de brouillon.

Le workflow est inactif. Import, configuration du modèle, protection du webhook, Data Table et tests : [GUIDE.md](GUIDE.md). Résultats et limites : [test/RESULTS.md](test/RESULTS.md).

Test final : 12 dépendances inventées, 4 anomalies détectées et aucun nouveau brouillon au passage identique suivant. Registres simulés, modèle réel lors des tests positifs. Le refus HTTP sans en-tête reste à vérifier après configuration locale.

Le workflow n'installe rien, ne change aucun fichier et ne garantit pas la conformité juridique. Le modèle et ses coûts restent à la charge de l'utilisateur. Aucun compte, clé ou identifiant d'instance n'est inclus dans l'export.
