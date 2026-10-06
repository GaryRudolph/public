#!/usr/bin/env python3
"""Check that the copies of the Claude Code tier routing agree: the Claude
Code row of plan-execution.md's model picker, the ROUTE table in
plan-segment.js, and the agent frontmatter; that reviewers are read-only;
and that the Claude manifest is named for the org and lists exactly the
agent files, the workflows folder and the gate hook. Skips when the org's
plugin has no orchestrate kit (ORG=agerpoint before it's ported).

Usage: orchestrate_check.py <plugin-root>
"""

import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
org = root.name
kit = root / f"skills/{org}-plan-orchestrate"
wf = kit / "claude-workflows/plan-segment.js"
if not wf.exists():
    print(f"orchestrate-check: no Claude kit in {kit}, skipping")
    sys.exit(0)
errors = []

row = next(l for l in (root / f"skills/{org}-standards/standards/plan-execution.md").read_text().splitlines()
           if l.startswith("| Claude Code |"))
cells = [c.strip() for c in row.strip("|").split("|")][1:5]
picked = {}
for tier, cell in zip(("xdeep", "deep", "exec", "fast"), cells):
    m = re.search(r"`/model (\w+)` \((\w+)\)", cell)
    picked[tier] = (m.group(1), None if m.group(2) == "none" else m.group(2))
alt = re.search(r"alt: `/model (\w+)` \((\w+)\)", cells[0])
if alt:
    picked["fable"] = (alt.group(1), alt.group(2))

src = wf.read_text()
route = {m.group(1): (m.group(2), m.group(3)) for m in
         re.finditer(r"^\s+(\w+): \{ model: '(\w+)'(?:, effort: '(\w+)')? \},?$", src, re.M)}
if route != picked:
    errors.append(f"plan-segment.js ROUTE {route} != picker {picked}")


def front(path):
    block = path.read_text().split("---")[1]
    return dict(l.split(": ", 1) for l in block.strip().splitlines())


agents = {p.stem: front(p) for p in sorted((kit / "claude-agents").glob("*.md"))}
want = {"plan-worker": ("inherit", None), "plan-worker-max": picked["xdeep"],
        "plan-reviewer": picked["deep"], "plan-reviewer-max": picked["xdeep"]}
for name, (model, effort) in want.items():
    a = agents.get(name)
    if not a:
        errors.append(f"missing agent {name}")
        continue
    if (a.get("model"), a.get("effort")) != (model, effort):
        errors.append(f"{name}: frontmatter {a.get('model')}/{a.get('effort')}, expected {model}/{effort}")
    if "reviewer" in name and {t.strip() for t in a.get("tools", "Edit").split(",")} - {"Read", "Grep", "Glob", "Bash"}:
        errors.append(f"{name}: tools must be read-only (Read, Grep, Glob, Bash)")
for n in (":plan-worker", ":plan-reviewer", "-max"):
    if n not in src:
        errors.append(f"plan-segment.js never builds an agentType with {n}")
extra = set(agents) - set(want)
if extra:
    errors.append(f"unexpected agent files {sorted(extra)}")

manifest = json.loads((root / ".claude-plugin/plugin.json").read_text())
if manifest.get("name") != org:
    errors.append(f"manifest name {manifest.get('name')} != plugin folder {org}; agentType namespaces would break")
if {Path(p).stem for p in manifest.get("agents", [])} != set(agents):
    errors.append(f"manifest agents {manifest.get('agents')} != files {sorted(agents)}")
if not (root / manifest.get("workflows", "missing")).joinpath("plan-segment.js").exists():
    errors.append("manifest workflows does not point at the folder with plan-segment.js")
hooks = manifest.get("hooks")
hooks = [hooks] if isinstance(hooks, str) else hooks or []
if not any("orchestrate_gate.py" in (root / h).read_text() for h in hooks if isinstance(h, str) and (root / h).exists()):
    errors.append("manifest hooks do not register orchestrate_gate.py")

for e in errors:
    print(f"FAIL: {e}", file=sys.stderr)
print("orchestrate-check: tier routing agrees" if not errors else "")
sys.exit(1 if errors else 0)
