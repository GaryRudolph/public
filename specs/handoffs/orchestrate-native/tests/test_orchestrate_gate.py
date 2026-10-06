#!/usr/bin/env python3
"""Tests for the orchestrate_gate.py PreToolUse hook. Usage: test_orchestrate_gate.py <scripts-dir>"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

scripts = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(scripts))
from plan_state import state  # noqa: E402

tmp = Path(tempfile.mkdtemp())
# The plan sits in a task-branch clone's specs/handoffs/, with a bare origin, so rule 9 can check commits and pushes.
repo, origin = tmp / "repo", tmp / "origin.git"


def git(*a, cwd=None):
    return subprocess.run(["git", *a], cwd=cwd or repo, capture_output=True, text=True, check=True).stdout.strip()


subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
subprocess.run(["git", "init", "-q", "-b", "feature/x", str(repo)], check=True)
for k, v in (("user.email", "t@example.com"), ("user.name", "t"), ("commit.gpgsign", "false")):
    git("config", k, v)
git("remote", "add", "origin", str(origin))
(repo / "specs" / "handoffs").mkdir(parents=True)
plan = repo / "specs" / "handoffs" / "plan-x.md"
handoff = plan.with_name("handoff-x.md")
COST = "\n**Cost (API-equiv, Claude Code models)**\n\n| wave | expected tokens | expected $ |\n|---|---|---|\n| 1 [exec] m1 s1 | ~1.6M | ~$0.9 |\n| **Total** | ~3M | ~$2.0 |\n\n"


def kickoff_prompt(mode):
    """The Kickoff prompt to paste into the next chat, carrying the confirmed mode (plan-execution.md "Kickoff template")."""
    return ["Read specs/handoffs/plan-x.md. The plan is already tagged.",
            "On branch feature/x (task branch): subagents commit each finished step.",
            f"Run in {mode} mode.",
            "Run the personal-plan-orchestrate skill from the top and follow its procedure."]


def write_plan(mode="gated | proposed gated (no runner signal) | guard 2x | fixups 2 | confirmed 2026-10-06 session s: gated",
               save=True, log="", prompt=None):
    """Write the plan and its handoff; with save, commit both in one commit and push, as each wave's bookkeeping does."""
    paste = "".join(f"      {line}\n" for line in prompt) if prompt else ""
    plan.write_text("```\n--- KICKOFF: begin orchestration at [deep] ---\n  Status: 0/1 groups done | updated 2026-10-06\n"
                    f"  mode: {mode}\n" + (f"\n    Prompt to paste into the next chat:\n{paste}\n---\n" if prompt else "")
                    + "```\n" + COST + "## m1 - A\n--- WAVE 1 [exec] ---\n#### m1.s1 - [exec] One\n"
                    + (f"\n## Review log\n\n{log}" if log else ""))
    handoff.write_text(f"# Handoff plan-x\n\nmode: {mode}\nNext: wave 1\n{log}")
    if save:
        git("add", str(plan), str(handoff))
        if git("status", "--porcelain"):
            git("commit", "-q", "-m", "update plan-x and its handoff")
        git("push", "-q", "-u", "origin", "feature/x")
    return state(plan.read_text())


ST = write_plan()
UN = "unattended | proposed unattended (CLAUDE_CODE_REMOTE=true) | guard 2x | fixups 2 | confirmed 2026-10-06 session s: "


def human(text):
    return {"type": "user", "promptSource": "sdk", "message": {"role": "user", "content": text}}


def said(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


QUESTION = said("Plan plan-x: 1 wave, ~$2.0 API-equiv. Runner detected (CLAUDE_CODE_REMOTE=true). Proposed mode: unattended. Reply unattended or gated.")


NOTIFY = {"type": "user", "origin": {"kind": "task-notification"}, "promptSource": "system",
          "turnOrigin": "task_notification", "message": {"role": "user", "content": "<task-notification>done</task-notification>"}}


def launch(args, tid):
    return [{"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": "Workflow",
                                                           "input": {"name": "personal:plan-segment", "args": args}}]}},
            {"type": "user", "toolUseResult": {"status": "async_launched", "runId": "wf_1"},
             "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": "launched"}]}}]


def record(rid, status="completed", stop="done", gates=(), groups=()):
    d = tmp / "t" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{rid}.json").write_text(json.dumps({"runId": rid, "status": status,
                                              "result": {"stop": stop, "gates": list(gates), "groups": list(groups)}}))


def hook(tool_input, transcript, records=(), runner=False):
    """Run the hook as Claude Code would; runner sets CLAUDE_CODE_REMOTE=true, which a workstation leaves unset."""
    shutil.rmtree(tmp / "t", ignore_errors=True)
    for r in records:
        record(**r)
    t = tmp / "t.jsonl"
    t.write_text("".join(json.dumps(r) + "\n" for r in transcript))
    inp = {"session_id": "s", "transcript_path": str(t), "hook_event_name": "PreToolUse", "tool_name": "Workflow",
           "tool_input": tool_input}
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_REMOTE"}
    env["GIT_CEILING_DIRECTORIES"] = str(tmp.resolve())  # a folder in tmp that isn't a clone is in no git repo
    if runner:
        env["CLAUDE_CODE_REMOTE"] = "true"
    out = subprocess.run([sys.executable, "-I", str(scripts / "orchestrate_gate.py")], input=json.dumps(inp),
                         capture_output=True, text=True, env=env)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)["hookSpecificOutput"]["permissionDecisionReason"] if out.stdout.strip() else None


def args(**kw):
    return {"plugin": "personal", "plan": {"name": "plan-x", "path": str(plan)}, "state": ST, "canaryDone": False,
            "approved": [], "approval": "", **kw}


def seg(a):
    return {"name": "personal:plan-segment", "args": a}


cases = []


def case(fn):
    cases.append(fn)
    return fn


@case
def other_workflows_are_left_alone():
    assert hook({"name": "deep-research", "args": {"q": "x"}}, [human("go")]) is None


@case
def plan_segment_by_script_path_is_denied():
    assert "by name" in hook({"scriptPath": "/x/plan-segment.js", "args": args()}, [human("go")])


@case
def an_honest_canary_launch_passes():
    assert hook(seg(args()), [human("orchestrate the plan")]) is None


@case
def a_state_that_differs_from_disk_is_denied():
    bad = json.loads(json.dumps(ST))
    bad["gates"] = []
    bad["next"]["steps"] = []
    assert "differs" in hook(seg(args(state=bad)), [human("go")])


@case
def approvals_from_a_notification_turn_are_denied():
    a = args(approved=[{"gate": "gate-5", "wave": 1}], approval="yes", canaryDone=True)
    t = [human("orchestrate")] + launch(args(), "t1") + [human("yes"), NOTIFY]
    assert "human answer started" in hook(seg(a), t, [{"rid": "wf_1", "stop": "gate", "gates": ["gate-5"]}])


@case
def approvals_must_be_the_human_answer_verbatim():
    a = args(approved=[{"gate": "gate-5", "wave": 1}], approval="yes", canaryDone=True)
    t = [human("orchestrate")] + launch(args(), "t1")
    canary = [{"rid": "wf_1", "stop": "gate", "gates": ["gate-5"]}]
    assert "verbatim" in hook(seg(a), t + [human("yes, but skip repo-b")], canary)
    assert hook(seg(a), t + [human("  yes ")], canary) is None


@case
def canary_done_needs_an_earlier_canary_launch():
    assert "canary" in hook(seg(args(canaryDone=True)), [human("go")])
    denied_launch = launch(args(), "t1")[:1]  # a tool_use with no launched result
    assert "canary" in hook(seg(args(canaryDone=True)), [human("go")] + denied_launch)
    assert hook(seg(args(canaryDone=True)), [human("go")] + launch(args(), "t1") + [NOTIFY], [{"rid": "wf_1"}]) is None


@case
def no_launch_while_an_earlier_run_is_unfinished():
    t = [human("go")] + launch(args(), "t1")
    assert "not finished" in hook(seg(args(canaryDone=True)), t)
    assert "not finished" in hook(seg(args(canaryDone=True)), t, [{"rid": "wf_1", "status": "running"}])


@case
def a_gate_stop_must_be_answered_by_the_next_launch():
    t = [human("go")] + launch(args(), "t1") + [NOTIFY]
    stopped = [{"rid": "wf_1", "stop": "gate", "gates": ["gate-1"]}]
    assert "stopped at gate-1" in hook(seg(args(canaryDone=True)), t, stopped)
    a = args(canaryDone=True, approved=[{"gate": "gate-1", "wave": 1}], approval="retry it")
    assert hook(seg(a), t + [human("retry it")], stopped) is None
    assert hook(seg(args(canaryDone=True)), t, [{"rid": "wf_1", "stop": "gate", "gates": ["gate-0"]}]) is None


@case
def a_hook_error_fails_closed():
    a = args()
    a["plan"]["path"] = str(tmp / "missing.md")
    assert "hook error" in hook(seg(a), [human("go")])


# ---- v3: unattended mode and the cost guard ----

@case
def a_confirmed_unattended_mode_passes():
    st = write_plan(UN + "unattended")
    assert hook(seg(args(state=st)), [human("orchestrate plan-x"), QUESTION, human("unattended")]) is None
    st = write_plan(UN + "orchestrate plan-x unattended")
    assert hook(seg(args(state=st)), [human("orchestrate plan-x unattended")]) is None
    write_plan()


@case
def an_unattended_record_with_no_matching_human_turn_is_denied():
    st = write_plan(UN + "unattended")
    assert "verbatim" in hook(seg(args(state=st)), [human("orchestrate plan-x"), QUESTION, human("go ahead")])
    write_plan()


@case
def an_unattended_answer_from_a_notification_turn_is_denied():
    st = write_plan(UN + "<task-notification>done</task-notification>")
    assert "verbatim" in hook(seg(args(state=st)), [human("orchestrate"), QUESTION, NOTIFY])
    write_plan()


@case
def a_bare_yes_re_asks_even_when_the_question_proposed_unattended():
    st = write_plan(UN + "yes")  # v6: the kit matches decision 9 as proposed, until Gary decides it
    gated_q = said("Plan plan-x: no runner signal. Proposed mode: gated. Reply gated or unattended.")
    for q in (QUESTION, gated_q):
        assert "does not name unattended" in hook(seg(args(state=st)), [human("orchestrate"), q, human("yes")])
    st = write_plan(UN + "unattended, not gated")
    assert "does not name unattended" in hook(seg(args(state=st)), [human("orchestrate"), QUESTION, human("unattended, not gated")])
    write_plan()


@case
def a_confirmation_from_another_session_is_denied():
    st = write_plan(UN.replace("session s:", "session old-1:") + "unattended")
    assert "not this one" in hook(seg(args(state=st)), [human("orchestrate"), QUESTION, human("unattended")])
    write_plan()


@case
def a_later_human_turn_naming_gated_voids_unattended():
    st = write_plan(UN + "unattended")
    t = [human("orchestrate"), QUESTION, human("unattended"), said("Running."), human("switch to gated please")]
    assert "names gated" in hook(seg(args(state=st)), t)
    write_plan()


@case
def a_raised_cost_guard_needs_a_human_approval():
    st2 = write_plan(UN + "unattended")
    t = [human("orchestrate"), QUESTION, human("unattended")] + launch(args(state=st2), "t1") + [NOTIFY]
    done = [{"rid": "wf_1"}]
    st3 = write_plan(UN.replace("guard 2x", "guard 3x") + "unattended")
    assert "cost guard rose" in hook(seg(args(state=st3, canaryDone=True)), t, done)
    ok = args(state=st3, canaryDone=True, approved=[{"gate": "gate-guard", "wave": 1}], approval="yes, keep going")
    assert hook(seg(ok), t + [human("yes, keep going")], done) is None
    write_plan()


# ---- v4: the committed handoff (rule 9) and the fix-up cap (rule 8) ----

KICK = [human("orchestrate plan-x"), QUESTION, human("unattended")]


GATED = "gated | proposed gated (no runner signal) | guard 2x | fixups 2 | confirmed 2026-10-06 session s: gated"
TASK = [{"workdir": str(repo), "branch": "feature/x"}]


def refreshed_handoff_sequence(mode):
    """Rule 9 in one mode: the plan and a refreshed handoff, committed and pushed, before every launch with a task-branch group."""
    st = write_plan(mode)
    assert hook(seg(args(state=st, groups=TASK)), KICK) is None
    st = write_plan(mode, save=False)
    plan.write_text(plan.read_text() + "\n")  # an uncommitted plan edit
    st = state(plan.read_text())
    assert "uncommitted" in hook(seg(args(state=st, groups=TASK)), KICK)
    assert "uncommitted" in hook(seg(args(state=st)), KICK)  # no groups: fail closed
    git("add", str(plan))
    git("commit", "-q", "-m", "update plan-x only")
    git("push", "-q")
    assert "after the handoff was last committed" in hook(seg(args(state=st, groups=TASK)), KICK)
    handoff.write_text(handoff.read_text() + "Done: wave 1\n")
    git("add", str(plan), str(handoff))
    git("commit", "-q", "-m", "update plan-x and its handoff")
    assert "not pushed" in hook(seg(args(state=st, groups=TASK)), KICK)
    git("push", "-q")
    assert hook(seg(args(state=st, groups=TASK)), KICK) is None
    write_plan()


def handoff_file_and_folder(mode):
    st = write_plan(mode)
    handoff.rename(tmp / "gone.md")
    assert "no session handoff" in hook(seg(args(state=st, groups=TASK)), KICK)
    (tmp / "gone.md").rename(handoff)
    elsewhere = repo / ".scratch" / "plan-x.md"  # in the clone, outside specs/handoffs/
    elsewhere.parent.mkdir(exist_ok=True)
    elsewhere.write_text(plan.read_text())
    a = args(state=st, groups=TASK)
    a["plan"]["path"] = str(elsewhere)
    assert "specs/handoffs" in hook(seg(a), KICK)
    shutil.rmtree(elsewhere.parent)
    write_plan()


@case
def unattended_needs_a_refreshed_handoff_committed_and_pushed():
    refreshed_handoff_sequence(UN + "unattended")


@case
def unattended_needs_the_handoff_file_and_the_specs_handoffs_folder():
    handoff_file_and_folder(UN + "unattended")


# ---- v5: the per-wave handoff in both modes ----

def init_repo(d, remote=None, branch="feature/x"):
    """A clone on branch; with remote, a bare origin to push to, and none without."""
    subprocess.run(["git", "init", "-q", "-b", branch, str(d)], check=True)
    for k, v in (("user.email", "t@example.com"), ("user.name", "t"), ("commit.gpgsign", "false")):
        git("config", k, v, cwd=d)
    if remote:
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git("remote", "add", "origin", str(remote), cwd=d)


@case
def gated_on_a_task_branch_needs_a_refreshed_handoff_committed_and_pushed():
    refreshed_handoff_sequence(GATED)


@case
def gated_on_a_task_branch_needs_the_handoff_file_and_the_specs_handoffs_folder():
    handoff_file_and_folder(GATED)


@case
def a_raised_fix_up_cap_needs_a_human_approval_of_gate_1():
    st2 = write_plan(UN + "unattended")
    t = KICK + launch(args(state=st2), "t1") + [NOTIFY]
    done = [{"rid": "wf_1"}]
    st3 = write_plan(UN.replace("fixups 2", "fixups 4") + "unattended")
    assert "fix-up cap rose from 2 to 4" in hook(seg(args(state=st3, canaryDone=True)), t, done)
    ok = args(state=st3, canaryDone=True, approved=[{"gate": "gate-1", "wave": 1}], approval="yes, allow four")
    assert hook(seg(ok), t + [human("yes, allow four")], done) is None
    write_plan()


@case
def every_task_branch_workdir_of_the_last_run_is_pushed_in_both_modes():
    st2 = write_plan(UN + "unattended")
    t = KICK + launch(args(state=st2), "t1") + [NOTIFY]
    rb, ob = tmp / "repo-b", tmp / "origin-b.git"
    subprocess.run(["git", "init", "-q", "--bare", str(ob)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "feature/x", str(rb)], check=True)
    for k, v in (("user.email", "t@example.com"), ("user.name", "t"), ("commit.gpgsign", "false")):
        git("config", k, v, cwd=rb)
    git("remote", "add", "origin", str(ob), cwd=rb)
    (rb / "b.txt").write_text("b\n")
    git("add", "-A", cwd=rb)
    git("commit", "-q", "-m", "m1.s2 Add b", cwd=rb)
    git("push", "-q", "-u", "origin", "feature/x", cwd=rb)
    ran = [{"rid": "wf_1", "groups": [{"workdir": str(rb), "branch": "feature/x"}]}]
    assert hook(seg(args(state=st2, canaryDone=True)), t, ran) is None
    (rb / "c.txt").write_text("c\n")
    git("add", "-A", cwd=rb)
    git("commit", "-q", "-m", "m1.s3 Add c", cwd=rb)
    assert "repo-b has commits that are not pushed" in hook(seg(args(state=st2, canaryDone=True)), t, ran)
    gated = write_plan()
    gt = [human("go")] + launch(args(state=gated), "t1") + [NOTIFY]
    assert "repo-b has commits that are not pushed" in hook(seg(args(state=gated, canaryDone=True)), gt, ran)  # v5: both modes
    git("push", "-q", cwd=rb)
    assert hook(seg(args(state=gated, canaryDone=True)), gt, ran) is None


@case
def gated_on_a_workstation_checks_no_push_where_there_is_no_remote():
    st = write_plan(GATED)
    text = plan.read_text()
    go = [human("orchestrate plan-x")]

    def at(p, groups, s=st):
        a = args(state=s, groups=groups)
        a["plan"]["path"] = str(p)
        return seg(a)
    # A plain folder of sibling repos: the cross-repo plan is in the non-git parent's .scratch/, the wave in a clone.
    loose = tmp / "plain" / ".scratch" / "plan-x.md"
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_text(text)
    loose.with_name("handoff-x.md").write_text("# Handoff plan-x\n")
    assert hook(at(loose, TASK), go) is None
    assert "specs/handoffs" in hook(at(loose, TASK), go, runner=True)  # a runner's .scratch/ dies with it
    loose.write_text(text.replace(f"mode: {GATED}", f"mode: {UN}unattended"))
    assert "unattended needs the plan in a git repo with a remote" in hook(at(loose, TASK, state(loose.read_text())), KICK)
    # A local-only clone: the plan and handoff are still committed in specs/handoffs/, and nothing is pushed.
    rc = tmp / "repo-c"
    init_repo(rc)
    pc = rc / "specs" / "handoffs" / "plan-x.md"
    pc.parent.mkdir(parents=True)
    pc.write_text(text)
    pc.with_name("handoff-x.md").write_text("# Handoff plan-x\n")
    cg = [{"workdir": str(rc), "branch": "feature/x"}]
    assert "uncommitted" in hook(at(pc, cg), go)
    git("add", "-A", cwd=rc)
    git("commit", "-q", "-m", "update plan-x and its handoff", cwd=rc)
    assert hook(at(pc, cg), go) is None
    ran = go + launch(args(state=st), "t1") + [NOTIFY]
    assert hook(at(pc, cg), ran, [{"rid": "wf_1", "groups": cg}]) is None  # the last run's clone has nowhere to push
    assert "not pushed" in hook(at(pc, cg), go, runner=True)
    pc.write_text(text.replace(f"mode: {GATED}", f"mode: {UN}unattended"))
    git("commit", "-q", "-am", "update plan-x", cwd=rc)
    assert "unattended needs the plan in a git repo with a remote" in hook(at(pc, cg, state(pc.read_text())), KICK)


@case
def a_new_waiver_must_be_a_human_message_verbatim():
    st2 = write_plan(UN + "unattended")
    t = KICK + launch(args(state=st2), "t1") + [NOTIFY]
    done = [{"rid": "wf_1"}]
    st3 = write_plan(UN + "unattended", log="review wave-1 (repo m1 s1) 1111111..2222222: WAIVED - skip that fix, it's fine - 2026-10-06\n")
    assert st3["waivers"] and "WAIVED line for wave 1" in hook(seg(args(state=st3, canaryDone=True)), t, done)
    assert hook(seg(args(state=st3, canaryDone=True)), t + [human("skip that fix, it's fine")], done) is None
    later = t + [human("skip that fix, it's fine")] + launch(args(state=st3, canaryDone=True), "t2") + [NOTIFY]
    assert hook(seg(args(state=st3, canaryDone=True)), later, [{"rid": "wf_1"}]) is None  # an older waiver isn't re-checked
    write_plan()


# ---- v6: always a task branch; the Kickoff prompt carries the confirmed mode ----

@case
def every_group_runs_on_its_task_branch_on_every_machine():
    st = write_plan(GATED)
    go = [human("orchestrate plan-x")]
    for runner in (False, True):
        assert hook(seg(args(state=st, groups=TASK)), go, runner=runner) is None
    ws, ows = tmp / "ws6", tmp / "origin-ws6.git"
    init_repo(ws, ows, branch="trunk")
    (ws / "a.txt").write_text("a\n")
    git("add", "-A", cwd=ws)
    git("commit", "-q", "-m", "init", cwd=ws)
    git("push", "-q", "-u", "origin", "trunk", cwd=ws)
    git("remote", "set-head", "origin", "trunk", cwd=ws)  # trunk is the remote's default branch
    on = lambda b: [{"workdir": str(ws), "branch": b}]  # noqa: E731
    for runner in (False, True):
        assert "trunk in" in hook(seg(args(state=st, groups=on("trunk"))), go, runner=runner)
    git("switch", "-q", "-c", "main", "--no-track", cwd=ws)
    assert "main in" in hook(seg(args(state=st, groups=on("main"))), go)
    held = ws / "specs" / "handoffs" / "plan-x.md"  # the repo that holds the plan is on a shared branch too
    held.parent.mkdir(parents=True)
    held.write_text(plan.read_text())
    a = args(state=st, groups=TASK)
    a["plan"]["path"] = str(held)
    assert "main in" in hook(seg(a), go)
    shutil.rmtree(ws / "specs")
    git("switch", "-q", "-c", "release/v2", "--no-track", cwd=ws)
    assert "release/v2 in" in hook(seg(args(state=st, groups=on("release/v2"))), go)
    git("switch", "-q", "-c", "feature/y", "--no-track", cwd=ws)
    assert "not the group's branch feature/x" in hook(seg(args(state=st, groups=on("feature/x"))), go)
    assert "not the group's branch (none given)" in hook(seg(args(state=st, groups=[{"workdir": str(ws)}])), go)
    assert hook(seg(args(state=st, groups=TASK + on("feature/y"))), go) is None
    git("switch", "-q", "--detach", cwd=ws)
    assert "no branch checked out" in hook(seg(args(state=st, groups=on("feature/y"))), go)
    loose = repo / ".scratch" / "plan-x.md"  # v5's gated shared-branch launch kept its plan here; v6 denies it
    loose.parent.mkdir(exist_ok=True)
    loose.write_text(plan.read_text())
    a = args(state=st, groups=TASK)
    a["plan"]["path"] = str(loose)
    assert "specs/handoffs" in hook(seg(a), go)
    shutil.rmtree(loose.parent)
    write_plan()


PROMPTED = "unattended | proposed unattended (CLAUDE_CODE_REMOTE=true) | guard 2x | fixups 2 | confirmed 2026-10-07 session s by Kickoff prompt: Run in unattended mode."


def paste(mode="unattended", indent="  "):
    """Gary pasting the Kickoff prompt as his first message in a new session, indented as the chat printed it."""
    return human("\n".join(indent + line for line in kickoff_prompt(mode)) + "\n")


@case
def a_pasted_kickoff_prompt_confirms_unattended_in_the_new_session():
    st = write_plan(PROMPTED, prompt=kickoff_prompt("unattended"))
    assert st["errors"] == [] and st["mode"]["via"] == "prompt" and st["prompt_mode"] == "unattended", st
    assert hook(seg(args(state=st, groups=TASK)), [paste()], runner=True) is None
    assert hook(seg(args(state=st, groups=TASK)), [paste(indent="")], runner=True) is None
    gone = [paste(), said("Running."), human("gated")]
    assert "names gated" in hook(seg(args(state=st, groups=TASK)), gone, runner=True)
    write_plan()


@case
def a_casual_mention_of_the_mode_is_not_a_pasted_kickoff_prompt():
    st = write_plan(PROMPTED, prompt=kickoff_prompt("unattended"))
    for text in ("Run in unattended mode.", "run unattended", "orchestrate plan-x. Run in unattended mode.",
                 "\n".join(kickoff_prompt("unattended")) + "\nand skip the canary"):
        assert "Kickoff prompt verbatim" in hook(seg(args(state=st, groups=TASK)), [human(text)], runner=True), text
    assert "Kickoff prompt verbatim" in hook(seg(args(state=st, groups=TASK)), [NOTIFY], runner=True)
    write_plan()


@case
def a_pasted_prompt_re_asks_when_the_environment_or_the_session_differs():
    st = write_plan(PROMPTED, prompt=kickoff_prompt("unattended"))
    assert "CLAUDE_CODE_REMOTE here is not true" in hook(seg(args(state=st, groups=TASK)), [paste()])  # pasted on a workstation
    old = write_plan(PROMPTED.replace("session s by", "session old-1 by"), prompt=kickoff_prompt("unattended"))
    assert "not this one" in hook(seg(args(state=old, groups=TASK)), [paste()], runner=True)
    ws = write_plan(PROMPTED.replace("proposed unattended (CLAUDE_CODE_REMOTE=true)", "proposed gated (no runner signal)"),
                    prompt=kickoff_prompt("unattended"))
    assert "CLAUDE_CODE_REMOTE here is true" in hook(seg(args(state=ws, groups=TASK)), [paste()], runner=True)
    write_plan()


@case
def a_prompt_confirmation_needs_the_prompts_own_mode_line():
    st = write_plan(PROMPTED.replace("Run in unattended mode.", "unattended"), prompt=kickoff_prompt("unattended"))
    assert "records its mode line" in hook(seg(args(state=st, groups=TASK)), [paste()], runner=True)
    st = write_plan(PROMPTED, prompt=kickoff_prompt("gated"))  # the plan's prompt says gated: plan_state reports gate 0
    assert st["errors"] and "records its mode line" in hook(seg(args(state=st, groups=TASK)), [paste("gated")], runner=True)
    st = write_plan(GATED.replace("session s: gated", "session s by Kickoff prompt: Run in gated mode."), prompt=kickoff_prompt("gated"))
    assert st["errors"] == [] and hook(seg(args(state=st, groups=TASK)), [human("go")]) is None  # gated needs no proof
    write_plan()


failed = 0
for fn in cases:
    try:
        fn()
        print(f"ok   {fn.__name__}")
    except Exception as e:  # a None reason in an "in" check is a failure too, not a crash of the suite
        failed += 1
        print(f"FAIL {fn.__name__}: {type(e).__name__} {e}")
print(f"{len(cases) - failed}/{len(cases)} passed")
sys.exit(1 if failed else 0)
