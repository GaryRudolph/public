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


class UnsafeFlags(unittest.TestCase):
    """A command passing --output, --pre or --upload-pack is never proposed,
    whatever its name says, whether the flag is in the command text or in the
    recipe or script body (r1.f4)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / ".git").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        f = self.repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)

    def scan_repo(self):
        res = scan.analyze_repo(self.repo, {h: [] for h in scan.HARNESSES}, self.repo)
        proposed = {e["segment"]: e["class"] for e in res["group1"] + res["group2"]}
        excluded = {e["segment"]: e["class"] for e in res["excluded"]}
        unclassified = {e["segment"] for e in res["unclassified"]}
        return proposed, excluded, unclassified

    def assertNeverProposed(self, seg, proposed, excluded, unclassified):
        self.assertNotIn(seg, proposed)
        self.assertNotIn(seg, unclassified)
        self.assertEqual(excluded.get(seg), scan.DESTRUCTIVE, seg)

    def test_makefile_test_target_with_output(self):
        for cmd in ("git log --output=/tmp/x", "git log --output /tmp/x"):
            self.write("Makefile", "test:\n\t%s\n" % cmd)
            self.assertNeverProposed("make test", *self.scan_repo())

    def test_script_with_pre(self):
        self.write("scripts/check.sh", "#!/usr/bin/env bash\nrg --pre cat TODO .\n")
        self.assertNeverProposed("bash scripts/check.sh", *self.scan_repo())

    def test_makefile_target_with_upload_pack(self):
        self.write("Makefile", "check:\n\tgit fetch --upload-pack=x origin\n")
        self.assertNeverProposed("make check", *self.scan_repo())

    def test_package_json_lint_script_with_pre(self):
        self.write("package.json", json.dumps({"scripts": {"lint": "rg --pre x TODO src"}}))
        self.assertNeverProposed("npm run lint", *self.scan_repo())

    def test_flag_in_the_command_text(self):
        for text in ("git diff --output=/tmp/x", "rg --pre cat x", "git fetch --upload-pack=x"):
            cls, _ = scan._classify_text(text)
            self.assertEqual(cls, scan.DESTRUCTIVE, text)

    def test_similar_flags_classify_as_before(self):
        self.write("Makefile",
                   "lint:\n\truff check --output-format=json .\n"
                   "test:\n\tnpm --prefix web test\n"
                   "check:\n\tcargo test --pre-release\n")
        proposed, excluded, _ = self.scan_repo()
        for seg in ("make lint", "make test", "make check"):
            self.assertEqual(proposed.get(seg), scan.BUILD, seg)
            self.assertNotIn(seg, excluded)
        for text, want in (("test", scan.BUILD), ("lint", scan.BUILD)):
            self.assertEqual(scan._classify_text(text, "ruff check --output-format=json .")[0], want)
            self.assertEqual(scan._classify_text(text, "npm --prefix web test")[0], want)
            self.assertEqual(scan._classify_text(text, "cargo test --pre-release")[0], want)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
