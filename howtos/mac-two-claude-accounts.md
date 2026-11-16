# Mac how-to: a primary and a secondary Claude account, side by side

Run two Claude accounts on one Mac at the same time. Your **primary** account is the one you launch the normal way today. Your **secondary** account opens from its own launcher and its own terminal command. No logging out and back in.

You name the secondary account. Everywhere below, `<secondary>` stands for that name: `work`, your company's name (`acme`), or `personal` if your primary is your work account.

![Primary runs from the normal folders; secondary runs the same apps pointed at a second set of folders](assets/mac-two-claude-accounts.svg)

> [!NOTE]
> **Two things to know before you start**
>
> 1. **The Dock will always show two plain Claude icons.** Whatever badge you put on the `Claude <Secondary>` launcher, once both apps are running macOS shows the stock Claude icon and the name "Claude" for each, in the Dock, Cmd-Tab, and the menu bar. The badge only shows on the launcher you click. Tell them apart by the account name inside the window.
> 2. **Have only one Claude running when you connect a connector.** Connecting Google Drive, Slack, GitHub, or any other connector ends with a link back into the Claude app, and with two running, macOS can't tell which one should get it, so the connection fails or lands in the wrong account. Quit the other one (Cmd-Q) first, connect, then reopen it. Same for signing in.

## Quick start with Claude

> [!CAUTION]
> **You only live once: just let Claude do it.**
>
> This hands your Mac to Claude Code with permission checks turned off. It will download files, write scripts, run them, and edit `~/.zshrc` without asking first. It's all in your home folder and all undoable, but read what it says as it goes.
>
> **1. Start Claude Code in your home folder, on Opus at High effort.** In Terminal:
>
> ```bash
> cd ~ && claude --model opus --effort high --dangerously-skip-permissions
> ```
>
> No `claude` command yet? Install it with `curl -fsSL https://claude.ai/install.sh | bash`, open a new Terminal window, and run the line above. The first time, Claude Code asks you to sign in (use your primary account), whether you trust your home folder, and whether you accept skipping permissions: say yes to each. Or skip the terminal: in the Claude app's **Code** tab, pick your home folder, Opus, High effort, and the permission mode that doesn't ask (bypass permissions; you may have to allow it in the app's settings first).
>
> **2. Paste this prompt:**
>
> ```text
> Read https://raw.githubusercontent.com/GaryRudolph/public/main/howtos/mac-two-claude-accounts.md and set up this Mac so I can use a primary and a secondary Claude account side by side, following it. Before changing anything, ask me the questions in its "Choices" section and explain the tradeoffs. Then do the work yourself, and stop whenever I need to sign in or click something.
> ```
>
> **What it will touch:** `~/Applications/Claude <Secondary>.app`, `~/.claude-<secondary>/`, `~/Library/Application Support/Claude-<secondary>/`, two lines in `~/.zshrc` (a hidden settings file for Terminal), and `~/Projects/claude-accounts/`, where it leaves a `README.md` saying what it did, why, and how to undo it. It restarts the Dock once, and for the first secondary sign-in it walks you through switching your default browser to Safari and back. Your primary setup isn't changed.

## Choices

Claude will ask you these before it changes anything.

**1. What do you call your secondary account?** One word works best, such as `work`, `acme`, or `personal`. Name it `acme` and you get a `Claude Acme` app and a `claude-acme` command. Your primary account needs no name: anything you launch the normal way is primary.

**2. What do you want set up?**

| Option | You get | Good for |
|---|---|---|
| **A. Claude app only** (recommended start) | A `Claude <Secondary>` launcher in `~/Applications`. Click it and the Claude app opens on your secondary account, including its Code tab. | Most people. Everything happens in the app. |
| **B. App + terminal command** | A, plus `claude-<secondary>` in Terminal for Claude Code on the secondary account. Plain `claude` stays primary. | You also run Claude Code in a terminal. |
| **C. Terminal command only** | Just `claude-<secondary>`. No launcher, nothing built. | You only use Claude Code in a terminal. |

**3. Branded icon or plain?** (A and B only)

| | Branded | Plain |
|---|---|---|
| Launcher icon | The Claude icon with a colored badge showing the first letter of the name ("A" for Acme) | The stock Claude icon |
| Told apart by | The badge and the name `Claude <Secondary>` | The name `Claude <Secondary>` only (Spotlight, the Applications folder, the label on a pinned Dock icon) |
| Extra work | Claude draws the badge with a scripting tool built into macOS | None, it copies the stock icon |

Either way, nothing extra gets installed: no Xcode tools, no Homebrew, no ImageMagick.

Either way, the running apps look identical in the Dock (see the note at the top). The account name inside the window, bottom left of the sidebar, is how you tell them apart.

## How it works

The Claude app and Claude Code each keep your login, settings, and history in a folder. Launch them normally and they use the default folder, which is your primary account. The secondary launcher and the `claude-<secondary>` command start the exact same programs, pointed at a second folder. Different folder, different login.

| | Primary (default) | Secondary |
|---|---|---|
| How you start it | `Claude` app as usual, `claude` in Terminal | `Claude <Secondary>` launcher, `claude-<secondary>` in Terminal |
| Claude app data | `~/Library/Application Support/Claude` | `~/Library/Application Support/Claude-<secondary>` |
| Claude Code data | `~/.claude` (and `~/.claude.json`) | `~/.claude-<secondary>` |

The app's Code tab follows the app: Code sessions in `Claude <Secondary>` use `~/.claude-<secondary>`, the same folder `claude-<secondary>` uses, so they share settings and history.

Still shared between the two: your files, git, SSH keys, and the rest of your home folder. Only the Claude logins are separate.

The engineer's version, with every flag, lives in [`macos-launchers/README.md`](../macos-launchers/README.md).

## Instructions for Claude

You're setting this up for someone who isn't an engineer. Explain in plain words, keep updates short, and do the work yourself. Use your judgment where this doesn't cover something; the outcome below is what matters.

**Names.** `<secondary>` is the slug: lowercase, matching `[a-z0-9-]+` ("Acme Corp" becomes `acme-corp`). `<Secondary>` is the display name in title case (`Acme Corp`), used only in the app name `Claude <Secondary>`. The badge letter is the display name's first letter. The worked example throughout is `acme`: `Claude Acme.app`, `claude-acme`, `~/.claude-acme`.

**Ask first.** Ask the three Choices questions in one go, with the tradeoffs in your own words, and wait for answers. There's no default name, so don't pick one for them. If branded, also offer a badge color (default a deep orange, `#C2410C`). Then check:

- Options A and B need `/Applications/Claude.app`; if it's missing, have them install the Claude app first.
- Options B and C need the `claude` command. If `command -v claude` finds nothing, install it with `curl -fsSL https://claude.ai/install.sh | bash` and make sure `~/.local/bin` is on the `PATH` in `~/.zshrc`.
- If `~/Applications/Claude <Secondary>.app`, `~/.claude-<secondary>`, or a `claude-<secondary>` alias already exists, say so and ask before replacing anything. Never delete an existing `~/.claude-<secondary>` or `~/Library/Application Support/Claude-<secondary>`: that's someone's login and history.

**Only what ships with macOS.** Don't install Xcode command line tools, Homebrew, or ImageMagick, and don't run `git`, `make`, or `python3`: on a stock Mac those are stubs that pop up an Xcode install. `zsh`, `curl`, `tar`, `osacompile`, `plutil`, `sips`, `iconutil`, `osascript`, and the usual `/bin` and `/usr/bin` tools (`cp`, `mkdir`, `mktemp`, `killall`, `sed`) are all fine.

**Get the reference code.** Read the commit hash with `curl -fsSL -H 'Accept: application/vnd.github.sha' https://api.github.com/repos/GaryRudolph/public/commits/main`, then download `https://github.com/GaryRudolph/public/archive/<sha>.tar.gz` into a temp folder, so the code matches the commit you record. Read `macos-launchers/apps/claude.applescript` and the `install` recipe in `macos-launchers/Makefile`. That's the tested recipe, so follow it, with one swap: the Makefile badges the icon with ImageMagick and a prepared PNG, which you replace with JXA (below). Don't use its `profiles/` (they're Gary's) and don't push anything anywhere.

**Write `install.sh` and `uninstall.sh`** in `~/Projects/claude-accounts/` (zsh, `set -euo pipefail`, safe to run again), whatever the option, then run `install.sh`. Embed the AppleScript template in `install.sh` so a rebuild never needs the download. `install.sh` does what was chosen:

- **Launcher (A, B).** Render the template with `<secondary>` as the slug and `osacompile` it to `~/Applications/Claude <Secondary>.app` (replacing the old one). Find Claude.app's icon from `CFBundleIconFile` in its `Info.plist` (add `.icns` if missing); if there's none, use the largest `.icns` in its `Contents/Resources`, and if there's still none, keep the default script icon and tell them.
  - Plain: copy that `.icns` in as is. No `sips` or `iconutil` needed.
  - Branded: `sips` it to a 1024px PNG, then draw the badge with JXA (`osascript -l JavaScript`, `ObjC.import('AppKit')`): draw the icon into a 1024x1024 `NSBitmapImageRep`, add a filled circle about 400px across, inset about 48px from the bottom-right corner, in the chosen color with a thin white ring, center the letter in white bold system font (about 260pt), and save it as a PNG. Make the iconset sizes with `sips` and the `.icns` with `iconutil`, as the Makefile does.
  - Either way, finish like the Makefile: write the icon to both `Contents/Resources/applet.icns` and `droplet.icns`, delete `Assets.car`, `touch` the app, then `killall Finder Dock`.
- **Terminal command (B, C).** Add these two lines to `~/.zshrc` (or their shell's startup file if it isn't zsh), only if the alias isn't there already. For `acme`:

  ```bash
  # Secondary Claude account (acme); see ~/Projects/claude-accounts/README.md
  alias claude-acme='CLAUDE_CONFIG_DIR="$HOME/.claude-acme" claude'
  ```

`uninstall.sh` removes the launcher and those two lines, and leaves the secondary data folders alone (deleting them is a separate choice in Undo).

**Leave a record.** Write `~/Projects/claude-accounts/README.md` for them or a future agent: a link to this how-to and the commit you read, the date, their answers, every file and folder you created or changed outside that folder, how to rebuild after a Claude app update changes its icon (`zsh install.sh`), and how to undo. Short and plain, with their real name filled in, not `<secondary>`.

**Walk them through signing in.** The Claude app signs in through a `claude://` link from the browser, and with two copies installed macOS can hand that link to the wrong copy, so sign-in silently fails. The workaround is to sign in through Safari with only the secondary copy running. Give them every step below in one message before they start, because step 1 closes the Claude app, and if you're running in its Code tab, you close with it:

1. Quit the Claude app completely (click a Claude window, then Cmd-Q; repeat until no Claude is left in the Dock). Terminal can stay open.
2. System Settings → Desktop & Dock → Default web browser → Safari. If Safari is already the default, skip this.
3. Open `Claude <Secondary>` (Spotlight, or `~/Applications`) and sign in with the secondary account.
4. Set the default browser back.
5. Reopen the normal Claude app; it should still be on the primary account.

If you were running in the Code tab, tell them to reopen this session from the primary app afterward to finish.

Then for B and C: open a new Terminal window, run `claude-<secondary>`, and sign in with the secondary account.

**Check it.** Both apps open at the same time, on different accounts. `claude-<secondary>` then `/status` shows the secondary account; plain `claude` shows the primary. Suggest they drag `Claude <Secondary>` from `~/Applications` to the Dock. Finish with a short plain-language summary: what they have, how to open each, where the README is, and the two points in the note at the top of this how-to (identical Dock icons, one Claude running when connecting a connector).

## Gotchas

- **Sign-in goes nowhere.** That's the `claude://` link going to the wrong copy. Quit every Claude window, open only `Claude <Secondary>`, and sign in through Safari (steps above). It only matters the first time.
- **Running icons look the same.** Expected. Look at the account name in the window.
- **A connector won't connect, or shows up in the wrong account.** Both copies were running when its sign-in link came back. Quit the one you're not connecting, then connect again.
- **Quitting `Claude <Secondary>` from the Dock doesn't close it.** The launcher only starts the app and exits. Click a secondary window, then Cmd-Q.
- **Secondary app shows primary Code history.** In the secondary copy, open Settings and look under environment variables for one named `CLAUDE_CONFIG_DIR`. If it's there, it overrides the launcher. Remove it and restart the secondary app.
- **A change didn't take.** The app reads its settings when it starts. Quit it with Cmd-Q and open it again from the launcher.

## Undo

Start from `~/Projects/claude-accounts/README.md`, which lists exactly what was done on your Mac. In short: run `zsh ~/Projects/claude-accounts/uninstall.sh` (it removes the launcher and the `claude-<secondary>` command), and if you want the secondary login and history gone too, delete `~/.claude-<secondary>` and `~/Library/Application Support/Claude-<secondary>`. Or paste that README into Claude Code and ask it to undo everything.
