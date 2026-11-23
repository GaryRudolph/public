"""Render-then-scan tests for the allowlist scout: what render.py writes for
Cursor CLI must allow exactly the approved command, and scan.py must read it
back as covering only that command. Stdlib only."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


render = load("render")
scan = load("scan")


def render_cli(repo, segment, harness="cursor_cli"):
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "render.py"), "--repo", str(repo),
         "--harness", harness, segment],
        capture_output=True, text=True)


def allow(repo):
    return json.loads((repo / ".cursor" / "cli.json").read_text())["permissions"]["allow"]


def covers(repo, command):
    prefixes = scan.permissions_allow_prefixes(repo / ".cursor" / "cli.json")
    return scan.covered_by(command, prefixes)[0]


class RenderThenScan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / ".git").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_make_test_is_exact(self):
        self.assertEqual(render_cli(self.repo, "make test").returncode, 0)
        self.assertEqual(allow(self.repo), ["Shell(make:test)"])
        self.assertTrue(covers(self.repo, "make test"))
        for other in ("make release", "make deploy", "make testflight",
                      "make test release", "make"):
            self.assertFalse(covers(self.repo, other), other)

    def test_npm_run_build_does_not_cover_publish(self):
        render_cli(self.repo, "npm run build")
        self.assertEqual(allow(self.repo), ["Shell(npm:run build)"])
        self.assertTrue(covers(self.repo, "npm run build"))
        for other in ("npm publish", "npm run deploy", "npm run build-all", "npm"):
            self.assertFalse(covers(self.repo, other), other)

    def test_one_word_segment_is_bare_base(self):
        render_cli(self.repo, "pytest")
        self.assertEqual(allow(self.repo), ["Shell(pytest)"])

    def test_extra_spaces_are_normalized(self):
        self.assertEqual(render._shell_token("make   test"), "Shell(make:test)")

    def test_quoted_args_keep_their_whitespace(self):
        seg = 'npm run "test  unit"'
        self.assertEqual(render._shell_token(seg), 'Shell(npm:run "test  unit")')
        render_cli(self.repo, seg)
        self.assertTrue(covers(self.repo, seg))
        self.assertFalse(covers(self.repo, 'npm run "test unit"'))

    def test_glob_segment_is_skipped_and_says_so(self):
        for seg in ("make test*", "git log ?"):
            r = render_cli(self.repo, seg)
            self.assertEqual(r.returncode, 0)
            self.assertIn("skip:", r.stderr)
            self.assertIn("skipped: %s -> cursor_cli" % seg, r.stderr)
            self.assertNotIn("ok:", r.stderr)
        self.assertFalse((self.repo / ".cursor" / "cli.json").exists())

    def test_colon_in_command_is_skipped(self):
        r = render_cli(self.repo, "./run:all now")
        self.assertIn("skipped:", r.stderr)
        self.assertFalse((self.repo / ".cursor" / "cli.json").exists())

    def test_other_harnesses_still_written(self):
        render_cli(self.repo, "make test", "claude")
        render_cli(self.repo, "make test", "cursor_ide")
        claude = json.loads((self.repo / ".claude" / "settings.json").read_text())
        self.assertEqual(claude["permissions"]["allow"], ["Bash(make test:*)"])
        ide = json.loads((self.repo / ".cursor" / "permissions.json").read_text())
        self.assertEqual(ide["terminalAllowlist"], ["make test"])

    def test_render_is_idempotent(self):
        render_cli(self.repo, "make test")
        render_cli(self.repo, "make test")
        self.assertEqual(allow(self.repo), ["Shell(make:test)"])


class Unwrap(unittest.TestCase):
    def test_forms(self):
        u = scan._unwrap_token
        self.assertEqual(u("Shell(make:*)"), "make")
        self.assertEqual(u("Bash(make test:*)"), "make test")
        self.assertEqual(u("Shell(git)"), "git")
        self.assertEqual(u("Shell(make:test)"), "make test")
        self.assertIsNone(u("Shell(make:test*)"))
        self.assertIsNone(u("Shell(make:te?t)"))
        self.assertIsNone(u("Mcp(datadog:*)"))
        self.assertEqual(u("make test"), "make test")

    def test_legacy_broad_rule_still_reads_as_broad(self):
        covered, entry, kind = scan.covered_by("make release", [scan._unwrap_token("Shell(make:*)")])
        self.assertEqual((covered, entry, kind), (True, "make", "broad"))

    def test_broad_rule_is_reported_beside_its_exact_twin(self):
        ents = [scan._unwrap_token("Shell(make:test)"),
                scan._unwrap_token("Shell(make:*)")]
        self.assertEqual(scan.covered_by("make test", ents), (True, "make", "broad"))
        self.assertEqual(scan.covered_by("make test", list(reversed(ents)))[2], "broad")

    def test_exact_entry_covers_only_itself(self):
        ents = [scan._unwrap_token("Shell(make:test)")]
        self.assertEqual(scan.covered_by("make test", ents)[2], "exact")
        self.assertFalse(scan.covered_by("make test foo", ents)[0])


class ClaudeConfigDirs(unittest.TestCase):
    HOME = Path("/home/u")

    def dirs(self, env):
        return scan.claude_config_dirs(env, self.HOME)

    def test_list_in_order_without_duplicates_plus_session(self):
        env = {"CLAUDE_CONFIG_DIRS": "/a/.claude-lolay:/b/.claude-ap::/a/.claude-lolay",
               "CLAUDE_CONFIG_DIR": "/a/.claude-lolay"}
        self.assertEqual(self.dirs(env), (
            "CLAUDE_CONFIG_DIRS",
            [Path("/a/.claude-lolay"), Path("/b/.claude-ap")],
            Path("/a/.claude-lolay")))

    def test_relative_and_tilde_entries_are_skipped(self):
        env = {"CLAUDE_CONFIG_DIRS": "rel/dir:~/.claude-x:/abs/dir"}
        self.assertEqual(self.dirs(env)[1], [Path("/abs/dir")])

    def test_session_dir_when_no_list(self):
        for env in ({"CLAUDE_CONFIG_DIR": "/c/.claude-x"},
                    {"CLAUDE_CONFIG_DIRS": " : ", "CLAUDE_CONFIG_DIR": "/c/.claude-x"}):
            self.assertEqual(self.dirs(env), ("session", [], Path("/c/.claude-x")))

    def test_unset_or_relative_session_dir_is_home_claude(self):
        for env in ({}, {"CLAUDE_CONFIG_DIR": ".claude-lolay"},
                    {"CLAUDE_DATA_HOME": "/old/home"}):  # no longer read
            self.assertEqual(self.dirs(env), ("session", [], self.HOME / ".claude"))

    def test_baseline_keeps_session_and_drops_missing_listed_dirs(self):
        with tempfile.TemporaryDirectory() as t:
            here, gone = Path(t) / "here", Path(t) / "gone"
            here.mkdir()
            session = Path(t) / "session-not-created"
            self.assertEqual(scan.claude_baseline_dirs([here, gone, session], session),
                             ([here, session], [gone]))


class CoveredByAll(unittest.TestCase):
    LOLAY = ["make test", "make lint"]
    AP = ["make lint"]

    def test_command_in_only_one_dir_is_not_covered(self):
        self.assertEqual(scan.covered_by_all("make test", [self.LOLAY, self.AP]),
                         (False, None, None))

    def test_command_in_every_dir_is_covered(self):
        self.assertEqual(scan.covered_by_all("make lint", [self.LOLAY, self.AP]),
                         (True, "make lint", "exact"))

    def test_repo_entry_covers_in_every_dir(self):
        repo = ["make test"]
        sets = [g + repo for g in (self.LOLAY, self.AP)]
        self.assertTrue(scan.covered_by_all("make test", sets)[0])

    def test_broad_only_when_every_dir_is_broad(self):
        self.assertEqual(scan.covered_by_all("make lint", [self.AP, ["make"]]),
                         (True, "make lint", "exact"))
        self.assertEqual(scan.covered_by_all("make lint", [["make"], ["make"]]),
                         (True, "make", "broad"))

    def test_single_dir_matches_covered_by(self):
        for seg in ("make test", "make build"):
            self.assertEqual(scan.covered_by_all(seg, [self.LOLAY]),
                             scan.covered_by(seg, self.LOLAY))

    def test_no_dirs_is_not_covered(self):
        self.assertFalse(scan.covered_by_all("make lint", [])[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
