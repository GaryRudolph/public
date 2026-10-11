#!/usr/bin/env python3
"""Claude Code PreToolUse hook on Bash: hold orch-spike-plan-orchestrate's subagents to their prompts.

Reviewers (<plugin>:plan-reviewer, <plugin>:plan-reviewer-xdeep) need Bash for
git diff, git log and the repo's tests, and their instructions forbid writes.
Phase 0 showed the instruction is the only thing that stops a write (their
tools allowlist can't narrow Bash), so this hook denies the commands that
change a repo or a file when the hook input's agent_type names a reviewer:
git subcommands that write (commit, push, add, reset, checkout, switch,
rebase, merge, ...), file writers (rm, mv, cp, touch, mkdir, tee, sed -i,
...), output redirection to a file, and gh.

Workers (<plugin>:plan-worker, -exec, -xdeep) write and commit, but never act
outside their working directory: the parent pushes, and Gary opens PRs,
releases and deploys. Phase 1's dogfood showed a worker can run an outward
command its prompt forbids, so this hook denies the clearly outward ones: git
push, gh pr and gh release subcommands that write, gh workflow run,
goreleaser release (or bare goreleaser) without --snapshot or
--skip=publish, goreleaser publish, announce and continue, and the package
publishers (npm, pnpm and yarn publish, cargo publish, twine upload, docker
push, gem push, poetry and uv publish) unless they carry --dry-run. A repo's
own publish script can't be told apart from any other script, so the
worker's prompt covers those.

Both lists are deny lists, so this is defence in depth: the instructions
stay. Every other caller (the main session, any other agent) gets no output
and exit 0 at once, and so does input that isn't JSON: this hook sees every
Bash call of every session, so unlike orchestrate_gate.py it fails open (the
hooks file has no exit-2 fallback for it). A plan agent's Bash call with no
command string is denied. Heredoc bodies and quoted strings are set aside
before the checks, so `git log --format='%h -> %s'` and a heredoc that writes
"git push" into a doc pass.
"""

import json
import re
import sys

REVIEWER = re.compile(r"^[a-z][a-z0-9-]*:plan-reviewer(?:-xdeep)?$")
WORKER = re.compile(r"^[a-z][a-z0-9-]*:plan-worker(?:-exec|-xdeep)?$")

# A command word's position: the start, or after a separator, a subshell or a substitution, past sudo/env and
# VAR=value prefixes.
START = r"(?:^|[;&|(`\n]|\$\()\s*(?:(?:sudo|env|command|exec|nohup|time)\s+|[A-Za-z_]\w*=\S*\s+)*"
GIT_OPTS = r"(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*"

GIT_WRITE = re.compile(
    r"\bgit\b" + GIT_OPTS + r"\s+"
    r"(commit|push|add|rm|mv|reset|checkout|switch|restore|rebase|merge|cherry-pick|revert|stash|tag|branch\s+-[dDmMcC]|"
    r"clean|apply|am|pull|fetch|worktree|update-ref|update-index|config|remote|gc|prune|notes|replace|filter-branch)\b")
WRITERS = re.compile(r"(?:^|[;&|(`\n]\s*|\$\(\s*|\bsudo\s+|\bxargs\s+)(rm|rmdir|mv|cp|touch|mkdir|tee|truncate|chmod|chown|ln|dd|install|gh|patch)\b")
SED_IN_PLACE = re.compile(r"\b(?:sed|perl)\b[^;&|\n]*\s-[a-zA-Z]*i")
REDIRECT = re.compile(r"(?<![0-9&])>>?\s*(?!&|/dev/null\b)\S|\b[0-9]>>?\s*(?!&|/dev/null\b)[^\s&]")

OUTWARD = [
    (re.compile(START + r"git" + GIT_OPTS + r"\s+push\b"), "git push"),
    (re.compile(START + r"gh\s+pr\s+(?:create|merge|close|reopen|ready|review|comment|edit)\b"), "a gh pr command that writes"),
    (re.compile(START + r"gh\s+release\s+(?:create|upload|edit|delete|delete-asset)\b"), "a gh release command that writes"),
    (re.compile(START + r"gh\s+workflow\s+run\b"), "gh workflow run"),
]
PUBLISH = re.compile(START + r"(npm\s+publish|pnpm\s+publish|yarn\s+(?:npm\s+)?publish|cargo\s+publish|twine\s+upload|"
                     r"docker\s+push|gem\s+push|poetry\s+publish|uv\s+publish)\b([^;&|\n]*)")
GORELEASER = re.compile(START + r"goreleaser\b([^;&|\n]*)")
GORELEASER_SAFE = re.compile(r"--snapshot\b|--skip[= ]\S*\bpublish\b")
GORELEASER_OTHER = {"build", "check", "healthcheck", "init", "jsonschema", "completion", "help", "man", "verify-license"}
GORELEASER_SENDS = {"publish", "announce", "continue"}

HEREDOC = re.compile(r"(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")


def bare(command):
    """The command with heredoc bodies and quoted strings set aside."""
    return QUOTED.sub("''", HEREDOC.sub(r"\1\4", command))


def reviewer_problem(command):
    """Why a reviewer may not run command, or None."""
    command = bare(command)
    for rx, what in ((GIT_WRITE, "a git command that writes"), (WRITERS, "a command that writes files or acts outward"),
                     (SED_IN_PLACE, "an in-place edit"), (REDIRECT, "output redirected to a file")):
        m = rx.search(command)
        if m:
            return f"{what} ({m.group(0).strip()[:40]!r})"
    return None


def worker_problem(command):
    """Why a worker may not run command, or None: only clearly outward commands."""
    command = bare(command)
    for rx, what in OUTWARD:
        if rx.search(command):
            return what
    for m in PUBLISH.finditer(command):
        if "--dry-run" not in m.group(2):
            return f"{' '.join(m.group(1).split())} without --dry-run"
    for m in GORELEASER.finditer(command):
        words = m.group(1).split()
        subs = {w for w in words if not w.startswith("-")}
        if "release" not in subs:  # bare goreleaser is a release; a flag's value may sit where a subcommand would
            sends = sorted(subs & GORELEASER_SENDS)
            if sends:
                return f"goreleaser {sends[0]}"
            if subs & GORELEASER_OTHER or set(words) & {"--version", "-v", "--help", "-h"}:
                continue
        if not GORELEASER_SAFE.search(m.group(1)):
            return "a goreleaser release that isn't --snapshot or --skip=publish"
    return None


def main():
    try:
        inp = json.load(sys.stdin)
    except ValueError:
        return  # not ours to judge; orchestrate_gate.py guards the launch itself
    agent = str(inp.get("agent_type") or "")
    if REVIEWER.match(agent):
        role, check, fix = "reviewer", reviewer_problem, ("read-only; {} is not allowed. Review with git diff, git log, git status, reads, "
                                                          "and tests that write only ignored build output; read their output inline.")
    elif WORKER.match(agent):
        role, check, fix = "worker", worker_problem, ("{} acts outside your working directory, and only the parent or Gary does that. "
                                                      "If the step needs it, return needs_info naming it; if the spec names a dry-run form, run that.")
    else:
        return
    command = (inp.get("tool_input") or {}).get("command")
    why = check(command) if isinstance(command, str) else "a Bash call with no command string"
    if why:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": f"orch-spike-plan-orchestrate {role}: {fix.format(why)}"}}))


if __name__ == "__main__":
    main()
