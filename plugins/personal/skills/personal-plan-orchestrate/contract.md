# Subagent context contract

Part of [`SKILL.md`](SKILL.md). On the Claude Code workflow path,
`plan-segment.js` writes every worker and reviewer prompt from the group
and `args`, so read this on Cursor and the Agent path, where you write
them. Section names in quotes refer to `SKILL.md`.


Every worker prompt carries items 1-8, and item 9 whenever the handoff has
anything to carry; every reviewer prompt carries item 10. On Claude Code
the workflow writes the prompt from the group and `args` you pass; on
Cursor you write it.

1. **Spec excerpt:** the plan section, verbatim. Quote, don't paraphrase.
   Then the whole feature: "Read `<plan path>` (read-only) for the steps
   before and after yours", the plan's `## Shape` section quoted
   (`plan_state.py`'s `shape`, when non-empty), and "run `git -C <workdir>
   log --stat <plan start>..HEAD` first, so you know what earlier steps
   built and where", where `<plan start>` is `plan_state.py`'s
   `plan_start` or, before any review, the group's `from`.
2. **Working-directory scope:** the absolute path of the one git working
   directory it may edit, as a hard limit ("All edits must be inside
   `<path>`. Do not edit anything outside this directory.").
3. **Acceptance criteria:** the plan's, quoted, or derived from the step
   titles.
4. **Hard scope limit:** the exact step IDs as `plan_state.py` reports
   them (a heading's `s1` under `m2` is `m2.s1`, since step numbers
   restart in each milestone), and "Do not implement later steps, and do
   no work not listed here. Prefer extending a file an earlier step
   created over adding a new one; a file you create that the Shape
   section's Creates list lacks goes under `newFiles` with one line on
   why."
5. **Standards pointers:** the specific standards files the work needs.
   Don't skimp for `[deep]` and `[xdeep]` work.
6. **Output contract:** "Write your full output (decisions, surprises,
   follow-ups; not diffs, which git holds) to
   `.scratch/orchestrate-{plan-name}-{wave-n}-{task-id}.md`. Return only a
   structured 1-paragraph summary covering: what changed, what was decided,
   any surprises (a workaround the environment needed on a line that
   starts `env:`), every file you created with its reason when the Shape
   section lacks it (`newFiles`, none when there is none), every rule of
   this prompt you broke or tried to break
   and whether it ran or was blocked (`breaches`, none when there is
   none), and the artifact path." `{wave-n}` and `{task-id}` are as in
   "Files a run keeps". The result's status is `done`, `failed`,
   `low_quality` or `needs_info` (with one question); never report partial
   work as `done`.
7. **Token reporting (Cursor `Task` subagents only):** see `adapters/cursor.md`.
   Claude Code workflow workers get no token instruction; the parent tallies
   their transcripts.
8. **Git instruction:** "Commit each finished step on the current branch
   (`<branch>`) as its own commit, staging only the paths you changed. A
   step that changes no file gets an empty commit (`git commit
   --allow-empty`). The first line is the step ID as the scope lists it,
   a space, and an imperative subject (`m2.s3 Wire the results view`);
   then a blank line; then, as the last paragraph, exactly these trailer
   lines: <the harness's trailers>. Never add `Co-authored-by` or
   `Signed-off-by` lines. Do not
   push, create, or switch branches." Plus: "If the spec reads two ways
   with materially different results, or you lack an access the step
   needs, return `needs_info` with one question. Never run a command that
   acts outside this working directory: a push, opening or merging a PR, a
   release, pushing a tag, deleting a remote branch, deploying, publishing
   a package, posting anywhere, or the repo's own publish, release or
   deploy scripts; when the spec names a dry-run form, run exactly that
   form. If a step needs an outward action, return `needs_info` naming
   it." Plus the resume rule: "Run `git -C
   <workdir> log --format=%s <from>..HEAD` first. A step that already has a
   commit whose subject starts with its ID was done by an earlier attempt:
   check it against the acceptance criteria and skip it if it holds. If a
   file you need already has uncommitted changes, don't touch it: return
   `failed` and name it." A retry's prompt also names the earlier attempt
   and how it ended.
9. **Carry-forward** (when any): the handoff's "Decisions so far",
   verbatim, with "where one changes what the spec excerpt says, follow
   the decision and say so under decided", and its "Environment notes",
   with "use them rather than finding them again". On Claude Code these
   are `args.decisions` and `args.environment`.
10. **Review questions (reviewers):** after the spec check ("does it do
    what the spec and the acceptance criteria ask, no more and no less,
    correctly, with tests where the repo expects them"), the code's
    shape, whatever the tier: "Could an engineer who didn't write it
    understand it in one reading? Does it duplicate something already in
    the repo, or in this plan's earlier commits (`git log --stat <plan
    start>..HEAD`)? Name the pair. Could it be fewer files or fewer public
    functions with no loss? Does any helper exist only to satisfy a
    length rule? Extraction that threads intermediate state through new
    parameters is a finding, not a fix, and about 50 lines a function is a
    smell, not a gate. A `consolidate` finding that names the files to
    merge is a legitimate CONCERNS. Compare `git diff --diff-filter=A
    --name-only <from>` with the plan's Shape section and the worker's
    `newFiles`: a new file in neither, or one whose reason doesn't hold,
    is a finding."

Reviewers are read-only and get the spec, the Shape section, the
carry-forward, the acceptance criteria, the standards, the worker's summary
(with its `newFiles`, and any breach it disclosed, to look for traces of)
and the commit range; they read command output inline rather than through
a file, back every finding with evidence and report only defects the plan
must fix. They run at the tier the standard's review routing gives
(`SKILL.md` "Tiers and models").
