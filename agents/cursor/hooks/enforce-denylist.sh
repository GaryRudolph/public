#!/bin/bash
# Seatbelt for terminalDenylist in the Cursor IDE, which ignores that key.
# This is a best-effort backstop, not enforcement: it splits the command
# string on shell operators and prefix-matches each segment, so quoting,
# variable expansion, `bash -c`, eval and the like get past it. The real
# boundary is the IDE sandbox and the approval cards. Known gaps: path-qualified
# or wrapped commands (/bin/rm, env rm, xargs rm, timeout 5 sudo), quoting,
# variable expansion, bash -c, eval. Known false positives: the split ignores
# quotes, so `git commit -m "(sudo) ..."` is denied; reword the command.
#
# Cursor removed auto-run denylists in v1.3; permissions.json only honors
# mcpAllowlist / terminalAllowlist / autoRun, and silently drops everything
# else. The allowlist installer (agents/lib/allowlists.sh) still renders
# terminalDenylist into permissions.json as plain strings, which the IDE
# ignores. The same deny entries are also rendered into
# ~/.cursor/cli-config.json (Cursor CLI) as prefix rules,
# Shell(<base>:<args>*), and into ~/.claude/settings.json (Claude Code) as
# Bash(<entry>:*); both tools read those. Before that wrapping, the installer
# wrote them as bare strings, which neither tool matched, so the denies did
# nothing anywhere. The IDE is now the only harness where they do nothing,
# and this hook narrows that gap.
#
# Live path: ~/.cursor/hooks/enforce-denylist.sh (copy preferred over a
# symlink into a git worktree). Wired from ~/.cursor/hooks.json as
# beforeShellExecution (failClosed) and preToolUse (rewrite pytest/ruff
# to an allowlisted prefix so native auto-run does not card).
#
# Deny entries are read LIVE from ~/.cursor/permissions.json and a
# workspace .cursor/permissions.json when the hook input has a cwd. The
# workspace file may only ADD denies: a cloned repo's terminalAllowlist is
# ignored, so it cannot switch off a deny. Only the home file's
# terminalAllowlist can waive an ordinary deny, and never an ALWAYS_DENY one.
#
# Gating strategy: route denylisted writes through sandbox-escalation
# approval. sandbox=true + denylist hit -> deny with agent_message;
# sandbox=false (engineer approved unsandboxed) -> allow.
#
# The command is split into segments (&&, ||, ;, |, &, newlines, parens,
# braces, backticks, $( ) and every segment is checked on its own, so a
# safe first word never vouches for the rest of the line.
#
# Argv-safe pytest/ruff (any interpreter path; pytest; uv/poetry run;
# ruff check / format --check/--diff) is allowed per segment — it must
# not wait on a denylist card. preToolUse also rewrites absolute venv
# paths, env-var prefixes, and `cd … &&` wrappers to a prefix that is
# already on terminalAllowlist, because Cursor auto-run is still
# prefix-only on the raw command string. python -c, python script.py,
# python -m anything else, ruff format without --check/--diff, and
# conda run are not argv-safe.

set -uo pipefail

allow() { printf '{"permission":"allow"}\n'; exit 0; }

# True when remaining argv is `check` or `format --check` / `format --diff`.
ruff_subcmd_ok() {
  [ "$#" -ge 1 ] || return 1
  if [ "$1" = "check" ]; then
    return 0
  fi
  if [ "$1" = "format" ]; then
    local a
    for a in "$@"; do
      if [ "$a" = "--check" ] || [ "$a" = "--diff" ]; then
        return 0
      fi
    done
  fi
  return 1
}

# True for pytest / ruff check (any interpreter or uv/poetry wrapper).
argv_is_safe_tool() {
  local segment="$1"
  local -a args
  local base i next
  read -r -a args <<< "$segment"
  [ "${#args[@]}" -ge 1 ] || return 1
  base="${args[0]##*/}"
  base="${base%\"}"; base="${base#\"}"
  base="${base%\'}"; base="${base#\'}"

  if [ "$base" = "pytest" ]; then
    return 0
  fi

  if [ "$base" = "ruff" ]; then
    ruff_subcmd_ok "${args[@]:1}"
    return $?
  fi

  if [ "$base" = "uv" ] || [ "$base" = "poetry" ]; then
    [ "${#args[@]}" -ge 3 ] || return 1
    [ "${args[1]}" = "run" ] || return 1
    if [ "${args[2]}" = "pytest" ]; then
      return 0
    fi
    if [ "${args[2]}" = "ruff" ]; then
      ruff_subcmd_ok "${args[@]:3}"
      return $?
    fi
    return 1
  fi

  case "$base" in
    python|python3|python3.[0-9]|python3.[0-9][0-9]) ;;
    *) return 1 ;;
  esac

  i=1
  while [ "$i" -lt "${#args[@]}" ]; do
    case "${args[$i]}" in
      -c) return 1 ;;
      -m)
        if [ $((i + 1)) -ge "${#args[@]}" ]; then
          return 1
        fi
        next="${args[$((i + 1))]}"
        if [ "$next" = "pytest" ]; then
          return 0
        fi
        if [ "$next" = "ruff" ]; then
          ruff_subcmd_ok "${args[@]:$((i + 2))}"
          return $?
        fi
        return 1
        ;;
      -*) ;;
      *) return 1 ;;
    esac
    i=$((i + 1))
  done
  return 1
}

strip_leading_env() {
  local s="$1"
  while [[ "$s" =~ ^[A-Za-z_][A-Za-z0-9_]*=([^[:space:]]*|\"[^\"]*\"|\'[^\']*\')[[:space:]]+(.*)$ ]]; do
    s="${BASH_REMATCH[2]}"
  done
  printf '%s' "$s"
}

strip_leading_cd() {
  local s="$1" rest
  case "$s" in
    cd\ *)
      rest="${s#*&& }"
      if [ "$rest" != "$s" ]; then
        printf '%s' "$rest"
        return 0
      fi
      ;;
  esac
  printf '%s' "$s"
}

# Map common auto-run misses onto prefixes already in agerpoint.json.
rewrite_for_allowlist() {
  local s="$1"
  s=$(strip_leading_env "$s")
  s=$(strip_leading_cd "$s")
  s=$(strip_leading_env "$s")

  if [[ "$s" =~ (^|[[:space:]])([^[:space:]]*/)?\.venv/bin/python3?[[:space:]]+-m[[:space:]]+ ]]; then
    s=$(printf '%s' "$s" | sed -E 's#(^|[[:space:]])([^[:space:]]*/)?\.venv/bin/python3?[[:space:]]+-m[[:space:]]+#\1.venv/bin/python -m #')
    printf '%s' "$s"
    return 0
  fi
  if [[ "$s" =~ (^|[[:space:]])([^[:space:]]*/)?\.venv/bin/ruff[[:space:]] ]]; then
    s=$(printf '%s' "$s" | sed -E 's#(^|[[:space:]])([^[:space:]]*/)?\.venv/bin/ruff[[:space:]]#\1.venv/bin/ruff #')
    printf '%s' "$s"
    return 0
  fi
  if [[ "$s" =~ (^|[[:space:]])[/~][^[:space:]]+/python3?[[:space:]]+-m[[:space:]]+ ]]; then
    s=$(printf '%s' "$s" | sed -E 's#(^|[[:space:]])[/~][^[:space:]]+/python3?[[:space:]]+-m[[:space:]]+#\1python3 -m #')
    printf '%s' "$s"
    return 0
  fi
  if [[ "$s" =~ (^|[[:space:]])[/~][^[:space:]]+/ruff[[:space:]] ]]; then
    s=$(printf '%s' "$s" | sed -E 's#(^|[[:space:]])[/~][^[:space:]]+/ruff[[:space:]]#\1ruff #')
    printf '%s' "$s"
    return 0
  fi
  printf '%s' "$s"
}

command_is_argv_safe() {
  local s
  s=$(strip_leading_env "$1")
  s=$(strip_leading_cd "$s")
  s=$(strip_leading_env "$s")
  argv_is_safe_tool "$s"
}

if [ "${1:-}" = "--self-test" ]; then
  fail=0
  expect_safe() {
    command_is_argv_safe "$1" || { printf 'FAIL safe: %s\n' "$1" >&2; fail=1; }
  }
  expect_unsafe() {
    command_is_argv_safe "$1" && { printf 'FAIL unsafe: %s\n' "$1" >&2; fail=1; }
  }
  expect_safe "pytest"
  expect_safe "python -m pytest tests/"
  expect_safe "/Users/me/proj/.venv/bin/python -m pytest"
  expect_safe "PYTHONDONTWRITEBYTECODE=1 python -m pytest"
  expect_safe "cd /tmp && ruff check ."
  expect_safe "uv run pytest"
  expect_safe "poetry run ruff check"
  expect_safe ".venv/bin/ruff check agents"
  expect_unsafe "python -c print(1)"
  expect_unsafe "python scripts/run.py"
  expect_unsafe "ruff format agents/foo.py"
  expect_unsafe "conda run -n reconstruction python -m pytest"
  got=$(rewrite_for_allowlist "/Users/me/proj/.venv/bin/python -m pytest tests/")
  [ "$got" = ".venv/bin/python -m pytest tests/" ] || { printf 'FAIL rewrite python: %s\n' "$got" >&2; fail=1; }
  got=$(rewrite_for_allowlist "FOO=1 /opt/homebrew/bin/ruff check .")
  [ "$got" = "ruff check ." ] || { printf 'FAIL rewrite ruff: %s\n' "$got" >&2; fail=1; }
  [ "$fail" -eq 0 ] || exit 1
  printf 'ok\n'
  exit 0
fi

input=$(cat)
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty' 2>/dev/null) || tool_name=""

# preToolUse: rewrite Shell commands so terminalAllowlist prefix-matches.
if [ "$tool_name" = "Shell" ]; then
  orig=$(printf '%s' "$input" | jq -r 'if (.tool_input | type) == "object" then .tool_input.command // empty elif (.tool_input | type) == "string" then .tool_input else empty end' 2>/dev/null) || orig=""
  if [ -n "$orig" ]; then
    new=$(rewrite_for_allowlist "$orig")
    if [ -n "$new" ] && [ "$new" != "$orig" ]; then
      printf '%s' "$input" | jq --arg c "$new" '
        if (.tool_input | type) == "object" then
          {updated_input: (.tool_input + {command: $c})}
        else
          {updated_input: {command: $c}}
        end
      '
      exit 0
    fi
  fi
  printf '{}\n'
  exit 0
fi

command=$(printf '%s' "$input" | jq -r '.command // empty' 2>/dev/null) || allow
cwd=$(printf '%s' "$input" | jq -r '.cwd // empty' 2>/dev/null) || true
sandboxed=$(printf '%s' "$input" | jq -r 'if .sandbox == false then "false" else "true" end' 2>/dev/null) || sandboxed=true
[ -n "$command" ] || allow

GLOBAL_PERMS="$HOME/.cursor/permissions.json"
WORKSPACE_PERMS=""
if [ -n "$cwd" ] && [ -f "$cwd/.cursor/permissions.json" ]; then
  WORKSPACE_PERMS="$cwd/.cursor/permissions.json"
fi

# Collapse runs of whitespace and trim, so entries and commands compare alike.
squeeze() { sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^ //' -e 's/ $//'; }

load_list() {
  local key="$1" f
  for f in "$GLOBAL_PERMS" "$WORKSPACE_PERMS"; do
    [ -n "$f" ] && [ -f "$f" ] && jq -r --arg k "$key" '.[$k][]? // empty' "$f" 2>/dev/null
  done | squeeze
}

# A workspace file may only add denies; its allowlist is never read.
denylist=$(load_list terminalDenylist)
allowlist=$(jq -r '.terminalAllowlist[]? // empty' "$GLOBAL_PERMS" 2>/dev/null | squeeze) || allowlist=""
[ -n "$denylist" ] || allow

# Prints every entry that prefix-matches the command, one per line.
matching_entries() {
  local cmd="$1" entry rc=1
  while IFS= read -r entry; do
    [ -z "$entry" ] && continue
    if [ "$cmd" = "$entry" ] || [[ "$cmd" == "$entry "* ]]; then
      printf '%s\n' "$entry"
      rc=0
    fi
  done
  return $rc
}

ALWAYS_DENY='^rm[[:space:]]|^dd$|^mkfs$|^sudo$|get-secret|auth token|^git -C$|^databricks bundle destroy$'
PROPOSE_ONLY='^databricks bundle deploy$'

# Every shell operator that can start a new command becomes a line break.
# tr, not sed: BSD sed on macOS does not expand \n in a replacement.
# One sed over the whole list, not one process per segment.
segments=$(printf '%s' "$command" | tr ';|&(){}`' '\n' | squeeze)

# Checks one candidate segment against the denylist. Emits a deny and exits,
# or returns 0 so the next segment is still checked.
check_segment() {
  local segment="$1" hits hit

  hits=$(printf '%s\n' "$denylist" | matching_entries "$segment") || return 0
  # A protected entry wins over an ordinary one that matched first.
  hit=$(printf '%s\n' "$hits" | grep -E "$ALWAYS_DENY" | head -n 1) || true
  [ -n "$hit" ] || hit=$(printf '%s\n' "$hits" | head -n 1)

  # ALWAYS_DENY comes before any allowlist.
  if printf '%s' "$hit" | grep -qE "$ALWAYS_DENY"; then
    jq -n --arg e "$hit" --arg s "$segment" '{
      permission: "deny",
      user_message: ("Blocked by terminalDenylist entry \"" + $e + "\" (no approval path): " + $s),
      agent_message: ("Blocked by the terminalDenylist entry \"" + $e + "\". This entry has no escalation path in the parent chat or in a Task. Do not retry with required_permissions [\"all\"], request_smart_mode_approval, or a REST/API workaround. Use a supported alternative (working_directory instead of git -C), or ask the engineer to run it themselves.")
    }'
    exit 0
  fi

  # The first pass looks for protected entries only, so an ordinary
  # approval is never requested for a command a later segment will refuse.
  [ "$SCAN" = protected ] && return 0

  printf '%s\n' "$allowlist" | matching_entries "$segment" >/dev/null && return 0

  if printf '%s' "$hit" | grep -qE "$PROPOSE_ONLY"; then
    jq -n --arg e "$hit" --arg s "$segment" '{
      permission: "deny",
      user_message: ("Propose-only (run this yourself in a terminal, not via the agent): " + $s),
      agent_message: ("\"" + $e + "\" is propose-only — including `databricks bundle deploy -t qa`. Do not retry with required_permissions [\"all\"] and do not set request_smart_mode_approval (that would still be the agent running the deploy). Do not wrap around via the REST API. Print the exact command for the engineer: only `databricks bundle deploy -t qa` plus an optional `--profile`, with working_directory set to the dab directory. Never propose or Shell deploy to dev / production / CICD. Never Shell this command yourself, parent or Task.")
    }'
    exit 0
  fi

  if [ "$sandboxed" = "false" ]; then
    return 0
  fi

  jq -n --arg e "$hit" --arg s "$segment" '{
    permission: "deny",
    user_message: ("Needs your approval (terminalDenylist entry \"" + $e + "\"): " + $s),
    agent_message: ("Matches the terminalDenylist entry \"" + $e + "\". This is the Cursor IDE denylist hook, not Auto-review. Parent chat: retry the SAME command with required_permissions [\"all\"] — that surfaces an approval card; on approval it runs in-session and you keep the output. Task / background subagent: do NOT retry and do not set request_smart_mode_approval (there is no approval UI; it fails the same way). Write the exact command and working_directory to the wave artifact and return; the orchestrator-parent runs it in the foreground. Sibling-root cwd also uses [\"all\"] — that is not denylist approval; still do not run this command from a Task.")
  }'
  exit 0
}

scan_segments() {
  while IFS= read -r segment; do
    [ -n "$segment" ] || continue
    # Check every intermediate form (the line as written, then each time a
    # leading env assignment or wrapper word comes off), so a deny on a
    # wrapper word still applies. The final form is checked below.
    while :; do
      if [[ "$segment" =~ ^[A-Za-z_][A-Za-z0-9_]*=[^[:space:]]*[[:space:]]+(.*)$ ]] \
         || [[ "$segment" =~ ^(if|then|else|elif|do|while|until|time|exec|command|nohup|\!)[[:space:]]+(.*)$ ]]; then
        check_segment "$segment"
        segment="${BASH_REMATCH[${#BASH_REMATCH[@]}-1]}"
      else
        break
      fi
    done
    [ -n "$segment" ] || continue

    if argv_is_safe_tool "$segment"; then
      continue
    fi
    check_segment "$segment"
  done <<< "$segments"
}

SCAN=protected scan_segments
SCAN=full scan_segments

allow
