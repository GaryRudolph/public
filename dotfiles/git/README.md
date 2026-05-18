# Per-context git identity

Personal is the default. Anything inside one of the four work trees under
`~/Projects/` (`lolay/`, `agerpoint/`, `nowline/`, `deskhound/`) overrides
the commit email to the matching company address. SSH still uses the one
shared `~/.ssh/id_ed25519` today; the scaffolding to split keys per context
is in place but dormant.

## How it works

Three pieces:

1. **Base config** — [`../gitconfig`](../gitconfig) (symlinked to `~/.gitconfig`)
   carries the personal identity and the `[includeIf "gitdir:..."]` blocks
   that route per directory.

2. **Per-context fragments** — `lolay.gitconfig`, `agerpoint.gitconfig`,
   `nowline.gitconfig`, `deskhound.gitconfig` in this directory each set
   only `user.email`. Symlinked into `~/.config/git/` by the dotfiles
   `Makefile`.

3. **SSH `Host` aliases** — [`~/.ssh/config`](file://$HOME/.ssh/config) has
   `github.com-lolay` and `github.com-agerpoint` aliases pointing at the
   shared key. They're harmless until a fragment opts in via `insteadOf`
   (see "Future split" below).

```
~/.gitconfig
  ├── [user] email = GaryRudolph@mac.com           # personal default
  └── [includeIf "gitdir:~/Projects/<ctx>/"]
        path = ~/.config/git/<ctx>.gitconfig       # overrides email per tree
```

| Tree                       | Email                       |
| -------------------------- | --------------------------- |
| anywhere else              | `GaryRudolph@mac.com`       |
| `~/Projects/lolay/`        | `gary@lolay.com`            |
| `~/Projects/agerpoint/`    | `grudolph@agerpoint.com`    |
| `~/Projects/nowline/`      | `gary@nowline.io`           |
| `~/Projects/deskhound/`    | `gary@deskhound.ai`         |

`includeIf "gitdir:"` matches once a repo's `.git` exists, so this only fires
in actual git repos under those trees — `cd ~/Projects/agerpoint` (the parent
dir itself) keeps the personal identity. Run `git config --show-origin
user.email` inside a repo to see which fragment is in effect.

## Install

```sh
cd ~/Projects/personal/public/dotfiles
make link-git
```

Idempotent. Creates `~/.config/git/` if missing and `ln -snf`s each
`dotfiles/git/*.gitconfig` into it. Re-run after pulling in a new fragment
or renaming one.

## Existing repos: nothing to update

No `.git/config` edits anywhere. `includeIf` overrides take effect on the
next `git` invocation inside a matched tree — every repo keeps its existing
`origin` URL and its existing local config. If a repo's `.git/config`
happens to have a stale `[user] email = ...` from before this setup, that
local value still wins (git's normal precedence); delete the local override
to fall back to the includeIf'd one.

## Future split: per-context SSH key

When any single context wants to stop sharing the personal key:

1. Generate the new key:
   ```sh
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_<ctx>
   ```
   Add the public key to that context's GitHub account.

2. Split the matching `Host github.com-<ctx>` stanza in `~/.ssh/config` so
   it points at the new `IdentityFile`.

3. Add `insteadOf` to that context's fragment in this directory:
   ```gitconfig
   [url "git@github.com-<ctx>:"]
       insteadOf = git@github.com:
   ```

That's it. `insteadOf` is a transparent URL rewrite — every existing repo
keeps its canonical `git@github.com:org/repo.git` remote and git routes
through the alias automatically. Personal stays on plain `github.com` (no
alias needed).

**One clone-time caveat** that only matters once `insteadOf` is active:
`includeIf` doesn't fire until a repo's `.git` exists, so a fresh
`git clone git@github.com:org/repo.git` from inside the relevant tree won't
be rewritten for that one command. For that single operation, clone with
the alias:

```sh
git clone git@github.com-<ctx>:org/repo.git
```

Every subsequent `pull`/`push`/`fetch` picks up `includeIf` and routes
correctly.
