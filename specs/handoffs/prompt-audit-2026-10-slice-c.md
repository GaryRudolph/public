# Prompt audit, slice C: personal-standards `standards/` (except plan-execution.md)

## Step 0 assumptions

- **Scope:** every `.md` under `plugins/personal/skills/personal-standards/standards/` except `plan-execution.md`: 35 files, 7,124 lines. Read-only. For verification only, I also read `core.md`, the personal-standards `SKILL.md`, `personal-secrets/SKILL.md`, `personal-handoff/SKILL.md` (naming table), the secrets and release templates, and `plugins/personal/scripts/session-doctor.py`. I didn't read `templates/claude-settings.json`; its `attribution` content comes from the brief. Nothing outside the repo was probed.
- **Target model:** Claude Opus 5.5 (named in the request). These files are loaded on demand by path, so they are audited as agent configuration and reference files.
- **Provenance:** checked with `git blame` (50 commits; most of these lines arrived in `21d557d` 2026-06-05, `259628f` 2026-09-27, `bf5da80` 2026-10-06 and `fc9c23d` 2026-10-01).
- **Not applicable here:** Group 3 (tool descriptions) and Group 4 (request config). The slice has no tool definitions and no request-building code.

## Summary

The highest-impact findings are drift between the on-demand standards and the always-loaded `core.md`:

1. **documentation.md has a stale handoff rule.** It names the general handoff file `.scratch/handoff-{topic}.md` and calls a runner session "the one exception" that writes to `specs/handoffs/`. The newer `core.md` (blamed 2026-10-11) and the `personal-handoff` skill use `handoff-{topic}-{word}.md` and add a second exception: every `personal-plan-orchestrate` run, on any machine. `git.md` "Merging" omits orchestrate runs from the cleanup rule.
2. **Two cross-file conflicts I can't resolve without the user.**
   - `secrets/repository.md` orders key rotation `rotate → set-keys → build`. The newer `personal-secrets` skill orders it `rotate → build → verify → commit → set-keys` (after a go-ahead).
   - `python/testing.md` says to number tests when order matters. `testing.md` says never to rely on execution order.
3. **Rules buried in long files.** 24 files run past 100 lines. Only `swift/state-observation.md` opens with a real summary (its TL;DR). Agent-relevant rules sit below line 100: changelog fragments (documentation.md:136), PR trailer placement and API merges (git.md:149-156), and most API house conventions (architecture.md:105-350).

Group 1 (dated prompt text) is nearly clean. The agent-facing sections (`git.md` "AI Agent Behavior", the documentation.md handoff rules) have no shouting, no update suppressors, no anti-formatting rules and no think-step scaffolds. Their prohibitions carry reasons and target a real, current failure: the harness default "If on the default branch, branch first" conflicts with Gary's rules. Keep-list items 3 and 5 apply.

The AI attribution rules in git.md are internally consistent with each other, with `core.md`, and with the baseline `attribution` template ({commit, pr} = `Assisted-by: Claude Code`).

**Counts**

| Group | High | Medium | Low |
|---|---|---|---|
| 1: dated prompt text | 0 | 0 | 3 |
| 2: brittle config | 4 (2 rewrite, 2 flag) | 4 | 13 |
| Progressive disclosure (TOC) | 0 | 4 | (table) |
| 3: tool descriptions | not applicable | | |
| 4: request config | not applicable | | |

---

## (1) Inventory (line counts from `wc -l`)

| File | Lines | | File | Lines |
|---|---|---|---|---|
| README.md | 59 | | python/architecture.md | 688 |
| code-style.md | 49 | | python/code-style.md | 177 |
| architecture.md | 393 | | python/documentation.md | 90 |
| platform-parity.md | 49 | | python/security.md | 226 |
| testing.md | 80 | | python/testing.md | 210 |
| documentation.md | 163 | | swift/architecture.md | 230 |
| git.md | 179 | | swift/code-style.md | 223 |
| versioning.md | 515 | | swift/documentation.md | 93 |
| makefile.md | 168 | | swift/security.md | 90 |
| security.md | 164 | | swift/state-observation.md | 131 |
| gcp.md | 107 | | swift/testing.md | 106 |
| secrets/README.md | 79 | | kotlin/architecture.md | 63 |
| secrets/makefile.md | 140 | | kotlin/code-style.md | 146 |
| secrets/repository.md | 479 | | kotlin/documentation.md | 74 |
| go/architecture.md | 613 | | kotlin/security.md | 114 |
| go/code-style.md | 247 | | kotlin/testing.md | 102 |
| go/documentation.md | 92 | | | |
| go/security.md | 500 | | | |
| go/testing.md | 285 | | | |

**Verification sweep**

- Every relative link and `#anchor` in the slice resolves. I checked them with a script using GitHub-style heading slugs; the one hit was a false positive on inline code in go/code-style.md:80.
- Named repo paths exist:
  - `plugins/personal/skills/personal-makefile/`
  - `personal-release/templates/{bump_version.py, release.yml, changelog.py}`
  - `personal-secrets/templates/secrets-repo/*` and `tests/test-kit.sh`
- Every secrets Makefile target named in `secrets/makefile.md` is defined in the kit's Makefile.
- `release.yml` and `bump_version.py` do refuse a level that would leave the release line (versioning.md:498).
- `session-doctor.py` matches makefile.md:150-152 (doctor, else task, else triage, trusted owners only).
- No symlinks sit on any path checked.

---

## (2) Findings (ordered by confidence)

| # | Location | Evidence | Pattern | Why obsolete | Confidence | Action |
|---|---|---|---|---|---|---|
| 1 | documentation.md:109 | "supersedes the general-purpose `.scratch/handoff-{topic}.md` convention … The one exception is a runner session" | G2 contradicting instruction files / stale fact | core.md:66 (blame 2026-10-11) and personal-handoff/SKILL.md:25 name it `handoff-{topic}-{word}.md`. core.md:51,66-67 and personal-handoff/SKILL.md:29 add a second exception: any `personal-plan-orchestrate` run, on any machine. This line (2026-10-01) is older, and "the one exception" is now false. | High | rewrite (H1) |
| 2 | documentation.md:49 | "A runner session's plan, session handoff, and asked-for drafts or research → `{project-root}/specs/handoffs/` … because `.scratch/` dies with the container" | G2 contradicting instruction files | Same conflict: the specs-folder list leaves out orchestrate runs that core.md:51 and personal-handoff/SKILL.md:29 send to `specs/handoffs/` | High | rewrite (H2) |
| 3 | secrets/repository.md:455 vs personal-secrets/SKILL.md:111-113 | "**Rotate consumer key:** `make rotate` → `set-keys` → `build` → commit" vs "`make rotate REPO= CONTEXT=`, `make build`, `make verify`, commit, then with Gary's go-ahead `CONFIRM_SET_KEYS=1 make set-keys`" | G2 contradicting instruction files | The two files give opposite orders for the same procedure. Blame orders them: repository.md:455 is from 2026-06-08 and SKILL.md:111 from 2026-09-27, so the skill is newer. The newer text adds a command (`make verify`) and a gated push, so per the Group 2 row this is a flag, not a rewrite. User decision: align repository.md to the skill's order, or replace the line with a pointer to the skill. | High | flag |
| 4 | python/testing.md:189 vs testing.md:61 | "Use numbered test names when execution order matters." vs "**Test interdependence** — each test sets up its own data; no execution order reliance" | G2 contradicting instruction files | The two rules are opposite and neither gives a reason. Both lines come from the same commit (`21d557d` 2026-06-05), so history can't say which is current. User decision: drop the python line, or scope it explicitly as an override for the HTTP integration suite. | High | flag |
| 5 | git.md:153 | "Before merging, remove the runner's files from `specs/handoffs/`" | G2 contradicting instruction files (omission) | core.md:51 (2026-10-11, newer than this 2026-10-01 line) says an orchestrate run "does the same on any machine". A workstation orchestrate run's plan and handoff therefore also need removing before merge, and this rule skips them. | Medium | rewrite (H3) |
| 6 | python/documentation.md:27 | `def calculate_total(items: list[Item], tax_rate: float, discount_code: str = None) -> float:` | G1c example over-indexing / G2 conflict | python/code-style.md:36-40 requires `X \| None` and full annotations, and its mypy `strict = true` rejects implicit Optional. Examples are the strongest signal in a prompt, so this one teaches the forbidden form. | Medium | rewrite (H4) |
| 7 | python/architecture.md:149 | "[the PostgreSQL 19 docs](…) (in beta) say to emulate them with triggers" | G2 time-sensitive content | A release-stage status has no verification date and rots on its own. PostgreSQL ships a major release every autumn, so the claim is likely already stale on 2026-10-19. | Medium | rewrite (H5) |
| 8 | go/code-style.md:5, go/architecture.md:5 | "Target **Go 1.27** for new projects, the current stable release; re-check it per [Starting New Projects]" | G2 volatile specifics (version pin with no date), duplicated in two files | "The current stable release" is a claim that expires. architecture.md:13-19 and core.md:63 tell the agent to look versions up, not trust a pinned number. Adding the blame date (2026-10-06) keeps the information and stops it posing as current. | Medium | rewrite (H6, two hunks) |
| 9 | git.md, documentation.md, architecture.md, versioning.md (first 15 lines) | No table of contents. Agent-relevant rules sit at git.md:149-156, documentation.md:136-146, architecture.md:105-350 and versioning.md:473-515 | Progressive disclosure (Anthropic skill guidance: reference files over 100 lines open with a contents list) | A partial read (head, offset or limit, or an agent that stops at what looks like the end) misses these rules. Section (4) has the full table. | Medium | add (H7-H10) |
| 10 | secrets/repository.md:339, :380 | "decrypted **only** by maintainer-local targets (`make build`, `make set-keys`)"; "targets that read source secrets (`src-decrypt`, `src-encrypt`, `build`, `set-keys`, `mint`, `rotate`)" | G2 stale fact (incomplete list) | `keys.sh` (mint, rotate, retire) and `verify.sh` also decrypt the registry (`registry_plain` in lib.sh:84). The rule ("only maintainer-local") still holds; only the examples are incomplete. | Low | flag |
| 11 | secrets/repository.md:97,106,114; versioning.md:107; architecture.md:41 | `actions/create-github-app-token@v1`, `actions/checkout@v4`, `nhedger/setup-sops@v2`, `lolay/triage-action@v0.5` | G2 version pins without a date | They match the kit's `templates/consumer/secrets-steps.yml`, so the repo doesn't contradict them. Re-check at the next touch. | Low | flag |
| 12 | go/code-style.md:178-179; go/architecture.md:15,156; go/security.md:172,415; security.md:35; versioning.md:351; kotlin/code-style.md:141 | `strings.CutLast` (1.27), `uuid` "standard library since Go 1.27", `encoding/json/v2` (Go 1.27), "Go 1.25's `http.CrossOriginProtection`", "pnpm 10", detekt `version "1.23+"` | G2 volatile API claims, no date | I can't verify these from the repo. They are the facts most likely to rot when Go or the tools ship. | Low | flag |
| 13 | git.md:65, :156; git.md:126 | "`gh pr view` and `gh pr list` go through GraphQL, which Claude Code's cloud proxy refuses"; "Merge queues need GitHub Enterprise Cloud for private org repos" | G2 environment and vendor claims, no date | Harness and vendor behavior that changes without notice. Keep the rule and add a checked-on date. | Low | flag |
| 14 | architecture.md:33,41; python/architecture.md:605; swift/code-style.md:159; python/security.md:38 | "Triage releases before `recommended_from` ignore it"; "FastAPI before 0.122 answered … 403"; "Before Foundation shipped SF-0021's lenient parser…"; "passlib … last release was 2020-10" | G1d migration-relative phrasing / G2 history | Each line tells a reader with an older dependency why the rule exists, which is context (keep-list item 1). Flag only. Drop each once its floor version is above the cutoff. | Low | flag |
| 15 | git.md:12, :73 (end), :78, :80 | The task-branch carve-out is stated four times in slightly different words. :79 adds "Do not spin one up proactively" right after "create a worktree only on explicit request" | G1c padding / repetition | The four statements agree, and each is a prohibition with a reason against a real harness default (keep-list items 5 and 8). Merging them is a refactor, not a fix. | Low | flag |
| 16 | README.md:53-59; documentation.md:150-154 | "**Simplicity** — prefer simple solutions…", "**Maintainability** — think about future developers"; "Clear and easy to understand?" | G1c padding: generic virtues | These restate defaults. They mostly serve as human orientation and do little harm. | Low | flag |
| 17 | git.md:22-30 | Example branch `feat/all-your-base` | G1c example vs rule | git.md:8 and :73 name `feature/`. The worktree slug rule does accept `feat/`, and the lines come from the same commit, so there is no clear current side. | Low | flag |
| 18 | go/code-style.md:159 | "Patterns below are **deprecated** on Go 1.22+" | G2 internal inconsistency | The table rows go up to Go 1.24-1.27. | Low | flag |
| 19 | code-style.md:22 | "Use the language community's standard indentation (typically 4 spaces); no tabs" | G2 override (not a conflict) | go/code-style.md:9 (gofmt tabs) and makefile.md:25 (Make requires tabs) explain their own overrides, so this is left alone. Optionally qualify "no tabs". | Low | flag |
| 20 | python/security.md:215, :223 | `bandit -r src/ -c pyproject.toml`; `pip install --require-hashes -r requirements.txt` | G2 stale against the sibling layout | python/architecture.md:34-60 uses an `app/` layout, and python/code-style.md:164-166 standardizes on uv + pyproject. | Low | flag |
| 21 | versioning.md:512 | `BUILD_CODE: ${{ vars.PLAY_PRODUCTION_VERSION_CODE + 1 }}` | Outside the audit's patterns (correctness) | GitHub Actions expressions have no arithmetic operator, so this would not evaluate as written. An agent could copy it. Verify and compute in a shell step. | Low | flag |
| 22 | versioning.md:90-99 | `// scripts/build-code.mjs` … `export function buildCode(): number` | Outside the audit's patterns (correctness) | A TypeScript return-type annotation in a `.mjs` file is a syntax error. | Low | flag |
| 23 | kotlin/security.md:5-19 (also security.md:99, README.md:44); kotlin/documentation.md:74 | `EncryptedSharedPreferences`; `./gradlew dokkaHtml` | Volatile vendor facts (external, unverified) | From memory, not the repo: Jetpack Security Crypto deprecated EncryptedSharedPreferences in 2025, and Dokka 2 replaced `dokkaHtml` with `dokkaGenerate`. Verify before acting. | Low | flag |

**AI attribution consistency (requested check)**

There is no inconsistency to fix:

- git.md:77 attributes trailer emission to `attribution.commit` and `attribution.pr`, which matches the template ({commit, pr} = `Assisted-by: Claude Code`).
- git.md:97 and :149 put trailers in the final paragraph.
- git.md:146 ends the PR body template with the same trailer.
- git.md:149 deliberately overrides the harness's placement of the session link (link above the trailer paragraph). This agrees with core.md:39.
- git.md:77 ("Keep `Claude-Session:` … on branch commits") matches what the harness emits on commits (`Assisted-by` followed by `Claude-Session:` in one trailer block). "`Assisted-by:` stays the last trailer" applies only to the squash message on `main`.
- git.md:77 "accept" the GitHub-added `Co-authored-by` and :156 "with no agent co-author line" on API merges cover different merge paths, and both match core.md:39.

---

## (3) Proposed diff (high and medium only, one finding per hunk; nothing applied)

### H1: finding 1 (documentation.md:109)

```diff
--- a/plugins/personal/skills/personal-standards/standards/documentation.md
+++ b/plugins/personal/skills/personal-standards/standards/documentation.md
@@ -107,5 +107,5 @@
 Handoff files go in version control; they are part of the project's working record.
 
-This rule supersedes the general-purpose `.scratch/handoff-{topic}.md` convention only for **milestone transitions on a project that has a `specs/` folder**. Ad-hoc handoffs (session wrap-ups, research, one-off spikes) still go to `.scratch/`. The one exception is a runner session, where `.scratch/` dies with the container: its plan, session handoff, and asked-for drafts go to `specs/handoffs/` under their usual names and are removed or promoted before the branch merges (see [git.md](git.md) "AI Agent Behavior").
+This rule supersedes the general-purpose `.scratch/handoff-{topic}-{word}.md` convention only for **milestone transitions on a project that has a `specs/` folder**. Ad-hoc handoffs (session wrap-ups, research, one-off spikes) still go to `.scratch/`. Two cases use `specs/handoffs/` instead, under their usual names, removed or promoted before the branch merges: a runner session, where `.scratch/` dies with the container (its plan, session handoff, and asked-for drafts), and any `personal-plan-orchestrate` run on any machine (its plan and session handoff). See [git.md](git.md) "AI Agent Behavior" and the `personal-handoff` skill.
 
 ## Architecture Decision Records
```

### H2: finding 2 (documentation.md:49)

```diff
--- a/plugins/personal/skills/personal-standards/standards/documentation.md
+++ b/plugins/personal/skills/personal-standards/standards/documentation.md
@@ -48,3 +48,3 @@
 - Throwaway drafts, research, spikes → `.scratch/` (gitignored)
-- A runner session's plan, session handoff, and asked-for drafts or research → `{project-root}/specs/handoffs/` under their usual names, removed or promoted before the branch merges, because `.scratch/` dies with the container (see [git.md](git.md) "AI Agent Behavior")
+- A runner session's plan, session handoff, and asked-for drafts or research, and the plan and session handoff of any `personal-plan-orchestrate` run on any machine → `{project-root}/specs/handoffs/` under their usual names, removed or promoted before the branch merges (a runner's `.scratch/` dies with the container; an orchestrate run commits and pushes them after every wave). See [git.md](git.md) "AI Agent Behavior"
 
```

### H3: finding 5 (git.md:153)

```diff
--- a/plugins/personal/skills/personal-standards/standards/git.md
+++ b/plugins/personal/skills/personal-standards/standards/git.md
@@ -151,3 +151,3 @@
 ### Merging
 
-- Before merging, remove the runner's files from `specs/handoffs/` (`plan-*.md`, the session `handoff-{topic}-{word}.md`, drafts) in the last commit on the branch, promoting anything durable to `specs/` or a milestone handoff first. Milestone handoffs (`handoff-m{N}-…`) stay. A forgotten removal lands plain markdown on `main`; one `git rm` fixes it
+- Before merging, remove the files a runner or a `personal-plan-orchestrate` run kept in `specs/handoffs/` (`plan-*.md`, the session `handoff-{topic}-{word}.md`, drafts) in the last commit on the branch, promoting anything durable to `specs/` or a milestone handoff first. Milestone handoffs (`handoff-m{N}-…`) stay. A forgotten removal lands plain markdown on `main`; one `git rm` fixes it
```

### H4: finding 6 (python/documentation.md:27)

```diff
--- a/plugins/personal/skills/personal-standards/standards/python/documentation.md
+++ b/plugins/personal/skills/personal-standards/standards/python/documentation.md
@@ -26,3 +26,3 @@
 ```python
-def calculate_total(items: list[Item], tax_rate: float, discount_code: str = None) -> float:
+def calculate_total(items: list[Item], tax_rate: float, discount_code: str | None = None) -> float:
     """Calculate the total price including tax and discount.
```

### H5: finding 7 (python/architecture.md:149)

Before applying, confirm that the PG19 page still says to emulate temporal tables with triggers.

```diff
--- a/plugins/personal/skills/personal-standards/standards/python/architecture.md
+++ b/plugins/personal/skills/personal-standards/standards/python/architecture.md
@@ -148,3 +148,3 @@
 - **Snapshot keys** are snake_case column names, so the lowerCamel response model reads them with `validate_by_name=True`
-- **No native option** — PostgreSQL has no system-versioned tables; [the PostgreSQL 19 docs](https://www.postgresql.org/docs/19/ddl-temporal-tables.html) (in beta) say to emulate them with triggers
+- **No native option** — PostgreSQL has no system-versioned tables; [the PostgreSQL 19 docs](https://www.postgresql.org/docs/19/ddl-temporal-tables.html) say to emulate them with triggers
 
```

### H6: finding 8 (go/code-style.md:5 and go/architecture.md:5)

```diff
--- a/plugins/personal/skills/personal-standards/standards/go/code-style.md
+++ b/plugins/personal/skills/personal-standards/standards/go/code-style.md
@@ -3,3 +3,3 @@
 Follows [code-style.md](../code-style.md), [Effective Go](https://go.dev/doc/effective_go), [Go Code Review Comments](https://go.dev/wiki/CodeReviewComments), and the [Google Go Style Guide](https://google.github.io/styleguide/go/).
 
-Target **Go 1.27** for new projects, the current stable release; re-check it per [Starting New Projects](../architecture.md#starting-new-projects). Run `go fix ./...` after upgrading to mechanically adopt modern idioms.
+Target the latest stable Go for new projects (**Go 1.27** as of 2026-10-06); look it up per [Starting New Projects](../architecture.md#starting-new-projects) rather than trusting this line. Run `go fix ./...` after upgrading to mechanically adopt modern idioms.
--- a/plugins/personal/skills/personal-standards/standards/go/architecture.md
+++ b/plugins/personal/skills/personal-standards/standards/go/architecture.md
@@ -3,5 +3,5 @@
 Follows [architecture.md](../architecture.md).
 
-Target **Go 1.27** for new projects, the current stable release; re-check it per [Starting New Projects](../architecture.md#starting-new-projects).
+Target the latest stable Go for new projects (**Go 1.27** as of 2026-10-06); look it up per [Starting New Projects](../architecture.md#starting-new-projects) rather than trusting this line.
 
 ## Technology Stack
```

### H7: finding 9 (git.md contents)

```diff
--- a/plugins/personal/skills/personal-standards/standards/git.md
+++ b/plugins/personal/skills/personal-standards/standards/git.md
@@ -1,3 +1,12 @@
 # Git Workflow Standards
 
+Contents:
+
+- [Branch Strategy](#branch-strategy) and [Worktrees](#worktrees): branch and worktree naming
+- [Versioning](#versioning): headlines; the full standard is versioning.md
+- [AI Agent Behavior](#ai-agent-behavior): task vs shared branches, when to commit and push, runners, AI attribution trailers
+- [Commit Messages](#commit-messages): subject format; trailers as the last paragraph
+- [Pull Requests](#pull-requests): hot files, PR body (session link above the `Assisted-by:` trailer paragraph), squash and API merges, `specs/handoffs/` cleanup
+- [.gitignore Essentials](#gitignore-essentials)
+
 ## Branch Strategy
```

### H8: finding 9 (documentation.md contents)

```diff
--- a/plugins/personal/skills/personal-standards/standards/documentation.md
+++ b/plugins/personal/skills/personal-standards/standards/documentation.md
@@ -1,3 +1,12 @@
 # Documentation Standards
 
+Contents:
+
+- [What to Document](#what-to-document), [Code Comments](#code-comments) (TODO format), [Filename Case Conventions](#filename-case-conventions)
+- [Product and Technical Specs](#product-and-technical-specs): the `specs/` layout; [Runbooks](#runbooks)
+- [Implementation Milestones](#implementation-milestones): `m{N}` / `s{N}` naming, strikethrough when done, milestone handoffs
+- [Architecture Decision Records](#architecture-decision-records)
+- [Changelog](#changelog): entries ship as `.changelog/` fragments, not edits to `CHANGELOG.md`
+- [Documentation Review Checklist](#documentation-review-checklist)
+
 ## What to Document
```

### H9: finding 9 (architecture.md contents)

```diff
--- a/plugins/personal/skills/personal-standards/standards/architecture.md
+++ b/plugins/personal/skills/personal-standards/standards/architecture.md
@@ -1,3 +1,12 @@
 # Architecture Standards
 
+Contents:
+
+- [Core Principles](#core-principles), [Starting New Projects](#starting-new-projects), [Toolchain Floor and Pin](#toolchain-floor-and-pin)
+- [Layered Architecture](#layered-architecture), [Dependency Management](#dependency-management), [Error Handling Layers](#error-handling-layers)
+- [API Design](#api-design): the standards table, then house conventions (lowerCamel JSON, strict decoding, custom methods, `/health`, success envelope)
+- [Error Responses (RFC 9457)](#error-responses-rfc-9457), [Hidden Resources](#hidden-resources), [Custom Headers](#custom-headers), [Timestamps](#timestamps)
+- [Resource State](#resource-state) (wire enums, soft delete), [Protobuf](#protobuf), [Resource History](#resource-history), [Activity Log](#activity-log)
+- [Environment Domains](#environment-domains), [Tenant Admin and Ops](#tenant-admin-and-ops), [State Management](#state-management)
+
 ## Core Principles
```

### H10: finding 9 (versioning.md contents, kept under the regime summary that already opens the file)

```diff
--- a/plugins/personal/skills/personal-standards/standards/versioning.md
+++ b/plugins/personal/skills/personal-standards/standards/versioning.md
@@ -7,4 +7,6 @@
 | 1. Integer-major | URL API paths, wire/RPC formats, message schemas, file/serialization formats | `v1`, `v2`, `v3` (`vN.x` only for hotfixes) |
 | 2. SemVer 2.0 | Service binaries, published packages, libraries, distributed apps | `MAJOR.MINOR.PATCH` |
 
+Contents: [Design principles](#design-principles) · [Regime 1](#regime-1-integer-major-contracts) · [Regime 2](#regime-2-semver-20) (lazy bump, build string, build code) · [Version string grammars](#version-string-grammars) · [Per-platform surfaces](#per-platform-surfaces) · [Promote-to-release flow](#promote-to-release-flow) · [Hotfix flow](#hotfix-flow)
+
 ## Design principles
```

All anchors used in H7-H10 match headings that already exist; I checked them against the file headings with the same slug rule as the link check.

---

## (4) Contents and partial-read table (files over 100 lines)

"Map in the first 15 lines": **yes** means a summary or contents of the whole file. **Partial** means a purpose line or the key rule, but no section map. **No** means the file opens straight into its first section.

A caveat on the "first N lines" premise: Claude Code's Read tool returns up to 2,000 lines by default. The realistic risk is a partial read (offset or limit, `head`, or a sub-agent told to skim), not a hard cutoff. Under that risk, the "buried" column lists the rules a partial read would miss.

| File | Lines | Map in the first 15 lines? | Agent-relevant rules below line 100 (at risk) |
|---|---|---|---|
| python/architecture.md | 688 | No | Request id middleware (255), RFC 9457 error catalog (297), `ApiModel` lowerCamel base and strict `ApiRequest` (483), 201 + `Location` (653) |
| go/architecture.md | 613 | No | Router errors wrapper (101), custom-method routing (154), Firestore modeling and ledger uniqueness (317), resource history (372), error catalog (500) |
| versioning.md | 515 | Partial: the regime table states the key rule | Promote-to-release (473), hotfix flow (489), Play hotfix `versionCode` override (501). The `personal-release` skill also covers these. |
| go/security.md | 500 | No | Strict JSON v2 decode → 400/422/413 (170), security headers (329), rate limiting on the real client IP (363), request id (407), opaque 5xx `writeProblem` (436) |
| secrets/repository.md | 479 | Partial: status and goals; "Consumer side (start here)" at 59 | Rotation and offboarding (452; conflicts with the skill, finding 3), threat model (465). secrets/README.md:59 summarizes it. |
| architecture.md | 393 | No | House conventions (105-126), RFC 9457 (128), custom headers (198), timestamps (210), wire enums and soft delete (223), resource history (275), environment domains (317), tenant/ops (338) |
| go/testing.md | 285 | No | Coverage per package (205), fuzzing (231) |
| go/code-style.md | 247 | Partial: the Go target and `go fix` at line 5 | Modern Go replacements table (157), golangci-lint v2 config (195) |
| swift/architecture.md | 230 | No | DI rules: no `EnvironmentValues` in ViewModels or Managers (130), environment keys (186) |
| python/security.md | 226 | No | slowapi real-IP keying (127), pip-audit blocking policy (219) |
| swift/code-style.md | 223 | No | JSON Codable rules (152), DI (197), access control (204), force unwraps (208) |
| python/testing.md | 210 | No | Conformance suites (116); numbered-order rule (189; conflicts, finding 4) |
| git.md | 179 | No | PR body trailer placement (149; core.md:39 also has it), merging: squash, API message, `specs/handoffs/` cleanup (151-157), `.triage/` ignore (159-179). Agent rules at 43-80 are within reach. |
| python/code-style.md | 177 | No | Model serialization (104), Ruff, mypy strict, uv (135-177) |
| makefile.md | 168 | Partial: purpose and pointer to the skill (3-7) | Danger guards `CONFIRM_*` (101), doctor and triage tooling (139-156) |
| security.md | 164 | No | Deploy checklist (105); everything else sits above 100 |
| documentation.md | 163 | No | Milestone handoffs (96-109), **changelog fragments, not `CHANGELOG.md` edits (132-146)**. core.md doesn't carry this one; git.md:124 mentions it, also below 100. |
| kotlin/code-style.md | 146 | No | Tools: ktlint and detekt (135) |
| secrets/makefile.md | 140 | Partial: purpose and kit pointer (3-8) | GitHub secret stores per context (127) |
| swift/state-observation.md | 131 | **Yes**: TL;DR (7-12) | None that matter; the TL;DR carries the rules |
| kotlin/security.md | 114 | No | Android checklist (101); a restatement of the content above |
| gcp.md | 107 | Partial: purpose line (3) | None. The body ends at 73 and the rest is link references. |
| swift/testing.md | 106 | No | UI testing conventions (92); minor |
| kotlin/testing.md | 102 | No | Compose UI testing (85); minor |

Recommendation: H7-H10 cover the four files where a missed rule changes what an agent does (git, documentation, architecture, versioning). Give the long language files the same short contents block when they are next edited; I didn't write hunks for them because they're reference material for humans and agents alike, and the gain is smaller.
