```
--- KICKOFF: begin execution at [deep] ---

  Status: BLOCKED at gate review-wave-2 | 2/2 groups done | last review: wave-2 CONCERNS 2026-11-22 | updated 2026-11-22

  review: every-wave

  Suggested chat title: Wave 1 of 2 [deep] m8 s1

  Next model
    Cursor:      claude-opus-5-5[effort=high]
    Claude Code: /model opus                (/effort high)

  Prompt to paste into the next chat:
    Read specs/handoffs/plan-r1-origin-doctor-heron.md. Begin execution at the top
    of the plan.
    On branch fix/r1-origin-helper-doctor (task branch): commit each finished step.
    Before you stop, update plan progress: append ` (done)` to the
    headings you finished, update the Kickoff Status line, and flip the
    matching todos. Append one line per model this chat ran to the
    plan's "## Token log", counted and priced per its counting header:
      tokens wave-1 m8-s1 (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
    Then stop at the next STOP marker and report what you changed and
    any deviations from the plan.

---
```

**Cost (API-equiv, Claude Code models)**

| wave | expected tokens | expected $ |
|---|---|---|
| 1 [deep] m8 s1 | ~2.7M | ~$1.4 |
| 2 [exec] m8 s2-s7 | ~7.6M | ~$2.9 |
| kickoff | ~1.5M | ~$1.0 |
| **Total** | ~12M | ~$5.3 |

Expected values are estimates, good to about 2-3× per wave.

# m8 - Origin helper and doctor (r1.f23, f24, f3, f15, f20, f10, f22)

One PR from this repo, `GaryRudolph/public`, on `fix/r1-origin-helper-doctor`. Part of #45 (remediation plan comment 7074103845, milestone m8).

**Authority.** The Owner's walk outcomes, https://github.com/GaryRudolph/public/issues/45#issuecomment-7074013504, decide every fix; where the register `specs/reviews/2026-11-04-r1-full-findings.md` recommends otherwise, the walk wins. The register's locations are at fe5a3fe: re-read each at your head. Change this repo only; nothing is ported to the Agerpoint bok (so `agents/lib/` is untouched).

**Decisions.**
- f23: one `plugins/personal/scripts/origin.py` (host, owner, repo, masked URL) used by every facts script. The real case is SSH aliases; the cloud origin is now plain https.
- f24: masked through the helper. f3: host check through the helper.
- f10: the session-doctor hook runs `make doctor` on runners only. Locally it only tells the agent to run it, so the run goes through Claude Code's folder trust and permissions.
- f22: `doctor` in `agents/Makefile` plus a root `triage.yaml`.

**Done when** `make -C agents validate test` passes, and each finding has a claim file `specs/reviews/r1/f<K>.md` in the shape of `specs/reviews/r1/f18.md` and `f21.md` (Finding, Claim, Change, Evidence). Touch nothing else under `specs/reviews/`.

## Shape

Creates:
- `plugins/personal/scripts/origin.py` — no shared module owns origin parsing; six callers each carry their own copy (f23)
- `plugins/personal/tests/test-origin.sh` (guess) — origin.py's cases, beside `test-session-doctor.sh`, wired as a `test-origin` target in `agents/Makefile`
- `triage.yaml` — the walk's f22 decision: the repo root declares its toolchain floors
- `specs/reviews/r1/f23.md`, `f24.md`, `f3.md`, `f15.md`, `f20.md`, `f10.md`, `f22.md` — one claim per finding
Modifies:
- `plugins/personal/skills/personal-review-guide/scripts/review_facts.py`
- `plugins/personal/skills/personal-ship-pr/scripts/pr_state.py`
- `plugins/personal/skills/personal-codebase-review/scripts/review_log_facts.py`
- `plugins/personal/skills/personal-repo-baseline/scripts/repo-facts.sh`
- `plugins/personal/skills/personal-secrets/scripts/secrets-facts.sh`
- `plugins/personal/scripts/session-doctor.py`
- `plugins/personal/tests/test-session-doctor.sh`
- `plugins/personal/skills/personal-release/scripts/release_facts.py` and its test (guess)
- `plugins/personal/skills/personal-standards/core.md`
- `plugins/personal/cursor/rules/personal-core.mdc` (generated)
- `plugins/personal/skills/personal-standards/standards/makefile.md`
- `agents/Makefile`
- the tests of the callers above, where they exist (guess)

## m8 - Origin helper and doctor

--- WAVE 1 [deep] ---
### s1 - [deep] Design origin.py and how every caller loads it (done)

Design `plugins/personal/scripts/origin.py`; do not implement. Decide:
- The interface: host class, owner, repo and masked URL, as a Python import and as a CLI the bash scripts (`repo-facts.sh`, `secrets-facts.sh`) call. Host classes: `github.com`; `github.com-*` SSH aliases; `ssh.github.com` on 443; the cloud proxy form (`http://local_proxy@127.0.0.1:<port>/git/<owner>/<repo>`); anything else is `other`. Masking: drop any userinfo password or token, as `repo-facts.sh` `redact_url` does now.
- How callers load it: by a path relative to their own file, as `personal-codebase-review/scripts/review_log_facts.py` loads `review_facts.py`. Check it resolves on every surface in `plugins/README.md` "Surfaces" (the plugin root's layout, no paths above the plugin root, no top-level `bin/`), and decide what a caller prints when it can't load or run it: fail open, never crash.
- What `session-doctor.py` trusts: only the GitHub classes with a trusted owner.

Output: a `### Design note` subsection appended under this step, short enough to paste into the PR description. Commit it as `m8.s1 design origin.py`.

### Design note

**What it is.** `plugins/personal/scripts/origin.py`, standard library only, runs on Python 3.9 (no `match`, no `X | Y` annotations). It parses; it runs nothing but one `git config --get remote.origin.url`, and never `ssh -G` or the network.

**Python interface.**
- `parse(url) -> Origin` and `read(repo_dir) -> Origin` (reads `remote.origin.url`; never raises: a missing origin or a failed git gives class `none`).
- `Origin` is a frozen dataclass: `host_class`, `host` (lowercased, `""` for local and none), `owner`, `repo` (no `.git`), `masked`, and `is_github`.
- `host_class` is one of `github` (github.com, www.github.com), `ssh443` (ssh.github.com, any port; GitHub's ssh-over-443 host), `alias` (an ssh or scp-form host matching `github.com-<x>` with no dot in `<x>`; `github.com-evil.example` is `other`, as `repo-facts.sh` has it now), `proxy` (http(s) to 127.0.0.1 or localhost whose path starts `/git/<owner>/<repo>`), `other` (anything else, IP addresses included), `local` (a path, `C:\`, `file://`), `none` (no origin).
- `is_github` is true for `github`, `ssh443`, `alias` and `proxy`. `https://github.com-x/...` is `other`: alias is an ssh-only form.
- `owner`/`repo` are the last two path segments for every class except `local` and `none`, so `secrets-facts.sh` can name a gitlab repo. GitHub-only callers gate on `is_github`, never on `owner` alone: `https://attacker.example/lolay/x.git` parses to owner `lolay`, class `other`.
- `mask(url)`, and `Origin.masked`: an http(s) URL's whole userinfo becomes `***` (a token can sit in the user part); any other scheme keeps the user and masks a password (`user:***@`). This is `repo-facts.sh` `redact_url` moved, unchanged.
- `transport` (`https`, `http`, `ssh`, `file`, `local`, `""`) rides along so `repo-facts.sh` can keep resolving an unknown ssh host with `ssh -G` for its report. That resolution stays in `repo-facts.sh` and never feeds trust.

**CLI** (for `repo-facts.sh` and `secrets-facts.sh`): `python3 -I origin.py URL` or `python3 -I origin.py --repo DIR`, exit 0, one tab-separated line `host_class<TAB>host<TAB>owner<TAB>repo<TAB>transport<TAB>masked`, `-` for an empty field (so `IFS=$'\t' read -r` doesn't collapse fields); control characters are stripped from every field. `--json` prints the same as one object, for tests and humans. Exit 2 on a usage error. The raw URL is never printed.

**How callers load it.** By a path from their own resolved file, as `review_log_facts.py` loads `review_facts.py`, but through `Path(__file__).resolve()` rather than `abspath`, because origin.py sits at the plugin root, outside the skill: a skill reached through a `~/.agents/skills` or `~/.cursor/skills` symlink must resolve back into the plugin first.
- Skill Python (`review_facts.py`, `pr_state.py`, `review_log_facts.py`): `Path(__file__).resolve().parents[3] / "scripts" / "origin.py"`, loaded with `importlib.util.spec_from_file_location`, never by `sys.path` (which `python3 -I` ignores anyway). Each carries the same five-line `load_origin()` that returns the module or `None`.
- `session-doctor.py`: `Path(__file__).resolve().parent / "origin.py"`, same loader (it runs under `python3 -I`).
- Bash (`repo-facts.sh`, `secrets-facts.sh`): `origin_py="$(cd "$(dirname "$0")" && pwd -P)/../../../scripts/origin.py"`, run as `python3 -I "$origin_py" …`.
- Surfaces: the Claude plugin cache, claude.ai sync (cloud, runners, Cowork), the Codex, Cursor and Gemini plugin installs and the Mac's symlinks all carry the whole plugin root, so the path resolves; nothing goes above the plugin root and there is no `bin/`. It does **not** resolve where a skill is copied on its own: `make install`'s Windows destinations (`copy_install_skill`, `cp -R` of one skill) and, likely, Claude chat. Those take the fail-open path below. Copying origin.py into each skill would fix that and bring back the six copies f23 removes, so this design accepts the gap and says so in the output.

**When it can't load or run: fail open, never crash, never leak.**
- `review_facts.py`: `github_repo: unknown (origin.py not found at <path>)`.
- `pr_state.py`: raises its existing `Unavailable`: `can't read origin (origin.py not found at <path>); pass --repo OWNER/REPO`.
- `review_log_facts.py`: `origin_owner` returns `""` with the same reason on stderr, so `--members` asks for `--owner` as it does for a non-GitHub origin.
- `repo-facts.sh`: `origin: not shown (origin.py unavailable at <path>)`, host and owner/name `unknown`, and the GitHub section `not read: origin.py unavailable`. It never falls back to printing the raw URL: masking fails closed.
- `secrets-facts.sh`: `remote: not shown (origin.py unavailable)`; the identity name falls back to the repo root's basename.
- `session-doctor.py`: runs no doctor and reports `not run: origin.py unavailable` per repo; the hook still exits 0. Trust fails closed, the session fails open.

**What `session-doctor.py` trusts.** `origin.is_github and is_trusted(origin.owner)`; the rest of the trust rule is unchanged. A gitlab or attacker-host origin naming a trusted owner gets `not run` with its host class and masked URL, never the raw one. The proxy and alias classes are no stronger than a github.com URL here, since the repo's author writes `.git/config` either way; f10 (doctor on runners only) is what closes that.

--- REVIEW: wave-1 [deep] ---

  Suggested chat title: Review wave 1 of 2 [deep] m8 s1

  Next model
    Cursor:      claude-opus-5-5[effort=high]
    Claude Code: /model opus                (/effort high)

  Prompt to paste into the next chat:
    Review wave 1 of 2 [deep] m8 s1
    Read specs/handoffs/plan-r1-origin-doctor-heron.md. Review the work completed in
    wave 1 (m8-s1) against its spec: read `git diff <from>` and
    `git status`, where <from> is the commit after `..` on the last
    Review log line (for the first review, `git merge-base HEAD
    origin/main`), and check it against the plan steps and
    any acceptance criteria. This is READ-ONLY -- do not fix anything
    yourself and do not start the next wave. Append one line to the
    "## Review log" section of the plan file (create the section if
    absent), with <to> from `git rev-parse --short HEAD`:
      review wave-1 (m8-s1) <from>..<to>: PASS|CONCERNS - <one-line note> - <YYYY-MM-DD>
    Append one line per model this chat ran to "## Token log",
    counted and priced per its counting header:
      tokens review-wave-1 m8-s1 (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
    If the verdict is CONCERNS, also set the Kickoff Status line to
    `BLOCKED at gate review-wave-1`, re-post the concern, and stop.
    On PASS, update the Status line `last review:` field and report back.
    On branch fix/r1-origin-helper-doctor (task branch): commit the plan update before you
    stop.

---

--- STOP: tier change [deep] -> [exec] ---

  Suggested chat title: Wave 2 of 2 [exec] m8 s2-s7

  Next model
    Cursor:      grok-4-7[effort=high,fast=false]   (or claude-sonnet-5-5[effort=high])
    Claude Code: /model sonnet              (/effort high)

  Prompt to paste into the next chat:
    Wave 2 of 2 [exec] m8 s2-s7
    Read specs/handoffs/plan-r1-origin-doctor-heron.md. Execute m8 s2-s7, following
    the s1 Design note.
    On branch fix/r1-origin-helper-doctor (task branch): commit each finished step.
    Before you stop, update plan progress: append ` (done)` to the
    headings you finished, update the Kickoff Status line, and flip the
    matching todos. Append one line per model this chat ran to the
    plan's "## Token log", counted and priced per its counting header:
      tokens wave-2 m8-s2-s7 (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
    Then stop at the next STOP marker and report what you changed and
    any deviations from the plan.

---

--- WAVE 2 [exec] ---
### s2 - [exec] Write origin.py with tests (done)

Implement `plugins/personal/scripts/origin.py` per the s1 Design note, with tests (`plugins/personal/tests/test-origin.sh`, wired into `agents/Makefile`'s `test`). Cases: https; https with a token in userinfo (masked, never printed); the proxy form; SSH aliases (`git@github.com-work:o/r.git`); `ssh://git@ssh.github.com:443/o/r.git`; gitlab (`other`); an attacker host whose path names a trusted owner (`https://attacker.example/lolay/x.git` is `other`).

### s3 - [exec] f23, f24, f3: move every origin reader onto origin.py (done)

Move onto origin.py, by the s1 Design note's loading rule: `personal-review-guide/scripts/review_facts.py` (`GITHUB_REMOTE`, about lines 100 and 242 at head), `personal-ship-pr/scripts/pr_state.py` (line 44, added by #78), `personal-codebase-review/scripts/review_log_facts.py` `origin_owner` (134), `personal-repo-baseline/scripts/repo-facts.sh` `origin_host` and `redact_url`, `personal-secrets/scripts/secrets-facts.sh` (line 36 prints the masked URL; line 114's name), and `plugins/personal/scripts/session-doctor.py` `origin_owner` (122-135), which now checks the host class too. Delete each local copy. Add the non-GitHub host cases (gitlab with a trusted owner; an attacker host) to `plugins/personal/tests/test-session-doctor.sh`, each proving the doctor doesn't run. Update each caller's existing tests where they assert origin output.

### s4 - [fast] f15: release_facts.py lists files from the repo root (done)

`plugins/personal/skills/personal-release/scripts/release_facts.py` line 35: run `git -C <root> ls-files -z` and split on NUL. Add a test that runs it from a subdirectory and finds the version files.

### s5 - [fast] f20: repo-facts.sh compiles on Python 3.9 (done)

`plugins/personal/skills/personal-repo-baseline/scripts/repo-facts.sh` line 360: compute the yes/no outside the f-string (no backslash inside an f-string expression). State the 3.9 floor in the script's header.

### s6 - [exec] f10: the session doctor runs only on runners (done)

`plugins/personal/scripts/session-doctor.py` runs a repo's doctor only on a runner (cloud or self-hosted, by the same signal `session-start.sh` uses; read it); locally it runs nothing and prints one line telling the agent to run the doctor itself, so the run goes through Claude Code's folder trust and permissions. Update its docstring, core.md "Read the doctor before trusting a build" (then `make -C agents cursor-core-rule`), makefile.md "Common tooling", and `test-session-doctor.sh` (a local case that runs nothing and prints the line; runner cases keep running it).

### s7 - [exec] f22: a doctor for this repo (done)

Add a `doctor` target to `agents/Makefile` and a root `triage.yaml`. Errors on python3 below 3.9, and on git, jq, make and claude below their floors (read each floor from what `make -C agents validate test` needs; name the source in a comment); warnings on missing sops, age and node. Follow makefile.md's `doctor` vocabulary and the triage format the session doctor already reads. Then write the seven claim files `specs/reviews/r1/f23.md`, `f24.md`, `f3.md`, `f15.md`, `f20.md`, `f10.md`, `f22.md` (Finding, Claim, Change, Evidence; Evidence names the test that proves it) and run `make -C agents validate test` until it passes.

--- REVIEW: wave-2 [deep] ---

  Suggested chat title: Review wave 2 of 2 [deep] m8 s2-s7

  Next model
    Cursor:      claude-opus-5-5[effort=high]
    Claude Code: /model opus                (/effort high)

  Prompt to paste into the next chat:
    Review wave 2 of 2 [deep] m8 s2-s7
    Read specs/handoffs/plan-r1-origin-doctor-heron.md. Review the work completed in
    wave 2 (m8-s2-s7) against its spec: read `git diff <from>` and
    `git status`, where <from> is the commit after `..` on the last
    Review log line (for the first review, `git merge-base HEAD
    origin/main`), and check it against the plan steps and
    any acceptance criteria. This is READ-ONLY -- do not fix anything
    yourself and do not start the next wave. Append one line to the
    "## Review log" section of the plan file (create the section if
    absent), with <to> from `git rev-parse --short HEAD`:
      review wave-2 (m8-s2-s7) <from>..<to>: PASS|CONCERNS - <one-line note> - <YYYY-MM-DD>
    Append one line per model this chat ran to "## Token log",
    counted and priced per its counting header:
      tokens review-wave-2 m8-s2-s7 (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv
    If the verdict is CONCERNS, also set the Kickoff Status line to
    `BLOCKED at gate review-wave-2`, re-post the concern, and stop.
    On PASS, update the Status line `last review:` field and report back.
    On PASS, this was the last wave, so also finish the plan: replace
    the Kickoff marker line with `--- KICKOFF: plan complete ---` and
    its Status line with `2/2 groups done | completed <YYYY-MM-DD>`,
    add the `actual tokens` and `actual $` columns to the Cost table
    from "## Token log" (your own lines included), and append the
    Completion summary, per plan-execution.md "Final completion".
    Then ship per the plan's "## Ship" section.
    On branch fix/r1-origin-helper-doctor (task branch): commit the plan update before you
    stop.

---

## Ship

Run `personal-ship-pr`. The PR description carries the s1 Design note, one `Fixes r1.f<K>` line per finding (f23, f24, f3, f15, f20, f10, f22) and `Part of #45`, never a closing keyword. Before it is marked ready, remove this plan from `specs/handoffs/`. When the PR opens, re-read #45's body, tick only these seven findings' boxes and append the PR link to each.

## Review log

review wave-1 (m8-s1) 4f6d337..7dec616: PASS - design note is complete and its paths check out (parents[3] and ../../../scripts reach plugins/personal/scripts through symlinked installs); the copy-install gap is acceptable given f23's one-helper decision and fail-closed masking; transport is fine as report-only. For s2-s3: read() should run `git remote get-url origin` as five of the six callers do today (config --get skips insteadOf, regressing shorthand remotes), and mask() must keep redact_url's rule exactly (any non-ssh scheme masks the whole userinfo, not only http(s)) - 2026-11-22
review wave-2 (m8-s2-s7) 7dec616..3c19132: CONCERNS - f10 is not fixed for Claude Code on the Owner's workstation: session-doctor.py's runner signal (no `# >>> personal >>>` block in ~/.claude/CLAUDE.md, copied from session-start.sh as s6 specified) is also true on a workstation in CLAUDE_MODE=plugin, agents/Makefile's default, where `make install` removes that block; so the hook still runs trusted repos' doctors there before folder trust, the one harness the walk's f10 rationale is about. The executor saw it (f10.md: "the Owner should know") yet claims `fixed` and logged no deviation; the workstation tests fake a home with the block, so they pass. Needs the Owner's call on the signal (e.g. CLAUDE_CODE_REMOTE=true for cloud plus an explicit opt-in for self-hosted runners) before a fix-up wave. Everything else checks out: origin.py matches the design note and both wave-1 asks (get-url, redact_url rule), all six callers moved with local copies gone and fail-open paths tested, f3/f24/f15/f20/f22 claims hold, validate+test pass. Nits for the fix-up: unused `import re` in pr_state.py (ruff F401) and no blank lines before FAILED there; repo-facts.sh's IPv4 glob `[0-9]*.[0-9]*.[0-9]*.[0-9]*` is looser than the old ipaddress check - 2026-11-22

## Token log

**Counting header (Claude Code)**

- Line, one per model a chat ran, appended below: `tokens <row> <group-id> (<model>): input ~X / cache read ~R / cache write ~W / output ~Y | ~$C API-equiv`. `<row>` is `wave-N`, `review-wave-N`, or `wave-N-fix` and `review-wave-N-fix` for a fix-up wave; `<group-id>` is the wave's group id with hyphens (`m8-s2-s7`); `<model>` is `message.model` without a date suffix. Round counts to two significant figures with `k` or `M`.
- Usage: `~/.claude/projects/<slug>/$CLAUDE_CODE_SESSION_ID.jsonl` (`<slug>` is the working directory with every character but a letter or digit turned into `-`, matched by prefix when long; without the id, the newest `.jsonl` there), plus its subagents' `<session-id>/subagents/**/agent-*.jsonl` in the same directory. Sum `message.usage` over assistant lines once per `message.id`, from the line with `stop_reason`: input `input_tokens`, cache read `cache_read_input_tokens`, cache write `cache_creation.ephemeral_5m_input_tokens` (with `ephemeral_1h_input_tokens` too, `cache write ~40k 5m + ~8k 1h`), output `output_tokens`. A call with no `stop_reason` line keeps its input-side counts, takes output as about 1,000, and its line ends `(output est.) session <id>`.
- Rates by `<model>`, $ per Mtok input / cached / output: `claude-opus-5-5` 4.00 / 0.20 / 20.00; `claude-sonnet-5-5` 2.00 / 0.10 / 10.00.
- `$C` = (input × in + cache read × cached + 5m write × in × 1.25 + 1h write × in × 2.00 + output × out) / 1M.
- In another harness, or on a model not listed here, count and price per plan-execution.md "Token accounting" and "Model price table" instead.
tokens kickoff plan-r1-origin-doctor-heron (claude-opus-5-5): input ~45 / cache read ~3.5M / cache write ~150k 1h / output ~15k | ~$2.2 API-equiv
tokens wave-1 m8-s1 (claude-opus-5-5): input ~35 / cache read ~2.3M / cache write ~90k 1h / output ~13k | ~$1.4 API-equiv
tokens review-wave-1 m8-s1 (claude-opus-5-5): input ~25 / cache read ~1.2M / cache write ~120k 1h / output ~7k | ~$1.3 API-equiv
tokens wave-2 m8-s2-s7 (claude-sonnet-5-5): input ~140 / cache read ~14M / cache write ~200k 1h / output ~62k | ~$2.9 API-equiv
tokens review-wave-2 m8-s2-s7 (claude-opus-5-5): input ~34 / cache read ~2.6M / cache write ~110k 1h / output ~10k | ~$1.6 API-equiv
