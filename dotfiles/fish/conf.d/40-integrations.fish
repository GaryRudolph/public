# Tool integrations: Homebrew, Java, Gradle, Maven, Android, gcloud, VS Code,
# Rust/Cargo, pnpm. Each block guards on the tool actually being installed.

# --- Homebrew -----------------------------------------------------------------
if test -x /opt/homebrew/bin/brew
    /opt/homebrew/bin/brew shellenv fish | source
end

# --- Java ---------------------------------------------------------------------
set -l _java_candidates \
    "/Applications/Android Studio.app/Contents/jbr/Contents/Home" \
    "$HOMEBREW_HOME/opt/openjdk"
for _j in $_java_candidates
    if test -d "$_j"
        set -gx JAVA_HOME "$_j"
        fish_add_path -gP "$_j/bin"
        break
    end
end

# --- Gradle -------------------------------------------------------------------
set -l _gradle "$TOOLS_HOME/gradle-3.0"
if test -d "$_gradle"
    set -gx GRADLE_HOME "$_gradle"
    fish_add_path -gP "$_gradle/bin"
end

# --- Maven --------------------------------------------------------------------
set -l _maven "$TOOLS_HOME/apache-maven-3.3.9"
if test -d "$_maven"
    set -gx MAVEN_HOME "$_maven"
    set -gx MAVEN_OPTS "-server -Xmx2048m -XX:MaxPermSize=512m"
    fish_add_path -gP "$_maven/bin"
end

# --- Android SDK / NDK --------------------------------------------------------
set -l _android_sdk "$HOME/Library/Android/sdk"
if test -d "$_android_sdk"
    set -gx ANDROID_SDK_ROOT "$_android_sdk"
    set -gx ANDROID_HOME     "$_android_sdk"
    fish_add_path -gP \
        "$_android_sdk/emulator" \
        "$_android_sdk/platform-tools" \
        "$_android_sdk/cmdline-tools/latest/bin"
end

set -l _android_ndk "$TOOLS_HOME/android-ndk-r9"
if test -d "$_android_ndk"
    set -gx ANDROID_NDK_HOME "$_android_ndk"
    fish_add_path -gP "$_android_ndk"
end

# --- Google Cloud SDK ---------------------------------------------------------
set -l _gcloud "$TOOLS_HOME/google-cloud-sdk"
if test -d "$_gcloud"
    set -gx GCLOUD_HOME "$_gcloud"
    fish_add_path -gP "$_gcloud/bin"

    test -f "$_gcloud/path.fish.inc";       and source "$_gcloud/path.fish.inc"
    test -f "$_gcloud/completion.fish.inc"; and source "$_gcloud/completion.fish.inc"
end

# --- VS Code ------------------------------------------------------------------
set -l _vscode "/Applications/Visual Studio Code.app"
if test -d "$_vscode"
    set -gx VSCODE_HOME "$_vscode"
    fish_add_path -gP "$_vscode/Contents/Resources/app/bin"
end

# --- Rust / Cargo -------------------------------------------------------------
set -l _rustup "$HOME/.rustup"
test -d "$_rustup"; and set -gx RUSTUP_HOME "$_rustup"

set -l _cargo "$HOME/.cargo"
if test -d "$_cargo"
    set -gx CARGO_HOME "$_cargo"
    test -f "$_cargo/env.fish"; and source "$_cargo/env.fish"
end

# --- pnpm ---------------------------------------------------------------------
set -gx PNPM_HOME "$HOME/Library/pnpm"
test -d "$PNPM_HOME"; and fish_add_path -gP "$PNPM_HOME"
