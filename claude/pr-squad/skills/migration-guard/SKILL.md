---
name: migration-guard
description: Check that the database migrations in a branch will run on a production database that already has rows, without locking or losing data. Use on any diff that adds or edits migrations (Django, Alembic, Prisma, Rails, Laravel, raw SQL).
---

# migration-guard

A migration that passes on an empty dev database can fail on the first deploy. Test it on a database that has data.

## 1. Find the migrations

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
git diff --name-only "$BASE"...HEAD | grep -Ei 'migrat|alembic|schema\.prisma|\.sql$'
```

For Django, also check that models and migrations agree: `python manage.py makemigrations --check --dry-run`.

## 2. Read each operation for these risks

- **NOT NULL without default** on an existing table (fails as soon as the table has rows).
- **Dropping or renaming** a column or table that code on the base branch still reads (breaks the old version during a rolling deploy).
- **Type changes** that truncate or reinterpret data.
- **Indexes or constraints on large tables** created without `CONCURRENTLY` (Postgres) or an online method: they lock writes.
- **Data migrations** with no reverse, or that load a whole table in memory.

## 3. Rehearse on a database with data

1. Check out the base branch, migrate a scratch database, insert a few realistic rows.
2. Switch to the branch and run the new migrations on that same database.
3. Keep the exact error if it fails.

Django example:

```bash
export TRAP_DB=/tmp/rehearsal.sqlite3   # or point DATABASES at a scratch DB
git checkout "$BASE" && python manage.py migrate
python manage.py shell -c "from invoices.models import *; c=Client.objects.create(name='Acme'); Invoice.objects.create(client=c)"
git checkout - && python manage.py migrate
```

## 4. Report

```
BLOCK | invoices/migrations/0002_invoice_discount_percent.py | NOT NULL column without default | rehearsal: IntegrityError NOT NULL constraint failed: invoices_invoice.discount_percent | add default=0, or add nullable, backfill, then set NOT NULL
```

End with `MIGRATIONS VERDICT: SAFE` or `MIGRATIONS VERDICT: BLOCK (<n>)`.
