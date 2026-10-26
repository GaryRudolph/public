#!/usr/bin/env python3
"""Tests for scripts/pr_body_guard.py, run as the hook runs it: JSON on stdin, a decision on stdout."""

import json
import os
import subprocess
import sys
import tempfile

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "pr_body_guard.py")
GOOD = "Intent.\n\n## Review guide\n\nReview tier: [check], because x.\n"
failures = 0


def run(event, env_extra=None, raw=None):
    env = {k: v for k, v in os.environ.items() if k != "PERSONAL_REVIEW_GUIDE"}
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, "-I", GUARD], input=raw if raw is not None else json.dumps(event),
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return f"exit {r.returncode}"
    if not r.stdout.strip():
        return None
    return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]


def bash(command, cwd=None):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd or os.getcwd()}


def check(name, got, want_deny, contains=None):
    global failures
    ok = (got is not None) == want_deny and not (isinstance(got, str) and got.startswith("exit "))
    if ok and contains and contains not in got:
        ok = False
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}" + ("" if ok else f": got {got!r}"))
    if not ok:
        failures += 1


heredoc_good = f"gh pr create --title 'add x' --body \"$(cat <<'EOF'\n{GOOD}EOF\n)\""
heredoc_bad = "gh pr create --title 'add x' --body \"$(cat <<'EOF'\n## Summary\nstuff\nEOF\n)\""

print("gh pr create")
check("body with guide and tier: allowed", run(bash(heredoc_good)), False)
check("body without them: denied", run(bash(heredoc_bad)), True, "`## Review guide` heading")
check("guide but no tier: denied, names the tier", run(bash("gh pr create -t x -b '## Review guide\nstuff'")), True,
      "`Review tier:` line")
check("--fill: denied", run(bash("gh pr create --fill")), True)
check("--web: allowed", run(bash("gh pr create --web")), False)
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, "body.md"), "w").write(GOOD)
    open(os.path.join(d, "bad.md"), "w").write("## Summary\n")
    check("--body-file with guide: allowed", run(bash("gh pr create -t x --body-file body.md", d)), False)
    check("-F file without guide: denied", run(bash("gh pr create -t x -F bad.md", d)), True)
    check("unreadable body file: fails open", run(bash("gh pr create -t x --body-file nope.md", d)), False)
check("after cd &&: still seen", run(bash("cd repo && gh pr create --fill")), True)
check("gh pr list: ignored", run(bash("gh pr list")), False)
check("heredoc that mentions gh pr create: ignored",
      run(bash("cat > notes.md <<'EOF'\ngh pr create --fill\nEOF")), False)

print("gh api")
check("POST to pulls with guide: allowed",
      run(bash(f"gh api -X POST repos/o/r/pulls -f title=x -f head=b -f base=main -f body='{GOOD}'")), False)
check("fields to pulls without guide: denied",
      run(bash("gh api repos/o/r/pulls -f title=x -f head=b -f base=main -f body='Summary'")), True)
check("GET pulls: ignored", run(bash("gh api 'repos/o/r/pulls?state=open' --jq length")), False)
check("-X GET with fields: ignored", run(bash("gh api -X GET repos/o/r/pulls -f state=open")), False)
check("PATCH a PR: ignored", run(bash("gh api -X PATCH repos/o/r/pulls/12 -f body=x")), False)
check("comment on a PR: ignored", run(bash("gh api repos/o/r/pulls/12/comments -f body=x")), False)
with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, "pr.json"), "w").write(json.dumps({"title": "x", "body": GOOD}))
    check("--input JSON with guide: allowed", run(bash("gh api repos/o/r/pulls --input pr.json", d)), False)
    open(os.path.join(d, "b.md"), "w").write(GOOD)
    check("-F body=@file with guide: allowed", run(bash("gh api repos/o/r/pulls -f title=x -F body=@b.md", d)), False)

print("MCP")
mcp = {"tool_name": "mcp__github__create_pull_request", "tool_input": {"owner": "o", "repo": "r", "body": GOOD}}
check("create_pull_request with guide: allowed", run(mcp), False)
check("create_pull_request without: denied",
      run({"tool_name": "mcp__github__create_pull_request", "tool_input": {"body": "## Summary"}}), True)
check("plugin-namespaced server: denied too",
      run({"tool_name": "mcp__plugin_engineering_github__create_pull_request", "tool_input": {}}), True)
check("update_pull_request: ignored", run({"tool_name": "mcp__github__update_pull_request", "tool_input": {}}), False)

print("off switch and failing open")
check("PERSONAL_REVIEW_GUIDE=0: allowed", run(bash("gh pr create --fill"), {"PERSONAL_REVIEW_GUIDE": "0"}), False)
check("other tools: ignored", run({"tool_name": "Read", "tool_input": {"file_path": "x"}}), False)
check("input that isn't JSON: silent", run(None, raw="not json"), False)
check("no command: silent", run({"tool_name": "Bash", "tool_input": {}}), False)

if failures:
    print(f"{failures} pr_body_guard test(s) failed", file=sys.stderr)
    sys.exit(1)
print("all pr_body_guard tests passed")
