---
name: personal-allowlist-scout
description: >
  Scans every git repo in the currently open workspace, detects build tooling,
  classifies each discovered command by access/intent, and proposes the safe
  subset (Inspect + Build & test only) that is missing from the existing
  per-harness allowlists. Confirms repo by repo; writes only the harness files
  that are missing each approved command; never writes a denylist; never edits
  the global meta-source. Triggers: "propose agent allowlist", "what commands
  are safe to auto-run", "audit repo build commands", "which make targets
  should I allowlist", "add missing allowlist entries".
---

# Allowlist Scout Skill

Read `reference.md` (in this skill's directory) before starting — it is the
single source of truth for the classification taxonomy, stack-detection rules,
harness token formats, and prefix-matching caveats referenced throughout this
workflow.

## Global promotion routing

When a command is a global-promotion candidate, route it to the correct
meta-source based on which workspace the repo belongs to:

- **Agerpoint repos** (repos under `~/Projects/agerpoint/` or repos whose
  remote URL contains `agerpoint`) → `agents/allowlists/agerpoint.json` in
  the agerpoint bok. Emit the copy-paste bullet and note it goes to the
  agerpoint bok agent.
- **All other repos** → `agents/allowlists/personal.json` in the personal/public
  bok (`~/Projects/personal/public/agents/allowlists/personal.json`). Emit the
  copy-paste bullet and note it goes to the personal bok agent.

The skill **never edits either meta-source directly** — it only emits the
bullet list for a subsequent bok-agent session.

## Workflow

### Step 1 — Scan

Run `scan.py` against the workspace roots (arguments provided by the user, or
CWD if none):

```
python3 <skill-dir>/scripts/scan.py [<workspace-root> ...] [--max-depth N]
```

The script emits a JSON proposal on stdout and optionally a human-readable
summary under `.scratch/`. Parse the JSON output for the subsequent steps;
show the user the summary path so they can review it independently.

### Step 2 — Deep-eval any Unclassified commands

For each entry in `repos[*].unclassified`:

1. Read the command's actual definition using the `evidence` field (Makefile
   recipe body, `package.json` script value, or script file contents).
2. Reason about what the command *accesses or does* against the taxonomy in
   `reference.md` (§ 1 Access / Intent Classification).
3. Assign a real class:
   - **Inspect** or **Build & test** → move the command into the proposable
     pool for this repo (add it to the appropriate group below).
   - **Remote Write / Sensitive / Destructive / Long-running** → omit; record
     the class in the session notes.
   - Still genuinely indeterminate → remains **Unclassified**; omit from
     proposals; surface to the user as "needs manual classification" with the
     evidence.

### Step 3 — Repo-by-repo confirmation

Process one repo at a time. For each repo that has any proposable entries:

1. **Present** the groups:
   - **Group 1** — commands missing from every harness; propose adding to all
     four per-repo harness files.
   - **Group 2** — drift; for each command, show which harnesses already have
     it and which are missing it.
   - For each command suppressed by a broad existing prefix, note the
     suppression (e.g. `"suppressed in cursor_ide by broad prefix 'make'"`).

2. **Ask for confirmation** for this repo:
   - **Approve** — proceed with all proposals as listed.
   - **Approve with input** — user tweaks the list (remove commands, restrict
     to specific harnesses); apply the amended list.
   - **Skip** — write nothing for this repo.
   - **Fail closed**: no response, a timeout, a dismiss, or anything that is
     not an explicit "approve" or "approve with input" = skip and write
     nothing for this repo.

3. **On explicit approval**, call `render.py` in batch mode (stdin JSON) for
   the approved commands, writing only to the harness files that lack each
   entry:

   ```
   python3 <skill-dir>/scripts/render.py --stdin <<'EOF'
   {
     "repo": "<abs-path>",
     "gemini_policy_name": "project",
     "commands": [
       {"segment": "make test", "harnesses": ["cursor_ide", "claude"]},
       ...
     ]
   }
   EOF
   ```

4. Move to the next repo.

### Step 4 — Global-promotion candidates

After all repos, for each entry in `global_promotion_candidates` (commands
recurring across ≥ 2 repos and not fully covered globally):

Present the candidate and ask the user to choose one of:

- **Promote to global** — determine the correct meta-source using the routing
  rules in § Global promotion routing above, then emit a copy-paste bullet for
  the appropriate bok agent. The skill **never edits the meta-source itself**.
- **Add to per-repo allowlists instead** — call `render.py` (same stdin JSON
  flow as Step 3) to write the command into the per-repo files of the repos
  that surfaced it.
- **Skip** — do nothing.
- **Fail closed**: no response / timeout / dismiss = skip.

At the end, if any global-promotion bullets were collected, print them grouped
by destination meta-source:

```
## Commands to promote to the agerpoint global allowlist
(paste into an agerpoint bok-agent session)

- make test
- swift build

## Commands to promote to the personal global allowlist
(paste into a personal bok-agent session)

- pytest
```

## Safety invariants (always enforce)

1. **Allow-only**: never write a `deny` / `ask_user` / `confirmationRequired`
   entry to any harness file.
2. **No new metadata file**: the harness allowlist files themselves are the
   source of truth. Do not create any new file to track proposals.
3. **Fail closed**: absent an explicit approval, write nothing.
4. **Workspace-scoped**: operate only on the git repos reachable from the
   currently open workspace (argv targets or CWD). Never scan `~/Projects` or
   any other workspace unless it *is* the open workspace.
5. **Never-propose classes respected**: Remote Write, Sensitive, Destructive,
   Long-running, and Unclassified (after deep-eval) commands are omitted and
   never written — not even to a denylist.
6. **Drift-aware writes**: a confirmed command is added only to the harness
   files that are missing it, never blindly to all harnesses.
7. **No global meta-source edits**: global-promotion emits a copy-paste list
   only. The skill never writes to either `agerpoint.json` or `personal.json`.

## Files in this skill

| File | Purpose |
|---|---|
| `SKILL.md` | This file — workflow, invariants, and personal global-routing section |
| `reference.md` | Taxonomy, stack-detection rules, harness token formats, prefix caveats |
| `scripts/scan.py` | Core scan engine — detects repos, classifies commands, computes coverage |
| `scripts/render.py` | Apply layer — writes confirmed entries to harness files (merge-safe, allow-only) |
