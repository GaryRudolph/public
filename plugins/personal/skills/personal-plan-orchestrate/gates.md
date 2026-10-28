# Gate details

Part of [`SKILL.md`](SKILL.md), whose "Gates" table says which gate fires
and whether it stops in each mode. This file is the rest: read it when
`plan_state.py` reports a stop or a checkpoint, the next unit is a fix-up,
a check fails, or a worker discloses a breach. Section names in quotes
refer to `SKILL.md`.

Contents: no gate 5 on a one-group unit · checkpoints · automatic retries · fix-ups · the cost guard · over expected · scope breaches · a waiver

**When the canary fires.** It holds back every group but the first of a
multi-group unit until that group passes its check and review, to catch a
bad setup (branch, access, routing) on one worker rather than N. On a
workstation it fires once per plan: `plan_state.py`'s `canary_passed` is
true once any Review log line is a PASS, and from then on a session's first
launch runs whole waves. On a cloud or self-hosted runner every session is
a new container, so its first launch canaries again (`mode.runner` is
`cloud` or `self-hosted`). The parent still passes `canaryDone: false` on
a session's first launch and true after; the script decides whether to
split. **No gate 5 on a one-group unit:** nothing is held back, so there is
no canary, and no gate-5 stop or checkpoint in either mode. `canaryDone` is
true from the next launch on all the same.

A first review CONCERNS (not a failed check or a disclosed breach) gets its
`N-fix` without a gate in both modes. Opening a PR, tags, remote branch
deletes, deploys and permission prompts wait in both modes; on a runner,
commit and push before a call likely to trip a permission prompt.

**Checkpoints are logged, not asked.** End the unit's Review log note with
them (`; passed unattended: gate 4, gate 2`; an automatic fix-up's
`; passed unattended: gate 1 (fix-up 2 of 2)`), keep only the latest unit's on
the Status line, replacing the earlier ones rather than adding to them
(`| passed unattended: gate 4, gate 2 before wave 3`), and list every
checkpoint, automatic retry and fix-up with its reason under **Deviations
from plan** in the handoff and the Completion summary.

**Automatic retries (unattended only, inside the run).** A worker with no
result, or a review that died, reruns once on the same tier (a dead review
reruns only the review). `failed` or `low_quality` reruns once a tier up,
into `[exec]` or `[deep]` only, logged as a gate-6 checkpoint. Never on an
`[xdeep]` or Fable unit, never on a step-up Gary approved, never for
`needs_info`. The retry keeps its wave's number and token row. A second
failure is gate 1. On Claude Code the workflow does this; elsewhere the
parent does.

**Fix-ups** come from the Review log, never from open steps. The k-th
CONCERNS line in a row for a group makes the next unit its fix-up, labeled
`N-fix` for the first and `N-fix<k>` after (`N-fix2`, `N-fix3`; never
`N-fix1`). A failed check is logged as a CONCERNS line, so it starts or
extends the same streak. A PASS ends the streak, and so does a WAIVED line.
When several groups of one wave have streaks, the longest goes first. A
fix-up's worker gets the failure verbatim, with the streak's earlier ones,
and its `from` is the `<from>` of the group's Review log line (the wave's
start), not HEAD. A **check-only fix-up** (every group's latest failure is a
`check_wave.py:` note with no `; review CONCERNS:`) runs its worker on the
`[fast]` row (Haiku medium) with a Sonnet high review, labeled `[fast]` in
its titles and token lines, since the script is the real check; a fix-up
that carries a review concern keeps the wave's tier and an Opus review:
- a review concern is fixed with new commits whose subjects start with the
  step ID they fix; earlier commits stay as they are;
- a failed check is fixed at its cause: a missing step commit is made (an
  empty one when the step changes no file), a by-product path is deleted or
  a path the group made is committed, and a rejected message (first line,
  `Co-authored-by`, missing trailer) is reworded on just the commits the
  check names by SHA: `git commit --amend` when HEAD is one of them,
  otherwise a non-interactive `git rebase` onto `<from>` (`GIT_SEQUENCE_EDITOR`
  and `GIT_EDITOR` set to commands) that keeps every other commit's message
  and content, the parent's bookkeeping commits included;
- a failed-check note that also carries `; review CONCERNS:` gets both
  instructions;
- the fix-up's reviewer checks the quoted failure itself too, not only the
  change.

A reword replays the commits after it with new SHAs, so after a fix-up that
rewrote pushed commits, push with `--force-with-lease --force-if-includes`.
Raising the cap (`fixups N` on the mode line) needs Gary's approval of
gate 1. Each fix-up gets a Cost table row with expected `—`, labeled with
its number (`2-fix2 [exec] repo-b m1 s4`), so it adds nothing to the guard's
projection until it has run.

**The cost guard**, before every unit, in both modes:

    projected = the Token log's dollars so far
              + the next unit's expected $ (its Cost table row; 0 once any step of
                that wave is done, which covers a canary's continuation and a split
                wave's later units; 0 for an unplanned row)
    stop at gate-guard when projected > max(guard × the Cost table's Total, floor)

With `guard 3x min $50`, a plan expected at $78 stops past $234, and one
expected at $10 past $50. A yes at the guard raises the multiple to the
next whole one above the projection, or to what Gary names; the raise needs
his approval of `gate-guard`. Unplanned premium work stops whatever the
spend.

**Over expected, a note.** Once `plan_state.py`'s `cost.actual` passes
`cost.expected_total`, add `| over expected: ~$<actual> of ~$<total>` to
Status, say so in the handoff and in the next message Gary sees, and carry
on: it is not a stop in either mode, only the guard is.

**Scope breaches stop at gate 1 in both modes** (decision 10), since no
fix-up can repair them: edits in a directory with no group, a `from` that
is no longer an ancestor of HEAD (both in `check_wave.py`'s `scope`), and,
on a workstation only, a group's new uncommitted path (its `uncommitted`,
which may be Gary's own edit). Write `BLOCKED at gate 1`, no Review log line
for the group, leave its steps open, save, ask. On a runner, `uncommitted`
paths are an ordinary failed check that gets `N-fix`.

**A waiver.** At a gate 1 a streak raised, Gary may waive the concern
instead of approving the next fix-up. Log `review wave-N (<group-id>)
<from>..<to>: WAIVED - <Gary's answer, whitespace collapsed> - <date>`,
which ends the streak as a PASS does. The words must be his message
verbatim (the Claude Code hook checks); a paste never waives.
