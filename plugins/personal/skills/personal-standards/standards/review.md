# Review Guides

How an agent hands a change to a human reviewer. Agents write code faster than anyone can read it line by line, so the goal is the least human review that doesn't raise reverts or incidents: the reviewer studies what can hurt (contracts, data, auth, concurrency), checks what changes behavior (orchestration, error handling), and skims or skips the rest. The agent's job is to say which is which, show evidence, and draw what changed shape.

Contents:

- [Review tiers](#review-tiers): `[study]`, `[check]`, `[skim]`, `[skip]` per area; the PR's tier is the highest; blast radius
- [Time to understand](#time-to-understand): about 2 minutes for the visible part, on a phone
- [Three moments](#three-moments): plan, pre-PR, PR
- [Description layout](#description-layout): the PR description, mobile first, a collapsible block per tier
- [Evidence](#evidence): commands and results, "not run" when it wasn't
- [Diagrams](#diagrams): before from the base commit, after from head, only where structure changed
- [Plan-time preview](#plan-time-preview): when cheap, else at completion
- [Review surfaces](#review-surfaces): a repo's own before/after renderers, in `AGENTS.md`
- [The draft](#the-draft): `-review.md` on the branch, published to the description
- [Ownership](#ownership)

The `personal-review-guide` skill runs the procedure. This file says what good looks like.

## Review tiers

Each area of a change (a group of files, or one hunk that matters) gets one tag saying what the reviewer should do with it:

| Tag | Reviewer | Typical areas |
| --- | --- | --- |
| `[study]` | Reads every line and questions the design | Public contracts, schema, auth, concurrency, irreversible operations |
| `[check]` | Reads the named hunks and confirms them against the evidence | Orchestration, error handling, rewritten tests, behavior-changing config |
| `[skim]` | Glances for surprises | Refactors covered by tests, docs, renames |
| `[skip]` | Trusts the tooling | Generated files, lockfiles, vendored code, formatting |

**Default-up bias**: when an area could take either of two tags, it takes the deeper one. A `[skim]` that should have been `[study]` is how a bad change merges; a `[study]` that should have been `[skim]` costs a few minutes.

### `[study]` checklist

An area is `[study]` if any of these is true:

- It changes a contract other code or people depend on: an API path, request or response shape, wire or file format, event, CLI flag, environment variable, or public type.
- It changes persisted data: a schema, a migration, a backfill, what gets written where.
- It touches auth, authorization, crypto, secrets, or input validation at a trust boundary.
- It changes concurrency or delivery: locking, ordering, retries, idempotency, timeouts that guard other work.
- It does something hard to undo: deletes data, sends email or money, writes to an external system.
- A repo [review surface](#review-surfaces) tags it `[study]`.

### `[check]` checklist

Not `[study]`, and any of these is true:

- It changes control flow across components: orchestration, the order of calls, what calls what.
- It changes error handling: what's caught, retried, swallowed, logged, or surfaced to a user.
- It deletes or rewrites existing tests, or loosens an assertion. Read these early: a rewritten test can hide a changed behavior.
- It changes config, feature flags, infra, or dependencies in a way that changes runtime behavior.

### `[skim]` and `[skip]`

`[skim]` needs all of: behavior is preserved or the change is local to one unit, tests that cover it ran, and nothing above applies. `[skip]` is for output a tool produced (generated code, a regenerated lockfile, vendored code, a formatter pass) where that tool ran; name the tool.

### PR tier

A PR gets one tier: the highest tag among its areas. Contracts at `[study]` and tests at `[skim]` make a `[study]` PR. The areas keep their own tags, so the reader still sees which parts don't need studying. The change sets the tier, not the author: an agent's change isn't riskier for being an agent's, and a senior engineer's isn't safer.

The tier suggests how many people review it. The repo's rules decide.

| PR tier | Suggested human reviewers |
| --- | --- |
| `[study]` | Two, one of whom knows the contract or data |
| `[check]` | One |
| `[skim]`, `[skip]` | None beyond the author reading the guide |

An agent's review (Claude Code Review, Copilot, Codex) is a sensor, not a verdict, and never counts as a person's. The intent paragraph is what a review bot should check the diff against; a repo using Claude Code Review can say so in its `REVIEW.md`.

### Blast radius

Next to the tier, one line on who or what breaks if the change is wrong (callers, users, stored data, deploys) and how reversible it is. "Every `/v1/orders` client; additive field, revert is safe" tells the reviewer more than a risk word.

## Time to understand

A reviewer should understand the change from the visible part of the description in about 2 minutes, on a phone. That's roughly 250 words, tables included. Each collapsed block fits on about one phone screen. If it doesn't fit, the writing is too long or the PR is too big.

The guide states `Review time: ~N min`: the agent's estimate of reading the guide plus each area at its tag. A rough rate is a minute per 25 changed lines at `[study]`, per 75 at `[check]`, per 250 at `[skim]`, and nothing for `[skip]`. Above about 30 minutes, say so in the guide and propose a split; [git.md](git.md) already asks for PRs under 400 changed lines.

## Three moments

The same document serves three moments, so it's written once and kept current.

| Moment | When | What the human sees |
| --- | --- | --- |
| Plan | A plan changes a contract, a flow, a schema, or a review surface | A "Shape of the change" section in the plan: the areas with expected tags, and a before/after [preview](#plan-time-preview) |
| Pre-PR | The work is done and the agent is about to ask to open a PR, or the human asks for a walkthrough | The draft PR description. Where the harness has Artifact pages (they render Mermaid), publish it as one; the terminal gets the PR tier, review time and reading order |
| PR | Opening the PR, and each push after | The description itself, regenerated when a push changes a tagged area, the tier, or the evidence |

Not every back-and-forth in a session needs a walkthrough: the pre-PR one is the one that counts.

## Description layout

Everything goes in the PR description, because that's what a reviewer opens on GitHub, often from a phone, and because the squash copies it to `main` as the commit message ([git.md](git.md) "PR Body"). The always-visible part comes first; then one `<details>` block per tier present, deepest first, so each tier collapses on its own. `[study]` starts open.

````markdown
Adds a fulfillment status to orders so the mobile app can show shipping
progress. Closes #123. Plan: `specs/fulfillment.md`.

## Review guide

Review tier: [study], because `GET /v1/orders/{id}` gains a field.
Blast radius: every orders client; the field is additive, a revert is safe.
Review time: ~12 min

1. [study] `api/orders.proto`: new `fulfillment` field
2. [check] `orders/service.go`: fills it, new carrier timeout path
3. [check] `orders/service_test.go`: two cases rewritten
4. [skim] `docs/orders.md`
5. [skip] `gen/`, `go.sum` (buf, go mod tidy)

## Validation

- `make test`: pass, 412 tests
- `make e2e`: not run, needs staging credentials

## Rollback

Revert the squash commit. Nothing is written in the new shape until the
client ships.

<details open>
<summary>[study] Contracts</summary>

| Field | Before | After |
| --- | --- | --- |
| `fulfillment` | absent | `{status, carrier, updateTime}` |

</details>

<details>
<summary>[check] Control flow and error handling</summary>

...before/after diagram, what's retried, what's surfaced...

</details>

<details>
<summary>Decisions</summary>

- Polled the carrier instead of a webhook: no inbound endpoint to secure yet.

</details>

Assisted-by: Claude Code
````

- **Intent**: one paragraph on what changes and why, linking the issue, spec or plan. No heading.
- **Review guide**: the `Review tier:` line with its reason, the blast radius, the review time, and the reading order as a numbered, tagged list. Contracts and the tests that define new behavior come first.
- **Validation** and **Rollback**: see [Evidence](#evidence). Rollback says how to undo it, including flags and migrations.
- **Tier blocks**: inside each, whichever of these the tier's areas need: Contracts (a before/after table), Control flow (before/after diagrams), Data and schema, Error handling (new failure modes, retries, what's swallowed). Leave a blank line after `<summary>` or the Markdown inside won't render.
- **Decisions**: alternatives ruled out and why, collapsed, last.
- Drop any section or tier with nothing to say. A `[skip]` block, if any, is just the file list with the tool that produced each.
- Keep tables to three or four narrow columns; wider ones scroll sideways on a phone.
- Trailers stay the last paragraph, with any session link above them ([git.md](git.md) "PR Body").

`<details>` tags and Mermaid source land on `main` through the squash. That's accepted: the design record sits with the change.

## Evidence

Show, don't assert. Validation lists each check that was run with its result (`pass`, `fail`, or the count), and each check that applies but wasn't run as `not run` with the reason. Never describe an unrun check as passing. Separate failures that exist on the base branch from new ones. When behavior changed, name the test that fails if the change is reverted. A screenshot or a rendered output is evidence for a visual change; a paragraph saying it looks right isn't.

## Diagrams

Draw only where structure changed, and pick the diagram that fits:

| What changed | Mermaid diagram |
| --- | --- |
| A request or call path between components | `sequenceDiagram` |
| Orchestration, a pipeline, branching control flow | `flowchart TD` |
| A lifecycle or status field | `stateDiagram-v2` |
| Tables, entities, relations | `erDiagram` |

- **Before from the base commit**, read from the code at the merge-base (`git show <base>:<path>`), never from memory or from the plan. **After from head.** Use the same node names in both so the difference is the only difference.
- Mark what changed in the after diagram with a thick stroke and what went away in the before diagram with a dashed one, rather than fill colors, so both read in GitHub's light and dark themes.
- Under 15 nodes, top to bottom so it fits a phone's width. Split a bigger picture into one diagram per concern.
- Regenerate on every push that changes the drawn code. A diagram that describes an earlier push is worse than none.
- Durable architecture diagrams belong in the repo's docs or specs; the PR's diagrams describe this change.

GitHub's web and mobile browser render Mermaid in PR descriptions. Images (rendered SVG or PNG from a review surface) can't be attached to a description through the API, so link to where the repo publishes them (a CI artifact, a review gallery), and embed them in the pre-PR Artifact page.

## Plan-time preview

When a plan changes a contract, a flow, a schema, or a review surface, it shows the shape of the change before any code is written, if that's cheap:

- **Cheap**, a few minutes: Mermaid drawn from the base commit's code next to the proposed shape; a contract before/after table; existing fixtures rendered at base next to a mockup. Show it with the plan; it rides the plan's existing approval, not a new stop.
- **Not cheap**, needs the real implementation to show anything honest: write `Preview skipped: <reason>; before/after at completion` in the plan and go on.

The before/after at completion is always made, in the walkthrough and the PR. A review surface can override the default with `preview: required` (stop for agreement before implementing, however it has to be mocked) or `preview: report-only` (never preview).

## Review surfaces

A repo whose changes have their own before/after (rendered diagrams, UI screens, CLI output, generated docs, API snapshots) names them in a `## Review surfaces` section of its `AGENTS.md`, one `###` per surface:

```markdown
## Review surfaces

### Rendered diagrams

- Counts: any change to the rendered SVG of a file under `examples/` or `tests/`
- Tag: [check]
- Preview: required
- Render: `node packages/cli/dist/index.js <file> -o .scratch/<name>-<before|after>.svg`
- Before: build and render at the base commit, extracted with `git archive <base> | tar -x -C .scratch/base`
- Publish: CI posts the `review/renders` status with a link to the gallery; link it in the PR
```

| Field | Meaning |
| --- | --- |
| Counts | What makes a change touch this surface |
| Tag | The least tag an area touching it gets; the checklists can raise it |
| Preview | `if-cheap` (the default when omitted), `required`, or `report-only` |
| Render | The command that produces the output |
| Before | How to produce the base version without switching branches or adding a worktree |
| Publish | Where the outputs go for the PR, if anywhere |

A repo's existing rule in other words (nowline's "Visual changes") counts as a surface; renaming it is tidy but not required.

## The draft

The description is drafted in a file the skill regenerates from, kept where plans are kept: `specs/handoffs/` on a runner, committed and pushed so it survives the container; `.scratch/` on a workstation. Its name is the plan's name with `-review` added, so they sort together: `plan-auth-otter.md` and `plan-auth-otter-review.md`. Without a plan it's `{topic}-{word}-review.md`.

The draft is a working copy. The PR description is what people read, and the squash copies it to `main`, so the draft is removed before merge with the other `specs/handoffs/` files ([git.md](git.md) "Merging").

## Ownership

Whoever directed the agent owns the guide as much as the code: read it before the PR opens, because a confident, wrong review guide is worse than none. The agent that wrote the change writes the guide, since it knows the intent; a fresh-context reviewer, not the author, checks the code against it.
