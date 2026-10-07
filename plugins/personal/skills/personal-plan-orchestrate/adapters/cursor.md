# Cursor adapter

How `personal-plan-orchestrate` runs on Cursor, where the dispatch tool is
`Task` with a per-call `model`. [`SKILL.md`](../SKILL.md) is the core: the
kickoff, the mode, the gates, the loop, the handoff. This file is the
Cursor-specific rest: the models and what to check before using them, the
dispatch call, the boundary rows, the tally, and what the harness can't
enforce. Read `SKILL.md` first.

This text is the Cursor procedure as it stood before the Claude Code
adapter. The Cursor fixes (the list at the end) are phase 3 of the
orchestrate-native plan; until they ship, the parent applies the core by
hand: it checks the gates itself, and reviews `[deep]`, `[exec]` and
`[fast]` waves inline and `[xdeep]` waves with a read-only xhigh subagent.

## Runner signal

A Cursor cloud agent shows itself through the Cloud MCP's `run-info` tool
and its own pushed branch, and is recorded as `harness=cursor runner=cloud`
(`SKILL.md` "Runner signals"). `CURSOR_AGENT` is not a signal.

## Harness gate: verify before proceeding

This path assumes Cursor's `Task` tool with a per-invocation `model`
parameter and the Cursor slugs from the standard's model picker:

- `[xdeep]`: `claude-opus-5-5[effort=xhigh]` (alt
  `claude-fable-5-1[effort=xhigh]` only as a different-model second opinion
  after Opus xhigh failed the step; `[effort=max]` only where a gain is
  measured)
- `[deep]` and the parent: `claude-opus-5-5[effort=high]`
- `[exec]`: `grok-4-7[effort=high,fast=false]`, or `claude-sonnet-5-5[effort=high]`
  once included Cursor-pool usage runs out
- `[fast]`: `composer-2.5[fast=false]`

If the standard's model picker and this list disagree, the picker wins.

**Default for Cursor: proceed.** Inspect your tool list. If a `Task` tool's
`model` parameter accepts these slugs, or takes a free-form model string,
assume it works and continue. The schema is enough evidence; don't ask Gary
to confirm, and don't verify that the parameter "actually takes effect"
beyond the schema.

**Bracket parameters.** The `[effort=...]` and `[fast=false]` forms come
from Cursor's subagent docs, which don't list the `Task` enum and list only
`high` and `max` as Claude efforts, so `xhigh`, `medium` and `low` are
unverified. A dropped value runs Cursor's default (medium on Opus 5.5). If
the enum offers plain or suffixed IDs instead, dispatch the entry for the
same model at the same or nearest effort, and tell Gary to refresh the
standard's model picker. If the only Composer entry is Fast, use it, name
its token lines' model `composer-2.5 Fast`, and price them at the Fast row
of the Model price table (6x standard on input and output, 2.5x on cache
reads).

**Use the newest version of each family.** Cursor has no version-less
alias, so these slugs go stale. If the enum offers a newer entry of the same
family at the same effort, dispatch that one and tell Gary to refresh the
picker. A missing exact slug is not a reason to stop while a newer entry of
the same family is present.

**Stop and ask Gary** only when one of these is true:
- `Task` is absent from your tool list.
- `Task` has no `model` parameter, or its enum lacks Opus, Composer, or
  both Grok and Sonnet: recommend `personal-plan-model-tiers` and wait. A
  missing Fable entry only removes the `[xdeep]` alt.
- No xhigh Opus entry exists, or `model` takes free text so nothing confirms
  `[effort=xhigh]`: say so in the gate-7 question and dispatch the effort
  Gary picks, for the wave and its review.

When you stop, name the specific concern, recommend the fallback, and wait
for an explicit answer.

## Dispatch

Issue real `Task` tool calls, never text for Gary to run, and never a code
block of calls: one per working directory, all in one assistant message,
each with:
- `description`: the wave title in the standard's [Wave title
  format](../../personal-standards/standards/plan-execution.md#wave-title-format),
  `Wave {n} of {t} [{tier}] {group-id}` (`Wave 2-fix2 of 4 [exec] repo-B m2
  s4`). `{n}` is the unit's label, `{t}` the total wave count (the `N` in
  Status), `{group-id}` the working-directory-scoped id. It is the
  subagent's title in Cursor's agent list and fixed at spawn: Cursor has no
  supported way to rename it.
- `subagent_type: "generalPurpose"`.
- `model`: the slug above.
- `prompt`: the full contract (`SKILL.md` "Subagent context contract"),
  scoped to that directory, with item 7 below.

Every `[deep]` wave goes out too, even on one working directory: the
parent's context never holds a wave's diffs. Groups in distinct working
directories run in parallel; Gary opts into in-repo parallelism by creating
worktrees (Cursor's `/worktree`, or `git worktree add`) before invoking the
skill.

**Worked example: a 2-repo `[exec]` wave.** The next `[exec]` group has
steps `m2 s1-s3` in repo A and `m2 s4-s6` in repo B, distinct working
directories. One assistant message calls `Task` twice, with `description`
`Wave 2 of 3 [exec] repo-A m2 s1-s3` and `Wave 2 of 3 [exec] repo-B m2
s4-s6`, `model: "grok-4-7[effort=high,fast=false]"`, and each prompt scoped to its
repo. After both return, collect the summaries and drop the full outputs
(they are on disk), then go on to "When a unit completes". A fix-up of that
wave is the same with `Wave 2-fix of 3` (`2-fix2` for the second).

**Worked example: a 2-repo `[deep]` wave.** The next group is an
architectural decision in repo A and a sibling decision in repo B. The
parent takes neither inline: one message, two `Task` calls with
`model: "claude-opus-5-5[effort=high]"`, one per directory. Quote the spec
verbatim and give the full standards-pointer set (architecture work: don't
skimp). The parent reads only the summaries, and re-reads an artifact when
needed, so it never holds the diffs even though it runs on the same model.
That is the always-dispatch rule: the parent supervises, whatever the tier.

## Boundaries

What each boundary dispatches. A gate in the row stops or is a checkpoint
per the mode (`SKILL.md` "Gates"); the parent dispatches only after it.

| Boundary | Dispatch |
|---|---|
| `[deep]` or `[xdeep]` to `[exec]`, one working directory | one `Task` on the `[exec]` model |
| the same, several working directories | one `Task` per directory, all on the `[exec]` model |
| to `[fast]`, three or more contiguous `[fast]` steps | `composer-2.5[fast=false]`, one per directory |
| to `[fast]`, fewer than three | the run was folded into the adjacent `[exec]` wave (its `[fast]` tags stay): treat as `[exec]` |
| `[exec]` to `[fast]` | the same no-thrash split: three or more, a `[fast]` wave; fewer, folded into the `[exec]` wave |
| `[exec]` or `[fast]` to `[deep]` | gate 2 or 3, then `claude-opus-5-5[effort=high]`, one per directory; the parent never runs the group itself |
| into `[xdeep]` | gate 7 (and 2 or 3 from `[exec]` or `[fast]`), then `claude-opus-5-5[effort=xhigh]`, one per directory; the Fable alt only on a gate-6 step-up after Opus xhigh failed the step |
| leaving `[xdeep]` | the rows for leaving `[deep]` |
| `[deep]` to `[deep]` | `claude-opus-5-5[effort=high]`, one per directory; always dispatch, even on a single directory |
| a milestone boundary mid-walk | gate 4 before the next dispatch |

**Step-up on failure:** composer, then the `[exec]` model at high, then
Opus high (re-tag `[deep]`), then Opus xhigh (re-tag `[xdeep]`, gates 6 and
7), then the Fable alt (gates 6 and 7). `[exec]` never goes past high. Quote
the re-attempt's expected cost from the standard's §"Expected cost" at the
gate.

**Checking.** `check_wave.py check --snapshot <s> --group '<json>'` per
group (`{"id","workdir","steps","from","trailers"}`), where `trailers` is
what the worker was told. Cursor has no run record, so there is no `--run`.

## Cost table and counting header

Label the Cost table `**Cost (API-equiv, Cursor models)**`. Estimate each
wave per the standard's §"Expected cost" at the Cursor slug for its tier,
each `[xdeep]` row including its review subagent.

The counting header at the top of `## Token log` is the Cursor form (the
standard's §"Token line format", "Counting header"): the token line format
and row labels, the accumulation heuristic, the price rows of the models
the plan runs (Opus for this parent, the `[deep]` and `[xdeep]` waves and
the `[xdeep]` reviews; Grok and the Sonnet alt for `[exec]`; Composer for
`[fast]`, at its Fast row when only Fast exists), and the one-line formula.
Contract item 7 quotes from it. On re-entry keep the header, refreshing it
in place when the plan's models changed; never write a second one.

## Tokens

**Contract item 7.** A `Task` subagent can't read its own usage. End its
returned summary with one token line per model it ran on:
`tokens wave-<label> <task-id> (<slug>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv (heuristic)`
(`review-wave-<label>` for the `[xdeep]` reviewer). Quote into the prompt,
from the counting header, the accumulation heuristic, the cache-aware
formula and its model's rate row, so the subagents count from that one
copy, and keep the `(heuristic)` label. The parent can recompute a line's
dollars from its four counts when a subagent omits or miscomputes them.

**The parent's lines.** Cursor exposes no usage to an agent, so the
parent's own lines use the same heuristic, in the standard's form for part
of a chat: `T0` is the tokens of this chat's earlier lines, and the first
call after a subagent run or a gate wait that outlasted the 5-minute cache
TTL is a cold start. `orchestrator-kickoff <plan name>` comes once the
kickoff is written, then `orchestrator-wave-<N> <group-id>` after each
wave's review and bookkeeping, each covering the parent's tokens since its
previous line in this chat, gates included. Inline review work counts
there, not as `review-wave-N` lines; only the `[xdeep]` reviewer subagent
reports its own.

**Pasted usage.** Cursor usage Gary pastes replaces the lines it covers
(the standard's §"Token line format", "Token log"). CSV rows that can't
tell the parent from an Opus subagent become one `(combined: <rows>)` line.
Never blend the parent's and the subagents' counts into one line: they run
on different models, and each line is priced at its own model's list rates
(the standard's §"Model price table", "Agent costs are API-equivalent").

**The running block**, printed at every stop with the Token log lines so
far and their total (`SKILL.md` "Token tally" says when):

```
tokens so far:
  tokens orchestrator-kickoff <plan-name> (claude-opus-5-5): input ~… / cache read ~… / cache write ~… / output ~… | ~$… API-equiv (heuristic)
  tokens wave-1 m1-s1-s3 (grok-4-7): input ~… / cache read ~… / cache write ~… / output ~… | ~$… API-equiv (heuristic)
  …
  RUNNING TOTAL: input ~… / cache read ~… / cache write ~… / output ~… | ~$… API-equiv (heuristic)
```

The RUNNING TOTAL's dollars are the sum of the lines' dollars, not a
blended rate applied to the summed tokens. It carries `(heuristic)` when any
line does.

## Mode on Cursor

Unattended is proposed on a Cursor cloud agent and rests on the parent: no
hook checks the confirmation, and none checks the gates either. A
workstation proposes gated.

## Phase 3

Not built yet; the parent applies the core by hand until it is:
- The gates computed by `plan_state.py` and checked in code, not read off
  the plan by the parent.
- A review subagent per working directory, on Opus, in place of the inline
  review.
- An optional fail-closed `subagentStart` hook that checks a dispatch the
  way the Claude Code hook checks a launch. A cloud agent reads only
  `.cursor/hooks.json`, so the hook has to live there.
