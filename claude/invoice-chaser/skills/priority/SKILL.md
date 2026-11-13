---
name: priority
description: Rank the invoices to chase by balance times days late, and say which client to call first. Use when there are more late invoices than time to chase them.
---

# priority

## 1. Read the plan

`chase_out/plan.json` is sorted with the chase invoices first, by `score = balance x days late`. Holds (wrong tax, duplicate) and invoices not yet due come after.

## 2. Add what the numbers miss

Ask the user, once, about each of the top 3 clients:
- is a dispute open on this work?
- is the client still a client (new project in progress)?
- did someone promise a date by phone?

A dispute moves the invoice out of the email flow: recommend a call. A promise moves the reminder to the day after the promised date.

## 3. Report

```
PRIORITY | 1 | F-2026-004 | Demo Delta | 2 069,55 $ | 133 days | L3 dernier avis, call before emailing
PRIORITY | 2 | F-2026-013 | Demo Alpha inc. | 2 529,45 $ | 33 days | L2 relance ferme
PRIORITY | 3 | F-2026-008 | Demo Foxtrot | 804,83 $ | 85 days | L3 dernier avis
```

End with `PRIORITY VERDICT: call <client> first`.
