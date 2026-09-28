# Self-Hosted Runner — Setup Runbook

Sets up one Claude Code self-hosted runner on `HOST`, running cloud sessions for one Claude organization and locked to one account. Self-hosted environments are in **public beta** (Team and Enterprise plans). Check flags against `claude self-hosted-runner --help` on the installed version.

Placeholders (`HOST`, `ADMIN`, `ORG`, `USER`, `ACCOUNT`, `ENV_NAME`) are defined in [README.md § Placeholders](README.md#placeholders).

## Rules
- **Capacity is always 1.** `--use-anthropic-git-proxy` requires it, and it keeps Git credentials off the Mac. For more parallel sessions, add another runner user (`ORG-runner-2`) with the same key and flags rather than raising capacity.
- **One runner user per org.** A runner registers with one environment in one org.
- **Never `claude auth login` in `USER`.** The runner authenticates with the environment key. A login would leave a full-account token that every session could read.
- **Nothing personal in `USER`:** no iCloud, SSH keys, cloud credentials, or Git tokens.

---

## 1. Prerequisites (Mac)

- [ ] **Mac-wide setup** (name, power, display, network, remote access, reboots, Homebrew `claude-code@latest`, Xcode): see [README.md §A](README.md#a-once-per-mac).
- [ ] **Per-user setup** for `USER` (Standard user, first login, verify tools, home isolation): see [README.md §B](README.md#b-once-per-macos-user-runner-or-agent).

---

## 2. Claude settings (claude.ai)

### 2a. Organization Owner, done once per org

| Setting | Where | Value |
|---|---|---|
| Cloud sessions | claude.ai/admin-settings/claude-code | On |
| Claude GitHub App | github.com/apps/claude → install | On every repo the runner will work on |
| Allow self-hosted environments | Admin settings → **Cloud environments** | On |
| Hide Anthropic-hosted environments | Admin settings → Cloud environments | **Off** (leave them visible) |
| Organization default environment | claude.ai/admin-settings/claude-code | **Not** `ENV_NAME` |

### 2b. Create the environment and key (Owner)
1. **Create:** Admin settings → **Cloud environments** → **Self-hosted environments** → **New**. Name it `ENV_NAME`, then **Create**.
2. **Copy the key:** on the wizard's second step, select **Copy environment key**. It's shown **once**. Keep it in your password manager until §3b, then delete that copy.
3. **Record** the environment's `ccpool_…` ID from its detail dialog.
4. **Set a reminder:** the key **expires 365 days** after creation. Add a calendar reminder 2 weeks before expiry.

> If you aren't an Owner of `ORG`, an Owner does §2a–2b and gives you the key. A name like `HOST (you only)` tells other members the environment isn't for them.

### 2c. As `ACCOUNT` (the person whose sessions will run)
- [ ] **Connect GitHub:** claude.ai → Settings → connect your GitHub account. The Git proxy clones and pushes with this account's token.
- [ ] **Restrict `claude/*` branches** (required because the plist uses `--push-outcome-on-release`). In each repo or org: GitHub → Settings → Rules → **New branch ruleset**.
  - Target: `claude/**`
  - Restrict creations, updates, and deletions to yourself (or a trusted team) via bypass list.

  On resume, the runner fetches the previously pushed `claude/*` branch without checking who pushed it.

---

## 3. Runner user configuration (as `USER`)

### 3a. Directories
```bash
mkdir -p ~/.claude-runner ~/runner-work ~/Library/Logs ~/Library/LaunchAgents
chmod 700 ~/.claude-runner
```

### 3b. Install the environment key
```bash
(umask 077 && cat > ~/.claude-runner/environment-secret)
# paste the key, press Enter, then Ctrl-D
ls -l ~/.claude-runner/environment-secret      # should be -rw-------
```
Then delete the key from wherever you staged it (clipboard, password manager note).

### 3c. Foreground test
```bash
/opt/homebrew/bin/claude self-hosted-runner \
  --environment-secret-file ~/.claude-runner/environment-secret \
  --base-dir ~/runner-work \
  --capacity 1 \
  --lock-to-account ACCOUNT \
  --use-anthropic-git-proxy \
  --configure-git \
  --confine-repo-settings enforce \
  --kill-session-after-min 480 \
  --release-idle-session-min 60 \
  --push-outcome-on-release
```
Then verify:
- [ ] **Registered:** Admin settings → Cloud environments → `ENV_NAME` shows **Healthy**.
- [ ] **Picks up work:** as `ACCOUNT`, start a session at claude.ai/code, pick `ENV_NAME`, and choose a repo. The terminal prints `Picked up session …`.
- [ ] **Session finishes:** the runner exits on its own when the session ends. That's by design.

If `--lock-to-account` rejects an email, check `--help` for the expected format (it may want an account ID).

### 3d. Flags

| Flag | Purpose |
|---|---|
| `--environment-secret-file` | Authenticates the runner to the environment |
| `--base-dir ~/runner-work` | Where repos are checked out; keep it the same on every runner in the environment |
| `--capacity 1` | One session at a time; required by the Git proxy |
| `--lock-to-account ACCOUNT` | Only this account's sessions run here; others stay queued |
| `--use-anthropic-git-proxy` | Clones and pushes with the session creator's GitHub token; no Git credentials on the Mac |
| `--configure-git` | Commits are signed as Claude, with `ACCOUNT` as co-author |
| `--confine-repo-settings enforce` | Refuses repos whose committed settings reach outside the workspace |
| `--kill-session-after-min 480` | Hard cap on a runaway session |
| `--release-idle-session-min 60` | Frees the runner from sessions idle for an hour |
| `--push-outcome-on-release` | Pushes committed work before release, so a resumed session keeps it |
| `--log-file` | Runner lifecycle log (used by `doctor`) |

---

## 4. launchd job (as `USER`)

The runner exits after each session by design, so launchd restarts it.

`~/Library/LaunchAgents/local.claude.runner.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>local.claude.runner</string>
  <key>ProgramArguments</key><array>
    <string>/opt/homebrew/bin/claude</string>
    <string>self-hosted-runner</string>
    <string>--environment-secret-file</string><string>/Users/USER/.claude-runner/environment-secret</string>
    <string>--base-dir</string><string>/Users/USER/runner-work</string>
    <string>--capacity</string><string>1</string>
    <string>--lock-to-account</string><string>ACCOUNT</string>
    <string>--use-anthropic-git-proxy</string>
    <string>--configure-git</string>
    <string>--confine-repo-settings</string><string>enforce</string>
    <string>--kill-session-after-min</string><string>480</string>
    <string>--release-idle-session-min</string><string>60</string>
    <string>--push-outcome-on-release</string>
    <string>--log-file</string><string>/Users/USER/Library/Logs/claude-runner.log</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>StandardOutPath</key><string>/Users/USER/Library/Logs/claude-runner.out</string>
  <key>StandardErrorPath</key><string>/Users/USER/Library/Logs/claude-runner.err</string>
</dict></plist>
```

Load it:
```bash
plutil -lint ~/Library/LaunchAgents/local.claude.runner.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/local.claude.runner.plist
launchctl print gui/$(id -u)/local.claude.runner | grep state
tail -f ~/Library/Logs/claude-runner.log
```

**Notes:**
- **Use a LaunchAgent, not a LaunchDaemon.** Xcode, simulators, and the keychain need `USER` logged into a GUI session through Fast User Switching.
- **`.err` is where startup failures go.** Errors like "cannot create or write to base directory" print to stderr before the log file opens.

---

## 5. Using the runner
- **Start a session:** signed in as `ACCOUNT`, in the Claude app or claude.ai/code, pick **`ENV_NAME`** in the environment picker.
- **From a terminal:** run `/remote-env` once to make it the default, then `claude --cloud "…"`.
- **Choose every repo up front.** A private repo can't be added mid-session.
- **Commit often.** `--push-outcome-on-release` preserves committed work only, not a dirty working tree.

---

## 6. Operations

| Task | How |
|---|---|
| Diagnose | As `USER`: `claude self-hosted-runner doctor` (local health, metrics, log). For queue and environment status, check the admin page. |
| Watch activity | `tail -f ~/Library/Logs/claude-runner.log` |
| Restart or upgrade | As `ADMIN`: `brew upgrade claude-code@latest` (upgrade only). Then as `USER`: `launchctl kickstart -k gui/$(id -u)/local.claude.runner` |
| Rotate key | Owner: environment → **Configuration** → new key. As `USER`: replace `~/.claude-runner/environment-secret`, kickstart the job. Owner: revoke the old key. |
| Add parallelism | Create `ORG-runner-2` (repeat §1, §3, §4 with the new `USER`; same key, same plist, same `--base-dir` path shape) |
| Remove the runner | `launchctl bootout gui/$(id -u)/local.claude.runner`, delete the plist and secret, then revoke the key |
| Sessions stay queued | The runner is down, the Mac user is logged out, or the session was started by a different account than `ACCOUNT` |

---

## 7. Security notes
- **Anyone in the org can dispatch** to `ENV_NAME`. `--lock-to-account` only ensures their sessions never run here.
- **Never drop `--lock-to-account`.** At capacity 1 the runner keeps one clone per repo under `--base-dir` and reuses it across sessions. That's only safe while every session belongs to `ACCOUNT`.
- **Sessions can read the key file.** Rotate the key after any suspicious session. On-demand runners are the documented way to keep the key off the host that runs sessions.
- **Connector traffic** (claude.ai connectors such as GitHub, Slack, Linear) runs through Anthropic, not this Mac.
- **Keep `USER` free of credentials** beyond the key file, and keep other users' homes locked (README §B5).

## Sources
- [Claude Code Docs — Self-hosted environments](https://code.claude.com/docs/en/self-hosted-environments)
- [Claude Code Docs — Self-hosted quickstart](https://code.claude.com/docs/en/self-hosted-environments-quickstart)
- [Claude Code Docs — Deploy self-hosted environments](https://code.claude.com/docs/en/self-hosted-environments-deploy)
