---
name: bug-hunt
description: Review the logic of a branch diff for bugs that tests usually miss - boundaries, None, rounding, money as float, time zones, swallowed exceptions - and prove each one with a concrete input. Use before merging.
---

# bug-hunt

Every finding needs a failing input. No input, no finding: write it as a NOTE called "suspicion".

## 1. Read the diff with its context

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
git diff -U15 "$BASE"...HEAD
```

Open each changed function in full, and the callers of each changed function (`grep -rn "<name>(" .`).

## 2. Check these, in this order

1. **Bounds**: off-by-one in ranges and slices, `<` against `<=`, empty collections, a single element.
2. **Unbounded input**: percentages above 100 or below 0, negative quantities, huge values, strings where numbers are expected.
3. **Money and precision**: money stored or returned as float, division producing floats, rounding direction, sums of rounded values.
4. **None / null**: an optional field read without a check, `.get()` results used directly, nullable foreign keys.
5. **Time**: naive against aware datetimes, local time compared with UTC, end-of-month and DST.
6. **Errors**: bare `except`, swallowed exceptions, an error returned as a value the caller ignores.
7. **Concurrency**: read-then-write without a lock or atomic update, check-then-act on unique values.

## 3. Prove it

For each candidate, run the function with the input that breaks it. Use the project's interpreter or test runner, for example:

```bash
python -c "from invoices.services import apply_discount; print(apply_discount(1000, 150))"
```

Paste the real output. If it needs a database or framework setup, write a throwaway test and run it.

## 4. Report

```
BLOCK | invoices/services.py:8 | discount above 100% gives a negative total | apply_discount(1000, 150) -> -500.0 | clamp percent to 0..100, reject otherwise
FIX   | invoices/services.py:8 | returns float cents | apply_discount(999, 10) -> 899.1 | integer math: total * (100 - percent) // 100, decide the rounding rule
NOTE  | invoices/views.py:17   | suspicion: discount_percent may be NULL on old rows | no failing input yet | covered by migration-guard
```

`BLOCK` corrupts data or money, `FIX` gives wrong output, `NOTE` is a suspicion. End with `BUGS VERDICT: CLEAN` or `BUGS VERDICT: <n> BLOCK, <m> FIX`.
