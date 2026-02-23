# Mac Setup

- [ ] See hidden files as greyed out in Finder
   * `defaults write com.apple.finder AppleShowAllFiles TRUE; killall Finder`

- [ ] Set Hostname
   * Settings -> General -> Sharing
   * Settings -> About -> Set Local Hostname
   * `sudo scutil --set HostName gMacBook`
   * `sudo scutil --set LocalHostName gMacBook.local`
   * `sudo scutil --set ComputerName gMacBook gMacBook`

- [ ] Make sure Documents are set to iCloud

- [ ] Setup SSH Keys
  * Note, these have to be copied and not symlink because SSH requirements
  * `mkdir ~/.ssh`
  * `chmod 700 ~/.ssh`
  * Download keys from [keys](keys) and place in `~/.ssh`
  * `chmod 600 ~/.ssh/id_ed25519`
  * `chmod 644 ~/.ssh/id_ed25519.pub`

- [ ] Checkout this repo to `Projects/personal/eng` and create Symbolic Links
  * `git clone git@github.com:GaryRudolph/eng.git`
  * `ln -s Projects/personal/eng/bin bin`
  * `ln -s Projects/personal/eng/dotfiles/zshrc .zshrc`
  * `ln -s Projects/personal/eng/dotfiles/zshrc-gMacBook .zshrc-local`
  * `cd .claude; ln -s ../Projects/personal/eng/standards/CLAUDE.md`

- Standard Software
  * [ ] Dropbox
  * [ ] Google Drive
  * [ ] Chrome
  * [ ] Slack
  * [ ] Zoom
  * [ ] Claude
  * [ ] ChatGPT
  * [ ] Jabra Direct
  * [ ] Parallels
  * [ ] Adobe Reader, Illustrator, Photoshop
  * [ ] Docker for Mac
  * [ ] Microsoft Office
  * [ ] [SF Symbols App](https://developer.apple.com/sf-symbols/)
  * [ ] Bambu Studio
  * [ ] Autodesk Fusion
  * [ ] KiCad
  * [ ] Garmin Aviation Database Manager
  * [ ] LG Screen Manager?
  * [ ] Omnigraffle
  * [ ] Whispr Flow
  * [ ] Signal
  * [ ] WhatsApp

- [ ] Install Xcode
  * [ ] Install App & SDKs
  * [ ] `sudo xcode-select --install`

- [ ] Brew (/opt/homebrew) (Pick and choose)
  * `brew install <package>`
  * `brew install python3`
  * `brew install virtualenv`
  * `brew install uv`
  * `brew install plantuml`
  * `brew install graphviz`
  * `brew install librsvg`
  * `brew install node`
  * `brew install s3cmd`
  * `brew install fastlane`
  * `brew install jq`
  * `brew install mdless`
  * `brew install awscli`
  * Animate Gifs and Video
      * `brew install imagemagick`
      * `brew install ffmpeg`
  * Protobuf
      * `brew install protobuf`
      * `brew install swift-protobuf`
      * `brew install grpc-swift`
  * `brew install rar`
  * `brew install openjdk`
  * `brew install gradle`
  * `brew install timeout`? If GUI, just install from app store
  * `brew install xprojectlint`
  * Wireshark
    * `brew install brew install --cask wireshark`
    * `brew install --cask wireshark-chmodbpf`
  * `brew install go`
  * `brew install mactex-no-gui` (this is a cask)
  * Terraform
    * `brew tap hashicorp/tap`
    * `brew install hashicorp/tap/terraform`

- [ ] Gems
  * `gem install <package>`
  * `gem install xcperfect`
  * `gem install xcpretty`

- [ ] NPM
  * `npm -g <package> install`
  * `npm -g firebase-tools install`

- [ ] VS Code
  * joaompinto.vscode-graphviz
  * jebbs.plantuml
  * naumovs.color-highlight
  * mhutchie.git-graph
  * yzhang.markdown-all-in-one
  * ms-python.python
  * ms-python.vscode-pylance
  * kasik96.swift
  * redhat.vscode-xml
  * redhat.vscode-yaml

- [ ] Cursor

- [ ] Rust

- Windows Parallels
  * Windows 11 ARM Build
  * Garmin Checklist Editor
  * VP-X