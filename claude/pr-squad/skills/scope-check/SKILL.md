---
name: scope-check
description: Compare a branch diff against its stated goal and flag every change that does not serve it. Use before opening or merging a pull request, or when the user asks whether a diff "does only what it says".
---

# scope-check

You check that a diff does one thing: the thing its author says it does.

## 1. Find the goal

Take the first available, in this order, and quote it verbatim in your report:

1. The goal the user gave you in this conversation.
2. The pull request title and body (`gh pr view --json title,body` if `gh` works).
3. The last commit subjects on the branch: `git log --format=%s <base>..HEAD`.
4. The branch name.

If none says what the change is for, stop and ask the user for one sentence.

## 2. Get the diff

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
git diff --stat "$BASE"...HEAD
git diff "$BASE"...HEAD
```

## 3. Judge each hunk

For every hunk, answer one question: would a reviewer who only read the goal expect this hunk?

- **IN**: the goal needs it, or it is a direct consequence (a migration for a new field, a test for new code, an import).
- **OUT**: the goal does not need it. Typical cases: a new feature in another module, an admin action, a refactor of untouched code, a dependency the new code never imports, debug output.
- **UNSURE**: you cannot tell without context. Say what context would settle it.

Never mark a hunk IN because it "looks harmless". Harmless and unrelated is still OUT.

## 4. Report

```
SCOPE | goal: "<quoted goal>"
FIX   | invoices/admin.py:9-21 | adds a CSV export of every client | not needed by the goal | move to its own PR
NOTE  | invoices/views.py:15   | debug print of request headers  | not needed by the goal | delete
OK    | invoices/services.py   | apply_discount() | the goal needs it
```

Verdicts: `FIX` for an OUT hunk that changes behavior, `NOTE` for an OUT hunk with no behavior change, `OK` for IN. End with one line: `SCOPE VERDICT: CLEAN` or `SCOPE VERDICT: SPLIT (<n> hunks out of scope)`.
