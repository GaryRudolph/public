#!/usr/bin/env python3
"""Facts for the personal-review-guide skill.

Prints what the agent needs to write a review guide for the change on the
current branch: the base it diffs against, the commits, every changed file
with its line counts and the bucket its path falls in, test lines removed,
paths that name a risk area (security, financial, concurrency, PII), the
changed files that are hotspots, each file's GitHub diff anchor, the repo's
review surfaces, the PR template, and the plan, handoff and review files
already on the branch.

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
import hashlib
import os
import re
import subprocess
import sys
import threading

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

# Path words that point at the risk tags' areas (review.md "Risk tags"). A
# fact about the name only: the agent reads the code to decide. Words match
# at the start of a path token (after / _ . - or a camelCase hump), so
# "lock" finds lock_manager.go but not block.tsx or clock.go.
RISK_WORDS = [
    ("security", r"auth|crypt|secret|token|permission|password|passwd|session|oauth|jwt|credential|acl|rbac|"
                 r"signing|cert|key(?:s|store|chain)?(?![a-z])|login"),
    ("financial", r"payment|billing|invoice|charge|refund|ledger|payout|wallet|stripe|checkout|subscription|"
                  r"pricing|price"),
    ("concurrency", r"thread|async|concurren|parallel|mutex|lock|semaphore|atomic|queue|worker|goroutine|"
                    r"scheduler|retry|retries|idempot"),
    ("pii", r"pii|personal|ssn|passport|birth|phone|email|consent|gdpr|kyc|medical|patient"),
]
RISK_WORDS = [(tag, re.compile(rf"(?<![a-z0-9])(?:{words})")) for tag, words in RISK_WORDS]


def risk_tokens(path):
    """The path lowercased, with camelCase humps split so each word starts a token."""
    path = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", path)  # APIKey -> API_Key
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", path).lower()

# Hotspots (review.md "Risk tags"): files in these buckets, scored by commits
# touching them in the window times their lines, top HOTSPOT_LIMIT. A fixed
# sort, shared with personal-codebase-review's full review.
HOTSPOT_LIMIT = 15
HOTSPOT_BUCKETS = ("source", "orchestration", "api", "schema")
HOTSPOT_DAYS = 180

SURFACE_HINT = re.compile(r"before|after|visual|render|screenshot|snapshot|diagram|golden", re.I)

PR_TEMPLATES = [".github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE.md", "PULL_REQUEST_TEMPLATE.md",
                "pull_request_template.md", "docs/pull_request_template.md", "docs/PULL_REQUEST_TEMPLATE.md"]


GITHUB_REMOTE = re.compile(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/*$")


def git(*args, check=False):
    r = subprocess.run(["git", "-c", "core.quotePath=false", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout.strip() if r.returncode == 0 else ""


def bucket(path):
    for name, patterns in BUCKETS:
        if any(fnmatch.fnmatchcase(path, p) for p in patterns):
            return name
    return "source"


def hotspots(repo, ref, days=HOTSPOT_DAYS):
    """(score, commits, lines, path) for the top files at ref, highest first.

    Commits count under the path the file has at ref, following renames in
    the window, and every file is read through one `git cat-file --batch`.
    """
    counts = {}
    for path, commits in churn(repo, ref, days).items():
        if bucket(path) in HOTSPOT_BUCKETS:
            counts[path] = commits
    rows = [(counts[path] * lines, counts[path], lines, path) for path, lines in line_counts(repo, ref, counts)]
    rows.sort(reverse=True)
    return rows[:HOTSPOT_LIMIT]


def churn(repo, ref, days):
    """Commits per path in the window, each counted under the path's newest name."""
    log = subprocess.run(["git", "log", f"--since={days}.days", "-M", "-z", "--format=%x00", "--name-status", ref],
                         cwd=repo, capture_output=True).stdout.decode("utf-8", "surrogateescape")
    fields = log.split("\0")
    newest = {}  # old name -> the name it has at ref, from renames seen so far (log runs newest first)
    counts = {}
    i = 0
    while i < len(fields):
        status = fields[i].strip("\n")
        if not status:
            i += 1
            continue
        if status[0] in "RC" and i + 2 < len(fields):
            old, new = fields[i + 1], fields[i + 2]
            if status[0] == "R":
                newest[old] = newest.get(new, new)
            path = newest.get(new, new)
            i += 3
        else:
            path = newest.get(fields[i + 1], fields[i + 1]) if i + 1 < len(fields) else ""
            i += 2
        if path:
            counts[path] = counts.get(path, 0) + 1
    return counts


def line_counts(repo, ref, paths):
    """(path, lines) for each text file present at ref, streamed through one cat-file process."""
    proc = subprocess.Popen(["git", "cat-file", "--batch"], cwd=repo, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    paths = list(paths)

    def feed():
        for path in paths:
            proc.stdin.write(f"{ref}:{path}\n".encode("utf-8", "surrogateescape"))
        proc.stdin.close()

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    out = proc.stdout
    for path in paths:
        line = out.readline()
        if not line or line.rstrip(b"\n").endswith(b" missing"):
            continue  # "<ref:path> missing" (the path may hold spaces): deleted since, no payload follows
        header = line.split()
        remaining, lines, is_text, first = int(header[2]), 0, header[1] == b"blob", True
        while remaining:  # every object's payload is read, so the next header lines up
            chunk = out.read(min(remaining, 65536))
            if not chunk:
                break
            if first and b"\0" in chunk[:8000]:
                is_text = False  # binary
            first = False
            lines += chunk.count(b"\n")
            remaining -= len(chunk)
        out.read(1)  # the newline after each payload
        if is_text:
            yield path, lines
    writer.join()
    proc.wait()


def is_shallow(repo):
    """A shallow clone's log misses older commits, so its hotspot counts are low."""
    r = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=repo, capture_output=True, text=True)
    return r.stdout.strip() == "true"


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


def github_repo():
    m = GITHUB_REMOTE.search(git("remote", "get-url", "origin"))
    return f"{m.group(1)}/{m.group(2)}" if m else "none"


def diff_anchor(path):
    """GitHub's anchor for a file in a PR's or compare view's diff: sha256 of the path."""
    return "diff-" + hashlib.sha256(path.encode("utf-8")).hexdigest()


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
    print(f"github_repo: {github_repo()} (from origin)")
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

    print("\n== paths naming a risk area (tag word path)")
    for f in files:
        for tag, words in RISK_WORDS:
            m = words.search(risk_tokens(f["path"]))
            if m:
                print(f"  {tag} {m.group(0).lower()}: {f['path']}")

    # Ranked at the merge base, so its paths line up with the diff's even if
    # the base branch renamed a file since.
    print(f"\n== hotspots changed (rank score=commits_in_{HOTSPOT_DAYS}d*lines path, "
          f"at merge_base {git('rev-parse', '--short', merge_base) if merge_base else 'none'})")
    if merge_base and is_shallow(root):
        print("  unavailable: shallow clone; deepen past the window first "
              f"(git fetch --shallow-since=\"{HOTSPOT_DAYS} days ago\" origin, or --unshallow)")
    elif merge_base:
        # A renamed hotspot ranks under its base path; report where it went.
        changed = {}
        for f in files:
            changed[f["path"]] = f["path"]
            if f["old"]:
                changed[f["old"]] = f["path"]
        for rank, (score, commits, lines, path) in enumerate(hotspots(root, merge_base), 1):
            if path in changed:
                moved = f" (from {path})" if changed[path] != path else ""
                print(f"  {rank} {score}={commits}*{lines} {changed[path]}{moved}")

    print("\n== diff anchors (path #anchor)")
    for f in files:
        print(f"  {f['path']} #{diff_anchor(f['path'])}")

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
