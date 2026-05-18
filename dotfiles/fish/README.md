# fish dotfiles

Public Fish shell config. Mirrors the standard `~/.config/fish/` layout and is
designed to be symlinked into place. Optional companion: a private repo with
matching layout.

## Layout

```text
dotfiles/fish/
  config.fish          # entry; sources host/<hn>.fish then ~/.config/fish-private/config.fish
  conf.d/              # auto-loaded by fish, lexical order
    00-umask.fish
    10-session.fish    # SESSION_TYPE, SSH_TUNNEL (used by ssh function in 60-aliases)
    20-env.fish        # EDITOR, VISUAL, TABSTOP, SHELL_INTERPRETER
    30-path-and-tools.fish
    40-integrations.fish   # brew shellenv, java, gradle, maven, android, gcloud, vscode, rust, pnpm
    50-aliases.docker.fish
    60-aliases.fish    # ls/dir/l (uname-aware), ssh wrapper, git, macOS shortcuts
    70-history.fish    # placeholder for HISTORY_IGNORE-style scrub
  functions/
    fish_prompt.fish           # 3 lines: spacer → [time user@host:pwd] → (ctx?) [hist] >
    fish_title.fish            # window title: argv when running, user@host:pwd (ctx?) [hist] when idle
    _fish_prompt_context.fish  # user@host:pwd, shared by prompt and title
    _fish_histnum.fish         # best-effort approximation of zsh %!
    xman.fish                  # `xman ls` → opens man page in macOS viewer
  host/
    gMacBook.fish      # example; loaded when `hostname -s` matches the basename
  README.md            # this file
```

## Setup

Symlink the directory into place:

```sh
ln -snf "$HOME/Projects/personal/public/dotfiles/fish" "$HOME/.config/fish"
```

Optional private layer (see [Private layer](#private-layer)):

```sh
ln -snf "$HOME/Projects/personal/private/dotfiles/fish" "$HOME/.config/fish-private"
```

Open a new fish session — that's it.

## Load order

1. `conf.d/*.fish` — auto-loaded by fish, lexical order.
2. `config.fish` runs after `conf.d/`:
   1. **`host/<hostname -s>.fish`** if it exists — per-machine settings and
      machine-only overrides.
   2. **`$__fish_config_dir/../fish-private/config.fish`** if it exists — the
      private repo's own entry (which then iterates its own `conf.d/` and
      registers its `functions/` + `completions/`). Default install path is
      `~/.config/fish-private`, but the lookup is sibling-relative so any
      `XDG_CONFIG_HOME` works.

There is no separate `fish-local.fish` layer. The host file plays that role —
gitignore the file if you want it untracked on a given machine.

## Per-machine config (host file)

Files in `host/` are loaded by name:

```fish
# config.fish (excerpt)
set -l _host (command hostname -s 2>/dev/null)
set -l _hostfile "$__fish_config_dir/host/$_host.fish"
test -f "$_hostfile"; and source "$_hostfile"
```

To find the right name, run `hostname -s`. Add `host/<that>.fish` and put
machine-specific PATH adjustments, env vars, or overrides there.

If your hostname changes (VPN, VM, cloud), the simplest fix is a small
`host/<newname>.fish` that sources the canonical one:

```fish
source $__fish_config_dir/host/gMacBook.fish
```

## Private layer

The companion private repo (`~/Projects/personal/private`) holds secrets, API
keys, and other things that shouldn't live in this public repo. Its
`dotfiles/fish/` directory mirrors this layout (`config.fish`, `conf.d/`,
`functions/`, `completions/`) so the mental model is identical.

Symlink the **whole** private fish directory into `~/.config/fish-private`
(not into the public symlink tree):

```sh
ln -snf "$HOME/Projects/personal/private/dotfiles/fish" "$HOME/.config/fish-private"
```

Inside the private repo, `dotfiles/fish/config.fish` does the wiring fish
won't do automatically (since it only auto-loads from `~/.config/fish/`):

```fish
set -l _dir (dirname (status filename))
for f in $_dir/conf.d/*.fish
    source $f
end
set -p fish_function_path "$_dir/functions"
set -p fish_complete_path "$_dir/completions"
```

If the symlink isn't present, the public `config.fish` notices and skips —
nothing breaks.

## `loadenv <name>` — on-demand env files

Some private dotenv files (Optimal backend env, Fastlane `.env.default` files,
etc.) shouldn't be exported into every interactive shell — that would leak
secrets like `MATCH_PASSWORD`, `AUTH0_*`, `FIREBASE_CLI_TOKEN` into every
child process.

The private repo provides a `loadenv <name>` function (with tab completion)
that sources one of those files into the **current shell only**:

```sh
loadenv optimal                 # sets SKYBOX_*, FASTIFY_*, POSTGRES_*, AUTH0_*
loadenv flipseats-ios           # Fastlane iOS env
loadenv flipseats-android
loadenv flipseats-certificates
```

Open a fresh shell and the vars are gone — load again as needed.

The function lives in `private/dotfiles/fish/functions/loadenv.fish`; tab
completion in `completions/loadenv.fish`. Both are made discoverable by the
private `config.fish` extending `fish_function_path` and `fish_complete_path`.

### `unloadenv <name>` — undo a `loadenv`

`loadenv` records the keys it set in a per-load tracking variable. `unloadenv`
reads that tracking variable and `set -e`s each key, so you only ever unset
the vars this particular load contributed (other env stays untouched):

```sh
loadenv optimal       # sets SKYBOX_*, FASTIFY_*, POSTGRES_*, AUTH0_*
unloadenv optimal     # clears exactly the vars `loadenv optimal` set
```

The per-context auto-switcher uses this internally to flip env state on `cd`,
but `unloadenv` is also useful by hand when you want a clean shell without
opening a new one.

### Caveats

- **`${VAR}` interpolation** in dotenv values (e.g.
  `SCAN_SCHEME=${SCHEME}` in Fastlane files) is **not** expanded by `loadenv`.
  The tools that consume those files (Fastlane via `--env`,
  `docker-compose --env-file`) handle their own interpolation.
- `set -gx` is per-session: closing the shell drops the vars. Different
  shell windows are independent.

## Per-context auto-switching

The five "worlds" you live in are derived from your `~/Projects/` layout:

| Tree                       | Context     |
| -------------------------- | ----------- |
| anywhere else              | `personal`  |
| `~/Projects/lolay/`        | `lolay`     |
| `~/Projects/agerpoint/`    | `agerpoint` |
| `~/Projects/nowline/`      | `nowline`   |
| `~/Projects/deskhound/`    | `deskhound` |

Whenever `PWD` changes, a fish event handler computes the new context, undoes
whatever the previous context applied (markers + loadenvs), then applies the
new one. The active name lives in `$__active_context` and shows up in the
prompt and window title for any non-personal context.

Mechanism (public side, [`conf.d/80-context.fish`](conf.d/80-context.fish)):

- `_context_from_path <p>` — directory → context name
- `context_register <name> --markers K=v ... --loadenv name1 ...` — registry helper
- `_context_apply` / `_context_unapply` — flip env state for a context
- `__context_on_pwd_changed` — `--on-variable PWD` handler that drives it all
- `__context_init_active` — one-shot init called by the registry after declarations
- [`functions/context.fish`](functions/context.fish) — `context` CLI:
  `context [current|show <name>|reload|list]`
- [`functions/_context_from_argv.fish`](functions/_context_from_argv.fish) —
  shared helper used by the smart `cursor` / `code` / `claude` wrappers below

Registry (private side, `fish-private/conf.d/context-registry.fish`) declares
what each context wants. Each `context_register` call takes two kinds of values:

- **`--markers`** — non-secret env vars that say "you're in `<ctx>`":
  `CLOUDSDK_CONFIG`, `AWS_PROFILE`, `CLAUDE_CONFIG_DIR`, ... Set automatically
  on cd; unset when you leave.
- **`--loadenv`** — short names of private dotenv files to source (see the
  `loadenv` registry above). Files live at
  `~/Projects/personal/private/dotfiles/<ctx>/<thing>.env` and short names
  follow `<thing>-<context>` (`firebase-nowline`, `gcp-agerpoint`, `aws-lolay`).

### One-time per-context bootstrapping

- **gcloud**: run once per context with the right `CLOUDSDK_CONFIG`:
  ```sh
  env CLOUDSDK_CONFIG=$HOME/.config/gcloud-agerpoint  gcloud auth login
  env CLOUDSDK_CONFIG=$HOME/.config/gcloud-nowline    gcloud auth login
  env CLOUDSDK_CONFIG=$HOME/.config/gcloud-deskhound  gcloud auth login
  ```
- **Firebase**: in each context's Firebase account, run `firebase login:ci`,
  copy the printed token into `~/Projects/personal/private/dotfiles/<ctx>/firebase.env`
  as `export FIREBASE_TOKEN=...`, then `context reload` (or open a new shell).
- **AWS**: add one `[profile <ctx>]` stanza per context to `~/.aws/credentials`.

## Smart `cursor` / `code` / `claude`

Bare `cursor .` / `code .` / `claude .` are path-aware wrappers (see
[`conf.d/65-aliases.apps.fish`](conf.d/65-aliases.apps.fish)). They derive a
context from the first path-like argument — or pwd if none — via
`_context_from_argv`, and route:

- **agerpoint** → `Cursor AP.app` / `Visual Studio Code AP.app` / `~/.claude-agerpoint`
- **everything else** → the bare `cursor` / `code` / `claude` (personal account)

This means `cd ~/Projects/agerpoint/bok && cursor .` opens the agerpoint
Cursor, and `cursor ~/Projects/agerpoint/bok` from anywhere does the same.
Personal, lolay, nowline, and deskhound all share the personal Cursor/Claude
because that's where you live most of the time.

The explicit `cursor-agerpoint` / `code-agerpoint` / `claude-agerpoint`
functions stay around for when you want to force agerpoint from outside its
tree without typing the path.

## Notes on the port

This config is the fish translation of `dotfiles/zshrc`. Notable choices:

- **Prompt** is three lines (underlined spacer / `[HH:MM:SS user@host:pwd]` /
  `(ctx?) [n] >`) — same spirit as the zsh `PS1` but built around
  `string repeat`, `set_color`, `prompt_pwd`, and a best-effort
  `_fish_histnum` (fish has no exact `%!`). The active project context (when
  non-personal) renders as a venv-style `(ctx)` left prefix on the input line.
- **Window title** is handled by `fish_title`, replacing the zsh
  `precmd`/`preexec` xterm escapes.
- **PATH** uses `fish_add_path -gP …` (auto-dedupes; replaces
  `typeset -U path`).
- **Tool integrations** use the `.fish` snippet that each tool ships when
  available (`brew shellenv fish | source`, `cargo`'s `env.fish`, gcloud
  `path.fish.inc` and `completion.fish.inc`).
- **Aliases** that shadow built-ins or binaries (`ls`, `dir`, `l`, `ssh`,
  `pwd`) are written as functions calling `command …` to avoid recursion.

Things intentionally not ported:

- `IGNOREEOF` (no fish equivalent).
- The dead, commented `precmd`/`preexec` title blocks.
- The `~/.exrc` bootstrap (already exists in `dotfiles/exrc`).
