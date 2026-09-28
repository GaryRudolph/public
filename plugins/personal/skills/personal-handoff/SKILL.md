---
name: personal-handoff
description: >-
  Write Gary's handoff and plan files with the right name, place, and
  contents: session handoffs and saved agent plans in
  .scratch/{handoff|plan}-{topic}-{word}.md, and milestone handoffs in
  specs/handoffs/handoff-m{N+1}-{topic}.md. Use when asked to "handoff",
  "write a handoff", "save the plan", or "write the plan to a file", when
  plan mode produces a plan, or when moving from milestone m{N} to m{N+1}.
---

# personal-handoff

Three kinds of file, one naming shape. Run
[`scripts/handoff-facts.sh`](scripts/handoff-facts.sh) first. It prints the
repo root, branch, working-tree changes, recent commits, existing handoff
and plan files, whether `.scratch/` is ignored, and a random `{word}`. Use
those facts; decide the topic and the contents yourself.

## Which file

| Request | File | Tracked in git |
| --- | --- | --- |
| "handoff", "write a handoff" | `.scratch/handoff-{topic}-{word}.md` | No |
| A plan from plan mode, or "write the plan to a file" | `.scratch/plan-{topic}-{word}.md` | No |
| Moving from `m{N}` to `m{N+1}` on a project with `specs/` | `{project-root}/specs/handoffs/handoff-m{N+1}-{topic}.md` | Yes |

## Naming

- `{topic}` is a short kebab-case name you derive from the work, such as
  `auth-api` or `pipeline-refactor`.
- `{word}` is a single random kebab-case word, such as `meadow`, `harbor`,
  or `quartz`. It keeps history across same-topic re-runs without a
  timestamp. The script suggests one that isn't taken.
- An adjective-noun pair (`eager-fox`) or a short hex hash (`b9d4e0d3`) is
  fine when the producing tool already emits one.
- Reuse an existing `{word}` only when you mean to overwrite that file.

Examples: `handoff-auth-api-meadow.md`, `plan-pipeline-refactor-harbor.md`,
`specs/handoffs/handoff-m3-search-engine.md`.

## Before writing to `.scratch/`

If `.scratch/` doesn't exist, create it. If the script reports it isn't
ignored, add `.scratch/` to `.gitignore` first. Never commit `.scratch/`
files.

## Contents

**Session handoff** (`.scratch/handoff-…`). Keep it short and actionable:

- What was done
- What's pending
- Key decisions made
- Gotchas for the next session

**Saved plan** (`.scratch/plan-…`). The plan as produced. If it becomes
durable, promote it to a spec in `specs/` or to a milestone handoff.

**Milestone handoff** (`specs/handoffs/…`). Write it before starting
`m{N+1}`:

- **Where we are**: what landed in `m{N}` that the next milestone depends
  on, and what was left partly done or skipped
- **What `m{N+1}` needs to deliver**: concrete deliverables from the spec
- **Key decisions already made**, so the next session doesn't re-debate them
- **Suggested plan**: a short ordered task list to start from
- **Gotchas**: traps, known bugs, unwired dependencies, platform quirks
- **Files to reference**: specific paths the next agent should read first

The canonical rules are in
[`../personal-standards/standards/documentation.md`](../personal-standards/standards/documentation.md)
under "Implementation Milestones" and "Handoffs between milestones".
