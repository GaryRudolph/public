Adds a `ussander` context at the same scope as agerpoint: `~/Projects/ussander/` routes to its own Claude config (`~/.claude-ussander`), Claude US and Visual Studio Code US launchers, an OpenCode profile, a git identity (`garyjr@ussander.com`), and the gcloud bootstrap loop. It also drops the Cursor launcher wrappers for every profile, so bare `cursor` is always the personal Cursor.

## Review guide

Review tier: [check] [security], because the shell routing for `claude`/`code`/`cursor`/`opencode` changes and session-doctor trusts a new GitHub owner.
Blast radius: Gary's Mac shells and launchers only. Agerpoint loses `Cursor AP.app`. A revert restores everything except the hand-deleted app.
Review time: ~10 min

1. [check] [`dotfiles/fish/conf.d/65-aliases.apps.fish`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-06669be6d957d8bd473ce8b48695d0c848f4c311eb21bcda276cd86ab27294a0): ussander arms, `cursor` unrouted, `CLAUDE_CONFIG_DIRS` += ussander
2. [check] [`dotfiles/fish/conf.d/80-context.fish`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-20cf9c89e2d1ac341a30a91f068c364f6ea5cd3629677ac87b1ac5b06453ceb2): path-map entry
3. [check] [security] [`plugins/personal/scripts/session-doctor.py`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-f9c53e03a9110c9dfd0f5b89580f8d21749440d4472b25fa9085d2ebdc7bc12f), [`plugins/personal/tests/test-session-doctor.sh`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-b0a9a38c3fc03b6eeb3da38791563b2c50e6470f3f7f92bad9d116215127da15): `us-sander` joins the owners whose `make doctor` runs at session start
4. [check] [`macos-launchers/Makefile`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-aaf2bc9c60568ab075cb9e535370390c5a614f71a82cd15bd81616bd578e3e99), [`macos-launchers/profiles/ussander.env`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-f3189731f9d0b634d45a4c8eb864e3c6b265283be58548380db1c2fa158838b8), [`macos-launchers/profiles/agerpoint.env`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-eac99ed967a4e444017867ef8882369ab89e762f981a4315dffce3219bd03cea), [`macos-launchers/apps/cursor.applescript`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-4a2feeef7f77aacc474cde182771a1b3fae9891487754a6441eaf62ff7aa3576), [`macos-launchers/apps/cursor.env`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-a80c2bb9bd648991633122dbda06a6c9261729e0b2be8b0af6364827f62b2e32): Cursor app and `__CURSOR_BIN__` token gone
5. [skim] [`dotfiles/zshrc`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-90e9c37a521826c59098df638b3b8191c58839b94425a2c7ff2ba240c0c97642), [`dotfiles/gitconfig`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-f7ec7ddf029023eb1ca23c1c458239cc9fe53e25923c4f48462b8d95a8f0ac14), [`dotfiles/git/ussander.gitconfig`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-6c904ca9addce28dcb50bea43f6bb865fdd13766cf42d78ce869e471e56f97cf), [`dotfiles/Makefile`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-1aa39e2dc10c64b39a57656b893d718af5206ee29a47e872bd85dc1dff9df620), [`dotfiles/opencode/ussander.json`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-218da2be2a6d259525a0ddb6c98bea5a8a6d7536a1f643fc55dae418beabdf4e), [`agents/Makefile`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-f636515ed16c6c062d2e31157b8ff5e38dd1fb03ce19f1dcc0cf5c4441b9d4ee)
6. [skim] [`macos-launchers/README.md`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-6144954a82962616ab0d02f2d30ea3246c989a6bdb50c0f8e2717e11b003380a), [`dotfiles/fish/README.md`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-a435f8cd45195343642412b0c74037517ff2f728d35412ae8addfdf2ec350ee7), [`dotfiles/git/README.md`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-9a44c7363a38206a8274806ff28caf1b1b17ce8703d7754e2bda7f644e9bb703), [`dotfiles/opencode/README.md`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-868ad28f19d13dcc40d264d059aa28725762ae2e2850f0df333f53a3e284edb5), [`setup/mac/README.md`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-2189f97fb90328512efbc2cce7096f773cd86f882443ffa73f02e94f907bb3aa)
7. [skip] [`macos-launchers/profiles/ussander.png`](https://github.com/GaryRudolph/public/compare/main...claude/focused-hawking-0xjtuf#diff-f40bbd956931ceb4606fa785d13414118c7d247b2405d9656771bba48c4c675c) (ImageMagick placeholder badge)

## Validation

- `make -C agents validate test`: pass (new `us-sander` session-doctor case included)
- `fish -n` on both edited `conf.d` files: pass
- fish routing smoke with a fake `HOME`: `_context_from_path` maps ussander/agerpoint/nowline/elsewhere correctly; `claude <path>` picks `.claude-ussander`, `.claude-agerpoint`, `.claude-lolay`
- `make -C macos-launchers validate-profiles`: pass
- `make -C macos-launchers validate-templates`/`install`: not run, needs macOS (`osacompile`)
- `zsh -n dotfiles/zshrc`: not run, no zsh on the runner

## Rollback

Revert the squash commit, then `make -C macos-launchers install PROFILE=agerpoint` to rebuild `Cursor AP.app`.

<details>
<summary>[check] Routing</summary>

| Command | Before | After |
| --- | --- | --- |
| `claude` | agerpoint, else lolay | agerpoint, ussander, else lolay |
| `code` | AP app, else personal | AP or US app, else personal |
| `cursor` | `Cursor AP`, else personal | always personal |
| `opencode` | agerpoint profile, else default | agerpoint or ussander profile, else default |

</details>

<details>
<summary>Decisions</summary>

- Deleted `apps/cursor.*` instead of leaving it unused: `make check` would still demand `/Applications/Cursor.app`.
- gcloud, `CLAUDE_CONFIG_DIR` and `OPENCODE_APPNAME` markers for ussander belong in the private `context-registry.fish`, not here.

</details>

Claude-Session: https://claude.ai/code/session_01BNKwNbSANM9YvuA4kydBHi

Assisted-by: Claude Code
