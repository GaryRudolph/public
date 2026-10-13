#!/usr/bin/env bash
# Tests for scripts/session-doctor.py against fixture repos, with stub make,
# task and triage on a PATH that holds only them and git. Needs bash, git,
# and python3.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
doctor="$here/../scripts/session-doctor.py"
python=$(command -v python3)
git_bin=$(command -v git)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
failures=0
pass() { printf '  ok    %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1" >&2; failures=$((failures + 1)); }
expect_grep()   { if grep -qF -- "$2" "$work/out"; then pass "$1"; else fail "$1: no '$2' in output"; sed 's/^/        /' "$work/out" >&2; fi; }
expect_nogrep() { if grep -qF -- "$2" "$work/out"; then fail "$1: '$2' in output"; sed 's/^/        /' "$work/out" >&2; else pass "$1"; fi; }
expect_called() { if grep -qF -- "$2" "$work/calls"; then pass "$1"; else fail "$1: no '$2' among the calls"; sed 's/^/        /' "$work/calls" >&2; fi; }
expect_nocall() { if grep -qF -- "$2" "$work/calls"; then fail "$1: '$2' among the calls"; else pass "$1"; fi; }
expect_empty()  { if [ -s "$work/out" ]; then fail "$1: output not empty"; sed 's/^/        /' "$work/out" >&2; else pass "$1"; fi; }

# Stubs log what ran and where to $work/calls, print the same line, then exit
# with STUB_RC after STUB_SLEEP.
bin="$work/bin"
mkdir -p "$bin"
ln -s "$git_bin" "$bin/git"
for tool in make task triage; do
    cat > "$bin/$tool" <<EOF
#!/bin/sh
[ -n "\${STUB_SLEEP:-}" ] && /bin/sleep "\$STUB_SLEEP"
echo "STUB $tool \$* in \$(pwd)" >> "$work/calls"
echo "STUB $tool \$* in \$(pwd)"
exit "\${STUB_RC:-0}"
EOF
    chmod +x "$bin/$tool"
done

# run_doctor <cwd> [env assignments...]: runs the hook with a SessionStart payload.
run_doctor() {
    local cwd="$1"; shift
    : > "$work/calls"
    printf '{"cwd": "%s", "source": "startup"}' "$cwd" \
        | env -i HOME="$work" PATH="$bin" "$@" "$python" -I "$doctor" --timeout 2 >"$work/out" 2>"$work/err"
    local rc=$?
    [ "$rc" = 0 ] || fail "hook exited $rc in $cwd"
}

# new_repo <dir> [origin-url]
new_repo() {
    mkdir -p "$1"
    "$git_bin" -C "$1" init -q
    [ -n "${2:-}" ] && "$git_bin" -C "$1" remote add origin "$2"
    return 0
}
makefile_with_doctor() { printf '.PHONY: doctor\n\ndoctor: ## Check tools\n\t@triage\n' > "$1/Makefile"; }

printf 'choosing the doctor\n'
r="$work/make-repo"; new_repo "$r" https://github.com/GaryRudolph/make-repo
makefile_with_doctor "$r"; touch "$r/triage.yaml"
run_doctor "$r"
expect_called "Makefile doctor target: runs make doctor"    "STUB make --no-print-directory doctor in $r"
expect_grep   "  ...and reports it passed"                  "passed: \`make doctor\` in $r"
expect_nocall "  ...not triage, though triage.yaml exists" "STUB triage"

r="$work/task-repo"; new_repo "$r" git@github.com:lolay/task-repo.git
printf 'version: "3"\n\nvars:\n  doctor: x\n\ntasks:\n  build:\n    cmds: [go build]\n  doctor:\n    cmds: [triage]\n' > "$r/Taskfile.yml"
printf 'build:\n\tgo build\n' > "$r/Makefile"
run_doctor "$r"
expect_called "Makefile without doctor, Taskfile with it: runs task doctor" "STUB task doctor in $r"

r="$work/triage-repo"; new_repo "$r" https://github.com/lolay/triage-repo.git
printf 'version: "3"\ntasks:\n  build:\n    cmds: [go build]\n    doctor: not-a-task\n' > "$r/Taskfile.yml"
touch "$r/triage.yaml"
run_doctor "$r"
expect_called "no doctor target or task: runs triage"       "STUB triage --profile default --no-color --no-update-check in $r"
expect_grep "  ...labelled without its quieting flags"    "passed: \`triage --profile default\`"

r="$work/decoys"; new_repo "$r" https://github.com/GaryRudolph/decoys
printf '.PHONY: doctor\ndoctor := x\ndoctor ?= y\n# doctor: commented\nnot-doctor: ; @true\n' > "$r/Makefile"
run_doctor "$r"
expect_empty "only .PHONY, variables and comments mention doctor: nothing runs"

r="$work/multi"; new_repo "$r" https://github.com/GaryRudolph/multi
printf 'lint doctor test:\n\t@true\n' > "$r/Makefile"
run_doctor "$r"
expect_called "doctor in a multi-target rule is found" "STUB make --no-print-directory doctor in $r"

printf 'where it looks\n'
r="$work/nested"; new_repo "$r" https://github.com/GaryRudolph/nested
makefile_with_doctor "$r"; mkdir -p "$r/packages/cli"
run_doctor "$r/packages/cli"
expect_called "cwd inside a repo: runs at the repo root" "STUB make --no-print-directory doctor in $r"

ws="$work/workspace"; mkdir -p "$ws"
new_repo "$ws/alpha" https://github.com/GaryRudolph/alpha; makefile_with_doctor "$ws/alpha"
new_repo "$ws/beta" https://github.com/lolay/beta; touch "$ws/beta/triage.yaml"
new_repo "$ws/gamma" https://github.com/lolay/gamma
mkdir -p "$ws/not-a-repo"; makefile_with_doctor "$ws/not-a-repo"
run_doctor "$ws"
expect_called "cwd outside a repo: each child repo runs" "STUB make --no-print-directory doctor in $ws/alpha"
expect_called "  ...with its own doctor" "STUB triage --profile default --no-color --no-update-check in $ws/beta"
expect_nogrep "  ...but not a child that isn't a repo"   "not-a-repo"

printf 'trust\n'
r="$work/stranger"; new_repo "$r" https://github.com/someone/stranger.git
makefile_with_doctor "$r"
run_doctor "$r"
expect_grep   "foreign owner: not run"   "not run: \`make doctor\` in $r: origin owner \"someone\" is not a trusted owner"
expect_nocall "  ...and nothing ran"     "STUB make"
run_doctor "$r" PERSONAL_DOCTOR_OWNERS="other SOMEONE"
expect_called "PERSONAL_DOCTOR_OWNERS adds owners, case-insensitively" "STUB make --no-print-directory doctor in $r"
run_doctor "$work/make-repo" PERSONAL_DOCTOR_OWNERS="someone"
expect_called "  ...on top of the defaults" "STUB make --no-print-directory doctor in $work/make-repo"
r="$work/agerpoint"; new_repo "$r" git@github.com:agerpoint/tool.git; makefile_with_doctor "$r"
run_doctor "$r"
expect_called "Agerpoint is a default owner" "STUB make --no-print-directory doctor in $r"

r="$work/no-origin"; new_repo "$r"; makefile_with_doctor "$r"
run_doctor "$r"
expect_grep "no origin: not run" "not run: \`make doctor\` in $r: no origin remote, so its owner is unknown"

r="$work/proxy"; new_repo "$r" http://local_proxy@127.0.0.1:41923/git/lolay/proxy
makefile_with_doctor "$r"
run_doctor "$r"
expect_grep "cloud git proxy URL: owner parsed" "passed: \`make doctor\` in $r"

r="$work/alias"; new_repo "$r" git@github.com-lolay:lolay/alias.git
makefile_with_doctor "$r"
run_doctor "$r"
expect_grep "ssh host alias URL: owner parsed" "passed: \`make doctor\` in $r"

printf 'outcomes\n'
r="$work/make-repo"
run_doctor "$r" STUB_RC=2
expect_grep   "failing doctor: reported with its exit code"   "FAILED (exit 2): \`make doctor\` in $r"
expect_grep   "  ...and its output"                            "    STUB make --no-print-directory doctor in $r"
expect_nogrep "  ...not as passed"                             "passed:"

run_doctor "$r" STUB_SLEEP=5
expect_grep "slow doctor: reported as timed out" "FAILED (timed out after 2s): \`make doctor\` in $r"

rm "$bin/make"
run_doctor "$r"
expect_grep "make not on PATH: not run" "not run: \`make doctor\` in $r: make is not on PATH"
ln -s "$bin/task" "$bin/make"  # any stub will do from here on

run_doctor "$r" PERSONAL_DOCTOR=0
expect_empty "PERSONAL_DOCTOR=0: silent"

empty="$work/empty"; mkdir -p "$empty"
run_doctor "$empty"
expect_empty "nothing with a doctor: silent"

printf 'output dialects\n'
run_doctor "$r" GEMINI_PROJECT_DIR="$r"
if "$python" -c 'import json,sys; d=json.load(open(sys.argv[1])); assert "passed:" in d["hookSpecificOutput"]["additionalContext"]' "$work/out"; then
    pass "Gemini: one JSON object with additionalContext"
else
    fail "Gemini: not the expected JSON object"; sed 's/^/        /' "$work/out" >&2
fi
run_doctor "$empty" GEMINI_PROJECT_DIR="$empty"
if [ "$(cat "$work/out")" = "{}" ]; then pass "Gemini with nothing to say: {}"; else fail "Gemini with nothing to say: got '$(cat "$work/out")'"; fi

(cd "$empty" && printf 'not json' | env -i HOME="$work" PATH="$bin" "$python" -I "$doctor" >"$work/out" 2>&1)
expect_empty "stdin that isn't JSON: falls back to the process cwd, fails open"

if [ "$failures" -gt 0 ]; then
    printf '%d failure(s)\n' "$failures" >&2
    exit 1
fi
printf 'all session-doctor tests passed\n'
