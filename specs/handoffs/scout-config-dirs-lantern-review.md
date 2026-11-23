The allowlist scout now reads every Claude Code config dir, not just `~/.claude`. Routed sessions run from `~/.claude-lolay` or `~/.claude-agerpoint`, so the scout was checking against a file they never read. It re-proposed commands the installer had already allowed and computed global-promotion candidates against the wrong baseline. Follows GaryRudolph/public#97 (r1.f17, which added `CLAUDE_CONFIG_DIRS`). Part of #45.

## Review guide

Review tier: [study]. The scout's env vars and JSON output change, and the fish config now exports `CLAUDE_CONFIG_DIRS`, which the installer reads when `local.mk` doesn't set it.
Blast radius: the scout's proposals and anyone who runs `make -C agents install` from a fish shell with this config. Revert is clean.
Review time: ~15 min

1. [study] [`scan.py`](https://github.com/GaryRudolph/public/compare/main...claude/upbeat-goldberg-0t3q7y#diff-f3dd3193617cf699f178a55dc31c43feb318a8a6d9298f0be32ea5f73a4bb9c1): `claude_config_dirs`, `covered_by_all`, and the new `global_allowlists.claude` shape
2. [study] [`65-aliases.apps.fish`](https://github.com/GaryRudolph/public/compare/main...claude/upbeat-goldberg-0t3q7y#diff-06669be6d957d8bd473ce8b48695d0c848f4c311eb21bcda276cd86ab27294a0): exports the list next to the routing
3. [check] [`test_render_scan.py`](https://github.com/GaryRudolph/public/compare/main...claude/upbeat-goldberg-0t3q7y#diff-1a8dc52bb8472ea43bf380a22a5fa084dcd4421662bfffe4dc0107149f7140d0): unit cases for dir resolution and intersection
4. [check] [`test-allowlist-scout.sh`](https://github.com/GaryRudolph/public/compare/main...claude/upbeat-goldberg-0t3q7y#diff-78fd2d47ecafd3fb17bef3948d314282745374339b7b2c158f8fecfff1644460): end to end, with two dirs, a repo-only command, the session dir and legacy `~/.claude`
5. [skim] [`reference.md`](https://github.com/GaryRudolph/public/compare/main...claude/upbeat-goldberg-0t3q7y#diff-cffe8a3546fa098f9bd7883c4f7c1453dab3d0afea926162ad3f37e6a5289164), [`runbook.md`](https://github.com/GaryRudolph/public/compare/main...claude/upbeat-goldberg-0t3q7y#diff-397a2ef4aea9aaf65ae3439f911db4dc92d3006528b0c0477a05f8953b941d30), [`Makefile`](https://github.com/GaryRudolph/public/compare/main...claude/upbeat-goldberg-0t3q7y#diff-f636515ed16c6c062d2e31157b8ff5e38dd1fb03ce19f1dcc0cf5c4441b9d4ee) (comment only)

## Validation

- `make -C agents validate test`: pass
- Scout tests: 23 unit tests and 4 end-to-end scenarios pass. Switching `covered_by_all` to union makes them fail.
- `CLAUDE_CONFIG_DIRS=/x:/y make -C agents help`: the Makefile picks up the exported list
- `fish -n` on the fish file: not run, because there's no fish in the runner

## Rollback

Revert the squash commit. If `local.mk` sets `CLAUDE_CONFIG_DIRS`, the installer behaves the same either way, because `local.mk` wins over the export.

## Porting

`scan.py` and the scout's tests are byte-identical with the Agerpoint bok's copy, so port them there. `agents/lib/` is untouched.

<details open>
<summary>[study] Contracts</summary>

| Input / output | Before | After |
| --- | --- | --- |
| Claude global baseline | `$CLAUDE_DATA_HOME/settings.json`, else `~/.claude` | each `<dir>/settings.json` in `$CLAUDE_CONFIG_DIRS`, else `$CLAUDE_CONFIG_DIR`, else `~/.claude` |
| Covered globally (Claude) | allowed by the one file | allowed by every dir (intersection) |
| `global_allowlists.claude` | `{path, exists, count}` | `{source, dirs: [{path, exists, count}]}` |
| `version` | `1` | `2` |

`CLAUDE_DATA_HOME` is no longer read: the installer already refuses that name. Nothing besides `scan.py` itself reads `global_allowlists`; the summary now lists the dirs and their counts.

`CLAUDE_CONFIG_DIRS` is now exported globally from fish. The Makefile's `CLAUDE_CONFIG_DIRS ?=` takes it when `local.mk` doesn't set the variable, so `local.mk` can drop its copy. Desktop sessions started from the macOS launchers don't get fish's env, so there the scout falls back to the launcher's `CLAUDE_CONFIG_DIR`.

</details>

<details>
<summary>Decisions</summary>

- Intersection, not union. The installer writes the same allowlist into every dir, so dirs differ only by hand edits and "always allow" saves. Union would count a command covered even when one dir lacks it, so sessions under that dir would still prompt. Intersection re-proposes it to the repo file, which applies under every dir.
- Per-repo dir routing (which dir governs a repo) was ruled out because it would copy the dotfiles routing into a plugin that runs from any workspace.
- The list comes from the environment. A Makefile print target was ruled out because the plugin can't find this checkout from another workspace. Discovering `~/.claude*` was ruled out because stale dirs would count.
- `CLAUDE_DATA_HOME` was dropped rather than kept as a fallback, per the Owner.

</details>

https://claude.ai/code/session_01BNKwNZGaMUxyLpofZLo1Xe

Assisted-by: Claude Code
