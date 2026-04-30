# macos-launchers

Some apps (Cursor, Claude Desktop, VS Code) tie a single login to a single license, but you may need to run them under more than one account — personal and work, for example. The fix is to launch the same app twice with different `--user-data-dir` paths so each instance keeps its own login, settings, and data; this directory builds branded `.app` wrappers that do exactly that, with a small badge composited onto the icon so you can tell the instances apart in the Dock and Spotlight.

---

## Part 1: Using it

### What this gives you

Up to three extra apps per profile (declared in the profile's `APPS=` list):

- `Cursor <LABEL>.app` — launches Cursor into a fully isolated profile (separate accounts, settings, extensions, indexes).
- `Claude <LABEL>.app` — launches Claude Desktop into a fully isolated profile.
- `Visual Studio Code <LABEL>.app` — launches VS Code into a fully isolated profile.

All are branded with your overlay so they're distinct in the Dock and Spotlight. Personal Cursor, Claude Desktop, and VS Code are unchanged — bare `cursor`, the normal Claude Desktop launch, and bare `code` keep their existing profile.

### Prereqs

- macOS.
- Each app's `SRC` bundle from `apps/*.env` installed (today: `/Applications/Cursor.app`, `/Applications/Claude.app`, and `/Applications/Visual Studio Code.app`).
- ImageMagick: `brew install imagemagick`.

### Install

```sh
make install
```

Builds wrappers for every profile in `profiles/` and installs them to `~/Applications/`. They show up in Spotlight and Launchpad.

Override the destination if you want them in the system Applications folder:

```sh
make install DEST=/Applications
```

### Use

Click the branded `.app` from Spotlight, Launchpad, or the Dock — or use the matching shell alias from the dotfiles:

```sh
cursor-company1           # opens Cursor in the Company1 profile
cursor-company1 .         # opens the current dir in Company1 Cursor
claude-company1           # Claude Code CLI in the Company1 config dir
code-company1             # opens VS Code in the Company1 profile
code-company1 .           # opens the current dir in Company1 VS Code
```

### First Claude Desktop sign-in (`claude://` OAuth deep-link gotcha)

Critical and easy to miss:

> Claude Desktop authenticates via `claude://` deep links. With two desktop instances installed, macOS doesn't know which one requested the login and the auth callback gets routed to the wrong process — sign-in silently fails.
>
> **Workaround for first sign-in only:**
>
> 1. Quit any running Claude Desktop windows.
> 2. System Settings → Desktop & Dock → set default browser to **Safari** (temporarily).
> 3. Launch the new `Claude <LABEL>.app` and sign in.
> 4. Switch your default browser back.
>
> After first sign-in this is no longer an issue and both Claude instances run side-by-side. (Source: the `claude-cursor-multi-account-handoff.md` doc this work is based on.)

### First Cursor / VS Code launch

Extensions are per `--user-data-dir`, so a new Cursor or VS Code instance starts empty. Reinstall what you need; consider each editor's built-in settings sync if both instances should share.

### Command-line tools (Claude Code)

GUI apps need `.app` wrappers because macOS launches them through Spotlight/Dock and they hold a single OS-level instance lock. Command-line tools don't — they're just processes spawned in a shell, so swapping accounts is a per-invocation environment variable. No wrapper, no Makefile, no rebuild.

For the Claude Code CLI (`claude`), set `CLAUDE_CONFIG_DIR` to a per-profile directory and the CLI uses that account's auth, history, and settings. Wrap it in a shell alias and you get one-keystroke account switching:

#### zsh (default macOS shell)

Add to `~/.zshrc`:

```sh
alias claude-company1='CLAUDE_CONFIG_DIR="$HOME/.claude-company1" claude'
```

Then `exec zsh` (or open a new tab) and `claude-company1` runs Claude Code against `~/.claude-company1/`. First time you'll be prompted to sign in to that profile's account; after that it's automatic.

For a second profile, copy the line and swap both occurrences of the slug:

```sh
alias claude-company2='CLAUDE_CONFIG_DIR="$HOME/.claude-company2" claude'
```

#### fish

If you use fish, the equivalent function lives at `dotfiles/fish/conf.d/65-aliases.apps.fish` (same pattern: a `set -lx CLAUDE_CONFIG_DIR ...` followed by `command claude`).

#### Other CLIs

The same trick works for any CLI that respects a config-dir env var: `OP_ACCOUNT` for 1Password, `KUBECONFIG` for kubectl, `GH_CONFIG_DIR` for the GitHub CLI, etc. The shell alias is the whole story — no wrapper needed.

### Daily commands

| Command | What it does |
|---|---|
| `make` (no args) | Print help. |
| `make help` | Same. |
| `make dry-run` | Read-only rehearsal of `make install`. Runs `check`, `validate-profiles`, and `validate-templates` first; if it succeeds, `make install` will succeed too. Marks each predicted wrapper as `(new)` or `(replaces existing)`. |
| `make install` | (Re)build all profiles. Pre-flight runs `check`, `validate-profiles`, `validate-templates` so install never produces a partial result. |
| `make install PROFILE=company1` | (Re)build one profile. |
| `make uninstall` | Remove all built wrappers from `$DEST`. |
| `make uninstall PROFILE=company1` | Remove one profile's wrappers. |
| `make check` | Verify prereqs (`osacompile`, `iconutil`, `sips`, `magick`, source apps). |
| `make validate-profiles` | Verify every `profiles/<slug>.env` has `APPS=` set and references known apps. |
| `make validate-templates` | Render each (profile, app) AppleScript through `sed` and `osacompile` it to a tmp dir; catches template syntax errors before install. |
| `make clean` | Remove `build/` artifacts. |

### When to re-run `make install`

After Cursor, Claude Desktop, or VS Code updates that change their app icons (rare). The wrapper itself doesn't depend on the source app's internals, so app updates generally don't require rebuilding.

### Adding a new profile

Example: `company2` (a second work account alongside the primary `company1`).

1. Drop a transparent ~1024px badge at `macos-launchers/profiles/company2.png`.
2. Create `macos-launchers/profiles/company2.env`:

   ```sh
   LABEL=C2
   NAME=Company2
   APPS=cursor          # only build Cursor C2.app; skip Claude
   ```

   The slug `company2` is taken from the filename — no `SLUG=` line needed. List one or more app slugs in `APPS=` (matching `apps/<slug>.env` files); for all three wrappers, use `APPS=cursor,claude,vscode`.

3. Build it:

   ```sh
   make install PROFILE=company2   # or just `make install` to rebuild all
   ```

4. Add the matching shell aliases to `dotfiles/fish/conf.d/65-aliases.apps.fish` and `dotfiles/zshrc`, following the company1 pattern (one `cursor-<slug>`, one `claude-<slug>`, one `code-<slug>`).

### Removing a profile

```sh
make uninstall PROFILE=company2
rm macos-launchers/profiles/company2.{env,png}
```

Then remove the matching aliases from the dotfiles.

### Known limitations (accepted, not bugs)

- **Cmd-Tab / Mission Control / Activity Monitor / menu bar all show "Cursor" or "Claude"** — never "Cursor C1" / "Claude C1". They show the *running* process; the wrapper exits immediately after launching it. The Dock icon (clicked launcher) is correctly branded; the running-window icon is the standard one.
- **Quitting `Cursor C1` / `Claude C1` from the Dock** kills only the AppleScript stub. The real app stays open until Cmd-Q on its window.

---

## Part 2: How it works (and how to adapt it)

For anyone who wants to understand the pieces, fork it for a different setup, or apply the same recipe to a different Electron app.

### The wrapper pattern

Each `.app` is an AppleScript application built with `osacompile`. The script has two handlers:

- `on run` — launches the target app with the per-profile `--user-data-dir` flag.
- `on open` — same, but appends any file paths macOS hands the wrapper. So `open -a "Cursor C1" .` opens the current directory.

The wrapper *is* the launcher; it isn't trying to be a long-running app. Once it runs `do shell script` to launch the real app, the wrapper exits.

### Why this over duplicating `Cursor.app` / `Claude.app`

A duplicated bundle would let Cmd-Tab show "Cursor C1" — but at the cost of:

- Auto-update breakage on every release.
- Ad-hoc code signature triggering Gatekeeper warnings.
- `claude://` URL-scheme registration colliding between bundles.

We trade Cmd-Tab labeling for zero-maintenance.

### Why `--user-data-dir`

Both Cursor and Claude Desktop are Electron apps. Electron honors `--user-data-dir` to relocate everything user-scoped (auth tokens, settings, extensions/indexes) to that directory. `open -n` (Claude) is needed to spawn a new instance instead of focusing the existing single-instance lock holder. Cursor doesn't need `-n` because it's launched via its bundled `cursor` CLI, not `open -a`.

### Profile config schema

Each profile is two files in `profiles/`: `<slug>.env` and `<slug>.png`. The env file only holds what `make install` consumes; alias-only details live in the shell alias, not the env file.

| Key | Source | Description |
|---|---|---|
| Slug | filename basename | Lowercase `[a-z0-9-]+`. Used everywhere a path or alias name is generated (`~/.cursor-<slug>`, `~/.claude-<slug>`, `~/Library/Application Support/Claude-<slug>`). |
| `LABEL` | `<slug>.env` | Required. Short string used in the visible `.app` name (`"<NAME> <LABEL>.app"` where the leading `NAME` comes from `apps/<app>.env`). |
| `NAME` | `<slug>.env` | Required. Profile display name used in build output. Distinct from app env's `NAME`; the Makefile sources them into different scopes (profile in outer, app in inner subshell). |
| `APPS` | `<slug>.env` | Required. Comma-separated app slugs (must match files in `apps/`). Whitespace around commas is tolerated. Determines which wrappers are built for this profile. |
| `<slug>.png` | image file | Transparent ~1024px badge composited onto the base app icon. |

### App config schema

Each wrappable app is two files in `apps/`: `<app>.env` and `<app>.applescript`. The slug (filename basename) is the key.

| Key | Source | Description |
|---|---|---|
| Slug | filename basename | Lowercase `[a-z0-9-]+`. Cosmetic; not used in any path. |
| `NAME` | `<app>.env` | Required. App display name used in the wrapper output (`"<NAME> <LABEL>.app"` where `LABEL` comes from the profile env). Distinct from profile env's `NAME`; see the install-% comment block in the Makefile for the shadowing rule. |
| `SRC` | `<app>.env` | Required. Absolute path to the source `.app` bundle. Used for icon extraction and prereq existence checking. |
| `<app>.applescript` | template | AppleScript launched by the wrapper. Tokens substituted at build: `__SLUG__` always, `__CURSOR_BIN__` when present. |

### Token substitution

Templates in `apps/*.applescript` use `__SLUG__` and `__CURSOR_BIN__` (kept inside `do shell script "..."` strings so AppleScript editors don't flag them). The `install-%` Makefile recipe `sed`-renders them per profile before `osacompile`. `__CURSOR_BIN__` is resolved once at Makefile parse time via `$(shell command -v cursor)` so the wrapper has an absolute path baked in. `__CURSOR_BIN__` substitution runs against every template; it's a harmless no-op for templates that don't use it.

### Icon pipeline

Per profile per app:

1. `plutil -extract CFBundleIconFile raw` finds the source app's icon name.
2. `sips -s format png ... -z 1024 1024` extracts the highest-res representation as a 1024x1024 PNG.
3. `magick composite -gravity southeast -geometry 320x320+60+60 profiles/<slug>.png base.png branded.png` overlays the profile badge in the bottom-right with corner padding.
4. `sips` resamples to all standard sizes (16, 32, 64, 128, 256, 512 px @1x and @2x).
5. `iconutil -c icns iconset/ -o ...` packages the iconset as `.icns`.
6. The resulting `.icns` overwrites `applet.icns` inside the wrapper bundle's `Contents/Resources/` (default name AppleScript apps use).
7. `touch` on the `.app` invalidates the macOS icon cache; `killall Finder Dock` after the outer fan-out picks up the new icons.

### Adding another app

Drop in two files, then opt in each profile that should get it. The bundled `vscode` app (`apps/vscode.env`, `apps/vscode.applescript`) is a worked example you can model on — it adds a new `__CODE_BIN__` token resolved via `command -v code` in the Makefile.

Example: a hypothetical Electron editor `someeditor`.

1. Create `apps/someeditor.applescript` modeled on `apps/cursor.applescript`, `apps/vscode.applescript`, or `apps/claude.applescript`. Use `__SLUG__` wherever the per-profile data dir name goes. If the app launches via a CLI binary, add a new token (e.g. `__SOMEEDITOR_BIN__`), resolve it at the top of the Makefile via `$(shell command -v someeditor)`, and add it to the `sed` line in both `validate-templates` and `install`. Single-quote the token in the AppleScript (`'__SOMEEDITOR_BIN__'`) if the binary's fallback path could contain spaces — that's why the `vscode` template quotes `__CODE_BIN__` and the `cursor` template doesn't.
2. Create `apps/someeditor.env`:

   ```sh
   NAME=Some Editor
   SRC=/Applications/Some Editor.app
   ```

3. Edit each profile's `APPS=` to include `someeditor` (or leave it out for profiles that shouldn't get a wrapper). For example, `profiles/company1.env` becomes `APPS=cursor,claude,vscode,someeditor`.
4. `make install` builds wrappers only for the (profile, app) pairs explicitly opted in (`Some Editor C1.app` appears in `~/Applications/`).
5. Confirm the app actually honors profile isolation. Not every Electron app does.
6. Optionally add matching shell aliases in `dotfiles/fish/conf.d/65-aliases.apps.fish` and `dotfiles/zshrc` (one per app per profile, following the `cursor-<slug>` / `claude-<slug>` / `code-<slug>` pattern).

### What we deliberately did NOT build

- Cloned `.app` bundles with rewritten `CFBundleIdentifier` (Cmd-Tab labeling at the cost of constant maintenance).
- Ad-hoc re-signing (`codesign --force --deep --sign -`) of cloned bundles.
- Custom URL-scheme handlers to intercept `claude://` callbacks (would let both Claude instances run without the Safari workaround for first sign-in, but is fragile).
- Auto-generated shell aliases from the profile registry.
- Auto-installation of `imagemagick` (the Makefile errors with the `brew install` hint instead).
