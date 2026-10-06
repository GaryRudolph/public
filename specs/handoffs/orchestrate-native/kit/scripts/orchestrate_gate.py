#!/usr/bin/env python3
"""Claude Code PreToolUse hook on Workflow: check a plan-segment launch is honest.

The workflow script trusts args.state and args.approved. This hook makes them
true, from disk and from the transcript, and fails closed:

1. args.state must equal plan_state.py run now on args.plan.path.
2. Approvals may ride only on a launch made in a turn that a human prompt
   started (not a completion notification, a hook, or a timer), and
   args.approval must be that prompt, verbatim.
3. canaryDone needs an earlier canary launch of plan-segment in this session.
4. No launch while an earlier plan-segment run of this session is unfinished.
5. After a run that stopped at a gate, the next launch must approve that gate.
6. plan-segment launches by name only, so the reviewed script is the one that runs.
7. An unattended mode in args.state must be confirmed in this session: the
   Kickoff mode line names this session, and no later human turn names
   gated. Confirmed by an answer, a human-started turn here is its words
   verbatim and they name unattended and not gated: a bare yes re-asks
   (decision 9). Confirmed by the Kickoff prompt, the words are its mode line
   "Run in unattended mode.", a human turn here is the plan's whole Kickoff
   prompt verbatim (whitespace collapsed), and CLAUDE_CODE_REMOTE matches the
   recorded runner signal. A gated mode needs no proof, since it relaxes
   nothing.
8. A cost guard raised since this session's last launch needs this turn's
   human approval of gate-guard, and a raised fix-up cap one of gate-1
   (rule 2 then checks the words).
9. Orchestrate runs only on a task branch, in both modes and on every
   machine. Every group's working directory has its group's branch checked
   out, and neither it nor the branch of the repo that holds the plan is
   main, master, release/*, or the remote's default branch. The plan and
   its session handoff sit in specs/handoffs/ (plan-{topic}-{word}.md,
   handoff-{topic}-{word}.md), have no uncommitted changes, the handoff's
   last commit is the plan's or a later one, and it is on the branch's
   upstream; and the HEAD of every working directory of this session's last
   finished run is on its upstream: every wave's results and their handoff
   are committed and pushed before the next launch. Gated on a workstation,
   where nothing can be pushed: a plan in no git repo (a plain folder of
   sibling repos) skips the plan check, a plan in a repo with no remote
   skips only its push check, and a working directory with no remote is not
   checked. Unattended needs the plan in a repo with a remote.
10. A WAIVED Review log line added since this session's last launch must be
   a human turn of this session, verbatim: a waiver is Gary's answer to a
   gate 1, never the parent's.

It prints a deny decision or nothing; it never allows, so the session's
permission rules still apply.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan_state import kickoff_prompt, state  # noqa: E402

SHARED_NAME = re.compile(r"^(main|master|release/.+)$")
PROMPT_WORDS = "Run in unattended mode."  # the Kickoff prompt's mode line, recorded as the words of a pasted prompt


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": f"personal-plan-orchestrate gate: {reason}"}}))
    sys.exit(0)


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def records(path):
    with open(path) as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return None
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return None


def turn_and_launches(path):
    """The record that started the current turn, every prompt turn, and earlier plan-segment launches."""
    turn, uses, launched = None, {}, []
    run_ids, turns = [], []
    for r in records(path):
        if r.get("isSidechain"):
            continue
        msg = r.get("message") or {}
        if r.get("type") == "assistant":
            for b in msg.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Workflow":
                    uses[b.get("id")] = b.get("input") or {}
        elif r.get("type") == "user":
            res = r.get("toolUseResult")
            if isinstance(res, dict) and res.get("runId") and not res.get("error"):
                for b in msg.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in uses:
                        launched.append(uses[b["tool_use_id"]])
                        if is_segment(uses[b["tool_use_id"]].get("name") or ""):
                            run_ids.append(res["runId"])
                continue
            text = text_of(msg.get("content"))
            if text is not None and not r.get("isMeta"):
                origin = (r.get("origin") or {}).get("kind")
                human = origin in (None, "human") and r.get("promptSource") != "system" and r.get("turnOrigin") != "task_notification"
                turn = {"human": human, "text": text}
                turns.append(turn)
    return turn, launched, run_ids, turns


def names(word, text):
    return re.search(rf"\b{word}\b", text or "", re.I) is not None


def unattended_proof(mode, session_id, turns, prompt, prompt_mode, runner):
    """None when the recorded unattended mode is confirmed in this session, else the reason it isn't."""
    if mode.get("session") != session_id:
        return f"the mode was confirmed in session {mode.get('session')}, not this one; ask the kickoff question again"
    words = norm(mode.get("words"))
    if mode.get("via") == "prompt":
        # Pasting the Kickoff prompt is Gary's own message. Only the whole prompt counts, never a message that mentions the mode.
        if words != PROMPT_WORDS or prompt_mode != "unattended" or not prompt:
            return f'a confirmation by Kickoff prompt records its mode line, "{PROMPT_WORDS}", and the plan\'s prompt must carry it'
        hits = [i for i, t in enumerate(turns) if t["human"] and norm(t["text"]) == norm(prompt)]
        if not hits:
            return "no human turn in this session is the plan's Kickoff prompt verbatim; ask the kickoff question"
        if ("CLAUDE_CODE_REMOTE=true" in (mode.get("signal") or "")) != runner:
            return (f"the mode was confirmed with runner signal ({mode.get('signal')}), and CLAUDE_CODE_REMOTE here "
                    f"{'is' if runner else 'is not'} true; ask the kickoff question again")
    else:
        hits = [i for i, t in enumerate(turns) if t["human"] and norm(t["text"]) == words]
        if not words or not hits:
            return "no human turn in this session is the recorded mode answer verbatim"
        t = turns[hits[-1]]
        if not names("unattended", t["text"]) or names("gated", t["text"]):
            return "the recorded answer does not name unattended (a bare yes re-asks, decision 9)"
    if any(u["human"] and names("gated", u["text"]) for u in turns[hits[-1] + 1:]):
        return "a later human turn names gated; record gated, or ask the kickoff question again"
    return None


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True)


def in_handoffs(plan_path):
    p = Path(plan_path).resolve()
    return p.parent.name == "handoffs" and p.parent.parent.name == "specs" and p.name.startswith("plan-")


def remote_of(d):
    """None outside any git work tree, False in a repo with no remote, True in one with a remote."""
    r = git(d, "remote")
    return None if r.returncode else bool(r.stdout.strip())


def branch_problem(d, want=None):
    """None when d has a branch checked out (want, when given) that isn't main, master, release/* or the remote's default."""
    head = git(d, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if not head:
        return f"{d} has no branch checked out (a detached HEAD, or no git repo); cut a task branch"
    if want is not None and head != want:
        return f"{d} is on {head}, not the group's branch {want or '(none given)'}"
    default = git(d, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD").stdout.strip()
    if SHARED_NAME.match(head) or (default and default.split("/", 1)[-1] == head):
        return f"{head} in {d} is a shared branch; orchestrate runs only on a task branch: cut one with --no-track"
    return None


def handoff_problem(plan_path, push=True):
    """None when the plan and a handoff refreshed since its last change are committed (and pushed)."""
    p = Path(plan_path).resolve()
    if not in_handoffs(p):
        return ("the plan lives in specs/handoffs/ as plan-{topic}-{word}.md, in both modes; move it there and commit it "
                "(only a gated plan in no git repo on a workstation stays in .scratch/)")
    h = p.with_name("handoff-" + p.name[len("plan-"):])
    if not h.exists():
        return f"no session handoff at {h}; write it, and commit it with the plan"
    d = str(p.parent)
    if git(d, "status", "--porcelain", "--", p.name, h.name).stdout.strip():
        return "the plan or the handoff has uncommitted changes; commit both in the bookkeeping commit and push"
    last = [git(d, "log", "-1", "--format=%H", "--", f).stdout.strip() for f in (p.name, h.name)]
    if not all(last):
        return "the plan and the handoff must both be tracked"
    if git(d, "merge-base", "--is-ancestor", last[0], last[1]).returncode:
        return "the plan changed after the handoff was last committed; refresh the handoff and commit it with the plan"
    if push and git(d, "merge-base", "--is-ancestor", last[1], "@{u}").returncode:
        return "the bookkeeping commit is not pushed (or the branch has no upstream); push it first"
    return None


def unpushed(groups, local=False):
    """None when every working directory of a run has its HEAD on its upstream (local: one with no remote is skipped)."""
    for g in groups:
        if isinstance(g, dict):
            d = g.get("workdir") or ""
            if local and remote_of(d) is False:
                continue
            if git(d, "merge-base", "--is-ancestor", "HEAD", "@{u}").returncode:
                return f"{d} has commits that are not pushed (or no upstream); push every working directory after the bookkeeping commit"
    return None


def runs_of(transcript_path, run_ids):
    """Run records of this session's plan-segment launches, oldest first; None for a run with no record yet."""
    base = transcript_path[:-len(".jsonl")] if transcript_path.endswith(".jsonl") else transcript_path
    out = []
    for rid in run_ids:
        try:
            with open(os.path.join(base, "workflows", f"{rid}.json")) as f:
                out.append((rid, json.load(f)))
        except OSError:
            out.append((rid, None))
    return out


def is_segment(name):
    return name == "plan-segment" or name.endswith(":plan-segment")


def main():
    inp = json.load(sys.stdin)
    ti = inp.get("tool_input") or {}
    name = ti.get("name") or ""
    script = (ti.get("script") or "") + (ti.get("scriptPath") or "")
    if not is_segment(name):
        if "plan-segment" in script:
            deny("launch plan-segment by name, not by script or scriptPath")
        return
    try:
        args = ti.get("args")
        if not isinstance(args, dict):
            deny("args must be a JSON object, not a string")
        path = args["plan"]["path"]
        with open(path) as f:
            text = f.read()
        fresh = state(text)
        if fresh != args.get("state"):
            deny(f"args.state differs from plan_state.py on {path}; re-run it after your last plan edit and pass its output verbatim")
        turn, launched, run_ids, turns = turn_and_launches(inp["transcript_path"])
        runs = runs_of(inp["transcript_path"], run_ids)
        mode = fresh.get("mode") or {}
        unattended = mode.get("value") == "unattended"
        groups = [g for g in args.get("groups") or [] if isinstance(g, dict)]
        runner = os.environ.get("CLAUDE_CODE_REMOTE") == "true"
        home = remote_of(str(Path(path).resolve().parent))
        for d, want in [(g.get("workdir") or "", g.get("branch") or "") for g in groups] + \
                ([(str(Path(path).resolve().parent), None)] if home is not None else []):
            why = branch_problem(d, want)
            if why:
                deny(f"task branch: {why}")
        if unattended:
            why = unattended_proof(mode, inp.get("session_id"), turns, kickoff_prompt(text), fresh.get("prompt_mode"), runner)
            if why:
                deny(f"unattended mode is not confirmed: {why}")
        if unattended and not home:
            deny("per-wave handoff: unattended needs the plan in a git repo with a remote, so each wave's handoff is pushed; run gated")
        local = not unattended and not runner  # gated on a workstation: where nothing can be pushed, nothing is checked for a push
        if not (local and home is None):  # fail closed: only a gated workstation plan in no git repo skips it
            why = handoff_problem(path, push=not (local and home is False))
            if why:
                deny(f"per-wave handoff: {why}")
        busy = [rid for rid, rec in runs if rec is None or rec.get("status") in ("running", "pending", "paused")]
        if busy:
            deny(f"run {', '.join(busy)} has not finished; wait for it (a run with no record after a crash means: start a new session)")
        done = [rec for _, rec in runs if rec]
        last = (done[-1].get("result") or {}) if done else {}
        owed = [g for g in last.get("gates") or [] if g not in ("gate-0", "gate-mode")] if last.get("stop") == "gate" else []
        given = {a.get("gate") for a in args.get("approved") or [] if isinstance(a, dict)}
        if [g for g in owed if g not in given]:
            deny(f"the last run stopped at {', '.join(owed)}; this launch must carry the human's approval of each")
        why = unpushed(last.get("groups") or [], local)  # both modes
        if why:
            deny(f"per-wave handoff: {why}")
        segs = [u for u in launched if is_segment(u.get("name") or "")]
        prior = (((segs[-1].get("args") or {}).get("state") or {}).get("mode") or {}) if segs else {}
        before, floor = prior.get("guard"), prior.get("guard_min")
        rose = (before is not None and (mode.get("guard") or 0) > before) or \
            (floor is not None and (mode.get("guard_min") or 0) > floor)
        if rose and "gate-guard" not in given:
            deny(f"the cost guard rose from {before:g}x min ${floor or 0:g} to {mode.get('guard') or 0:g}x min ${mode.get('guard_min') or 0:g} since the last launch; approve gate-guard with the human's answer")
        cap = prior.get("fixups")
        if cap is not None and (mode.get("fixups") or 0) > cap and "gate-1" not in given:
            deny(f"the fix-up cap rose from {cap} to {mode.get('fixups')} since the last launch; approve gate-1 with the human's answer")
        if segs:
            had = ((segs[-1].get("args") or {}).get("state") or {}).get("waivers") or []
            for w in fresh.get("waivers") or []:
                if w not in had and not any(t["human"] and norm(t["text"]) == norm(w.get("words")) for t in turns):
                    deny(f"the WAIVED line for wave {w.get('wave')} ({w.get('group')}) is not a human message of this session, verbatim; a waiver records Gary's answer")
        if args.get("approved"):
            if not turn or not turn["human"]:
                deny("approvals can ride only on a launch in the turn a human answer started; relaunch with approved: []")
            if norm(turn["text"]) != norm(args.get("approval")):
                deny("args.approval is not the human's last message verbatim")
        if args.get("canaryDone") and not any(is_segment(u.get("name") or "") and not (u.get("args") or {}).get("canaryDone")
                                              for u in launched):
            deny("canaryDone is true, but this session has no earlier canary launch of plan-segment")
    except SystemExit:
        raise
    except Exception as e:  # fail closed
        deny(f"hook error ({type(e).__name__}: {e})")


if __name__ == "__main__":
    main()
