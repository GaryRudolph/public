#!/usr/bin/env bash
# Build the phase 0 spike plugin `orch-spike` from plugins/personal, so org sync and Cowork can be tried on the
# new manifest fields (agents, workflows, hooks) without touching the `personal` plugin every synced surface gets.
# Re-run it after any change to the kit; it rebuilds orch-spike/ from scratch.
#
# Usage: build-spike-plugin.sh [name]     (default name: orch-spike; the suggested form is <letters-digits-hyphens>)
#
# What the copy keeps: the manifest (renamed, with the same agents, workflows and hooks fields), the four
# planning skills the kit cites (standards, plan-orchestrate, plan-model-tiers, plan-tag-tiers) under the new
# prefix, and a SessionStart hook that prints one marker line instead of the core standards (so a session with both
# plugins doesn't inject the standards twice, and the marker shows whether the synced copy's hook ran).
# The kit's namespace rule: the folder, the manifest name, args.plugin and the skill prefix all agree.
set -euo pipefail
name=${1:-orch-spike}
here=$(cd "$(dirname "$0")" && pwd)
src=$(cd "$here/../../../../plugins/personal" && pwd)
out=$here/$name
case "$name" in personal|*[!a-z0-9-]*|-*) echo "bad name: $name" >&2; exit 1;; esac

rm -rf "$out"
mkdir -p "$out/.claude-plugin" "$out/hooks" "$out/scripts" "$out/skills"
for s in standards plan-orchestrate plan-model-tiers plan-tag-tiers; do
  rsync -a --exclude __pycache__ --exclude '*.pyc' "$src/skills/personal-$s/" "$out/skills/$name-$s/"
done

python3 - "$name" "$src" "$out" <<'PY'
import json, re, sys
from pathlib import Path
name, src, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])

# Rename the skill prefix in every text file the copy carries.
pat = re.compile(r"personal-(standards|plan-orchestrate|plan-model-tiers|plan-tag-tiers)")
for p in out.rglob("*"):
    if p.is_file():
        try:
            t = p.read_text()
        except UnicodeDecodeError:
            continue
        n = pat.sub(rf"{name}-\1", t)
        if n != t:
            p.write_text(n)

m = json.loads((src / ".claude-plugin/plugin.json").read_text())
m["name"] = name
m["description"] = (f"Phase 0 spike copy of the personal plugin ({name}): the orchestrate kit's manifest fields "
                    "(agents, workflows, hooks) for checking org sync and Cowork. Not for daily use.")
m["agents"] = [a.replace("personal-plan-orchestrate", f"{name}-plan-orchestrate") for a in m["agents"]]
m["workflows"] = m["workflows"].replace("personal-plan-orchestrate", f"{name}-plan-orchestrate")
(out / ".claude-plugin/plugin.json").write_text(json.dumps(m, indent=2) + "\n")

hooks = (src / "hooks/claude-hooks.json").read_text().replace("personal-plan-orchestrate", f"{name}-plan-orchestrate")
(out / "hooks/claude-hooks.json").write_text(hooks)
(out / "hooks/hooks.json").write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [
    {"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}\"/scripts/session-start.sh"}]}]}}, indent=2) + "\n")
(out / "scripts/session-start.sh").write_text(
    "#!/usr/bin/env bash\n"
    f"# SessionStart hook of the {name} spike plugin: one marker line, so a session shows the synced hook ran.\n"
    f"echo \"{name} SessionStart hook ran (phase 0 spike plugin; not the personal standards).\"\n")
(out / "scripts/session-start.sh").chmod(0o755)
PY

# A marketplace file for the spike plugin, to copy into a private scratch repo's root (the only place Claude's
# surfaces look for it; see the route in .scratch/orchestrate-plan-orchestrate-native-kestrel-2-m1-s4-s6.md).
cat > "$here/.claude-plugin/marketplace.json" <<JSON
{
  "name": "$name-lab",
  "description": "Phase 0 spike marketplace for the orchestrate-native work. Holds one plugin, $name, pinned to a branch of GaryRudolph/public.",
  "owner": { "name": "Gary Rudolph" },
  "plugins": [
    {
      "name": "$name",
      "description": "Spike copy of the personal plugin with the orchestrate kit's manifest fields (agents, workflows, hooks).",
      "source": {
        "source": "git-subdir",
        "url": "https://github.com/GaryRudolph/public.git",
        "path": "specs/handoffs/orchestrate-native/spike-plugin/$name",
        "ref": "feature/orchestrate-native"
      }
    }
  ]
}
JSON
echo "built $out and $here/.claude-plugin/marketplace.json"
