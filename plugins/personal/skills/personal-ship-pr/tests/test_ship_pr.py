#!/usr/bin/env python3
"""Offline tests for scripts/pr_state.py (against a fake `gh`) and scripts/ship_pr_hook.py (as the hook runs it)."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
STATE = os.path.join(SCRIPTS, "pr_state.py")
HOOK = os.path.join(SCRIPTS, "ship_pr_hook.py")
HOOKS_FILE = os.path.join(HERE, "..", "..", "..", "hooks", "claude-hooks.json")
failures = 0

# A fake gh: `gh api [--paginate --slurp] <path>` answers from $FAKE_GH/<key>.<n>.json for its nth call of that
# path, else <key>.json. With --slurp the answer is wrapped as one page, unless the fixture is <key>.pages.json,
# which holds every page already.
FAKE_GH = r'''#!/usr/bin/env python3
import os, re, sys
d = os.environ["FAKE_GH"]
args = sys.argv[1:]
paths = [a for a in args[1:] if not a.startswith("-")]
if args[:1] != ["api"] or len(paths) != 1:
    sys.exit("fake gh: only `gh api [--paginate --slurp] <path>`")
slurp = "--slurp" in args
key = re.sub(r"[^A-Za-z0-9]+", "_", paths[0]).strip("_")
count = os.path.join(d, "." + key)
n = int(open(count).read()) + 1 if os.path.exists(count) else 1
open(count, "w").write(str(n))
if slurp and os.path.exists(os.path.join(d, key + ".pages.json")):
    sys.stdout.write(open(os.path.join(d, key + ".pages.json")).read())
    sys.exit(0)
for name in (f"{key}.{n}.json", f"{key}.json"):
    if os.path.exists(os.path.join(d, name)):
        body = open(os.path.join(d, name)).read()
        sys.stdout.write("[" + body + "]" if slurp else body)
        sys.exit(0)
sys.exit(f"fake gh: no fixture for {key}")
'''

REPO = "acme/orders"
HEAD = "h2"


def key(path):
    return re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_")


def check(name, ok, detail=""):
    global failures
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}" + ("" if ok else f": {detail}"))
    if not ok:
        failures += 1


class Fake:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.bin = os.path.join(self.dir, "bin")
        os.mkdir(self.bin)
        gh = os.path.join(self.bin, "gh")
        open(gh, "w").write(FAKE_GH)
        os.chmod(gh, 0o755)
        self.base()

    def put(self, path, data, n=None):
        name = key(path) + (f".{n}" if n else "") + ".json"
        open(os.path.join(self.dir, name), "w").write(json.dumps(data))

    def base(self):
        self.put(f"repos/{REPO}/pulls/7", {"number": 7, "html_url": "https://github.com/acme/orders/pull/7",
                                           "state": "open", "draft": True, "merged": False, "mergeable": True,
                                           "mergeable_state": "clean", "head": {"sha": HEAD, "ref": "feature/x"},
                                           "base": {"ref": "main"}, "requested_reviewers": [{"login": "Copilot"}]})
        self.checks(pending=True)
        self.put(f"repos/{REPO}/commits/{HEAD}/status?per_page=100", {"statuses": [{"context": "lint", "state": "success"}]})
        self.put(f"repos/{REPO}/pulls/7/reviews?per_page=100", [
            {"id": 1, "user": {"login": "copilot-pull-request-reviewer[bot]"}, "state": "COMMENTED",
             "commit_id": "h1", "submitted_at": "t", "body": "found 2"}])
        self.put(f"repos/{REPO}/pulls/7/comments?per_page=100", [
            {"id": 10, "user": {"login": "copilot-pull-request-reviewer[bot]"}, "path": "a.go", "line": 3,
             "commit_id": "h1"},
            {"id": 11, "in_reply_to_id": 10, "user": {"login": "gary"}, "path": "a.go", "line": 3, "commit_id": "h1"},
            {"id": 12, "user": {"login": "copilot-pull-request-reviewer[bot]"}, "path": "b.go", "line": 9,
             "commit_id": HEAD}])

    def checks(self, pending=False, failed=False, none=False, n=None):
        runs = [] if none else [
            {"name": "test", "status": "in_progress" if pending else "completed",
             "conclusion": None if pending else ("failure" if failed else "success")},
            {"name": "build", "status": "completed", "conclusion": "success"}]
        self.put(f"repos/{REPO}/commits/{HEAD}/check-runs?per_page=100", {"check_runs": runs}, n)

    def run(self, *args):
        env = {**os.environ, "FAKE_GH": self.dir, "PATH": self.bin + os.pathsep + os.environ["PATH"]}
        r = subprocess.run([sys.executable, "-I", STATE, "--repo", REPO, "--pr", "7", *args],
                           capture_output=True, text=True, env=env, timeout=30)
        try:
            out = json.loads(r.stdout) if r.stdout.strip() else None
        except ValueError:
            out = None
        return r.returncode, out, r.stderr


print("pr_state.py: one snapshot")
f = Fake()
rc, s, err = f.run()
check("exits 0", rc == 0, err)
check("head and draft", s and s["head_sha"] == HEAD and s["draft"] is True, s)
check("pending check named", s and s["checks"]["pending"] == ["test"], s and s["checks"])
check("statuses counted with check runs", s and s["checks"]["total"] == 3, s and s["checks"])
check("review on an old commit isn't on head", s and s["reviews"][0]["on_head"] is False, s and s["reviews"])
check("review body size reported", s and s["reviews"][0]["body_chars"] == 7, s and s["reviews"])
threads = {t["id"]: t for t in (s or {}).get("threads", [])}
check("reply folds into its thread", threads.get(10, {}).get("replies") == 1 and threads[10]["last_author"] == "gary",
      threads)
check("new thread on head", threads.get(12, {}).get("on_head") is True, threads)
check("no verdict fields", s and not {"verdict", "ready", "ok"} & set(s), s and list(s))

print("pr_state.py: waits")
f = Fake()
f.checks(pending=True, n=1)
f.checks(failed=True, n=2)
rc, s, err = f.run("--wait-until", "checks-done", "--interval", "0")
check("checks-done returns when nothing is pending", rc == 0 and s and s["checks"]["failed"] == ["test"], (rc, s, err))
check("  ...names the condition", s and s.get("condition") == "checks-done", s)

f = Fake()
f.checks(none=True, n=1)
f.checks(pending=True, n=2)
f.checks(n=3)
f.checks(n=4)
rc, s, err = f.run("--wait-until", "checks-done", "--interval", "0")
check("a fast check alone doesn't end the wait before CI registers",
      rc == 0 and s and s["checks"]["total"] == 3 and not s["checks"]["pending"], (rc, s and s["checks"], err))

f = Fake()
rc, s, err = f.run("--wait-until", "checks-done", "--interval", "0", "--timeout", "0")
check("timeout: exit 3, timed_out", rc == 3 and s and s.get("timed_out") is True, (rc, err))

f = Fake()
f.checks(none=True)
f.put(f"repos/{REPO}/commits/{HEAD}/status?per_page=100", {"statuses": []})
rc, s, err = f.run("--wait-until", "checks-done", "--interval", "0", "--grace", "0")
check("no CI: done after the grace period", rc == 0 and s and s["checks"]["total"] == 0, (rc, err))
rc, s, err = f.run("--wait-until", "checks-done", "--interval", "0", "--grace", "100", "--timeout", "0")
check("no CI, inside the grace period: not done", rc == 3, (rc, err))

f = Fake()
f.put(f"repos/{REPO}/pulls/7/reviews?per_page=100", [
    {"id": 1, "user": {"login": "copilot-pull-request-reviewer[bot]"}, "state": "COMMENTED", "commit_id": "h1"},
    {"id": 2, "user": {"login": "copilot-pull-request-reviewer[bot]"}, "state": "COMMENTED", "commit_id": HEAD}], n=2)
rc, s, err = f.run("--wait-until", "review-on-head", "--interval", "0")
check("review-on-head: waits for Copilot on the head commit", rc == 0 and s and len(s["reviews"]) == 2, (rc, err))
f = Fake()
f.put(f"repos/{REPO}/pulls/7/reviews?per_page=100", [
    {"id": 3, "user": {"login": "someone"}, "state": "APPROVED", "commit_id": HEAD}])
rc, s, err = f.run("--wait-until", "review-on-head", "--interval", "0", "--timeout", "0")
check("  ...someone else's review doesn't count", rc == 3, (rc, err))
rc, s, err = f.run("--wait-until", "review-on-head", "--reviewer", "any", "--interval", "0")
check("  ...unless --reviewer any", rc == 0, (rc, err))
f = Fake()
f.put(f"repos/{REPO}/pulls/7/reviews?per_page=100", [
    {"id": 4, "user": {"login": "gary"}, "state": "PENDING", "commit_id": HEAD}])
rc, s, err = f.run("--wait-until", "review-on-head", "--reviewer", "any", "--interval", "0", "--timeout", "0")
check("  ...an unsubmitted (PENDING) review doesn't count", rc == 3, (rc, err))

f = Fake()
f.checks(pending=True, n=1)
f.checks(pending=True, n=2)
f.checks(failed=True, n=3)
rc, s, err = f.run("--wait-until", "change", "--interval", "0")
check("change: returns on the first difference", rc == 0 and s and s["checks"]["failed"] == ["test"], (rc, err))

f = Fake()
pr = json.load(open(os.path.join(f.dir, key(f"repos/{REPO}/pulls/7") + ".json")))
f.put(f"repos/{REPO}/pulls/7", {**pr, "mergeable": False, "mergeable_state": "dirty"}, n=2)
rc, s, err = f.run("--wait-until", "conflict", "--interval", "0")
check("conflict: returns when GitHub says dirty", rc == 0 and s and s["mergeable_state"] == "dirty", (rc, err))
f = Fake()
rc, s, err = f.run("--wait-until", "conflict", "--interval", "0", "--timeout", "0")
check("  ...a clean PR keeps waiting", rc == 3, (rc, err))
f = Fake()
f.put(f"repos/{REPO}/pulls/7", {**pr, "state": "closed", "merged": True}, n=2)
rc, s, err = f.run("--wait-until", "conflict", "--interval", "0")
check("  ...and ends when the PR merges", rc == 0 and s and s["merged"] is True, (rc, err))
f = Fake()
f.put(f"repos/{REPO}/pulls/7", {**pr, "mergeable_state": "behind"}, n=2)
rc, s, err = f.run("--wait-until", "conflict", "--interval", "0")
check("  ...and when it falls behind where the repo requires up to date",
      rc == 0 and s and s["mergeable_state"] == "behind", (rc, err))

print("pr_state.py: Copilot round 1")
f = Fake()
pending_page = {"check_runs": [{"name": "e2e", "status": "queued", "conclusion": None}]}
done_page = {"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"}]}
open(os.path.join(f.dir, key(f"repos/{REPO}/commits/{HEAD}/check-runs?per_page=100") + ".pages.json"), "w").write(
    json.dumps([done_page, pending_page]))
rc, s, err = f.run()
check("a pending check on page 2 is seen", rc == 0 and s and s["checks"]["pending"] == ["e2e"], (rc, s and s["checks"]))

f = Fake()
H3 = "h3"
f.put(f"repos/{REPO}/pulls/7", {**pr, "head": {"sha": H3, "ref": "feature/x"}}, n=2)
f.put(f"repos/{REPO}/pulls/7", {**pr, "head": {"sha": H3, "ref": "feature/x"}})
f.checks(n=1)
same_done = {"check_runs": [{"name": "test", "status": "completed", "conclusion": "success"},
                            {"name": "build", "status": "completed", "conclusion": "success"}]}
same_running = {"check_runs": [{"name": "test", "status": "in_progress", "conclusion": None},
                               {"name": "build", "status": "completed", "conclusion": "success"}]}
f.put(f"repos/{REPO}/commits/{H3}/check-runs?per_page=100", same_done, 1)
f.put(f"repos/{REPO}/commits/{H3}/check-runs?per_page=100", same_running, 2)
f.put(f"repos/{REPO}/commits/{H3}/check-runs?per_page=100", same_done)
f.put(f"repos/{REPO}/commits/{H3}/status?per_page=100", {"statuses": [{"context": "lint", "state": "success"}]})
rc, s, err = f.run("--wait-until", "checks-done", "--interval", "0")
h3_calls = int(open(os.path.join(f.dir, "." + key(f"repos/{REPO}/commits/{H3}/check-runs?per_page=100"))).read())
check("a push mid-wait starts the new commit's checks over", rc == 0 and s and s["head_sha"] == H3 and h3_calls >= 3,
      (rc, h3_calls, err))

f = Fake()
f.put(f"repos/{REPO}/pulls/7/reviews?per_page=100", [
    {"id": 1, "user": {"login": "copilot-pull-request-reviewer[bot]"}, "state": "DISMISSED", "commit_id": "h1",
     "submitted_at": "t", "body": "found 2"}], n=2)
f.checks(pending=True, n=2)
rc, s, err = f.run("--wait-until", "change", "--interval", "0", "--timeout", "1")
check("change: a dismissed review (same id) counts", rc == 0 and s and s["reviews"][0]["state"] == "DISMISSED", (rc, err))
f = Fake()
f.put(f"repos/{REPO}/pulls/7", {**pr, "requested_reviewers": []}, n=2)
rc, s, err = f.run("--wait-until", "change", "--interval", "0", "--timeout", "1")
check("  ...and so does a reviewer request ending", rc == 0 and s and s["requested_reviewers"] == [], (rc, err))

print("pr_state.py: errors")
f = Fake()
os.remove(os.path.join(f.dir, key(f"repos/{REPO}/pulls/7") + ".json"))
rc, s, err = f.run()
check("gh can't answer at the start: exit 1", rc == 1 and "pr_state:" in err, (rc, err))
f = Fake()
f.checks(pending=True, n=1)
os.rename(os.path.join(f.dir, key(f"repos/{REPO}/pulls/7") + ".json"),
          os.path.join(f.dir, key(f"repos/{REPO}/pulls/7") + ".1.json"))
f.put(f"repos/{REPO}/commits/{HEAD}/check-runs?per_page=100", {"check_runs": []}, n=3)
rc, s, err = f.run("--wait-until", "checks-done", "--interval", "0.05", "--timeout", "0.3")
check("a failed poll later is retried, not fatal", rc == 3 and s is not None and "retrying" in err, (rc, err))
f = Fake()
f.checks(none=True)
f.put(f"repos/{REPO}/commits/{HEAD}/status?per_page=100", {"statuses": []})
os.rename(os.path.join(f.dir, key(f"repos/{REPO}/pulls/7") + ".json"),
          os.path.join(f.dir, key(f"repos/{REPO}/pulls/7") + ".1.json"))
rc, s, err = f.run("--wait-until", "checks-done", "--interval", "0.05", "--grace", "0.1", "--timeout", "0.4")
check("grace never passes on a stale snapshot while polls fail", rc == 3, (rc, err))


print("pr_state.py: the repo from origin")


def run_without_repo(f, origin_url, script=STATE):
    """Run pr_state with no --repo, in a fixture repo whose origin is origin_url; returns (rc, state, stderr)."""
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q", d], check=True)
        if origin_url:
            subprocess.run(["git", "-C", d, "remote", "add", "origin", origin_url], check=True)
        env = {**os.environ, "FAKE_GH": f.dir, "PATH": f.bin + os.pathsep + os.environ["PATH"]}
        r = subprocess.run([sys.executable, "-I", script, "--pr", "7"], capture_output=True, text=True, env=env,
                           cwd=d, timeout=30)
    try:
        out = json.loads(r.stdout) if r.stdout.strip() else None
    except ValueError:
        out = None
    return r.returncode, out, r.stderr


for url in (f"git@github.com-work:{REPO}.git", f"ssh://git@ssh.github.com:443/{REPO}.git",
            f"http://local_proxy@127.0.0.1:41923/git/{REPO}", f"https://github.com/{REPO}"):
    rc, s, err = run_without_repo(Fake(), url)
    check(f"origin {url.split('@')[-1]}: owner/repo found", rc == 0 and s and s["head_sha"] == HEAD, (rc, err))
for url in (f"https://gitlab.com/{REPO}.git", f"https://attacker.example/{REPO}.git", None):
    rc, s, err = run_without_repo(Fake(), url)
    check(f"origin {url}: not a GitHub remote, asks for --repo",
          rc != 0 and "origin is not a GitHub remote; pass --repo OWNER/REPO" in err, (rc, err))
with tempfile.TemporaryDirectory() as lone:
    os.makedirs(os.path.join(lone, "scripts"))
    shutil.copy(STATE, os.path.join(lone, "scripts", "pr_state.py"))
    rc, s, err = run_without_repo(Fake(), f"https://github.com/{REPO}", os.path.join(lone, "scripts", "pr_state.py"))
    check("no origin.py beside the plugin root: says where it looked, asks for --repo",
          rc != 0 and "origin.py not found at" in err and "pass --repo OWNER/REPO" in err, (rc, err))


print("ship_pr_hook.py")


def hook(event, env_extra=None, raw=None):
    env = {k: v for k, v in os.environ.items() if k != "PERSONAL_SHIP_PR"}
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, "-I", HOOK], input=raw if raw is not None else json.dumps(event),
                       capture_output=True, text=True, env=env)
    if r.returncode != 0:
        return f"exit {r.returncode}"
    if not r.stdout.strip():
        return None
    out = json.loads(r.stdout)["hookSpecificOutput"]
    return out["additionalContext"] if out.get("hookEventName") == "PostToolUse" else "wrong event"


def bash(command, stdout=None, stderr=""):
    event = {"tool_name": "Bash", "tool_input": {"command": command}}
    if stdout is not None:
        event["tool_response"] = {"stdout": stdout, "stderr": stderr, "interrupted": False}
    return event


def fires(name, got, want):
    check(name, (got is not None and "personal-ship-pr" in got) == want and not str(got).startswith(("exit", "wrong")),
          repr(got))


fires("MCP create_pull_request", hook({"tool_name": "mcp__github__create_pull_request", "tool_input": {}}), True)
fires("gh pr create --draft", hook(bash("gh pr create --draft -t x -F body.md")), True)
fires("after cd &&", hook(bash("cd repo && gh pr create --fill")), True)
fires("gh pr create --web: no PR yet", hook(bash("gh pr create --web")), False)
fires("gh api POST pulls", hook(bash("gh api -X POST repos/a/b/pulls -f title=x -f head=y -f base=main")), True)
fires("gh api with fields, no method", hook(bash("gh api repos/a/b/pulls -f title=x")), True)
fires("gh api GET pulls", hook(bash("gh api repos/a/b/pulls")), False)
fires("gh api -X GET with fields", hook(bash("gh api -X GET repos/a/b/pulls -f state=open")), False)
fires("gh api PATCH a PR", hook(bash("gh api -X PATCH repos/a/b/pulls/3 -f draft=false")), False)
fires("gh pr list", hook(bash("gh pr list")), False)
fires("gh pr create --dry-run", hook(bash("gh pr create --dry-run -t x -b y")), False)
fires("gh pr create that printed the PR URL",
      hook(bash("gh pr create -t x -F b.md", "https://github.com/a/b/pull/12\n")), True)
fires("gh api that returned the PR", hook(bash("gh api -X POST repos/a/b/pulls -f title=x",
                                                 '{"html_url": "https://github.com/a/b/pull/12"}')), True)
fires("gh pr create that failed (no URL, error on stderr)",
      hook(bash("gh pr create -t x -F b.md", "", "pull request create failed: GraphQL: No commits")), False)
fires("gh api that failed (HTTP 422)",
      hook(bash("gh api -X POST repos/a/b/pulls -f title=x", "", "gh: Validation Failed (HTTP 422)")), False)
fires("gh api --jq .number: no URL, no error", hook(bash("gh api -X POST repos/a/b/pulls -f title=x --jq .number",
                                                           "12\n")), True)
fires("gh pr create with stdout redirected: progress on stderr only",
      hook(bash("gh pr create -t x -F b.md > /dev/null", "", "Creating pull request for x into main in a/b")), True)
fires("MCP call flagged as an error", hook({"tool_name": "mcp__github__create_pull_request",
                                            "tool_response": {"isError": True}}), False)
fires("gh pr create --help", hook(bash("gh pr create --help")), False)
fires("gh api ... pulls -h", hook(bash("gh api -X POST repos/a/b/pulls -h")), False)
fires("--dry-run on a continued line", hook(bash("gh pr create --body-file pr.md \\\n  --dry-run")), False)
fires("--web on a continued line", hook(bash("gh pr create -t x \\\n  --web")), False)
fires("a continued gh pr create still counts", hook(bash("gh pr create --draft \\\n  -t x -F b.md")), True)
ctx = hook({"tool_name": "mcp__github__create_pull_request"}) or ""
check("context asks to confirm a new PR exists first", "First confirm it did" in ctx, ctx)
fires("heredoc mentioning gh pr create", hook(bash("cat > n.md <<'EOF'\ngh pr create --fill\nEOF")), False)
fires("other MCP tool", hook({"tool_name": "mcp__github__update_pull_request", "tool_input": {}}), False)
fires("PERSONAL_SHIP_PR=0 turns it off", hook({"tool_name": "mcp__github__create_pull_request"},
                                               {"PERSONAL_SHIP_PR": "0"}), False)
fires("not JSON: fails open", hook(None, raw="nope"), False)
ctx = hook({"tool_name": "mcp__github__create_pull_request"}) or ""
check("context says not to merge and how to skip review", "Never merge" in ctx and "Skipping /code-review" in ctx, ctx)

try:
    entries = json.load(open(HOOKS_FILE))["hooks"]["PostToolUse"]
    mine = [e for e in entries if any("personal-ship-pr/scripts/ship_pr_hook.py" in h["command"] for h in e["hooks"])]
    m = re.compile(mine[0]["matcher"])
    ok = (len(mine) == 1 and m.fullmatch("Bash") and m.fullmatch("mcp__github__create_pull_request")
          and not m.fullmatch("Read") and "exit 2" not in mine[0]["hooks"][0]["command"])
    check("claude-hooks.json registers the hook on PostToolUse, failing open", bool(ok), mine)
except (KeyError, IndexError, OSError, ValueError) as e:
    check("claude-hooks.json registers the hook on PostToolUse, failing open", False, e)

if failures:
    print(f"{failures} ship-pr test(s) failed", file=sys.stderr)
    sys.exit(1)
print("all ship-pr tests passed")
