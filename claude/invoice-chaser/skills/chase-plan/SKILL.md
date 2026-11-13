---
name: chase-plan
description: Turn the invoice-chaser results into a dated follow-up calendar (who to remind, when, at which level) and a one-line cash summary. Use at the end of a chase run, or weekly to keep reminders on schedule.
---

# chase-plan

## 1. Read

`chase_out/plan.csv`: one row per open invoice with its next step. `chase_out/report.md`: the verdict line.

## 2. Build the calendar

For each chased invoice, the next date depends on the level just sent:
- after L1: L2 in 14 days if still unpaid;
- after L2: L3 at the date given in the email plus 1 day;
- after L3: a phone call, then the step the user decided (pause, collection).

For `wait` invoices: an L1 the day after the due date. For `hold`: no date until the invoice is fixed.

Write `chase_out/calendar.md` as a table: date, client, invoices, action. If the user has a calendar or task tool connected, offer to create the reminders there. Do not create them without a yes.

## 3. Report

```
PLAN | today: 4 emails (7 invoices, 8 080,63 $) | next: 2026-11-14 L1 Demo Charlie F-2026-019 | on hold: 2 (2 406,88 $)
```

End with `CHASE VERDICT` copied from the report.
