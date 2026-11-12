#!/usr/bin/env bash
# pr-squad PreToolUse hook: block pull request creation until the current
# commit has a pr-squad verdict (written by /pr-squad:ship or the
# review-before-pr skill in <git dir>/pr-squad/<HEAD sha>).
# Plain bash and git only, so it also runs in Git Bash on Windows.
# Turn it off with PR_SQUAD_SKIP=1.

input="$(cat)"
[ "${PR_SQUAD_SKIP:-0}" = "1" ] && exit 0

# Only act on pull request creation: gh / glab CLI, or an MCP tool that creates a PR.
if ! printf '%s' "$input" | grep -Eq 'gh[[:space:]]+pr[[:space:]]+create|glab[[:space:]]+mr[[:space:]]+create|"tool_name"[[:space:]]*:[[:space:]]*"mcp__[^"]*create_pull_request'; then
  exit 0
fi

dir="${CLAUDE_PROJECT_DIR:-$PWD}"
git_dir="$(git -C "$dir" rev-parse --absolute-git-dir 2>/dev/null)" || exit 0
head="$(git -C "$dir" rev-parse HEAD 2>/dev/null)" || exit 0

[ -f "$git_dir/pr-squad/$head" ] && exit 0

reason="pr-squad: no review recorded for commit ${head:0:7}. Before creating the pull request, run the pr-squad review on this branch (review-before-pr skill, same steps as /pr-squad:ship), show the user the summary table and the SHIP line, record the verdict, then create the PR. Set PR_SQUAD_SKIP=1 to turn this check off."
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$reason"
exit 0
