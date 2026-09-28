#!/usr/bin/env python3
"""Check that every plugin carries matching Claude, Codex, Cursor, and Gemini
manifests, and that the three marketplaces list the same plugins.

Vendor CLIs validate their own schema; this only catches drift between the
copies, which is the mistake that's easy to make and hard to notice.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLUGIN_MANIFESTS = (
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    "gemini-extension.json",
)


def load(path, errors):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        errors.append(f"{path.relative_to(REPO)}: {exc}")
        return None


def marketplace_sources(errors):
    claude = load(REPO / ".claude-plugin/marketplace.json", errors) or {}
    codex = load(REPO / ".agents/plugins/marketplace.json", errors) or {}
    cursor = load(REPO / ".cursor-plugin/marketplace.json", errors) or {}
    listed = {
        "claude": {p["name"]: p["source"].removeprefix("./") for p in claude.get("plugins", [])},
        "codex": {p["name"]: p["source"]["path"].removeprefix("./") for p in codex.get("plugins", [])},
        "cursor": {p["name"]: p["source"].removeprefix("./") for p in cursor.get("plugins", [])},
    }
    for vendor, entries in listed.items():
        if entries != listed["claude"]:
            errors.append(f"{vendor} marketplace lists {entries}, claude lists {listed['claude']}")
    return listed["claude"]


def main():
    errors = []
    for name, source in marketplace_sources(errors).items():
        root = REPO / source
        if root.name != name:
            errors.append(f"{source}: directory name differs from plugin name {name}")
        manifests = {m: load(root / m, errors) for m in PLUGIN_MANIFESTS}
        claude = manifests[".claude-plugin/plugin.json"] or {}
        for rel, data in manifests.items():
            if data is None:
                continue
            if data.get("name") != name:
                errors.append(f"{source}/{rel}: name {data.get('name')!r}, expected {name!r}")
            if data.get("description") != claude.get("description"):
                errors.append(f"{source}/{rel}: description differs from .claude-plugin/plugin.json")
        if (root / "bin").exists():
            errors.append(f"{source}: top-level bin/ makes claude.ai refuse the plugin")
    for err in errors:
        print(f"FAIL: {err}", file=sys.stderr)
    if errors:
        return 1
    print("manifests-check: all plugin manifests agree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
