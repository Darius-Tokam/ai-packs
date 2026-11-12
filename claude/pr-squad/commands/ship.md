---
description: Run the 8 pr-squad agents on the current branch and give one merge verdict.
argument-hint: "[goal of the branch, optional]"
---

Review the current branch before it is pushed or merged. Goal given by the user: $ARGUMENTS

1. Find the base: `git merge-base HEAD origin/main`, falling back to `main` then `master`. Print the base, the branch and `git diff --stat` once.
2. Run these skills in this order. Each one reports with its own verdict lines. Do not stop at the first problem.
   1. `secret-scan`
   2. `dep-audit`
   3. `migration-guard`
   4. `scope-check` (use the goal above if one was given)
   5. `test-gaps`
   6. `bug-hunt`
   7. `query-check`
   8. `pr-writer` (last, it uses every verdict above)
3. Print one summary table:

| Agent | Verdict | Findings |
|---|---|---|

4. Final line, exactly one of:
   - `SHIP: GO` when there is no BLOCK and no FIX;
   - `SHIP: FIX FIRST (<n> FIX)` when there are FIX but no BLOCK;
   - `SHIP: STOP (<n> BLOCK)` when there is at least one BLOCK.
5. Record the verdict for the current commit. The pr-squad hook only lets `gh pr create` (or a create-pull-request tool) through once this file exists for HEAD:

```bash
d="$(git rev-parse --absolute-git-dir)/pr-squad"; mkdir -p "$d"
printf '%s\n' "<the final SHIP line>" > "$d/$(git rev-parse HEAD)"
```

Do not modify application code. The only files you may create are the tests written by `test-gaps`. Propose every other fix and let the user decide.
