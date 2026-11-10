#!/usr/bin/env python3
"""Check the GitHub Actions files in this repo agree with each other.

1. Every `uses: owner/repo@ref` pin names one ref per action, across the
   workflows, the workflow templates and the standards that quote them, so a
   bump can't land in some copies and miss the rest (r1.f21).
2. A workflow file, whether in .github/workflows or a template, that runs on
   pull_request also runs on merge_group, so turning a merge queue on later
   can't stall on a required check that never reports (standards/git.md
   "Hot files").

This file is this repo's alone; the rest of agents/lib/ is shared with the
Agerpoint bok.
"""

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# specs/reviews quotes old pins on purpose, as findings.
SCAN_DIRS = (".github", "plugins", "agents", "specs")
SKIP_DIRS = {".git", "node_modules", "build", "reviews"}
SUFFIXES = {".yml", ".yaml", ".md"}
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([\w.-]+/[\w.-]+)(?:/[^@\s]*)?@([^\s#]+)")


def scan_files():
    for top in SCAN_DIRS:
        for root, dirs, files in os.walk(REPO / top):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if Path(name).suffix in SUFFIXES:
                    yield Path(root) / name


def check_pins(errors):
    pins = defaultdict(lambda: defaultdict(list))
    for path in scan_files():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            match = USES.match(line)
            if match:
                action, ref = match.groups()
                pins[action][ref].append(f"{path.relative_to(REPO)}:{number}")
    for action, refs in sorted(pins.items()):
        if len(refs) > 1:
            found = "; ".join(f"@{ref} at {', '.join(where)}" for ref, where in sorted(refs.items()))
            errors.append(f"{action} is pinned to more than one ref: {found}")
    return len(pins)


def check_merge_group(errors):
    for path in scan_files():
        if path.suffix not in {".yml", ".yaml"}:
            continue
        text = path.read_text()
        has = lambda trigger: re.search(rf"^\s+{trigger}:", text, re.M)
        # A workflow, not a steps snippet: it has a top-level `on:`.
        if re.search(r"^on:", text, re.M) and has("pull_request") and not has("merge_group"):
            errors.append(f"{path.relative_to(REPO)} runs on pull_request but not merge_group")


def main():
    errors = []
    count = check_pins(errors)
    check_merge_group(errors)
    for err in errors:
        print(f"FAIL: {err}", file=sys.stderr)
    if errors:
        return 1
    print(f"actions-check: {count} actions, one pin each; workflows run on merge_group")
    return 0


if __name__ == "__main__":
    sys.exit(main())
