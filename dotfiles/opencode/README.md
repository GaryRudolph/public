# OpenCode dotfiles

Multi-profile OpenCode config mirroring the Cursor / Claude Code setup in
[`dotfiles/fish/conf.d/65-aliases.apps.fish`](../fish/conf.d/65-aliases.apps.fish).

**Rollback:** if you decide not to use OpenCode, see [Rollback](#rollback) below.

## Layout

| Source (this repo) | Symlink target |
| ------------------ | -------------- |
| `personal.json` | `~/.config/opencode/opencode.json` |
| `agerpoint.json` | `~/.config/opencode-agerpoint/opencode.json` |

OpenCode always reads `opencode.json` inside each profile's config directory.
Only the repo-side filenames use the flat `personal.json` / `agerpoint.json`
shape (same idea as `dotfiles/git/agerpoint.gitconfig`).

## Profile routing

| Context | Profile |
| ------- | ------- |
| `agerpoint` | `OPENCODE_APPNAME=opencode-agerpoint` |
| personal, lolay, nowline, deskhound | default (no marker) |

Inside `~/Projects/agerpoint/`, the fish context switcher sets
`OPENCODE_APPNAME` automatically. The bare `opencode` wrapper routes by path
when launched from outside the tree (see [`dotfiles/fish/README.md`](../fish/README.md)).

Without the CLI installed, bare `opencode` launches the desktop app via
`open -a OpenCode`.

## Install

```sh
cd ~/Projects/personal/public/dotfiles
make link-opencode
```

Or `make install` (includes git, ghostty, and opencode links).

## One-time auth (per machine)

Credentials live in runtime data dirs — never symlinked or committed:

- Personal: `~/.local/share/opencode/auth.json`
- Agerpoint: `~/.local/share/opencode-agerpoint/auth.json`

After linking configs, authenticate once per profile:

```sh
opencode auth login
OPENCODE_APPNAME=opencode-agerpoint opencode auth login
```

OAuth (Claude Pro/Max login) is recommended for daily use. Re-run on a new
machine the same way you re-login Claude Code or Cursor.

## Optional API key fallback

To use a pay-as-you-go API key instead of (or in addition to) OAuth, add to
the relevant JSON file:

```json
{
  "provider": {
    "anthropic": {
      "options": {
        "apiKey": "{file:~/Projects/personal/private/dotfiles/agerpoint/anthropic-key}"
      }
    }
  }
}
```

If both OAuth and an API key are configured, OpenCode tends to prefer the
API key — omit `apiKey` unless you intentionally want pay-as-you-go billing.

## What not to symlink

- `~/.local/share/opencode/` — auth, sessions, logs (machine-local)
- `~/.local/share/opencode-agerpoint/` — same for agerpoint profile
- `~/.cache/opencode*` — caches and provider packages

Session history under `project/` stays on each machine by design.

## Rollback

Use this section to undo the OpenCode dotfiles integration. Nothing here touches
Cursor, Claude Code, or your other context markers (AWS, gcloud, etc.) except
removing `OPENCODE_APPNAME` from the agerpoint registry.

### Change inventory (for agents)

**Rollback commits** (one per repo — revert these to undo all OpenCode dotfiles work):

| Repo | Commit | Message |
| ---- | ------ | ------- |
| `~/Projects/personal/public` | [`63cc521`](https://github.com/GaryRudolph/public/commit/63cc521) | `feat(dotfiles): add OpenCode multi-profile setup` |
| `~/Projects/personal/private` | [`837956a`](https://github.com/GaryRudolph/private/commit/837956a) | `feat(fish): set OPENCODE_APPNAME for agerpoint context` |

Parent before OpenCode (if you need pre-change baselines): public `3c97e60`, private `24c727b`.

#### Public repo — `~/Projects/personal/public` (`63cc521`)

| Path | Status | Notes |
| ---- | ------ | ----- |
| `dotfiles/opencode/personal.json` | **added** | minimal `$schema` only |
| `dotfiles/opencode/agerpoint.json` | **added** | minimal `$schema` only |
| `dotfiles/opencode/README.md` | **added** | install + this rollback doc |
| `dotfiles/Makefile` | **modified** | `link-opencode` target; wired into `install` |
| `dotfiles/fish/conf.d/65-aliases.apps.fish` | **modified** | `_opencode_launch_desktop`, `opencode` function |
| `dotfiles/fish/README.md` | **modified** | OpenCode routing paragraph |
| `setup/mac.md` | **modified** | OpenCode install bullets |

#### Private repo — `~/Projects/personal/private` (`837956a`)

| Path | Status | Notes |
| ---- | ------ | ----- |
| `dotfiles/fish/conf.d/context-registry.fish` | **modified** | `OPENCODE_APPNAME=opencode-agerpoint` on agerpoint |

#### Machine-local only (not in git)

| Path | Created by |
| ---- | ---------- |
| `~/.config/opencode/opencode.json` | `make link-opencode` → `personal.json` |
| `~/.config/opencode-agerpoint/opencode.json` | `make link-opencode` → `agerpoint.json` |
| `~/.local/share/opencode/` | OpenCode auth/sessions (optional delete) |
| `~/.local/share/opencode-agerpoint/` | same for agerpoint profile |
| `~/.cache/opencode*` | caches |
| `/Applications/OpenCode.app` | manual install (optional delete) |

#### Agent handoff (copy-paste)

```text
Roll back the OpenCode dotfiles integration.

Repos (one revert each):
  cd ~/Projects/personal/public && git revert 63cc521
  cd ~/Projects/personal/private && git revert 837956a

Machine:
  rm -f ~/.config/opencode/opencode.json ~/.config/opencode-agerpoint/opencode.json
  rmdir ~/.config/opencode ~/.config/opencode-agerpoint 2>/dev/null || true
  context reload   # or new fish tab

Do NOT touch cursor/claude/code wrappers or other context markers (AWS, gcloud, etc.).
Optional: remove ~/.local/share/opencode*, ~/.cache/opencode*, OpenCode.app.

Full instructions: ~/Projects/personal/public/dotfiles/opencode/README.md#rollback
Commits: public 63cc521, private 837956a
```

Or inspect what those commits changed:

```sh
git -C ~/Projects/personal/public show 63cc521 --stat
git -C ~/Projects/personal/private show 837956a --stat
```

### Option A — Stop using OpenCode on this machine (keep repo files)

Reversible. Dotfiles stay in git; you only detach the machine.

**1. Remove config symlinks**

```sh
rm -f ~/.config/opencode/opencode.json
rm -f ~/.config/opencode-agerpoint/opencode.json
rmdir ~/.config/opencode ~/.config/opencode-agerpoint 2>/dev/null || true
```

**2. Disable the fish wrapper** (pick one)

- Open a shell where `type opencode` shows the real binary/ nothing, not the
  function — e.g. temporarily `functions -e opencode` in the current session, or
- Revert `65-aliases.apps.fish` from git (Option B step 2) while keeping the
  rest of the repo.

**3. Remove agerpoint context marker** (private repo)

Edit `~/Projects/personal/private/dotfiles/fish/conf.d/context-registry.fish`
and delete the `OPENCODE_APPNAME=opencode-agerpoint \` line (and trim the
OpenCode mention in the header comment if you like). Then:

```sh
context reload   # or open a new fish tab
```

**4. Optional — remove OpenCode app and runtime data**

```sh
# Quit OpenCode first (Cmd+Q)
rm -rf ~/.local/share/opencode ~/.local/share/opencode-agerpoint
rm -rf ~/.cache/opencode ~/.cache/opencode-agerpoint
rm -rf ~/Library/Application\ Support/ai.opencode.desktop   # desktop app state
# rm -rf /Applications/OpenCode.app                          # if you installed the .app
# brew uninstall opencode                                    # if you installed the CLI
```

**5. Verify**

```sh
type opencode          # should NOT be a fish function (or command not found)
context show agerpoint # should not list OPENCODE_APPNAME
ls ~/.config/opencode* 2>/dev/null || echo "config symlinks gone"
```

Cursor, Claude, and VS Code wrappers are unchanged.

### Option B — Remove OpenCode from the dotfiles repos (full rollback)

Do Option A first, then revert repo changes (see [Change inventory](#change-inventory-for-agents)).

**Public repo** (`~/Projects/personal/public`):

```sh
cd ~/Projects/personal/public
git revert 63cc521
```

**Private repo** (`~/Projects/personal/private`):

```sh
cd ~/Projects/personal/private
git revert 837956a
```

Open a new fish tab after reverting `65-aliases.apps.fish`.

### Option C — Keep configs, drop fish integration only

If you might return to OpenCode later but want `opencode` out of fish:

1. Option A steps 2–3 only (leave symlinks and JSON files in place).
2. Launch OpenCode from Spotlight or `open -a OpenCode` manually.

### After rollback

- No `make install` change needed unless you removed `link-opencode` from the
  Makefile (Option B); otherwise future `make install` will re-link OpenCode
  configs until you revert the Makefile too.
- OpenCode is **not** part of [`agents/`](../../agents/README.md); no `make
  uninstall` there.
- To try again later: `make link-opencode`, restore fish/registry changes from
  git, `context reload`, auth per [One-time auth](#one-time-auth-per-machine).
