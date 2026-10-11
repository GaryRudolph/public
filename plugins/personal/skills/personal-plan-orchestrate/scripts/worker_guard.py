#!/usr/bin/env python3
"""Claude Code PreToolUse hook on Bash: keep personal-plan-orchestrate's workers inside their working directory.

Workers (<plugin>:plan-worker, -exec, -xdeep) write and commit, but never act
outside their working directory: the parent pushes, and Gary opens PRs,
releases and deploys. Phase 1's dogfood showed a worker can run an outward
command its prompt forbids, so this hook denies, when the hook input's
agent_type names a worker:

- the clearly outward commands: git push, gh pr and gh release subcommands
  that write, gh workflow run, goreleaser release (or bare goreleaser)
  without --snapshot or --skip=publish, goreleaser publish, announce and
  continue, and the package publishers (npm, pnpm and yarn publish, cargo
  publish, twine upload, docker push, gem push, poetry and uv publish)
  unless they carry --dry-run;
- the repo's own publish, release and deploy scripts: a script run whose
  basename contains publish, release or deploy (`scripts/publish-formula.sh`,
  `./release.sh`, `bash scripts/deploy.sh`, `python3 tools/release.py`), a
  make target whose name does (`make release`, `make deploy-prod`), and an
  npm, pnpm, yarn or bun `run` of such a package script, unless a dry-run
  form is present: a DRY_RUN=1 prefix (or an `export DRY_RUN=1` earlier in
  the command, or DRY_RUN=1 as a make variable), --dry-run, and for make -n
  (--just-print, --recon). Reading, grepping, linting or syntax-checking
  such a script (cat, grep, shellcheck, bash -n) is not a run, a make
  variable's value (`make doctor MODE=release`) is not a target, and a path
  named only as an argument or a redirect target is not a script run.

A deny list, so this is defence in depth: the prompt still forbids every
outward action, and the worker reports any it ran or tried under breaches.
Every other caller (the main session, the plan's reviewers, any other agent)
gets no output and exit 0 at once; reviewer_guard.py holds the reviewers. So
does input that isn't JSON, and so does any error of this hook's own: it
sees every Bash call of every session, so unlike orchestrate_gate.py it
fails open (the hooks file has no exit-2 fallback for it). A worker's Bash
call with no command string is denied. Heredoc bodies and quoted strings
are set aside before the checks, so a heredoc that writes "git push" or
"make release" into a doc passes.
"""

import json
import re
import sys

WORKER = re.compile(r"^[a-z][a-z0-9-]*:plan-worker(?:-exec|-xdeep)?$")

# A command word's position: the start, or after a separator, a subshell or a substitution, past sudo/env and
# VAR=value prefixes.
START = r"(?:^|[;&|(`\n]|\$\()\s*(?:(?:sudo|env|command|exec|nohup|time)\s+|[A-Za-z_]\w*=\S*\s+)*"
GIT_OPTS = r"(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*"

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

# The repo's own scripts and make targets, by name.
OUTWARD_NAME = re.compile(r"publish|release|deploy", re.I)
SEPARATOR = re.compile(r"\|\||&&|[;|&()`\n]|\$\(")
# Redirections, removed before a command is split into words: their targets are files, not scripts or targets.
REDIRECTION = re.compile(r"(?:\d+|&)?(?:>>?|<)(?:&\d+|&-|\s*[^\s;&|()<>`]+)")
PREFIX_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "then", "do", "else", "elif", "if", "while", "until", "!", "{"}
ASSIGN = re.compile(r"^([A-Za-z_]\w*)=(.*)$")
TRUE = {"1", "true", "yes"}
DRY_EXPORT = re.compile(r"\bexport\s+(?:[A-Za-z_]\w*=\S*\s+)*DRY_RUN=(?:1|true|yes)\b")
QUOTED_DRY = re.compile(r"\bDRY_RUN=(['\"])(1|true|yes)\1")
SCRIPT_EXT = re.compile(r"\.(?:sh|bash|zsh|py|rb|pl|js|mjs|cjs|ts)$")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "source", "."}
PYTHON = re.compile(r"^python(?:\d+(?:\.\d+)?)?$")
OTHER_INTERPRETERS = {"node", "ruby", "perl", "deno", "bun", "tsx", "ts-node"}
MAKES = {"make", "gmake"}
MAKE_VALUE_OPTS = {"-C", "-f", "-I", "-o", "-W", "--directory", "--file", "--makefile", "--include-dir", "--old-file",
                   "--new-file", "--what-if", "--assume-old", "--assume-new"}
MAKE_DRY = {"-n", "--dry-run", "--just-print", "--recon"}
RUNNERS = {"npm", "pnpm", "yarn", "bun"}

HEREDOC = re.compile(r"(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")


def bare(command):
    """The command with heredoc bodies and quoted strings set aside (a quoted DRY_RUN=1 kept as DRY_RUN=1)."""
    return QUOTED.sub("''", HEREDOC.sub(r"\1\4", QUOTED_DRY.sub(r"DRY_RUN=\2", command)))


def name_of(path):
    return path.rstrip("/").rsplit("/", 1)[-1]


def dry_flag(words):
    return any(w == "--dry-run" or (w.startswith("--dry-run=") and w.split("=", 1)[1].lower() in TRUE) for w in words)


def script_of(word, args):
    """The script (or module) a command runs when it names one by path, or None: the command word itself when it is a
    path or a script file, else the first operand of a shell or interpreter. A syntax check runs nothing."""
    base = name_of(word)
    if "/" in word or SCRIPT_EXT.search(word):
        return None if base == "goreleaser" else word  # goreleaser has its own rule
    if base in SHELLS:
        if "-n" in args or "-c" in args:
            return None
        return next((a for a in args if not a.startswith("-")), None)
    if PYTHON.match(base):
        it = iter(args)
        for a in it:
            if a == "-c":
                return None
            if a == "-m":
                return next(it, None)
            if a in ("-W", "-X"):
                next(it, None)
            elif not a.startswith("-"):
                return a
        return None
    if base in OTHER_INTERPRETERS:
        if {"-e", "-p", "-c", "--check", "--eval", "--print"} & set(args):
            return None
        rest = [a for a in args if not a.startswith("-")]
        if base in ("deno", "bun") and rest[:1] == ["run"]:
            rest = rest[1:]
        return rest[0] if rest else None
    return None


def make_targets(args):
    """The targets, the variables and whether a dry-run flag is set, from a make command's arguments."""
    targets, variables, dry, skip = [], {}, False, False
    for a in args:
        if skip:
            skip = False
            continue
        if a in MAKE_VALUE_OPTS:
            skip = True
        elif a.startswith("-"):
            dry = dry or a in MAKE_DRY or (re.fullmatch(r"-[A-Za-z]+", a) is not None and "n" in a[1:])
        elif ASSIGN.match(a):
            k, v = ASSIGN.match(a).groups()
            variables[k] = v
        else:
            targets.append(a)
    return targets, variables, dry


def named_problem(command):
    """Why a worker may not run command because it runs a repo's own publish, release or deploy script or make target
    without a dry-run form, or None."""
    exported = False
    for segment in SEPARATOR.split(REDIRECTION.sub(" ", command)):
        words, env, prefixed = segment.split(), {}, False
        while words:  # past sudo/env (and their flags) and VAR=value prefixes, to the command word
            m = ASSIGN.match(words[0])
            if m:
                env[m.group(1)] = m.group(2)
            elif words[0] in PREFIX_WORDS:
                prefixed = True
            elif not (prefixed and words[0].startswith("-")):
                break
            words = words[1:]
        if not words:
            continue
        if words[0] == "export":
            exported = exported or bool(DRY_EXPORT.search(segment))
            continue
        word, args = words[0], words[1:]
        dry = exported or env.get("DRY_RUN", "").lower() in TRUE or dry_flag(args)
        base = name_of(word)
        if base in MAKES:
            targets, variables, make_dry = make_targets(args)
            hits = [t for t in targets if OUTWARD_NAME.search(t)]
            if hits and not (dry or make_dry or variables.get("DRY_RUN", "").lower() in TRUE):
                return f"make {hits[0]} without -n or DRY_RUN=1"
            continue
        if base in RUNNERS and args[:1] in (["run"], ["run-script"]) and len(args) > 1 and OUTWARD_NAME.search(args[1]):
            if not dry:
                return f"{base} run {args[1]} without --dry-run or DRY_RUN=1"
            continue
        script = script_of(word, args)
        if script and OUTWARD_NAME.search(name_of(script)) and not dry:
            return f"the repo script {script} without DRY_RUN=1 or --dry-run"
    return None


def problem(command):
    """Why a worker may not run command, or None."""
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
    return named_problem(command)


def decide(inp):
    if not isinstance(inp, dict) or not WORKER.match(str(inp.get("agent_type") or "")):
        return None
    command = (inp.get("tool_input") or {}).get("command")
    return problem(command) if isinstance(command, str) else "a Bash call with no command string"


def main():
    try:
        why = decide(json.load(sys.stdin))
    except Exception:  # fail open: this hook sees every Bash call, and orchestrate_gate.py guards the launch itself
        return
    if why:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": f"personal-plan-orchestrate worker: {why} acts outside "
                                                 "your working directory, and only the parent or Gary does that. If the step needs "
                                                 "it, return needs_info naming it; if the spec names a dry-run form, run that."}}))


if __name__ == "__main__":
    main()
