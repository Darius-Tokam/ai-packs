---
name: aging
description: Compute how late each unpaid balance is, by bucket (not yet due, 1-30, 31-60, 61-90, 90+ days), and flag invoices with no due date. Use to see how much money is late and how late, after bank-match.
---

# aging

## 1. Read the buckets

Run `chase.py check` (see bank-match) or read `chase_out/report.md` if it is fresh. The script ages the balance left after bank-match, not the invoice total, and leaves out duplicates on hold.

## 2. Missing due dates

An invoice without a due date gets the default terms (`--terms`, 30 days unless the user says otherwise). Ask the user for their real terms if they differ, then rerun. Recommend writing the due date on every future invoice: a reminder that cites a date is harder to ignore.

## 3. Report

```
AGING | not yet due 6 668,56 $ | 1-30 3 441,66 $ | 31-60 3 596,59 $ | 61-90 804,83 $ | 90+ 2 069,55 $
FIX   | F-2026-013 | no due date: 30-day terms assumed, due 2026-10-10
```

End with `AGING VERDICT: <amount> late, <amount> beyond 60 days`.
