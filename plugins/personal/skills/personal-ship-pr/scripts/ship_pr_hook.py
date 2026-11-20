#!/usr/bin/env python3
"""Claude Code PostToolUse hook: a PR that just opened starts the personal-ship-pr loop.

After a call that creates a pull request, it adds context telling the agent
to run personal-ship-pr from step 2 in the same turn, so a draft PR isn't
where the session stops. It sees PR creation through a GitHub MCP server's
`create_pull_request` tool, `gh pr create` (not `--web`, which only opens a
browser, or `--dry-run`) and `gh api` POSTs to `repos/<owner>/<repo>/pulls`.
When the tool's response shows it failed (an error flag, or Bash output
with no PR URL and an error on stderr), it stays quiet; output with no URL
and no error (`--jq`, `--silent`, a redirect) still counts as opened.

`PERSONAL_SHIP_PR=0` in the harness environment turns it off. Every other
call gets no output, and so does any error of this hook's own: it sees
every Bash call, so it fails open.
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
PR_URL = re.compile(r"/pulls?/\d+")
GH_ERROR = re.compile(r"(?i)\b(error|failed|could not|not found|HTTP [45]\d\d)\b")

CONTEXT = (
    "personal-ship-pr: a pull request was just opened. Unless the Owner said \"draft only\" or \"hold\" for it, "
    "load the personal-ship-pr skill (if it isn't already running) and carry its loop on from step 2 now, in this "
    "turn: /code-review at the level the tier sets, or say \"Skipping /code-review: <reason>\"; fix CI; mark the "
    "PR ready; work the Copilot rounds. The loop has standing approval, so don't stop between its steps to ask; "
    "wait on CI and reviews as the skill's \"Waiting\" section says. Never merge."
)


def strip_heredocs(command):
    out, lines, i = [], command.split("\n"), 0
    while i < len(lines):
        out.append(lines[i])
        i += 1
        for m in HEREDOC.finditer(out[-1]):
            while i < len(lines) and lines[i].strip() != m.group(2):
                i += 1
            i += 1
    return "\n".join(out)


def words(segment):
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def gh_api_creates_pr(args):
    argv = words(args)
    if not any(not w.startswith("-") and PULLS_PATH.search(w.split("?")[0]) for w in argv):
        return False
    methods = [argv[i + 1].upper() for i, w in enumerate(argv[:-1]) if w in ("-X", "--method")]
    methods += [w.split("=", 1)[1].upper() for w in argv if w.startswith("--method=")]
    if methods:
        return methods[-1] == "POST"
    return any(w in ("-f", "-F", "--field", "--raw-field", "--input") or
               w.startswith(("--field=", "--raw-field=", "--input=")) for w in argv)


def creates_pr(event):
    tool = event.get("tool_name", "")
    if MCP_CREATE.match(tool):
        return True
    if tool != "Bash":
        return False
    visible = strip_heredocs((event.get("tool_input") or {}).get("command") or "")
    for m in GH_PR_CREATE.finditer(visible):
        argv = words(m.group(1))
        if not {"--web", "-w", "--dry-run"} & set(argv):
            return True
    return any(gh_api_creates_pr(m.group(1)) for m in GH_API.finditer(visible))


def failed(response):
    """True when the tool's response shows the call didn't open a PR."""
    if not isinstance(response, dict):
        return False
    if response.get("is_error") or response.get("isError") or response.get("interrupted"):
        return True
    # Output alone can't prove success: --jq, --silent and redirects all hide the URL. So only output with no PR URL
    # whose stderr reads like an error counts as a failure.
    if "stdout" in response and not PR_URL.search(str(response.get("stdout") or "")):
        return bool(GH_ERROR.search(str(response.get("stderr") or "")))
    return False


def main():
    try:
        if os.environ.get("PERSONAL_SHIP_PR", "").strip().lower() in ("0", "false", "no", "off"):
            return
        event = json.load(sys.stdin)
        if creates_pr(event) and not failed(event.get("tool_response")):
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": CONTEXT}}))
    except Exception:  # fail open: this hook sees every Bash call
        return


if __name__ == "__main__":
    main()
