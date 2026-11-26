Routes the nowline repos that live under `~/Projects/lolay/` (`nowline*`, including `nowline-commercial*`) to the nowline context, the same as `~/Projects/nowline/*`: the fish context switcher gives them nowline's markers and loadenvs (gcloud, ADC, Firebase, AWS), and git commits there as `gary@nowline.io` instead of `gary@lolay.com`.

## Review guide

Review tier: [check], because the fish path matcher's comparison changed for every entry, and git identity changes for repos under `lolay/nowline*`.
Blast radius: the Owner's own shells and commits on machines that pull these dotfiles; a revert restores lolay routing on the next `context reload` and the next commit.
Review time: ~6 min

1. [check] [`dotfiles/fish/conf.d/80-context.fish`](LINK/#diff-20cf9c89e2d1ac341a30a91f068c364f6ea5cd3629677ac87b1ac5b06453ceb2): path map takes fish globs; `lolay/nowline*` entry above `lolay`
2. [check] [`dotfiles/gitconfig`](LINK/#diff-f7ec7ddf029023eb1ca23c1c458239cc9fe53e25923c4f48462b8d95a8f0ac14): second nowline `includeIf`, after lolay's so it wins
3. [skim] [`dotfiles/git/nowline.gitconfig`](LINK/#diff-afb3622870544fc6abccd2607da1d6e2c526c5c8167b9685779ca1443a48a253): header comment
4. [skim] [`dotfiles/fish/README.md`](LINK/#diff-a435f8cd45195343642412b0c74037517ff2f728d35412ae8addfdf2ec350ee7), [`dotfiles/git/README.md`](LINK/#diff-9a44c7363a38206a8274806ff28caf1b1b17ce8703d7754e2bda7f644e9bb703): table rows

## Validation

- `_context_from_path` under fish 3.7 with `HOME=/Users/g`: `lolay/nowline`, `lolay/nowline-commercial`, `lolay/nowline-commercial/web/src`, `lolay/nowline-core/x` give `nowline`; `lolay`, `lolay/bok`, `lolay/other/nowline-x` give `lolay`; `nowline`, `nowline/core` give `nowline`; `agerpoint/bok` gives `agerpoint`; `nowliner`, `personal/public`, `/tmp` give `personal`
- `git config user.email` in fresh `git init` repos under a throwaway `HOME` with this gitconfig: `lolay/nowline`, `lolay/nowline-commercial` (and its `web/` subfolder), `lolay/nowline-core` give `gary@nowline.io`; `lolay/bok`, `lolay/other/nowline-x` give `gary@lolay.com`; `nowline/core` gives `gary@nowline.io`
- `make -C agents validate test`: not run, nothing under `plugins/` or `agents/` changed
- On a Mac: not run; takes effect after pulling, then `context reload` for fish

## Rollback

Revert the squash commit, then `context reload` in open shells. Commits already made in `lolay/nowline*` repos keep the nowline email.

<details>
<summary>[check] Matching</summary>

| Piece | Before | After |
| --- | --- | --- |
| fish exact match | `test "$abs" = "$prefix"` | `string match -q -- "$prefix" "$abs"` (glob) |
| fish subtree | `string match -q "$prefix/*"` | unchanged, now with a glob prefix |
| `lolay/nowline*` context | `lolay` | `nowline` |
| `lolay/nowline*` email | `gary@lolay.com` | `gary@nowline.io` |

fish's `*` crosses `/`, so `lolay/nowline*` also matches deeper paths under any `nowline*` folder; git's `gitdir:` `*` doesn't cross `/`, and the trailing `/` covers the subtree. Both only match a `nowline*` folder directly under `lolay/`.

</details>

<details>
<summary>Decisions</summary>

- Git identity follows the shell: the Owner chose `gary@nowline.io` for these repos even though they sit in the lolay org.
- A glob entry rather than one entry per repo, so a new `lolay/nowline-*` clone routes without an edit.

</details>

https://claude.ai/code/session_01BNKwNa49X4xcPSghu7v5YR

Assisted-by: Claude Code
