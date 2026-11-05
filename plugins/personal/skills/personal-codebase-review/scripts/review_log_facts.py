#!/usr/bin/env python3
"""Facts for the personal-codebase-review skill.

Prints what the agent needs to decide on and scope a review of the default
branch: the layout, the estate's members if asked, and per repo the default
branch and its head, the review log's rows, the last anchor and whether it
is still reachable, days and churn since it, hotspots, the open and accepted
findings in earlier registers, and the next review number.

Emits no verdicts: whether a review is due, which kind, and what a finding
means are the agent's call from standards/codebase-review.md. Churn buckets
come from personal-review-guide's fixed path table; hotspots are sorted by
the fixed formula in reference.md (core.md "Facts in script, judgment in
agent").

Usage: review_log_facts.py [--members <list|glob>] [--owner <owner>]
                           [--hotspot-days N] [--no-fetch] [<repo>]
  <repo>          the home repo, or a workspace or plain folder (default .)
  --members       comma-separated repo names or a glob (nowline*): matched
                  against the folders beside the home repo (for a workspace,
                  inside it and then beside it), and against the owner's
                  GitHub repos through gh when gh is available
  --owner         GitHub owner for --members (default: from origin's URL)
  --hotspot-days  look-back for hotspots (default 180)
  --no-fetch      don't fetch the default branch before reading it
"""

import argparse
import datetime
import fnmatch
import importlib.util
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REVIEW_FACTS = os.path.join(HERE, "..", "..", "personal-review-guide", "scripts", "review_facts.py")

LOG = "specs/reviews/README.md"
ROW = re.compile(r"^\|\s*r(\d+)\s*\|")
FINDING = re.compile(r"^###\s+(r\d+\.f\d+)\s+-\s+(.*)$")
FIELD = re.compile(r"^-\s+(Severity|Kind|Status|Location|Reason|Resolution):\s*(.*)$")
RANGE = re.compile(r"^([0-9a-f]*)\.\.([0-9a-f]+)$")
HOTSPOT_LIMIT = 15
HOTSPOT_BUCKETS = ("source", "orchestration", "api", "schema")


def load_buckets():
    spec = importlib.util.spec_from_file_location("review_facts", REVIEW_FACTS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.bucket


bucket = load_buckets()


def run(cmd, cwd, check=False):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or " ".join(cmd) + " failed")
    return r.stdout.strip() if r.returncode == 0 else ""


def git(cwd, *args):
    return run(["git", *args], cwd)


def is_repo(path):
    return os.path.exists(os.path.join(path, ".git"))


def detect_layout(root):
    """Same order as personal-makefile's audit.sh detect_layout."""
    if os.path.isfile(os.path.join(root, "repos.mk")) and os.path.isfile(os.path.join(root, "Makefile")):
        return "workspace"
    if os.path.isfile(os.path.join(root, ".gitmodules")):
        return "submodule_estate"
    if not is_repo(root):
        children = [d for d in sorted(os.listdir(root)) if is_repo(os.path.join(root, d))]
        if len(children) > 1:
            return "plain_folder"
        return "not_a_repo"
    return "single_repo"


def repos_mk_members(root):
    """REPOS from repos.mk, through make when it's installed, else the plain assignments."""
    if shutil.which("make"):
        out = subprocess.run(["make", "-s", "--no-print-directory", "-f", "repos.mk", "-f", "-", "_print_repos"],
                             cwd=root, input="_print_repos:\n\t@echo $(REPOS)\n", capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.split()
    names = []
    with open(os.path.join(root, "repos.mk")) as f:
        text = f.read().replace("\\\n", " ")
    for m in re.finditer(r"^REPOS\s*(\+?[:?]?=)\s*(.*)$", text, re.M):
        names = (names if m.group(1).startswith("+") else []) + m.group(2).split()
    return names


def default_branch(repo, fetch):
    head = git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    name = head.removeprefix("refs/remotes/origin/") if head else ""
    if not name:
        for candidate in ("main", "master"):
            if git(repo, "rev-parse", "--verify", "--quiet", f"origin/{candidate}") or \
                    git(repo, "rev-parse", "--verify", "--quiet", candidate):
                name = candidate
                break
    if not name:
        return "", "", "none found"
    fetched = "not fetched"
    if fetch and git(repo, "remote"):
        deepen = ["--unshallow"] if is_shallow(repo) else []
        r = subprocess.run(["git", "fetch", "-q", *deepen, "origin", name], cwd=repo, capture_output=True, text=True)
        fetched = ("fetched, unshallowed" if deepen else "fetched") if r.returncode == 0 else "fetch failed"
    ref = f"origin/{name}" if git(repo, "rev-parse", "--verify", "--quiet", f"origin/{name}") else name
    return name, ref, fetched


def is_shallow(repo):
    return git(repo, "rev-parse", "--is-shallow-repository") == "true"


def origin_owner(repo):
    url = git(repo, "remote", "get-url", "origin")
    m = re.search(r"[:/]([^/:]+)/[^/]+?(?:\.git)?/?$", url)
    return m.group(1) if m else ""


def show(repo, ref, path):
    """A file's text at ref, or None when it isn't there."""
    r = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=repo, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def log_rows(repo, ref):
    text = show(repo, ref, LOG)
    if text is None:
        return None
    rows = []
    for line in text.splitlines():
        if not ROW.match(line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        cells += [""] * (8 - len(cells))
        rows.append(dict(zip(("review", "date", "kind", "range", "findings", "issue", "outcome", "record"), cells)))
    return rows


def registers(repo, ref):
    names = git(repo, "ls-tree", "--name-only", f"{ref}:specs/reviews")
    return sorted(f"specs/reviews/{n}" for n in names.splitlines() if n.endswith("-findings.md"))


def findings(repo, ref, path):
    found, current = [], None
    for line in (show(repo, ref, path) or "").splitlines():
        m = FINDING.match(line)
        if m:
            current = {"id": m.group(1), "title": m.group(2).strip(), "file": os.path.basename(path)}
            found.append(current)
            continue
        if line.startswith("## ") or line.startswith("### "):
            current = None
            continue
        m = FIELD.match(line.strip())
        if current is not None and m:
            current[m.group(1).lower()] = m.group(2).strip()
    return found


def register_header(repo, ref, path, key):
    for line in (show(repo, ref, path) or "").splitlines():
        m = re.match(r"^-?\s*" + key + r":\s*(.*)$", line.strip())
        if m:
            return m.group(1).strip()
        if FINDING.match(line):
            break
    return ""


def status_word(value):
    """The first word of a Status value, without backticks or punctuation."""
    m = re.match(r"[`*_\s]*([A-Za-z-]+)", value or "")
    return m.group(1).lower() if m else ""


def resolve(repo, short):
    return git(repo, "rev-parse", "--verify", "--quiet", f"{short}^{{commit}}") if short else ""


def churn(repo, frm, to):
    """Changed files and lines since the anchor, by bucket and by directory (two levels deep)."""
    by_bucket, by_dir = {}, {}
    for line in git(repo, "diff", "--numstat", "--no-renames", f"{frm}..{to}").splitlines():
        added, deleted, path = line.split("\t", 2)
        parts = path.split("/")[:-1][:2]
        for key, totals in ((bucket(path), by_bucket), ("/".join(parts) + "/" if parts else "(root)", by_dir)):
            t = totals.setdefault(key, [0, 0, 0])
            t[0] += 1
            t[1] += int(added) if added.isdigit() else 0
            t[2] += int(deleted) if deleted.isdigit() else 0
    return by_bucket, by_dir


def hotspots(repo, ref, days):
    """Files in source-like buckets, by commits in the window times current lines (reference.md)."""
    since = f"--since={days}.days"
    counts = {}
    for path in git(repo, "log", since, "--format=", "--name-only", ref).splitlines():
        if path and bucket(path) in HOTSPOT_BUCKETS:
            counts[path] = counts.get(path, 0) + 1
    rows = []
    for path, commits in counts.items():
        blob = subprocess.run(["git", "cat-file", "-p", f"{ref}:{path}"], cwd=repo, capture_output=True)
        if blob.returncode != 0 or b"\0" in blob.stdout[:8000]:
            continue  # deleted since, or binary
        lines = blob.stdout.count(b"\n")
        rows.append((commits * lines, commits, lines, path))
    rows.sort(reverse=True)
    return rows[:HOTSPOT_LIMIT]


def days_since(date):
    try:
        return (datetime.date.today() - datetime.date.fromisoformat(date)).days
    except ValueError:
        return None


def report_repo(repo, args):
    print(f"\n== repo {os.path.basename(repo)} ({repo})")
    name, ref, fetched = default_branch(repo, not args.no_fetch)
    if not ref:
        print("  default_branch: none found")
        return
    head = git(repo, "rev-parse", ref)
    print(f"  default_branch: {name} ({ref}, {fetched})")
    print(f"  head: {head}")
    print(f"  checked_out: {git(repo, 'branch', '--show-current') or '(detached)'}")
    print(f"  shallow: {'yes' if is_shallow(repo) else 'no'}")
    print(f"  records_read_from: {ref}")

    rows = log_rows(repo, ref)
    if rows is None:
        print(f"  log: none ({LOG} missing on {ref})")
    else:
        print(f"  log: {LOG}, {len(rows)} rows")
        for r in rows:
            print(f"    {r['review']} {r['date']} {r['kind']} {r['range']} | findings: {r['findings']} | "
                  f"issue: {r['issue']} | outcome: {r['outcome']}")
        last = max((int(r["review"][1:]) for r in rows if r["review"][1:].isdigit()), default=0)
        print(f"  logged_last: r{last}")

    pending = sorted(set(re.findall(r"refs/heads/(review/r(\d+)-\S+)", git(repo, "ls-remote", "--heads", "origin",
                                                                       "review/r*")) +
                         re.findall(r"^\*?\s*(review/r(\d+)-\S+)$", git(repo, "branch", "--list", "review/r*"), re.M)))
    print(f"  unmerged_review_branches: {', '.join(b for b, _ in pending) or 'none'}")
    taken = [int(r["review"][1:]) for r in (rows or []) if r["review"][1:].isdigit()] + [int(n) for _, n in pending]
    print(f"  next_review: r{max(taken, default=0) + 1}")

    anchors = [r for r in (rows or []) if r["kind"] in ("incremental", "full")]
    for label, pool in (("last_anchor", anchors), ("last_full", [r for r in anchors if r["kind"] == "full"]),
                        ("last_estate", [r for r in (rows or []) if r["kind"] == "estate"])):
        if not pool:
            print(f"  {label}: none")
            continue
        r = pool[-1]
        m = RANGE.match(r["range"].replace(" ", ""))
        to_sha = resolve(repo, m.group(2)) if m else ""
        days = days_since(r["date"])
        reach = "unknown"
        if to_sha:
            reach = "yes" if subprocess.run(["git", "merge-base", "--is-ancestor", to_sha, head], cwd=repo,
                                            capture_output=True).returncode == 0 else "no"
        found = "yes" if to_sha else ("outside local history (shallow)" if is_shallow(repo) else "no")
        print(f"  {label}: {r['review']} {r['kind']} {r['date']} to={to_sha or (m.group(2) if m else '?')} "
              f"days_since={days if days is not None else '?'} found={found} "
              f"reachable_from_default={reach}")
        if label == "last_anchor" and to_sha and reach == "yes":
            commits = git(repo, "rev-list", "--count", f"{to_sha}..{head}")
            totals, dirs = churn(repo, to_sha, head)
            added = sum(t[1] for t in totals.values())
            deleted = sum(t[2] for t in totals.values())
            print(f"  since_anchor: commits={commits} files={sum(t[0] for t in totals.values())} "
                  f"+{added} -{deleted} changed_lines={added + deleted}")
            for b, (n, a, d) in sorted(totals.items()):
                print(f"    {b}: {n} +{a} -{d}")
            print("  since_anchor_by_dir (changed_lines files +added -deleted dir, largest first):")
            for path, (n, a, d) in sorted(dirs.items(), key=lambda kv: -(kv[1][1] + kv[1][2])):
                print(f"    {a + d} {n} +{a} -{d} {path}")

    print(f"  hotspots (score=commits_in_{args.hotspot_days}d*lines commits lines path):")
    for score, commits, lines, path in hotspots(repo, ref, args.hotspot_days):
        print(f"    {score} {commits} {lines} {path}")

    regs = registers(repo, ref)
    open_, accepted, other = [], [], []
    for path in regs:
        for f in findings(repo, ref, path):
            status = status_word(f.get("status"))
            if status in ("open", "deferred", ""):
                open_.append(f)
            elif status == "accepted":
                accepted.append(f)
            elif status not in ("fixed", "decided"):
                other.append(f)
    print(f"  registers: {len(regs)}")
    print(f"  open_findings ({len(open_)}): id | status | severity | kind | location | resolution | title")
    for f in open_:
        print(f"    {f['id']} | {f.get('status', '?')} | {f.get('severity', '?')} | {f.get('kind', '?')} | "
              f"{f.get('location', '?')} | {f.get('resolution', '-')} | {f['title']}")
    print(f"  accepted_findings ({len(accepted)}): id | location | title | reason")
    for f in accepted:
        print(f"    {f['id']} | {f.get('location', '?')} | {f['title']} | {f.get('reason', '(no reason)')}")
    print(f"  other_status_findings ({len(other)}): id | status | title")
    for f in other:
        print(f"    {f['id']} | {f.get('status')} | {f['title']}")

    estate_regs = [p for p in regs if p.endswith("-estate-findings.md")]
    if estate_regs:
        print(f"  last_estate_members: {register_header(repo, ref, estate_regs[-1], 'Members') or '(none recorded)'}"
              f" ({os.path.basename(estate_regs[-1])})")


def github_repos(owner, cwd):
    """The owner's repo names over REST (an org's, then the signed-in user's own), or an error."""
    if not owner:
        return None, "owner unknown (pass --owner)"
    if not shutil.which("gh"):
        return None, "gh missing"
    errors = []
    for path in (f"orgs/{owner}/repos?type=all&per_page=100", "user/repos?affiliation=owner&per_page=100",
                 f"users/{owner}/repos?per_page=100"):
        r = subprocess.run(["gh", "api", "--paginate", path, "-q", ".[] | .owner.login + \"/\" + .name"], cwd=cwd,
                           capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f"{path.split('?')[0]}: {(r.stderr.strip().splitlines() or ['failed'])[-1]}")
            continue
        names = [n.split("/", 1)[1] for n in r.stdout.splitlines() if n.lower().startswith(owner.lower() + "/")]
        if names:
            return names, ""
    return None, "error: " + "; ".join(errors) if errors else "none listed"


def member_path(root, name):
    """A workspace member's clone: inside the workspace, else beside it (how a runner clones)."""
    inside = os.path.join(root, name)
    if is_repo(inside):
        return inside, "inside"
    beside = os.path.join(os.path.dirname(root), name)
    if beside != root and is_repo(beside):
        return beside, "beside"
    return None, None


def parse_patterns(spec):
    return [p.strip() for p in spec.split(",") if p.strip()]


def local_matches(patterns, folder):
    return sorted(d for d in os.listdir(folder) if is_repo(os.path.join(folder, d))
                  and any(fnmatch.fnmatchcase(d, p) for p in patterns))


def match_members(spec, folder, owner):
    """Local folders, then the owner's GitHub repos, matching a list or a glob."""
    patterns = parse_patterns(spec)
    local = local_matches(patterns, folder)
    names, problem = github_repos(owner, folder)
    remote = sorted(n for n in (names or []) if any(fnmatch.fnmatchcase(n, p) for p in patterns))
    return local, remote, problem


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--members")
    ap.add_argument("--owner")
    ap.add_argument("--hotspot-days", type=int, default=180)
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("repo", nargs="?", default=".")
    args = ap.parse_args()

    root = os.path.abspath(args.repo)
    top = git(root, "rev-parse", "--show-toplevel") if is_repo(root) or git(root, "rev-parse", "--git-dir") else ""
    root = top or root
    layout = detect_layout(root)
    print(f"root: {root}")
    print(f"layout: {layout}")
    print(f"today: {datetime.date.today().isoformat()}")
    print(f"gh: {'available' if shutil.which('gh') else 'missing'}")
    print(f"claude_code_remote: {os.environ.get('CLAUDE_CODE_REMOTE', 'unset')}")

    repos = []
    if layout in ("single_repo", "submodule_estate", "workspace"):
        repos.append(root)

    if args.members:
        folder = root if layout in ("plain_folder", "not_a_repo", "workspace") else os.path.dirname(root)
        owner = args.owner or origin_owner(root)
        local, remote, problem = match_members(args.members, folder, owner)
        print(f"\n== members from --members '{args.members}' (owner: {owner or 'unknown'})")
        print(f"  local ({folder}): {', '.join(local) or 'none'}")
        cloned = [os.path.join(folder, d) for d in local]
        if layout == "workspace":
            parent = os.path.dirname(root)
            try:
                beside = [d for d in local_matches(parse_patterns(args.members), parent)
                          if d not in local and os.path.join(parent, d) != root]
                print(f"  local_beside ({parent}): {', '.join(beside) or 'none'}")
            except OSError as e:
                beside = []
                print(f"  local_beside ({parent}): unreadable ({e.strerror or e})")
            local = local + beside
            cloned += [os.path.join(parent, d) for d in beside]
        print(f"  github: {problem or ', '.join(remote) or 'none matched'}")
        print(f"  github_not_cloned: {'unknown' if problem else ', '.join(n for n in remote if n not in local) or 'none'}")
        repos += [p for p in cloned if p != root]
    elif layout == "workspace":
        names = repos_mk_members(root)
        print(f"\n== members from repos.mk: {', '.join(names) or 'none'}")
        for n in names:
            path, where = member_path(root, n)
            print(f"  {n}: {f'cloned {where} ({path})' if path else 'not cloned'}")
            if path:
                repos.append(path)
    elif layout == "submodule_estate":
        paths = re.findall(r"^\s*path\s*=\s*(.+)$", open(os.path.join(root, ".gitmodules")).read(), re.M)
        print(f"\n== submodules (candidates, not members until confirmed): {', '.join(p.strip() for p in paths)}")
    elif layout == "plain_folder":
        names = sorted(d for d in os.listdir(root) if is_repo(os.path.join(root, d)))
        print(f"\n== repos in this folder (not members until confirmed): {', '.join(names)}")
        repos += [os.path.join(root, d) for d in names]

    if not repos:
        print("no git repository found", file=sys.stderr)
        return 1
    for repo in repos:
        report_repo(repo, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
