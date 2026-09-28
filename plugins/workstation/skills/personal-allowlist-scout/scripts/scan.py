#!/usr/bin/env python3
"""Allowlist Scout — core scan engine.

Stdlib-only (Python 3.8+; no venv, no third-party deps). Generic: contains no
personal paths, org names, or repo names — both the agerpoint and personal
copies of this file are byte-identical.

What it does (current workspace only — never scans ~/Projects or any other
workspace):

  1. Enumerate the git repos reachable from the given roots (argv, else CWD),
     descending at most --max-depth levels and skipping build/vendor dirs.
  2. Per repo, detect the stack(s) and extract candidate commands from the
     build tooling (Makefile targets, package.json scripts, pyproject, go.mod,
     Cargo.toml, .csproj/.sln, Package.swift/xcodeproj, gradle, terraform,
     scripts/*).
  3. Classify each command by access/intent:
       Inspect / Build & test          -> proposable (safe to auto-run)
       Remote Write / Sensitive /
       Destructive / Long-running      -> never proposed (omitted, reason kept)
       Unclassified                    -> fail-closed fallback; emitted WITH
                                          its supporting evidence so the agent
                                          can deep-evaluate and reassign it.
  4. Compute per-harness coverage of each proposable command against the
     EXISTING allowlists (the single source of truth) — both the global files
     and the repo's own per-harness files — using true-prefix matching, where
     a broader existing entry suppresses a narrower candidate.
  5. Bucket survivors per repo into Group 1 (missing from every harness) and
     Group 2 (drift: present in some harnesses, missing in others).
  6. Flag global-promotion candidates (proposable commands recurring across
     >= 2 repos and not already covered by every global file).

Output: a tool-agnostic JSON proposal on stdout (consumed by the skill and by
render.py) plus an optional human-readable summary under .scratch/. Neither is
a persisted source of truth — the harness allowlist files are. This engine is
allow-only: it never emits a denylist and never writes anything itself.

Harness allowlist locations (global paths overridable via the same env vars the
installer uses, which keeps this testable without touching the real home):

  cursor_ide  global $CURSOR_DATA_HOME/permissions.json  (terminalAllowlist)
              repo   <repo>/.cursor/permissions.json      (terminalAllowlist)
  cursor_cli  global $CURSOR_DATA_HOME/cli-config.json    (permissions.allow)
              repo   <repo>/.cursor/cli.json              (permissions.allow)
  claude      global $CLAUDE_DATA_HOME/settings.json      (permissions.allow)
              repo   <repo>/.claude/settings.json         (permissions.allow)
  gemini      global $GEMINI_DATA_HOME/policies/*.toml    (allow rules)
              repo   <repo>/.gemini/policies/*.toml       (allow rules)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Directories never descended into while enumerating repos or scanning.
SKIP_DIRS = {
    "node_modules", ".build", "build", "checkouts", "vendor", "external",
    "Pods", "DerivedData", "dist", "target", "out", ".git", ".venv", "venv",
    "__pycache__", ".gradle", ".idea", ".tox", "coverage",
}

DEFAULT_MAX_DEPTH = 2

# Access / intent classes (the class name IS the meaning).
INSPECT = "Inspect"
BUILD = "Build & test"
REMOTE = "Remote Write"
SENSITIVE = "Sensitive"
DESTRUCTIVE = "Destructive"
LONG = "Long-running"
UNCLASSIFIED = "Unclassified"

PROPOSE_CLASSES = {INSPECT, BUILD}
NEVER_CLASSES = {REMOTE, SENSITIVE, DESTRUCTIVE, LONG}

HARNESSES = ["cursor_ide", "cursor_cli", "claude", "gemini"]

# Words for the transient summary filename (no meaning; just a stable handle).
SUMMARY_WORDS = [
    "amber", "basalt", "cedar", "delta", "ember", "flint", "granite",
    "harbor", "indigo", "juniper", "kelp", "lumen", "marble", "nimbus",
    "onyx", "pewter", "quartz", "russet", "slate", "topaz",
]

# ---------------------------------------------------------------------------
# Classification keyword tables
# ---------------------------------------------------------------------------
# Body-level signals are high-precision regexes (anchored on real command
# tokens) so a stray word in a comment does not misfire. Name-level signals
# are exact token membership after splitting the name on non-alphanumerics.

REMOTE_BODY = [
    r"\bgit\s+push\b", r"\bgit\s+tag\b.*\bpush\b", r"\bscp\b", r"\brsync\b",
    r"\bssh\b\s+\S+", r"\bsftp\b", r"terraform\s+apply", r"terraform\s+destroy",
    r"kubectl\s+apply", r"kubectl\s+delete", r"helm\s+(install|upgrade|uninstall)",
    r"docker\s+push", r"(npm|pnpm|yarn)\s+publish", r"cargo\s+publish",
    r"twine\s+upload", r"firebase\s+deploy", r"\bgh\s+release\s+create",
    r"aws\s+s3\s+(cp|sync|mv|rm)", r"gcloud\s+\S+\s+deploy", r"\baz\s+\S+\s+(create|deploy)",
    r"xcrun\s+altool", r"xcrun\s+notarytool", r"fastlane\s+(pilot|deliver|release|match)",
    r"pod\s+trunk\s+push", r"netlify\s+deploy", r"vercel\s+(deploy|--prod)",
    r"databricks\s+\S+\s+(create|deploy|run|submit)", r"\bcurl\b[^|]*\s-X\s*(POST|PUT|PATCH|DELETE)",
]
SENSITIVE_BODY = [
    r"decrypt", r"gpg\s+-d\b", r"gpg\s+--decrypt", r"openssl\s+enc[^\n]*-d\b",
    r"openssl\s+rsautl[^\n]*-decrypt", r"sops\s+-d\b", r"sops\s+--decrypt",
    r"ansible-vault\s+(decrypt|view)", r"secrets?[-_ ](decrypt|export|print|show)",
    r"\bkeychain\b", r"security\s+find-", r"\.env\.enc\b", r"\bunseal\b",
    r"vault\s+(read|kv\s+get)", r"print[-_ ]?secret",
]
DESTRUCTIVE_BODY = [
    r"\brm\s+-[rf]", r"\bdd\s+if=", r"\bmkfs", r"\bsudo\b", r"\bfdisk\b",
    r"git\s+reset\s+--hard", r"git\s+clean\s+-[a-z]*[fd]", r"\bflash\b",
    r"\berase\b", r"\bdiskutil\b", r"\bchmod\s+-R\b", r">\s*/dev/",
]
LONG_BODY = [
    r"--watch\b", r"-w\b\s*$", r"\bnodemon\b", r"\bvite\b(?!\s+build)",
    r"next\s+dev", r"ng\s+serve", r"runserver", r"\bwatchexec\b",
    r"webpack(-dev)?-server", r"webpack\s+serve", r"livereload",
    r"\bhttp-server\b", r"\bserve\b", r"--hot\b", r"\btail\s+-[fF]\b",
    r"\bwatch\b\s", r"jekyll\s+serve", r"hugo\s+server", r"mkdocs\s+serve",
]

REMOTE_NAME = {
    "deploy", "publish", "release", "push", "testflight", "appstore",
    "notarize", "upload", "distribute", "promote", "ship", "sync", "prod",
    "production", "staging", "deliver", "pilot",
}
SENSITIVE_NAME = {
    "decrypt", "secrets", "secret", "keychain", "keystore", "creds",
    "credentials", "unseal", "vault",
}
DESTRUCTIVE_NAME = {
    "clean", "distclean", "mrproper", "nuke", "reset", "wipe", "purge",
    "erase", "init", "setup", "install", "bootstrap", "provision",
    "reinstall", "uninstall", "destroy",
}
LONG_NAME = {
    "dev", "serve", "server", "watch", "start", "run", "daemon", "up",
    "preview", "hot", "live", "watcher", "develop", "devserver",
}
BUILD_NAME = {
    "build", "test", "tests", "lint", "check", "compile", "fmt", "format",
    "typecheck", "tsc", "coverage", "cov", "bench", "ci", "verify",
    "validate", "audit", "analyze", "archive", "sign", "assemble",
    "package", "bundle", "precommit", "unit", "integration", "e2e", "spec",
    "snapshot", "clippy", "vet", "make",
}
INSPECT_NAME = {
    "help", "status", "list", "ls", "show", "info", "version", "env",
    "doctor", "print", "describe", "tree", "outdated", "why", "config",
    "which", "summary", "report", "stats",
}


def _classify_text(name: str, body: str = ""):
    """Return (class, reason). `name` is the human-facing command/target name;
    `body` is the recipe/script value used for high-precision unsafe signals."""
    body_l = (body or "").lower()

    for pat in SENSITIVE_BODY:
        m = re.search(pat, body_l)
        if m:
            return SENSITIVE, "body matched /%s/" % pat
    for pat in REMOTE_BODY:
        m = re.search(pat, body_l)
        if m:
            return REMOTE, "body matched /%s/" % pat
    for pat in DESTRUCTIVE_BODY:
        m = re.search(pat, body_l)
        if m:
            return DESTRUCTIVE, "body matched /%s/" % pat
    for pat in LONG_BODY:
        m = re.search(pat, body_l)
        if m:
            return LONG, "body matched /%s/" % pat

    tokens = [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]
    tset = set(tokens)
    if tset & REMOTE_NAME:
        return REMOTE, "name token in {%s}" % ",".join(sorted(tset & REMOTE_NAME))
    if tset & SENSITIVE_NAME:
        return SENSITIVE, "name token in {%s}" % ",".join(sorted(tset & SENSITIVE_NAME))
    if tset & DESTRUCTIVE_NAME:
        return DESTRUCTIVE, "name token in {%s}" % ",".join(sorted(tset & DESTRUCTIVE_NAME))
    if tset & LONG_NAME:
        return LONG, "name token in {%s}" % ",".join(sorted(tset & LONG_NAME))
    if tset & BUILD_NAME:
        return BUILD, "name token in {%s}" % ",".join(sorted(tset & BUILD_NAME))
    if tset & INSPECT_NAME:
        return INSPECT, "name token in {%s}" % ",".join(sorted(tset & INSPECT_NAME))
    return UNCLASSIFIED, "no confident signal in name or body"


# ---------------------------------------------------------------------------
# Small IO helpers
# ---------------------------------------------------------------------------

def read_text(path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def load_json_lenient(path):
    """json.load with a fallback that strips // and /* */ comments and trailing
    commas (real settings.json files are occasionally JSONC). Returns None on
    a hard failure rather than raising."""
    txt = read_text(path)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        pass
    no_block = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    no_line = re.sub(r"(?m)^\s*//.*$", "", no_block)
    no_trailing = re.sub(r",(\s*[}\]])", r"\1", no_line)
    try:
        return json.loads(no_trailing)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Harness allowlist parsing -> plain shell command prefixes (allow only)
# ---------------------------------------------------------------------------

def _unwrap_token(tok: str):
    """Normalize one permissions.allow token to a bare shell prefix.
    Handles Cursor CLI Shell(...) and Claude Bash(...) wrappers and the
    trailing :* argument wildcard. Returns None for non-shell tokens
    (Mcp(...), mcp__..., WebFetch(...))."""
    tok = tok.strip()
    if not tok:
        return None
    if tok.startswith(("Mcp(", "mcp__", "WebFetch(")):
        return None
    m = re.match(r"^(?:Shell|Bash)\((.*)\)$", tok)
    inner = m.group(1) if m else tok
    inner = inner.strip()
    if inner.endswith(":*"):
        inner = inner[:-2]
    inner = inner.strip()
    return inner or None


def cursor_ide_prefixes(path):
    data = load_json_lenient(path)
    if not isinstance(data, dict):
        return []
    arr = data.get("terminalAllowlist") or []
    return [s.strip() for s in arr if isinstance(s, str) and s.strip()]


def permissions_allow_prefixes(path):
    data = load_json_lenient(path)
    if not isinstance(data, dict):
        return []
    perms = data.get("permissions") or {}
    arr = perms.get("allow") or []
    out = []
    for tok in arr:
        if isinstance(tok, str):
            p = _unwrap_token(tok)
            if p:
                out.append(p)
    return out


def _toml_strings(value: str):
    """Extract the string literal(s) from a TOML value that is either a basic
    string or an inline array of basic strings (single-line)."""
    out = []
    for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', value):
        s = m.group(1).replace('\\"', '"').replace("\\\\", "\\")
        if s:
            out.append(s)
    return out


def gemini_allow_prefixes_from_text(text: str):
    """Parse `decision = "allow"` commandPrefix values out of a policy .toml.
    Tolerant of the simple [[rule]] shape this project renders and that users
    typically hand-write. commandRegex / argsPattern rules are ignored for
    coverage (a regex is not a prefix); deny / ask_user never count."""
    out = []
    blocks = re.split(r"(?m)^\s*\[\[\s*rule\s*\]\]\s*$", text)
    for b in blocks:
        dm = re.search(r'(?m)^\s*decision\s*=\s*"([^"]+)"', b)
        if not dm or dm.group(1) != "allow":
            continue
        cpm = re.search(r"(?m)^\s*commandPrefix\s*=\s*(.+?)\s*$", b)
        if not cpm:
            continue
        out.extend(_toml_strings(cpm.group(1)))
    return out


def gemini_prefixes_from_dir(dirpath):
    out = []
    d = Path(dirpath)
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.toml")):
        out.extend(gemini_allow_prefixes_from_text(read_text(f)))
    return out


# ---------------------------------------------------------------------------
# Coverage (true-prefix; a broader entry suppresses a narrower candidate)
# ---------------------------------------------------------------------------

def covered_by(segment: str, prefixes):
    """Return (covered, matching_entry, kind) where kind is 'exact' or 'broad'.
    A candidate is covered when an existing entry equals it or is a true token
    prefix of it (entry + ' ' is a prefix of the candidate)."""
    broad = None
    for p in prefixes:
        if not p:
            continue
        if segment == p:
            return True, p, "exact"
        if segment.startswith(p + " "):
            if broad is None or len(p) > len(broad):
                broad = p
    if broad is not None:
        return True, broad, "broad"
    return False, None, None


# ---------------------------------------------------------------------------
# Repo discovery (current workspace only)
# ---------------------------------------------------------------------------

def is_git_repo(d: Path) -> bool:
    return (d / ".git").exists()


def find_repos(root: Path, max_depth: int):
    found = []

    def walk(d: Path, depth: int):
        if d.name in SKIP_DIRS:
            return
        if is_git_repo(d):
            found.append(d)
        if depth >= max_depth:
            return
        try:
            children = sorted(d.iterdir())
        except OSError:
            return
        for child in children:
            if not child.is_dir() or child.is_symlink():
                continue
            if child.name in SKIP_DIRS or child.name.startswith("."):
                continue
            walk(child, depth + 1)

    root = root.resolve()
    if root.is_dir():
        walk(root, 0)
    return found


# ---------------------------------------------------------------------------
# Candidate collection per repo
# ---------------------------------------------------------------------------

class Candidate:
    __slots__ = ("segment", "cls", "reason", "source", "evidence")

    def __init__(self, segment, cls, reason, source, evidence=None):
        self.segment = segment
        self.cls = cls
        self.reason = reason
        self.source = source
        self.evidence = evidence


def _add(cands, segment, cls, reason, source, evidence=None):
    segment = re.sub(r"\s+", " ", segment).strip()
    if not segment:
        return
    if segment in cands:
        return
    cands[segment] = Candidate(segment, cls, reason, source, evidence)


def parse_makefile_targets(text: str):
    """Return {target: recipe_body} for plain-word, non-pattern targets."""
    targets = {}
    lines = text.splitlines()
    i = 0
    n = len(lines)
    target_re = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*::?\s*(?:[^=].*)?$")
    while i < n:
        line = lines[i]
        m = target_re.match(line)
        # A target line has a colon that is not part of := / ::= assignment.
        if m and ":" in line and not re.search(r":=", line):
            name = m.group(1)
            body = []
            j = i + 1
            while j < n:
                nxt = lines[j]
                if nxt.startswith("\t"):
                    body.append(nxt.strip())
                    j += 1
                elif nxt.strip() == "":
                    j += 1
                    # blank line inside a recipe is allowed; peek ahead
                    if j < n and lines[j].startswith("\t"):
                        continue
                    break
                else:
                    break
            targets.setdefault(name, "\n".join(body))
            i = j
            continue
        i += 1
    # Drop Make's special/internal pseudo-targets.
    for special in ("PHONY", "DEFAULT_GOAL", "SUFFIXES", "PRECIOUS", "SILENT"):
        targets.pop(special, None)
    return {k: v for k, v in targets.items() if not k.startswith(".")}


def collect_makefile(repo: Path, cands, stacks):
    mk = repo / "Makefile"
    if not mk.is_file():
        mk = repo / "makefile"
    if not mk.is_file():
        return
    stacks.add("make")
    targets = parse_makefile_targets(read_text(mk))
    for name, body in sorted(targets.items()):
        cls, reason = _classify_text(name, body)
        seg = "make %s" % name
        ev = None
        if cls == UNCLASSIFIED:
            ev = "Makefile target `%s` recipe:\n%s" % (name, body or "(empty recipe)")
        _add(cands, seg, cls, reason, "Makefile:%s" % name, ev)


def detect_node_pm(repo: Path) -> str:
    if (repo / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (repo / "yarn.lock").is_file():
        return "yarn"
    if (repo / "package-lock.json").is_file():
        return "npm"
    return "npm"


def collect_package_json(repo: Path, cands, stacks):
    pkg_files = [repo / "package.json"]
    for sub in ("packages", "apps"):
        d = repo / sub
        if d.is_dir():
            for child in sorted(d.iterdir()):
                if child.is_dir() and (child / "package.json").is_file():
                    pkg_files.append(child / "package.json")
    pm = detect_node_pm(repo)
    for pf in pkg_files:
        if not pf.is_file():
            continue
        data = load_json_lenient(pf)
        if not isinstance(data, dict):
            continue
        scripts = data.get("scripts")
        if not isinstance(scripts, dict):
            continue
        stacks.add("node")
        rel = pf.parent.relative_to(repo)
        prefix = "" if str(rel) == "." else "%s: " % rel
        for sname, sval in sorted(scripts.items()):
            sval = sval if isinstance(sval, str) else ""
            cls, reason = _classify_text(sname, sval)
            seg = ("%s test" % pm) if sname == "test" else ("%s run %s" % (pm, sname))
            ev = None
            if cls == UNCLASSIFIED:
                ev = "%spackage.json script `%s` = %s" % (prefix, sname, sval or "(empty)")
            _add(cands, seg, cls, reason, "package.json:%s%s" % (prefix, sname), ev)


def collect_python(repo: Path, cands, stacks):
    pyproject = repo / "pyproject.toml"
    reqs = list(repo.glob("requirements*.txt"))
    has_tests = (repo / "tests").is_dir() or (repo / "test").is_dir()
    if not (pyproject.is_file() or reqs or has_tests or (repo / "setup.cfg").is_file()):
        return
    stacks.add("python")
    text = read_text(pyproject)
    for r in reqs:
        text += "\n" + read_text(r)
    text += "\n" + read_text(repo / "setup.cfg")
    tl = text.lower()
    if "pytest" in tl or has_tests:
        _add(cands, "pytest", BUILD, "python test runner", "python:pytest")
    if "ruff" in tl:
        _add(cands, "ruff check", BUILD, "python linter", "python:ruff")
    if "mypy" in tl:
        _add(cands, "mypy", BUILD, "python type checker", "python:mypy")
    if "pyright" in tl:
        _add(cands, "pyright", BUILD, "python type checker", "python:pyright")
    if "black" in tl:
        _add(cands, "black --check", BUILD, "python formatter (check)", "python:black")
    if "isort" in tl:
        _add(cands, "isort --check", BUILD, "python import sort (check)", "python:isort")
    if "[tool.uv]" in text or (repo / "uv.lock").is_file():
        _add(cands, "uv lock --check", INSPECT, "uv lockfile check", "python:uv")
    # [project.scripts] console entrypoints — arbitrary behavior, deep-eval.
    m = re.search(r"(?ms)^\[project\.scripts\]\s*(.*?)(?:^\[|\Z)", text)
    if m:
        for em in re.finditer(r'(?m)^\s*([A-Za-z0-9_.-]+)\s*=\s*"([^"]+)"', m.group(1)):
            ename, etarget = em.group(1), em.group(2)
            _add(cands, ename, UNCLASSIFIED, "console entrypoint (unknown behavior)",
                 "python:[project.scripts]:%s" % ename,
                 "pyproject [project.scripts]: %s = %s" % (ename, etarget))


def collect_go(repo: Path, cands, stacks):
    if not (repo / "go.mod").is_file():
        return
    stacks.add("go")
    _add(cands, "go build ./...", BUILD, "go build", "go:build")
    _add(cands, "go test ./...", BUILD, "go test", "go:test")
    _add(cands, "go vet ./...", INSPECT, "go vet (static analysis)", "go:vet")


def collect_rust(repo: Path, cands, stacks):
    if not (repo / "Cargo.toml").is_file():
        return
    stacks.add("rust")
    _add(cands, "cargo build", BUILD, "cargo build", "rust:build")
    _add(cands, "cargo test", BUILD, "cargo test", "rust:test")
    _add(cands, "cargo clippy", BUILD, "cargo lint", "rust:clippy")
    _add(cands, "cargo fmt --check", INSPECT, "cargo format (check)", "rust:fmt")


def collect_dotnet(repo: Path, cands, stacks):
    has = list(repo.glob("*.sln")) or list(repo.glob("*.csproj")) \
        or list(repo.glob("**/*.csproj"))
    if not has:
        return
    stacks.add("dotnet")
    _add(cands, "dotnet build", BUILD, "dotnet build", "dotnet:build")
    _add(cands, "dotnet test", BUILD, "dotnet test", "dotnet:test")
    _add(cands, "dotnet format --verify-no-changes", INSPECT,
         "dotnet format (check)", "dotnet:format")


def collect_swift(repo: Path, cands, stacks):
    has_spm = (repo / "Package.swift").is_file()
    xcodeproj = list(repo.glob("*.xcodeproj")) or list(repo.glob("*.xcworkspace"))
    if not (has_spm or xcodeproj):
        return
    stacks.add("swift")
    if has_spm:
        _add(cands, "swift build", BUILD, "swift build", "swift:build")
        _add(cands, "swift test", BUILD, "swift test", "swift:test")
        _add(cands, "swift package describe", INSPECT, "spm describe", "swift:describe")
    if xcodeproj:
        _add(cands, "xcodebuild -list", INSPECT, "list schemes/targets", "swift:xcodebuild-list")
        _add(cands, "xcodebuild build", BUILD, "xcodebuild build", "swift:xcodebuild-build")
        _add(cands, "xcodebuild test", BUILD, "xcodebuild test", "swift:xcodebuild-test")


def collect_gradle(repo: Path, cands, stacks):
    if not (list(repo.glob("build.gradle*")) or list(repo.glob("settings.gradle*"))):
        return
    stacks.add("gradle")
    g = "./gradlew" if (repo / "gradlew").is_file() else "gradle"
    _add(cands, "%s tasks" % g, INSPECT, "list gradle tasks", "gradle:tasks")
    _add(cands, "%s test" % g, BUILD, "gradle test", "gradle:test")
    _add(cands, "%s build" % g, BUILD, "gradle build", "gradle:build")
    _add(cands, "%s check" % g, BUILD, "gradle check", "gradle:check")


def collect_terraform(repo: Path, cands, stacks):
    if not list(repo.glob("*.tf")) and not list(repo.glob("**/*.tf")):
        return
    stacks.add("terraform")
    _add(cands, "terraform validate", BUILD, "terraform validate", "terraform:validate")
    _add(cands, "terraform plan", INSPECT, "terraform plan (read-only diff)", "terraform:plan")
    _add(cands, "terraform fmt -check", INSPECT, "terraform format (check)", "terraform:fmt")


SCRIPT_RUNNERS = {
    ".mjs": "node", ".cjs": "node", ".js": "node", ".ts": "node",
    ".py": "python3", ".sh": "bash", ".bash": "bash", ".rb": "ruby",
}


def collect_scripts(repo: Path, cands, stacks):
    for sub in ("scripts", "bin", "tools"):
        d = repo / sub
        if not d.is_dir():
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file():
                continue
            runner = SCRIPT_RUNNERS.get(f.suffix)
            if not runner:
                continue
            stacks.add("scripts")
            rel = f.relative_to(repo)
            head = "\n".join(read_text(f).splitlines()[:60])
            cls, reason = _classify_text(f.stem, head)
            seg = "%s %s" % (runner, rel)
            ev = None
            if cls == UNCLASSIFIED:
                ev = "script %s (first 60 lines):\n%s" % (rel, head)
            _add(cands, seg, cls, reason, "script:%s" % rel, ev)


COLLECTORS = [
    collect_makefile, collect_package_json, collect_python, collect_go,
    collect_rust, collect_dotnet, collect_swift, collect_gradle,
    collect_terraform, collect_scripts,
]


# ---------------------------------------------------------------------------
# Per-repo analysis
# ---------------------------------------------------------------------------

def repo_per_harness_files(repo: Path):
    return {
        "cursor_ide": repo / ".cursor" / "permissions.json",
        "cursor_cli": repo / ".cursor" / "cli.json",
        "claude": repo / ".claude" / "settings.json",
        "gemini": repo / ".gemini" / "policies",
    }


def repo_prefixes(repo: Path):
    f = repo_per_harness_files(repo)
    return {
        "cursor_ide": cursor_ide_prefixes(f["cursor_ide"]),
        "cursor_cli": permissions_allow_prefixes(f["cursor_cli"]),
        "claude": permissions_allow_prefixes(f["claude"]),
        "gemini": gemini_prefixes_from_dir(f["gemini"]),
    }


def analyze_repo(repo: Path, global_prefixes, repo_root_for_rel):
    cands = {}
    stacks = set()
    for collector in COLLECTORS:
        try:
            collector(repo, cands, stacks)
        except Exception as exc:  # never let one bad repo abort the scan
            sys.stderr.write("warn: %s failed on %s: %s\n"
                             % (collector.__name__, repo, exc))

    rpref = repo_prefixes(repo)
    per_repo_meta = {}
    files = repo_per_harness_files(repo)
    for h in HARNESSES:
        per_repo_meta[h] = {
            "path": str(files[h]),
            "exists": files[h].exists(),
            "count": len(rpref[h]),
        }

    group1, group2, excluded, unclassified = [], [], [], []

    for seg in sorted(cands):
        c = cands[seg]
        if c.cls == UNCLASSIFIED:
            unclassified.append({
                "segment": seg,
                "source": c.source,
                "reason": c.reason,
                "evidence": c.evidence or "",
            })
            continue
        if c.cls in NEVER_CLASSES:
            excluded.append({
                "segment": seg,
                "class": c.cls,
                "source": c.source,
                "reason": "not proposed - class: %s (%s)" % (c.cls, c.reason),
            })
            continue

        # proposable: compute coverage
        cov = {}
        for h in HARNESSES:
            ok, ent, kind = covered_by(seg, global_prefixes[h] + rpref[h])
            cov[h] = {"covered": ok, "by": ent, "kind": kind}
        present = [h for h in HARNESSES if cov[h]["covered"]]
        missing = [h for h in HARNESSES if not cov[h]["covered"]]

        if not missing:
            continue  # fully covered everywhere

        notes = []
        for h in present:
            if cov[h]["kind"] == "broad":
                notes.append("suppressed in %s by broad prefix '%s'" % (h, cov[h]["by"]))

        entry = {
            "segment": seg,
            "class": c.cls,
            "source": c.source,
            "missing_harnesses": missing,
        }
        if not present:
            group1.append(entry)
        else:
            entry["present_harnesses"] = present
            entry["coverage_notes"] = notes
            group2.append(entry)

    return {
        "path": str(repo),
        "name": repo.name,
        "stacks": sorted(stacks),
        "per_repo_allowlists": per_repo_meta,
        "group1": group1,
        "group2": group2,
        "excluded": excluded,
        "unclassified": unclassified,
    }


# ---------------------------------------------------------------------------
# Global-promotion candidates
# ---------------------------------------------------------------------------

def compute_global_promotions(repos_out, global_prefixes):
    seg_to_repos = {}
    seg_to_class = {}
    for r in repos_out:
        for entry in r["group1"] + r["group2"]:
            seg = entry["segment"]
            seg_to_repos.setdefault(seg, set()).add(r["name"])
            seg_to_class.setdefault(seg, entry["class"])
    promotions = []
    for seg in sorted(seg_to_repos):
        repos = sorted(seg_to_repos[seg])
        if len(repos) < 2:
            continue
        missing_global = []
        for h in HARNESSES:
            ok, _, _ = covered_by(seg, global_prefixes[h])
            if not ok:
                missing_global.append(h)
        if not missing_global:
            continue
        promotions.append({
            "segment": seg,
            "class": seg_to_class[seg],
            "repos": repos,
            "missing_global_harnesses": missing_global,
        })
    return promotions


# ---------------------------------------------------------------------------
# Summary rendering
# ---------------------------------------------------------------------------

def render_summary_md(result) -> str:
    lines = []
    lines.append("# Allowlist proposal (%s)" % result["generated"])
    lines.append("")
    lines.append("_Transient report — the harness allowlist files remain the "
                 "source of truth. Allow-only; nothing was written._")
    lines.append("")
    lines.append("Workspace roots: %s" % ", ".join(result["workspace_roots"]))
    lines.append("")
    for r in result["repos"]:
        lines.append("## %s" % r["path"])
        lines.append("")
        lines.append("Stacks: %s" % (", ".join(r["stacks"]) or "(none detected)"))
        lines.append("")
        if r["group1"]:
            lines.append("### Group 1 — missing from every harness (add to all)")
            for e in r["group1"]:
                lines.append("- `%s`  _(%s; %s)_" % (e["segment"], e["class"], e["source"]))
            lines.append("")
        if r["group2"]:
            lines.append("### Group 2 — drift (add only to missing harnesses)")
            for e in r["group2"]:
                lines.append("- `%s`  _(%s)_ — have: %s; add to: %s"
                             % (e["segment"], e["class"],
                                ", ".join(e.get("present_harnesses", [])),
                                ", ".join(e["missing_harnesses"])))
                for note in e.get("coverage_notes", []):
                    lines.append("    - note: %s" % note)
            lines.append("")
        if r["unclassified"]:
            lines.append("### Unclassified — needs agent deep-eval (omitted for now)")
            for e in r["unclassified"]:
                lines.append("- `%s`  _(%s)_" % (e["segment"], e["source"]))
            lines.append("")
        if r["excluded"]:
            lines.append("### Excluded — never proposed")
            for e in r["excluded"]:
                lines.append("- `%s` — %s" % (e["segment"], e["reason"]))
            lines.append("")
    if result["global_promotion_candidates"]:
        lines.append("## Global-promotion candidates (recur across repos)")
        for e in result["global_promotion_candidates"]:
            lines.append("- `%s`  _(%s)_ — repos: %s; missing globally from: %s"
                         % (e["segment"], e["class"], ", ".join(e["repos"]),
                            ", ".join(e["missing_global_harnesses"])))
        lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Scan the current workspace's git repos and propose safe, "
                    "agent-runnable commands missing from the existing allowlists.")
    parser.add_argument("roots", nargs="*", default=["."],
                        help="workspace roots to scan (default: current dir)")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH,
                        help="how many levels below each root to search for "
                             "nested git repos (default: %d)" % DEFAULT_MAX_DEPTH)
    parser.add_argument("--summary-dir", default=".scratch",
                        help="directory for the human-readable summary "
                             "(default: .scratch under CWD)")
    parser.add_argument("--no-summary", action="store_true",
                        help="emit JSON only; do not write a summary file")
    args = parser.parse_args(argv)

    home = Path.home()
    cursor_home = Path(os.environ.get("CURSOR_DATA_HOME", str(home / ".cursor")))
    claude_home = Path(os.environ.get("CLAUDE_DATA_HOME", str(home / ".claude")))
    gemini_home = Path(os.environ.get("GEMINI_DATA_HOME", str(home / ".gemini")))

    global_files = {
        "cursor_ide": cursor_home / "permissions.json",
        "cursor_cli": cursor_home / "cli-config.json",
        "claude": claude_home / "settings.json",
        "gemini": gemini_home / "policies",
    }
    global_prefixes = {
        "cursor_ide": cursor_ide_prefixes(global_files["cursor_ide"]),
        "cursor_cli": permissions_allow_prefixes(global_files["cursor_cli"]),
        "claude": permissions_allow_prefixes(global_files["claude"]),
        "gemini": gemini_prefixes_from_dir(global_files["gemini"]),
    }

    # Enumerate repos (dedup by resolved path; stable order).
    seen = set()
    repos = []
    for root in args.roots:
        for repo in find_repos(Path(root), args.max_depth):
            rp = repo.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            repos.append(rp)
    repos.sort(key=lambda p: str(p))

    repos_out = [analyze_repo(repo, global_prefixes, repo) for repo in repos]
    promotions = compute_global_promotions(repos_out, global_prefixes)

    result = {
        "version": 1,
        "generated": random.choice(SUMMARY_WORDS),
        "workspace_roots": [str(Path(r).resolve()) for r in args.roots],
        "harnesses": HARNESSES,
        "global_allowlists": {
            h: {
                "path": str(global_files[h]),
                "exists": global_files[h].exists(),
                "count": len(global_prefixes[h]),
            } for h in HARNESSES
        },
        "repos": repos_out,
        "global_promotion_candidates": promotions,
        "summary_path": None,
    }

    if not args.no_summary:
        summary_dir = Path(args.summary_dir)
        try:
            summary_dir.mkdir(parents=True, exist_ok=True)
            spath = summary_dir / ("allowlist-proposal-%s.md" % result["generated"])
            spath.write_text(render_summary_md(result), encoding="utf-8")
            result["summary_path"] = str(spath)
            sys.stderr.write("summary written to %s\n" % spath)
        except OSError as exc:
            sys.stderr.write("warn: could not write summary: %s\n" % exc)

    json.dump(result, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
