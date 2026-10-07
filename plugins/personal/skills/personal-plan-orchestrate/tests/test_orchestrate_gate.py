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


subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
for k, v in (("user.email", "t@example.com"), ("user.name", "t"), ("commit.gpgsign", "false")):
    git("config", k, v)
git("remote", "add", "origin", str(origin))
(repo / "README.md").write_text("x\n")
git("add", "-A")
git("commit", "-q", "-m", "init")
git("push", "-q", "-u", "origin", "main")
git("remote", "set-head", "origin", "--auto")  # origin/HEAD, as a clone records it; rule 9 denies without it
git("switch", "-q", "-c", "feature/x", "--no-track")
(repo / "specs" / "handoffs").mkdir(parents=True)
plan = repo / "specs" / "handoffs" / "plan-x.md"
handoff = plan.with_name("handoff-x.md")
COST = "\n**Cost (API-equiv, Claude Code models)**\n\n| wave | expected tokens | expected $ |\n|---|---|---|\n| 1 [exec] m1 s1 | ~1.6M | ~$0.9 |\n| **Total** | ~3M | ~$2.0 |\n\n"


def kickoff_prompt(mode):
    """The Kickoff prompt to paste into the next chat, carrying the confirmed mode (plan-execution.md "Kickoff template")."""
    return ["In example/repo, read specs/handoffs/plan-x.md. The plan is already tagged.",
            "On branch feature/x (task branch): subagents commit each finished step.",
            f"Run in {mode} mode.",
            "Run the personal-plan-orchestrate skill from the top and follow its procedure."]


def write_plan(mode="gated | proposed gated (harness=claude-code runner=none) | guard 2x | fixups 2 | confirmed 2026-10-06 session s: gated",
               save=True, log="", prompt=None, status="0/1 groups done | updated 2026-10-06"):
    """Write the plan and its handoff; with save, commit both in one commit and push, as each wave's bookkeeping does."""
    paste = "".join(f"      {line}\n" for line in prompt) if prompt else ""
    plan.write_text(f"```\n--- KICKOFF: begin orchestration at [deep] ---\n  Status: {status}\n"
                    f"  mode: {mode}\n" + (f"\n    Prompt to paste into the next chat:\n{paste}\n---\n" if prompt else "")
                    + "```\n" + COST + "## m1 - A\n--- WAVE 1 [exec] ---\n#### m1.s1 - [exec] One\n"
                    + (f"\n## Review log\n\n{log}" if log else ""))
    resume = " / ".join(prompt) if prompt else "none yet"
    handoff.write_text(f"# Handoff plan-x\n\nmode: {mode}\nStatus: {status}\nResume: {resume}\nNext: wave 1\n{log}")
    if save:
        git("add", str(plan), str(handoff))
        if git("status", "--porcelain"):
            git("commit", "-q", "-m", "update plan-x and its handoff")
        git("push", "-q", "-u", "origin", "feature/x")
    return state(plan.read_text())


ST = write_plan()
# Unattended, confirmed by an answer on a workstation (the hook's default environment): Gary overrode a gated proposal.
UN = "unattended | proposed gated (harness=claude-code runner=none) | guard 2x | fixups 2 | confirmed 2026-10-06 session s: "


def human(text):
    return {"type": "user", "promptSource": "sdk", "message": {"role": "user", "content": text}}


def said(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


QUESTION = said("Plan plan-x: 1 wave, ~$2.0 API-equiv. No runner signal (CLAUDE_CODE_REMOTE unset). Proposed mode: gated.\n"
                "main is a shared branch, so the run goes on a new task branch, feature/x. Reply gated or unattended.")


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


RUNNER_ENV = ("CLAUDE_CODE_REMOTE", "CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE", "CI", "GITHUB_ACTIONS")


def env_for(runner=False, ci=False):
    """The hook's environment: runner True is a cloud session, "self-hosted" a self-hosted runner; a workstation sets neither."""
    env = {k: v for k, v in os.environ.items() if k not in RUNNER_ENV}
    env["GIT_CEILING_DIRECTORIES"] = str(tmp.resolve())  # a folder in tmp that isn't a clone is in no git repo
    if runner:
        env["CLAUDE_CODE_REMOTE"] = "true"
        env["CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE"] = "self_hosted" if runner == "self-hosted" else "cloud_default"
    if ci:
        env["CI"] = "true"
    return env


def hook_input(tool_input, transcript, records=()):
    shutil.rmtree(tmp / "t", ignore_errors=True)
    for r in records:
        record(**r)
    t = tmp / "t.jsonl"
    t.write_text("".join(json.dumps(r) + "\n" for r in transcript))
    return json.dumps({"session_id": "s", "transcript_path": str(t), "hook_event_name": "PreToolUse", "tool_name": "Workflow",
                       "tool_input": tool_input})


def run(stdin, runner=False, ci=False, cmd=None):
    return subprocess.run(cmd or [sys.executable, "-I", str(scripts / "orchestrate_gate.py")], input=stdin,
                          capture_output=True, text=True, env=env_for(runner, ci))


def hook(tool_input, transcript, records=(), runner=False, ci=False):
    """Run the hook as Claude Code would; the reason it denies, or None. A deny exits 0, and a hook error exits 2."""
    out = run(hook_input(tool_input, transcript, records), runner, ci)
    assert out.returncode in (0, 2), out.stderr
    assert (out.returncode == 2) == ("hook error" in out.stdout), (out.returncode, out.stdout)
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


@case
def a_hook_that_cannot_decide_denies_with_exit_2():
    def denied(out, why):
        return out.returncode == 2 and why in out.stderr and "deny" in out.stdout
    out = run("not json")
    assert denied(out, "hook error (JSONDecodeError"), (out.returncode, out.stdout, out.stderr)
    alone = tmp / "alone"  # the hook without its plan_state.py, as after a half-updated install
    alone.mkdir(exist_ok=True)
    shutil.copy(scripts / "orchestrate_gate.py", alone)
    cmd = [sys.executable, "-I", str(alone / "orchestrate_gate.py")]
    out = run(hook_input(seg(args()), [human("go")]), cmd=cmd)
    assert denied(out, "ModuleNotFoundError"), (out.returncode, out.stderr)
    out = run(hook_input({"name": "deep-research", "args": {}}, [human("go")]), cmd=cmd)
    assert out.returncode == 0 and not out.stdout.strip()  # other workflows don't need plan_state.py
    stall = tmp / "stall.jsonl"  # a transcript that never opens: the hook's own deadline denies before Claude Code's timeout
    if not stall.exists():
        os.mkfifo(stall)
    inp = json.loads(hook_input(seg(args()), []))
    inp["transcript_path"] = str(stall)
    code = f"import sys; sys.path.insert(0, {str(scripts)!r}); import orchestrate_gate as g; g.DEADLINE = 1; g.main()"
    out = run(json.dumps(inp), cmd=[sys.executable, "-I", "-c", code])
    assert denied(out, "no decision within 1s"), (out.returncode, out.stderr)
    hooks = scripts.parents[2] / "hooks" / "claude-hooks.json"  # in the plugin layout
    if hooks.exists():  # the hooks file blocks with exit 2 when python3 won't start
        line = json.loads(hooks.read_text())["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        env = {"PATH": str(tmp / "no-bin"), "CLAUDE_PLUGIN_ROOT": str(scripts.parents[2])}
        out = subprocess.run(["/bin/sh", "-c", line], input="{}", capture_output=True, text=True, env=env)
        assert out.returncode == 2 and "fail closed" in out.stderr, (out.returncode, out.stderr)


# ---- v3: unattended mode and the cost guard ----

@case
def a_confirmed_unattended_mode_passes():
    st = write_plan(UN + "unattended")
    assert hook(seg(args(state=st)), [human("orchestrate plan-x"), QUESTION, human("unattended")]) is None
    st = write_plan(UN + "orchestrate plan-x unattended")  # an invoking message only proposes the mode (§1.5)
    assert "doesn't follow the kickoff question" in hook(seg(args(state=st)), [human("orchestrate plan-x unattended")])
    st = write_plan(UN.replace("runner=none", "runner=ci") + "orchestrate plan-x unattended")
    assert hook(seg(args(state=st)), [human("orchestrate plan-x unattended")], ci=True) is None  # in CI nobody can reply
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
    runner_q = said("Plan plan-x: runner detected (CLAUDE_CODE_REMOTE=true). Proposed mode: unattended. Reply unattended or gated.")
    for q in (QUESTION, runner_q):
        assert "does not name unattended" in hook(seg(args(state=st)), [human("orchestrate"), q, human("yes")])
    st = write_plan(UN + "unattended, not gated")
    assert "does not name unattended" in hook(seg(args(state=st)), [human("orchestrate"), QUESTION, human("unattended, not gated")])
    write_plan()


@case
def an_answer_counts_only_right_after_the_kickoff_question():
    for words in ("Run in unattended mode.", "don't run unattended", "what does unattended mean?",
                  "orchestrate plan-x, maybe unattended later"):
        st = write_plan(UN + words)
        why = hook(seg(args(state=st)), [human(words)])
        assert "doesn't follow the kickoff question" in why or "holds its mode line" in why, (words, why)
    for words in ("don't run unattended", "what does unattended mean?", "unattended? not sure"):
        st = write_plan(UN + words)
        assert "plainly" in hook(seg(args(state=st)), [human("orchestrate plan-x"), QUESTION, human(words)]), words
    st = write_plan(UN + "unattended")
    t = [human("orchestrate plan-x"), QUESTION, human("hmm"), said("Noted."), human("unattended")]
    assert "doesn't follow the kickoff question" in hook(seg(args(state=st)), t)
    write_plan()


@case
def a_pasted_prompt_recorded_as_an_answer_is_denied():
    # The whole runner prompt, pasted on a workstation and recorded as an answer, so that rule 7's environment check is skipped.
    words = " ".join(kickoff_prompt("unattended"))
    st = write_plan(UN + words, prompt=kickoff_prompt("unattended"))
    assert "holds its mode line" in hook(seg(args(state=st, groups=TASK)), [human("orchestrate plan-x"), QUESTION, paste()])
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
    git("remote", "set-head", "origin", "trunk", cwd=ws)  # trunk is the remote's default branch (a clone records it)
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


PROMPTED = "unattended | proposed unattended (harness=claude-code runner=cloud) | guard 2x | fixups 2 | confirmed 2026-10-07 session s by Kickoff prompt: Run in unattended mode."


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
    assert "this is harness=claude-code runner=none" in hook(seg(args(state=st, groups=TASK)), [paste()])  # on a workstation
    assert "this is harness=claude-code runner=self-hosted" in hook(seg(args(state=st, groups=TASK)), [paste()], runner="self-hosted")
    old = write_plan(PROMPTED.replace("session s by", "session old-1 by"), prompt=kickoff_prompt("unattended"))
    assert "not this one" in hook(seg(args(state=old, groups=TASK)), [paste()], runner=True)
    ws = write_plan(PROMPTED.replace("proposed unattended (harness=claude-code runner=cloud)", "proposed gated (harness=claude-code runner=none)"),
                    prompt=kickoff_prompt("unattended"))
    assert "this is harness=claude-code runner=cloud" in hook(seg(args(state=ws, groups=TASK)), [paste()], runner=True)
    cx = write_plan(PROMPTED.replace("harness=claude-code", "harness=codex"), prompt=kickoff_prompt("unattended"))
    assert "proposed for harness=codex" in hook(seg(args(state=cx, groups=TASK)), [paste()], runner=True)  # another harness
    write_plan()


@case
def a_runner_on_its_own_assigned_branch_still_counts_the_paste():
    # The cloud session was assigned claude/abc and rewrote the prompt's On branch line; Gary pasted the earlier prompt.
    moved = [x.replace("On branch feature/x", "On branch claude/abc") for x in kickoff_prompt("unattended")]
    st = write_plan(PROMPTED, prompt=moved)
    assert hook(seg(args(state=st, groups=TASK)), [paste()], runner=True) is None
    other = [x.replace("plan is already tagged", "plan is tagged") for x in kickoff_prompt("unattended")]
    assert "Kickoff prompt verbatim" in hook(seg(args(state=st, groups=TASK)), [human("\n".join(other))], runner=True)
    write_plan()


@case
def a_pasted_prompt_never_answers_a_gate():
    for gate in ("1", "guard", "7"):
        st = write_plan(PROMPTED, prompt=kickoff_prompt("unattended"), status=f"BLOCKED at gate {gate} | 0/1 groups done")
        assert f"gate-{gate}" in st["stops"], st["stops"]
        text = paste()["message"]["content"]
        a = args(state=st, groups=TASK, approved=[{"gate": g, "wave": 1} for g in st["stops"]], approval=text)
        assert "a paste answers no gate" in hook(seg(a), [paste()], runner=True), gate
    ok = args(state=st, groups=TASK, approved=[{"gate": g, "wave": 1} for g in st["stops"]], approval="run the xdeep wave")
    asked = said("BLOCKED at gate 7: wave 1 is [xdeep], ~$0.9. Run it?")
    assert hook(seg(ok), [paste(), asked, human("run the xdeep wave")], runner=True) is None
    log = f"review wave-1 (repo m1 s1) 1111111..2222222: WAIVED - {' '.join(kickoff_prompt('unattended'))} - 2026-10-06\n"
    st = write_plan(PROMPTED, prompt=kickoff_prompt("unattended"), log=log)
    assert st["waivers"] and "a paste waives nothing" in hook(seg(args(state=st, groups=TASK)), [paste()], runner=True)
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


@case
def a_repo_whose_default_branch_is_unknown_is_denied():
    st = write_plan(GATED)
    go = [human("orchestrate plan-x")]
    ws, ows = tmp / "ws7", tmp / "origin-ws7.git"
    init_repo(ws, ows, branch="trunk")
    (ws / "a.txt").write_text("a\n")
    git("add", "-A", cwd=ws)
    git("commit", "-q", "-m", "init", cwd=ws)
    git("push", "-q", "-u", "origin", "trunk", cwd=ws)  # no origin/HEAD, as in a cloud checkout
    for b in ("trunk", "feature/y"):
        if b != "trunk":
            git("switch", "-q", "-c", b, "--no-track", cwd=ws)
        assert "default branch is unknown" in hook(seg(args(state=st, groups=[{"workdir": str(ws), "branch": b}])), go), b
    git("remote", "set-head", "origin", "trunk", cwd=ws)  # what the hook's deny says to run, with --auto
    assert hook(seg(args(state=st, groups=[{"workdir": str(ws), "branch": "feature/y"}])), go) is None
    write_plan()


@case
def a_git_error_in_the_plan_repo_denies_instead_of_skipping_checks():
    st = write_plan(GATED)
    rd = tmp / "repo-d"  # a local-only clone, gated on a workstation: nothing to push, the commit still checked
    init_repo(rd)
    pd = rd / "specs" / "handoffs" / "plan-x.md"
    pd.parent.mkdir(parents=True)
    pd.write_text(plan.read_text())
    pd.with_name("handoff-x.md").write_text("# Handoff plan-x\n")
    git("add", "-A", cwd=rd)
    git("commit", "-q", "-m", "update plan-x and its handoff", cwd=rd)
    a = args(state=st, groups=TASK)
    a["plan"]["path"] = str(pd)
    assert hook(seg(a), [human("go")]) is None
    with open(rd / ".git" / "config", "a") as f:
        f.write("[core]\n\trepositoryformatversion = 99\n")  # git now refuses the repo; it isn't "no git repo"
    assert "hook error" in hook(seg(a), [human("go")])
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
