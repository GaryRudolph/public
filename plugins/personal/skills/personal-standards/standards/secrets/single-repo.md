# Secrets in a Single Repo

> Placeholders: `<org>`, `<repo>`, `<env>` (a named environment: `dev`,
> `prod`), `<consumer>` (the service, app or resource that reads a file).

The default strategy for a **private** repo. A repo's secrets live encrypted in
its own `secrets/` folder with SOPS + age, and everything that reads them holds
its own age key. A public repo never has a `secrets/` folder: it uses OIDC,
estate grants or a plain GitHub secret instead
([README.md](README.md#public-repos)).
It needs nothing but GitHub and the platform the code deploys to. A value that
more than one repo uses lives in the estate secrets repo instead
([estate.md](estate.md)), which reuses everything here and changes only how
files reach their readers.

Contents: [What goes in](#what-goes-in) · [Scopes](#scopes) · [Naming](#naming) · [Layout](#layout) · [Editing](#editing) · [Identities and keys](#identities-and-keys) · [`.sops.yaml`](#sopsyaml) · [Minting a CI key](#minting-a-ci-key) · [CI](#ci) · [Deployed services](#deployed-services) · [Local development](#local-development) · [Checks](#checks) · [Rotation and leaks](#rotation-and-leaks) · [Threat model](#threat-model)

## What goes in

Only secrets: values that grant access on their own, such as private keys,
signing certificates and their passwords, API keys, tokens and database
passwords. **Every value in a secret file is encrypted.** Don't use
`encrypted_regex` or `mac_only_encrypted`. A rule based on names leaks the first
secret whose name doesn't fit: with `^(.*_PASSWORD|.*_SECRET|.*_TOKEN)$`,
`RESEND_API_KEY` is committed in plaintext, and a leak check that matches the
same suffixes passes it. SOPS dotenv keeps key names in plaintext either way,
so a diff still shows which key changed.

Everything else is config: plaintext, committed, and kept out of `secrets/`
([architecture.md](../architecture.md#ci-configuration)). Bundle ids, app record
ids, project ids, origins, and identifiers that are useless without a private
key (an App Store Connect key id or issuer id) go in `deploy/<env>.env` or
`.github/ci.env`. A secret file never carries config "for convenience": then it
can't be loaded by make's `include`, and the config can't be read without a key.

## Scopes

A scope is a folder under `secrets/` with one set of recipients: every file in
it opens with the same keys.

| Scope | Holds | Read by |
|---|---|---|
| `ci/` | What CI needs to build, sign and publish: signing certificates and their passwords, store API keys (App Store Connect `.p8`, a Play service account), package-registry tokens, deploy tokens for targets without OIDC | Workflow jobs. Never deployed |
| `<env>/` | Runtime secrets of the services deployed to that environment: the API keys they call with, database passwords, webhook signing secrets. One folder per named environment, matching `deploy/<env>.env` | That environment's deploy job, which hands them to the platform's secret store ([Deployed services](#deployed-services)); developers, for `dev/` |

Signing material belongs in `ci/`, not `prod/`. CI signs every build and
publishes it, and no deployed service reads it. A repo that deploys nothing (an
app, a library) has only `ci/`.

## Naming

Names are the same in every repo, so a reader knows what a file is for and what
a key holds without opening it.

**Files are named for their consumer**: the service, app or resource that reads
them, in lowercase kebab-case.

- `<env>/<service>.env`: everything that service reads at runtime in that
  environment (`prod/api.env`, `prod/mcp.env`, `prod/yjs.env`). The file is the
  complete list of what the service gets.
- `ci/<app>.env`: what CI needs to build, sign and publish that app or package
  (`ci/deskhound.env`). A repo that ships one thing has one file.
- Every `<env>/` folder has the same files with the same keys. Only the values
  differ.
- Binary files keep the issuer's own file name (`AuthKey_BV7QPDLS45.p8`) or name
  the credential (`apple-distribution.p12`). A password for one goes in the
  consumer's env file.

**Keys are environment variable names**, in UPPER_SNAKE. The same name is the
key in the file, the variable the code reads, and the platform store's secret.

- Where a provider's SDK or CLI reads a documented variable, use exactly that
  name (`RESEND_API_KEY`, `SENTRY_AUTH_TOKEN`).
- Otherwise use `<PROVIDER>_<PURPOSE>_<KIND>` for a third party
  (`STRIPE_WEBHOOK_SECRET`, `APPLE_DISTRIBUTION_P12_PASSWORD`), and
  `<SYSTEM>_<PURPOSE>_<KIND>` for your own, where the system is whatever checks
  the secret (`YJS_AUTH_SECRET`).
- `<KIND>` is one of `_API_KEY`, `_TOKEN`, `_SECRET` (a shared signing or
  webhook secret), `_PASSWORD` or `_PRIVATE_KEY`.
- A name never contains an environment (`_PROD`), a repo or a service: the
  folder says the environment and the file says the consumer. So
  `RESEND_API_KEY` is spelled the same in every file, repo and environment.
- One name means one value within a scope. When two services read the same
  value, it appears in both files under the same name, and the sync refuses to
  deploy if the copies differ ([Deployed services](#deployed-services)).

## Layout

A repo that deploys services, and an app repo:

```text
nowline-api/                           deskhound-mac/
├─ deploy/                             ├─ deploy/
│  ├─ dev.env      config, plaintext   │  └─ prod.env        config, plaintext
│  └─ prod.env                         └─ secrets/
└─ secrets/                               ├─ .sops.yaml
   ├─ README.md                           ├─ README.md
   ├─ .sops.yaml                          └─ ci/
   ├─ ci/                                    ├─ deskhound.env.sops
   │  └─ api.env.sops   SENTRY_AUTH_TOKEN    ├─ AuthKey_BV7QPDLS45.p8.sops
   ├─ dev/                                   └─ apple-distribution.p12.sops
   │  ├─ api.env.sops
   │  ├─ mcp.env.sops
   │  └─ yjs.env.sops
   └─ prod/
      ├─ api.env.sops   DATABASE_PASSWORD, RESEND_API_KEY
      ├─ mcp.env.sops   RESEND_API_KEY
      └─ yjs.env.sops   YJS_AUTH_SECRET
```

**Cleartext next to ciphertext.** `api.env` is the cleartext you edit, and
`api.env.sops` is what's committed: the encrypted file is the cleartext's name
plus `.sops`. The `.gitignore` lets only `*.sops` be committed under a scope
folder, so a cleartext file can sit beside its ciphertext while you work and
still can't be staged. The suffix names the tool that opens the file. `.age`
would be wrong for SOPS files, and `.enc` doesn't say what decrypts it. Binary
files use SOPS too (`--input-type binary`), so one recipient list covers
everything. Raw `age -R` needs a second recipient file that drifts from
`.sops.yaml`.

```gitignore
# secrets/<scope>/ holds ciphertext only; a cleartext sibling can't be staged
/secrets/*/**
!/secrets/*/**/
!/secrets/*/**/*.sops
```

Scope folders hold ciphertext and the cleartext you're working on, nothing else.
Scripts go in `scripts/` or the Makefile, never inside a scope folder.

## Editing

Edit cleartext, then encrypt it. The Makefile targets are in
[makefile.md](makefile.md#single-repo-targets):

```bash
make secrets-decrypt FILE=prod/api.env      # writes prod/api.env (asks first)
$EDITOR secrets/prod/api.env
make secrets-encrypt FILE=prod/api.env      # rewrites prod/api.env.sops, deletes prod/api.env
make secrets-clean                          # removes any cleartext left behind, runs the checks
```

- **A new file**: write the cleartext (`secrets/prod/worker.env`), then
  `make secrets-encrypt FILE=prod/worker.env`. Encrypting needs only public
  keys, so anyone can add a value they can't read back.
- **`secrets-encrypt`** with no `FILE=` encrypts every cleartext file under
  `secrets/`. It refuses a file that's already SOPS output, so nothing gets
  encrypted twice.
- **`secrets-decrypt`** asks before writing a cleartext `.env`, unless
  `CONFIRM=1`. Binary files decrypt without asking, because CI needs them on
  disk. Code reads values with `secrets-env`, which never writes cleartext to
  disk.

## Identities and keys

Every reader has its own age key, and a key is a recipient only on the scopes it
may open. People never share a key with CI or with each other.

| Identity | Where the private key lives | Opens |
|---|---|---|
| Maintainer | Their own machine | Every scope |
| Developer | Their own machine | `dev/` |
| `<repo>__actions` | Repo Actions secret `SOPS_AGE_KEY` | `ci/` |
| `<repo>__env-<env>` | Actions secret `SOPS_AGE_KEY` in GitHub environment `<env>` | `<env>/` |
| `<repo>__agents`, `__codespaces`, `__dependabot` | That GitHub store's `SOPS_AGE_KEY` | `dev/` at most, and only once a job there needs it |
| `claude__<environment>` | `SOPS_AGE_KEY` in a Claude Code cloud environment's settings | `dev/` at most |
| Break-glass | Offline | Every scope |

People's identities are named by their GitHub login, and break-glass is
`breakglass`.

**One name, one key per job.** The secret is always `SOPS_AGE_KEY`. When a repo
secret and an environment secret share a name, the environment's wins, so a job
that declares `environment: prod` sees only the prod key, and a job with no
environment sees the `actions` key. A job that needs two scopes becomes two
jobs. Set `environment:` and `ENVIRONMENT` from the same value
([architecture.md](../architecture.md#ci-configuration)).

**An environment key is only as safe as its environment.** Give `prod` a
deployment branch policy (`main` and release tags). Without one, any branch can
declare `environment: prod` and read the key. On private repos, GitHub Pro and
Team have environments, environment secrets and branch policies. Required
reviewers and wait timers on a private repo need Enterprise
([deployments and environments][gh-envs]).

**The `actions` key reaches every branch.** That's accepted for `ci/`: CI signs
and publishes from any build it runs. To keep signing material to `main`, move
that key into an environment (say `release`) with a branch policy. Every signing
job then declares it.

**Personal keys** live in `~/.config/sops/age/keys.txt`. On macOS, sops looks in
`~/Library/Application Support/sops/age/keys.txt` instead, so the Makefile
exports `SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt` when neither
`SOPS_AGE_KEY` nor `SOPS_AGE_KEY_FILE` is set.

## `.sops.yaml`

One creation rule per scope. Each key is written once as a YAML anchor named
for its identity, so the file doubles as the list of who can open what. The
Makefile runs sops from `secrets/`, so paths start at the scope.

```yaml
# secrets/.sops.yaml: one creation rule per scope; run sops from secrets/
creation_rules:
  - path_regex: ^ci/.+\.sops$
    key_groups:
      - age:
          - &garyrudolph    age1...   # maintainer
          - &breakglass     age1...   # offline
          - &actions        age1...   # nowline-api__actions
  - path_regex: ^dev/.+\.sops$
    key_groups:
      - age:
          - *garyrudolph
          - *breakglass
          - &dana           age1...   # developer
          - &env_dev        age1...   # nowline-api__env-dev
  - path_regex: ^prod/.+\.sops$
    key_groups:
      - age:
          - *garyrudolph
          - *breakglass
          - &env_prod       age1...   # nowline-api__env-prod
```

A creation rule applies when a file is encrypted. After changing a scope's
recipients, run `make secrets-updatekeys SCOPE=<scope>` to re-wrap its files,
and add `ROTATE=1` when a recipient was removed ([Rotation](#rotation-and-leaks)).

## Minting a CI key

A single repo keeps no key registry. A CI or environment key is generated in
memory, its private half goes straight to GitHub, and only the public half is
kept:

```bash
key="$(age-keygen 2>/dev/null)"
printf '%s\n' "$key" | grep '^AGE-SECRET-KEY-' | gh secret set SOPS_AGE_KEY -R <org>/<repo> --env prod
printf '%s\n' "$key" | age-keygen -y      # public half: add it to .sops.yaml
```

`make secrets-mint CONTEXT=env-prod` wraps this behind `CONFIRM_MINT=1`
([makefile.md](makefile.md#single-repo-targets)). A lost key is never
recovered: mint a new one and swap it in. When the repo joins an estate, the
estate mints its keys from then on ([estate.md](estate.md#how-it-differs-from-a-single-repo)).

## CI

```yaml
jobs:
  release:                               # ci/ scope: repo-level key
    runs-on: macos-26
    steps:
      - uses: actions/checkout@v7
      - name: Import signing certificate
        env:
          SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
        run: |
          make secrets-decrypt FILE=ci/apple-distribution.p12
          APPLE_DISTRIBUTION_P12_PASSWORD="$(make -s secrets-env FILE=ci/deskhound.env KEY=APPLE_DISTRIBUTION_P12_PASSWORD)" make keychain-import
      - name: Remove cleartext
        if: always()
        run: make secrets-clean

  deploy:                                # prod/ scope: environment key
    environment: prod
    env:
      ENVIRONMENT: prod
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - name: Sync and deploy api
        env:
          SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
        run: make deploy SERVICE=api ENVIRONMENT=prod CONFIRM_SYNC=1
```

- Put `SOPS_AGE_KEY` on the steps that decrypt, never on the job.
- Prefer one value for one command (`secrets-env KEY=`). Append dotenv to
  `$GITHUB_ENV` only when later steps need it, and never a value a later step
  doesn't use.
- A decrypted file is mode `0600`, sits next to its ciphertext or under
  `$RUNNER_TEMP`, and is removed in an `if: always()` step.

## Deployed services

A deployed service never holds an age key and never runs sops. The deploy job
for `<env>` decrypts that service's file and writes each value into the
platform's secret store: Secret Manager on GCP
([gcp.md](../gcp.md#runtime-secrets)), Secrets Manager on AWS, Key Vault on
Azure. The service reads values from there as environment variables or mounted
files.

Why not decrypt in the service: a running container has no GitHub secret store,
so its age key would have to live in the platform's store anyway (or in a
plaintext environment variable, which is worse). Once that's true, decrypting
in the service adds sops to every image, bakes ciphertext into images, and gives
up the store's per-secret access control and audit log, for nothing in return.

### Each service gets only its own file

`make deploy SERVICE=api ENVIRONMENT=prod` deploys from `secrets/prod/api.env.sops`
and nothing else:

- **One store secret per key, named the key.** `RESEND_API_KEY` becomes the
  store secret `RESEND_API_KEY` in the prod project or account. When `api` and
  `mcp` both read it, they share that one store secret.
- **The sync writes only that file's keys.** It adds a store version for each
  value that changed, and the deploy binds `api` to exactly those keys, pinned
  to the versions just written.
- **Shared copies must match.** Before writing, the sync decrypts every file in
  the scope (the job's key opens them all) and refuses if another file holds the
  same key with a different value. Rotating a shared value means editing every
  file that holds it, and the sync catches a file you missed.
- **Each service runs as its own identity**, with read access to exactly the
  keys in its file, so `yjs` can't read the database password only `api` uses.
  Infrastructure code creates the store secrets (with no values, since IaC state
  stores values in plaintext) and these grants, from the key names in each
  service's file, which SOPS leaves in plaintext.

### Cloud credentials don't come from sops

The deploy job signs in to the cloud with GitHub's OIDC token: Workload
Identity Federation on GCP, an IAM role assumed with web identity on AWS, a
federated credential on Azure. No long-lived cloud key exists to store. Bind the
cloud side to the GitHub environment as well as the repo: the provider's
condition checks the `environment` claim on GCP
([gcp.md](../gcp.md#ci-identity)), and the subject
`repo:<org>/<repo>:environment:prod` on AWS and Azure. A job outside `prod` can
then neither decrypt `prod/` nor reach the prod project: two separate gates.

Store a deploy credential in sops only for a target with no OIDC support, in
the scope that uses it: `<env>/` for an environment's deploy, `ci/` for
publishing.

## Local development

Developers open `dev/` with their own keys and load it into a shell or dev
server with `make secrets-env FILE=dev/<service>.env`. Nobody but maintainers
and break-glass opens `prod/`. Where an emulator or `demo-` project works, local
runs need no secrets at all ([gcp.md](../gcp.md#firebase-emulator-guard)).

## Checks

`make secrets-check` needs no key, and runs in the pre-commit hook and in CI:

- Nothing but `*.sops` is tracked under a scope folder, and every `*.sops` file
  sits in a scope that has a creation rule.
- Every file's recipients, which SOPS stores in plaintext metadata, equal its
  scope's rule. This catches a file left behind by a recipient change, and a
  file shared more widely than its scope.
- Every value is encrypted: no `encrypted_regex` in `.sops.yaml`, and no
  plaintext value in a dotenv file.
- Break-glass is a recipient of every file.
- File and key names follow [Naming](#naming), and every `<env>/` folder has the
  same files with the same keys.

One more check runs in CI only, because it needs the network: the repo is
private (`gh api repos/{owner}/{repo} --jq .private` prints `true`). A public
repo with a `secrets/` folder fails the build.

## Rotation and leaks

- **Add a reader**: add its public key to the scope's rule, then
  `make secrets-updatekeys SCOPE=<scope>`.
- **Remove a reader**: remove its key, then `make secrets-updatekeys
  SCOPE=<scope> ROTATE=1`. `updatekeys` re-wraps the existing data key and
  `rotate` makes a new one, so a key that read the old data key can't open
  later edits. Git history still holds every past version, which the removed key
  still opens. If its private key may have leaked, rotate the values too.
- **Rotate a CI or environment key**: mint a new one (which overwrites the
  GitHub secret), swap the public key in `.sops.yaml`, then updatekeys with
  `ROTATE=1`.
- **A leaked value**: revoke it with the provider, replace it in every file that
  holds it, commit, then redeploy so the store gets a new version. `git revert`
  fixes nothing: history keeps the old ciphertext.

## Threat model

- **Read access to the repo** yields ciphertext only.
- **The `actions` key** opens `ci/`, history included, and is readable by any
  workflow on any branch. If it leaks, revoke the signing certificates and
  store keys it opened, not just the age key.
- **An environment key** opens that environment's runtime secrets, history
  included. Its branch policy decides which code can read it.
- **A maintainer key** opens every scope. Break-glass does too, and stays
  offline.
- **The platform store** is the only place a running service reads secrets
  from. Its IAM is per service, and its audit log records each access.

[gh-envs]: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
