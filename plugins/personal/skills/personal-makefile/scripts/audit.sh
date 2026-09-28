#!/usr/bin/env bash
# Read-only Makefile inventory for personal-makefile skill.
# Usage: audit.sh [<root> ...]
# Emits JSON on stdout. No writes.
#
# Facts in script, judgment in agent: this script gathers mechanical facts
# (target inventory, sections, .PHONY membership, layout, presence checks).
# It emits NO verdicts, classifications, or findings — diffing against the
# standard, layout-aware reasoning, and known-defect checks are the agent's
# job (see SKILL.md step 2 and reference.md).

set -euo pipefail

roots=("${@:-.}")

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' <<<"$1"
}

find_makefiles() {
  local root="$1"
  find "$root" -name Makefile \
    -not -path '*/node_modules/*' \
    -not -path '*/.git/*' \
    -not -path '*/.build/checkouts/*' \
    -not -path '*/.scratch/*' \
    2>/dev/null | sort
}

detect_layout() {
  local root="$1"
  local layout="single_repo"
  if [[ -f "$root/repos.mk" && -f "$root/Makefile" ]]; then
    layout="workspace"
  elif [[ -f "$root/.gitmodules" ]]; then
    layout="submodule_estate"
  elif [[ ! -d "$root/.git" ]]; then
    local git_children=0
    for d in "$root"/*; do
      [[ -d "$d/.git" ]] && git_children=$((git_children + 1))
    done
    if [[ "$git_children" -gt 1 ]]; then
      layout="plain_folder"
    fi
  fi
  echo "$layout"
}

parse_makefile() {
  local mf="$1"
  local section=""
  local phony=""
  local in_phony=0

  # Extract .PHONY targets (best-effort, single-line and continuation)
  phony=$(grep -E '^\.PHONY:' "$mf" 2>/dev/null | sed 's/^\.PHONY://' | tr '\\' ' ' || true)

  python3 - "$mf" "$phony" <<'PY'
import re, sys, json

mf, phony_raw = sys.argv[1], sys.argv[2]
phony = set(phony_raw.split())

section = ""
targets = []
sections_seen = []

with open(mf, encoding="utf-8", errors="replace") as f:
    for line in f:
        line = line.rstrip("\n")
        msec = re.match(r"^##@ (.+)$", line)
        if msec:
            section = msec.group(1)
            if section not in sections_seen:
                sections_seen.append(section)
            continue
        mt = re.match(r"^([a-zA-Z0-9_.-]+)\s*:([^=]|$)", line)
        if mt and not line.startswith("\t") and not line.startswith("#"):
            name = mt.group(1)
            if name.startswith("."):
                continue
            desc = ""
            dm = re.search(r"##\s*(.+)$", line)
            if dm:
                desc = dm.group(1).strip()
            targets.append({
                "name": name,
                "section": section,
                "description": desc,
                "phony": name in phony,
            })

# Mechanical facts only — no verdicts. The agent interprets these.
import os
text = open(mf, encoding="utf-8", errors="replace").read()

# Literal character class used in the help target's awk pattern, if any
# (a fact for the agent to compare against the standard; not a verdict).
help_regex_match = re.search(r"/\^(\[[^\]]+\]\+):", text)

facts = {
    "has_shell_bash": "SHELL := bash" in text,
    "has_default_goal_help": ".DEFAULT_GOAL := help" in text,
    "has_help_target": any(t["name"] == "help" for t in targets),
    "help_awk_char_class": help_regex_match.group(1) if help_regex_match else None,
    "has_makefile_md": os.path.isfile(
        os.path.join(os.path.dirname(mf), "Makefile.md")
    ),
}

print(json.dumps({
    "path": mf,
    "targets": targets,
    "sections": sections_seen,
    "facts": facts,
}, indent=2))
PY
}

main_json="["
first_root=1
for root in "${roots[@]}"; do
  root=$(cd "$root" && pwd)
  layout=$(detect_layout "$root")
  makefiles=()
  while IFS= read -r mf; do
    makefiles+=("$mf")
  done < <(find_makefiles "$root")

  repos_mk=null
  if [[ -f "$root/repos.mk" ]]; then
    repos_mk="$root/repos.mk"
  fi

  entries="["
  first_mf=1
  for mf in "${makefiles[@]}"; do
    parsed=$(parse_makefile "$mf")
    if [[ $first_mf -eq 0 ]]; then entries+=","; fi
    entries+="$parsed"
    first_mf=0
  done
  entries+="]"

  if [[ $first_root -eq 0 ]]; then main_json+=","; fi
  main_json+=$(cat <<EOF
{
  "root": $(json_escape "$root"),
  "layout": $(json_escape "$layout"),
  "repos_mk": $(if [[ "$repos_mk" == null ]]; then echo null; else json_escape "$repos_mk"; fi),
  "makefiles": $entries
}
EOF
)
  first_root=0
done
main_json+="]"

echo "$main_json"
