#!/usr/bin/env python3
"""Allowlist Scout — apply layer.

Stdlib-only (Python 3.8+; no venv, no third-party deps). Generic: contains no
personal paths, org names, or repo names — both the agerpoint and personal
copies of this file are byte-identical.

Takes a list of (segment, harnesses-missing) pairs for one repo and writes only
the harness files that are missing the entry.  Never removes anything, never
writes a deny rule, never touches a harness that already covers the command.

Supported targets
-----------------
  cursor_ide  <repo>/.cursor/permissions.json  ->  terminalAllowlist  (raw prefix strings)
  cursor_cli  <repo>/.cursor/cli.json          ->  permissions.allow  (Shell(<base>) tokens)
  claude      <repo>/.claude/settings.json     ->  permissions.allow  (Bash(<cmd>:*) tokens)
  gemini      <repo>/.gemini/policies/<name>.toml  additive [[rule]] blocks
                  toolName = "run_shell_command"
                  commandPrefix = "<segment>"
                  decision = "allow"
                  priority = 100

CLI interface
-------------
  python3 render.py --repo <path> --harness <h1> [--harness <h2> ...] <segment>

  Or (preferred, batch): supply a JSON document on stdin:
    {
      "repo": "/path/to/repo",
      "commands": [
        {"segment": "make test", "harnesses": ["cursor_ide", "claude"]},
        {"segment": "swift build", "harnesses": ["cursor_cli", "gemini"]}
      ],
      "gemini_policy_name": "project"   // optional; default "project"
    }
  and call with --stdin.

Exit codes: 0 = success (or dry-run); 1 = any harness write failed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# JSON helpers (lenient reader; strict writer)
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> Any:
    """Load JSON from path with basic JSONC tolerance. Returns None on error."""
    txt = _read_text(path)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        pass
    no_block = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    no_line  = re.sub(r"(?m)^\s*//.*$", "", no_block)
    no_trail = re.sub(r",(\s*[}\]])", r"\1", no_line)
    try:
        return json.loads(no_trail)
    except json.JSONDecodeError:
        return None


def _write_json(path: Path, obj: Any, dry_run: bool = False) -> None:
    text = json.dumps(obj, indent=2, sort_keys=False) + "\n"
    if dry_run:
        sys.stderr.write("[dry-run] would write %s\n" % path)
        return
    _atomic_write(path, text)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _atomic_write(path: Path, text: str) -> None:
    """Write *text* to *path* atomically (tmp sibling -> rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".render-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Per-harness union-only writers
# ---------------------------------------------------------------------------

def _add_cursor_ide(path: Path, segment: str, dry_run: bool) -> bool:
    """Add *segment* to terminalAllowlist if not already present. Returns True
    on success or when already covered."""
    data = _load_json(path) or {}
    arr = data.get("terminalAllowlist")
    if not isinstance(arr, list):
        arr = []
        data["terminalAllowlist"] = arr
    if segment in arr:
        return True
    arr.append(segment)
    try:
        _write_json(path, data, dry_run)
        return True
    except OSError as exc:
        sys.stderr.write("error: cursor_ide %s: %s\n" % (path, exc))
        return False


def _shell_token(segment: str) -> str:
    """Return the Shell(…) token for a segment.

    If the segment contains a space (i.e. has arguments), use Shell(<base>:*)
    so the wildcard grants any arguments to that command.  If it's a bare word
    with no spaces, Shell(<word>) covers exact invocations.  Both are safe
    prefix-matching tokens; the :* form is more permissive but matches the
    Cursor CLI convention for multi-word commands."""
    if " " in segment.strip():
        base = segment.strip().split()[0]
        return "Shell(%s:*)" % base
    return "Shell(%s)" % segment.strip()


def _add_cursor_cli(path: Path, segment: str, dry_run: bool) -> bool:
    """Add Shell(…) token to .cursor/cli.json permissions.allow."""
    data = _load_json(path) or {}
    perms = data.setdefault("permissions", {})
    arr   = perms.setdefault("allow", [])
    if not isinstance(arr, list):
        arr = []
        perms["allow"] = arr

    token = _shell_token(segment)
    if token in arr or segment in arr:
        return True
    arr.append(token)
    try:
        _write_json(path, data, dry_run)
        return True
    except OSError as exc:
        sys.stderr.write("error: cursor_cli %s: %s\n" % (path, exc))
        return False


def _bash_token(segment: str) -> str:
    """Return the Bash(…:*) token for a segment (Claude Code format)."""
    return "Bash(%s:*)" % segment.strip()


def _add_claude(path: Path, segment: str, dry_run: bool) -> bool:
    """Add Bash(…:*) token to .claude/settings.json permissions.allow."""
    data = _load_json(path) or {}
    perms = data.setdefault("permissions", {})
    arr   = perms.setdefault("allow", [])
    if not isinstance(arr, list):
        arr = []
        perms["allow"] = arr

    token = _bash_token(segment)
    if token in arr or segment in arr:
        return True
    arr.append(token)
    try:
        _write_json(path, data, dry_run)
        return True
    except OSError as exc:
        sys.stderr.write("error: claude %s: %s\n" % (path, exc))
        return False


def _toml_string(s: str) -> str:
    """Return a TOML basic string literal for *s* (double-quoted, minimal escaping)."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


_GEMINI_ALLOW_BLOCK = """\
[[rule]]
toolName = "run_shell_command"
commandPrefix = {prefix}
decision = "allow"
priority = 100
"""


def _add_gemini(policies_dir: Path, segment: str, policy_name: str,
                dry_run: bool) -> bool:
    """Append an allow [[rule]] block to <policies_dir>/<policy_name>.toml if
    the exact commandPrefix is not already present."""
    toml_path = policies_dir / ("%s.toml" % policy_name)
    existing  = _read_text(toml_path)

    # Check: is this exact prefix already present in an allow block?
    for block in re.split(r"(?m)^\s*\[\[\s*rule\s*\]\]\s*$", existing):
        dm = re.search(r'(?m)^\s*decision\s*=\s*"([^"]+)"', block)
        if not dm or dm.group(1) != "allow":
            continue
        cpm = re.search(r"(?m)^\s*commandPrefix\s*=\s*(.+?)\s*$", block)
        if not cpm:
            continue
        vals = []
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', cpm.group(1)):
            vals.append(m.group(1).replace('\\"', '"').replace("\\\\", "\\"))
        if segment in vals:
            return True

    # Append the new block.
    block_text = _GEMINI_ALLOW_BLOCK.format(prefix=_toml_string(segment))
    new_text   = (existing.rstrip() + "\n\n" + block_text) if existing.strip() else block_text

    if dry_run:
        sys.stderr.write("[dry-run] would append to %s\n" % toml_path)
        return True
    try:
        _atomic_write(toml_path, new_text)
        return True
    except OSError as exc:
        sys.stderr.write("error: gemini %s: %s\n" % (toml_path, exc))
        return False


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

HARNESS_WRITERS = {
    "cursor_ide", "cursor_cli", "claude", "gemini",
}


def write_entry(repo: Path, segment: str, harness: str,
                gemini_policy_name: str = "project",
                dry_run: bool = False) -> bool:
    """Write *segment* into the per-repo allowlist file for *harness*.
    Returns True on success (or when already covered / dry-run)."""
    if harness not in HARNESS_WRITERS:
        sys.stderr.write("warn: unknown harness %r — skipped\n" % harness)
        return True

    if harness == "cursor_ide":
        path = repo / ".cursor" / "permissions.json"
        return _add_cursor_ide(path, segment, dry_run)

    if harness == "cursor_cli":
        path = repo / ".cursor" / "cli.json"
        return _add_cursor_cli(path, segment, dry_run)

    if harness == "claude":
        path = repo / ".claude" / "settings.json"
        return _add_claude(path, segment, dry_run)

    if harness == "gemini":
        policies_dir = repo / ".gemini" / "policies"
        return _add_gemini(policies_dir, segment, gemini_policy_name, dry_run)

    return True  # unreachable


# ---------------------------------------------------------------------------
# Main (CLI + stdin batch)
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Write confirmed allowlist commands into per-repo harness files.")
    parser.add_argument("--repo", help="path to the git repo (required unless --stdin)")
    parser.add_argument("--harness", action="append", dest="harnesses",
                        choices=sorted(HARNESS_WRITERS),
                        help="harness to write (may repeat; required unless --stdin)")
    parser.add_argument("--gemini-policy-name", default="project",
                        help="TOML filename stem under .gemini/policies/ (default: project)")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be written; do not modify any file")
    parser.add_argument("--stdin", action="store_true",
                        help="read a batch JSON document from stdin instead of CLI args")
    parser.add_argument("segment", nargs="?",
                        help="the shell command segment to allow (CLI mode only)")
    args = parser.parse_args(argv)

    if args.stdin:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, OSError) as exc:
            sys.stderr.write("error: could not parse stdin JSON: %s\n" % exc)
            return 1
        repo = Path(payload["repo"])
        policy_name = payload.get("gemini_policy_name", "project")
        commands = payload.get("commands", [])
        ok = True
        for cmd in commands:
            seg = cmd["segment"]
            for h in cmd.get("harnesses", []):
                if not write_entry(repo, seg, h, policy_name, args.dry_run):
                    ok = False
                    sys.stderr.write("FAILED: %s -> %s\n" % (seg, h))
                else:
                    sys.stderr.write("ok:     %s -> %s\n" % (seg, h))
        return 0 if ok else 1

    # CLI mode.
    if not args.repo or not args.segment or not args.harnesses:
        parser.print_help(sys.stderr)
        return 1

    repo = Path(args.repo)
    ok   = True
    for h in args.harnesses:
        if not write_entry(repo, args.segment, h,
                           args.gemini_policy_name, args.dry_run):
            ok = False
            sys.stderr.write("FAILED: %s -> %s\n" % (args.segment, h))
        else:
            sys.stderr.write("ok:     %s -> %s\n" % (args.segment, h))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
