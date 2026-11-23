"""Tests for agents/org/settings_issue.py, with fake git, GitHub and Slack.

Run: python3 -m unittest discover -s agents/org/tests
"""

from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ORG_DIR = Path(__file__).resolve().parents[1]
REPO = ORG_DIR.parents[1]
sys.path.insert(0, str(ORG_DIR))

import settings_issue as si  # noqa: E402

CONTENT = "agents/org/claude-managed-settings.json"
A = "a" * 40
B = "b" * 40
C = "c" * 40
V1 = b'{"permissions": {"allow": ["Bash(ls)"]}, "settings-commit": "{{ commit }}"}\n'
V2 = b'{"permissions": {"allow": ["Bash(ls)", "Bash(pwd)"]}, "settings-commit": "{{ commit }}"}\n'
LOLAY = si.Org("Lolay", "claude.ai > Lolay")
NEXT = si.Org("Next & Co", "claude.ai > Next")


def setting(*orgs: si.Org) -> si.Setting:
    return si.Setting(
        id="claude-managed-settings",
        name="Claude Code managed settings",
        content=CONTENT,
        steps="steps.md",
        orgs=orgs or (LOLAY,),
    )


def marker(sha: str, orgs: list[str], id_: str = "claude-managed-settings") -> str:
    return "<!-- org-settings " + json.dumps({"id": id_, "sha": sha, "orgs": orgs}, separators=(",", ":")) + " -->\nbody"


def raw(number: int, sha: str, orgs: list[str], reason: str = "", closed_at: str = "") -> dict:
    return {"number": number, "body": marker(sha, orgs), "url": f"https://x/issues/{number}",
            "stateReason": reason, "closedAt": closed_at}


class FakeGit:
    def __init__(self, files: dict[str, bytes], tip: str) -> None:
        self.files = files  # sha -> content of CONTENT at that sha
        self.tip = tip

    def last_change(self, sha: str, path: str) -> str | None:
        return self.tip if path == CONTENT else None

    def file_at(self, sha: str, path: str) -> bytes | None:
        return self.files.get(sha) if path == CONTENT else None


class FakeGitHub:
    def __init__(self, open_: list[dict] | None = None, closed: list[dict] | None = None) -> None:
        self.open = open_ or []
        self.closed = closed or []
        self.created: list[tuple[str, str]] = []
        self.closed_now: list[tuple[int, str]] = []
        self.labels = 0
        self.locked: list[int] = []
        self.lock_fails = False

    def issues(self, state: str) -> list[dict]:
        return self.open if state == "open" else self.closed

    def ensure_label(self) -> None:
        self.labels += 1

    def create(self, title: str, body: str) -> si.Issue:
        self.created.append((title, body))
        return si.Issue(number=100, sha="", orgs=(), url="https://github.com/GaryRudolph/public/issues/100")

    def lock(self, number: int) -> None:
        if self.lock_fails:
            raise si.subprocess.CalledProcessError(1, ["gh", "issue", "lock"])
        self.locked.append(number)

    def close(self, number: int, comment: str) -> None:
        self.closed_now.append((number, comment))


class Run(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "steps.md").write_text("Paste {{ short }}:\n\n{{ checklist }}\n\n{{ content_block }}\n")
        self.notified: list[si.Outcome] = []

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def go(self, s: si.Setting, git: FakeGit, gh: FakeGitHub, dry_run: bool = False) -> si.Outcome:
        return si.run(s, self.root, "GaryRudolph/public", git.tip, git, gh, dry_run, self.notified.append)

    def test_first_run_files_for_every_org(self) -> None:
        gh = FakeGitHub()
        o = self.go(setting(LOLAY, NEXT), FakeGit({A: V1}, A), gh)
        self.assertEqual(o.action, "file")
        self.assertEqual(o.orgs, ["Lolay", "Next & Co"])
        self.assertTrue(o.changed)
        title, body = gh.created[0]
        self.assertEqual(title, "Paste the Claude Code managed settings into Lolay, Next & Co (aaaaaaa)")
        self.assertIn('"orgs":["Lolay","Next & Co"]', body)
        self.assertIn("- [ ] **Lolay**: claude.ai > Lolay", body)
        self.assertIn('"settings-commit": "aaaaaaa"', body)  # the stamp is filled in
        self.assertNotIn("{{", body)
        self.assertEqual(len(self.notified), 1)
        self.assertEqual(gh.labels, 1)
        self.assertEqual(gh.locked, [100])

    def test_an_issue_that_wont_lock_is_withdrawn_and_the_run_fails(self) -> None:
        gh = FakeGitHub(open_=[raw(7, B, ["Lolay"])])
        gh.lock_fails = True
        with self.assertRaises(RuntimeError):
            self.go(setting(), FakeGit({A: V2, B: V1}, A), gh)
        self.assertEqual([n for n, _ in gh.closed_now], [100])  # the new one, not #7
        self.assertEqual(self.notified, [])

    def test_nothing_when_every_org_has_it(self) -> None:
        gh = FakeGitHub(closed=[raw(5, B, ["Lolay"], "COMPLETED", "2026-11-01")])
        o = self.go(setting(), FakeGit({A: V1, B: V1}, A), gh)
        self.assertEqual(o.action, "skip")
        self.assertEqual(gh.created, [])
        self.assertEqual(self.notified, [])

    def test_new_org_files_for_it_alone(self) -> None:
        gh = FakeGitHub(closed=[raw(5, A, ["Lolay"], "COMPLETED", "2026-11-01")])
        o = self.go(setting(LOLAY, NEXT), FakeGit({A: V1}, A), gh)
        self.assertEqual((o.action, o.orgs, o.changed), ("file", ["Next & Co"], False))
        body = gh.created[0][1]
        self.assertIn("new to the org list", body)
        self.assertNotIn("**Lolay**", body)

    def test_change_files_for_every_org_and_supersedes_the_open_issue(self) -> None:
        gh = FakeGitHub(
            open_=[raw(7, B, ["Next & Co"])],
            closed=[raw(5, B, ["Lolay"], "COMPLETED", "2026-11-01")],
        )
        o = self.go(setting(LOLAY, NEXT), FakeGit({A: V2, B: V1}, A), gh)
        self.assertEqual((o.action, o.orgs, o.changed), ("file", ["Lolay", "Next & Co"], True))
        self.assertIn(f"compare/{B}...{A}", gh.created[0][1])
        self.assertEqual(gh.closed_now, [(7, "Superseded by #100.")])

    def test_a_due_org_with_an_older_paste_is_a_change_not_a_new_org(self) -> None:
        # Lolay has the current V2 (#6); Next & Co's last paste was V1 (#5).
        gh = FakeGitHub(closed=[
            raw(5, B, ["Next & Co"], "COMPLETED", "2026-11-01"),
            raw(6, A, ["Lolay"], "COMPLETED", "2026-11-02"),
        ])
        o = self.go(setting(LOLAY, NEXT), FakeGit({A: V2, B: V1}, A), gh)
        self.assertEqual((o.action, o.orgs, o.changed), ("file", ["Next & Co"], True))
        self.assertIn(f"compare/{B}...{A}", gh.created[0][1])

    def test_orgs_add_up_across_completed_issues(self) -> None:
        gh = FakeGitHub(closed=[
            raw(5, B, ["Lolay"], "COMPLETED", "2026-11-01"),
            raw(6, A, ["Next & Co"], "COMPLETED", "2026-11-02"),
        ])
        o = self.go(setting(LOLAY, NEXT), FakeGit({A: V1, B: V1}, A), gh)
        self.assertEqual(o.action, "skip")

    def test_a_revert_asks_again_when_the_org_pasted_something_newer(self) -> None:
        # Pasted V1 (#5), then V2 (#6); main is back on V1: Lolay has V2.
        gh = FakeGitHub(closed=[
            raw(5, C, ["Lolay"], "COMPLETED", "2026-11-01"),
            raw(6, B, ["Lolay"], "COMPLETED", "2026-11-02"),
        ])
        o = self.go(setting(), FakeGit({A: V1, B: V2, C: V1}, A), gh)
        self.assertEqual((o.action, o.orgs, o.changed), ("file", ["Lolay"], True))
        self.assertIn(f"compare/{B}...{A}", gh.created[0][1])

    def test_not_planned_never_counts(self) -> None:
        gh = FakeGitHub(closed=[raw(5, A, ["Lolay"], "NOT_PLANNED", "2026-11-01")])
        o = self.go(setting(), FakeGit({A: V1}, A), gh)
        self.assertEqual((o.action, o.reason), ("file", "nothing pasted yet"))

    def test_leave_the_open_issue_and_close_leftovers(self) -> None:
        gh = FakeGitHub(open_=[raw(3, A, ["Lolay"]), raw(4, A, ["Lolay"])])
        o = self.go(setting(), FakeGit({A: V1}, A), gh)
        self.assertEqual(o.action, "leave")
        self.assertEqual(gh.created, [])
        self.assertEqual(gh.closed_now, [(3, "Superseded by #4.")])

    def test_open_issue_for_other_orgs_is_replaced(self) -> None:
        gh = FakeGitHub(open_=[raw(4, A, ["Lolay"])])
        o = self.go(setting(LOLAY, NEXT), FakeGit({A: V1}, A), gh)
        self.assertEqual(o.action, "file")
        self.assertEqual(gh.closed_now, [(4, "Superseded by #100.")])

    def test_close_when_content_matches_what_was_pasted_again(self) -> None:
        gh = FakeGitHub(open_=[raw(8, B, ["Lolay"])], closed=[raw(5, C, ["Lolay"], "COMPLETED", "2026-11-01")])
        o = self.go(setting(), FakeGit({A: V1, B: V2, C: V1}, A), gh)
        self.assertEqual(o.action, "close")
        self.assertEqual([n for n, _ in gh.closed_now], [8])

    def test_dry_run_changes_nothing(self) -> None:
        gh = FakeGitHub(open_=[raw(7, B, ["Lolay"])])
        o = self.go(setting(), FakeGit({A: V2, B: V1}, A), gh, dry_run=True)
        self.assertEqual(o.action, "file")
        self.assertTrue(o.body)
        self.assertEqual((gh.created, gh.closed_now, gh.labels, gh.locked, self.notified), ([], [], 0, [], []))
        self.assertIn("dry run", si.summary(o, True))

    def test_markers_for_other_ids_and_bad_markers_are_ignored(self) -> None:
        other = {"number": 9, "body": marker(A, ["Lolay"], "something-else"), "stateReason": "COMPLETED"}
        broken = {"number": 10, "body": "<!-- org-settings {not json} -->", "stateReason": "COMPLETED"}
        gh = FakeGitHub(closed=[other, broken])
        o = self.go(setting(), FakeGit({A: V1}, A), gh)
        self.assertEqual(o.action, "file")

    def test_body_too_big_for_an_issue_stops(self) -> None:
        big = json.dumps({"permissions": {"allow": ["Bash(x)"] * 9000}}).encode()
        with self.assertRaises(ValueError):
            self.go(setting(), FakeGit({A: big}, A), FakeGitHub())

    def test_missing_file_skips(self) -> None:
        o = self.go(setting(), FakeGit({}, A), FakeGitHub())
        self.assertEqual(o.action, "skip")


class Authors(unittest.TestCase):
    def test_only_the_workflow_bot_counts(self) -> None:
        self.assertTrue(si.by_workflow({"author": {"login": "app/github-actions", "is_bot": True}}))
        self.assertTrue(si.by_workflow({"author": {"login": "github-actions[bot]", "is_bot": True}}))
        self.assertFalse(si.by_workflow({"author": {"login": "someone", "is_bot": False}}))
        self.assertFalse(si.by_workflow({"author": {"login": "app/github-actions", "is_bot": False}}))
        self.assertFalse(si.by_workflow({"author": {"login": "app/other-bot", "is_bot": True}}))
        self.assertFalse(si.by_workflow({}))


class Slack(unittest.TestCase):
    def outcome(self, changed: bool, orgs: list[str]) -> si.Outcome:
        return si.Outcome("file", "", orgs=orgs, changed=changed,
                          issue=si.Issue(100, "", (), "https://github.com/GaryRudolph/public/issues/100"))

    def test_text_names_the_repo_and_what_to_do(self) -> None:
        s = setting()
        self.assertEqual(
            si.slack_text(s, "GaryRudolph/public", self.outcome(True, ["Lolay"])),
            "GaryRudolph/public: Claude Code managed settings changed. Paste into Lolay: "
            "https://github.com/GaryRudolph/public/issues/100",
        )
        self.assertEqual(
            si.slack_text(s, "GaryRudolph/public", self.outcome(False, ["Next & Co", "<b>"])),
            "GaryRudolph/public: Claude Code managed settings for new orgs. Paste into Next &amp; Co, &lt;b&gt;: "
            "https://github.com/GaryRudolph/public/issues/100",
        )
        self.assertIn("for a new org. Paste into Next &amp; Co:",
                      si.slack_text(s, "GaryRudolph/public", self.outcome(False, ["Next & Co"])))

    def test_post_sends_the_text_to_the_channel(self) -> None:
        sent = []

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(request, timeout):
            sent.append((request.full_url, request.get_header("Authorization"), json.loads(request.data)))
            return Response(b'{"ok": true}')

        si.post_to_slack("hi", "xoxb-1-abc", "C0CHEJ64U93", opener)
        url, auth, payload = sent[0]
        self.assertEqual(url, "https://slack.com/api/chat.postMessage")
        self.assertEqual(auth, "Bearer xoxb-1-abc")
        self.assertEqual((payload["channel"], payload["text"]), ("C0CHEJ64U93", "hi"))

    def test_missing_token_or_bad_channel_warns_and_sends_nothing(self) -> None:
        def opener(*a, **k):
            raise AssertionError("no request expected")

        for token, channel in (("", "C0CHEJ64U93"), ("xoxb-1", ""), ("xoxp-1", "C0CHEJ64U93"), ("xoxb-1", "#infra")):
            out = io.StringIO()
            sys.stdout, saved = out, sys.stdout
            try:
                si.post_to_slack("hi", token, channel, opener)
            finally:
                sys.stdout = saved
            self.assertIn("::warning::", out.getvalue())

    def test_slack_errors_are_warnings(self) -> None:
        def down(*a, **k):
            raise OSError("down")

        out = io.StringIO()
        sys.stdout, saved = out, sys.stdout
        try:
            si.post_to_slack("hi", "xoxb-1", "C0CHEJ64U93", down)
        finally:
            sys.stdout = saved
        self.assertIn("Couldn't reach Slack", out.getvalue())


class RealFiles(unittest.TestCase):
    """The committed registry, steps and generated file work together."""

    def test_registry_loads_and_names_real_files(self) -> None:
        s = si.load_registry(REPO / si.REGISTRY)
        self.assertTrue((REPO / s.content).is_file())
        self.assertTrue((REPO / s.steps).is_file())
        self.assertIn("Lolay", [o.name for o in s.orgs])

    def test_real_body_renders_fully_and_fits(self) -> None:
        s = si.load_registry(REPO / si.REGISTRY)
        content = (REPO / s.content).read_bytes()
        body = si.render_body(s, "GaryRudolph/public", A, list(s.orgs), True, None,
                              (REPO / s.steps).read_text(), content)
        self.assertNotIn("{{", body)
        self.assertLess(len(body), si.MAX_BODY)
        block = re.search(r"```json\n(.*?)\n```", body, re.S).group(1)
        self.assertEqual(json.loads(block)["settings-commit"], A[:7])

    def test_workflow_triggers_on_the_registry_and_the_generated_file(self) -> None:
        s = si.load_registry(REPO / si.REGISTRY)
        workflow = (REPO / ".github/workflows/org-settings.yml").read_text()
        paths = re.findall(r"^\s+- (agents/\S+)\s*$", workflow, re.M)
        self.assertEqual(sorted(paths), sorted([s.content, si.REGISTRY]))


if __name__ == "__main__":
    unittest.main()
