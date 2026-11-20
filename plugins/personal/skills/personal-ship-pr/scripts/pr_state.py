#!/usr/bin/env python3
"""Facts about one pull request, from GitHub's REST API through `gh api`, as JSON.

    pr_state.py [--repo OWNER/REPO] [--pr N]
    pr_state.py ... --wait-until checks-done|review-on-head|conflict|change
                [--reviewer PREFIX ...] [--interval S] [--timeout S] [--grace S]

Without --wait-until it prints the state once. With it, it polls every
--interval seconds and prints the state when the condition holds (exit 0),
or when --timeout passes first (exit 3, "timed_out": true):

- checks-done: no check run or commit status on the head commit is still
  pending, and the same checks were there on the previous poll (so a fast
  check that finishes before slower CI registers doesn't end the wait),
  or --grace seconds have passed with none (a repo without CI).
- review-on-head: a review of the head commit by a login that starts with
  any one --reviewer prefix, case-insensitive (default `copilot`; `any`
  for anyone). It's any-of: wait once per reviewer to wait for several.
- conflict: GitHub reports the PR conflicts with its base
  (`mergeable_state` is `dirty`), or it's no longer open (merged or
  closed), so a parked watch ends either way.
- change: anything in the state differs from the first poll (a push, a
  check, a review, a comment, draft or mergeable state).

It reports facts and emits no verdicts: which failure the change caused,
what a finding means and what to do next are the agent's calls
(personal-ship-pr). The repo defaults to origin's GitHub owner/repo and the
PR to the open one whose head is the current branch. Exit 1 when gh or git
can't answer at the start; a poll that fails later is retried.
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse

GITHUB_REMOTE = re.compile(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/*$")
FAILED = {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"}
PER_PAGE = 100


class Unavailable(Exception):
    pass


def run(*argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Unavailable(f"{argv[0]}: {e}")
    if r.returncode != 0:
        raise Unavailable(f"{' '.join(argv[:3])}: {(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout


def api(path):
    return json.loads(run("gh", "api", path) or "null")


def default_repo():
    m = GITHUB_REMOTE.search(run("git", "remote", "get-url", "origin").strip())
    if not m:
        raise Unavailable("origin is not a GitHub remote; pass --repo OWNER/REPO")
    return f"{m.group(1)}/{m.group(2)}"


def default_pr(repo):
    branch = run("git", "branch", "--show-current").strip()
    if not branch:
        raise Unavailable("detached HEAD; pass --pr N")
    owner = repo.split("/")[0]
    head = urllib.parse.quote(f"{owner}:{branch}", safe=":/")
    pulls = api(f"repos/{repo}/pulls?head={head}&state=open&per_page=5")
    if not pulls:
        raise Unavailable(f"no open PR with head {owner}:{branch}; pass --pr N")
    return pulls[0]["number"]


def snapshot(repo, number):
    pr = api(f"repos/{repo}/pulls/{number}")
    head = pr["head"]["sha"]
    runs = api(f"repos/{repo}/commits/{head}/check-runs?per_page={PER_PAGE}").get("check_runs", [])
    statuses = api(f"repos/{repo}/commits/{head}/status").get("statuses", [])
    reviews = api(f"repos/{repo}/pulls/{number}/reviews?per_page={PER_PAGE}")
    comments = api(f"repos/{repo}/pulls/{number}/comments?per_page={PER_PAGE}")

    checks = [{"name": c["name"], "kind": "check_run",
               "state": c["conclusion"] if c["status"] == "completed" else "pending"} for c in runs]
    checks += [{"name": s["context"], "kind": "status", "state": s["state"]} for s in statuses]
    checks.sort(key=lambda c: (c["kind"], c["name"]))
    pending = [c["name"] for c in checks if c["state"] == "pending"]
    failed = [c["name"] for c in checks if c["state"] in FAILED or c["state"] == "error"]

    threads = {}
    for c in sorted(comments, key=lambda c: c["id"]):
        root = c.get("in_reply_to_id") or c["id"]
        t = threads.setdefault(root, {"id": root, "path": c.get("path"), "line": c.get("line"),
                                      "author": c["user"]["login"], "commit_id": c.get("commit_id"),
                                      "on_head": c.get("commit_id") == head, "replies": 0})
        if root != c["id"]:
            t["replies"] += 1
        t["last_author"] = c["user"]["login"]

    return {
        "repo": repo, "number": number, "url": pr.get("html_url"), "state": pr["state"],
        "draft": pr.get("draft", False), "merged": pr.get("merged", False),
        "mergeable": pr.get("mergeable"), "mergeable_state": pr.get("mergeable_state"),
        "head_sha": head, "head_ref": pr["head"]["ref"], "base_ref": pr["base"]["ref"],
        "requested_reviewers": [u["login"] for u in pr.get("requested_reviewers", [])],
        "checks": {"total": len(checks), "pending": pending, "failed": failed, "all": checks},
        "reviews": [{"id": r["id"], "author": r["user"]["login"], "state": r["state"],
                     "commit_id": r.get("commit_id"), "on_head": r.get("commit_id") == head,
                     "submitted_at": r.get("submitted_at"), "body_chars": len(r.get("body") or "")}
                    for r in reviews],
        "threads": list(threads.values()),
        "truncated": [n for n, xs in (("check_runs", runs), ("reviews", reviews), ("comments", comments))
                      if len(xs) >= PER_PAGE],
    }


def fingerprint(s):
    return json.dumps([s["head_sha"], s["draft"], s["state"], s["mergeable_state"], s["checks"]["all"],
                       [r["id"] for r in s["reviews"]], [(t["id"], t["replies"]) for t in s["threads"]]],
                      sort_keys=True)


def check_names(s):
    return sorted((c["kind"], c["name"]) for c in s["checks"]["all"])


def met(condition, s, first, prev, elapsed, reviewers, grace):
    if condition == "checks-done":
        if s["checks"]["pending"]:
            return False
        if s["checks"]["total"] == 0:
            return elapsed >= grace
        return prev is not None and check_names(prev) == check_names(s)
    if condition == "review-on-head":
        return any(r["on_head"] and ("any" in reviewers or r["author"].lower().startswith(reviewers))
                   for r in s["reviews"])
    if condition == "conflict":
        return s["mergeable_state"] == "dirty" or s["state"] != "open" or s["merged"]
    return fingerprint(s) != fingerprint(first)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--repo")
    p.add_argument("--pr", type=int)
    p.add_argument("--wait-until", choices=["checks-done", "review-on-head", "conflict", "change"])
    p.add_argument("--reviewer", action="append")
    p.add_argument("--interval", type=float, default=60)
    p.add_argument("--timeout", type=float, default=3600)
    p.add_argument("--grace", type=float, default=180)
    a = p.parse_args()
    reviewers = tuple(r.lower() for r in (a.reviewer or ["copilot"]))

    try:
        repo = a.repo or default_repo()
        number = a.pr or default_pr(repo)
        first = state = snapshot(repo, number)
    except (Unavailable, KeyError, TypeError, ValueError) as e:
        print(f"pr_state: {e}", file=sys.stderr)
        return 1

    start, prev = time.monotonic(), None
    while a.wait_until:
        elapsed = time.monotonic() - start
        if met(a.wait_until, state, first, prev, elapsed, reviewers, a.grace):
            break
        if elapsed >= a.timeout:
            state["timed_out"] = True
            break
        time.sleep(max(0, min(a.interval, a.timeout - elapsed)))
        try:
            prev, state = state, snapshot(repo, number)
        except (Unavailable, KeyError, TypeError, ValueError) as e:
            print(f"pr_state: poll failed, retrying: {e}", file=sys.stderr)

    if a.wait_until:
        state["condition"] = a.wait_until
        state["elapsed_s"] = round(time.monotonic() - start)
    print(json.dumps(state, indent=2))
    return 3 if state.get("timed_out") else 0


if __name__ == "__main__":
    sys.exit(main())
