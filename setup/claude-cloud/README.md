# Claude Cloud Environments

Setup scripts for Claude Code cloud environments (claude.ai/code). Pick a
variant, copy its block, and paste it into the environment's **Setup script**:
the cloud environment menu in a session's title bar, then **Edit**. New
sessions run it as root on the default Ubuntu image; running sessions don't.

Each block is complete on its own, so one paste covers a variant. Amazon and
Google start with Base's lines; when Base changes, copy the change into them.

Every tool installs its latest release when the session starts. GitHub tools
find their latest tag from the redirect on `releases/latest/download/`,
because the cloud proxy blocks GitHub's API and the `releases/latest` page for
repos outside the session but lets release downloads through.

Mac work runs on the [self-hosted runner](../mac/claude/runner.md) instead, so
nothing here covers macOS. Diagram tools (graphviz, plantuml, librsvg) belong
in a repo's own setup, not here. Scripts are x86_64 only, which is what cloud
containers run today.

## Base

Any development: `triage`.

```bash
#!/bin/bash
set -euo pipefail
tmp=$(mktemp -d)
latest_tag() {
  curl -fsS -o /dev/null -w '%{redirect_url}' "https://github.com/$1/releases/latest/download/x" \
    | sed -E 's|.*/download/([^/]+)/x$|\1|'
}

# triage (environment doctor), checked against its release checksums
v=$(latest_tag lolay/triage)
f="triage_${v#v}_linux_amd64.tar.gz"
curl -fsSL -o "$tmp/$f" "https://github.com/lolay/triage/releases/download/$v/$f"
curl -fsSL -o "$tmp/checksums.txt" "https://github.com/lolay/triage/releases/download/$v/checksums.txt"
(cd "$tmp" && sha256sum -c --ignore-missing checksums.txt)
tar -xzf "$tmp/$f" -C /usr/local/bin triage

rm -rf "$tmp"
```

## Amazon

Base, plus `protoc`, `terraform`, and `aws`.

```bash
#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
tmp=$(mktemp -d)
latest_tag() {
  curl -fsS -o /dev/null -w '%{redirect_url}' "https://github.com/$1/releases/latest/download/x" \
    | sed -E 's|.*/download/([^/]+)/x$|\1|'
}

# triage (environment doctor), checked against its release checksums
v=$(latest_tag lolay/triage)
f="triage_${v#v}_linux_amd64.tar.gz"
curl -fsSL -o "$tmp/$f" "https://github.com/lolay/triage/releases/download/$v/$f"
curl -fsSL -o "$tmp/checksums.txt" "https://github.com/lolay/triage/releases/download/$v/checksums.txt"
(cd "$tmp" && sha256sum -c --ignore-missing checksums.txt)
tar -xzf "$tmp/$f" -C /usr/local/bin triage

# protoc (Ubuntu's protobuf-compiler is 3.21, from 2022)
v=$(latest_tag protocolbuffers/protobuf)
curl -fsSL -o "$tmp/protoc.zip" \
  "https://github.com/protocolbuffers/protobuf/releases/download/$v/protoc-${v#v}-linux-x86_64.zip"
unzip -q -o "$tmp/protoc.zip" -d /usr/local bin/protoc 'include/*'

# terraform from HashiCorp's apt repo
curl -fsSL https://apt.releases.hashicorp.com/gpg \
  | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(. /etc/os-release && echo "$VERSION_CODENAME") main" \
  > /etc/apt/sources.list.d/hashicorp.list
apt-get update -qq
apt-get install -y -qq terraform

# aws CLI v2
curl -fsSL -o "$tmp/awscli.zip" https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip
unzip -q "$tmp/awscli.zip" -d "$tmp"
"$tmp/aws/install" --update

rm -rf "$tmp"
```

## Google

Base, plus `protoc`, `terraform`, `gcloud`, and `firebase`. The default image
ships an older `gcloud` under `/opt/google-cloud-sdk`, so the script updates
it in place, and installs it from Google's apt repo only when it's missing.

```bash
#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
tmp=$(mktemp -d)
latest_tag() {
  curl -fsS -o /dev/null -w '%{redirect_url}' "https://github.com/$1/releases/latest/download/x" \
    | sed -E 's|.*/download/([^/]+)/x$|\1|'
}

# triage (environment doctor), checked against its release checksums
v=$(latest_tag lolay/triage)
f="triage_${v#v}_linux_amd64.tar.gz"
curl -fsSL -o "$tmp/$f" "https://github.com/lolay/triage/releases/download/$v/$f"
curl -fsSL -o "$tmp/checksums.txt" "https://github.com/lolay/triage/releases/download/$v/checksums.txt"
(cd "$tmp" && sha256sum -c --ignore-missing checksums.txt)
tar -xzf "$tmp/$f" -C /usr/local/bin triage

# protoc (Ubuntu's protobuf-compiler is 3.21, from 2022)
v=$(latest_tag protocolbuffers/protobuf)
curl -fsSL -o "$tmp/protoc.zip" \
  "https://github.com/protocolbuffers/protobuf/releases/download/$v/protoc-${v#v}-linux-x86_64.zip"
unzip -q -o "$tmp/protoc.zip" -d /usr/local bin/protoc 'include/*'

# terraform from HashiCorp's apt repo; gcloud from Google's if the image lacks it
codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
curl -fsSL https://apt.releases.hashicorp.com/gpg \
  | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $codename main" \
  > /etc/apt/sources.list.d/hashicorp.list
packages=(terraform)
if command -v gcloud >/dev/null; then
  gcloud components update --quiet
else
  curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | gpg --dearmor --yes -o /usr/share/keyrings/cloud.google.gpg
  echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    > /etc/apt/sources.list.d/google-cloud-sdk.list
  packages+=(google-cloud-cli)
fi
apt-get update -qq
apt-get install -y -qq "${packages[@]}"

# firebase CLI, standalone binary (bundles its own Node)
curl -fsSL -o /usr/local/bin/firebase \
  https://github.com/firebase/firebase-tools/releases/latest/download/firebase-tools-linux
chmod +x /usr/local/bin/firebase

rm -rf "$tmp"
```
