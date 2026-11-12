---
name: test-gaps
description: Find functions a branch adds or changes without a test, write the missing tests, run the whole suite and report what fails. Use before a pull request or when the user asks "is this covered?".
---

# test-gaps

You do not report "missing tests". You write them and run them.

## 1. List what changed

```bash
BASE=$(git merge-base HEAD origin/main 2>/dev/null || git merge-base HEAD main 2>/dev/null || git merge-base HEAD master)
git diff -U0 "$BASE"...HEAD
```

List every function, method or class the diff adds or edits. Skip migrations, settings and pure renames.

## 2. Run the existing suite first

Detect the runner: `pytest` (pytest.ini, pyproject, conftest.py), `python manage.py test`, `npm test` / `vitest` / `jest`, `go test ./...`, `cargo test`. Run it and keep the output. A suite that is already red is a finding: report which tests fail and the first line of each error.

## 3. Find the gaps

For each changed unit, search the tests for its name (`grep -rn "<name>" tests/ test/ __tests__/ *_test.go`). No hit means no direct test. A hit that never asserts on the changed behavior also counts as a gap.

## 4. Write the missing tests

For each gap, write the smallest tests that pin the intended behavior:

- one normal case;
- the boundaries the code invites: zero, empty, negative, the maximum, `None`/`null`, a value above 100 for a percentage, a past date for a deadline;
- money and counts as integers: assert on exact values, never on floats.

Follow the project's test style and location. Do not change application code in this skill: a test that fails on a real bug stays failing, and you report it.

## 5. Run again and report

```
FIX   | invoices/services.py:6 apply_discount | no test before this branch | wrote 4 tests in tests/test_discount.py | 2 FAIL: percent=150 returns -500.0 (negative total), returns float not int cents
FIX   | suite | test_invoice_total_sums_lines fails on this branch | IntegrityError: NOT NULL constraint failed: invoices_invoice.discount_percent
OK    | invoices/views.py discounted_invoices | covered by tests/test_views.py
```

End with `TESTS VERDICT: GREEN`, or `TESTS VERDICT: RED (<n> failing, <m> gaps filled)`. Leave the new test files in place so the author sees them.
