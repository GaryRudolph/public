#!/usr/bin/env python3
"""Render the Cursor always-apply rule that carries the always-on core.

Cursor plugins can't run the SessionStart hook that injects core.md for
Claude, Codex, and Gemini, but they can ship rules. This writes core.md
behind rule frontmatter so the Cursor plugin carries the same core.
With --check it only reports whether the committed rule is current.
"""

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ORG = os.environ.get("ORG", "agerpoint")
CORE = REPO / f"plugins/{ORG}/skills/{ORG}-standards/core.md"
RULE = REPO / f"plugins/{ORG}/cursor/rules/{ORG}-core.mdc"
FRONTMATTER = (
    "---\n"
    f"description: {ORG} always-on core working agreements (generated from core.md; do not edit)\n"
    "alwaysApply: true\n"
    "---\n\n"
)


def render():
    return FRONTMATTER + CORE.read_text()


def main():
    expected = render()
    if "--check" in sys.argv[1:]:
        if not RULE.exists() or RULE.read_text() != expected:
            print(f"FAIL: {RULE.relative_to(REPO)} is stale; run make -C agents cursor-core-rule",
                  file=sys.stderr)
            return 1
        return 0
    RULE.write_text(expected)
    print(f"wrote {RULE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
