#!/usr/bin/env python3
"""Deterministic git checks around one orchestrate dispatch unit.

  check_wave.py snapshot DIR...                 before the launch: HEAD and dirty paths per working directory
  check_wave.py check --snapshot S --run R      after it, from a Claude Code workflow run record
  check_wave.py check --snapshot S --group J    after it, one JSON group per flag (any harness):
      {"id","workdir","steps","from","trailers"}
  check options:
      --plan P       the plan file (default: the run record's args.plan.path)
      --baseline B   for a fix-up: the snapshot taken before the wave it fixes, kept until the
                     streak ends, so a path that wave left behind is checked again

check verifies, per group (orchestrate runs only on a task branch): `from` is
an ancestor of HEAD; every commit in from..HEAD has a first line
`<step-id> <subject>` for one of the group's steps, a blank second line, no
Co-authored-by or Signed-off-by line, and the required trailers in its last
paragraph; every step has a commit; no new dirty paths (new since the
baseline too, when one is given); and every snapshotted directory without a
group is unchanged. A commit that touches only the plan and its session
handoff (handoff-{topic}-{word}.md beside plan-{topic}-{word}.md), under a
subject that doesn't start with a step ID, is the parent's bookkeeping
commit: it is listed and skipped, in a group's range and in a directory
with no group (the plan's repo, when no group runs there). Any other commit
that touches either file fails. It prints JSON with each group's `to` (the
reviewed HEAD) and exits 1 on any problem.

The output also sorts out the scope breaches that stop at gate 1 in both
modes (decision 10), since no fix-up can repair them: `scope` lists a `from`
that is no longer an ancestor of HEAD and every directory with no group that
changed; `uncommitted` lists each group's new uncommitted paths, which are a
scope breach on a workstation only (they may be Gary's own edits) and an
ordinary failure, fixed by `N-fix`, on a runner.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

BANNED = re.compile(r"\b(co-authored-by|signed-off-by):", re.I)
STEP_ID = re.compile(r"^(?:m\d+\.)?s\d+ ")  # a step commit's subject, never a bookkeeping commit's


def git(d, *a, check=True):
    r = subprocess.run(["git", "-C", d, *a], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(a)} in {d}: {r.stderr.strip()}")
    return r


def dirty(d):
    out = git(d, "status", "--porcelain", "--untracked-files=all").stdout
    return sorted(line[3:] for line in out.splitlines() if line)


def snapshot(dirs):
    snap, problems = {}, []
    for d in dirs:
        d = str(Path(d).resolve())
        snap[d] = {"head": git(d, "rev-parse", "HEAD").stdout.strip(), "dirty": dirty(d)}
        if git(d, "check-ignore", "-q", ".scratch/x", check=False).returncode:
            problems.append(f"{d}: .scratch/ is not gitignored, so worker artifacts would show as untracked")
        settings = Path(d, ".claude/settings.json")
        try:
            attribution = json.loads(settings.read_text()).get("attribution", {}).get("commit")
        except (OSError, ValueError):
            attribution = None
        snap[d]["attribution"] = attribution
    return {"dirs": snap, "problems": problems}


def plan_files(d, plan):
    """The plan and its session handoff, as paths relative to d's repository root, if they are inside it."""
    if not plan:
        return set()
    top = Path(git(d, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    p = Path(plan).resolve()
    files = [p] + ([p.with_name("handoff-" + p.name[len("plan-"):])] if p.name.startswith("plan-") else [])
    return {str(f.relative_to(top)) for f in files if f.is_relative_to(top)}


def check_group(g, base, plan=None, baseline=None):
    d, problems = g["workdir"], []
    if git(d, "merge-base", "--is-ancestor", g["from"], "HEAD", check=False).returncode:
        return {"id": g["id"], "workdir": d, "to": None, "problems": [f"from {g['from']} is not an ancestor of HEAD"],
                "bookkeeping": [], "uncommitted": [], "scope": True}
    to = git(d, "rev-parse", "--short", "HEAD").stdout.strip()
    shas = git(d, "rev-list", "--reverse", f"{g['from']}..HEAD").stdout.split()
    covered, books, mine = set(), [], plan_files(d, plan)
    for sha in shas:
        msg = git(d, "log", "-1", "--format=%B", sha).stdout.rstrip("\n")
        lines = msg.split("\n")
        short = sha[:7]
        m = re.match(r"^(\S+) \S", lines[0])
        touched = set(git(d, "diff-tree", "--root", "-r", "--no-commit-id", "--name-only", sha).stdout.split("\n")) - {""}
        if mine and touched & mine:
            if touched <= mine and not (m and m.group(1) in g["steps"]):
                books.append(short)  # the parent's plan and handoff commit, inside a fix-up's or a relaunch's range
            else:
                problems.append(f"{short}: touches the plan or its handoff ({', '.join(sorted(touched & mine))}); only the parent's bookkeeping commits may, under a subject with no step ID")
            continue
        if not m or m.group(1) not in g["steps"]:
            problems.append(f"{short}: first line {lines[0][:80]!r} does not start with one of {', '.join(g['steps'])}")
        else:
            covered.add(m.group(1))
        if len(lines) > 1 and lines[1].strip():
            problems.append(f"{short}: no blank line after the subject")
        if BANNED.search(msg):
            problems.append(f"{short}: carries a Co-authored-by or Signed-off-by line")
        last = msg.split("\n\n")[-1].split("\n")
        missing = [t for t in g.get("trailers", []) if t not in last]
        if missing or len(msg.split("\n\n")) < 2:
            problems.append(f"{short}: last paragraph lacks {', '.join(missing) or 'the trailers'}")
    for s in g["steps"]:
        if s not in covered:
            problems.append(f"step {s} has no commit")
    before = set(base.get("dirty", []))
    if baseline is not None:
        before &= set(baseline.get("dirty", []))  # a fix-up: what the fixed wave left behind is checked again
    new = sorted(set(dirty(d)) - before)
    if new:
        problems.append(f"uncommitted paths left behind: {', '.join(new[:10])}")
    return {"id": g["id"], "workdir": d, "to": to, "problems": problems, "bookkeeping": books, "uncommitted": new, "scope": False}


def only_bookkeeping(d, old, plan):
    """The short SHAs of old..HEAD in d when every commit there is the parent's plan and handoff commit, else None."""
    mine = plan_files(d, plan)
    if not mine or git(d, "merge-base", "--is-ancestor", old, "HEAD", check=False).returncode:
        return None
    books = []
    for sha in git(d, "rev-list", "--reverse", f"{old}..HEAD").stdout.split():
        touched = set(git(d, "diff-tree", "--root", "-r", "--no-commit-id", "--name-only", sha).stdout.split("\n")) - {""}
        if not touched or not touched <= mine or STEP_ID.match(git(d, "log", "-1", "--format=%s", sha).stdout):
            return None
        books.append(sha[:7])
    return books


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("snapshot", "check"):
        sys.exit(__doc__)
    if sys.argv[1] == "snapshot":
        out = snapshot(sys.argv[2:])
        print(json.dumps(out, indent=1))
        sys.exit(1 if out["problems"] else 0)
    a, i, groups, snap, plan, baseline = sys.argv[2:], 0, [], None, None, None
    while i < len(a):
        if a[i] == "--snapshot":
            snap = json.loads(Path(a[i + 1]).read_text())["dirs"]
        elif a[i] == "--baseline":
            baseline = json.loads(Path(a[i + 1]).read_text())["dirs"]
        elif a[i] == "--plan":
            plan = a[i + 1]
        elif a[i] == "--run":
            rec = json.loads(Path(a[i + 1]).read_text())
            trailers = rec["args"].get("trailers", [])
            plan = plan or (rec["args"].get("plan") or {}).get("path")
            groups += [{**g, "trailers": trailers} for g in rec.get("result", {}).get("groups", [])]
        elif a[i] == "--group":
            groups.append(json.loads(a[i + 1]))
        else:
            sys.exit(f"unknown argument {a[i]}")
        i += 2
    if snap is None:
        sys.exit("check needs --snapshot")
    for g in groups:
        g["workdir"] = str(Path(g["workdir"]).resolve())
    results = [check_group(g, snap.get(g["workdir"], {}), plan, (baseline or {}).get(g["workdir"])) for g in groups]
    mine = {g["workdir"] for g in groups}
    others, books = [], {}
    for d, s in snap.items():
        if d in mine:
            continue
        now = {"head": git(d, "rev-parse", "HEAD").stdout.strip(), "dirty": dirty(d)}
        if now["head"] != s["head"] and now["dirty"] == s["dirty"]:
            b = only_bookkeeping(d, s["head"], plan)  # the parent's own commit in the plan's repo, after the run
            if b is not None:
                books[d] = b
                continue
        if now["head"] != s["head"] or now["dirty"] != s["dirty"]:
            others.append(f"{d} changed during the run, but no group was dispatched there")
    ok = not others and all(not r["problems"] for r in results)
    scope = others + [f"{r['workdir']}: {r['problems'][0]}" for r in results if r["scope"]]
    print(json.dumps({"ok": ok, "groups": results, "others": others, "bookkeeping": books, "scope": scope}, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
