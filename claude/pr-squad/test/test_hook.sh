#!/usr/bin/env bash
# Replays the pr-squad hook (hooks/require-review.sh) on the inputs Claude Code
# sends before a tool call, in a throwaway git repository.
#   bash test/test_hook.sh
set -u
HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/require-review.sh"
REPO="$(mktemp -d)"
git -C "$REPO" init -q
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
export CLAUDE_PROJECT_DIR="$REPO"

pass=0; fail=0
check() { # name, expected (deny|allow), stdin json, [env]
  local name="$1" expected="$2" json="$3" out got
  out="$(printf '%s' "$json" | env ${4:-} bash "$HOOK")"
  if printf '%s' "$out" | grep -q '"permissionDecision":"deny"'; then got=deny; else got=allow; fi
  if [ "$got" = "$expected" ]; then pass=$((pass+1)); echo "ok    $name -> $got"
  else fail=$((fail+1)); echo "FAIL  $name -> $got (expected $expected)"; fi
}

PR='{"tool_name":"Bash","tool_input":{"command":"gh pr create --title \"feat: discount\" --body-file pr.md"}}'
MR='{"tool_name":"Bash","tool_input":{"command":"glab mr create --fill"}}'
MCP='{"tool_name":"mcp__github__create_pull_request","tool_input":{"owner":"me","repo":"app","title":"x"}}'
PUSH='{"tool_name":"Bash","tool_input":{"command":"git push -u origin feat/discounts"}}'
LS='{"tool_name":"Bash","tool_input":{"command":"ls -la"}}'

check "gh pr create, no review"           deny  "$PR"
check "glab mr create, no review"         deny  "$MR"
check "MCP create_pull_request, no review" deny "$MCP"
check "git push is not a PR"              allow "$PUSH"
check "unrelated command"                 allow "$LS"
check "PR_SQUAD_SKIP=1"                   allow "$PR" "PR_SQUAD_SKIP=1"

# Record a verdict for HEAD the way /pr-squad:ship does.
(cd "$REPO" && d="$(git rev-parse --absolute-git-dir)/pr-squad" && mkdir -p "$d" \
  && printf '%s\n' "SHIP: STOP (4 BLOCK)" > "$d/$(git rev-parse HEAD)")
check "gh pr create, HEAD reviewed"       allow "$PR"

# A new commit after the review asks for a new review.
git -C "$REPO" -c user.name=t -c user.email=t@t commit -q --allow-empty -m change
check "gh pr create, new commit since review" deny "$PR"

echo "passed $pass, failed $fail"
[ "$fail" -eq 0 ]
