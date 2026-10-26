#!/usr/bin/env python3
"""Facts for the personal-review-guide skill.

Prints what the agent needs to write a review guide for the change on the
current branch: the base it diffs against, the commits, every changed file
with its line counts and the bucket its path falls in, test lines removed,
paths that name a sensitive area, the repo's review surfaces, the PR
template, and the plan, handoff and review files already on the branch.

Emits no verdicts. Buckets come from the fixed path table below, which
reference.md documents; the agent reads the code and assigns the review
tags (core.md "Facts in script, judgment in agent").

Usage: review_facts.py [--base <ref>] [--committed] [<repo>]
  --base <ref>   diff against the merge-base with <ref> (default: the
                 remote's default branch)
  --committed    diff the merge-base against HEAD only; by default the
                 working tree's uncommitted changes to tracked files count
"""

import argparse
import fnmatch
import os
import re
import subprocess
import sys

# First match wins. Keep in step with reference.md "Bucket table".
BUCKETS = [
    ("generated", [
        "*package-lock.json", "*pnpm-lock.yaml", "*yarn.lock", "*go.sum", "*Cargo.lock", "*poetry.lock", "*uv.lock",
        "*Gemfile.lock", "*Package.resolved", "*composer.lock", "*bun.lockb", "*.min.js", "*.min.css",
        "gen/*", "*/gen/*", "generated/*", "*/generated/*", "*_pb2.py", "*_pb2_grpc.py", "*.pb.go", "*.g.dart",
        "vendor/*", "*/vendor/*", "*/__snapshots__/*", "*.snap",
    ]),
    ("tests", [
        "test/*", "*/test/*", "tests/*", "*/tests/*", "*/__tests__/*", "spec/*", "*/spec/*",
        "*_test.go", "test_*.py", "*/test_*.py", "*_test.py", "*.test.[jt]s", "*.test.[jt]sx", "*.spec.[jt]s",
        "*.spec.[jt]sx", "*Tests.swift", "*Test.kt", "*Tests.kt", "*Test.java", "conftest.py", "*/conftest.py",
    ]),
    ("schema", [
        "migrations/*", "*/migrations/*", "migrate/*", "*/migrate/*", "alembic/*", "*/alembic/*",
        "*.sql", "*.prisma", "schema.*", "*/schema.*", "*.avsc",
    ]),
    ("api", [
        "*.proto", "openapi*", "*/openapi*", "swagger*", "*/swagger*", "*.graphql", "*.gql", "*.schema.json",
        "api/*", "*/api/*", "routes/*", "*/routes/*", "handlers/*", "*/handlers/*", "controllers/*", "*/controllers/*",
    ]),
    ("config", [
        "Dockerfile*", "*/Dockerfile*", "*.tf", "*.tfvars", ".github/*", "k8s/*", "*/k8s/*", "helm/*", "*/helm/*",
        "charts/*", "*/charts/*", "Makefile", "*/Makefile", "*.mk", "package.json", "*/package.json", "go.mod",
        "*/go.mod", "Cargo.toml", "*/Cargo.toml", "pyproject.toml", "*/pyproject.toml", "requirements*.txt",
        "*.yaml", "*.yml", "*.toml", "*.ini", ".env*", "*/.env*", ".claude/*", "*/hooks/*.json",
    ]),
    ("docs", ["*.md", "*.mdx", "*.mdc", "*.rst", "docs/*", "*/docs/*", "LICENSE*", "*.txt"]),
    ("orchestration", [
        "*orchestrat*", "*workflow*", "*pipeline*", "*scheduler*", "*/jobs/*", "*/workers/*", "*/worker/*", "*queue*",
        "*saga*", "*dispatch*",
    ]),
]

# Path words that point at the [study] checklist's sensitive areas. A fact
# about the name only: the agent reads the code to decide.
SENSITIVE = re.compile(r"auth|crypt|secret|token|permission|password|passwd|session|oauth|jwt|credential|acl|rbac|"
                       r"signing|cert|key(?:s|store|chain)?\b|login", re.I)

SURFACE_HINT = re.compile(r"before|after|visual|render|screenshot|snapshot|diagram|golden", re.I)

PR_TEMPLATES = [".github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE.md", "PULL_REQUEST_TEMPLATE.md",
                "pull_request_template.md", "docs/pull_request_template.md", "docs/PULL_REQUEST_TEMPLATE.md"]


def git(*args, check=False):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout.strip() if r.returncode == 0 else ""


def bucket(path):
    for name, patterns in BUCKETS:
        if any(fnmatch.fnmatchcase(path, p) for p in patterns):
            return name
    return "source"


def default_base():
    head = git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if head:
        return head.removeprefix("refs/remotes/"), "origin/HEAD"
    for ref in ("origin/main", "origin/master", "main", "master"):
        if git("rev-parse", "--verify", "--quiet", ref):
            return ref, "first that exists of origin/main, origin/master, main, master"
    return "", "none found"


def changed_files(base, committed):
    target = [base, "HEAD"] if committed else [base]
    numstat = git("diff", "--numstat", "-M", "-z", *target)
    status = git("diff", "--name-status", "-M", *target)
    statuses = []
    for line in status.splitlines():
        parts = line.split("\t")
        statuses.append((parts[0][0], parts[-1], parts[1] if len(parts) == 3 else ""))
    counts = {}
    # -z numstat: "added\tdeleted\tpath\0" or, for a rename, "added\tdeleted\t\0old\0new\0".
    fields = numstat.split("\0")
    i = 0
    while i < len(fields):
        if not fields[i]:
            i += 1
            continue
        added, deleted, path = fields[i].split("\t", 2)
        if path == "" and i + 2 < len(fields):
            path = fields[i + 2]
            i += 3
        else:
            i += 1
        counts[path] = (added, deleted)
    files = []
    for code, path, old in statuses:
        added, deleted = counts.get(path, ("0", "0"))
        files.append({"status": code, "path": path, "old": old, "added": added, "deleted": deleted,
                      "bucket": bucket(path)})
    return files


def to_int(n):
    return int(n) if n.isdigit() else 0


def section(text, heading):
    """The body of a `## heading` section, up to the next `## ` heading, or None."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(r"^##\s+" + re.escape(heading) + r"\s*$", line, re.I):
            body = []
            for rest in lines[i + 1:]:
                if re.match(r"^##\s", rest):
                    break
                body.append(rest)
            return "\n".join(body).strip("\n")
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base")
    ap.add_argument("--committed", action="store_true")
    ap.add_argument("repo", nargs="?", default=".")
    args = ap.parse_args()

    os.chdir(args.repo)
    root = git("rev-parse", "--show-toplevel")
    if not root:
        print(f"not a git repository: {os.path.abspath(args.repo)}", file=sys.stderr)
        return 1
    os.chdir(root)

    base_ref, how = (args.base, "--base") if args.base else default_base()
    merge_base = git("merge-base", "HEAD", base_ref) if base_ref else ""

    print(f"repo_root: {root}")
    print(f"branch: {git('branch', '--show-current') or '(detached)'}")
    print(f"head: {git('rev-parse', '--short', 'HEAD')}")
    print(f"base_ref: {base_ref or 'none'} ({how})")
    print(f"merge_base: {git('rev-parse', '--short', merge_base) if merge_base else 'none'}")
    print(f"diff: {'merge_base..HEAD' if args.committed else 'merge_base..working tree (tracked files)'}")
    print(f"claude_code_remote: {os.environ.get('CLAUDE_CODE_REMOTE', 'unset')}")

    print("\n== commits since merge_base")
    if merge_base:
        for line in git("log", "--format=%h %s", f"{merge_base}..HEAD").splitlines():
            print(f"  {line}")

    files = changed_files(merge_base, args.committed) if merge_base else []
    print("\n== changed files (status +added -deleted bucket path)")
    for f in files:
        moved = f" (from {f['old']})" if f["old"] else ""
        print(f"  {f['status']} +{f['added']} -{f['deleted']} {f['bucket']} {f['path']}{moved}")
    untracked = git("ls-files", "--others", "--exclude-standard")
    if untracked and not args.committed:
        print("\n== untracked files (not in the diff)")
        for path in untracked.splitlines():
            print(f"  {bucket(path)} {path}")

    print("\n== totals by bucket (files +added -deleted)")
    totals = {}
    for f in files:
        t = totals.setdefault(f["bucket"], [0, 0, 0])
        t[0] += 1
        t[1] += to_int(f["added"])
        t[2] += to_int(f["deleted"])
    for name in [b for b, _ in BUCKETS] + ["source"]:
        if name in totals:
            n, a, d = totals[name]
            print(f"  {name}: {n} +{a} -{d}")
    print(f"  all: {len(files)} +{sum(t[1] for t in totals.values())} -{sum(t[2] for t in totals.values())}")

    print("\n== test lines removed (status -deleted path)")
    for f in files:
        if f["bucket"] == "tests" and (f["status"] == "D" or to_int(f["deleted"]) > 0):
            print(f"  {f['status']} -{f['deleted']} {f['path']}")

    print("\n== paths naming a sensitive area")
    for f in files:
        m = SENSITIVE.search(f["path"])
        if m:
            print(f"  {m.group(0).lower()}: {f['path']}")

    print("\n== review surfaces")
    found = False
    for name in ("AGENTS.md", "CLAUDE.md"):
        if not os.path.isfile(name):
            continue
        text = open(name, encoding="utf-8", errors="replace").read()
        body = section(text, "Review surfaces")
        if body is not None:
            found = True
            print(f"  from {name}:")
            for line in body.splitlines():
                print(f"    {line}")
        outside = set(text.splitlines()) - set((body or "").splitlines())
        hints = [line for line in text.splitlines() if line in outside and re.match(r"^#{2,4}\s", line)
                 and SURFACE_HINT.search(line) and not re.match(r"^##\s+Review surfaces\s*$", line, re.I)]
        for line in hints:
            print(f"  heading in {name} that mentions before/after, renders or snapshots: {line.strip()}")
            found = True
    if not found:
        print("  none")

    print("\n== PR template")
    templates = [p for p in PR_TEMPLATES if os.path.isfile(p)]
    if os.path.isdir(".github/PULL_REQUEST_TEMPLATE"):
        templates += sorted(os.path.join(".github/PULL_REQUEST_TEMPLATE", p)
                            for p in os.listdir(".github/PULL_REQUEST_TEMPLATE"))
    for p in templates:
        text = open(p, encoding="utf-8", errors="replace").read()
        has = "yes" if re.search(r"^##\s+Review guide\s*$", text, re.M | re.I) else "no"
        print(f"  {p} (has ## Review guide: {has})")
    if not templates:
        print("  none")

    print("\n== plan, handoff and review files")
    listed = False
    for d in (".scratch", "specs/handoffs"):
        if os.path.isdir(d):
            for p in sorted(os.listdir(d)):
                if p.endswith(".md") and (p.startswith(("plan-", "handoff-")) or p.endswith("-review.md")):
                    print(f"  {d}/{p}")
                    listed = True
    if not listed:
        print("  none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
