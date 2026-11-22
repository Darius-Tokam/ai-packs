# leak-watch

Bonus n8n du pack Claude Code leak-scan. Le workflow reçoit des journaux génériques, masque les valeurs reconnues, regroupe leurs répétitions et demande à un AI Agent de proposer un correctif. Le modèle consulte des preuves masquées et une procédure. Un contrôle précède tout brouillon conservé.

## Livré

- workflow.json : import autonome, désactivé, sans connexion ni identifiant d’instance.
- GUIDE.md : installation Cloud et serveur, réglages et lancement.
- test/cases.py : données entièrement fictives, générées au lancement.
- test/RESULTS.md et mesures.json : résultats manuels et limites.

Le brouillon apparaît dans la Data Table Codex_leak_watch_registre, colonne payload, lignes de type brouillon. Aucun courriel, aucune messagerie ni publication ne sont utilisés.

Le filtre de détection dérive du filtre Node de leak-scan, dépôt Darius-Tokam/ai-packs, licence MIT. L’agent et les contrôles du bonus sont distincts du script. Les résultats de l’un ne doivent pas être attribués à l’autre.
