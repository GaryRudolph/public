# Claude Code Remote Control — Setup Runbook

Sets up an always-on Claude Code Remote Control server on `HOST` for one Claude account. You steer the sessions from the Claude app on your phone or iPad, or from claude.ai/code. Claude runs on this Mac, with its files, Xcode, simulators, and local tools.

Placeholders (`HOST`, `ADMIN`, `ORG`, `USER`, `ACCOUNT`, `REPO`, `GH_OWNER`) are defined in [README.md § Placeholders](README.md#placeholders).

## Rules
- **One Claude account per macOS user.** Never sign a different account into `USER`.
- **One org's code per user.** Never clone another org's repos into `USER`.
- **A subscription login only.** Remote Control does not work with an API key, Bedrock/Vertex, or a custom `ANTHROPIC_BASE_URL`.

---

## 1. Prerequisites (Mac)

- [ ] **Mac-wide setup** (name, power, display, network, remote access, reboots, Homebrew `claude-code@latest` + `tmux` + `gh`, Xcode): see [README.md §A](README.md#a-once-per-mac).
- [ ] **Per-user setup** for `USER` (Standard user, first login, verify tools, home isolation): see [README.md §B](README.md#b-once-per-macos-user-runner-or-agent).

---

## 2. Claude and GitHub settings

### 2a. Enable Remote Control

| Plan | What to do |
|---|---|
| Pro, Max | Nothing to enable. Turn on **Require trusted devices** yourself under claude.ai → Settings → Account. Use `ORG` = `personal`. |
| Team, Enterprise | An Owner turns on **Remote Control** at claude.ai/admin-settings/claude-code (off by default) and, recommended, **Require trusted devices** under Organization settings → Capabilities → Remote sessions. |

> If you aren't an Owner of `ORG`, ask one to turn these on. Also confirm `ORG` allows its code on this Mac before cloning anything.

### 2b. Protect the default branch
The GitHub token in §3c can write to any branch it reaches, and so can every session. In each repo or org: GitHub → Settings → Rules → **New branch ruleset** targeting the default branch, with **Require a pull request before merging** and **Block force pushes**.

### 2c. As `ACCOUNT`
- [ ] **Claude app on your phone:** install it, sign in as `ACCOUNT`, and allow notifications.
- [ ] **Trusted Devices:** enroll the phone the first time it prompts. It uses Face ID; each device enrolls once.

---

## 3. Agent user configuration (as `USER`)

### 3a. Check the environment
None of these should be set. Each one disables Remote Control:
```bash
env | grep -E 'ANTHROPIC_API_KEY|ANTHROPIC_BASE_URL|ANTHROPIC_AUTH_TOKEN|CLAUDE_CODE_USE_BEDROCK|CLAUDE_CODE_USE_VERTEX|CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC|DISABLE_GROWTHBOOK'
grep -E 'apiKeyHelper|ANTHROPIC_|CLAUDE_CODE_USE_' ~/.claude/settings.json
# expect no output from either; also check ~/.zshrc
```
If Trusted Devices is required, `DISABLE_TELEMETRY` and `DO_NOT_TRACK` must be unset too.

### 3b. Sign in
```bash
claude auth login          # choose the claude.ai option; sign in as ACCOUNT
claude doctor              # confirms the account and Remote Control eligibility
```

### 3c. GitHub credential (scoped to this org)
Use a **fine-grained personal access token**, not your personal SSH key.
1. **Create it:** github.com → Settings → Developer settings → Fine-grained tokens → **Generate new token**.
   - Resource owner: `GH_OWNER`
   - Repository access: only the repos this user works on
   - Permissions: **Contents** read/write, **Pull requests** read/write
   - Expiration: 90 days (set a reminder)
   - If the org requires approval or SSO, get it approved or authorized for `GH_OWNER`.
2. **Configure it:**
   ```bash
   gh auth login --with-token        # paste token, Enter, Ctrl-D
   gh auth setup-git
   git config --global user.name  "YOUR_NAME"
   git config --global user.email "ACCOUNT"          # or your GitHub email for this org
   ```

### 3d. Clone and trust each repo
```bash
mkdir -p ~/code && cd ~/code
gh repo clone GH_OWNER/REPO
cd ~/code/REPO
claude                     # accept the workspace trust dialog, then /exit
```
Repeat for each repo.

### 3e. One-time Remote Control consent and notifications
```bash
cd ~/code/REPO
claude remote-control      # answer "y" to "Enable Remote Control?", then Ctrl-C
claude                     # then run /config:
                           #   Push when actions required → on
                           #   Push when Claude decides   → on
```

### 3f. Signing (only if building Apple apps)
- **Xcode:** Settings → Accounts → add `ORG`'s developer Apple ID, or use an App Store Connect API key.
- **Certificates:** only `ORG`'s development certificates in this user's login keychain.

---

## 4. Keep-alive scripts and launchd job (as `USER`)

One tmux session named `rc` holds one window per repo. Each window runs a Remote Control server in a restart loop.

### 4a. Repo list
`~/.config/claude-rc/repos`, one folder name under `~/code` per line:
```
REPO
```

### 4b. Server script
`~/bin/rc-server.sh`:
```zsh
#!/bin/zsh
# Usage: rc-server.sh REPO
ORG="ORG"
REPO="$1"
cd "$HOME/code/$REPO" || exit 1
while true; do
  # Rerunning in the same folder brings back this server's sessions (~4 hours).
  /opt/homebrew/bin/claude remote-control --spawn worktree \
    --name "$(hostname -s)-$ORG-$REPO"
  sleep 30   # server mode exits after ~10 min without network; restart it
done
```

### 4c. Start script
`~/bin/rc-start.sh`:
```zsh
#!/bin/zsh
# Recreates the "rc" tmux session with one window per repo in ~/.config/claude-rc/repos.
TMUX_BIN=/opt/homebrew/bin/tmux
$TMUX_BIN kill-session -t rc 2>/dev/null
first=1
while read -r repo; do
  [[ -z "$repo" || "$repo" == \#* ]] && continue
  if (( first )); then
    $TMUX_BIN new-session -d -s rc -n "$repo" "$HOME/bin/rc-server.sh $repo"
    first=0
  else
    $TMUX_BIN new-window -t rc -n "$repo" "$HOME/bin/rc-server.sh $repo"
  fi
done < "$HOME/.config/claude-rc/repos"
```
```bash
mkdir -p ~/bin && chmod +x ~/bin/rc-server.sh ~/bin/rc-start.sh
```

### 4d. launchd job
`~/Library/LaunchAgents/local.claude.rc.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>local.claude.rc</string>
  <key>ProgramArguments</key><array>
    <string>/bin/zsh</string>
    <string>/Users/USER/bin/rc-start.sh</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/Users/USER/Library/Logs/claude-rc.out</string>
  <key>StandardErrorPath</key><string>/Users/USER/Library/Logs/claude-rc.err</string>
</dict></plist>
```
```bash
plutil -lint ~/Library/LaunchAgents/local.claude.rc.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.claude.rc.plist
tmux attach -t rc          # watch it; switch windows with Ctrl-b n, detach with Ctrl-b d
```
- **Why tmux:** it keeps the servers running with a terminal you can reattach to over SSH.
- **Why the loop:** `rc-server.sh` restarts the server if it exits. Rerunning `claude remote-control` in the same folder brings back the sessions it was serving, so a network drop doesn't lose them.
- **Why no KeepAlive:** `rc-start.sh` returns as soon as tmux starts, so launchd only runs it at login or on `kickstart`.
- **Keep the default session-in-dir.** Don't add `--no-create-session-in-dir`: with it, stopping the server archives its sessions and the loop can't bring them back.
- **More repos:** add a line to `~/.config/claude-rc/repos`, clone and trust the repo (§3d), then restart the job.

---

## 5. Using it
- **In the Claude app** (signed in as `ACCOUNT`) → **Code** tab. Sessions named `HOST-ORG-REPO` show a computer icon with a green dot when online.
- **Starting a new session** from the phone gives it its own git worktree (`--spawn worktree`).
- **Reviewing changes:** the diff pane shows changes on the session's branch.
- **More than one account:** the phone app shows one account at a time. Use claude.ai/code in Safari, or a separate browser profile, for the other.

---

## 6. Operations

| Task | How |
|---|---|
| Check status | `tmux attach -t rc` as `USER` (from SSH: `sudo -iu USER tmux attach -t rc`) |
| Diagnose | `claude doctor` as `USER` |
| Restart or upgrade | As `ADMIN`: `brew upgrade claude-code@latest` (upgrade only). Then as `USER`: `launchctl kickstart -k gui/$(id -u)/local.claude.rc` |
| Resume sessions after a restart | Automatic: the loop reruns `claude remote-control` in the same folder, which brings back every session that server was serving (within ~4 hours) |
| Token expiring | Create a new fine-grained token, then `gh auth login --with-token` |
| "Remote Control is disabled by your organization's policy" | Owner hasn't turned on the toggle (§2a), or the login is stale: `claude auth logout && claude auth login` |
| "requires claude.ai subscription auth" | An API key, token, or `apiKeyHelper` is set (§3a) |
| "sign-in is more than 18 hours old" (Trusted Devices) | Confirm with Face ID when the app prompts, or run `/login` in `claude` as `USER` |

---

## 7. Security notes
- **Remote Control sessions run as `USER`.** They can read everything in that user: the repos, the GitHub token, signing certificates, and the Claude login. Keep it to one org's material, and keep other users' homes locked (README §B5).
- **No personal credentials in `USER`:** no iCloud, personal SSH keys, or production cloud credentials.
- **Keep permission prompts on.** Don't start servers with a `--permission-mode` that auto-approves edits or commands; approve from the phone instead.
- **Transcripts are stored by Anthropic** while Remote Control is connected. Execution and files stay on the Mac.

## Sources
- [Claude Code Docs — Remote Control](https://code.claude.com/docs/en/remote-control)
- [Claude Code Docs — Settings reference](https://code.claude.com/docs/en/settings-reference)
