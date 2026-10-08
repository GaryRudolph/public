#!/usr/bin/env python3
"""Changelog fragments: one file per change, assembled at release time.
Copy to scripts/changelog.py, next to scripts/bump_version.py.

A PR that appends to CHANGELOG.md edits the same lines as every other open
PR, so they conflict with each other and a merge queue ejects all but the
first. Instead each change ships its entry as its own file in a .changelog/
directory beside the CHANGELOG.md it feeds, and the release step assembles
the files into a new release section and deletes them. This is the model
HashiCorp's go-changelog uses; this script is a stdlib-only take on it.

A fragment is .changelog/<name>.txt holding one or more fenced blocks:

    ```release-note:fixed
    `--serve` accepts `--theme grayscale`.
    ```

The kind is a Keep a Changelog section: added, changed, deprecated,
removed, fixed, or security. Each block is one entry; the release step
adds the leading "- " and indents continuation lines, and a body that
already starts with "- " is kept as written. Name the file anything
unique: the branch slug (serve-grayscale-theme.txt) or the PR number
(123.txt). Other files in .changelog/ (its README.md) are ignored.

Commands:
    changelog.py check [--base REF] [--require]
        Validates every fragment. With --base, also fails if the branch
        edits a CHANGELOG.md that has a .changelog/ beside it, and with
        --require, if the branch adds or edits no fragment at all.
    changelog.py preview
        Prints the section each CHANGELOG.md would gain at the next release.
    changelog.py release X.Y.Z [--date YYYY-MM-DD] [--dry-run]
        Writes the release section into each CHANGELOG.md and deletes the
        fragments it used. Entries still under "## [Unreleased]" (from
        before the repo adopted fragments) are folded in and the heading
        is dropped. bump_version.py calls this when it sits beside it.
"""

import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

KINDS = ("added", "changed", "deprecated", "removed", "fixed", "security")
FRAGMENT_DIR = ".changelog"
BLOCK = re.compile(r"^```release-note:([A-Za-z-]*)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
RELEASE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SKIP_DIRS = {"node_modules", ".git", "vendor", "target", "build", "dist", ".venv", "venv"}


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


def repo_root():
    out = git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(out.strip()) if out else Path.cwd()


def fragment_dirs(root):
    """Every .changelog/ directory in the repo, outside vendored trees."""
    found = []
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if FRAGMENT_DIR in dirnames:
            found.append(Path(dirpath) / FRAGMENT_DIR)
            dirnames.remove(FRAGMENT_DIR)
    return sorted(found)


def targets(root):
    """CHANGELOG.md files fed by a .changelog/ beside them."""
    return [d.parent / "CHANGELOG.md" for d in fragment_dirs(root) if (d.parent / "CHANGELOG.md").exists()]


def parse_fragment(path):
    """Return ([(kind, body)], [error]) for one fragment file."""
    text = path.read_text()
    entries, errors = [], []
    for m in BLOCK.finditer(text):
        kind, body = m.group(1), m.group(2).strip("\n").rstrip()
        if kind not in KINDS:
            errors.append(f"unknown kind {kind!r}; use one of {', '.join(KINDS)}")
        elif not body.strip():
            errors.append(f"empty release-note:{kind} block")
        else:
            entries.append((kind, body))
    if BLOCK.sub("", text).strip():
        errors.append("text outside a ```release-note:<kind> block (check the fence spelling)")
    if not entries and not errors:
        errors.append("no ```release-note:<kind> blocks")
    return entries, errors


def fragments(directory):
    return sorted(p for p in directory.glob("*.txt") if p.is_file())


def added_at(root, directory):
    """Commit time each fragment was added, so entries list in merge order."""
    out = git(root, "log", "--diff-filter=A", "--name-only", "--format=@%ct", "--", str(directory.relative_to(root))) or ""
    times, stamp = {}, None
    for line in out.splitlines():
        if line.startswith("@"):
            stamp = int(line[1:])
        elif line and stamp is not None:
            times.setdefault(line, stamp)
    return times


def bullet(body):
    if body.startswith(("- ", "* ")):
        return body
    first, *rest = body.splitlines()
    return "\n".join([f"- {first}", *(f"  {line}" if line.strip() else "" for line in rest)])


def unreleased_span(text):
    """(start, body_start, end) of the ## [Unreleased] section, or None."""
    m = re.search(r"^## \[Unreleased\][^\n]*(\n|\Z)", text, re.M)
    if not m:
        return None
    nxt = re.compile(r"^## ", re.M).search(text, m.end())
    return m.start(), m.end(), nxt.start() if nxt else len(text)


def legacy_entries(text):
    """Split the old Unreleased body into {heading-or-None: chunk} in order."""
    span = unreleased_span(text)
    if not span:
        return {}
    chunks, heading, lines = {}, None, []
    for line in text[span[1]:span[2]].splitlines():
        m = re.match(r"^### (.+?)\s*$", line)
        if m:
            chunks[heading] = "\n".join(lines).strip("\n")
            heading, lines = m.group(1), []
        else:
            lines.append(line)
    chunks[heading] = "\n".join(lines).strip("\n")
    return {h: c for h, c in chunks.items() if c.strip()}


def render(changelog, root):
    """Return (body, used_fragments, errors) for the next release section."""
    directory = changelog.parent / FRAGMENT_DIR
    times = added_at(root, directory)
    by_kind = {k: [] for k in KINDS}
    used, errors = [], []
    ordered = sorted(fragments(directory),
                     key=lambda p: (times.get(p.relative_to(root).as_posix(), float("inf")), p.name))
    for path in ordered:
        entries, problems = parse_fragment(path)
        errors += [f"{path.relative_to(root)}: {e}" for e in problems]
        for kind, body in entries:
            by_kind[kind].append(bullet(body))
        used.append(path)

    legacy = legacy_entries(changelog.read_text())
    titles = {k.title(): k for k in KINDS}
    parts = []
    if None in legacy:
        parts.append(legacy.pop(None))
    for kind in KINDS:
        items = [c for h, c in legacy.items() if titles.get(h.strip().title()) == kind] + by_kind[kind]
        if items:
            parts.append(f"### {kind.title()}\n\n" + "\n".join(items))
    for heading, chunk in legacy.items():
        if heading.strip().title() not in titles:
            parts.append(f"### {heading}\n\n{chunk}")
    return "\n\n".join(parts), used, errors


def release_label(text, version):
    """## [vX.Y.Z], or ## [X.Y.Z] when the file's past releases drop the v."""
    sample = re.search(r"^## \[(v?)\d+\.\d+\.\d+\]", text, re.M)
    prefix = sample.group(1) if sample else "v"
    return f"## [{prefix}{version}]"


def release(root, version, date):
    """Return (writes {path: text}, deletes [path], notes [str]) for every target."""
    if not RELEASE.match(version):
        fail(f"version {version!r} must be MAJOR.MINOR.PATCH")
    writes, deletes, notes, errors = {}, [], [], []
    for changelog in targets(root):
        text = changelog.read_text()
        label = release_label(text, version)
        if re.search(rf"^{re.escape(label)}", text, re.M):
            errors.append(f"{changelog.relative_to(root)} already has {label}")
            continue
        body, used, problems = render(changelog, root)
        errors += problems
        section = f"{label} - {date}\n" + (f"\n{body}\n" if body else "")
        if not body:
            notes.append(f"{changelog.relative_to(root)}: no fragments or Unreleased entries; the release heading is empty")
        span = unreleased_span(text)
        if span:
            start, end = span[0], span[2]
        else:
            nxt = re.compile(r"^## ", re.M).search(text)
            start = end = nxt.start() if nxt else len(text)
        before, after = text[:start], text[end:]
        if before and not before.endswith("\n\n"):
            before = before.rstrip("\n") + "\n\n"
        writes[changelog] = before + section + ("\n" + after if after else "")
        deletes += used
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        fail("fix the changelog problems above, then rerun")
    return writes, deletes, notes


def check(root, base, require):
    dirs = fragment_dirs(root)
    if not dirs:
        fail(f"no {FRAGMENT_DIR}/ directory in this repo")
    errors = []
    for d in dirs:
        if not (d.parent / "CHANGELOG.md").exists():
            errors.append(f"{d.relative_to(root)} has no CHANGELOG.md beside it")
        for path in fragments(d):
            errors += [f"{path.relative_to(root)}: {e}" for e in parse_fragment(path)[1]]
    if base:
        diff = git(root, "diff", "--name-status", "--no-renames", f"{base}...HEAD")
        if diff is None:
            fail(f"can't diff against {base}; fetch it (actions/checkout needs fetch-depth: 0)")
        managed = {(d.parent / "CHANGELOG.md").relative_to(root).as_posix() for d in dirs}
        touched = []
        for line in diff.splitlines():
            status, path = line.split("\t", 1)
            p = Path(path)
            if path in managed:
                errors.append(f"{path} is edited directly; add a {p.parent / FRAGMENT_DIR}/<name>.txt fragment instead "
                              "(only the release commit writes CHANGELOG.md)")
            elif p.parent.name == FRAGMENT_DIR and p.suffix == ".txt" and status in ("A", "M"):
                touched.append(path)
        for path in touched:
            print(f"fragment: {path}")
        if require and not touched:
            errors.append(f"no changelog fragment; add {FRAGMENT_DIR}/<name>.txt, or label the PR no-changelog "
                          "if nothing user-visible changed")
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    return 1 if errors else 0


def main(argv):
    if not argv or argv[0] not in ("check", "preview", "release"):
        fail("usage: changelog.py check [--base REF] [--require] | preview | release X.Y.Z [--date YYYY-MM-DD] [--dry-run]")
    command, args = argv[0], argv[1:]

    def option(flag):
        if flag not in args:
            return None
        i = args.index(flag)
        if i + 1 >= len(args) or args[i + 1].startswith("--"):
            fail(f"{flag} needs a value")
        return args.pop(i + 1)

    root = repo_root()
    if command == "check":
        return check(root, option("--base"), "--require" in args)

    if command == "preview":
        for changelog in targets(root):
            body, _, errors = render(changelog, root)
            for e in errors:
                print(f"error: {e}", file=sys.stderr)
            print(f"== {changelog.relative_to(root)}\n## [Unreleased]\n\n{body or '(no entries)'}\n")
        return 0

    date = option("--date") or datetime.date.today().isoformat()
    positional = [a for a in args if not a.startswith("--")]
    if len(positional) != 1:
        fail("usage: changelog.py release X.Y.Z [--date YYYY-MM-DD] [--dry-run]")
    if not targets(root):
        fail(f"no CHANGELOG.md with a {FRAGMENT_DIR}/ beside it")
    dry_run = "--dry-run" in args
    writes, deletes, notes = release(root, positional[0], date)
    for path in writes:
        print(f"{'would update' if dry_run else 'updated'} {path.relative_to(root)}")
    for path in deletes:
        print(f"{'would remove' if dry_run else 'removed'} {path.relative_to(root)}")
    for note in notes:
        print(f"note: {note}", file=sys.stderr)
    if not dry_run:
        for path, content in writes.items():
            path.write_text(content)
        for path in deletes:
            path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
