---
name: duplicate-guard
description: Find duplicate invoices (same client, date and total) and gaps in invoice numbering. Use before chasing, so a client never gets two reminders for one job, and before a tax return.
---

# duplicate-guard

## 1. Run

`chase.py check ...` (see bank-match). It reports:

- **duplicate**: same client, same issue date, same total, different number. The later number goes on hold.
- **gap**: a number missing from a sequence (`F-2026-013`, then `F-2026-015`).

## 2. Ask, do not decide

A duplicate can be real (two identical monthly jobs on the same day). Show both lines and ask. A gap can be a cancelled invoice: tax authorities usually expect cancelled invoices to stay in the books with a cancelled status, so ask the user to check with their accountant rather than renumbering.

## 3. Report

```
BLOCK | F-2026-018 | same client, date and total as F-2026-017 | cancel it or confirm it
FIX   | F-2026-014 | missing from the sequence | find it or record it as cancelled
```

End with `DUPLICATE VERDICT: CLEAN` or `DUPLICATE VERDICT: <n> duplicates, <m> gaps`.
