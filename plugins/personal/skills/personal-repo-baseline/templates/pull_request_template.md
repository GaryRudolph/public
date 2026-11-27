<!--
A review guide (personal standards, review.md): a reviewer should understand
the change from everything above the first <details> in about 2 minutes on a
phone, without having seen the session or the plan that produced it. So say
what's true today before what changes, give a linked plan's or issue's
one-line content inline, and use no label the reader would have to look up.

Tag each area of the diff with what the reviewer should do with it; the PR's
tier is the highest tag, and an area that could take two takes the deeper.

- [study] read every line: contracts, schema, auth, concurrency, anything
  hard to undo.
- [check] read the named hunks: control flow, error handling, rewritten
  tests, behavior-changing config.
- [skim] glance: refactors covered by tests, docs, renames.
- [skip] trust the tool: generated code, lockfiles, formatter passes.

Drop any section or tier with nothing to say. A [skim] or [skip] PR also
drops Before and after; a [study] or [check] PR keeps it, as
"None: <reason>" when there's nothing to show.
-->

Today <what's true now, and what goes wrong or is missing>.

This <what changes>. Closes #

## Before and after

<!-- The one view that explains the change, read from the base commit and from head: a table for who can do what, a contract or config, or behavior per input; a Mermaid pair for a flow or lifecycle; a link to rendered output. -->

| <what> | Before | After |
| --- | --- | --- |
| <actor, field or case> | | |

## Review guide

Review tier: [check], because <reason>.
Blast radius: <who or what breaks if it's wrong; how reversible>.
Review time: ~N min

<!-- Reading order: contracts and the tests that define new behavior first. One line per area, saying what to confirm there, not what the diff contains. Link each path to its diff. -->

1. [check] `path`: <what to confirm there>
2. [skim] `path`

## Validation

<!-- One line per check: what ran, with its result, and what applies but didn't run, with why. -->

- `<command>`: pass, fail, or not run (why)

## Rollback

<how to undo it: revert, flag, migration>

<!-- One collapsible block per tier present, deepest first; [study] starts open. Keep the blank line after <summary> or the Markdown inside won't render. -->

<details>
<summary>[check] Control flow and error handling</summary>

<further before/after for this tier's areas: contracts table, Mermaid diagrams, data, error handling>

</details>

<details>
<summary>Decisions</summary>

<alternatives ruled out, and why>

</details>

<!-- If an agent helped, end with the trailer paragraph: Assisted-by: <tool> -->
