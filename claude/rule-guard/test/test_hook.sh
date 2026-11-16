#!/usr/bin/env bash
# Replays the rule-guard hook (hooks/rule-guard.sh) on the inputs Claude Code
# sends before a Bash tool call, in a throwaway repository built by
# build_repo.sh, then runs the same script as a git pre-commit hook.
# Single entry point:
#   bash test/test_hook.sh
# No real secret is written in this file: the fake keys and the long dash are
# assembled at run time. python3, when present, only checks that the hook
# prints valid JSON (Claude Code ignores invalid JSON, so a danger would pass).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
HOOK="$HERE/../hooks/rule-guard.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
REPO="$WORK/shop"
bash "$HERE/build_repo.sh" "$REPO" >/dev/null || { echo "build_repo.sh failed"; exit 1; }
export CLAUDE_PROJECT_DIR="$REPO"
unset RULE_GUARD_SKIP
HAVE_PY=0; command -v python3 >/dev/null 2>&1 && HAVE_PY=1

# Fake secrets and the long dash, assembled here so no file of the pack holds one.
AWS_KEY="AKIA""TESTONLY""FAKE1234"
STRIPE_KEY="sk_""live_""testonly0fake0key0000000"
GH_TOKEN="ghp""_""$(printf '0%.0s' 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36)"
PEM_HEAD="-----BEGIN ""RSA PRIVATE"" KEY-----"
PEM_TAIL="-----END ""RSA PRIVATE"" KEY-----"
LONG_DASH="$(printf '\342\200\224')"

now_ms() { local t; t="$(date +%s%N 2>/dev/null)"; case "$t" in *N|'') echo 0 ;; *) echo $((t / 1000000)) ;; esac; }
jstr() {
  local s="$1"
  s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; s="${s//$'\n'/\\n}"; s="${s//$'\t'/\\t}"
  printf '"%s"' "$s"
}
# The JSON Claude Code sends to a PreToolUse hook before a Bash call.
tool_call() { # command [cwd]
  printf '{"session_id":"test","transcript_path":"/dev/null","cwd":%s,"permission_mode":"default","hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":%s,"description":"test"}}' \
    "$(jstr "${2:-$REPO}")" "$(jstr "$1")"
}
reset_repo() {
  rm -f "$REPO/.git/index.lock" "$REPO/.git/hooks/pre-commit"
  git -C "$REPO" reset -q --hard base 2>/dev/null || { rm -f "$REPO/.git/index"; git -C "$REPO" reset -q --hard base; }
  git -C "$REPO" clean -qfdx
}
in_repo() { (cd "$REPO" && "$@"); }
label() { # decision, everything the hook printed
  local f=""
  case "$2" in *"BLOCK  "*) f="block" ;; esac
  case "$2" in *"WARN   "*) f="${f:+$f+}warn" ;; esac
  case "$2" in *"NOTICE "*) f="${f:+$f+}notice" ;; esac
  if [ -n "$f" ]; then printf '%s(%s)' "$1" "$f"; else printf '%s' "$1"; fi
}

N=0; PASS=0; FAIL=0; ROWS=(); EXPS=(); GOTS=(); TIMES=()
SAMPLE_DENY=""; SAMPLE_WARN=""
row() { # name expected got detail ms ok
  N=$((N + 1))
  [ "$6" = ok ] && PASS=$((PASS + 1)) || FAIL=$((FAIL + 1))
  EXPS[${#EXPS[@]}]="$2"; GOTS[${#GOTS[@]}]="$3"
  ROWS[${#ROWS[@]}]="$(printf '%-3s %-56s %-24s %-24s %-28s %-5s %s' "$N" "$1" "$2" "$3" "$4" "$5" "$6")"
}
shown() { # the wants, as printed in the table
  local s="$1"
  s="${s//BLOCK  /}"; s="${s//WARN   /}"; s="${s//  |/|}"; s="${s%  }"; s="${s//|/, }"
  printf '%s' "$s"
}
wanted() { # output, wants separated by |
  local w rest="$2"
  while [ -n "$rest" ]; do
    w="${rest%%|*}"; [ "$w" = "$rest" ] && rest="" || rest="${rest#*|}"
    case "$1" in *"$w"*) ;; *) return 1 ;; esac
  done
  return 0
}

# One Claude Code case: name, expected, text the output must contain, tool call JSON, [env...]
case_hook() {
  local name="$1" expected="$2" want="$3" json="$4"; shift 4
  local out err rc dec got ok=ok t0 t1 ms detail
  t0=$(now_ms)
  out="$(printf '%s' "$json" | env "$@" bash "$HOOK" 2>"$WORK/err")"; rc=$?
  t1=$(now_ms); ms=$((t1 - t0)); TIMES[${#TIMES[@]}]=$ms
  err="$(cat "$WORK/err")"
  if printf '%s' "$out" | grep -q '"permissionDecision":"deny"'; then dec=deny; else dec=allow; fi
  got="$(label "$dec" "$out$err")"
  [ "$got" = "$expected" ] || ok=FAIL
  [ "$rc" -eq 0 ] || ok=FAIL
  if [ -n "$out" ] && [ "$HAVE_PY" = 1 ]; then
    printf '%s' "$out" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null || ok=FAIL
  fi
  detail="-"
  if [ -n "$want" ]; then
    if wanted "$out$err" "$want"; then detail="$(shown "$want")"; else ok=FAIL; detail="missing: $want"; fi
  fi
  case "$expected" in deny*) case "$out" in *"Fix: "*) ;; *) ok=FAIL ;; esac ;; esac
  [ "$expected" = "allow" ] && [ -n "$out$err" ] && ok=FAIL
  case "$name" in *"warn + block"*) SAMPLE_DENY="$out" ;; *"long dash"*) SAMPLE_WARN="$out" ;; esac
  row "$name" "$expected" "$got" "$detail" "$ms" "$ok"
}

# One git pre-commit case: name, expected, text stderr must contain, git commit args...
case_git() {
  local name="$1" expected="$2" want="$3"; shift 3
  local before after err rc dec got ok=ok detail
  cp "$HOOK" "$REPO/.git/hooks/pre-commit"; chmod +x "$REPO/.git/hooks/pre-commit"
  before="$(git -C "$REPO" rev-parse HEAD)"
  err="$(cd "$REPO" && git commit -q "$@" 2>&1 >/dev/null)"; rc=$?
  after="$(git -C "$REPO" rev-parse HEAD)"
  if [ "$after" = "$before" ]; then dec=deny; else dec=allow; fi
  got="$(label "$dec" "$err")"
  [ "$got" = "$expected" ] || ok=FAIL
  if [ "$dec" = deny ] && [ "$rc" -eq 0 ]; then ok=FAIL; fi
  detail="-"
  if [ -n "$want" ]; then
    if wanted "$err" "$want"; then detail="$(shown "$want")"; else ok=FAIL; detail="missing: $want"; fi
  fi
  row "$name" "$expected" "$got" "$detail" "-" "$ok"
}

# One case through the command line of hooks/hooks.json, as Claude Code runs it:
# name, expected, text the output must contain, plugin root, tool call JSON
HOOK_CMD="$(sed -n 's/.*"command": "\(.*\)",$/\1/p' "$HERE/../hooks/hooks.json" | sed 's/\\"/"/g')"
case_cmd() {
  local name="$1" expected="$2" want="$3" root="$4" json="$5"
  local out err rc got ok=ok detail
  out="$(printf '%s' "$json" | CLAUDE_PLUGIN_ROOT="$root" sh -c "$HOOK_CMD" 2>"$WORK/err")"; rc=$?
  err="$(cat "$WORK/err")"
  if [ "$rc" -eq 2 ] || printf '%s' "$out" | grep -q '"permissionDecision":"deny"'; then
    got="$(label deny "$out$err")"
  elif [ "$rc" -ne 0 ]; then got="allow(exit $rc)"
  else got="$(label allow "$out$err")"; fi
  [ "$got" = "$expected" ] || ok=FAIL
  detail="-"
  if [ -n "$want" ]; then
    if wanted "$out$err" "$want"; then detail="$(shown "$want")"; else ok=FAIL; detail="missing: $want"; fi
  fi
  row "$name" "$expected" "$got" "$detail" "-" "$ok"
}

# ------------------------------------------------------------ the 4 dangers
reset_repo
printf 'export const API_KEY = "%s";\n' "$AWS_KEY" > "$REPO/src/config.js"
in_repo git add src/config.js
case_hook "API key (AWS format) in src/config.js" "deny(block)" "src/config.js:1" "$(tool_call 'git commit -m "Add config"')"

reset_repo
printf 'import os\n\nSTRIPE_KEY = "%s"\n' "$STRIPE_KEY" > "$REPO/app/settings.py"
in_repo git add app/settings.py
case_hook "API key (Stripe live format) in app/settings.py" "deny(block)" "app/settings.py:3" "$(tool_call 'git commit -m "Add settings"')"

reset_repo
mkdir -p "$REPO/deploy"; printf '%s\nMIIfake0notakey\n%s\n' "$PEM_HEAD" "$PEM_TAIL" > "$REPO/deploy/id_rsa"
in_repo git add deploy/id_rsa
case_hook "private key in deploy/id_rsa" "deny(block)" "deploy/id_rsa:1" "$(tool_call 'git commit -m "Add deploy key"')"

reset_repo
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"
in_repo git add .env
case_hook ".env at the root" "deny(block)" "BLOCK  .env  " "$(tool_call 'git commit -m "Add env"')"

reset_repo
mkdir -p "$REPO/api"; printf 'DB_PASSWORD=changeme\n' > "$REPO/api/.env"
in_repo git add api/.env
case_hook ".env in a subfolder (api/.env)" "deny(block)" "BLOCK  api/.env  " "$(tool_call 'git commit -m "Add api env"')"

reset_repo
printf 'DROP TABLE legacy_orders;\n' > "$REPO/migrations/0002_drop_legacy.sql"
in_repo git add migrations
case_hook "DROP TABLE in migrations/0002_drop_legacy.sql" "deny(block)" "migrations/0002_drop_legacy.sql:1" "$(tool_call 'git commit -m "Drop legacy table"')"

# ------------------------------------------------------------ the 4 style rules
reset_repo
printf '\nShipping is free above 50 euros %s no code needed.\n' "$LONG_DASH" >> "$REPO/docs/guide.md"
in_repo git add docs/guide.md
case_hook "long dash in docs/guide.md" "allow(warn)" "docs/guide.md:5" "$(tool_call 'git commit -m "Document shipping"')"

reset_repo
printf 'console.log("total", total);\n' >> "$REPO/src/cart.js"
in_repo git add src/cart.js
case_hook "console.log in src/cart.js" "allow(warn)" "src/cart.js:5" "$(tool_call 'git commit -m "Debug cart"')"

reset_repo
printf '# TODO: handle refunds\n' >> "$REPO/app/orders.py"
in_repo git add app/orders.py
case_hook "TODO without an issue number in app/orders.py" "allow(warn)" "app/orders.py:9" "$(tool_call 'git commit -m "Note refunds"')"

reset_repo
printf '\ndef cancel(order):\n    print("cancel", order)\n    return None\n' >> "$REPO/app/orders.py"
in_repo git add app/orders.py
case_hook "print( debugging in app/orders.py" "allow(warn)" "app/orders.py:11" "$(tool_call 'git commit -m "Add cancel"')"

# ------------------------------------------------------------ clean commits
reset_repo
printf 'DB_PASSWORD=\nSTRIPE_KEY=\n' > "$REPO/.env.example"
printf 'export const API_KEY = process.env.API_KEY;\nexport const job = "task-runner-configuration-loader";\n' > "$REPO/src/config.js"
printf '# Migrations\n\nNever use DROP TABLE in a migration.\n' > "$REPO/docs/migrations.md"
printf 'console.log("dev only");\n' >> "$REPO/scripts/dev.js"
printf '// TODO(#42): handle refunds\n' >> "$REPO/src/cart.js"
printf 'from pprint import pprint\n\n\ndef dump(data):\n    pprint(data)\n' > "$REPO/app/report.py"
in_repo git add -A
case_hook "clean commit with 6 near misses (.env.example...)" "allow" "" "$(tool_call 'git commit -m "Add config, report and docs"')"

reset_repo
{ printf 'export function big(order) {\n'; i=1; while [ $i -le 120 ]; do printf '  order.step%s = %s;\n' $i $i; i=$((i + 1)); done; printf '  return order;\n}\n'; } > "$REPO/src/big.js"
in_repo git add src/big.js
case_hook "judgment rules only: message \"wip\", 120-line function" "allow" "" "$(tool_call 'git commit -m "wip"')"

# ------------------------------------------------------------ mixed and commit forms
reset_repo
printf 'console.log("total", total);\n' >> "$REPO/src/cart.js"
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"
in_repo git add src/cart.js .env
case_hook "warn + block in one commit (console.log + .env)" "deny(block+warn)" "BLOCK  .env  |WARN   src/cart.js:5" "$(tool_call 'git commit -m "Cart and env"')"

reset_repo
printf 'const KEY = "%s";\n' "$AWS_KEY" >> "$REPO/src/cart.js"
case_hook "git commit -am, API key only in the working tree" "deny(block)" "src/cart.js:5" "$(tool_call 'git commit -am "Update cart"')"

reset_repo
printf 'const KEY = "%s";\n' "$AWS_KEY" >> "$REPO/src/cart.js"
printf '// Run with node.\n' >> "$REPO/scripts/dev.js"
in_repo git add scripts/dev.js
case_hook "git commit (no -a), same key left unstaged" "allow" "" "$(tool_call 'git commit -m "Update dev helper"')"

reset_repo
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"
case_hook "git add -A && git commit, new .env untracked" "deny(block)" "BLOCK  .env  " "$(tool_call 'git add -A && git commit -m "Save work"')"

reset_repo
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"
printf '// Totals are in cents.\n' >> "$REPO/src/cart.js"
case_hook "git add src/cart.js && git commit, .env left out" "allow" "" "$(tool_call 'git add src/cart.js && git commit -m "Document cents"')"

reset_repo
printf '#!/bin/sh\nexport GITHUB_TOKEN=%s\n' "$GH_TOKEN" > "$REPO/scripts/deploy.sh"
in_repo git add scripts/deploy.sh
HEREDOC_CMD="$(printf 'git commit -m "$(cat <<%sEOF%s\nAdd deploy script\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nEOF\n)"' "'" "'")"
case_hook "heredoc message (Claude Code style), GitHub token" "deny(block)" "scripts/deploy.sh:2" "$(tool_call "$HEREDOC_CMD")"

reset_repo
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"; in_repo git add .env
case_hook "git -C <repo> commit, run from another folder" "deny(block)" "BLOCK  .env  " "$(tool_call "git -C $REPO commit -m env" "$WORK")"
case_hook "cd <repo> && git commit, run from another folder" "deny(block)" "BLOCK  .env  " "$(tool_call "cd $REPO && git commit -m env" "$WORK")"
case_hook "not a commit: git status, .env staged" "allow" "" "$(tool_call 'git status --short')"
case_hook "RULE_GUARD_SKIP=1, .env staged" "allow" "" "$(tool_call 'git commit -m env')" RULE_GUARD_SKIP=1

# ------------------------------------------------------------ the hook's own failures
case_cmd "hooks.json command line, .env staged" "deny(block)" "BLOCK  .env  " "$HERE/.." "$(tool_call 'git commit -m env')"
mkdir -p "$WORK/broken/hooks"; printf 'if then fi\n' > "$WORK/broken/hooks/rule-guard.sh"
case_cmd "hooks.json command line, script with a syntax error" "allow(exit 1)" "syntax error" "$WORK/broken" "$(tool_call 'git commit -m env')"

rm "$REPO/.rule-guard/rules.tsv"
case_hook "missing rules file, .env staged" "allow(notice)" "no .rule-guard/rules.tsv" "$(tool_call 'git commit -m env')"

reset_repo
nlines="$(wc -l < "$REPO/.rule-guard/rules.tsv" | tr -d ' ')"
{ printf 'block\tcontent\n'; printf 'warn\tcontent\t([unclosed\tbroken regex\tfix it\n'; printf 'error\tpath\t*.log\tlog file\tremove it\n'; } >> "$REPO/.rule-guard/rules.tsv"
printf 'console.log("total", total);\n' >> "$REPO/src/cart.js"
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"
in_repo git add src/cart.js .env
case_hook "3 malformed rules lines, .env + console.log staged" "deny(block+warn+notice)" "line $((nlines + 1)) skipped|line $((nlines + 2)) skipped|line $((nlines + 3)) skipped|BLOCK  .env  " "$(tool_call 'git commit -m env')"

mkdir -p "$WORK/plain"
case_hook "not a git repository" "allow(notice)" "not inside a git repository" "$(tool_call 'git commit -m x' "$WORK/plain")"

reset_repo
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"; in_repo git add .env
printf 'not an index' > "$REPO/.git/index"
case_hook "unreadable diff (corrupt index)" "allow(notice)" "could not read the diff" "$(tool_call 'git commit -m env')"

# ------------------------------------------------------------ as a git pre-commit hook
reset_repo
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"; in_repo git add .env
case_git "git pre-commit hook: .env staged" "deny(block)" "BLOCK  .env  " -m "Add env"

reset_repo
printf 'console.log("total", total);\n' >> "$REPO/src/cart.js"; in_repo git add src/cart.js
case_git "git pre-commit hook: console.log staged" "allow(warn)" "src/cart.js:5" -m "Debug cart"

reset_repo
printf 'const KEY = "%s";\n' "$AWS_KEY" >> "$REPO/src/cart.js"
case_git "git pre-commit hook: commit -a, key unstaged" "deny(block)" "src/cart.js:5" -a -m "Update cart"

reset_repo
printf 'DB_PASSWORD=changeme\n' > "$REPO/.env"; in_repo git add .env
err="$(cd "$REPO/src" && bash "$HOOK" --git-hook 2>&1 </dev/null)"; rc=$?
if [ "$rc" -eq 1 ]; then got="$(label deny "$err")"; else got="$(label allow "$err")"; fi
ok=ok; [ "$got" = "deny(block)" ] || ok=FAIL; wanted "$err" "BLOCK  .env  " || ok=FAIL
row "run by hand with --git-hook (skill self-check)" "deny(block)" "$got" ".env" "-" "$ok"

# ------------------------------------------------------------ report
show_json_text() { # prints the text fields of the hook output
  if [ "$HAVE_PY" = 1 ]; then
    printf '%s' "$1" | python3 -c 'import json,sys
o = json.load(sys.stdin); h = o.get("hookSpecificOutput", {})
for k, v in (("permissionDecision", h.get("permissionDecision")), ("permissionDecisionReason", h.get("permissionDecisionReason")), ("systemMessage", o.get("systemMessage"))):
    if v: print("[" + k + "]"); print(v)'
  else
    printf '%s\n' "$1"
  fi
}
echo "rule-guard hook test, $(date -u +%Y-%m-%d), git $(git --version | awk '{print $3}'), bash ${BASH_VERSION}"
echo
echo "Sample: what Claude receives when a commit is refused (case \"warn + block in one commit\")"
show_json_text "$SAMPLE_DENY"
echo
echo "Sample: what the user sees when a commit only warns (case \"long dash in docs/guide.md\")"
show_json_text "$SAMPLE_WARN"
echo
printf '%-3s %-56s %-24s %-24s %-28s %-5s %s\n' "#" "case" "expected" "got" "reported" "ms" "check"
for r in "${ROWS[@]}"; do echo "$r"; done
echo

blocked=0; blocks=0; warned=0; warns=0; false_blocks=0; allows=0; own_fail_blocks=0; own=0
i=0
while [ "$i" -lt "$N" ]; do
  exp="${EXPS[i]}"; got="${GOTS[i]}"; i=$((i + 1))
  case "$exp" in
    deny*) blocks=$((blocks + 1)); case "$got" in deny*) blocked=$((blocked + 1)) ;; esac ;;
    *) allows=$((allows + 1)); case "$got" in deny*) false_blocks=$((false_blocks + 1)) ;; esac ;;
  esac
  case "$exp" in allow\(warn\)) warns=$((warns + 1)); [ "$got" = "allow(warn)" ] && warned=$((warned + 1)) ;; esac
  case "$exp" in allow\(notice\)|allow\(exit*) own=$((own + 1)); case "$got" in deny*) own_fail_blocks=$((own_fail_blocks + 1)) ;; esac ;; esac
done
sorted="$(printf '%s\n' "${TIMES[@]}" | sort -n)"
nt=${#TIMES[@]}
median="$(printf '%s\n' "$sorted" | awk -v n="$nt" 'NR == int((n + 1) / 2) { print }')"
slowest="$(printf '%s\n' "$sorted" | tail -n 1)"
echo "commits that had to be refused: $blocked/$blocks refused"
echo "commits that had to go through: $((allows - false_blocks))/$allows went through ($false_blocks refused by mistake)"
echo "style-only commits: $warned/$warns went through with their warning shown"
echo "hook failures (no rules file, no repo, unreadable diff, script crash): $own_fail_blocks/$own blocked the commit"
echo "hook time under Claude Code, $nt runs: median ${median} ms, slowest ${slowest} ms"
echo "cases: $N, as expected: $PASS, not as expected: $FAIL"
if [ "$FAIL" -eq 0 ]; then echo "RESULT: PASS"; else echo "RESULT: FAIL"; exit 1; fi
