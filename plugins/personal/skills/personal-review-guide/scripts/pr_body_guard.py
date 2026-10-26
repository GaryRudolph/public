#!/usr/bin/env python3
"""Claude Code PreToolUse hook: a PR is created with a review guide in its body.

Denies creating a pull request whose body has no `## Review guide` heading
or no `Review tier:` line (standards/review.md "Description layout"). It
checks that both are present, nothing more: what they say is the
personal-review-guide skill's job and the author's.

It sees PR creation through:

- `gh pr create`: the body is in the command (`--body`, a heredoc) or in
  the `--body-file`/`-F` file; `--fill` and friends supply none. `--web`
  hands the body to a browser and passes.
- `gh api` to `repos/<owner>/<repo>/pulls` with a write: `-X POST`, or a
  `-f`/`-F`/`--field`/`--raw-field`/`--input` without `-X GET`. The body is
  in the command or in a `-F body=@<file>` or `--input <file>` file.
- A GitHub MCP server's `create_pull_request` tool: the `body` argument.

Editing an existing PR's description isn't checked.

`PERSONAL_REVIEW_GUIDE=0` in the harness environment turns it off, for a
repo or machine that doesn't use review guides. Every other call gets no
output at once, and so does any error of this hook's own: it sees every
Bash call of every session, so it fails open (the hooks file has no exit-2
fallback for it).
"""

import json
import os
import re
import shlex
import sys

MCP_CREATE = re.compile(r"^mcp__.+__create_pull_request$")
START = r"(?:^|[;&|(`\n]|\$\()\s*(?:(?:sudo|env|command|exec|nohup|time)\s+|[A-Za-z_]\w*=\S*\s+)*"
GH_PR_CREATE = re.compile(START + r"gh\s+pr\s+create\b([^;&|\n]*)")
GH_API = re.compile(START + r"gh\s+api\b([^;&|\n]*)")
PULLS_PATH = re.compile(r"(?:^|/)repos/[^/\s'\"]+/[^/\s'\"]+/pulls/?$")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_]\w*)\1")
GUIDE = re.compile(r"##\s+Review guide", re.I)
TIER = re.compile(r"Review tier:", re.I)


def strip_heredocs(command):
    """The command without heredoc bodies, so a heredoc that writes about `gh pr create` isn't a run of it."""
    out, lines, i = [], command.split("\n"), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        i += 1
        for m in HEREDOC.finditer(line):
            tag = m.group(2)
            while i < len(lines) and lines[i].strip() != tag:
                i += 1
            i += 1
    return "\n".join(out)


def words(segment):
    try:
        return shlex.split(segment, comments=False, posix=True)
    except ValueError:
        return segment.split()


def read(path, cwd):
    if not path or path == "-":
        return ""
    full = os.path.join(cwd, os.path.expanduser(path))
    with open(full, encoding="utf-8", errors="replace") as f:
        return f.read()


def option_values(argv, names):
    """Values of the options in names, as `--opt value`, `--opt=value` or `-o value`."""
    values = []
    for i, w in enumerate(argv):
        for n in names:
            if w == n and i + 1 < len(argv):
                values.append(argv[i + 1])
            elif n.startswith("--") and w.startswith(n + "="):
                values.append(w[len(n) + 1:])
    return values


def gh_pr_create_body(args, command, cwd):
    """Text that would be the body, or None when the body isn't the agent's (--web)."""
    argv = words(args)
    if "--web" in argv or "-w" in argv:
        return None
    text = command
    for path in option_values(argv, ["--body-file", "-F"]):
        text += "\n" + read(path, cwd)
    return text


def gh_api_body(args, command, cwd):
    """Text that would be the body when this gh api call creates a PR, else None."""
    argv = words(args)
    paths = [w for w in argv if not w.startswith("-") and PULLS_PATH.search(w.split("?")[0])]
    if not paths:
        return None
    methods = [m.upper() for m in option_values(argv, ["-X", "--method"])]
    has_fields = any(w in ("-f", "-F", "--field", "--raw-field", "--input") or
                     w.startswith(("--field=", "--raw-field=", "--input=")) for w in argv)
    if methods:
        if methods[-1] != "POST":
            return None
    elif not has_fields:
        return None
    text = command
    for value in option_values(argv, ["-F", "--field"]):
        if value.startswith("body=@"):
            text += "\n" + read(value[len("body=@"):], cwd)
    for path in option_values(argv, ["--input"]):
        text += "\n" + read(path, cwd)
    return text


def decide(event):
    """The deny reason, or None."""
    if os.environ.get("PERSONAL_REVIEW_GUIDE", "").strip().lower() in ("0", "false", "no", "off"):
        return None
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd") or os.getcwd()
    bodies = []
    if MCP_CREATE.match(tool):
        bodies.append(str(tool_input.get("body") or ""))
    elif tool == "Bash":
        command = tool_input.get("command") or ""
        visible = strip_heredocs(command)
        for m in GH_PR_CREATE.finditer(visible):
            body = gh_pr_create_body(m.group(1), command, cwd)
            if body is not None:
                bodies.append(body)
        for m in GH_API.finditer(visible):
            body = gh_api_body(m.group(1), command, cwd)
            if body is not None:
                bodies.append(body)
    for body in bodies:
        missing = [what for what, rx in (("a `## Review guide` heading", GUIDE), ("a `Review tier:` line", TIER))
                   if not rx.search(body)]
        if missing:
            return " and ".join(missing)
    return None


def main():
    try:
        missing = decide(json.load(sys.stdin))
    except Exception:  # fail open: this hook sees every Bash call
        return
    if missing:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"personal-review-guide: this PR's body has no {missing}. Write the review "
            "guide with the personal-review-guide skill (pr mode) and use its draft as the body, per "
            "standards/review.md \"Description layout\". A repo or machine that doesn't use review guides sets "
            "PERSONAL_REVIEW_GUIDE=0 in the harness environment; ask Gary rather than setting it yourself."}}))


if __name__ == "__main__":
    main()
