#!/usr/bin/env bash
# rule-guard: checks the rules of .rule-guard/rules.tsv (written from your
# CLAUDE.md by the rule-guard skill) on every git commit.
#
# As a Claude Code PreToolUse hook on the Bash tool, it reads the tool call on
# stdin and only acts on `git commit`, including `git commit -a` and
# `git add ... && git commit` in the same command.
# As a plain git pre-commit hook: copy it to .git/hooks/pre-commit (or run it
# with --git-hook). It then checks the index and exits 1 on a block rule.
#
# Two levels. block: a real danger, the commit is refused with the rule, the
# file, the line and the fix. warn: reported, never refused.
# It never blocks on its own failure: no rules file, a malformed rule, no git
# repository or an unreadable diff let the commit through with a notice.
# Plain bash, grep, sed, awk and git. Turn it off with RULE_GUARD_SKIP=1.

RULES_FILE=".rule-guard/rules.tsv"
MAX_SHOWN=15
MAX_UNTRACKED=500
TAB=$'\t'
NL=$'\n'

mode=claude
[ "${1:-}" = "--git-hook" ] && mode=git
[ "$(basename -- "$0")" = "pre-commit" ] && mode=git

input=""
[ "$mode" = claude ] && input="$(cat)"
[ "${RULE_GUARD_SKIP:-0}" = "1" ] && exit 0

blocks=(); warns=(); notices=()
nblock=0; nwarn=0
tmp=""

note() { notices[${#notices[@]}]="  NOTICE $*"; }

json_escape() {
  local s
  s="$(printf '%s' "$1" | tr -d '\000-\010\013\014\016-\037')"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$TAB/\\t}"
  s="${s//$'\r'/\\r}"
  s="${s//$NL/\\n}"
  printf '%s' "$s"
}

# Value of the last "key":"..." string in the hook input, JSON-unescaped
# (enough for a shell command, a path or a tool name).
json_field() {
  local v soh=$'\001'
  v="$(printf '%s' "$input" | tr -d '\n\r' \
    | sed -nE 's/.*"'"$1"'"[[:space:]]*:[[:space:]]*"(([^"\\]|\\.)*)".*/\1/p')"
  v="${v//\\\\/$soh}"
  v="${v//\\\"/\"}"
  v="${v//\\n/$NL}"
  v="${v//\\t/$TAB}"
  v="${v//\\r/}"
  v="${v//\\\//\/}"
  v="${v//$soh/\\}"
  printf '%s' "$v"
}

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

# \uXXXX in a pattern becomes the UTF-8 bytes of that character, so the rules
# file can stay ASCII.
utf8_char() {
  local c=$1
  if [ "$c" -lt 128 ]; then
    printf "\\$(printf '%03o' "$c")"
  elif [ "$c" -lt 2048 ]; then
    printf "\\$(printf '%03o' $((192 + c / 64)))\\$(printf '%03o' $((128 + c % 64)))"
  else
    printf "\\$(printf '%03o' $((224 + c / 4096)))\\$(printf '%03o' $((128 + (c / 64) % 64)))\\$(printf '%03o' $((128 + c % 64)))"
  fi
}
expand_u() {
  local s="$1" out="" hex re='\\u([0-9A-Fa-f]{4})'
  while [[ $s =~ $re ]]; do
    hex="${BASH_REMATCH[1]}"
    out="$out${s%%\\u$hex*}$(utf8_char $((16#$hex)))"
    s="${s#*\\u$hex}"
  done
  printf '%s' "$out$s"
}

norm_glob() {
  local g="$1"
  g="${g//\*\*\//}"
  case "$g" in */) g="$g*" ;; esac
  printf '%s' "$g"
}

# A glob with a slash matches the whole path (a leading slash anchors it at
# the root); without a slash it also matches the file name alone.
# `*` matches any characters, including `/`.
glob_match() {
  local p="$1" g="$2"
  case "$g" in
    /*) g="${g#/}"; [[ $p == $g ]] ;;
    */*) [[ $p == $g ]] ;;
    *) [[ $p == $g || ${p##*/} == $g ]] ;;
  esac
}

resolve() {
  local p="$2"
  p="${p#[\"\']}"; p="${p%[\"\']}"
  case "$p" in "~") p="$HOME" ;; "~/"*) p="$HOME/${p#\~/}" ;; esac
  case "$p" in /*|[A-Za-z]:*) ;; *) p="$1/$p" ;; esac
  printf '%s' "$p"
}

finish() {
  local text="" item reason ctx
  if [ "$nblock" -gt 0 ]; then
    text="rule-guard: commit refused, $nblock blocking item(s)."
    for item in "${blocks[@]}"; do text="$text$NL$item"; done
    [ "$nblock" -gt "$MAX_SHOWN" ] && text="$text$NL  ... and $((nblock - MAX_SHOWN)) more"
  fi
  if [ "$nwarn" -gt 0 ]; then
    [ -n "$text" ] && text="$text$NL"
    text="${text}rule-guard: $nwarn warning(s), they do not block."
    for item in "${warns[@]}"; do text="$text$NL$item"; done
    [ "$nwarn" -gt "$MAX_SHOWN" ] && text="$text$NL  ... and $((nwarn - MAX_SHOWN)) more"
  fi
  if [ "${#notices[@]}" -gt 0 ]; then
    [ -n "$text" ] && text="$text$NL"
    text="${text}rule-guard could not check everything:"
    for item in "${notices[@]}"; do text="$text$NL$item"; done
  fi

  if [ "$mode" = git ]; then
    if [ "$nblock" -gt 0 ]; then
      text="$text${NL}Fix the BLOCK items and commit again. To skip once: RULE_GUARD_SKIP=1 git commit ..."
    fi
    [ -n "$text" ] && printf '%s\n' "$text" >&2
    [ "$nblock" -gt 0 ] && exit 1
    exit 0
  fi

  if [ "$nblock" -gt 0 ]; then
    reason="$text${NL}Fix the BLOCK items, stage the fix and commit again. Do not edit $RULES_FILE, lower a rule to warn or rewrite the command to get past this check unless the user asks. If a match looks like a false positive, show it to the user: they can set that rule to warn in $RULES_FILE, or turn the check off with RULE_GUARD_SKIP=1."
    printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}\n' "$(json_escape "$reason")"
  elif [ -n "$text" ]; then
    printf '%s\n' "$text" >&2
    if [ "$nwarn" -gt 0 ]; then
      ctx="$text${NL}The commit goes ahead. Tell the user about these warnings and offer to fix them in a follow-up commit."
    else
      ctx="$text${NL}The commit goes ahead unchecked. Tell the user."
    fi
    printf '{"systemMessage":"%s","hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"%s"}}\n' "$(json_escape "$text")" "$(json_escape "$ctx")"
  fi
  exit 0
}

# ---------------------------------------------------------------- the command
is_commit=0; commit_all=0; commit_dir=""; n_add=0
ADD_DIR=(); ADD_ARGS=()

parse_command() {
  local cmd="$1" dir="$2" seg segs sub rest globals gdir prev
  local re_cd='^cd[[:space:]]+([^[:space:]]+)'
  local re_git='^([A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+)*git((([[:space:]]+-[cC][[:space:]]+[^[:space:]]+)|([[:space:]]+--[A-Za-z][A-Za-z-]*(=[^[:space:]]*)?))*)[[:space:]]+(add|commit)([[:space:]].*)?$'
  local re_C='-C[[:space:]]+([^[:space:]]+)'
  local re_all='(^|[[:space:]])(-[A-Za-z]*a[A-Za-z]*|--all)([[:space:]]|$)'
  segs="$(printf '%s\n' "$cmd" | awk '{ gsub(/&&|\|\||;|\|/, "\n"); print }')"
  while IFS= read -r seg; do
    prev=""
    while [ "$seg" != "$prev" ]; do
      prev="$seg"
      seg="$(trim "$seg")"
      seg="${seg#\$(}"; seg="${seg#[({\`\"\']}"
    done
    if [[ $seg =~ $re_cd ]]; then
      dir="$(resolve "$dir" "${BASH_REMATCH[1]}")"
      continue
    fi
    [[ $seg =~ $re_git ]] || continue
    globals="${BASH_REMATCH[2]}"; sub="${BASH_REMATCH[7]}"; rest="${BASH_REMATCH[8]}"
    gdir="$dir"
    [[ $globals =~ $re_C ]] && gdir="$(resolve "$dir" "${BASH_REMATCH[1]}")"
    if [ "$sub" = commit ]; then
      is_commit=1; commit_dir="$gdir"
      [[ $rest =~ $re_all ]] && commit_all=1
      return
    fi
    ADD_DIR[n_add]="$gdir"; ADD_ARGS[n_add]="$rest"; n_add=$((n_add + 1))
  done <<EOF
$segs
EOF
}

if [ "$mode" = claude ]; then
  tool="$(json_field tool_name)"
  [ -n "$tool" ] && [ "$tool" != "Bash" ] && exit 0
  cmd="$(json_field command)"
  case "$cmd" in *commit*) ;; *) exit 0 ;; esac
  cwd="$(json_field cwd)"
  [ -n "$cwd" ] || cwd="${CLAUDE_PROJECT_DIR:-$PWD}"
  parse_command "$cmd" "$cwd"
  [ "$is_commit" = 1 ] || exit 0
else
  commit_dir="$PWD"
fi

# ---------------------------------------------------------------- the repo
top="$(git -C "$commit_dir" rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$top" ]; then
  note "$commit_dir is not inside a git repository: nothing was checked."
  finish
fi
G() { git -C "$top" -c core.quotepath=off "$@"; }

# ---------------------------------------------------------------- the rules
rules="$top/$RULES_FILE"
if [ ! -f "$rules" ]; then
  note "no $RULES_FILE in $top: nothing was checked. Ask Claude to turn your CLAUDE.md rules into checks (rule-guard skill), or set RULE_GUARD_SKIP=1 to turn rule-guard off."
  finish
fi
if [ ! -r "$rules" ]; then
  note "$RULES_FILE is not readable: nothing was checked."
  finish
fi

R_LEVEL=(); R_KIND=(); R_GLOB=(); R_PAT=(); R_MSG=(); R_FIX=(); R_LINE=()
nrules=0
load_rules() {
  local line n=0 rest nf level kind glob pat msg fix
  local -a F
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    line="${line%$'\r'}"
    case "$line" in '#'*) continue ;; esac
    case "$line" in *[![:space:]]*) ;; *) continue ;; esac
    F=(); rest="$line"
    while :; do
      case "$rest" in
        *"$TAB"*) F[${#F[@]}]="${rest%%$TAB*}"; rest="${rest#*$TAB}" ;;
        *) F[${#F[@]}]="$rest"; break ;;
      esac
    done
    nf=${#F[@]}
    if [ "$nf" -lt 4 ] || [ "$nf" -gt 5 ]; then
      note "$RULES_FILE line $n skipped: $nf field(s), expected 5 separated by tabs (level, kind, pattern, message, fix)."
      continue
    fi
    level="$(trim "${F[0]}")"; kind="$(trim "${F[1]}")"; pat="${F[2]}"
    msg="$(trim "${F[3]}")"; fix="$(trim "${F[4]:-}")"
    case "$level" in
      block|warn) ;;
      *) note "$RULES_FILE line $n skipped: level \"$level\" is not block or warn."; continue ;;
    esac
    glob=""
    case "$kind" in
      path|content) ;;
      content:?*) glob="$(norm_glob "${kind#content:}")"; kind=content ;;
      *) note "$RULES_FILE line $n skipped: kind \"$kind\" is not content, content:<glob> or path."; continue ;;
    esac
    if [ -z "$pat" ]; then
      note "$RULES_FILE line $n skipped: empty pattern."
      continue
    fi
    if [ "$kind" = content ]; then
      pat="$(expand_u "$pat")"
      LC_ALL=C grep -E -e "$pat" </dev/null >/dev/null 2>&1
      if [ $? -eq 2 ]; then
        note "$RULES_FILE line $n skipped: the pattern is not a valid extended regex (grep -E)."
        continue
      fi
    else
      pat="$(norm_glob "$pat")"
    fi
    [ -n "$msg" ] || msg="pattern $pat"
    R_LEVEL[nrules]="$level"; R_KIND[nrules]="$kind"; R_GLOB[nrules]="$glob"
    R_PAT[nrules]="$pat"; R_MSG[nrules]="$msg"; R_FIX[nrules]="$fix"; R_LINE[nrules]="$n"
    nrules=$((nrules + 1))
  done < "$rules"
}
load_rules
if [ "$nrules" -eq 0 ]; then
  note "no valid rule in $RULES_FILE: nothing was checked."
  finish
fi

# ---------------------------------------------------------------- the changes
tmp="$(mktemp -d 2>/dev/null || mktemp -d -t rule-guard 2>/dev/null)"
if [ -z "$tmp" ] || [ ! -d "$tmp" ]; then
  note "could not create a temporary directory: nothing was checked."
  finish
fi
trap 'rm -rf "$tmp"' EXIT
: > "$tmp/meta"; : > "$tmp/text"; : > "$tmp/names"

DOPTS=(--no-color --no-ext-diff --no-textconv -U0 --src-prefix=a/ --dst-prefix=b/ --diff-filter=ACMRT)
# Added lines of a unified diff: path<TAB>line in meta, the line itself in text.
AWK_ADDED='
/^diff --git / { hdr = 1; p = ""; next }
hdr && /^\+\+\+ / {
  p = substr($0, 5); sub(/\t$/, "", p)
  if (p ~ /^"/) { p = substr(p, 2); sub(/"$/, "", p) }
  if (p == "/dev/null") p = ""; else sub(/^b\//, "", p)
  if (p ~ /^\.rule-guard\//) p = ""
  next
}
/^@@ / { hdr = 0; s = $0; sub(/^@@ -[0-9,]+ \+/, "", s); sub(/[^0-9].*$/, "", s); n = s + 0; next }
hdr { next }
/^\+/ { if (p != "") { print p "\t" n >> meta; print substr($0, 2) >> text }; n++; next }
'
unreadable=""
read_diff() { # git diff arguments
  if ! G diff "${DOPTS[@]}" "$@" > "$tmp/d" 2> "$tmp/e"; then
    unreadable="$(head -n 1 "$tmp/e")"; return 1
  fi
  awk -v meta="$tmp/meta" -v text="$tmp/text" "$AWK_ADDED" < "$tmp/d"
  G diff --name-only -z --diff-filter=ACMRT "$@" >> "$tmp/names" 2>/dev/null
}

if G rev-parse -q --verify 'HEAD^{commit}' >/dev/null 2>&1; then
  base="HEAD"
else
  base="$(G hash-object -t tree /dev/null 2>/dev/null)"
fi

if [ "$commit_all" = 1 ]; then read_diff "$base"; else read_diff --cached; fi

# `git add ... && git commit` in one command: the files that git add is about
# to stage count too (tracked changes and new files under its pathspecs).
i=0
while [ "$i" -lt "$n_add" ] && [ -z "$unreadable" ]; do
  adir="${ADD_DIR[i]}"; aargs="${ADD_ARGS[i]}"; i=$((i + 1))
  a_all=0; a_update=0; a_force=0; whole=0; specs=(); dashdash=0
  prefix="$(git -C "$adir" rev-parse --show-prefix 2>/dev/null)"
  set -f
  for t in $aargs; do
    t="${t#[\"\']}"; t="${t%[\"\']}"
    [ -n "$t" ] || continue
    if [ "$dashdash" = 0 ]; then
      case "$t" in
        --) dashdash=1; continue ;;
        --all|--no-ignore-removal) a_all=1; continue ;;
        --update) a_update=1; continue ;;
        --force) a_force=1; continue ;;
        --*) continue ;;
        -*) case "$t" in *A*) a_all=1 ;; esac
            case "$t" in *u*) a_update=1 ;; esac
            case "$t" in *f*) a_force=1 ;; esac
            continue ;;
      esac
    fi
    case "$t" in
      .|./|:/|'*')
        if [ -z "$prefix" ] || [ "$t" = ":/" ]; then whole=1; else specs[${#specs[@]}]="${prefix%/}"; fi ;;
      /*) specs[${#specs[@]}]="$t" ;;
      *) specs[${#specs[@]}]="$prefix$t" ;;
    esac
  done
  set +f
  if [ "$whole" = 1 ]; then
    specs=()
  elif [ "${#specs[@]}" -eq 0 ] && [ "$a_all" = 0 ] && [ "$a_update" = 0 ]; then
    continue # `git add` with nothing to add
  fi
  read_diff -- "${specs[@]}" || break
  [ "$a_update" = 1 ] && [ "$a_all" = 0 ] && continue
  if [ "$a_force" = 1 ]; then
    G ls-files --others -z -- "${specs[@]}" > "$tmp/u" 2>/dev/null
  else
    G ls-files --others --exclude-standard -z -- "${specs[@]}" > "$tmp/u" 2>/dev/null
  fi
  nu=0
  while IFS= read -r -d '' f; do
    nu=$((nu + 1))
    if [ "$nu" -gt "$MAX_UNTRACKED" ]; then
      note "more than $MAX_UNTRACKED new files in git add: only the first $MAX_UNTRACKED were checked."
      break
    fi
    case "$f" in .rule-guard/*) continue ;; esac
    G diff --no-index "${DOPTS[@]}" -- /dev/null "$f" > "$tmp/d" 2>/dev/null
    awk -v meta="$tmp/meta" -v text="$tmp/text" "$AWK_ADDED" < "$tmp/d"
    printf '%s\0' "$f" >> "$tmp/names"
  done < "$tmp/u"
done

if [ -n "$unreadable" ]; then
  note "could not read the diff of this commit (git: ${unreadable:-no message}): nothing was checked."
  finish
fi

# ---------------------------------------------------------------- the checks
record() { # rule index, where (file or file:line)
  local r=$1 item
  item="$2  ${R_MSG[r]} [rules.tsv line ${R_LINE[r]}]"
  [ -n "${R_FIX[r]}" ] && item="$item  Fix: ${R_FIX[r]}"
  if [ "${R_LEVEL[r]}" = block ]; then
    nblock=$((nblock + 1))
    [ "$nblock" -le "$MAX_SHOWN" ] && blocks[${#blocks[@]}]="  BLOCK  $item"
  else
    nwarn=$((nwarn + 1))
    [ "$nwarn" -le "$MAX_SHOWN" ] && warns[${#warns[@]}]="  WARN   $item"
  fi
}

# Paths of the files this commit adds or changes (several diffs may name the
# same file: keep each once).
tr '\0' '\n' < "$tmp/names" | awk '!seen[$0]++' > "$tmp/paths"
while IFS= read -r f; do
  case "$f" in ''|.rule-guard/*) continue ;; esac
  r=0
  while [ "$r" -lt "$nrules" ]; do
    if [ "${R_KIND[r]}" = path ] && glob_match "$f" "${R_PAT[r]}"; then record "$r" "$f"; fi
    r=$((r + 1))
  done
done < "$tmp/paths"

# Added lines. A rule limited by a glob is matched on the files first, then on
# the lines of those files only; the same file:line is reported once per rule.
if [ -s "$tmp/text" ]; then
  cut -f1 "$tmp/meta" | awk '!seen[$0]++' > "$tmp/lpaths"
  r=0
  while [ "$r" -lt "$nrules" ]; do
    if [ "${R_KIND[r]}" = content ]; then
      : > "$tmp/inscope"
      if [ -n "${R_GLOB[r]}" ]; then
        while IFS= read -r f; do
          glob_match "$f" "${R_GLOB[r]}" && printf '%s\n' "$f" >> "$tmp/inscope"
        done < "$tmp/lpaths"
      fi
      if [ -z "${R_GLOB[r]}" ] || [ -s "$tmp/inscope" ]; then
        LC_ALL=C grep -a -n -E -e "${R_PAT[r]}" "$tmp/text" 2>/dev/null | cut -d: -f1 > "$tmp/rows"
        if [ -s "$tmp/rows" ]; then
          awk -F '\t' -v scoped="${R_GLOB[r]:+1}" '
            FILENAME == ARGV[1] { want[$0] = 1; next }
            FILENAME == ARGV[2] { ok[$0] = 1; next }
            (FNR in want) && (scoped == "" || ($1 in ok)) && !seen[$0]++ { print }
          ' "$tmp/rows" "$tmp/inscope" "$tmp/meta" > "$tmp/hits"
          while IFS="$TAB" read -r hp hl; do
            record "$r" "$hp:$hl"
          done < "$tmp/hits"
        fi
      fi
    fi
    r=$((r + 1))
  done
fi

finish
