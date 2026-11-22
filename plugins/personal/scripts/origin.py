#!/usr/bin/env python3
"""Parse a git remote URL: host class, owner, repo and a credential-masked form.

The one place the personal plugin's facts scripts learn what `origin` is, so
an SSH host alias (`git@github.com-work:o/r.git`), GitHub's ssh-over-443 host,
Claude Code's cloud git proxy and a plain https URL are read the same way by
every caller, and a token in a URL is never printed.

It parses. It runs nothing but `git remote get-url origin` (read()), and never
`ssh -G` or the network. Standard library only; runs on Python 3.9.

host_class:
  github   github.com, www.github.com
  ssh443   ssh.github.com (GitHub's ssh host on port 443, any port)
  alias    an ssh or scp-form host `github.com-<x>` with no dot in <x>
           (`github.com-evil.example` is `other`: aliases are dotless)
  proxy    http(s) to 127.0.0.1 or localhost with a path `/git/<owner>/<repo>`
  other    any other host, IP addresses included
  local    a path, `C:\\`, or file://
  none     no origin

is_github is true for github, ssh443, alias and proxy, when an owner and a
repo parsed. Gate GitHub-only behavior on it, never on `owner` alone:
`https://attacker.example/lolay/x.git` parses to owner `lolay`, class `other`.

Python:  origin.parse(url) -> Origin;  origin.read(repo_dir) -> Origin (never raises)
CLI:     python3 -I origin.py URL | --repo DIR   [--json]
         one tab-separated line: host_class host owner repo transport masked
         (`-` for an empty field); exit 0, or 2 on a usage error. The raw URL
         is never printed.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict

SCHEME_URL = re.compile(r"^(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?P<authority>[^/]*)(?P<path>/.*)?$", re.S)
HOSTPORT = re.compile(r"^(?P<host>\[[^\]]*\]|[^:]*)(?::(?P<port>[0-9]*))?$")
SCP_FORM = re.compile(r"^(?:[^@/:]+@)?(?P<host>\[[^\]]*\]|[^/:]+):(?P<path>.*)$", re.S)
WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]")
ALIAS_HOST = re.compile(r"^github\.com-[^.]+$")
CONTROL = re.compile(r"[\x00-\x1f\x7f]")
GITHUB_CLASSES = ("github", "ssh443", "alias", "proxy")


@dataclass(frozen=True)
class Origin:
    host_class: str = "none"
    host: str = ""
    owner: str = ""
    repo: str = ""
    transport: str = ""  # https, http, ssh, file, local, or "" (none, or a scheme this module doesn't name)
    masked: str = ""

    @property
    def is_github(self):
        return self.host_class in GITHUB_CLASSES and bool(self.owner) and bool(self.repo)


def mask(url):
    """The URL with credentials masked: all of a non-ssh scheme URL's userinfo
    (a token can sit in the user part), and the password of an ssh one.
    A URL with no `scheme://` is returned as is."""
    m = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*://)([^/]*)(.*)$", url, re.S)
    if m and "@" in m.group(2):
        scheme, authority, rest = m.groups()
        userinfo, _, hostport = authority.rpartition("@")
        if "ssh" in scheme.lower():
            user, colon, _ = userinfo.partition(":")
            userinfo = user + (":***" if colon else "")
        else:
            userinfo = "***"
        url = scheme + userinfo + "@" + hostport + rest
    return url


def _owner_repo(path):
    segments = [s for s in path.split("/") if s]
    if segments:
        segments[-1] = segments[-1].removesuffix(".git")
    return (segments[-2], segments[-1]) if len(segments) >= 2 and segments[-1] else ("", "")


def parse(url):
    """Classify a remote URL. Never raises. A URL holding a control character is
    `other` with no host, owner or repo (trust fails closed)."""
    url = (url or "").strip()
    if not url:
        return Origin()
    masked = CONTROL.sub("?", mask(url))
    if CONTROL.search(url):
        return Origin("other", masked=masked)
    if WINDOWS_PATH.match(url):
        return Origin("local", transport="local", masked=masked)
    m = SCHEME_URL.match(url)
    if m:
        scheme = m.group("scheme").lower()
        authority = m.group("authority").rpartition("@")[2]
        hp = HOSTPORT.match(authority)
        host = (hp.group("host") if hp else authority).lower()
        path = m.group("path") or ""
        if scheme == "file" or not host:
            return Origin("local", transport="file" if scheme == "file" else "local", masked=masked)
        is_ssh = "ssh" in scheme
        transport = "ssh" if is_ssh else scheme if scheme in ("http", "https") else ""
    else:
        m = SCP_FORM.match(url)
        if not m:
            return Origin("local", transport="local", masked=masked)
        host, path, is_ssh, transport, scheme = m.group("host").lower(), m.group("path"), True, "ssh", "scp"
    if host in ("github.com", "www.github.com"):
        host_class = "github"
    elif host == "ssh.github.com":
        host_class = "ssh443"
    elif is_ssh and ALIAS_HOST.match(host):
        host_class = "alias"
    elif scheme in ("http", "https") and host in ("127.0.0.1", "localhost") and path.startswith("/git/"):
        host_class = "proxy"
    else:
        host_class = "other"
    owner, repo = _owner_repo(path)
    return Origin(host_class, host, owner, repo, transport, masked)


def read(repo_dir="."):
    """The Origin of the repo at repo_dir, from `git remote get-url origin` (so a
    url.<base>.insteadOf rewrite applies). Class `none` when there is no origin
    or git fails; never raises."""
    try:
        r = subprocess.run(["git", "-C", str(repo_dir), "remote", "get-url", "origin"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return Origin()
    return parse(r.stdout.strip()) if r.returncode == 0 else Origin()


def _field(value):
    return CONTROL.sub("", value) or "-"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classify a git remote URL.")
    parser.add_argument("url", nargs="?", help="the remote URL")
    parser.add_argument("--repo", metavar="DIR", help="read origin from this repo instead of a URL")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead of a tab-separated line")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    if (args.url is None) == (args.repo is None):
        parser.print_usage(sys.stderr)
        return 2
    o = read(args.repo) if args.repo is not None else parse(args.url)
    if args.json:
        print(json.dumps({**asdict(o), "is_github": o.is_github}))
    else:
        print("\t".join(_field(v) for v in (o.host_class, o.host, o.owner, o.repo, o.transport, o.masked)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
