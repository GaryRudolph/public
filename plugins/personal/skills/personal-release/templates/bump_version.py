#!/usr/bin/env python3
"""Bump the release version in lock-step. Copy to scripts/bump_version.py.

Implements the release step of Gary Rudolph's versioning standard:
version.txt holds the LAST released version; at release time this reads it,
computes the next version for the chosen level, rewrites version.txt and
every managed version field to it, and moves the CHANGELOG.md
"## [Unreleased]" entries under "## [vX.Y.Z] - YYYY-MM-DD".

Managed fields (edited in place; the rest of each file is left byte-for-byte):
    package.json    top-level "version"   (every package.json outside node_modules)
    pyproject.toml  [project] version
    Cargo.toml      [package] version

Everything else (Info.plist, build.gradle, pom.xml, Docker tags, ...) should
derive from version.txt at build time. Those files are not touched.

Usage:
    bump_version.py patch|minor|major [--dry-run] [--date YYYY-MM-DD]

Prints the new version as the last line of stdout. Refuses without changing
anything when version.txt isn't MAJOR.MINOR.PATCH or a managed field
already disagrees with it (lock-step broken; fix that first).
"""

import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

RELEASE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SKIP_DIRS = {"node_modules", ".git", "vendor", "target", "build", "dist", ".venv", "venv"}


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def next_version(current, level):
    match = RELEASE.match(current)
    if not match:
        fail(f"version.txt holds {current!r}; it must be MAJOR.MINOR.PATCH (no v, no suffix)")
    major, minor, patch = (int(p) for p in match.groups())
    return {
        "major": f"{major + 1}.0.0",
        "minor": f"{major}.{minor + 1}.0",
        "patch": f"{major}.{minor}.{patch + 1}",
    }[level]


def repo_files(root, name):
    try:
        listed = subprocess.run(["git", "ls-files", "--", f"*{name}", name], cwd=root,
                                capture_output=True, text=True, check=True).stdout.split()
        paths = [root / p for p in listed if Path(p).name == name]
    except (OSError, subprocess.CalledProcessError):
        paths = list(root.rglob(name))
    return sorted(p for p in paths if not SKIP_DIRS & set(p.relative_to(root).parts))


class Field:
    """One version field: where it is, its current value, how to rewrite it."""

    def __init__(self, path, label, text, span):
        self.path, self.label, self.text, self.span = path, label, text, span
        self.value = text[span[0]:span[1]]

    def rewritten(self, version):
        return self.text[:self.span[0]] + version + self.text[self.span[1]:]


def package_json_field(path):
    text = path.read_text()
    data = json.loads(text)
    if "version" not in data:
        return None
    # Find the top-level "version" key: the first "version" at brace depth 1.
    depth, i, in_str = 0, 0, False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            if depth == 1:
                m = re.compile(r'"version"\s*:\s*"([^"]*)"').match(text, i)
                if m:
                    return Field(path, "version", text, m.span(1))
            in_str = True
        elif c in "{[":
            depth += 1
        elif c in "}]":
            depth -= 1
        i += 1
    fail(f"{path}: couldn't locate the top-level version field")


def toml_field(path, section):
    text = path.read_text()
    current = None
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("["):
            current = stripped
        elif current == f"[{section}]":
            m = re.match(r'(\s*version\s*=\s*")([^"]*)"', line)
            if m:
                return Field(path, f"[{section}] version", text, (offset + m.start(2), offset + m.end(2)))
        offset += len(line)
    return None


def changelog_update(text, version, date):
    """Move the Unreleased entries under a new release heading.

    Keeps an empty "## [Unreleased]" at the top and everything after the
    Unreleased section (older releases) exactly as it was.
    """
    m = re.search(r"^## \[Unreleased\][^\n]*\n", text, re.M)
    if not m:
        return None, "CHANGELOG.md has no ## [Unreleased] section; left unchanged"
    next_heading = re.compile(r"^## ", re.M).search(text, m.end())
    end = next_heading.start() if next_heading else len(text)
    entries = text[m.end():end].strip("\n")
    note = None if entries.strip() else "## [Unreleased] was empty; the release heading has no entries"
    section = f"## [v{version}] - {date}\n"
    if entries:
        section += f"\n{entries}\n"
    rest = text[end:]
    if rest:
        section += "\n"
    return text[:m.end()] + "\n" + section + rest, note


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    dry_run = "--dry-run" in argv
    date = datetime.date.today().isoformat()
    if "--date" in argv:
        date = argv[argv.index("--date") + 1]
        args.remove(date)
    if len(args) != 1 or args[0] not in ("patch", "minor", "major"):
        fail("usage: bump_version.py patch|minor|major [--dry-run] [--date YYYY-MM-DD]")

    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or ".")
    version_file = root / "version.txt"
    if not version_file.exists():
        fail("version.txt not found at the repo root; create it with the last released version")
    current = version_file.read_text().strip()
    new = next_version(current, args[0])

    fields = []
    for path in repo_files(root, "package.json"):
        field = package_json_field(path)
        if field:
            fields.append(field)
    for name, section in (("pyproject.toml", "project"), ("Cargo.toml", "package")):
        for path in repo_files(root, name):
            field = toml_field(path, section)
            if field:
                fields.append(field)

    out_of_step = [f for f in fields if f.value != current]
    if out_of_step:
        for f in out_of_step:
            print(f"error: {f.path.relative_to(root)} {f.label} is {f.value}, but version.txt is {current}", file=sys.stderr)
        fail("version fields are out of lock-step; make them match version.txt, then rerun")

    writes = {version_file: new + "\n"}
    for f in fields:
        writes[f.path] = f.rewritten(new)
    notes = []
    changelog = root / "CHANGELOG.md"
    if changelog.exists():
        updated, note = changelog_update(changelog.read_text(), new, date)
        if updated is not None:
            writes[changelog] = updated
        if note:
            notes.append(note)

    for path in writes:
        print(f"{'would update' if dry_run else 'updated'} {path.relative_to(root)}")
    for note in notes:
        print(f"note: {note}", file=sys.stderr)
    if not dry_run:
        for path, content in writes.items():
            path.write_text(content)
    print(f"{current} -> {new}")
    print(new)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
