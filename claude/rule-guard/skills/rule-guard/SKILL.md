---
name: rule-guard
description: Turn the rules of the project's CLAUDE.md into checks that the rule-guard hook runs before every git commit, written to .rule-guard/rules.tsv. Real dangers block the commit, style rules only warn, rules that need judgment stay unchecked. Use when the user asks to turn their CLAUDE.md rules into checks or to enforce project rules on commit, or complains that the agent forgets or breaks a rule, in any language ("transforme mes règles CLAUDE.md en contrôles", "mon agent oublie mes règles", "turn my CLAUDE.md rules into commit checks", "enforce my project rules on commit"). Also use when the user wants to change a rule after rule-guard refused or warned about a commit.
---

# rule-guard

The user wants the rules of their CLAUDE.md checked on every commit instead of repeated in every prompt. Write them to `.rule-guard/rules.tsv` at the repository root. The rule-guard hook reads that file before each `git commit` run through the Bash tool and checks what the commit adds: the added lines and the paths of the added or changed files.

## 1. Read the rules

- Read `CLAUDE.md` at the repository root, `.claude/CLAUDE.md`, and every `CLAUDE.md` in a subdirectory (its rules apply to that directory only: scope them with a glob).
- If `.rule-guard/rules.tsv` already exists, read it first. Keep every line in it, including a level the user changed by hand. Add the new rules. Never delete or weaken a rule without asking.
- List every rule as one numbered line, quoted from the file, with its file and line number.

## 2. Sort each rule

For each rule, ask: can a machine see a break of this rule in a staged diff, with no judgment?

- A forbidden file or folder: kind `path`.
- Forbidden text in the added lines: kind `content`, or `content:<glob>` when the rule is about some files only.
- Anything else is not checkable. Write it as a comment and move on:
  `# not checkable (judgment): "Keep functions small." (CLAUDE.md:14)`

Do not invent a pattern that only looks like the rule. "Keep functions small" is not "more than 50 lines"; "write clear commit messages" is not "message shorter than 10 characters". A made-up pattern blocks good work or gives false comfort. Usually not checkable: naming, clarity, size, architecture, "ask before", "add tests for", commit message quality, and any rule about something that must be present (a header, a test, a changelog entry).

## 3. Choose the level

`block` only for real dangers, where a commit that goes through costs more than a refused one:

- a secret in clear, matched by its known format: AWS `AKIA[0-9A-Z]{16}`, Stripe `(sk|rk)_live_[0-9A-Za-z]{16,}`, GitHub `gh[pousr]_[0-9A-Za-z]{36}`, Slack `xox[baprs]-[0-9A-Za-z-]{10,}`, a private key `-----BEGIN ([A-Z]+ )?PRIVATE KEY-----`;
- env and credential files: `.env`, `*.pem`, `id_rsa`, `credentials.json`, and the variants the project really uses (`.env.local`, `.env.production`). Never `.env.*` when the project commits a `.env.example`;
- generated artifacts the project says never to commit: `dist/`, `build/`, `node_modules/`, `*.pyc`;
- destructive SQL in migrations: `DROP TABLE`, `TRUNCATE`, `DROP COLUMN`, scoped to the migrations folder;
- a rule the user explicitly asks to block. Say so in a comment above it.

Everything else is `warn`: style, wording, typography, logging, debug prints, TODO format. When in doubt, `warn`. A warn rule that matches too much costs one line of output; a block rule that matches too much freezes the work. Generic secret heuristics (`password = "..."`, `api_key=`) also match tests and placeholders: `warn`, never `block`.

## 4. Write the patterns

- A `content` pattern is a POSIX extended regex as `grep -E` reads it, tested on one added line at a time, case-sensitive. No `\d`, `\w`, `\s` or lookahead: write `[0-9]`, `[A-Za-z0-9_]`, `[[:space:]]`. Write case variants out: `(DROP|drop)[[:space:]]+(TABLE|table)`. "X not followed by Y" is written with alternatives: `TODO($|[^(]|\(($|[^#]|#($|[^0-9])))` catches a TODO without `(#<number>)`.
- Write a non-ASCII character as `\uXXXX` (`\u00a0` for a no-break space): the hook turns it into the character, and the rules file stays ASCII.
- A glob (in `content:<glob>` and in `path`): `*` matches any characters, `/` included. A glob without `/` also matches the file name alone, so `.env` matches `api/.env` and `*.md` matches `docs/guide.md`. A glob with `/` matches the whole path from the root: `src/*`, `migrations/*`. `**/` is accepted.
- Test every content pattern before you write it, on one line it must catch and one it must not:

  ```bash
  printf '%s\n' 'console.log(total)' '// console logging is off' | grep -nE 'console\.log\('
  ```

- Never paste a real secret into a test line or into the rules file. Build test values from parts if you need one.

## 5. Write the file

Five fields separated by real tabs: level, kind, pattern, message, fix. The message names the rule in a few words; the fix is one action. Lines starting with `#` are comments. Write the file with `printf` so the tabs are real:

```bash
mkdir -p .rule-guard
rule() { printf '%s\t%s\t%s\t%s\t%s\n' "$@"; }
{
  echo "# rule-guard rules, written from CLAUDE.md. Fields: level, kind, pattern, message, fix (tab-separated)."
  echo "# CLAUDE.md:7 never commit the .env file"
  rule block path '.env' '.env file' 'git rm --cached the file, then add .env to .gitignore'
  echo "# CLAUDE.md:12 no console.log in src/"
  rule warn 'content:src/*' 'console\.log\(' 'console.log in src/' 'use the project logger'
  echo '# not checkable (judgment): "Keep functions small." (CLAUDE.md:14)'
} > .rule-guard/rules.tsv
```

Put a comment above each group of lines with the CLAUDE.md rule it comes from.

## 6. Check the file

Run the hook once on the current index. It must print no `NOTICE ... skipped` line. If it does, fix that line:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/hooks/rule-guard.sh" --git-hook; echo "exit $?"
```

Exit 1 only means the files staged right now break a block rule: show those items to the user.

## 7. Show the user

In the user's language, one row per CLAUDE.md rule, in the order of the file:

| # | Rule (CLAUDE.md) | Level | Check |
|---|---|---|---|
| 3 | Never commit the `.env` file | block | path `.env` |
| 6 | No `console.log` in `src/` | warn | content `console\.log\(` in `src/*` |
| 10 | Keep functions small | not checkable | needs judgment, stays in CLAUDE.md |

Then one line: `<n> rules: <b> block, <w> warn, <j> not checkable.`

Tell the user:
- to move a rule between `block` and `warn`, they change the first field of its line;
- to commit `.rule-guard/rules.tsv` so the whole team gets the same checks. Do not commit it yourself unless asked;
- to turn the hook off: `RULE_GUARD_SKIP=1` in the environment of Claude Code.

## When the hook refuses or warns about a commit

- Refused: fix the BLOCK items, stage the fix, commit again. Never edit `.rule-guard/rules.tsv`, lower a rule to `warn` or rewrite the commit command to get past the check unless the user asks. If a match looks like a false positive, show it to the user and let them decide.
- Warned: the commit went through. Tell the user what was reported and offer a fix in a follow-up commit. Do not amend or rewrite the commit without asking.
- A notice (no rules file, a skipped line, no repository): the commit went through unchecked. Say so, and offer to write or fix the rules file.
