#!/usr/bin/env python3
"""Ask package registries for the latest stable release of each component.

Facts only: prints what each registry reports, with the source URL, and
never judges whether a version is a good pick. The agent decides.

Usage:
    latest_versions.py npm:react pypi:fastapi go:github.com/gin-gonic/gin \\
        crates:serde gem:rails maven:org.springframework.boot:spring-boot \\
        github:astral-sh/uv brew:node eol:python eol:nodejs

Each result is one tab-separated line:
    spec  latest  released  source
`eol:<product>` prints one line per recent release cycle instead:
    spec  cycle=<c>  latest=<v>  lts=<bool>  eol=<date|bool>  source
`released` is the registry's date for that version where it gives one; for
Maven it is the artifact's last metadata update. Lookup failures print
`error: <reason>` in the latest column and set exit status 1, so a missing
answer is never mistaken for a version.
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from xml.etree import ElementTree

TIMEOUT_SECONDS = 15
EOL_CYCLES_SHOWN = 4
USER_AGENT = "personal-new-project (https://github.com/GaryRudolph/public)"


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def npm(name):
    url = f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}/latest"
    return fetch_json(url)["version"], "", url


def pypi(name):
    url = f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json"
    data = fetch_json(url)
    version = data["info"]["version"]
    files = data.get("releases", {}).get(version) or []
    released = files[0]["upload_time"][:10] if files else ""
    return version, released, url


def go(module):
    url = f"https://proxy.golang.org/{module.lower()}/@latest"
    data = fetch_json(url)
    return data["Version"], data.get("Time", "")[:10], url


def crates(name):
    url = f"https://crates.io/api/v1/crates/{urllib.parse.quote(name)}"
    crate = fetch_json(url)["crate"]
    return crate["max_stable_version"], crate.get("updated_at", "")[:10], url


def gem(name):
    url = f"https://rubygems.org/api/v1/versions/{urllib.parse.quote(name)}/latest.json"
    return fetch_json(url)["version"], "", url


PRERELEASE_MARKERS = re.compile(r"(?i)(snapshot|alpha|beta|preview|milestone|[.-]m\d|[.-]rc|[.-]cr\d|[.-]ea\b|-b\d)")


def version_key(version):
    return [int(part) if part.isdigit() else -1 for part in re.split(r"[.-]", version)]


def maven(coordinate):
    group, _, artifact = coordinate.partition(":")
    if not artifact:
        raise ValueError("expected maven:<group>:<artifact>")
    # The search index lags, and <release> in the metadata can be a
    # milestone, so read every version and drop pre-release qualifiers.
    url = f"https://repo1.maven.org/maven2/{group.replace('.', '/')}/{artifact}/maven-metadata.xml"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        root = ElementTree.parse(response).getroot()
    stable = [v.text for v in root.iter("version") if v.text and not PRERELEASE_MARKERS.search(v.text)]
    if not stable:
        raise LookupError("no stable version in maven-metadata.xml")
    updated = root.findtext("versioning/lastUpdated", "")
    released = f"{updated[:4]}-{updated[4:6]}-{updated[6:8]}" if len(updated) >= 8 else ""
    # Some artifacts publish flavors of one version (guava 33.7.1-jre and
    # -android); list them all rather than picking one.
    top = max(version_key(v) for v in stable)
    flavors = sorted(v for v in stable if version_key(v) == top)
    return ", ".join(flavors), released, url


def github(repo):
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        data = fetch_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise LookupError("no GitHub release published (the project may only tag; check its tags or site)") from exc
        raise
    return data["tag_name"], data.get("published_at", "")[:10], url


def brew(formula):
    url = f"https://formulae.brew.sh/api/formula/{urllib.parse.quote(formula)}.json"
    return fetch_json(url)["versions"]["stable"], "", url


LOOKUPS = {
    "npm": npm,
    "pypi": pypi,
    "go": go,
    "crates": crates,
    "gem": gem,
    "maven": maven,
    "github": github,
    "brew": brew,
}


def eol(spec, product):
    url = f"https://endoflife.date/api/{urllib.parse.quote(product)}.json"
    for cycle in fetch_json(url)[:EOL_CYCLES_SHOWN]:
        print("\t".join([
            spec,
            f"cycle={cycle.get('cycle')}",
            f"latest={cycle.get('latest')}",
            f"lts={cycle.get('lts')}",
            f"eol={cycle.get('eol')}",
            url,
        ]))


def main(specs):
    if not specs:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    failed = False
    for spec in specs:
        ecosystem, _, name = spec.partition(":")
        try:
            if ecosystem == "eol":
                eol(spec, name)
                continue
            if ecosystem not in LOOKUPS or not name:
                raise ValueError(f"unknown spec; use one of {', '.join(sorted(LOOKUPS))}, eol")
            version, released, url = LOOKUPS[ecosystem](name)
            print("\t".join([spec, version, released, url]))
        except Exception as exc:  # report every failure the same way, and keep going
            failed = True
            reason = getattr(exc, "reason", None) or exc
            print("\t".join([spec, f"error: {reason}", "", ""]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
