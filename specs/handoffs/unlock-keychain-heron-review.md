Adds an `unlock-keychain` alias to the fish and zsh configs. Over ssh the login keychain stays locked, so `codesign` and anything else that needs a cert or password from it fails. The alias runs `security unlock-keychain` on `~/Library/Keychains/login.keychain-db` and prompts for the login password. The path is explicit because the default keychain can resolve differently in an ssh session.

## Review guide

Review tier: [skim], because it's one new interactive alias per shell and nothing else changes.
Blast radius: interactive shells on Gary's Macs only; a revert is safe.
Review time: ~1 min

1. [skim] `dotfiles/fish/conf.d/60-aliases.fish`: alias in the macOS shortcuts section
2. [skim] `dotfiles/zshrc`: the same alias, next to `flushdns`

## Validation

- `zsh -n dotfiles/zshrc`: pass
- `fish --no-execute dotfiles/fish/conf.d/60-aliases.fish`: pass; sourcing it defines `unlock-keychain` with the expected body
- Running it against a real keychain: not run, the runner is Linux

## Rollback

Revert the squash commit.

<details>
<summary>Decisions</summary>

- Left out `security set-keychain-settings` (disables auto-lock): it's a lasting change to the keychain, not an unlock.

</details>
