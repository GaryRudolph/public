#!/usr/bin/env python3
"""Claude Code PreToolUse hook on Bash: keep personal-plan-orchestrate's workers inside their working directory.

Workers (<plugin>:plan-worker) write and commit, but never act
outside their working directory: the parent pushes, and the Owner opens PRs,
releases and deploys. Phase 1's dogfood showed a worker can run an outward
command its prompt forbids, so this hook denies, when the hook input's
agent_type names a worker:

- the clearly outward commands: git push, gh pr and gh release subcommands
  that write, gh workflow run, goreleaser release (or bare goreleaser)
  without --snapshot or --skip=publish, goreleaser publish, announce and
  continue, and the package publishers (npm, pnpm and yarn publish, cargo
  publish, twine upload, docker push or docker image push after any global
  options, gem push, poetry and uv publish)
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
import shlex
import sys

WORKER = re.compile(r"^[a-z][a-z0-9-]*:plan-worker$")

# Words that sit before the command word: wrappers that run what follows, and the shell's keywords and `{` that
# begin a command (`if make release; then ...`, `for d in a; do git push; done`, `{ git push; }`, `! git push`).
PREFIX_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "eval", "then", "do", "else", "elif", "if", "while",
                "until", "!", "{"}
# The wrappers with flags of their own: the short flags that take a separate value, the long ones, and an operand
# pattern (timeout's duration). A boolean flag takes none, so `xargs -r echo git push` prints text. -l, -i, -e and
# their long forms take only an attached optional value.
WRAPPER_FLAGS = {
    "timeout": ("sk", {"signal", "kill-after"}, r"[+-]?\d+(?:\.\d+)?[smhd]?"),
    "nice": ("n", {"adjustment"}, None),
    "xargs": ("aEIJLnPsdRS", {"arg-file", "delimiter", "max-args", "max-chars", "max-procs", "process-slot-var"}, None),
    "sudo": ("ugCUhpRrT", {"user", "group", "chdir", "host", "prompt", "role", "type", "chroot", "other-user", "close-from"}, None),
    "env": ("uCS", {"unset", "chdir", "split-string"}, None),
}
# Commands that may be named by path (/usr/bin/timeout); the keywords may not.
COMMAND_WORDS = {"sudo", "env", "command", "exec", "nohup", "time", "timeout", "nice", "xargs", "eval"}


def _prefix_word(word):
    shorts, longs, operand = WRAPPER_FLAGS.get(word, ("", (), None))
    alts = ([rf"-[{shorts}]\s+\S+"] if shorts else []) + ([r"--(?:" + "|".join(sorted(longs)) + r")\s+\S+"] if longs else [])
    alts += [r"-\S+"] + ([operand] if operand else [])
    path = r"(?:\S*/)?" if word in COMMAND_WORDS else ""
    return path + re.escape(word) + r"(?:\s+(?:" + "|".join(alts) + r"))*\s+"


# What may sit between a separator and the command word: prefix words with their flags, and VAR=value assignments.
PREFIX = r"(?:" + "|".join(_prefix_word(w) for w in sorted(PREFIX_WORDS | set(WRAPPER_FLAGS), key=len, reverse=True)) + r"|[A-Za-z_]\w*=\S*\s+)*"
# A command word's position: the start, or after a separator, a subshell or a substitution, past the prefix.
START = r"(?:^|[;&|(`\n]|\$\()\s*" + PREFIX
GIT_OPTS = r"(?:\s+-[Cc]\s+\S+|\s+--?[\w-]+(?:=\S+)?)*"
# docker's global options before the subcommand (--context prod, --config dir, -H host), so a push that names its
# context or config, as security.md "Explicit CLI Identity" asks, is still a push.
DOCKER_OPTS = r"(?:\s+--?[\w-]+(?:=\S+|\s+(?!-)[^\s;&|]+)?)*"

OUTWARD = [
    (re.compile(START + r"git" + GIT_OPTS + r"\s+push\b"), "git push"),
    (re.compile(START + r"gh\s+pr\s+(?:create|merge|close|reopen|ready|review|comment|edit)\b"), "a gh pr command that writes"),
    (re.compile(START + r"gh\s+release\s+(?:create|upload|edit|delete|delete-asset)\b"), "a gh release command that writes"),
    (re.compile(START + r"gh\s+workflow\s+run\b"), "gh workflow run"),
]
PUBLISH = re.compile(START + r"(npm\s+publish|pnpm\s+publish|yarn\s+(?:npm\s+)?publish|cargo\s+publish|twine\s+upload|"
                     r"docker" + DOCKER_OPTS + r"\s+(?:image\s+)?push|gem\s+push|poetry\s+publish|uv\s+publish)\b([^;&|\n]*)")
GORELEASER = re.compile(START + r"goreleaser\b([^;&|\n]*)")
GORELEASER_SAFE = re.compile(r"--snapshot\b|--skip[= ]\S*\bpublish\b")
GORELEASER_OTHER = {"build", "check", "healthcheck", "init", "jsonschema", "completion", "help", "man", "verify-license"}
GORELEASER_SENDS = {"publish", "announce", "continue"}

# The repo's own scripts and make targets, by name.
OUTWARD_NAME = re.compile(r"publish|release|deploy", re.I)
SEPARATOR = re.compile(r"\|\||&&|[;|&()`\n]|\$\(")
# Redirections, removed before a command is split into words: their targets are files, not scripts or targets.
REDIRECTION = re.compile(r"(?:\d+|&)?(?:>>?|<)(?:&\d+|&-|\s*[^\s;&|()<>`]+)")
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

HEREDOC = re.compile(r"(?<!<)(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n(?:(?P<body>.*?)\n)??[ \t]*\3[ \t]*(?=\n|$)", re.S)
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")  # a $'...' string is the single-quoted one after its $


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


def named_problem(command, dry=False):
    """Why a worker may not run command because it runs a repo's own publish, release or deploy script or make target
    without a dry-run form, or None."""
    exported = dry  # a nested shell inherits the DRY_RUN of the command that started it
    for segment in SEPARATOR.split(REDIRECTION.sub(" ", command)):
        words, env, prefixed, wrapper, skip = segment.split(), {}, False, None, False
        while words:  # past the prefix words and their flags and VAR=value prefixes, to the command word
            w, m = words[0], ASSIGN.match(words[0])
            base = name_of(w) if name_of(w) in COMMAND_WORDS else w
            if skip:
                skip = False
            elif m:
                env[m.group(1)] = m.group(2)
            elif base in PREFIX_WORDS or base in WRAPPER_FLAGS:
                prefixed, wrapper = True, base
            elif prefixed and (w.startswith("-") or (WRAPPER_FLAGS.get(wrapper, ("", (), None))[2] and
                                                     re.fullmatch(WRAPPER_FLAGS[wrapper][2], w))):
                shorts, longs, _ = WRAPPER_FLAGS.get(wrapper, ("", (), None))
                skip = (len(w) == 2 and w[0] == "-" and w[1] in shorts) or (w.startswith("--") and w[2:] in longs)
            else:
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


SHELL_C = re.compile(START + r"(?:\S*/)?(?:sh|bash|zsh|dash|ksh)(?:\s+(?:-[Oo]\s+\S+|-[A-Za-z-]+|--))*?\s+-[A-Za-z]*c[A-Za-z]*(?:\s+--)?\s*\$?$")
# eval joins its arguments and runs them, so every argument counts, quoted or not.
EVAL_ARGS = re.compile(START + r"eval\s+((?:'[^']*'|\"(?:[^\"\\]|\\.)*\"|[^;&|\n'\"])*)")
# A shell that reads its commands from stdin (`... | sh`, `bash <<EOF`, `bash <<< '...'`, `sh -`, `bash -s`): nothing here
# can see them.
STDIN_SHELL = re.compile(START + r"(?:\S*/)?(?:sh|bash|zsh|dash|ksh)(?:\s+-[A-Za-z-]+)*?"
                         r"(?:\s+-[A-Za-z]*s[A-Za-z]*(?=\s|$)|\s+-(?=\s|$)|\s*(?:$|[;&|)`\n]|<<))")


def substitutions(text):
    """The bodies of the $(...) and `...` substitutions the shell would run in text: outside single quotes (but inside
    double ones), with escapes honoured and parentheses balanced across nested quotes."""
    out, i, n, dq = [], 0, len(text), False
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
        elif c == '"':
            dq, i = not dq, i + 1
        elif c == "'" and not dq:
            j = text.find("'", i + 1)
            i = n if j < 0 else j + 1
        elif text.startswith("$(", i) and not text.startswith("$((", i):
            depth, j, quote = 1, i + 2, None
            while j < n and depth:
                d = text[j]
                if d == "\\":
                    j += 1
                elif quote:
                    quote = None if d == quote else quote
                elif d in "'\"":
                    quote = d
                elif d == "(":
                    depth += 1
                elif d == ")":
                    depth -= 1
                j += 1
            out.append(text[i + 2:j - 1] if depth == 0 else text[i + 2:j])
            i = j
        elif c == "`":
            j = i + 1
            while j < n and text[j] != "`":
                j += 2 if text[j] == "\\" else 1
            out.append(text[i + 1:j])
            i = j + 1
        else:
            i += 1
    return out


def inner_strings(command):
    """The (string, text before it) pairs a shell would run that bare() sets aside: the quoted string after
    `sh|bash|zsh -c`, the joined arguments of an `eval`, and every substitution, in double quotes or an unquoted
    heredoc body included. A quoted heredoc body is inert."""
    plain = HEREDOC.sub(r"\1\4", command)
    found = [(m.group(0)[1:-1].replace('\\"', '"'), plain[:m.start()]) for m in QUOTED.finditer(plain)
             if SHELL_C.search(plain[:m.start()])]
    for m in EVAL_ARGS.finditer(plain):
        try:
            joined = " ".join(shlex.split(m.group(1)))
        except ValueError:
            joined = m.group(1).replace("'", "").replace('"', "")
        found.append((joined, plain[:m.start()]))
    live = HEREDOC.sub(lambda m: m.group(1) + m.group(4) + ("" if m.group(2) else "\n" + (m.group("body") or "")), command)
    found += [(body, live) for body in substitutions(live)]
    return found


def inherits_dry_run(before):
    """Whether a nested shell's text starts under DRY_RUN=1: exported earlier, or set on its own command line."""
    return bool(DRY_EXPORT.search(before) or re.search(r"(?:^|[;&|(`\n])\s*(?:[A-Za-z_]\w*=\S*\s+)*DRY_RUN=(?:1|true|yes)\s+[^;&|\n]*$", before))


def problem(command, depth=0, dry=False):
    """Why a worker may not run command, or None."""
    if depth < 3:
        for text, before in inner_strings(command):
            why = problem(text, depth + 1, dry or inherits_dry_run(before))
            if why:
                return why
    command = bare(command)
    if STDIN_SHELL.search(command):
        return "a shell that reads its commands from stdin"
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
    return named_problem(command, dry)


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
                                                 "your working directory, and only the parent or the Owner does that. If the step needs "
                                                 "it, return needs_info naming it; if the spec names a dry-run form, run that."}}))


if __name__ == "__main__":
    main()
