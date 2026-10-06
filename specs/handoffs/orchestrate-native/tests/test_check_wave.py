#!/usr/bin/env python3
"""Tests for check_wave.py against throwaway git repos. Usage: test_check_wave.py <scripts-dir>"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

tool = Path(sys.argv[1]).resolve() / "check_wave.py"
tmp = Path(tempfile.mkdtemp())


def sh(d, *a):
    return subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True, text=True).stdout.strip()


def repo(name):
    d = tmp / name
    d.mkdir()
    sh(d, "init", "-q", "-b", "main")
    sh(d, "config", "user.email", "t@example.com")
    sh(d, "config", "user.name", "T")
    (d / ".gitignore").write_text(".scratch/\n")
    sh(d, "add", "-A")
    sh(d, "commit", "-q", "-m", "init")
    return d


def commit(d, path, msg):
    (d / path).write_text(path + "\n")
    sh(d, "add", path)
    sh(d, "commit", "-q", "-m", msg)


def run(*a):
    r = subprocess.run([sys.executable, "-I", str(tool), *map(str, a)], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)


def group(d, steps, frm, git="task"):
    return json.dumps({"id": f"{d.name} x", "workdir": str(d), "steps": steps, "from": frm, "git": git,
                       "trailers": ["Assisted-by: Claude Code"]})


GOOD = "m1.s1 Add one\n\nBody.\n\nAssisted-by: Claude Code\nClaude-Session: https://example.com/s"
a, b, idle = repo("a"), repo("b"), repo("idle")
code, snap = run("snapshot", a, b, idle)
assert code == 0, snap
(tmp / "snap.json").write_text(json.dumps(snap))
base_a, base_b = sh(a, "rev-parse", "HEAD"), sh(b, "rev-parse", "HEAD")
commit(a, "one.txt", GOOD)
commit(b, "two.txt", "m1.s2 Add two Co-Authored-By: Claude <noreply@anthropic.com>")
cases = []

code, out = run("check", "--snapshot", tmp / "snap.json", "--group", group(a, ["m1.s1"], base_a), "--group", group(b, ["m1.s2"], base_b))
ga, gb = out["groups"]
cases.append(("a good commit passes and reports its HEAD", not ga["problems"] and ga["to"] == sh(a, "rev-parse", "--short", "HEAD") and not out["others"]))
p = " ".join(gb["problems"])
cases.append(("a co-author trailer on the subject line fails", code == 1 and "Co-authored-by" in p and "lacks" in p))
code, out = run("check", "--snapshot", tmp / "snap.json", "--group", group(a, ["m1.s1", "m1.s3"], base_a), "--group", group(b, ["m1.s2"], base_b))
cases.append(("a step with no commit fails", code == 1 and "m1.s3 has no commit" in " ".join(out["groups"][0]["problems"])))
code, out = run("check", "--snapshot", tmp / "snap.json", "--group", group(a, ["m1.s9"], base_a), "--group", group(b, ["m1.s2"], base_b))
cases.append(("a commit for another step fails (a stale from)", code == 1 and "does not start with one of m1.s9" in " ".join(out["groups"][0]["problems"])))
code, out = run("check", "--snapshot", tmp / "snap.json", "--group", group(a, ["m1.s1"], base_a, git="shared"), "--group", group(b, ["m1.s2"], base_b))
cases.append(("a commit on a shared branch fails", code == 1))
(a / "stray.txt").write_text("x")
code, out = run("check", "--snapshot", tmp / "snap.json", "--group", group(a, ["m1.s1"], base_a), "--group", group(b, ["m1.s2"], base_b))
cases.append(("a new uncommitted path fails", code == 1 and "stray.txt" in " ".join(out["groups"][0]["problems"])))
(a / "stray.txt").unlink()
(idle / "edit.txt").write_text("x")
code, out = run("check", "--snapshot", tmp / "snap.json", "--group", group(a, ["m1.s1"], base_a), "--group", group(b, ["m1.s2"], base_b))
cases.append(("an edit in a directory with no group fails", code == 1 and out["others"]))
nog = repo("noignore")
(nog / ".gitignore").write_text("")
code, out = run("snapshot", nog)
cases.append(("snapshot flags a .scratch/ that is not ignored", code == 1 and out["problems"]))

sh_ = repo("shared")
(sh_ / "mine.txt").write_text("Gary's own edit\n")
code, snap2 = run("snapshot", sh_)
(sh_ / "wave.txt").write_text("from the wave\n")
diff = subprocess.run([sys.executable, "-I", str(tool), "diff", str(sh_), snap2["dirs"][str(sh_.resolve())]["tree"]], capture_output=True, text=True).stdout
cases.append(("a shared-branch diff shows only the wave's new file", "wave.txt" in diff and "mine.txt" not in diff and not sh(sh_, "diff", "--cached", "--name-only")))

# ---- v4: fix-ups in the repo that holds a tracked plan, and a leftover path checked again ----

T = "\n\nAssisted-by: Claude Code"
pr = repo("planrepo")
(pr / "specs" / "handoffs").mkdir(parents=True)
plan_p, hand_p = pr / "specs/handoffs/plan-x.md", pr / "specs/handoffs/handoff-x.md"
plan_p.write_text("plan\n")
hand_p.write_text("handoff\n")
sh(pr, "add", "-A")
sh(pr, "commit", "-q", "-m", "start plan-x")
frm = sh(pr, "rev-parse", "--short", "HEAD")
commit(pr, "a.txt", "m1.s4 Add a" + T)                       # wave 2 leaves m1.s5 without a commit
plan_p.write_text("plan\nreview wave-2 ...: CONCERNS - check_wave.py: step m1.s5 has no commit\n")
hand_p.write_text("handoff\nnext: 2-fix\n")
sh(pr, "add", "specs")
sh(pr, "commit", "-q", "-m", "update plan-x and its handoff after wave 2" + T)
book = sh(pr, "rev-parse", "--short=7", "HEAD")
code, snap3 = run("snapshot", pr)
(tmp / "snap3.json").write_text(json.dumps(snap3))
commit(pr, "b.txt", "m1.s5 Add b" + T)                       # the fix-up, exactly as told
fix = json.dumps({"id": "planrepo m1 s4-s5", "workdir": str(pr), "steps": ["m1.s4", "m1.s5"], "from": frm, "git": "task"})
rec = tmp / "run-fix.json"
rec.write_text(json.dumps({"args": {"plan": {"name": "plan-x", "path": str(plan_p)}, "trailers": ["Assisted-by: Claude Code"]},
                           "result": {"groups": [json.loads(fix)]}}))
code, out = run("check", "--snapshot", tmp / "snap3.json", "--run", rec)
g = out["groups"][0]
cases.append(("a fix-up range that spans the parent's plan and handoff commit passes", code == 0 and g["bookkeeping"] == [book] and not g["problems"]))
code, out = run("check", "--snapshot", tmp / "snap3.json", "--group", json.dumps({**json.loads(fix), "trailers": ["Assisted-by: Claude Code"]}))
cases.append(("without the plan path, that commit fails the subject check", code == 1 and book in " ".join(out["groups"][0]["problems"])))
plan_p.write_text("plan, edited by a worker\n")
commit(pr, "c.txt", "m1.s5 Add c")
sh(pr, "add", "specs")
sh(pr, "commit", "-q", "--amend", "-m", "m1.s5 Add c" + T)    # a step commit that also edits the plan
code, out = run("check", "--snapshot", tmp / "snap3.json", "--run", rec)
cases.append(("a step commit that also edits the plan fails", code == 1 and "touches the plan" in " ".join(out["groups"][0]["problems"])))
sh(pr, "reset", "-q", "--hard", "HEAD~2")
sh(pr, "commit", "-q", "--amend", "-m", "m1.s4 Add a" + T)    # a message fix-up that amended the bookkeeping commit
code, out = run("check", "--snapshot", tmp / "snap3.json", "--run", rec)
cases.append(("a step subject on a plan-only commit fails", code == 1 and "touches the plan" in " ".join(out["groups"][0]["problems"])))

lo = repo("leftover")
code, s0 = run("snapshot", lo)                                # before wave 2
(tmp / "s0.json").write_text(json.dumps(s0))
lo_from = sh(lo, "rev-parse", "--short", "HEAD")
commit(lo, "a.txt", "m1.s4 Add a" + T)
(lo / "out.log").write_text("junk\n")                        # wave 2 leaves a build output behind
lg = json.dumps({"id": "leftover m1 s4", "workdir": str(lo), "steps": ["m1.s4"], "from": lo_from, "git": "task", "trailers": ["Assisted-by: Claude Code"]})
code, s1 = run("snapshot", lo)                                # the fresh snapshot before the fix-up
(tmp / "s1.json").write_text(json.dumps(s1))
code, out = run("check", "--snapshot", tmp / "s1.json", "--group", lg)
cases.append(("without a baseline, a fix-up that did nothing hides the leftover path", code == 0))
code, out = run("check", "--snapshot", tmp / "s1.json", "--baseline", tmp / "s0.json", "--group", lg)
cases.append(("with the fixed wave's snapshot as baseline, the leftover path still fails", code == 1 and "out.log" in " ".join(out["groups"][0]["problems"])))
(lo / "out.log").unlink()
code, out = run("check", "--snapshot", tmp / "s1.json", "--baseline", tmp / "s0.json", "--group", lg)
cases.append(("once the fix-up removes it, the check passes", code == 0))

failed = [n for n, ok in cases if not ok]
for n, ok in cases:
    print(("ok   " if ok else "FAIL ") + n)
print(f"{len(cases) - len(failed)}/{len(cases)} passed")
sys.exit(1 if failed else 0)
