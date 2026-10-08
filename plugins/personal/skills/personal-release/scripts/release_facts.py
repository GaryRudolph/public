#!/usr/bin/env python3
"""Facts for the personal-release skill. Run from anywhere inside a repo.

Prints what a release decision needs: git state, the canonical build-version
string, tags and commits since the last release, every version field found
and its value, CHANGELOG state, release tooling, and which platform surfaces
the repo appears to ship. Makes no recommendation (not even a bump level):
the agent decides.

Usage:
    release_facts.py                 # facts
    release_facts.py --next minor    # also print version.txt bumped by a level
"""

import json
import re
import subprocess
import sys
from pathlib import Path

RELEASE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PRERELEASE = re.compile(r"-(rc|beta|alpha|pre|dev|snapshot)", re.IGNORECASE)
SKIP_DIRS = {"node_modules", ".git", "vendor", "target", "build", "dist", ".venv", "venv", "Pods", ".build", "DerivedData"}
MAX_COMMITS_LISTED = 30


def git(*args, check=False):
    result = subprocess.run(["git", *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if check and result.returncode:
        raise SystemExit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip() if result.returncode == 0 else ""


def tracked_files(root):
    listed = git("ls-files")
    if listed:
        paths = [root / p for p in listed.splitlines()]
    else:
        paths = [p for p in root.rglob("*") if p.is_file()]
    return [p for p in paths if p.is_file() and not SKIP_DIRS & set(p.relative_to(root).parts)]


def bump(version, level):
    match = RELEASE.match(version)
    if not match:
        raise SystemExit(f"version.txt holds {version!r}, not MAJOR.MINOR.PATCH")
    major, minor, patch = (int(p) for p in match.groups())
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SystemExit("level must be patch, minor, or major")


def toml_section_value(text, section, key):
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped == f"[{section}]"
            continue
        if in_section:
            m = re.match(rf'{key}\s*=\s*"([^"]*)"', stripped)
            if m:
                return m.group(1)
    return None


def version_fields(root, files):
    """Yield (path, field, value, note) for every version field found."""
    for path in files:
        rel = path.relative_to(root).as_posix()
        name = path.name
        try:
            if name == "version.txt":
                yield rel, "(file)", path.read_text().strip(), "source of truth"
            elif name == "package.json":
                data = json.loads(path.read_text())
                notes = []
                if data.get("private"):
                    notes.append("private")
                if "vscode" in (data.get("engines") or {}):
                    notes.append("VS Code extension")
                if "version" in data:
                    yield rel, "version", str(data["version"]), ", ".join(notes)
            elif name == "pyproject.toml":
                value = toml_section_value(path.read_text(), "project", "version") \
                    or toml_section_value(path.read_text(), "tool.poetry", "version")
                if value:
                    yield rel, "project.version", value, ""
            elif name == "Cargo.toml":
                value = toml_section_value(path.read_text(), "package", "version")
                if value:
                    yield rel, "package.version", value, ""
            elif name == "pom.xml":
                text = re.sub(r"<parent>.*?</parent>", "", path.read_text(), flags=re.S)
                m = re.search(r"<version>([^<]+)</version>", text)
                if m:
                    yield rel, "<version>", m.group(1), ""
            elif name in ("build.gradle", "build.gradle.kts"):
                text = path.read_text()
                for key in ("versionName", "version"):
                    m = re.search(rf'^\s*{key}\s*=?\s*"([^"]+)"', text, re.M)
                    if m:
                        yield rel, key, m.group(1), ""
            elif name == "project.pbxproj":
                for value in sorted(set(re.findall(r"MARKETING_VERSION = ([^;]+);", path.read_text()))):
                    yield rel, "MARKETING_VERSION", value.strip('"'), ""
            elif name == "Info.plist":
                m = re.search(r"<key>CFBundleShortVersionString</key>\s*<string>([^<]+)</string>", path.read_text())
                if m:
                    yield rel, "CFBundleShortVersionString", m.group(1), ""
            elif name.endswith(".csproj"):
                m = re.search(r"<Version>([^<]+)</Version>", path.read_text())
                if m:
                    yield rel, "<Version>", m.group(1), ""
            elif name == "snapcraft.yaml":
                m = re.search(r"^version:\s*['\"]?([^'\"\n]+)", path.read_text(), re.M)
                if m:
                    yield rel, "version", m.group(1), ""
            elif rel.startswith("Formula/") and name.endswith(".rb"):
                m = re.search(r'^\s*version\s+"([^"]+)"', path.read_text(), re.M)
                if m:
                    yield rel, "version", m.group(1), "Homebrew formula"
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            yield rel, "?", f"unreadable: {exc}", ""


def surfaces(root, files):
    names = {p.name for p in files}
    rels = [p.relative_to(root).as_posix() for p in files]
    found = []

    def has(pred):
        return any(pred(r) for r in rels)

    if "project.pbxproj" in names or has(lambda r: r.endswith("Info.plist")):
        found.append("iOS/Apple (CFBundleShortVersionString, CFBundleVersion)")
    if has(lambda r: r.endswith(("build.gradle", "build.gradle.kts"))) and has(lambda r: r.endswith("AndroidManifest.xml")):
        found.append("Android (versionName, versionCode)")
    for p in files:
        if p.name == "package.json":
            try:
                data = json.loads(p.read_text())
            except (OSError, ValueError):
                continue
            rel = p.relative_to(root).as_posix()
            if "vscode" in (data.get("engines") or {}):
                found.append(f"VS Code extension ({rel})")
            elif data.get("private"):
                found.append(f"web app / private package ({rel})")
            else:
                found.append(f"npm package ({rel})")
    if "pyproject.toml" in names:
        found.append("Python package (pyproject.toml)")
    if "Cargo.toml" in names:
        found.append("Rust crate (Cargo.toml)")
    if "pom.xml" in names:
        found.append("Maven artifact (pom.xml)")
    if has(lambda r: r.startswith("Formula/")) or has(lambda r: ".goreleaser" in r):
        found.append("Homebrew / GitHub Releases")
    if has(lambda r: Path(r).name.startswith("Dockerfile")):
        found.append("Docker / OCI image")
    if "snapcraft.yaml" in names or has(lambda r: r.endswith((".spec", "debian/control"))):
        found.append("Linux packages")
    if has(lambda r: r.endswith((".csproj", ".wxs", ".iss"))):
        found.append("Windows installer / .NET")
    if "go.mod" in names:
        found.append("Go module/binary (version via -ldflags at build)")
    return found


def main(argv):
    root = Path(git("rev-parse", "--show-toplevel") or ".").resolve()
    if not (root / ".git").exists():
        raise SystemExit("not inside a git repository")
    files = tracked_files(root)

    print("== git")
    branch = git("branch", "--show-current") or "(detached)"
    sha = git("rev-parse", "--short=7", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    shallow = git("rev-parse", "--is-shallow-repository") == "true"
    build_code = git("rev-list", "--count", "HEAD")
    print(f"  branch: {branch}")
    line = re.match(r"^release/v(\d+)(?:\.(\d+))?$", branch)
    if line:
        kind = "minor line: patches only" if line.group(2) is not None else "major line: patches and minors"
        print(f"  release line: v{line.group(1)}{'.' + line.group(2) if line.group(2) is not None else ''} ({kind})")
    print(f"  head: {sha}")
    print(f"  working tree: {'dirty' if dirty else 'clean'}")
    print(f"  shallow clone: {'yes (buildCode below undercounts; fetch full history)' if shallow else 'no'}")
    print(f"  buildCode (git rev-list --count HEAD): {build_code}")
    upstream = git("rev-parse", "--abbrev-ref", "@{upstream}")
    if upstream:
        ahead_behind = git("rev-list", "--left-right", "--count", f"{upstream}...HEAD").split()
        if len(ahead_behind) == 2:
            print(f"  vs {upstream}: behind {ahead_behind[0]}, ahead {ahead_behind[1]}")

    print("\n== tags")
    tags = git("tag", "-l", "v[0-9]*", "--sort=-v:refname").splitlines()
    print(f"  v-tags (newest first): {' '.join(tags[:10]) or 'none'}")
    nonconforming = [t for t in tags if not RELEASE.match(t[1:]) and not re.match(r"^v\d+(\.\d+)?$", t)]
    if nonconforming:
        print(f"  tags not matching vMAJOR.MINOR.PATCH: {' '.join(nonconforming[:10])}")
    last = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*")
    print(f"  last v-tag reachable from HEAD: {last or 'none'}")
    if last:
        count = git("rev-list", "--count", f"{last}..HEAD")
        print(f"  commits since {last}: {count}")
        log = git("log", "--no-merges", "--format=%h %s", f"-{MAX_COMMITS_LISTED}", f"{last}..HEAD")
        for line in log.splitlines():
            print(f"    {line}")
        if count and int(count) > MAX_COMMITS_LISTED:
            print(f"    ... {int(count) - MAX_COMMITS_LISTED} more")
    on_tag = git("tag", "--points-at", "HEAD", "-l", "v[0-9]*")
    if on_tag:
        print(f"  HEAD is tagged: {on_tag.replace(chr(10), ' ')}")

    print("\n== version fields")
    fields = list(version_fields(root, files))
    source = next((v for p, f, v, _ in fields if p == "version.txt"), None)
    if not fields:
        print("  none found")
    for path, field, value, note in fields:
        flags = []
        if PRERELEASE.search(value):
            flags.append("has a pre-release/dev suffix")
        if "+" in value:
            flags.append("has +build metadata")
        if source and path != "version.txt" and value != source:
            flags.append(f"differs from version.txt ({source})")
        extra = "; ".join(x for x in [note, *flags] if x)
        print(f"  {path}: {field} = {value}" + (f"  [{extra}]" if extra else ""))
    if source is None:
        print("  no version.txt at the repo root")
    if source:
        suffix = ".dirty" if dirty else ""
        print(f"  build-version for HEAD: {source}+{sha}{suffix} ({build_code})")

    print("\n== changelog")
    changelog = root / "CHANGELOG.md"
    if changelog.exists():
        text = changelog.read_text()
        m = re.search(r"^## \[Unreleased\][^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if m:
            entries = [l for l in m.group(1).splitlines() if l.strip().startswith(("-", "*"))]
            print(f"  ## [Unreleased]: {len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")
        else:
            print("  no ## [Unreleased] section")
        latest = re.search(r"^## \[(v?\d[^\]]*)\]", text, re.M)
        print(f"  latest released heading: {latest.group(1) if latest else 'none'}")
    else:
        print("  no CHANGELOG.md")
    for directory in sorted({p.parent for p in files if p.parent.name == ".changelog"}):
        kinds, bare = {}, 0
        fragment_files = sorted(directory.glob("*.txt"))
        for frag in fragment_files:
            found = re.findall(r"^```release-note:([A-Za-z-]*)", frag.read_text(errors="replace"), re.M)
            bare += not found
            for kind in found:
                kinds[kind] = kinds.get(kind, 0) + 1
        blocks = ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())) or "none"
        print(f"  {directory.relative_to(root).as_posix()}/: {len(fragment_files)} fragment file(s); "
              f"release-note blocks: {blocks}" + (f"; {bare} file(s) with no block" if bare else ""))

    print("\n== release tooling")
    rels = [p.relative_to(root).as_posix() for p in files]
    for rel in rels:
        if re.search(r"(^|/)bump[-_]version\.|(^|/)scripts/changelog\.py$", rel) or re.match(r"\.github/workflows/.*(release|backport|publish|deploy|changelog).*\.ya?ml$", rel):
            print(f"  {rel}")
    for rel in rels:
        if rel.startswith(".github/workflows/") and rel.endswith((".yml", ".yaml")):
            text = (root / rel).read_text(errors="replace")
            depths = sorted(set(re.findall(r"fetch-depth:\s*(\d+)", text)))
            if "actions/checkout" in text:
                print(f"  {rel}: checkout fetch-depth {', '.join(depths) or 'default (1, shallow)'}")

    print("\n== surfaces")
    for s in surfaces(root, files) or ["none detected"]:
        print(f"  {s}")

    print("\n== contract versions in source (Regime 1, counts)")
    counts = {}
    for p in files:
        if p.suffix in {".png", ".jpg", ".pdf", ".zip", ".jar", ".lock"} or p.name.endswith(".min.js"):
            continue
        try:
            for hit in re.findall(r"/api/v\d+\b", p.read_text(errors="ignore")):
                counts[hit] = counts.get(hit, 0) + 1
        except OSError:
            continue
    if counts:
        for hit, n in sorted(counts.items()):
            print(f"  {hit}: {n}")
    else:
        print("  no /api/vN paths found")

    if len(argv) >= 2 and argv[0] == "--next":
        if not source:
            raise SystemExit("--next needs version.txt")
        print(f"\n== next\n  {argv[1]}: {source} -> {bump(source, argv[1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
