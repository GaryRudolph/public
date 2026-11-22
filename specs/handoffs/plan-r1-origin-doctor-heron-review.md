Moves every reader of a repo's `origin` onto one helper, `plugins/personal/scripts/origin.py`, so the GitHub check, the owner and the masking are decided once, and stops the session-doctor hook from running a repo's own `make doctor` outside a runner, before the harness asks whether to trust the folder. Also fixes three smaller findings from the r1 review and gives this repo a doctor. Part of #45 (milestone m8).

Fixes r1.f23
Fixes r1.f24
Fixes r1.f3
Fixes r1.f15
Fixes r1.f20
Fixes r1.f10
Fixes r1.f22

## Review guide

Review tier: [study] [security], because the SessionStart hook decides when to run repo-owned code (f10, f3), and origin.py masks tokens in remote URLs before any facts script prints them (f24).
Blast radius: every session using the `personal` plugin (the hook) and the six facts scripts behind the skills. All fail open; nothing is persisted, so a revert is safe. On a workstation the hook stops running doctors and asks the agent to.
Review time: ~29 min

1. [study] [security] [`plugins/personal/scripts/session-doctor.py`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-f9c53e03a9110c9dfd0f5b89580f8d21749440d4472b25fa9085d2ebdc7bc12f): runner check (`CLAUDE_CODE_REMOTE`, `CI` or `GITHUB_ACTIONS` = `true`) and trust through origin.py
2. [study] [security] [`plugins/personal/tests/test-session-doctor.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-b0a9a38c3fc03b6eeb3da38791563b2c50e6470f3f7f92bad9d116215127da15): runner or workstation, host-class trust
3. [study] [security] [`plugins/personal/scripts/origin.py`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-5fca0abc6de5454070764062a9105183a3c6d7c67af383fec4626897bb32c3d0): parse, host classes, `mask()`
4. [study] [`plugins/personal/tests/test-origin.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-5ad743232df539a2bd085893720eb754737eaed6c303a2e3a30284f2ad88dd38)
5. [check] [security] [`plugins/personal/skills/personal-secrets/scripts/secrets-facts.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-98437b54f727e4942449645140daf81e5e4d27e56342380a11b3a1cef3d27b91): prints the masked remote, not the raw one (f24)
6. [check] [`plugins/personal/skills/personal-repo-baseline/scripts/repo-facts.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-a9efcf1cc213b0b5a815eb241f555b014639310a391a17b57b0be67399ecb214): on origin.py; strict IPv4 check; Python 3.9 f-strings (f20)
7. [check] [`plugins/personal/skills/personal-ship-pr/scripts/pr_state.py`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-96f08d4e88305c0b7f65c9555d8ddf9a48f22458d6f984a135f33c2266067fa8), [`plugins/personal/skills/personal-review-guide/scripts/review_facts.py`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-7a8854cb9e9a46d088a7f6d8dd8e1cf00071267bd6334a2f686ac67d5acc3e61), [`plugins/personal/skills/personal-codebase-review/scripts/review_log_facts.py`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-912b15e966fedb54dbe31de02d7bd96e595f41718a2cdeabec30fccf7e4182c6): local copies replaced by `load_origin()`
8. [check] the callers' tests: [`test-single-repo.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-84766284501e3f9a74ba1b87a4c840cd624b53bcadac0c0ba4f23a29a655d3f4), [`test-repo-baseline.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-55b07ff002f368ba9296d8cb242f37c05c806d5991678a4f61cbd6d78f90e200), [`test_ship_pr.py`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-cb936fde61a28c2a5574a6f1b16d1e492bb69959bd1719c8fa7cc643f78f8e61), [`test-review-guide.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-c554edcc6ca4421fb68c883223343781e7149a12280dfd8ef7d0b8d0af605b8b), [`test-codebase-review.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-ec92cd9a2cd15f7bfb366b9da4842cfbc2e04f855432c7c766a7387b17acc02a)
9. [check] [`agents/Makefile`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-f636515ed16c6c062d2e31157b8ff5e38dd1fb03ce19f1dcc0cf5c4441b9d4ee), [`triage.yaml`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-6c888fa5630a58b1f40931c1cb9281fb4daa914750c9230a5d385f520781e741), [`plugins/personal/tests/test-doctor.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-ee2c4fea5d1938f1cf9dfb25468c575abcfa51a3a2f11a4c3b7084f4eafe2b55), [`.gitignore`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-bc37d034bad564583790a46f19d807abfe519c5671395fd494d8cce506c42947): `make -C agents doctor` and its floors (f22)
10. [skim] [`plugins/personal/skills/personal-release/scripts/release_facts.py`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-fcbea12f40497592de947650c363584b8da61c920af498408a5a39e735581a45) and [`test-release.sh`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-1d69e580c8e5c57e9849d1e269c8203919e1ab2e27f089013ade10a771e69a9e): `ls-files` from the repo root (f15)
11. [skim] [`plugins/personal/skills/personal-standards/core.md`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-c1e2d2bf9b7fab8b83d3edd958794a2bf08b42577e5266e9ccf8a9673588c443), [`plugins/personal/skills/personal-standards/standards/makefile.md`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-e55b326d9197456fb39037f4199fc40c172d9c6a1c9d419c3362f1f859578f31), [`plugins/README.md`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-8b2fec43efe67316d27984b7b6fe79569fa2e61ffdd6ed811aa114e29338b860)
12. [skip] [`plugins/personal/cursor/rules/personal-core.mdc`](https://github.com/GaryRudolph/public/compare/main...fix/r1-origin-helper-doctor#diff-39a8d78a12609c027a769b918fbe42135cdb4da5ab7deaa55bb03bb12d504a79) (`make -C agents cursor-core-rule`); `specs/reviews/r1/f*.md`, one claim file per finding

## Validation

- `make -C agents validate test`: pass, on this branch rebased onto `main` at 6abaf90
- `make -C agents doctor`: pass, 7 ok, 1 warning (sops not installed; its tests print SKIP)
- Revert check: `test-session-doctor.sh` "runner or workstation" fails if the runner check is removed; `test-origin.sh`'s attacker-host and token cases fail without origin.py's host class and mask

## Rollback

Revert the squash commit. Nothing is written or migrated. The hook goes back to running trusted repos' doctors on every machine.

<details open>
<summary>[study] Session doctor: when a repo's doctor runs</summary>

| | Before (`main`) | After |
| --- | --- | --- |
| Where | Every machine | Only when `CLAUDE_CODE_REMOTE`, `CI` or `GITHUB_ACTIONS` is `true`; elsewhere one line telling the agent to run it |
| Trusted origin | Owner segment of any URL on any host | origin.py `is_github` (github.com, a `github.com-<x>` ssh alias, `ssh.github.com`, the cloud proxy) and a trusted owner |
| `https://attacker.example/lolay/x.git` | Runs | `not run`, with host class and masked URL |
| origin.py missing | n/a | `not run: origin.py unavailable`; hook exits 0 |

The home file's `# >>> personal >>>` block isn't the signal: `make install` leaves it out in plugin mode, the default, so a workstation looked like a runner. The Owner chose the three variables; a self-hosted Claude runner sets `CLAUDE_CODE_REMOTE=true` with `CLAUDE_CODE_REMOTE_ENVIRONMENT_TYPE=self_hosted`.

</details>

<details>
<summary>[study] origin.py design note</summary>

- Standard library only, Python 3.9. `parse(url)` and `read(repo_dir)`, which runs `git remote get-url origin` (so `insteadOf` shorthands resolve) and never raises: no origin is class `none`.
- `host_class`: `github`, `ssh443`, `alias` (ssh or scp `github.com-<x>`, no dot in `<x>`), `proxy` (http(s) to 127.0.0.1 or localhost under `/git/<owner>/<repo>`), `other` (IPs included), `local`, `none`. `is_github` covers the first four. Callers gate on `is_github`, never on `owner`.
- `mask()`: any non-ssh scheme's whole userinfo becomes `***`; ssh keeps the user and masks a password. This is `repo-facts.sh`'s `redact_url`, moved unchanged.
- CLI for the bash scripts: one tab-separated line, `-` for empty fields, control characters stripped, never the raw URL.
- Loaded by a path from the caller's resolved file (`Path(__file__).resolve()`, so symlinked skill installs land back in the plugin). Where a skill is copied on its own (Windows `make install`), it can't load, and every caller fails open with a reason; masking fails closed (no URL shown).

</details>

<details>
<summary>Decisions</summary>

- One helper, not a copy per skill: copies were the f23 problem. The cost is the copied-skill gap above, accepted.
- No separate CI state for the doctor: CI and cloud both run it until something needs to differ.
- One PR for seven findings, per the m8 plan; it runs past 400 lines because origin.py replaces six parsers at once.

</details>

https://claude.ai/code/session_01BNKwNXoyRd6Bpa9828PePd

Assisted-by: Claude Code
