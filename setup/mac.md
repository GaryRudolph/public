# Mac Setup

- Set Hostname
  - Replace `gMacBook` with this machine's name; the dotfiles pick per-machine
  files by `hostname -s`
  - Settings -> General -> Sharing
  - Settings -> About -> Set Local Hostname

  ```bash
  sudo scutil --set HostName gMacBook
  sudo scutil --set LocalHostName gMacBook
  sudo scutil --set ComputerName gMacBook
  ```

- Make sure Desktop & Documents are set to iCloud
  - Settings -> Apple Account -> iCloud -> Drive -> turn on Desktop & Documents Folders
  - Settings -> Apple Account -> iCloud -> Drive -> turn off Optimize Mac Storage (keep all files local)
- See hidden files as greyed out in Finder

  ```bash
  defaults write com.apple.finder AppleShowAllFiles TRUE; killall Finder
  ```

- Setup SSH Keys
  - Note, these have to be copied and not symlink because SSH requirements

  ```bash
  mkdir ~/.ssh
  chmod 700 ~/.ssh
  ```

  - Download `id_ed25519` and `id_ed25519.pub` from the private repo's
  [keys](https://github.com/GaryRudolph/private/tree/main/keys) folder via the
  GitHub website (no SSH yet) and place them in `~/.ssh`

  ```bash
  chmod 600 ~/.ssh/id_ed25519
  chmod 644 ~/.ssh/id_ed25519.pub
  ```

- Install Homebrew and fish (prereq for the symlinks and chsh tasks below)
  - Install Homebrew if not already present: see [https://brew.sh](https://brew.sh)

  ```bash
  brew install fish
  ```

- Checkout this repo to `Projects/personal/public` and create Symbolic Links

  ```bash
  mkdir -p ~/Projects/personal && cd ~/Projects/personal
  git clone git@github.com:GaryRudolph/public.git
  ```

  - Create this machine's per-host files if they don't exist yet (commit them
  afterwards)

  ```bash
  cd ~/Projects/personal/public/dotfiles
  [ -e "zshrc-$(hostname -s)" ] || printf '#!/bin/zsh\n\n' > "zshrc-$(hostname -s)"
  [ -e "fish/host/$(hostname -s).fish" ] || \
    sed "s/gMacBook/$(hostname -s)/" fish/host/gMacBook.fish \
    > "fish/host/$(hostname -s).fish"
  ```

  ```bash
  cd ~
  ln -s Projects/personal/public/bin bin
  ln -s Projects/personal/public/dotfiles/zshrc .zshrc
  ln -s "Projects/personal/public/dotfiles/zshrc-$(hostname -s)" .zshrc-local
  [ -e .exrc ] && [ ! -L .exrc ] && mv .exrc .exrc.bak
  ln -snf Projects/personal/public/dotfiles/exrc .exrc
  mkdir -p ~/.config
  [ -e ~/.config/fish ] && mv ~/.config/fish ~/.config/fish.bak
  ln -s ~/Projects/personal/public/dotfiles/fish ~/.config/fish
  ```

  - See `dotfiles/fish/README.md` for prompt/config details.
- Git identity per directory tree (built-in `includeIf`; see
[dotfiles/git/README.md](../dotfiles/git/README.md))
  - `~/.gitconfig` sets the name and personal email (`GaryRudolph@mac.com`);
  repos under `~/Projects/{lolay,agerpoint,nowline,deskhound}/` get that
  company's email from fragments in `~/.config/git/`
  - Link the base config (backs up any existing `~/.gitconfig`)

  ```bash
  cd ~
  [ -e .gitconfig ] && [ ! -L .gitconfig ] && mv .gitconfig .gitconfig.bak
  ln -snf Projects/personal/public/dotfiles/gitconfig .gitconfig
  ```

  - The company fragments are linked by `make install` in the dotfiles
  step below
- Make fish the default login shell
  - Confirm the path (typically `/opt/homebrew/bin/fish`)

  ```bash
  which fish
  ```

  ```bash
  grep -q "$(which fish)" /etc/shells || echo "$(which fish)" | sudo tee -a /etc/shells
  chsh -s "$(which fish)"
  ```

  - Open a new terminal and verify

  ```bash
  echo $SHELL
  ```

- Configure AI agent tools (see [agents/README.md](../agents/README.md))

  ```bash
  cd ~/Projects/personal/public/agents && make install
  ```

- Install dotfiles symlinks (git, Ghostty, OpenCode; see
[dotfiles/opencode/README.md](../dotfiles/opencode/README.md))
  - Install OpenCode (`brew install opencode` or the official installer)

  ```bash
  cd ~/Projects/personal/public/dotfiles && make install
  ```

  - Verify git identity from inside any repo (shows which file set it)

  ```bash
  git config --show-origin user.email
  ```

  - One-time auth per profile

  ```bash
  opencode auth login
  ```

  ```bash
  OPENCODE_APPNAME=opencode-agerpoint opencode auth login
  ```

- Checkout the private repo to `Projects/personal/private` and
create Symbolic Links

  ```bash
  cd ~/Projects/personal
  git clone git@github.com:GaryRudolph/private.git
  ```

  ```bash
  ln -snf ~/Projects/personal/private/dotfiles/fish ~/.config/fish-private
  ```

- Standard Software
  - Dropbox
  - Google Drive
  - Chrome
  - Ghostty (config is linked by the dotfiles `make install` step)
  - Slack
  - Zoom
  - Claude
  - ChatGPT
  - Cursor
  - Jabra Direct
  - Parallels
  - Adobe Reader, Illustrator, Photoshop
  - OrbStack (Docker runtime; fish config wires up its `docker` and
  completions)
  - Visual Studio Code
  - Android Studio (fish uses its bundled JDK for `JAVA_HOME`); install the NDK
  from its SDK Manager and the shells pick up the newest one
  - Microsoft Office
  - [SF Symbols App](https://developer.apple.com/sf-symbols/)
  - Bambu Studio
  - Autodesk Fusion
  - KiCad
  - Garmin Aviation Database Manager
  - LG Screen Manager?
  - Omnigraffle
  - Whispr Flow
  - Signal
  - WhatsApp
- (Optional) Build branded multi-account launchers
(see [macos-launchers/README.md](../macos-launchers/README.md))
  - Prereqs: Cursor.app and Claude.app (Standard Software above) plus
  `brew install imagemagick` (Brew section below)
  - Add your profile: `macos-launchers/profiles/<slug>.env` and `<slug>.png`

  ```bash
  cd ~/Projects/personal/public/macos-launchers && make install
  ```

  - Wrappers (e.g. `Cursor AP.app`, `Claude AP.app`) land in `~/Applications/`
- Install Xcode
  - Install App & SDKs

  ```bash
  xcode-select --install
  ```

- Brew (/opt/homebrew) (Pick and choose, `brew install <package>`)

  ```bash
  brew install python3
  ```

  ```bash
  brew install virtualenv
  ```

  ```bash
  brew install uv
  ```

  ```bash
  brew install plantuml
  ```

  ```bash
  brew install graphviz
  ```

  ```bash
  brew install librsvg
  ```

  ```bash
  brew install node
  ```

  - nvm (fish wraps it; needs `~/.nvm` to exist)

  ```bash
  brew install nvm
  mkdir -p ~/.nvm
  ```

  - pnpm (fish sets `PNPM_HOME` to `~/Library/pnpm`; skip `pnpm setup`, which
  would append to the symlinked shell configs in this repo)

  ```bash
  brew install pnpm
  mkdir -p ~/Library/pnpm
  ```

  ```bash
  brew install s3cmd
  ```

  ```bash
  brew install fastlane
  ```

  ```bash
  brew install jq
  ```

  ```bash
  brew install mdless
  ```

  ```bash
  brew install awscli
  ```

  - imagemagick (also a prereq for `macos-launchers`)

  ```bash
  brew install imagemagick
  ```

  - Animate Gifs and Video

  ```bash
  brew install ffmpeg
  ```

  - Protobuf

  ```bash
  brew install protobuf swift-protobuf grpc-swift
  ```

  ```bash
  brew install rar
  ```

  ```bash
  brew install openjdk
  ```

  ```bash
  brew install gradle
  ```

  ```bash
  brew install maven
  ```

  - timeout (provided by coreutils as `gtimeout`)

  ```bash
  brew install coreutils
  ```

  ```bash
  brew install xprojectlint
  ```

  ```bash
  brew install xcodegen
  ```

  ```bash
  brew install xcbeautify
  ```

  - Wireshark

  ```bash
  brew install --cask wireshark wireshark-chmodbpf
  ```

  ```bash
  brew install go
  ```

  - mactex-no-gui (this is a cask)

  ```bash
  brew install --cask mactex-no-gui
  ```

  - Terraform

  ```bash
  brew tap hashicorp/tap
  brew install hashicorp/tap/terraform
  ```

  - triage (environment doctor) from the Lolay tap; trust the whole tap so
  future formulae from it load without another prompt

  ```bash
  brew tap lolay/tap
  brew trust --tap lolay/tap
  brew install lolay/tap/triage
  ```

- Gems (`gem install <package>`)
  - Intentional global exception to the `bundle exec` rule: these are
  standalone CLI tools used outside any project Gemfile

  ```bash
  gem install xcperfect
  ```

  ```bash
  gem install xcpretty
  ```

- NPM (`npm install -g <package>`)
  - Intentional global exception to the `npx` rule: `firebase` is a
  standalone CLI used across projects

  ```bash
  npm install -g firebase-tools
  ```

- VS Code
  - joaompinto.vscode-graphviz
  - jebbs.plantuml
  - naumovs.color-highlight
  - mhutchie.git-graph
  - yzhang.markdown-all-in-one
  - ms-python.python
  - ms-python.vscode-pylance
  - kasik96.swift
  - redhat.vscode-xml
  - redhat.vscode-yaml
- Cursor
  - ⌘↩ submits, ↩ new line
    - Open Cursor Settings (`⇧⌘J`) → Chat → enable  
    "Submit message with ⌘↩"
  - Optional keybindings overrides (User → `keybindings.json`):
    - `cmd+i` (⌘I) → `composerMode.agent` (open agent composer)
    - `alt+cmd+s` (⌥⌘S) → `workbench.action.toggleUnifiedSidebarFromKeyboard`
- Google Cloud CLI (fish expects it in `~/Applications/google-cloud-sdk`;
fish adds it to PATH, so skip the installer's PATH update)

  ```bash
  mkdir -p ~/Applications && cd ~/Applications
  curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-darwin-arm.tar.gz
  tar -xzf google-cloud-cli-darwin-arm.tar.gz && rm google-cloud-cli-darwin-arm.tar.gz
  ./google-cloud-sdk/install.sh --quiet --path-update false \
    --command-completion false
  ```

- Rust (official rustup installer; fish sources `~/.cargo/env.fish` itself, so
`--no-modify-path` keeps rustup from writing into the symlinked shell configs)

  ```bash
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- --no-modify-path
  ```

- Per-company logins (one-time; see "One-time per-context bootstrapping" in
[dotfiles/fish/README.md](../dotfiles/fish/README.md))
  - Needs the Google Cloud CLI, `awscli`, and `firebase-tools` from above
  - Google Cloud: CLI login and application-default login (for Terraform) per
  company, each in its own config dir

  ```fish
  for ctx in agerpoint nowline deskhound
      env CLOUDSDK_CONFIG=$HOME/.config/gcloud-$ctx gcloud auth login
      env CLOUDSDK_CONFIG=$HOME/.config/gcloud-$ctx \
          gcloud auth application-default login
  end
  ```

  - AWS: one named profile per company (the fish context sets `AWS_PROFILE`)

  ```bash
  aws configure --profile agerpoint
  ```

  ```bash
  aws configure --profile lolay
  ```

  - Firebase: signed in to each company's Firebase account, generate a CI token
  and paste it as `export FIREBASE_TOKEN=...` into
  `~/Projects/personal/private/dotfiles/<ctx>/firebase.env` (nowline,
  deskhound), then run `context reload`

  ```bash
  firebase login:ci
  ```

  - Claude Code for the Agerpoint account: sign in once in its own config dir

  ```bash
  claude-agerpoint
  ```

  - Claude Desktop for Agerpoint (first sign-in only): quit Claude Desktop,
  temporarily set Safari as the default browser, open `Claude AP.app` and sign
  in, then switch the default browser back (see the `claude://` sign-in note in
  [macos-launchers/README.md](../macos-launchers/README.md))
- Windows Parallels
  - Windows 11 ARM Build
  - Garmin Checklist Editor
  - VP-X
