---
name: personal-secrets
description: >-
  Run SOPS + age secrets under the personal secrets standard, in either
  strategy: a private repo's own secrets/ folder (set it up from a tested
  kit, add or edit a secret in cleartext beside its ciphertext, add a person,
  mint a CI or environment key, give a privileged job such as terraform
  apply its own scope, sync a service's secrets to Secret Manager at deploy)
  or the estate's <estate>-secrets repo (grant or revoke a repo in
  access.map, mint, rotate or retire a (repo, context) key, push
  SOPS_AGE_KEY, wire a member's CI), plus moving a value to the estate and
  responding to a leaked key or value. Use for "set up secrets for this
  repo", "add a secret", "encrypt this .env", "give <repo> access to
  <file>", "rotate the key", "wire secrets into CI", "SOPS", "age key", or
  "SOPS_AGE_KEY".
---

# personal-secrets

The rules, the threat model, and when to use which strategy are in the
standard,
[`../personal-standards/standards/secrets/`](../personal-standards/standards/secrets/README.md);
read `README.md` there before first use. This skill is the procedure, plus two
tested kits that implement the standard's Makefile contracts:

- [`templates/single-repo/`](templates/single-repo/) for a private repo's own
  `secrets/` folder ([`single-repo.md`](../personal-standards/standards/secrets/single-repo.md)),
  the default.
- [`templates/secrets-repo/`](templates/secrets-repo/) for the estate repo
  ([`estate.md`](../personal-standards/standards/secrets/estate.md)).

A public repo gets neither: it uses OIDC, estate grants, or a plain GitHub
secret (the standard's "Public repos").

## Ground rules

- **Never show a secret.** Don't print, echo, or paste secret values or
  private keys into the conversation, a commit, a PR, or a log. When you
  need to confirm a value, compare it (`cmp`, a hash) instead of displaying
  it. Refer to secrets by file and key name.
- **Maintainer work stays local.** Anything that reads a whole scope, the
  estate's `src/`, or `keys/repos.env.sops` needs a maintainer age key on the
  Owner's machine. Never suggest putting a maintainer key in CI.
- **Ask before anything remote or irreversible.** `make set-keys`,
  `make secrets-mint`, `make secrets-sync` outside CI, `gh secret set` or
  `gh secret delete`, pushing the secrets repo, and
  deleting keys all need the Owner's explicit go-ahead for that step: a choice
  dialog where the harness has one (Claude Code's `AskUserQuestion`), its
  question naming the exact command, options `Run it` and `Not now`. A
  dismissed or declined dialog is a no.
- **Revocation isn't erasure.** Removing access or rotating a key stops
  future reads at HEAD; git history still holds old ciphertext. A value
  that may have leaked must also be rotated at its upstream provider.

## Start with the facts

```bash
bash scripts/secrets-facts.sh
```

Run it in the target repo. It reports whether that's an estate secrets repo,
a single repo with a `secrets/` folder, or a consumer; which tools and key
sources exist (names only); for a single repo, its scopes, key names,
ciphertext, cleartext on disk and deploy environments; for the estate, the
expanded `access.map`, `src/` and `dist/` inventory and registry identity
names; keyless check results; and the workflow wiring, GitHub environments
and secret names. It never prints values. Decide the next step from these
facts.

## Single-repo procedures

Run from the repo root. `FILE=` is a path under `secrets/` without `.sops`.

### Set up `secrets/` in a private repo

1. Confirm the repo is private (`gh repo view --json isPrivate`). If it's
   public, stop: the standard's "Public repos" applies.
2. Copy the kit: `scripts/secrets.sh` to `scripts/`, `secrets.mk` to the root,
   `secrets/.sops.yaml` and `secrets/README.md` to `secrets/`, and append
   `secrets.gitignore` to `.gitignore`. Add `include secrets.mk` to the
   Makefile after `SHELL := bash`, make `doctor` depend on `secrets-doctor`,
   and run `make secrets-check` in the pre-commit hook and in CI (with
   `ONLINE=1` in CI).
3. Agree the scopes with the Owner: `ci/`, one folder per deploy environment
   (each with a `deploy/<env>.env`), and one per privileged job that needs
   permissions other CI jobs mustn't have (below). Give each a creation rule
   in `.sops.yaml`.
4. Fill in public keys: the Owner's (anchor named for their GitHub login), the
   break-glass key the Owner generates offline (`&breakglass`), and the CI
   keys from `make secrets-mint` (next procedure). Fix the README's scope table.
5. `make secrets-doctor`, then `make secrets-check`.

### Add or edit a secret

1. Existing file: `make secrets-decrypt FILE=prod/api.env CONFIRM=1`. New
   file: write `secrets/<scope>/<consumer>.env` (or the binary file) directly.
   Name it for its consumer and its keys by the standard's "Naming". A value
   most consumers in the scope read goes in `<scope>/shared.env`; a consumer
   that needs a different value sets the same key in its own file, which wins.
2. The Owner edits the cleartext, or you do without echoing values. In a
   deploy environment, add a new key to the same file in every environment
   folder, or `secrets-check` fails.
3. `make secrets-encrypt FILE=prod/api.env`, then `make secrets-clean`.
4. Commit only `*.sops`; the gitignore refuses the cleartext.

Encrypting needs only public keys, so anyone can add a value. Decrypting a
file you only need in code is wrong: use `make -s secrets-env FILE= KEY=`.

### Add or remove a person

Add: their public key goes into the rules for the scopes they may open
(developers get `dev/` only), then `make secrets-updatekeys SCOPE=<scope>` for
each, run by a maintainer. Remove: delete the key from those rules, then
`make secrets-updatekeys SCOPE=<scope> ROTATE=1`. If their key may have
leaked, rotate the values it could open at their providers too.

### Mint a CI or environment key

1. With the Owner's go-ahead: `make secrets-mint CONTEXT=<ctx> CONFIRM_MINT=1`,
   where `<ctx>` is `actions` (repo-level, opens `ci/`), `env-<env>` (the
   GitHub environment `<env>`, opens the `<env>/` scope), or `agents`,
   `codespaces`, `dependabot`. The private half goes straight to GitHub;
   nothing is written to disk.
2. Add the printed public key to its scope's rule as `&<ctx>` (dashes become
   underscores), then `make secrets-updatekeys SCOPE=<scope>` and commit.
3. For an `env-<env>` key, make sure the GitHub environment has a deployment
   branch policy before anything sensitive goes into its scope.

Rotating a CI key is the same: mint again (it overwrites the GitHub secret),
swap the public key, and run updatekeys with `ROTATE=1`.

### Give a privileged job its own scope

When one CI job needs permissions the others mustn't have, such as
`terraform apply` against `terraform plan`:

1. Create a GitHub environment for it (`terraform-prod`) with a branch policy
   (`main` only), and required reviewers where the plan allows.
2. Add a scope with the same name to `.sops.yaml` and mint `env-terraform-prod`.
3. Put the job's write credentials in `secrets/terraform-prod/<consumer>.env`;
   the read-only ones the plan job uses stay in `ci/`.
4. The job declares `environment: terraform-prod`. Its cloud access comes
   from OIDC, bound to that environment's claim, not from sops.

### Wire CI

Start from [`templates/single-repo/ci-steps.yml`](templates/single-repo/ci-steps.yml)
and keep the narrowest step that works: one value for one command
(`make -s secrets-env FILE= KEY=`), then `FORMAT=dotenv >> "$GITHUB_ENV"`, then
`make secrets-decrypt FILE=` for a tool that needs a file, with
`make secrets-clean` in an `if: always()` step. `SOPS_AGE_KEY` goes on the
step, never the job.

### Wire a service's deploy

1. Infrastructure code creates one Secret Manager secret per key the service
   reads, named `<service>--<KEY>`, with no value, and grants the service's own
   service account read access to exactly those. The keys are the ones in
   `secrets/<env>/shared.env.sops` plus `secrets/<env>/<service>.env.sops`;
   their names are plaintext.
2. The deploy service account gets `secretVersionAdder` and `secretAccessor`
   on those secrets, and is the only principal with `serviceAccountUser` on
   the service's runtime account. The service never runs as the default
   compute account, and no runtime account holds a Secret Manager role on the
   project. Add the Policy Troubleshooter check from `gcp.md` "Runtime Secrets"
   to the infrastructure job, and turn on Secret Manager's Data Access audit
   logs.
3. The deploy job declares `environment: <env>`, loads `deploy/<env>.env`
   (which sets `GOOGLE_CLOUD_PROJECT`), and runs
   `make -s secrets-sync ENVIRONMENT=<env> SERVICE=<service> CONFIRM_SYNC=1`.
   It prints `KEY=<service>--KEY:<version>,...` for
   `gcloud run deploy --set-secrets`. A Firebase Functions codebase reads
   secrets by bare name: run its sync with `STORE_PREFIX=` set to empty.
4. A value the service shares with another repo is `@estate` in its file or
   in `shared.env`; check out the estate's `dist/` to `_secrets/` before the
   sync.

After changing `shared.env` in a deploy environment, redeploy every service in
that scope: each one picks the new value up only at its own sync.

### Move a value to the estate

When a second repo needs a value: add it to the estate's `src/<scope>/`,
grant both repos in `access.map`, `make build`, and wire both repos' CI to the
estate copy (`@estate` in a service file or `shared.env`). Then delete it from this repo's
`secrets/` in the same change set.

### Before making a private repo public

Move every value in `secrets/` to the estate, rotate each one at its
provider, then delete `secrets/`. The history goes public with the repo, so
deleting the folder alone exposes every past value to anyone with a future
key leak.

### A key or value leaked (single repo)

1. **A CI or environment key:** mint a replacement, remove the old public key,
   updatekeys with `ROTATE=1`, and rotate every value that scope holds at its
   provider, including signing certificates.
2. **A value:** revoke and reissue it at the provider, replace it in every
   file that holds it, encrypt, commit, and redeploy.
3. **A person's key:** remove it (above) and rotate the values its scopes
   held.

## Estate procedures

### Set up a new secrets repo

1. Agree the estate boundary and name (`<org>/<estate>-secrets`) with the Owner.
2. Copy the kit into a new private repo:
   `cp -R <this skill>/templates/secrets-repo/. <new-repo>/`.
3. The Owner generates the break-glass key offline and keeps it offline. Only its
   public key goes into `breakglass.pub` and `.sops.yaml`.
4. Add maintainer public keys to `.sops.yaml`, and set `OWNER` in the
   Makefile.
5. `make init`, then `make doctor`.
6. Walk through the standard's setup runbook for the pieces outside the
   repo: branch protection and CODEOWNERS on `src/`, `access.map`, `keys/`,
   and `.githooks/`; and the read-only Secrets GitHub App with
   `contents: read`.

### Add or edit a secret

`make src-decrypt FILE=<f>`, then the Owner edits the plaintext (or you do,
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

1. `make mint REPO=<repo> CONTEXT=<actions|env-<name>|agents|codespaces|dependabot>`.
   Provision `actions` first; add other contexts only when a workflow there
   needs secrets. `env-<name>` is the GitHub environment `<name>`, for a deploy
   or a privileged job (`env-prod`, `env-terraform-prod`); check that the
   environment has a branch policy before granting it anything. Give `agents`
   less than `actions` where possible.
2. Grant the identity in `access.map`, `make build`, `make verify`, commit.
3. With the Owner's go-ahead: `CONFIRM_SET_KEYS=1 make set-keys REPO=<repo> CONTEXT=<ctx>`.
4. Wire the consumer (below).

### Wire a consumer repo's CI

Start from [`templates/consumer/secrets-steps.yml`](templates/consumer/secrets-steps.yml)
and keep only the narrowest decrypt step that works:

1. One key for one command: `make -C _secrets dist-decrypt-env KEY=NAME`
2. Export to the job environment: `... KEY=NAME FORMAT=dotenv >> "$GITHUB_ENV"`
   (or all env files the key can open)
3. Files on disk, only when a tool needs a file: `make -C _secrets dist-decrypt FILE=<f>`

The repo needs `vars.SECRETS_APP_CLIENT_ID`, `secrets.SECRETS_APP_PRIVATE_KEY`, and
its own `SOPS_AGE_KEY` in each store it uses. A job that reads an
`env-<name>` grant declares `environment: <name>`, which is what hands it that
environment's key.

### Rotate a consumer key

`make rotate REPO= CONTEXT=`, `make build`, `make verify`, commit, then with
the Owner's go-ahead `CONFIRM_SET_KEYS=1 make set-keys REPO= CONTEXT=`. The old
key stops working at HEAD once the rebuilt `dist/` is pushed.

### Remove a consumer

Remove it from `access.map`, `make build`, then `make retire REPO= CONTEXT=`
(it refuses while the identity is still granted), commit, and, with the Owner's
go-ahead, the `gh secret delete` that `retire` prints (`--app <ctx>`, or
`--env <name>` for an `env-<name>` context).

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

## Scheduled rotation (both strategies)

The standard's "Rotation and break-glass" sets the schedule: regular keys every
9 months, break-glass every 12, never in the same change. `.sops.yaml` records
the month each key was minted; read it to see what's due. When a key is
due, tell the Owner which one and wait for a go-ahead before touching GitHub.

### Rotate the regular keys (every 9 months)

1. **People:** each maintainer and developer runs `age-keygen`, sends you the
   public half, and keeps the old key until step 4.
2. **CI keys:** single repo, `make secrets-mint CONTEXT=<ctx> CONFIRM_MINT=1`
   for each; estate, `make rotate REPO= CONTEXT=` for each consumer.
3. Swap the public keys and their `minted` comments, then re-wrap with a new
   data key: single repo, `make secrets-updatekeys ROTATE=1`; estate, the
   maintainer list in `.sops.yaml`, `sops updatekeys` and `sops rotate -i` on
   `src/**/*.sops` and `keys/repos.env.sops`, then `make build` and
   `make verify`. Commit and push; for the estate, then
   `CONFIRM_SET_KEYS=1 make set-keys`.
4. Drill break-glass (below), then ask everyone to destroy their old keys.

### Drill break-glass (at every regular rotation)

The Owner, holding the offline key, decrypts one file per scope to
`/dev/null`, so no value is shown:

- Single repo: `SOPS_AGE_KEY_FILE=<break-glass file> make -s secrets-env FILE=<scope>/<file>.env >/dev/null`
  for each scope.
- Estate: `SOPS_AGE_KEY_FILE=<break-glass file> sops -d --input-type dotenv --output-type dotenv <file> >/dev/null`
  on one `src/` and one `dist/` file per scope.

Report each scope's pass or fail. A failure is a break-glass rotation now, not
in a year.

### Rotate break-glass (every 12 months)

1. The Owner generates the new key offline and makes two copies for two
   custodians.
2. Add its public key beside the old one: single repo, as `&breakglass_next` in
   the first rule and `*breakglass_next` in the rest, then
   `make secrets-updatekeys`; estate, in `.sops.yaml`, then
   `sops updatekeys` on `src/` and `keys/`. For the estate, also replace
   `breakglass.pub` with it, then `make build`.
3. Drill the new key (above). Don't go on until every scope passes.
4. Remove the old key. Single repo: delete the old `&breakglass` entries,
   rename `&breakglass_next` to `&breakglass` with its `minted` comment, and
   run `make secrets-updatekeys ROTATE=1`. Estate: remove it from `.sops.yaml`,
   then `sops updatekeys` and `sops rotate -i` on `src/` and `keys/`. Run the
   checks, commit and push.
5. The custodians destroy both copies of the old key.

## The kits

`templates/single-repo/` implements the single-repo contract: `secrets.mk`
wraps `scripts/secrets.sh`, which runs under macOS's bash 3.2, parses the
kit's `.sops.yaml` layout (anchors named for identities), and checks
recipients from SOPS's plaintext metadata, so `secrets-check` needs no key.
`secrets-sync` targets Google Cloud Secret Manager; for AWS or Azure, adapt
its store calls. `tests/test-single-repo.sh` exercises every single-repo
flow above with stub `gh` and `gcloud`.

`templates/secrets-repo/` implements the estate contract, and
`tests/test-kit.sh` exercises every estate flow above in a sandbox. Both
tests need `sops` and `age`, and skip without them. The estate kit meets the
two constraints in the standard's "Reference implementation":

- `build.sh` runs `sops --config /dev/null` for `dist/`. With the committed
  `.sops.yaml`, sops otherwise refuses stdin with "no matching creation
  rules". It writes through a temp file, so a failed encrypt never leaves an
  empty `dist/` file behind.
- The scripts run under macOS's bash 3.2, with no associative arrays.

The kit also carries `verify` (grants, denials, and freshness, checked with
each consumer key), `retire`, a keyless `check.sh` shared by the hook and
CI, and `dist/` cleanup when a file leaves `access.map`.
