# Mac how-to: a Personal and a Work Claude account, side by side

Run two Claude accounts on one Mac at the same time: your **Personal** account the way you launch Claude today, and a **Work** account (call it whatever you like) from its own launcher and its own terminal command. No logging out and back in.

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
> No `claude` command yet? Install it with `curl -fsSL https://claude.ai/install.sh | bash`, open a new Terminal window, and run the line above. The first time, Claude Code asks you to sign in (use your Personal account), whether you trust your home folder, and whether you accept skipping permissions: say yes to each. Or skip the terminal: in the Claude app's **Code** tab, pick your home folder, Opus, High effort, and the permission mode that doesn't ask (bypass permissions; you may have to allow it in the app's settings first).
>
> **2. Paste this prompt:**
>
> ```text
> Read https://raw.githubusercontent.com/GaryRudolph/public/main/howtos/mac-two-claude-accounts.md and set up this Mac so I can use a Personal and a Work Claude account side by side, following it. Before changing anything, ask me the questions in its "Choices" section and explain the tradeoffs. Then do the work yourself, and stop whenever I need to sign in or click something.
> ```
>
> **What it will touch:** `~/Applications/Claude Work.app`, `~/.claude-work/`, `~/Library/Application Support/Claude-work/`, two lines in `~/.zshrc` (a hidden settings file for Terminal), and `~/Projects/claude-accounts/`, where it leaves a `README.md` saying what it did, why, and how to undo it. It restarts the Dock once, and for the first Work sign-in it walks you through switching your default browser to Safari and back. Your Personal setup isn't changed.

![Personal runs from the normal folders; Work runs the same apps pointed at a second set of folders](assets/mac-two-claude-accounts.svg)

## Choices

Claude will ask you these before it changes anything.

**1. What's the second account called?** Default is **Work**. That gives you a `Claude Work` app and a `claude-work` command. Personal stays the default: anything you launch the normal way is Personal.

**2. What do you want set up?**

| Option | You get | Good for |
|---|---|---|
| **A. Claude app only** (recommended start) | A `Claude Work` launcher in `~/Applications`. Click it and the Claude app opens on your Work account, including its Code tab. | Most people. Everything happens in the app. |
| **B. App + terminal command** | A, plus `claude-work` in Terminal for Claude Code on the Work account. Plain `claude` stays Personal. | You also run Claude Code in a terminal. |
| **C. Terminal command only** | Just `claude-work`. No launcher, nothing built. | You only use Claude Code in a terminal. |

**3. Branded icon or plain?** (A and B only)

| | Branded | Plain |
|---|---|---|
| Launcher icon | The Claude icon with a colored badge (a "W" for Work) | The stock Claude icon |
| Told apart by | The badge and the name `Claude Work` | The name `Claude Work` only (Spotlight, the Applications folder, the label on a pinned Dock icon) |
| Extra work | Claude draws the badge with a scripting tool built into macOS | None, it copies the stock icon |

Either way, nothing extra gets installed: no Xcode tools, no Homebrew, no ImageMagick.

**The catch with both:** the badge is only on the launcher you click. Once the app is running, both copies show the plain Claude icon and the name "Claude" in the Dock, Cmd-Tab, and the menu bar, and macOS has no way to change that. Tell them apart by the account name inside the window (bottom left of the sidebar).

## How it works

The Claude app and Claude Code each keep your login, settings, and history in a folder. Launch them normally and they use the default folder, which is Personal. The Work launcher and the `claude-work` command start the exact same programs, pointed at a second folder. Different folder, different login.

| | Personal (default) | Work |
|---|---|---|
| How you start it | `Claude` app as usual, `claude` in Terminal | `Claude Work` launcher, `claude-work` in Terminal |
| Claude app data | `~/Library/Application Support/Claude` | `~/Library/Application Support/Claude-work` |
| Claude Code data | `~/.claude` (and `~/.claude.json`) | `~/.claude-work` |

The app's Code tab follows the app: Code sessions in `Claude Work` use `~/.claude-work`, the same folder `claude-work` uses, so they share settings and history.

Still shared between the two: your files, git, SSH keys, and the rest of your home folder. Only the Claude logins are separate.

The engineer's version, with every flag, lives in [`macos-launchers/README.md`](../macos-launchers/README.md).

## Instructions for Claude

You're setting this up for someone who isn't an engineer. Explain in plain words, keep updates short, and do the work yourself. Use your judgment where this doesn't cover something; the outcome below is what matters.

**Ask first.** Ask the three Choices questions in one go, with the tradeoffs in your own words, and wait for answers. If branded, also offer a badge color (default a deep orange, `#C2410C`). From the name, derive a slug matching `[a-z0-9-]+` ("Acme Corp" becomes `acme-corp`) and a badge letter (`A`); the app is `Claude <Name>`. Everything below uses `work` as the example. Then check:

- Options A and B need `/Applications/Claude.app`; if it's missing, have them install the Claude app first.
- Options B and C need the `claude` command. If `command -v claude` finds nothing, install it with `curl -fsSL https://claude.ai/install.sh | bash` and make sure `~/.local/bin` is on the `PATH` in `~/.zshrc`.
- If `~/Applications/Claude Work.app`, `~/.claude-work`, or a `claude-work` alias already exists, say so and ask before replacing anything. Never delete an existing `~/.claude-work` or `~/Library/Application Support/Claude-work`: that's someone's login and history.

**Only what ships with macOS.** Don't install Xcode command line tools, Homebrew, or ImageMagick, and don't run `git`, `make`, or `python3`: on a stock Mac those are stubs that pop up an Xcode install. `zsh`, `curl`, `tar`, `osacompile`, `plutil`, `sips`, `iconutil`, `osascript`, and the usual `/bin` and `/usr/bin` tools (`cp`, `mkdir`, `mktemp`, `killall`, `sed`) are all fine.

**Get the reference code.** Read the commit hash with `curl -fsSL -H 'Accept: application/vnd.github.sha' https://api.github.com/repos/GaryRudolph/public/commits/main`, then download `https://github.com/GaryRudolph/public/archive/<sha>.tar.gz` into a temp folder, so the code matches the commit you record. Read `macos-launchers/apps/claude.applescript` and the `install` recipe in `macos-launchers/Makefile`. That's the tested recipe, so follow it, with one swap: the Makefile badges the icon with ImageMagick and a prepared PNG, which you replace with JXA (below). Don't use its `profiles/` (they're Gary's) and don't push anything anywhere.

**Write `install.sh` and `uninstall.sh`** in `~/Projects/claude-accounts/` (zsh, `set -euo pipefail`, safe to run again), whatever the option, then run `install.sh`. Embed the AppleScript template in `install.sh` so a rebuild never needs the download. `install.sh` does what was chosen:

- **Launcher (A, B).** Render the template with the slug and `osacompile` it to `~/Applications/Claude Work.app` (replacing the old one). Find Claude.app's icon from `CFBundleIconFile` in its `Info.plist` (add `.icns` if missing); if there's none, use the largest `.icns` in its `Contents/Resources`, and if there's still none, keep the default script icon and tell them.
  - Plain: copy that `.icns` in as is. No `sips` or `iconutil` needed.
  - Branded: `sips` it to a 1024px PNG, then draw the badge with JXA (`osascript -l JavaScript`, `ObjC.import('AppKit')`): draw the icon into a 1024x1024 `NSBitmapImageRep`, add a filled circle about 400px across, inset about 48px from the bottom-right corner, in the chosen color with a thin white ring, center the letter in white bold system font (about 260pt), and save it as a PNG. Make the iconset sizes with `sips` and the `.icns` with `iconutil`, as the Makefile does.
  - Either way, finish like the Makefile: write the icon to both `Contents/Resources/applet.icns` and `droplet.icns`, delete `Assets.car`, `touch` the app, then `killall Finder Dock`.
- **Terminal command (B, C).** Add these two lines to `~/.zshrc` (or their shell's startup file if it isn't zsh), only if the alias isn't there already:

  ```bash
  # Work Claude account; see ~/Projects/claude-accounts/README.md
  alias claude-work='CLAUDE_CONFIG_DIR="$HOME/.claude-work" claude'
  ```

`uninstall.sh` removes the launcher and those two lines, and leaves the Work data folders alone (deleting them is a separate choice in Undo).

**Leave a record.** Write `~/Projects/claude-accounts/README.md` for them or a future agent: a link to this how-to and the commit you read, the date, their answers, every file and folder you created or changed outside that folder, how to rebuild after a Claude app update changes its icon (`zsh install.sh`), and how to undo. Short and plain.

**Walk them through signing in.** The Claude app signs in through a `claude://` link from the browser, and with two copies installed macOS can hand that link to the wrong copy, so sign-in silently fails. The workaround is to sign in through Safari with only the Work copy running. Give them every step below in one message before they start, because step 1 closes the Claude app, and if you're running in its Code tab, you close with it:

1. Quit the Claude app completely (click a Claude window, then Cmd-Q; repeat until no Claude is left in the Dock). Terminal can stay open.
2. System Settings → Desktop & Dock → Default web browser → Safari. If Safari is already the default, skip this.
3. Open `Claude Work` (Spotlight, or `~/Applications`) and sign in with the Work account.
4. Set the default browser back.
5. Reopen the normal Claude app; it should still be on Personal.

If you were running in the Code tab, tell them to reopen this session from the Personal app afterward to finish.

Then for B and C: open a new Terminal window, run `claude-work`, and sign in with the Work account.

**Check it.** Both apps open at the same time, on different accounts. `claude-work` then `/status` shows the Work account; plain `claude` shows Personal. Suggest they drag `Claude Work` from `~/Applications` to the Dock. Finish with a short plain-language summary: what they have, how to open each, and where the README is.

## Gotchas

- **Sign-in goes nowhere.** That's the `claude://` link going to the wrong copy. Quit every Claude window, open only `Claude Work`, and sign in through Safari (steps above). It only matters the first time.
- **Running icons look the same.** Expected. Look at the account name in the window.
- **Quitting `Claude Work` from the Dock doesn't close it.** The launcher only starts the app and exits. Click a Work window, then Cmd-Q.
- **Work app shows Personal Code history.** In the Work copy, open Settings and look under environment variables for one named `CLAUDE_CONFIG_DIR`. If it's there, it overrides the launcher. Remove it and restart the Work app.
- **A change didn't take.** The app reads its settings when it starts. Quit it with Cmd-Q and open it again from the launcher.

## Undo

Start from `~/Projects/claude-accounts/README.md`, which lists exactly what was done on your Mac. In short: run `zsh ~/Projects/claude-accounts/uninstall.sh` (it removes the launcher and the `claude-work` command), and if you want the Work login and history gone too, delete `~/.claude-work` and `~/Library/Application Support/Claude-work`. Or paste that README into Claude Code and ask it to undo everything.
