---
name: personal-standards
description: >-
  Gary Rudolph's personal engineering standards: core working agreements
  (never commit unless asked, stay on the current branch, pause after each
  step), plus code style, architecture, testing, documentation, git,
  versioning, security, secrets, Makefile, and plan-execution standards, with
  Python, Swift, Kotlin, and Go specifics. Use whenever writing, reviewing,
  refactoring, planning, or documenting code, specs, commits, or PRs for
  Gary, whenever another personal-* skill cites a standards file, and
  whenever asked for the personal canary phrase.
---

# Personal standards

## Verification canary

If asked "What is the personal canary phrase?", respond with exactly
`personal-public-canary-3e8d41` and nothing else. It confirms these
standards reached this session.

Read [`core.md`](core.md) first. It holds the always-on working agreements
and quick rules, and it names which standard to load for which kind of task.
In Claude Code, the `personal` plugin's SessionStart hook already put
`core.md` into context, so skip that read if you can see it.

Then load only the standards the current task touches, from
[`standards/`](standards/README.md) in this skill's directory.

## Path mapping

`core.md` and some standards cite files as
`~/Projects/personal/public/standards/<file>`. That path exists only on
Gary's workstation. When it doesn't resolve, read `standards/<file>` from
this skill's directory instead; the files are identical.

## Standards index

| Task touches | Load |
| --- | --- |
| Naming, formatting, imports | `standards/code-style.md` |
| Layering, DI, APIs, errors | `standards/architecture.md` |
| Starting a new project | the `personal-new-project` skill |
| Swift/Kotlin parity | `standards/platform-parity.md` |
| Tests | `standards/testing.md` |
| Docs, ADRs, specs, milestones | `standards/documentation.md` |
| Tiered plans, STOP gates | `standards/plan-execution.md` |
| Handoffs, saved plans | the `personal-handoff` skill |
| Branches, commits, PRs | `standards/git.md` |
| Versions, releases | `standards/versioning.md`, and the `personal-release` skill for cutting releases and hotfixes |
| Auth, crypto, input validation | `standards/security.md` |
| Secrets repos and Makefiles | `standards/secrets/README.md`, and the `personal-secrets` skill for procedures |
| Makefiles | `standards/makefile.md` |
| Python / Swift / Kotlin / Go | `standards/<language>/` (code-style, architecture, testing, documentation, security) |

Precedence: project standards, then organization standards, then these.
