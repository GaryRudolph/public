#!/usr/bin/env python3
"""Open one GitHub issue when Claude Code managed settings need pasting.

claude.ai has no API for an org's managed settings, so the Owner pastes them
by hand into every org listed in agents/org/settings.json. On each push to
main this finds the last commit that changed the generated file, works out
which orgs don't have that content yet, and then files one issue covering
them, leaves the open issue alone, closes it, or does nothing. It checks main's
current tip every run, so a run dropped from the queue, a rerun of an old push
and a first run all end in the same state.

What an org has is read from the issues themselves: every issue closed as
completed records the content it pinned and the orgs it listed. An org has the
current content when the newest of those issues that lists it pinned the same
content. So a change to the file asks for every org, and an org added to the list
with no change asks for that org alone. Issues closed as not planned
(superseded, or no longer needed) never count.

Each newly filed issue is posted to Slack (SLACK_BOT_TOKEN, SLACK_CHANNEL_ID),
best effort: Slack trouble is a warning, never a failure. A dry run files,
closes and posts nothing.

Usage (from the repo root):
  settings_issue.py --sha SHA [--dry-run] [--repo OWNER/NAME]
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REGISTRY = "agents/org/settings.json"
LABEL = "allowlist"
MARKER_RE = re.compile(r"<!-- org-settings (\{.*?\}) -->")
PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
# The generated file's own stamp, filled in with the commit the issue pins.
STAMP_RE = re.compile(r"\{\{\s*commit\s*\}\}")
# GitHub refuses an issue body over 65,536 characters.
MAX_BODY = 65_000
TOKEN_RE = re.compile(r"^xoxb-[A-Za-z0-9-]+$")
CHANNEL_RE = re.compile(r"^[CG][A-Z0-9]{6,}$")


@dataclass(frozen=True)
class Org:
    name: str
    where: str


@dataclass(frozen=True)
class Setting:
    id: str
    name: str
    content: str
    steps: str
    orgs: tuple[Org, ...]


@dataclass(frozen=True)
class Issue:
    number: int
    sha: str
    orgs: tuple[str, ...]
    url: str = ""


@dataclass
class Outcome:
    action: str  # file, leave, skip, close
    reason: str
    orgs: list[str] = field(default_factory=list)
    changed: bool = True
    issue: Issue | None = None
    closed: list[int] = field(default_factory=list)
    title: str = ""
    body: str = ""


def load_registry(path: Path) -> Setting:
    data = json.loads(path.read_text(encoding="utf-8"))
    orgs = tuple(Org(name=o["name"], where=o["where"]) for o in data["orgs"])
    names = [o.name for o in orgs]
    if not orgs or len(set(names)) != len(names) or any(not n.strip() for n in names):
        raise ValueError(f"{path}: orgs must be a non-empty list of distinct names")
    return Setting(id=data["id"], name=data["name"], content=data["content"], steps=data["steps"], orgs=orgs)


def by_workflow(raw: dict) -> bool:
    """Only the workflow's own issues count: the repo is public, and an issue
    someone else got labelled must not decide what's due or what was pasted.
    gh names the Actions bot app/github-actions or github-actions[bot]."""
    author = raw.get("author") or {}
    return bool(author.get("is_bot")) and author.get("login") in ("app/github-actions", "github-actions", "github-actions[bot]")


def same(a: bytes | None, b: bytes | None) -> bool:
    if a is None or b is None:
        return a is b
    return json.loads(a) == json.loads(b)


def parse_issue(raw: dict, setting_id: str) -> Issue | None:
    match = MARKER_RE.search(raw.get("body") or "")
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return None
    if data.get("id") != setting_id or not re.fullmatch(r"[0-9a-f]{40}", str(data.get("sha", ""))):
        return None
    return Issue(number=raw["number"], sha=data["sha"], orgs=tuple(data.get("orgs") or ()), url=raw.get("url", ""))


def open_issues(raw_issues: list[dict], setting_id: str) -> list[Issue]:
    """Open issues with the marker, oldest first. Normally one; more only if
    an earlier run failed between opening a new issue and closing the old."""
    found = (parse_issue(r, setting_id) for r in raw_issues)
    return sorted((i for i in found if i), key=lambda i: i.number)


def completed(raw_issues: list[dict], setting_id: str) -> list[Issue]:
    """Issues closed as completed, newest first: what has been pasted."""
    done = [r for r in raw_issues if (r.get("stateReason") or "").upper() == "COMPLETED"]
    done.sort(key=lambda r: r.get("closedAt") or "", reverse=True)
    found = (parse_issue(r, setting_id) for r in done)
    return [i for i in found if i]


def fence(text: str, lang: str = "") -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{lang}\n{text.rstrip(chr(10))}\n{ticks}"


def render_template(template: str, values: dict[str, str]) -> str:
    def fill(match: re.Match) -> str:
        name = match.group(1)
        if name not in values:
            raise KeyError(f"unknown placeholder {{{{ {name} }}}}")
        return values[name]

    return PLACEHOLDER_RE.sub(fill, template)


def render_body(
    setting: Setting,
    repo: str,
    sha: str,
    due: list[Org],
    changed: bool,
    baseline: Issue | None,
    steps_template: str,
    content: bytes,
) -> str:
    short = sha[:7]
    server = f"https://github.com/{repo}"
    if not changed:
        what = f"nothing; {', '.join(o.name for o in due)} {'is' if len(due) == 1 else 'are'} new to the org list"
    elif baseline:
        what = f"[`{baseline.sha[:7]}...{short}`]({server}/compare/{baseline.sha}...{sha}) (since the last paste, #{baseline.number})"
    else:
        what = f"[`{short}`]({server}/commit/{sha}) (nothing pasted through an issue yet)"
    steps = render_template(
        steps_template,
        {
            "short": short,
            "file_url": f"{server}/blob/{sha}/{setting.content}",
            "checklist": "\n".join(f"   - [ ] **{o.name}**: {o.where}" for o in due),
            "content_block": fence(STAMP_RE.sub(short, content.decode("utf-8")), "json"),
        },
    )
    marker = json.dumps({"id": setting.id, "sha": sha, "orgs": [o.name for o in due]}, separators=(",", ":"))
    return "\n".join(
        [
            f"<!-- org-settings {marker} -->",
            f"The {setting.name} on `main` need pasting into: {', '.join(o.name for o in due)}.",
            "",
            f"- **What changed:** {what}",
            "",
            "## Steps",
            "",
            steps.rstrip("\n"),
            "",
            "## Done",
            "",
            "Close this issue as **completed** once every box is ticked: that records these orgs as having "
            f"`{short}`. Don't close it as not planned; that's for issues a newer one replaced.",
            "",
        ]
    )


class Git:
    def last_change(self, sha: str, path: str) -> str | None:
        """The newest commit at or before sha that touched path: what the
        issue pins, so it names the change, not whatever main's tip is."""
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", sha, "--", path], capture_output=True, text=True, check=True
        )
        return result.stdout.strip() or None

    def file_at(self, sha: str, path: str) -> bytes | None:
        result = subprocess.run(["git", "show", f"{sha}:{path}"], capture_output=True, check=False)
        return result.stdout if result.returncode == 0 else None


class GitHub:
    def __init__(self, repo: str) -> None:
        self.repo = repo

    def _gh(self, *args: str) -> str:
        return subprocess.run(["gh", *args, "-R", self.repo], capture_output=True, text=True, check=True).stdout

    def issues(self, state: str) -> list[dict]:
        # One issue per change, so the history stays in reach for years.
        out = self._gh(
            "issue", "list", "--label", LABEL, "--state", state, "--limit", "5000",
            "--json", "number,body,url,stateReason,closedAt,author",
        )
        return [r for r in json.loads(out) if by_workflow(r)]

    def ensure_label(self) -> None:
        subprocess.run(
            ["gh", "label", "create", LABEL, "-R", self.repo, "--color", "5319e7", "--force",
             "--description", "Claude Code managed settings to paste by hand (agents/org/README.md)"],
            capture_output=True, check=True,
        )

    def create(self, title: str, body: str) -> Issue:
        url = self._gh("issue", "create", "--title", title, "--body", body, "--label", LABEL).strip()
        return Issue(number=int(url.rsplit("/", 1)[1]), sha="", orgs=(), url=url)

    def lock(self, number: int) -> None:
        self._gh("issue", "lock", str(number))

    def close(self, number: int, comment: str) -> None:
        self._gh("issue", "close", str(number), "--reason", "not planned", "--comment", comment)


def run(setting: Setting, root: Path, repo: str, sha: str, git, github, dry_run: bool, notify=lambda o: None) -> Outcome:
    """notify is called right after the issue is filed, before anything else
    can fail, so a GitHub error later in the run doesn't lose its Slack post."""
    pin = git.last_change(sha, setting.content)
    content = git.file_at(pin, setting.content) if pin else None
    if content is None:
        return Outcome("skip", f"{setting.content} doesn't exist at {sha[:7]}")

    done = completed(github.issues("closed"), setting.id)
    # Each org's latest paste is the newest completed issue that lists it; an
    # older issue that happens to match (a revert) says nothing about today.
    have: set[str] = set()
    seen: set[str] = set()
    for issue in done:
        fresh = [org for org in issue.orgs if org not in seen]
        seen.update(fresh)
        if fresh and same(content, git.file_at(issue.sha, setting.content)):
            have.update(fresh)
    due = [o for o in setting.orgs if o.name not in have]
    changed = not have
    baseline = done[0] if done else None

    still_open = open_issues(github.issues("open"), setting.id)
    newest = still_open[-1] if still_open else None
    outcome = Outcome("skip", "every org has it", orgs=[o.name for o in due], changed=changed, issue=newest)

    def close(issues: list[Issue], comment: str) -> None:
        for issue in issues:
            if not dry_run:
                github.close(issue.number, comment)
            outcome.closed.append(issue.number)

    if not due:
        if still_open:
            outcome.action, outcome.reason = "close", "every org has it"
            close(still_open, f"No longer needed: every org has `{pin[:7]}`.")
        return outcome

    if newest and same(content, git.file_at(newest.sha, setting.content)) and set(newest.orgs) == set(outcome.orgs):
        outcome.action, outcome.reason = "leave", f"#{newest.number} already covers it"
        close(still_open[:-1], f"Superseded by #{newest.number}.")
        return outcome

    template = (root / setting.steps).read_text(encoding="utf-8")
    outcome.action = "file"
    outcome.reason = "changed since the last paste" if changed and baseline else ("nothing pasted yet" if changed else "new org")
    outcome.title = f"Paste the {setting.name} into {', '.join(outcome.orgs)} ({pin[:7]})"
    outcome.body = render_body(setting, repo, pin, due, changed, baseline, template, content)
    if len(outcome.body) > MAX_BODY:
        raise ValueError(f"the issue body is {len(outcome.body)} characters; GitHub takes at most 65,536")
    if dry_run:
        outcome.issue = None
        close(still_open, "Superseded by the new issue.")
        return outcome
    github.ensure_label()
    # New issue first: a failure before the close leaves two open, never none,
    # and the next run closes the extra one.
    outcome.issue = github.create(outcome.title, outcome.body)
    notify(outcome)
    # Locked, only collaborators can comment, so no one else can post a
    # "corrected" JSON beside the one to paste. Best effort, like Slack.
    try:
        github.lock(outcome.issue.number)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"::warning::Couldn't lock #{outcome.issue.number}: {error}")
    close(still_open, f"Superseded by #{outcome.issue.number}.")
    return outcome


def slack_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def slack_text(setting: Setting, repo: str, outcome: Outcome) -> str:
    """One line that says which repo and what to do, since other repos post as
    the same Slack app. Slack links the bare URL itself."""
    what = "changed" if outcome.changed else ("for a new org" if len(outcome.orgs) == 1 else "for new orgs")
    orgs = ", ".join(outcome.orgs)
    return slack_escape(f"{repo}: {setting.name} {what}. Paste into {orgs}: ") + outcome.issue.url


def post_to_slack(text: str, token: str, channel: str, opener=urllib.request.urlopen) -> None:
    """Best effort: a missing or malformed token or channel, or a Slack error,
    is a warning, never a failure."""
    if not TOKEN_RE.match(token or "") or not CHANNEL_RE.match(channel or ""):
        print("::warning::SLACK_BOT_TOKEN or SLACK_CHANNEL_ID is missing or malformed; nothing posted to Slack")
        return
    payload = {"channel": channel, "text": text, "unfurl_links": False, "unfurl_media": False}
    request = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json; charset=utf-8", "Authorization": f"Bearer {token}"},
    )
    try:
        with opener(request, timeout=20) as response:
            result = json.load(response)
    # HTTPException covers a truncated reply (IncompleteRead), which is
    # neither an OSError nor a ValueError.
    except (OSError, ValueError, http.client.HTTPException) as error:
        print(f"::warning::Couldn't reach Slack for {channel}: {error}")
        return
    if not isinstance(result, dict) or not result.get("ok"):
        error = result.get("error") if isinstance(result, dict) else result
        print(f"::warning::Slack didn't take the message for {channel}: {error}")


def summary(outcome: Outcome, dry_run: bool) -> str:
    what = {"file": "file an issue", "leave": "leave the open issue", "skip": "nothing to do", "close": "close the open issue"}
    detail = f" #{outcome.issue.number}" if outcome.action == "file" and outcome.issue else ""
    orgs = f" for {', '.join(outcome.orgs)}" if outcome.action in ("file", "leave") else ""
    closed = (", closed " + ", ".join(f"#{n}" for n in outcome.closed)) if outcome.closed else ""
    lines = [
        "## Org settings" + (" (dry run, nothing filed)" if dry_run else ""),
        "",
        f"- {what[outcome.action]}{detail}{orgs}{closed} ({outcome.reason})",
    ]
    if outcome.body and dry_run:
        lines += ["", fence(outcome.body, "markdown")]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sha", required=True, help="the commit to compare; the workflow passes main's tip")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "GaryRudolph/public"))
    args = parser.parse_args(argv)

    root = Path.cwd()
    setting = load_registry(root / REGISTRY)
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    channel = os.environ.get("SLACK_CHANNEL_ID", "")

    def notify(outcome: Outcome) -> None:
        post_to_slack(slack_text(setting, args.repo, outcome), token, channel)

    outcome = run(setting, root, args.repo, args.sha, Git(), GitHub(args.repo), args.dry_run, notify)

    text = summary(outcome, args.dry_run)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
