#!/usr/bin/env bash
# Builds the test repository of rule-guard: a small shop project whose
# CLAUDE.md has 10 rules (4 dangers, 4 checkable style rules, 2 rules that
# need judgment), and the .rule-guard/rules.tsv that the rule-guard skill
# writes for that CLAUDE.md (the 2 judgment rules stay as comments).
#   bash test/build_repo.sh /tmp/shop     (the directory must not exist)
set -eu
REPO="${1:?usage: build_repo.sh <new directory>}"
if [ -e "$REPO" ]; then echo "$REPO already exists" >&2; exit 1; fi
mkdir -p "$REPO"
cd "$REPO"
git init -q
git symbolic-ref HEAD refs/heads/main
git config user.name "rule-guard test"
git config user.email "test@example.invalid"
git config commit.gpgsign false
git config core.hooksPath .git/hooks

cat > CLAUDE.md <<'EOF'
# CLAUDE.md

Shop: a small Node front end (`src/`) and a Python order service (`app/`).

## Security, never break these
1. Never hardcode an API key or a token in the code: read it from the environment.
2. Never commit a private key.
3. Never commit the `.env` file.
4. No `DROP TABLE` in a migration: migrations must stay reversible.

## Style
5. No long dash in the docs (Markdown files): use a colon, a comma or a new sentence.
6. No `console.log` in `src/`: use the logger in `src/log.js`.
7. Every TODO names its issue, like `TODO(#123)`.
8. No `print(` debugging in the Python app code (`app/`): use `logging`.

## Habits
9. Write clear commit messages that say why.
10. Keep functions small.
EOF

mkdir -p .rule-guard
rule() { printf '%s\t%s\t%s\t%s\t%s\n' "$@"; }
{
  echo "# rule-guard rules, written from CLAUDE.md by the rule-guard skill."
  echo "# One rule per line, 5 fields separated by tabs: level, kind, pattern, message, fix."
  echo "#   level: block (real danger, the commit is refused) or warn (reported, never refused)"
  echo "#   kind:  content (extended regex on added lines), content:<glob> (same, only in"
  echo "#          matching files), path (glob on the paths the commit adds or changes)"
  echo "# CLAUDE.md:6 never hardcode an API key or a token (one line per key format)"
  rule block content 'AKIA[0-9A-Z]{16}' 'AWS access key in clear' 'read it from an environment variable, and rotate the key if it was ever pushed'
  rule block content '(sk|rk)_live_[0-9A-Za-z]{16,}' 'Stripe live key in clear' 'read it from an environment variable, and roll the key in the Stripe dashboard'
  rule block content 'gh[pousr]_[0-9A-Za-z]{36}' 'GitHub token in clear' 'read it from an environment variable, and revoke the token'
  echo "# CLAUDE.md:7 never commit a private key"
  rule block content '-----BEGIN ([A-Z]+ )?PRIVATE KEY-----' 'private key' 'take the file out of the commit and keep the key outside the repository'
  echo "# CLAUDE.md:8 never commit the .env file"
  rule block path '.env' '.env file' 'git rm --cached the file, then add .env to .gitignore'
  echo "# CLAUDE.md:9 no DROP TABLE in a migration"
  rule block 'content:migrations/*' '(DROP|drop)[[:space:]]+(TABLE|table)' 'DROP TABLE in a migration' 'write a reversible migration (rename or archive the table)'
  echo "# CLAUDE.md:12 no long dash in the docs (Markdown files)"
  rule warn 'content:*.md' '\u2014' 'long dash in a Markdown file' 'use a colon, a comma or a new sentence'
  echo "# CLAUDE.md:13 no console.log in src/"
  rule warn 'content:src/*' 'console\.log\(' 'console.log in src/' 'use the logger in src/log.js'
  echo "# CLAUDE.md:14 every TODO names its issue"
  rule warn content 'TODO($|[^(]|\(($|[^#]|#($|[^0-9])))' 'TODO without an issue number' 'write TODO(#<issue>)'
  echo "# CLAUDE.md:15 no print( debugging in app/"
  rule warn 'content:app/*.py' '(^|[^A-Za-z0-9_.])print\(' 'print( debugging in app/' 'use the logging module'
  echo '# not checkable (judgment): "Write clear commit messages that say why." (CLAUDE.md:18)'
  echo '# not checkable (judgment): "Keep functions small." (CLAUDE.md:19)'
} > .rule-guard/rules.tsv

mkdir -p src app migrations docs scripts
cat > src/cart.js <<'EOF'
// Cart totals.
export function total(items) {
  return items.reduce((sum, item) => sum + item.price * item.qty, 0);
}
EOF
cat > src/log.js <<'EOF'
export const log = (...args) => process.stderr.write(args.join(" ") + "\n");
EOF
cat > app/orders.py <<'EOF'
import logging

log = logging.getLogger(__name__)


def place(order):
    log.info("order %s placed", order["id"])
    return order["id"]
EOF
cat > migrations/0001_init.sql <<'EOF'
CREATE TABLE orders (id INTEGER PRIMARY KEY, total INTEGER NOT NULL);
EOF
cat > docs/guide.md <<'EOF'
# Guide

Run the shop with `npm start`.
EOF
cat > scripts/dev.js <<'EOF'
// Local helpers, not shipped.
EOF
printf 'node_modules/\n' > .gitignore

git add -A
git commit -q -m "Initial shop project"
git tag base
echo "$REPO"
