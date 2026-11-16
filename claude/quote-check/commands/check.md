---
description: Check a quote against the client's brief before sending it, with 2 agents and one verdict.
argument-hint: "[quote file] [brief file] [taxes, e.g. TPS=5 TVQ=9.975]"
---

Check this quote before it is sent to the client. Arguments given by the user: $ARGUMENTS

1. Find the quote and the brief from the arguments, or in the current folder (`quote.md` or `devis.md`, `brief.md` or the client's email). Ask once if one of them is missing.
2. Run `brief-reader` on the brief. It writes `scope.md`.
3. Run `quote-auditor` on the quote, the brief and `scope.md`, with the tax rates given in the arguments.
4. Print the report and exactly one final line: `QUOTE: SEND` when nothing is left, otherwise `QUOTE: FIX FIRST (<n>)`.

Never send anything to the client, and never edit the quote without an explicit yes.
