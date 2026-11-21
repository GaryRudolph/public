When a review walk ends with many fixes, plan the remediation in a fresh `[deep]` session before any fix starts, then hand out one card per PR at its own tier. Small fix sets still go straight to tier-tagged cards. Neither the walk session nor the review session writes a fix.

## Review guide

Review tier: [check], because it changes how sessions hand work to each other at the end of a walk and a review.
Blast radius: agent workflow text only; a revert restores the old one-card-per-group ending.
Review time: ~6 min

1. [check] [`personal-review-walk/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/gallant-curie-hy6ez1#diff-ae0942fa0a9edd918e4c70e3597ca923613559d7c7401cec569cb6005b3313c3): End step 3 asks plan-or-cards with a plan-sized test; Don't forbids fixing or planning in the walk session
2. [check] [`standards/codebase-review.md`](https://github.com/GaryRudolph/public/compare/main...claude/gallant-curie-hy6ez1#diff-aad28a647717089d0427308a09326c5992883ebc92d148e6e79aa533e1bab3ea): "Who writes the fixes" and "Planning the remediation" under Outputs
3. [skim] [`personal-codebase-review/SKILL.md`](https://github.com/GaryRudolph/public/compare/main...claude/gallant-curie-hy6ez1#diff-84f4da220c8aefe3daa979f74462c52f6ce4236655150818a371896b43409474): "Show it" offers the planning session when plan-sized
4. [skim] [`core.md`](https://github.com/GaryRudolph/public/compare/main...claude/gallant-curie-hy6ez1#diff-c1e2d2bf9b7fab8b83d3edd958794a2bf08b42577e5266e9ccf8a9673588c443): one sentence on the walk bullet
5. [skip] [`personal-core.mdc`](https://github.com/GaryRudolph/public/compare/main...claude/gallant-curie-hy6ez1#diff-39a8d78a12609c027a769b918fbe42135cdb4da5ab7deaa55bb03bb12d504a79) (make -C agents cursor-core-rule)

## Validation

- `make -C agents validate test`: pass (the 8 validation warnings are on main too)

## Rollback

Revert the squash commit.

<details>
<summary>[check] Control flow</summary>

Before: walk ends, then one card per `fix` group, straight from the walk session.

After: walk ends, then the walk judges plan-sized (more than three groups, an order between groups, a cross-repo group, or a decision that needs design):

- plan-sized: one `[deep]` planning session (new) groups fixes into PRs, tags tiers with `personal-plan-tag-tiers`, posts the plan on the tracking issue, queues one card per PR at its tier. No code, no PR.
- otherwise: one card per group, title starting with its tier.

Each PR's session runs directly or under a driver, whose kickoff question already picks this session or a new one.

</details>

<details>
<summary>Decisions</summary>

- New session for planning, not the walk session: the walk's context is long and every call re-sends it, and a separate session makes "don't fix here" structural.
- `personal-plan-tag-tiers`, not `personal-plan-model-tiers`, in the planning session: model-tiers drives one plan on one branch, which is one PR; remediation is several PRs.
- Plan only when plan-sized (Owner's call): small sets skip the extra session.

</details>

Claude-Session: https://claude.ai/code/session_01BNKwNYocNHZSceaBugtKDt

Assisted-by: Claude Code
