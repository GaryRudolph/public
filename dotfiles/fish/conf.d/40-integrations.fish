# Tool integrations: Homebrew, Java, Gradle, Maven, Android, gcloud, VS Code,
# Rust/Cargo, pnpm, nvm, OrbStack. Each block guards on the tool actually being installed.

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

# --- Gradle / Maven -----------------------------------------------------------
# Homebrew already puts gradle/mvn on PATH; the *_HOME vars are for IDEs and
# build tools that look for them. opt/<name> always points at the current version.
set -l _gradle "$HOMEBREW_HOME/opt/gradle/libexec"
test -d "$_gradle"; and set -gx GRADLE_HOME "$_gradle"

set -l _maven "$HOMEBREW_HOME/opt/maven/libexec"
if test -d "$_maven"
    set -gx MAVEN_HOME "$_maven"
    set -gx MAVEN_OPTS "-Xmx2048m"
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

# Newest NDK installed via Android Studio's SDK Manager (ndk/<version>/).
set -l _android_ndks $_android_sdk/ndk/*/
if set -q _android_ndks[1]
    set -l _android_ndk (printf '%s\n' $_android_ndks | sort -V | tail -n 1 | string trim -r -c /)
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

# --- nvm (Node Version Manager) -----------------------------------------------
set -gx NVM_DIR "$HOME/.nvm"
set -l _nvm_sh "/opt/homebrew/opt/nvm/nvm.sh"
if test -s "$_nvm_sh"
    function nvm --wraps nvm --description 'Node Version Manager'
        # nvm is a bash function; run it in bash and sync the updated PATH back
        set -l _tmp (mktemp)
        bash -c "source /opt/homebrew/opt/nvm/nvm.sh --no-use; nvm $argv; printf '%s' \"\$PATH\" > $_tmp"
        set -l _new_path (cat $_tmp)
        rm -f $_tmp
        test -n "$_new_path"; and set -gx PATH (string split : "$_new_path")
    end
end

# --- OrbStack (Docker / Kubernetes / Linux VMs) -------------------------------
# OrbStack ships its own `docker`, `kubectl`, `orbctl` binaries in ~/.orbstack
# and fish completions inside the app bundle. We bypass OrbStack's installer
# append (which sources a generated ~/.orbstack/shell/init2.fish with a
# hardcoded /Users/<name> path) so this stays portable across machines.
set -l _orbstack "$HOME/.orbstack"
if test -d "$_orbstack"
    fish_add_path -aP "$_orbstack/bin"
end

set -l _orbstack_completions "/Applications/OrbStack.app/Contents/Resources/completions/fish"
test -d "$_orbstack_completions"; and set -p fish_complete_path "$_orbstack_completions"
