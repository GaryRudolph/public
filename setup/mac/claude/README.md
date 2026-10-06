# Claude Agent Host (Mac)

Sets up a Mac as an always-on host for Claude agents. Each org gets its own Standard macOS user. That user runs a [self-hosted runner](runner.md), a [Remote Control](remote-control.md) server, or both, signed in to that org's Claude account only.

Part A is done **once per Mac**. Part B is done **once per macOS user** that runs a runner or Remote Control. Everything is done as `ADMIN` unless noted.

## Which one?

| | [Self-hosted runner](runner.md) | [Remote Control](remote-control.md) |
|---|---|---|
| What runs here | Cloud sessions started at claude.ai/code | Local Claude Code sessions you steer from the Claude app or a browser |
| Claude plan | Team or Enterprise (public beta) | Pro, Max, Team, or Enterprise |
| Claude login in `USER` | ❌ Never; an environment key authenticates it | ✅ Required |
| Git credential in `USER` | ❌ None; the Anthropic Git proxy uses the session creator's GitHub | ✅ Fine-grained token |
| Admin setting | Allow self-hosted environments, then create one | Remote Control toggle (Team/Enterprise only) |
| launchd label | `local.claude.runner` (runs `claude` directly) | `local.claude.rc` (runs tmux and a script) |

Both need §A and §B below, a GUI login kept alive through Fast User Switching, and a LaunchAgent in `~/Library/LaunchAgents`.

## Placeholders

Used by all three docs. Labels, plist files, and log files are the same in every user; the owning user shows which org a job is for.

| Placeholder | Meaning | Example |
|---|---|---|
| `HOST` | This Mac's short name | `hangar` |
| `ADMIN` | Admin user that owns Homebrew and SSH | `gary` |
| `ORG` | Claude org slug, or `personal` for a Pro/Max account | `acme` |
| `USER` | macOS short name for the runner or agent user | `acme-runner`, `acme-agent` |
| `ACCOUNT` | The one Claude account used in `USER` | `you@example.com` |
| `REPO` | Repository folder under `~/code` (Remote Control) | `widgets` |
| `GH_OWNER` | GitHub org or user that owns the repo | `acme` |
| `ENV_NAME` | Self-hosted environment name in claude.ai (runner) | `hangar (you only)` |

---

## A. Once per Mac

### A1. Name the machine
```bash
sudo scutil --set ComputerName HOST
sudo scutil --set HostName HOST
sudo scutil --set LocalHostName HOST
```
In the Tailscale admin console, rename the machine to `HOST`.

### A2. Admin account
`ADMIN` can follow the [workstation setup](../README.md) for Homebrew, fish, and dotfiles. On an agent host, **skip** iCloud Desktop & Documents, the personal SSH private key, the private repo, and the per-company logins. Agent sessions run arbitrary commands, so nothing on this Mac should hold credentials beyond what each agent user needs.

### A3. Never sleep on power
```bash
sudo pmset -c sleep 0 disksleep 0 displaysleep 10 womp 1
pmset -g            # verify: sleep 0, womp 1 on AC
```
- System Settings → Battery → Options → **Prevent automatic sleeping on power adapter when the display is off**: on.
- On a laptop, keep **Optimized Battery Charging** on, or cap the charge at ~80% with AlDente. It's plugged in all the time, so check periodically for battery swelling.

### A4. Display and network
- **HDMI dummy plug** (e.g., DTECH 4K) in the HDMI port. With power and the plug connected, a laptop lid can stay closed.
- **Resolution:** System Settings → Displays → **1920×1080**.
- **Network:** wired Ethernet rather than Wi-Fi.

### A5. Remote access
- **Tailscale:** install it, sign in, and turn on MagicDNS so `ssh ADMIN@HOST` works from anywhere.
- **Screen Sharing:** System Settings → General → Sharing → on.
- **Remote Login (SSH):** on, with "Allow access for: **Only these users**" set to `ADMIN`.
- **Keys-only SSH.** Create `/etc/ssh/sshd_config.d/100-hardening.conf`:
  ```
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  PermitRootLogin no
  ```
  Add your laptop's public key to `~ADMIN/.ssh/authorized_keys`, then reload and verify:
  ```bash
  sudo launchctl kickstart -k system/com.openssh.sshd
  sudo sshd -T | grep -Ei 'passwordauth|kbdinteractive|permitroot'   # all "no"
  ```

### A6. Multi-user sessions
- **Fast User Switching:** System Settings → Control Center → Fast User Switching → **Show in Menu Bar**. It lets several users stay logged in at once. Runners and Remote Control both need their user logged into a GUI session for Xcode, simulators, and the keychain.

### A7. Reboots
- **FileVault:** keep it on. For planned restarts, use `sudo fdesetup authrestart` so the disk unlocks once.
- **After any reboot,** log in each runner and agent user via Fast User Switching so their launchd jobs start.
- **Unplanned reboots don't recover on their own.** After a power loss or kernel panic, the Mac waits at the FileVault unlock screen, and nothing runs until you unlock it and log in each user. A small UPS avoids the common case.
- **Automatic macOS updates:** System Settings → General → Software Update → Automatic Updates → turn **off** "Install macOS updates". An overnight update reboots and logs everyone out. Update by hand instead.

### A8. Shared tools (Homebrew, as `ADMIN`)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install tmux gh git
brew install --cask claude-code@latest
claude --version        # runners need v2.1.224+
git --version           # git proxy needs 2.32+; --configure-git needs 2.34+
```
- **One shared copy:** `/opt/homebrew/bin/claude` serves every user, so there's one version to maintain. The launchd jobs call it by absolute path and leave `~/.local/bin` off `PATH`, so a stray per-user install can't shadow it.
- **Upgrading:** `brew upgrade claude-code@latest`, then restart each job (§C).
- **Why `@latest`:** it tracks the `latest` release channel, so new runner and Remote Control features land as soon as they ship; the plain `claude-code` cask trails it by about a week. The two casks conflict, so install only one.

### A9. Xcode (if any user builds Apple-platform apps)
Install Xcode from the App Store, then:
```bash
sudo xcode-select -s /Applications/Xcode.app
sudo xcodebuild -license accept
sudo xcodebuild -runFirstLaunch
```

---

## B. Once per macOS user (runner or agent)

### B1. Create the user
- **Where:** System Settings → Users & Groups → **Add User**.
- **Type:** **Standard**, not Administrator.
- **Full Name:** readable, e.g., "Acme Runner".
- **Short name (`USER`):** follow the naming convention below. Choose carefully; short names are hard to change later.

| Role | Short name | Example |
|---|---|---|
| Runner | `ORG-runner` | `acme-runner` |
| Extra runner for parallel sessions | `ORG-runner-N` | `acme-runner-2` |
| Agent (Remote Control + Claude desktop app) | `ORG-agent` | `acme-agent`; `ADMIN-agent` for a personal Pro/Max account |

### B2. First login
Log in as `USER` once through Fast User Switching and finish the macOS setup assistant.
- **Apple ID / iCloud:** **skip**. Nothing in these users should sync to iCloud.
- **Screen Time, Siri, analytics:** skip or off.

### B3. Verify tools
As `USER`, in Terminal:
```bash
which claude git tmux         # all under /opt/homebrew/bin
claude --version
xcodebuild -version           # if building Apple apps
```
If `USER` builds Apple apps, open Xcode once so it installs any per-user components.

### B4. Directories
```bash
mkdir -p ~/Library/Logs ~/Library/LaunchAgents
```

### B5. Isolate the home directory
Every local user is in the `staff` group, and the fish dotfiles set `umask 002`, so group-readable files are common. Lock each home down so one org's agent can't read another org's code or credentials. As `ADMIN`:
```bash
sudo chmod 700 /Users/USER
sudo chmod 700 /Users/ADMIN            # once
sudo -u OTHER_USER ls /Users/USER      # expect "Permission denied"
```

---

## C. Common operations

`LABEL` is `local.claude.runner` or `local.claude.rc`. The commands run as `USER`; from an SSH session as `ADMIN`, use the `sudo` form.

| Task | As `USER` | From SSH as `ADMIN` |
|---|---|---|
| Restart a job | `launchctl kickstart -k gui/$(id -u)/LABEL` | `sudo launchctl kickstart -k gui/$(id -u USER)/LABEL` |
| Stop a job | `launchctl bootout gui/$(id -u)/LABEL` | `sudo launchctl bootout gui/$(id -u USER)/LABEL` |
| Start a job | `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/LABEL.plist` | `sudo launchctl bootstrap gui/$(id -u USER) /Users/USER/Library/LaunchAgents/LABEL.plist` |
| See if a job is running | `launchctl print gui/$(id -u)/LABEL \| grep state` | `sudo launchctl print gui/$(id -u USER)/LABEL \| grep state` |
| Act as another user | | `sudo -iu USER` (GUI-dependent work still needs that user logged in via Fast User Switching) |
| Upgrade Claude Code | | `brew upgrade claude-code@latest`, then restart each user's job |
| Planned reboot | | `sudo fdesetup authrestart`, then log each user back in |
