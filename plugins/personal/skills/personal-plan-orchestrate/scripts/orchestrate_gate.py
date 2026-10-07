#!/usr/bin/env python3
"""Claude Code PreToolUse hook on Workflow: check a plan-segment launch is honest.

The workflow script trusts args.state and args.approved. This hook makes them
true, from disk and from the transcript, and fails closed:

1. args.state must equal plan_state.py run now on args.plan.path.
2. Approvals may ride only on a launch made in a turn that a human prompt
   started or that a human message typed mid-turn joined (not a completion
   notification, a hook, or a timer), and args.approval must be the latest
   such message, verbatim. A pasted Kickoff prompt, or
   any words that hold its mode line, never answer anything: not a gate, a
   needs_info question, a waiver, or the kickoff question.
3. canaryDone needs an earlier canary launch of plan-segment in this session.
4. No launch while an earlier plan-segment run of this session is unfinished.
5. After a run that stopped at a gate, the next launch must approve that gate.
6. plan-segment launches by name only, so the reviewed script is the one that runs.
7. An unattended mode in args.state must be confirmed in this session: the
   Kickoff mode line names this session, its proposed signal names this
   harness (claude-code) and this runner (from CLAUDE_CODE_REMOTE, its
   environment type, and CI), and no later human message of 10 words or
   fewer names gated and not unattended (the take-back).
   Confirmed by an answer, a human message here is its words verbatim, it
   comes right after the kickoff question ("Proposed mode: ... Reply"),
   unless CI=true, where the invoking words are the answer, and it asks or
   negates nothing; it names unattended and not gated, or it is a plain yes
   to a question that carried "Proposed mode: unattended." (decision 9). A
   yes to a gated proposal records gated, never unattended. Confirmed by the Kickoff prompt, the words are its mode line
   "Run in unattended mode.", and a human turn here is the plan's whole
   Kickoff prompt verbatim (whitespace collapsed; its On branch lines may
   differ, since a runner keeps its assigned branch and rewrites them). A
   gated mode needs no proof, since it relaxes nothing.
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
   checked; a plan git ignores, in a repo where no group runs, is in no repo
   (a plain folder nested in another repo's work tree). Unattended needs the
   plan in a repo with a remote. A repo with a
   remote must record origin's default branch (refs/remotes/origin/HEAD), and
   any git error other than "not a git repository" denies.
10. A WAIVED Review log line added since this session's last launch must be
   a human turn of this session, verbatim: a waiver is Gary's answer to a
   gate 1, never the parent's. In any session, a WAIVED line whose words are
   the Kickoff prompt or hold its mode line denies.

It prints a deny decision or nothing; it never allows, so the session's
permission rules still apply. Any failure of its own (bad input, a missing
plan_state.py, an exception, no decision within DEADLINE seconds) denies
with exit 2, which blocks even without valid JSON; the hooks file adds
"|| exit 2" for a python3 that won't start. A hook that Claude Code times
out (30 s) doesn't block, hence the shorter deadline.

Which records are human. A user record is human only when origin.kind or
turnOrigin is "human" and promptSource isn't "system" (typed and queued on
the CLI, sdk on the desktop app and the web). Compaction summaries
(isCompactSummary, isVisibleInTranscriptOnly), isMeta records (a runner's
Stop hook feedback), the "[Request interrupted by user" marker, slash-command
records and turnOrigin "sdk" records never are. A message typed while the
parent works is a queued_command attachment (commandMode "prompt", origin
human): it is human text of the turn that absorbed it. A record whose uuid
was seen before (a replay after a compaction) counts once. The Mac CLI wraps
a bracketed paste in <pasted_content id="..."> tags; they are removed before
every comparison.
"""

import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

SHARED_NAME = re.compile(r"^(main|master|release/.+)$")
PROMPT_WORDS = "Run in unattended mode."  # the Kickoff prompt's mode line, recorded as the words of a pasted prompt
MODE_LINES = ("Run in unattended mode.", "Run in gated mode.")
KICKOFF_ASK = re.compile(r"Proposed mode: (?:gated|unattended)\b[\s\S]*\bReply\b")
# An answer that asks back or negates is not an opt-in; a false trip re-asks, which errs toward stopping.
NOT_OPT_IN = re.compile(r"\?|\b(?:no|not|never|without|don't|dont|do not)\b|n't\b", re.I)
PROPOSED_UNATTENDED = re.compile(r"Proposed mode: unattended\.")
# A plain yes (decision 9): only these words, at least one from YES, nothing that asks back or adds a condition.
YES = {"yes", "yep", "yeah", "yup", "y", "ok", "okay", "sure", "confirm", "confirmed", "proceed", "go", "lgtm", "approved", "good"}
YES_FILLER = {"please", "thanks", "thank", "you", "ahead", "sounds", "that", "works"}
TAKE_BACK_WORDS = 10  # a later human message this short that names gated, and not unattended, ends unattended
PASTE_TAG = re.compile(r"</?pasted_content\b[^>]*>")  # the Mac CLI's wrapper around a bracketed paste
INTERRUPT = "[Request interrupted by user"
DEADLINE = 20  # seconds; Claude Code cancels this hook at 30, and a canceled hook blocks nothing


def deny(reason, code=0):
    msg = f"personal-plan-orchestrate gate: {reason}"
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": msg}}))
    if code:
        print(msg, file=sys.stderr)  # exit 2 blocks on its own; stderr is the reason if the JSON doesn't parse
    sys.exit(code)


def unwrap(s):
    return PASTE_TAG.sub("\n", s or "")


def norm(s):
    return re.sub(r"\s+", " ", unwrap(s)).strip()


def plain_yes(text):
    words = re.findall(r"[a-z']+", norm(text).lower())
    return (bool(words) and len(words) <= 6 and not re.search(r"[^a-z' ,.!]", norm(text).lower())
            and all(w in YES or w in YES_FILLER for w in words) and any(w in YES for w in words))


def is_human(r):
    """A user record a person typed or pasted; never a notification, a hook's feedback, a compaction summary, a slash
    command's records, the interrupt marker, or an SDK-injected prompt."""
    if r.get("isMeta") or r.get("isCompactSummary") or r.get("isVisibleInTranscriptOnly") or r.get("promptSource") == "system":
        return False
    return "human" in ((r.get("origin") or {}).get("kind"), r.get("turnOrigin"))


def queued_text(r):
    """The text of a message typed while the parent worked (absorbed into the running turn), or None."""
    a = r.get("attachment") if r.get("type") == "attachment" else None
    if isinstance(a, dict) and a.get("type") == "queued_command" and a.get("commandMode") == "prompt" \
            and ((a.get("origin") or {}).get("kind") == "human" or a.get("humanTurn") is True) and isinstance(a.get("prompt"), str):
        return a["prompt"]
    return None


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
    """The current turn's messages (the record that started it, then human messages absorbed into it), every
    message, and earlier plan-segment launches."""
    turn, uses, launched = [], {}, []
    run_ids, turns, said, seen = [], [], "", set()
    for r in records(path):
        if r.get("isSidechain"):
            continue
        uid = r.get("uuid")
        if uid:
            if uid in seen:
                continue  # a record replayed after a compaction counts once
            seen.add(uid)
        msg = r.get("message") or {}
        q = queued_text(r)
        if q is not None:
            t = {"human": True, "text": unwrap(q), "after": said}
            turns.append(t)
            turn.append(t)
            continue
        if r.get("type") == "assistant":
            text = "\n".join(b.get("text", "") for b in msg.get("content") or [] if isinstance(b, dict) and b.get("type") == "text")
            said = text or said  # the assistant's latest words, which the next human turn answers
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
            if text is None or r.get("isMeta") or r.get("isCompactSummary") or r.get("isVisibleInTranscriptOnly") \
                    or text.lstrip().startswith(INTERRUPT):
                continue  # none of these starts a turn
            t = {"human": is_human(r), "text": unwrap(text), "after": said}
            turns.append(t)
            turn = [t]
    return turn, launched, run_ids, turns


def names(word, text):
    return re.search(rf"\b{word}\b", text or "", re.I) is not None


def lines_of(text, drop):
    return norm(" ".join(x for x in (text or "").splitlines() if not drop(x.strip())))


def is_paste(text, prompt, strict=True):
    """Whether text is the plan's Kickoff prompt, whitespace collapsed. Its On branch lines may differ (a runner keeps
    its assigned branch and rewrites them); strict=False lets the mode line differ too, for a prompt copied earlier."""
    if not prompt or not norm(text):
        return False
    if norm(text) == norm(prompt):
        return True
    drop = (lambda x: x.startswith("On branch")) if strict else (lambda x: x.startswith("On branch") or x in MODE_LINES)
    return lines_of(text, drop) == lines_of(prompt, drop)


def not_an_answer(words, prompt):
    """A pasted Kickoff prompt starts a session; neither it nor words that hold its mode line answer anything."""
    w = norm(words).lower()
    return any(m.lower() in w for m in MODE_LINES) or is_paste(words, prompt, strict=False)


def env_runner():
    """This hook's runner token, as the mode line's proposed signal spells it."""
    if os.environ.get("CLAUDE_CODE_REMOTE") == "true":
        return "self-hosted" if os.environ.get("CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE") == "self_hosted" else "cloud"
    return "ci" if "true" in (os.environ.get("CI"), os.environ.get("GITHUB_ACTIONS")) else "none"


def unattended_proof(mode, session_id, turns, prompt, prompt_mode):
    """None when the recorded unattended mode is confirmed in this session, else the reason it isn't."""
    if mode.get("session") != session_id:
        return f"the mode was confirmed in session {mode.get('session')}, not this one; ask the kickoff question again"
    here = ("claude-code", env_runner())
    if (mode.get("harness"), mode.get("runner")) != here:
        return (f"the mode was proposed for harness={mode.get('harness')} runner={mode.get('runner')}, and this is "
                f"harness={here[0]} runner={here[1]}; ask the kickoff question again with a fresh proposal")
    words = norm(mode.get("words"))
    if mode.get("via") == "prompt":
        # Pasting the Kickoff prompt is Gary's own message. Only the whole prompt counts, never a message that mentions the mode.
        if words != PROMPT_WORDS or prompt_mode != "unattended" or not prompt:
            return f'a confirmation by Kickoff prompt records its mode line, "{PROMPT_WORDS}", and the plan\'s prompt must carry it'
        hits = [i for i, t in enumerate(turns) if t["human"] and is_paste(t["text"], prompt)]
        if not hits:
            return "no human turn in this session is the plan's Kickoff prompt verbatim; ask the kickoff question"
    else:
        if not_an_answer(words, prompt):
            return "the recorded answer is the Kickoff prompt or holds its mode line; a paste counts only by Kickoff prompt"
        hits = [i for i, t in enumerate(turns) if t["human"] and norm(t["text"]) == words]
        if not words or not hits:
            return "no human turn in this session is the recorded mode answer verbatim"
        ci = env_runner() == "ci"  # nobody can reply in CI, so the invoking words are the answer
        hits = [i for i in hits if ci or KICKOFF_ASK.search(turns[i]["after"])]
        if not hits:
            return "the recorded answer doesn't follow the kickoff question; an invoking message only proposes the mode, so ask it"

        def opts_in(t):
            if NOT_OPT_IN.search(t["text"]) or names("gated", t["text"]):
                return False
            # Decision 9: a plain yes counts when the kickoff question right before it proposed unattended.
            return names("unattended", t["text"]) or (plain_yes(t["text"]) and bool(PROPOSED_UNATTENDED.search(t["after"])))
        good = [i for i in hits if opts_in(turns[i])]
        if not good:
            if plain_yes(turns[hits[-1]]["text"]):
                return "the recorded answer is a yes to a gated proposal, which records gated, never unattended (decision 9)"
            return ("the recorded answer does not name unattended plainly (a question or a negation re-asks; a bare yes counts "
                    "only when the question proposed unattended, decision 9)")
        hits = good
    if any(took_back(u) for u in turns[hits[-1] + 1:]):
        return "a later short human message names gated; record gated, or ask the kickoff question again"
    return None


def took_back(t):
    """A human message of 10 words or fewer that names gated and not unattended ends unattended."""
    return t["human"] and len(norm(t["text"]).split()) <= TAKE_BACK_WORDS and names("gated", t["text"]) \
        and not names("unattended", t["text"])


def git(d, *a):
    return subprocess.run(["git", "-C", d, *a], capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"})


def in_handoffs(plan_path):
    p = Path(plan_path).resolve()
    return p.parent.name == "handoffs" and p.parent.parent.name == "specs" and p.name.startswith("plan-")


def remote_of(d):
    """None outside any git work tree, False in a repo with no remote, True in one with a remote. Any other git
    failure (dubious ownership, a broken config or index) raises, so the hook denies instead of skipping checks."""
    r = git(d, "remote")
    if r.returncode:
        if "not a git repository" in r.stderr:
            return None
        raise RuntimeError(f"git in {d}: {r.stderr.strip()[:200]}")
    return bool(r.stdout.strip())


def branch_problem(d, want=None):
    """None when d has a branch checked out (want, when given) that isn't main, master, release/* or the remote's default."""
    head = git(d, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if not head:
        return f"{d} has no branch checked out (a detached HEAD, or no git repo); cut a task branch"
    if want is not None and head != want:
        return f"{d} is on {head}, not the group's branch {want or '(none given)'}"
    default = None
    if remote_of(d):  # fail closed: a repo with a remote must say which branch is its default
        if "origin" not in git(d, "remote").stdout.split():
            return f"{d} has no origin remote, so its default branch is unknown; orchestrate pushes to origin"
        default = git(d, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD").stdout.strip()
        if not default:
            return f"origin's default branch is unknown in {d} (no refs/remotes/origin/HEAD); run git -C {d} remote set-head origin --auto"
    if SHARED_NAME.match(head) or (default and default.split("/", 1)[-1] == head):
        return f"{head} in {d} is a shared branch; orchestrate runs only on a task branch: cut one with --no-track"
    return None


def plan_home(plan_path, groups):
    """remote_of for the repo that holds the plan, except that a plan git ignores, in a repo that holds no group, is in
    no repo: a plain folder of sibling repos nested in another repo's work tree keeps its plan in its own .scratch/."""
    p = Path(plan_path).resolve()
    home = remote_of(str(p.parent))
    if home is None or git(str(p.parent), "check-ignore", "-q", str(p)).returncode:
        return home
    top = git(str(p.parent), "rev-parse", "--show-toplevel").stdout.strip()
    tops = {git(g.get("workdir") or "", "rev-parse", "--show-toplevel").stdout.strip() for g in groups}
    return home if top in tops else None


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
    st = git(d, "status", "--porcelain", "--", p.name, h.name)
    if st.returncode:
        return f"git status failed in {d}: {st.stderr.strip()[:200]}"
    if st.stdout.strip():
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


def check(inp):
    ti = inp.get("tool_input") or {}
    name = ti.get("name") or ""
    script = (ti.get("script") or "") + (ti.get("scriptPath") or "")
    if not is_segment(name):
        if "plan-segment" in script:
            deny("launch plan-segment by name, not by script or scriptPath")
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from plan_state import kickoff_prompt, state  # inside the guard: a missing or older plan_state.py denies
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
    prompt = kickoff_prompt(text)
    home = plan_home(path, groups)
    for d, want in [(g.get("workdir") or "", g.get("branch") or "") for g in groups] + \
            ([(str(Path(path).resolve().parent), None)] if home is not None else []):
        why = branch_problem(d, want)
        if why:
            deny(f"task branch: {why}")
    if unattended:
        why = unattended_proof(mode, inp.get("session_id"), turns, prompt, fresh.get("prompt_mode"))
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
    for w in fresh.get("waivers") or []:  # in any session: a paste is never a waiver
        if not_an_answer(w.get("words"), prompt):
            deny(f"the WAIVED line for wave {w.get('wave')} ({w.get('group')}) records the Kickoff prompt or its mode line; a paste waives nothing")
    if segs:
        had = ((segs[-1].get("args") or {}).get("state") or {}).get("waivers") or []
        for w in fresh.get("waivers") or []:
            if w not in had and not any(t["human"] and norm(t["text"]) == norm(w.get("words")) for t in turns):
                deny(f"the WAIVED line for wave {w.get('wave')} ({w.get('group')}) is not a human message of this session, verbatim; a waiver records Gary's answer")
    answers = [(g.get("answer") or {}).get("answer") for g in groups if isinstance(g.get("answer"), dict)]
    if args.get("approved") or answers:
        said_now = [t for t in turn if t["human"]]  # the human message that started this turn, or one typed into it
        if not said_now:
            deny("approvals can ride only on a launch in the turn a human answer started or joined; relaunch with approved: []")
        if norm(said_now[-1]["text"]) != norm(args.get("approval")):
            deny("args.approval is not the human's last message verbatim")
        if any(not_an_answer(a, prompt) for a in [args.get("approval")] + answers):
            deny("the approval is the pasted Kickoff prompt, or holds its mode line; a paste answers no gate or question: "
                 "re-post the BLOCKED question and wait for Gary's answer")
    if args.get("canaryDone") and not any(is_segment(u.get("name") or "") and not (u.get("args") or {}).get("canaryDone")
                                          for u in launched):
        deny("canaryDone is true, but this session has no earlier canary launch of plan-segment")


def on_alarm(signum, frame):
    raise TimeoutError(f"no decision within {DEADLINE}s")


def main():
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, on_alarm)
        signal.alarm(DEADLINE)
    try:
        check(json.load(sys.stdin))
    except SystemExit:
        raise
    except BaseException as e:  # fail closed, with exit 2, which blocks even if the JSON is lost
        deny(f"hook error ({type(e).__name__}: {e})", code=2)


if __name__ == "__main__":
    main()
