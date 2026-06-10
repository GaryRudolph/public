---
name: personal-makefile
description: >
  Audit and align project Makefiles to the personal Makefile standard: target
  vocabulary, self-documenting help, workspace/polyrepo delegation, danger
  guards, and Makefile.md companions. Detects layout (single repo, workspace
  + repos.mk, submodule estate, plain folder of sibling repos). Dry-run first;
  apply repo-by-repo with explicit confirmation. Never bootstraps a missing
  workspace. Triggers: "align makefiles", "audit make targets", "fix makefile
  conventions", "standardize makefile", "makefile audit", "personal-makefile".
---

# Makefile Align Skill

Read `reference.md` (in this skill's directory) before starting — it holds the
`repos.mk` contract, per-stack recipe expectations, known-defect checks, rename
guidance, and template usage notes referenced throughout this workflow.

Load `~/Projects/personal/public/standards/makefile.md` for the canonical target
vocabulary and delegation rules.

## Workflow

### Step 1 — Detect layout

For each root the user names (or CWD if none), classify:

| Layout | Signals |
|--------|---------|
| **Workspace** | Root `Makefile` + `repos.mk`; child dirs are separate git repos |
| **Submodule estate** | Root `.gitmodules`; may or may not also have `repos.mk` |
| **Plain folder** | Sibling git repos under a non-git parent (e.g. `deskhound/`) — audit each repo independently; **never** bootstrap a workspace |
| **Single repo** | One git repo with its own Makefile |

Record layout in the audit report. A missing workspace when multiple repos exist
is an **observation only**, not a defect.

### Step 2 — Audit (dry-run, always)

**Facts in script, judgment in agent.** The inventory script gathers mechanical
facts only (targets, descriptions, sections, `.PHONY`, layout, presence checks)
— it emits no verdicts. You, the agent, apply the standard to those facts and
read recipe bodies directly where semantics matter.

Run the read-only inventory script:

```
bash <skill-dir>/scripts/audit.sh [<root> ...]
```

Then reason over the facts, **layout-aware** — the same fact means different
things depending on which Makefile it describes:

| Makefile role | What applies |
|---------------|--------------|
| **Workspace root** | Orchestration targets and fan-out semantics; leaf core verbs (`lint`, `format`, `test`) intentionally absent — never flag them |
| **Leaf repo root** | Full core verb set (no-op stubs where N/A), section order, danger guards, `Makefile.md` |
| **Domain helper** (e.g. `assets/Makefile`, `samples/Makefile` inside a repo) | Exempt from the core verb rule; only note self-doc gaps when substantial |
| **External / vendored checkout** | Out of scope; note and skip |

Checks to perform (against `standards/makefile.md` and `reference.md`):

- Missing / non-standard core targets and section order (per role above)
- Missing `.DEFAULT_GOAL := help`, `SHELL := bash`, self-documenting `help`
- Help awk character class vs the standard (`[a-zA-Z0-9_.-]+`)
- Missing `Makefile.md` when the Makefile is non-trivial
- `repos.mk` list variables vs directories present
- Known-defect recipe patterns — **read the actual recipe bodies** and reason
  about their semantics (see reference.md § Known defects); do not rely on
  pattern matching alone
- Template drift for shared recipes (`gh-runs-*`, workspace fan-out, `doctor`)
- Doc cross-references — README / CONTRIBUTING / AGENTS.md mentions of make
  targets that no longer exist or were renamed

Write the report to `.scratch/makefile-audit-{estate}-{word}.md` (same
`{topic}-{word}` shape as handoffs) in the workspace, or in the personal bok
when auditing external estates.

**In plan mode, dry-run-only requests, or when the user has not approved apply:
stop here.** Present the report; write nothing to audited repos.

### Step 3 — Repo-by-repo confirmation

Process one repo at a time that has findings. Group proposals as:

- **Rename** — legacy name → standard verb (reason per repo; ask when ambiguous)
- **Add** — missing standard target (no-op stub if N/A)
- **Restructure** — `##@` sections, help awk, `.PHONY`, confirm macro
- **Guard** — move remote-mutating targets under `##@ Danger` with `CONFIRM_*`
- **Docs** — create or update `Makefile.md`
- **Manifest** — `repos.mk` list consistency
- **Re-sync** — replace drifted shared recipe with current template body

Ask for confirmation per repo:

- **Approve** — apply all proposals for this repo
- **Approve with edits** — user tweaks the list; apply the amended set
- **Skip** — write nothing for this repo
- **Fail closed** — no response, timeout, dismiss, or ambiguous reply = skip

When a rename mapping is ambiguous (e.g. is legacy `verify` this repo's `ci` or
`lint`?), ask before proposing.

### Step 4 — Apply

For each approved repo:

1. Start from the matching template in `templates/` (workspace, leaf, or
   submodule fragment).
2. **Preserve existing recipe bodies** for stack-specific targets — re-home and
   re-document; never invent build commands.
3. Create or update `Makefile`, `Makefile.md`, `repos.mk`, and any scripts a
   target already depends on.
4. Do **not** add version markers or skill metadata comments to estate files.

### Step 5 — Verify

In each changed repo:

- `make help` renders without error
- `make -n <target>` parses for every changed target
- Optional: `checkmake` if installed

Report deviations from the plan.

## Safety invariants (always enforce)

1. **Audit-first** — step 2 runs before any write; dry-run is the default.
2. **Fail closed** — absent explicit per-repo approval, write nothing.
3. **No workspace bootstrap** — never create a workspace repo for a plain folder.
4. **No invented recipes** — preserve or stub; do not guess build commands.
5. **No estate markers** — no version comments or skill fingerprints in target repos.
6. **Standards precedence** — project/org Makefile conventions override personal
   standard when documented; note the override in the report.

## Files in this skill

| File | Purpose |
|------|---------|
| `SKILL.md` | This file — workflow and invariants |
| `reference.md` | Deep detail: repos.mk, stacks, known defects, rename guidance |
| `templates/` | Customizable skeletons for workspace and leaf Makefiles |
| `scripts/audit.sh` | Read-only target inventory and layout detection (JSON stdout; facts only, no verdicts) |
