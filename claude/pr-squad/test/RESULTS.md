# Résultats du test : pr-squad sur le dépôt piège

Test du 12 novembre 2026. Rejouable avec :

```bash
pip install "django==5.2.*" pytest pytest-django detect-secrets pip-audit
python build_trap.py /tmp/trap
python run_checks.py /tmp/trap
```

## Le dépôt piège

Une petite app Django de facturation. La branche `feat/discounts` annonce « ajouter une remise en pourcentage aux factures » et contient 8 défauts plantés.

| # | Défaut planté | Agent qui l'a trouvé | Preuve mesurée |
|---|---|---|---|
| 1 | Clé Stripe live en dur dans `settings.py` | secret-scan | detect-secrets : `settings.py:24`, Secret Keyword + chaîne à haute entropie |
| 2 | En-têtes HTTP (Authorization, cookies) imprimés dans les logs | secret-scan | ligne ajoutée `print("DEBUG headers", dict(request.headers))` |
| 3 | `PyYAML==5.3.1` ajouté | dep-audit | pip-audit : PYSEC-2021-142, corrigé en 5.4 ; et `yaml` n'est importé nulle part |
| 4 | Colonne NOT NULL sans défaut sur une table qui a des lignes | migration-guard | répétition sur une base avec une facture : `IntegrityError: NOT NULL constraint failed` |
| 5 | Admin « exporter tous les clients » sans rapport avec la remise | scope-check | lecture du diff contre l'objectif de la branche |
| 6 | `apply_discount()` sans aucun test | test-gaps | 4 tests écrits, 2 échouent |
| 7 | Remise au-delà de 100 % et montant en float | bug-hunt | `apply_discount(1000, 150)` renvoie `-500.0` ; `apply_discount(999, 10)` renvoie `899.1` |
| 8 | Requête N+1 dans la nouvelle vue | query-check | 41 requêtes pour 20 factures, 81 pour 40 ; 2 requêtes après `select_related` + `prefetch_related` |

**8 défauts plantés, 8 trouvés.** Verdict de `/pr-squad:ship` : `SHIP: STOP (4 BLOCK)`.

Trouvés en plus, sans les avoir plantés :

- la suite existante est rouge sur la branche (`test_invoice_total_sums_lines`, conséquence du défaut 4) ;
- `django 5.2.8` et `requests 2.32.3` ont des failles connues (PYSEC-2026-3717, PYSEC-2026-4035, PYSEC-2026-1872, PYSEC-2026-2275). Elles existaient déjà sur `main`, donc dep-audit les classe en NOTE.

## Le déclencheur (version 1.1.0, 12 novembre 2026)

Le hook `hooks/require-review.sh` a été rejoué sur 8 cas avec `bash test/test_hook.sh` : 8 sur 8 conformes.

| Cas | Attendu | Obtenu |
|---|---|---|
| `gh pr create` sans revue | bloqué | bloqué |
| `glab mr create` sans revue | bloqué | bloqué |
| outil MCP `create_pull_request` sans revue | bloqué | bloqué |
| `git push` | laissé passer | laissé passer |
| commande sans rapport (`ls`) | laissé passer | laissé passer |
| `gh pr create` avec `PR_SQUAD_SKIP=1` | laissé passer | laissé passer |
| `gh pr create` après une revue du commit en cours | laissé passer | laissé passer |
| `gh pr create` après un nouveau commit | bloqué | bloqué |

## Limite du test

Le même agent a planté les défauts puis lancé les contrôles. Les mesures outillées (detect-secrets, pip-audit, migration, pytest, comptage de requêtes) sont reproductibles avec `run_checks.py` et ne dépendent pas de lui. La lecture de scope-check et le choix des entrées de bug-hunt, eux, ne sont pas un test à l'aveugle. Lance `/pr-squad:ship` sur une de tes branches et compare.

Pour le déclencheur, le script du hook est testé, pas le choix du modèle : que Claude Code active `review-before-pr` sur « fais une PR » dépend de la description du skill. Le hook est le filet si le skill n'est pas choisi.

## Description de PR générée par pr-writer

```
feat(invoices): add percentage discount to invoices
```

```markdown
DO NOT MERGE

## Why
Clients need a percentage discount on their invoices.

## What changes
- `invoices/services.py`: new `apply_discount(total_cents, percent)`.
- `invoices/models.py` + migration 0002: new `Invoice.discount_percent` column.
- `invoices/views.py`: new endpoint `/invoices/discounted/` listing discounted totals.
- `invoices/admin.py`: CSV export of every client (out of scope, see below).

## How to test
1. `python manage.py migrate` on a database that already has invoices.
2. `pytest`.

## Risks and follow-ups
- BLOCK: Stripe live key hardcoded in `billing/settings.py`. Rotate it, it is in git history.
- BLOCK: migration 0002 fails on any table with rows (NOT NULL without default).
- BLOCK: `apply_discount(1000, 150)` returns -500.0.
- BLOCK: PyYAML 5.3.1 (PYSEC-2021-142), and nothing imports it.
- FIX: N+1 on `/invoices/discounted/` (41 queries for 20 invoices).
- FIX: request headers printed to logs.
- FIX: admin CSV export belongs in its own PR.
- FIX: existing test suite is red on this branch.
```
