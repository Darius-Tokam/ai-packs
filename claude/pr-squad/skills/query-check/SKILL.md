---
name: query-check
description: Detect N+1 queries and unbounded database reads a branch introduces, and measure the query count before and after the fix. Use on any diff that touches views, serializers, loops over model instances or ORM calls (Django, SQLAlchemy, Prisma, ActiveRecord, Eloquent).
---

# query-check

An N+1 is invisible with 3 rows in dev and takes the page down with 3 000 in prod. Count queries, do not guess.

## 1. Spot candidates in the diff

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
git diff -U10 "$BASE"...HEAD
```

Flag:

- a loop over a queryset that reads a related object (`obj.client.name`) or a reverse relation (`obj.lines.all()`) without `select_related` / `prefetch_related` (Django), `joinedload` / `selectinload` (SQLAlchemy), `include` (Prisma), `includes` (Rails), `with` (Laravel);
- a query inside a loop (`Model.objects.get(...)` per item);
- `.all()` or `findMany()` without pagination on an endpoint;
- a function called per row that queries the database itself.

## 2. Measure

Write a throwaway test that creates N rows (N = 20), calls the code path and counts queries.

Django:

```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as ctx:
    client.get("/invoices/discounted/")
print(len(ctx.captured_queries))
```

SQLAlchemy: count with an `after_cursor_execute` event listener. Prisma: `$on('query')`. Rails: `ActiveSupport::Notifications.subscribe("sql.active_record")`.

Run it once with N = 20 and once with N = 40. A count that grows with N is an N+1.

## 3. Fix and measure again

Apply the eager-loading fix in the throwaway copy, rerun, and report both numbers. Do not commit the fix: propose it.

## 4. Report

```
FIX | invoices/views.py:16 discounted_invoices | N+1: 41 queries for 20 invoices, 81 for 40 | measured | Invoice.objects.select_related("client").prefetch_related("lines") -> 2 queries for 20 or 40
```

End with `QUERIES VERDICT: CLEAN` or `QUERIES VERDICT: <n> N+1`.
