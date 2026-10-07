---
name: personal-secrets
description: >-
  Run Gary's SOPS + age secrets repository (<estate>-secrets): set one up
  from a tested kit, add or edit a secret or signing file, grant or revoke
  a repo's access in access.map, mint, rotate, or retire a consumer's
  (repo, context) key, push SOPS_AGE_KEY to GitHub, wire a consumer repo's
  CI to read secrets with least privilege, and respond to a leaked key or
  value. Use for "set up a secrets repo", "add a secret", "give <repo>
  access to <file>", "rotate the key", "wire secrets into CI", "SOPS",
  "age key", or "SOPS_AGE_KEY".
---

# personal-secrets

The architecture and threat model are in
[`../personal-standards/standards/secrets/`](../personal-standards/standards/secrets/README.md);
read `README.md` there before first use. This skill is the procedure, plus a
tested kit in [`templates/secrets-repo/`](templates/secrets-repo/) that
implements the standard's Makefile contract.

## Ground rules

- **Never show a secret.** Don't print, echo, or paste secret values or
  private keys into the conversation, a commit, a PR, or a log. When you
  need to confirm a value, compare it (`cmp`, a hash) instead of displaying
  it. Refer to secrets by file and key name.
- **Maintainer work stays local.** Anything that reads `src/` or
  `keys/repos.env.sops` needs a maintainer age key on Gary's machine. Never
  suggest putting a source key in CI.
- **Ask before anything remote or irreversible.** `make set-keys`,
  `gh secret set` or `gh secret delete`, pushing the secrets repo, and
  deleting keys all need Gary's explicit go-ahead for that step.
- **Revocation isn't erasure.** Removing access or rotating a key stops
  future reads at HEAD; git history still holds old ciphertext. A value
  that may have leaked must also be rotated at its upstream provider.

## Start with the facts

```bash
bash scripts/secrets-facts.sh
```

Run it in the target repo. It reports whether that's a secrets repo or a
consumer, which tools and key sources exist (names only), the expanded
`access.map`, `src/` and `dist/` inventory, plaintext on disk, registry
identity names, keyless check results, and the consumer's workflow wiring.
It never prints values. Decide the next step from these facts.

## Procedures

### Set up a new secrets repo

1. Agree the estate boundary and name (`<org>/<estate>-secrets`) with Gary.
2. Copy the kit into a new private repo:
   `cp -R <this skill>/templates/secrets-repo/. <new-repo>/`.
3. Gary generates the break-glass key offline and keeps it offline. Only its
   public key goes into `breakglass.pub` and `.sops.yaml`.
4. Add maintainer public keys to `.sops.yaml`, and set `OWNER` in the
   Makefile.
5. `make init`, then `make doctor`.
6. Walk through the standard's setup runbook for the pieces outside the
   repo: branch protection and CODEOWNERS on `src/`, `access.map`, `keys/`,
   and `.githooks/`; and the read-only Secrets GitHub App with
   `contents: read`.

### Add or edit a secret

`make src-decrypt FILE=<f>`, then Gary edits the plaintext (or you do,
without echoing values), then `make src-encrypt FILE=<f>`. For a new file,
also add its line to `access.map`. Then `make build`, `make verify`, and
commit. The pre-commit hook refuses the commit if `src/` and `dist/` don't
pair up.

Binary files (`.p8`, `.p12`, certs, provisioning profiles) work the same
way; anything not named `*.env` is treated as binary.

### Grant or revoke access

Edit `access.map`, with groups defined above the lines that use them and no
inheritance. Then `make build`, `make verify`, and commit. `verify` fails if
anyone can decrypt a file they aren't granted.

### Add a consumer (repo, context)

1. `make mint REPO=<repo> CONTEXT=<actions|agents|codespaces|dependabot>`.
   Provision `actions` first; add other contexts only when a workflow there
   needs secrets. Give `agents` less than `actions` where possible.
2. Grant the identity in `access.map`, `make build`, `make verify`, commit.
3. With Gary's go-ahead: `CONFIRM_SET_KEYS=1 make set-keys REPO=<repo> CONTEXT=<ctx>`.
4. Wire the consumer (below).

### Wire a consumer repo's CI

Start from [`templates/consumer/secrets-steps.yml`](templates/consumer/secrets-steps.yml)
and keep only the narrowest decrypt step that works:

1. One key for one command: `make -C _secrets dist-decrypt-env KEY=NAME`
2. Export to the job environment: `... KEY=NAME FORMAT=dotenv >> "$GITHUB_ENV"`
   (or all env files the key can open)
3. Files on disk, only when a tool needs a file: `make -C _secrets dist-decrypt FILE=<f>`

The repo needs `vars.SECRETS_APP_ID`, `secrets.SECRETS_APP_PRIVATE_KEY`, and
its own `SOPS_AGE_KEY` in each store it uses.

### Rotate a consumer key

`make rotate REPO= CONTEXT=`, `make build`, `make verify`, commit, then with
Gary's go-ahead `CONFIRM_SET_KEYS=1 make set-keys REPO= CONTEXT=`. The old
key stops working at HEAD once the rebuilt `dist/` is pushed.

### Remove a consumer

Remove it from `access.map`, `make build`, then `make retire REPO= CONTEXT=`
(it refuses while the identity is still granted), commit, and, with Gary's
go-ahead, `gh secret delete SOPS_AGE_KEY -R <owner>/<repo> --app <ctx>`.

### Add or remove a maintainer

Edit the `age:` list in `.sops.yaml`, then
`sops updatekeys src/**/*.sops keys/repos.env.sops` and commit.

### A key or value leaked

1. **A consumer private key:** rotate it (above). Everything that key could
   decrypt, including in git history, is exposed, so rotate those values at
   their upstream providers too.
2. **A secret value:** revoke and reissue it at the upstream provider
   first, then update `src/`, `make build`, and commit. `git revert` doesn't
   un-leak anything.
3. **A maintainer key:** every consumer private key in `keys/repos.env.sops`
   is exposed. Remove the maintainer, rotate every consumer key, and rotate
   the secret values.

## The kit

`templates/secrets-repo/` implements the standard's Makefile contract, and
`tests/test-kit.sh` exercises every flow above in a sandbox (it needs `sops`
and `age`). It meets the two constraints in the standard's "Reference
implementation":

- `build.sh` runs `sops --config /dev/null` for `dist/`. With the committed
  `.sops.yaml`, sops otherwise refuses stdin with "no matching creation
  rules". It writes through a temp file, so a failed encrypt never leaves an
  empty `dist/` file behind.
- The scripts run under macOS's bash 3.2, with no associative arrays.

The kit also carries `verify` (grants, denials, and freshness, checked with
each consumer key), `retire`, a keyless `check.sh` shared by the hook and
CI, and `dist/` cleanup when a file leaves `access.map`.
