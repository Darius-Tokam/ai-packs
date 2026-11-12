---
name: review-before-pr
description: Run the full pr-squad review before a pull request is created. Use whenever the user asks to open, create, prepare or submit a pull request or merge request, in any language ("make a PR for the invoice discount", "open a PR", "fais une PR pour ajouter ma facture", "ouvre une PR", "push this for review"), and before running gh pr create, glab mr create or any create-pull-request tool.
---

# review-before-pr

The user asked for a pull request. Review the branch first, then create the PR with what the review found. This is the same review as `/pr-squad:ship`, started by the request instead of the command.

## 1. Goal and base

- Take the goal of the branch from the user's request ("fais une PR pour ajouter ma facture" means the goal is "add the invoice"). Do not ask for it again.
- Find the base: `git merge-base HEAD origin/main`, falling back to `main` then `master`. Print the base, the branch and `git diff --stat` once.

## 2. The 8 checks, in this order

Run each skill and keep its verdict lines. Do not stop at the first problem.

1. `secret-scan`
2. `dep-audit`
3. `migration-guard`
4. `scope-check`, with the goal from step 1
5. `test-gaps`
6. `bug-hunt`
7. `query-check`
8. `pr-writer`, last: it uses every verdict above

Print one summary table:

| Agent | Verdict | Findings |
|---|---|---|

Then exactly one final line:
- `SHIP: GO` when there is no BLOCK and no FIX;
- `SHIP: FIX FIRST (<n> FIX)` when there are FIX but no BLOCK;
- `SHIP: STOP (<n> BLOCK)` when there is at least one BLOCK.

## 3. Record the verdict

The pr-squad hook blocks PR creation until a verdict exists for the current commit:

```bash
d="$(git rev-parse --absolute-git-dir)/pr-squad"; mkdir -p "$d"
printf '%s\n' "<the final SHIP line>" > "$d/$(git rev-parse HEAD)"
```

## 4. Create the PR, or not yet

- `SHIP: GO`: create the PR with the title and description written by pr-writer.
- `SHIP: FIX FIRST` or `SHIP: STOP`: do not create the PR yet. Show the BLOCK and FIX findings, then ask the user: fix first, or open the PR anyway as a draft with the description pr-writer wrote (it starts with DO NOT MERGE when a BLOCK is open). Create it only on an explicit yes.

New commits after the review change HEAD, so the hook asks for a new review. If the new commits only add the tests written by test-gaps, rerun test-gaps alone and record its verdict for the new HEAD. Otherwise rerun the whole review.

Never modify application code during the review. The only files you may create are the tests written by test-gaps. Propose every other fix and let the user decide.
