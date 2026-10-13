#!/usr/bin/env python3
"""SessionStart hook for the `personal` plugin: run each repo's doctor so a session starts knowing what the machine lacks.

It looks at the session's repo (the working directory's git root) or, when
the working directory isn't in a repo and has no doctor of its own, at each
git repo directly under it: a cloud session starts in /workspace with the
repos beneath. Each repo gets the first doctor it has:

- `make doctor` when its Makefile defines a doctor target;
- `task doctor` when its Taskfile defines a doctor task;
- `triage --profile default` when it has a triage config (triage.yaml,
  triage.yml, .triage.yaml or .triage.yml, triage's own discovery list).

A doctor is the repo's own code, and a personal plugin's hooks run before
the harness asks whether to trust the folder. So a repo's doctor runs only
when the owner in its `origin` URL is a default owner or one named in
PERSONAL_DOCTOR_OWNERS (space-separated; both case-insensitive), which adds
owners that shouldn't be named in this public repo. Any other repo, or one
with no origin, gets a "not run" line instead. Targets are found
by reading the files, never with `make -n` or `task --list`: both evaluate
the file, and GNU make runs `$(shell ...)` while it parses.

The doctors run in parallel, each with a timeout. The output is facts only,
for the agent to judge: one line naming the repos that passed and, for each
that didn't, the command, how it ended and the tail of its output. Plain
text for Claude Code and Codex, one JSON object for Gemini CLI, as in
session-start.sh. It never blocks a session: it fails open, printing nothing
on an error of its own. PERSONAL_DOCTOR=0 turns it off.
"""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

MAKEFILES = ("GNUmakefile", "makefile", "Makefile")  # make's own search order
TASKFILES = tuple(f"{case}askfile{dist}.{ext}" for dist in ("", ".dist") for ext in ("yml", "yaml") for case in "Tt")
TRIAGE_CONFIGS = ("triage.yaml", "triage.yml", ".triage.yaml", ".triage.yml")
DEFAULT_OWNERS = "GaryRudolph lolay Agerpoint Coastal-Carbon optimal-ticketing"
# Quiet output and no network call to GitHub, also for a triage that `make doctor` runs.
DOCTOR_ENV = {"NO_COLOR": "1", "TRIAGE_NO_UPDATE_CHECK": "1"}

# A rule line: targets, then ':' or '::' that doesn't start ':=' or '::='.
MAKE_RULE = re.compile(r"^(?P<targets>[^:#=\s][^:#=]*?)\s*::?(?!=)", re.MULTILINE)
TOP_LEVEL_KEY = re.compile(r"^(?P<key>[^\s#][^:]*):")
TASK_KEY = re.compile(r"^(?P<indent>\s+)(?P<key>[^\s#][^:]*?)\s*:")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

DEFAULT_TIMEOUT = 30
MAX_PARALLEL = 8
TAIL_LINES = 30
OUTPUT_BUDGET = 9000  # under Claude Code's 10,000-character hook output cap


def read_text(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def makefile_has_doctor(text):
    return any("doctor" in m.group("targets").split() for m in MAKE_RULE.finditer(text))


def taskfile_has_doctor(text):
    """True when the top-level `tasks:` map has a `doctor` key."""
    in_tasks, task_indent = False, None
    for line in text.splitlines():
        top = TOP_LEVEL_KEY.match(line)
        if top:
            in_tasks, task_indent = top.group("key").strip() == "tasks", None
            continue
        task = TASK_KEY.match(line) if in_tasks else None
        if not task:
            continue
        task_indent = task_indent or task.group("indent")
        if task.group("indent") == task_indent and task.group("key").strip("'\"") == "doctor":
            return True
    return False


def doctor_command(repo):
    """The doctor this repo defines, as an argv list, or None."""
    makefile = next((repo / name for name in MAKEFILES if (repo / name).is_file()), None)
    if makefile and makefile_has_doctor(read_text(makefile)):
        return ["make", "--no-print-directory", "doctor"]
    taskfile = next((repo / name for name in TASKFILES if (repo / name).is_file()), None)
    if taskfile and taskfile_has_doctor(read_text(taskfile)):
        return ["task", "doctor"]
    if any((repo / name).is_file() for name in TRIAGE_CONFIGS):
        return ["triage", "--profile", "default"]
    return None


def git_root(path):
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def repos_to_check(cwd):
    root = git_root(cwd)
    if root:
        return [root]
    if doctor_command(cwd):
        return [cwd]
    try:
        children = sorted(p for p in cwd.iterdir() if p.is_dir() and (p / ".git").exists())
    except OSError:
        return []
    return children


def origin_owner(repo):
    """The owner segment of origin's URL (https, scp-style ssh or a proxy path), or None without an origin."""
    try:
        url = subprocess.run(["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    segments = re.split(r"[:/]", url.rstrip("/").removesuffix(".git"))
    return segments[-2] if len(segments) >= 2 and segments[-2] else None


def is_trusted(owner):
    owners = f"{DEFAULT_OWNERS} {os.environ.get('PERSONAL_DOCTOR_OWNERS', '')}".lower().split()
    return bool(owner) and owner.lower() in owners


def run_doctor(repo, argv, timeout):
    """Run one doctor; returns (repo, argv, outcome, output).

    outcome is an exit code, 'timeout', 'missing' (the tool isn't on PATH) or
    'untrusted' (output then holds origin's owner, empty without an origin).
    """
    owner = origin_owner(repo)
    if not is_trusted(owner):
        return repo, argv, "untrusted", owner or ""
    if not shutil.which(argv[0]):
        return repo, argv, "missing", ""
    env = {**os.environ, **DOCTOR_ENV}
    proc = subprocess.Popen(argv, cwd=repo, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, start_new_session=True)
    try:
        out, _ = proc.communicate(timeout=timeout)
        return repo, argv, proc.returncode, out.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        kill_group(proc)
        out, _ = proc.communicate()
        return repo, argv, "timeout", out.decode("utf-8", "replace")


def kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (AttributeError, OSError):
        proc.kill()


def label(argv):
    """The command as the report names it, without make's directory chatter flag."""
    return " ".join(arg for arg in argv if arg != "--no-print-directory")


def tail(output, limit):
    lines = ANSI.sub("", output).rstrip().splitlines()[-TAIL_LINES:]
    text = "\n".join("    " + line for line in lines)
    return text if len(text) <= limit else "    ..." + text[-limit:]


def report(results, timeout):
    passed = [r for r in results if r[2] == 0]
    failed = [r for r in results if r[2] != 0]
    if not results:
        return ""
    lines = ["Environment doctor, run at session start by the personal plugin:"]
    if passed:
        lines.append("passed: " + ", ".join(f"`{label(argv)}` in {repo}" for repo, argv, _, _ in passed))
    budget = max(500, (OUTPUT_BUDGET - sum(len(line) for line in lines)) // max(1, len(failed)) - 200)
    for repo, argv, outcome, output in failed:
        command = label(argv)
        if outcome in ("missing", "untrusted"):
            lines.append(f"not run: `{command}` in {repo}: {not_run_reason(argv, outcome, output)}")
            continue
        how = f"timed out after {timeout}s" if outcome == "timeout" else f"exit {outcome}"
        lines.append(f"FAILED ({how}): `{command}` in {repo}")
        if output.strip():
            lines.append(tail(output, budget))
    return "\n".join(lines)[:OUTPUT_BUDGET]


def not_run_reason(argv, outcome, owner):
    if outcome == "missing":
        return f"{argv[0]} is not on PATH"
    if owner:
        return f'origin owner "{owner}" is not a trusted owner (add it to PERSONAL_DOCTOR_OWNERS)'
    return "no origin remote, so its owner is unknown"


def session_cwd():
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        data = {}
    cwd = data.get("cwd") if isinstance(data, dict) else None
    cwd = cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("GEMINI_PROJECT_DIR") or os.getcwd()
    return Path(cwd).resolve()


def emit(text):
    is_gemini = bool(os.environ.get("GEMINI_PROJECT_DIR")) and not os.environ.get("CLAUDE_PLUGIN_ROOT")
    if is_gemini:
        payload = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}} if text else {}
        print(json.dumps(payload))
    elif text:
        print(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="seconds per doctor")
    args = parser.parse_args()
    if os.environ.get("PERSONAL_DOCTOR") == "0":
        emit("")
        return
    jobs = [(repo, argv) for repo in repos_to_check(session_cwd()) if (argv := doctor_command(repo))]
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
        results = list(pool.map(lambda job: run_doctor(*job, args.timeout), jobs))
    timeout = f"{args.timeout:g}"
    emit(report(results, timeout))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a SessionStart hook must never break the session
        emit("")
    sys.exit(0)
