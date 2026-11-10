# Secrets in a Single Repo

> Placeholders: `<org>`, `<repo>`, `<env>` (a named environment: `dev`,
> `prod`), `<consumer>` (the service, app, resource or job that reads a file).

The default strategy for a **private** repo. A repo's secrets live encrypted in
its own `secrets/` folder with SOPS + age, and everything that reads them holds
its own age key. A public repo never has a `secrets/` folder: it uses OIDC,
estate grants or a plain GitHub secret instead
([README.md](README.md#public-repos)). A value that more than one repo uses
lives in the estate secrets repo instead ([estate.md](estate.md)), which reuses
everything here and changes only how files reach their readers.

This file holds the rules. The procedures (setting up, editing, minting keys,
wiring CI and deploys, rotating) and a tested kit that implements them are in
the `personal-secrets` skill ([SKILL.md](../../../personal-secrets/SKILL.md),
[`templates/single-repo/`](../../../personal-secrets/templates/single-repo/)).

Contents: [What goes in](#what-goes-in) · [Scopes](#scopes) · [Naming](#naming) · [Layout](#layout) · [Editing](#editing) · [Identities and keys](#identities-and-keys) · [`.sops.yaml`](#sopsyaml) · [CI](#ci) · [Deployed services](#deployed-services) · [Local development](#local-development) · [Checks](#checks) · [Rotation and leaks](#rotation-and-leaks) · [Threat model](#threat-model)

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
it opens with the same keys. **Make one scope per distinct set of
permissions.** `ci/` opens with the repo's Actions key; every other scope is the
GitHub environment of the same name, opened by that environment's key.

| Scope | Holds | Read by |
|---|---|---|
| `ci/` | What any CI job may read: signing certificates and their passwords, store API keys (App Store Connect `.p8`, a Play service account), package-registry tokens, read-only tokens such as the one `terraform plan` uses | Workflow jobs with no `environment:`. Never deployed |
| `<env>/`, a deploy environment | Runtime secrets of the services deployed there: the API keys they call with, database passwords, webhook signing secrets. A scope is a deploy environment when `deploy/<env>.env` exists | That environment's deploy job, which hands them to the platform's secret store ([Deployed services](#deployed-services)); developers, for `dev/` |
| `<job-env>/`, a privileged job | What one job needs that the other CI jobs mustn't have: `terraform apply`'s write token against `plan`'s read-only one (`terraform-prod/`) | The job that declares that environment, behind its branch policy |

Signing material belongs in `ci/`, not `prod/`. CI signs every build and
publishes it, and no deployed service reads it. A repo that deploys nothing (an
app, a library) may have only `ci/`. Each repo picks the scopes its jobs need:
the rule is one scope per set of permissions, not a fixed list.

## Naming

Names are the same in every repo, so a reader knows what a file is for and what
a key holds without opening it.

**Files are named for their consumer**: the service, app, resource or job that
reads them, in lowercase kebab-case.

- `<env>/<service>.env`: what that service reads at runtime in that
  environment (`prod/api.env`, `prod/mcp.env`, `prod/yjs.env`).
- `<scope>/shared.env`: the one reserved name. Every consumer in the scope
  reads it, layered under its own file ([Shared values](#shared-values)).
- `ci/<consumer>.env`: what one CI consumer needs, such as an app's release
  (`ci/deskhound.env`) or the plan job (`ci/terraform-plan.env`).
- `<job-env>/<consumer>.env`: what that privileged job needs
  (`terraform-prod/terraform.env`).
- Every deploy environment folder has the same files with the same keys. Only
  the values differ.
- Binary files keep the issuer's own file name (`AuthKey_BV7QPDLS45.p8`) or name
  the credential (`apple-distribution.p12`). A password for one goes in the
  consumer's env file.

**Keys are environment variable names**, in UPPER_SNAKE. The same name is the
key in the file, the variable the code reads, and the platform store's secret.

- Where a provider's SDK or CLI reads a documented variable, use exactly that
  name (`RESEND_API_KEY`, `SENTRY_AUTH_TOKEN`, `CLOUDFLARE_API_TOKEN`).
- Otherwise use `<PROVIDER>_<PURPOSE>_<KIND>` for a third party
  (`STRIPE_WEBHOOK_SECRET`, `APPLE_DISTRIBUTION_P12_PASSWORD`), and
  `<SYSTEM>_<PURPOSE>_<KIND>` for your own, where the system is whatever checks
  the secret (`YJS_AUTH_SECRET`).
- `<KIND>` is one of `_API_KEY`, `_TOKEN`, `_SECRET` (a shared signing or
  webhook secret), `_PASSWORD` or `_PRIVATE_KEY`.
- A name never contains an environment (`_PROD`), a repo or a service: the
  folder says the environment and the file says the consumer. So
  `RESEND_API_KEY` is spelled the same in every file, repo and environment, and
  `plan` and `apply` both read `CLOUDFLARE_API_TOKEN`, from different scopes.
- A value several consumers in a scope read goes in `shared.env`, once.

### Shared values

sops has no include, so the layering is a convention the tooling applies: a
consumer reads its scope's `shared.env` first, then its own
`<consumer>.env`, and **the last value for a key wins**. A consumer overrides a
shared value by setting the same key in its own file. `secrets-env` and the
deploy both read a consumer this way; `shared.env` is optional, and the
consumer's own file must exist even when it's empty.

Every consumer in the scope gets every key in `shared.env`, so put a value there
only when most of them need it. A value one or two services need goes in their
own files instead.

## Layout

A repo that deploys services and manages infrastructure:

```text
nowline-api/
├─ deploy/
│  ├─ dev.env                          config, plaintext
│  └─ prod.env
└─ secrets/
   ├─ README.md
   ├─ .sops.yaml
   ├─ ci/
   │  ├─ api.env.sops                  SENTRY_AUTH_TOKEN
   │  └─ terraform-plan.env.sops       CLOUDFLARE_API_TOKEN (read-only)
   ├─ terraform-prod/
   │  └─ terraform.env.sops            CLOUDFLARE_API_TOKEN (write)
   ├─ dev/
   │  ├─ shared.env.sops
   │  ├─ api.env.sops
   │  ├─ mcp.env.sops
   │  └─ yjs.env.sops
   └─ prod/
      ├─ shared.env.sops               RESEND_API_KEY (every service reads it)
      ├─ api.env.sops                  DATABASE_PASSWORD
      ├─ mcp.env.sops                  (empty: mcp reads only shared values)
      └─ yjs.env.sops                  YJS_AUTH_SECRET
```

An app repo, which deploys nothing:

```text
deskhound-mac/
├─ deploy/
│  └─ prod.env                         config, plaintext
└─ secrets/
   ├─ README.md
   ├─ .sops.yaml
   └─ ci/
      ├─ deskhound.env.sops            APPLE_DISTRIBUTION_P12_PASSWORD
      ├─ AuthKey_BV7QPDLS45.p8.sops
      └─ apple-distribution.p12.sops
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

Edit cleartext, then encrypt it, through the repo's Makefile
([makefile.md](makefile.md#single-repo-targets)): `secrets-decrypt` writes the
cleartext beside its ciphertext, `secrets-encrypt` seals it and deletes the
cleartext, and `secrets-clean` removes anything left behind.

- Encrypting needs only public keys, so anyone can add a value they can't
  read back.
- Encrypting refuses a file that's already SOPS output, so nothing is
  encrypted twice.
- Decrypting a `.env` asks first. Code never decrypts to disk: it reads
  values with `secrets-env`, which writes only to stdout. Binary files decrypt
  without asking, because CI needs them on disk.

## Identities and keys

Every reader has its own age key, and a key is a recipient only on the scopes it
may open. People never share a key with CI or with each other.

| Identity | Where the private key lives | Opens |
|---|---|---|
| Maintainer | Their own machine | Every scope |
| Developer | Their own machine | `dev/` |
| `<repo>__actions` | Repo Actions secret `SOPS_AGE_KEY` | `ci/` |
| `<repo>__env-<name>` | Actions secret `SOPS_AGE_KEY` in GitHub environment `<name>` | The `<name>/` scope: a deploy environment or a privileged job |
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

**An environment key is only as safe as its environment.** Give every
environment that holds a key a deployment branch policy (`main` and release
tags). Without one, any branch can declare the environment and read the key. On
private repos, GitHub Pro and Team have environments, environment secrets and
branch policies. Required reviewers and wait timers on a private repo need
Enterprise ([deployments and environments][gh-envs]).

**The `actions` key reaches every branch.** That's accepted for `ci/`: CI signs
and publishes from any build it runs. Anything a branch build mustn't reach goes
in a privileged job's scope instead.

**CI keys have no registry.** A CI or environment key is generated in memory, its
private half goes straight to GitHub, and only the public half is kept, in
`.sops.yaml`. A lost key is never recovered: mint a new one and swap it in. When
the repo joins an estate, the estate mints its keys from then on
([estate.md](estate.md#how-it-differs-from-a-single-repo)).

**Personal keys** live in `~/.config/sops/age/keys.txt`. On macOS, sops looks in
`~/Library/Application Support/sops/age/keys.txt` instead, so the tooling
exports `SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt` when neither
`SOPS_AGE_KEY` nor `SOPS_AGE_KEY_FILE` is set.

## `.sops.yaml`

One creation rule per scope, under `key_groups`. Each key is written once as a
YAML anchor named for its identity, so the file doubles as the list of who can
open what. sops is run from `secrets/`, where it finds `.sops.yaml`, so paths
start at the scope.

```yaml
# secrets/.sops.yaml: one creation rule per scope; run sops from secrets/
creation_rules:
  - path_regex: ^ci/.+\.sops$
    key_groups:
      - age:
          - &garyrudolph    age1...   # maintainer
          - &breakglass     age1...   # offline
          - &actions        age1...   # nowline-api__actions
  - path_regex: ^terraform-prod/.+\.sops$
    key_groups:
      - age:
          - *garyrudolph
          - *breakglass
          - &env_terraform_prod age1...   # nowline-api__env-terraform-prod
  - path_regex: ^prod/.+\.sops$
    key_groups:
      - age:
          - *garyrudolph
          - *breakglass
          - &env_prod       age1...   # nowline-api__env-prod
```

A creation rule applies when a file is encrypted, so a change to a scope's keys
re-wraps that scope's files (`sops updatekeys`), and removing a key also makes a
new data key (`sops rotate`) ([Rotation](#rotation-and-leaks)).

## CI

- Put `SOPS_AGE_KEY` on the steps that decrypt, never on the job.
- Prefer one value for one command (`secrets-env KEY=`). Append dotenv to
  `$GITHUB_ENV` only when later steps need it, and never a value a later step
  doesn't use.
- A decrypted file is mode `0600`, sits next to its ciphertext or under
  `$RUNNER_TEMP`, and is removed in an `if: always()` step.
- A job that needs a privileged scope declares its environment, and gets its
  cloud access through OIDC bound to that environment
  ([Cloud credentials](#cloud-credentials-dont-come-from-sops)).

Example jobs (release, plan and apply, deploy):
[`ci-steps.yml`](../../../personal-secrets/templates/single-repo/ci-steps.yml).

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

### Each service gets its own store secrets

Deploying `api` to `prod` reads `prod/shared.env.sops` and then
`prod/api.env.sops`, with the last value winning, and nothing else:

- **One store secret per service and key**, named for both with the store's
  delimiter (`api--RESEND_API_KEY` on GCP, below), in the prod project or
  account. The service still reads the variable `RESEND_API_KEY`; the deploy
  binds it to that secret.
  Because each service has its own copy, one that overrides a shared value never
  collides with one that doesn't.
- **Code reads the unprefixed name.** The prefix exists only in the store; the
  binding maps the variable to its secret. No service, library or helper
  translates names (`API_RESEND_API_KEY`), so provider SDKs find their
  documented variable, shared code reads one name in every service, and local
  runs use the same names as deploys.
- **The delimiter is `/` on AWS and `--` everywhere else**, so there are only
  two forms to know.

  | Store | Name | Why |
  | --- | --- | --- |
  | AWS Secrets Manager | `api/RESEND_API_KEY` | `/` is its path hierarchy; IAM grants `api/*` |
  | Azure Key Vault | `api--RESEND-API-KEY` | `--` is the separator its .NET configuration provider maps to `:`. Names allow only letters, digits and hyphens, so the key's underscores become hyphens |
  | GCP Secret Manager | `api--RESEND_API_KEY` | No convention of its own, and names allow only letters, digits, `_` and `-`, so it follows Azure |

  `--` splits unambiguously because service names use single hyphens, which
  `secrets-check` enforces.

- **The deploy writes only that service's keys.** It adds a store version for
  each value that changed, and binds the service to exactly those keys, pinned
  to the versions just written.
- **A shared value reaches a service at its next deploy.** Rotating a value in
  `shared.env` means redeploying every service in the scope.
- **Each service runs as its own identity**, with read access to exactly its own
  store secrets, so `yjs` can't read the database password only `api` uses.
  Infrastructure code creates the store secrets (with no values, since IaC state
  stores values in plaintext) and these grants, from the key names in
  `shared.env.sops` and each service's file, which SOPS leaves in plaintext.

### Cloud credentials don't come from sops

Every job signs in to the cloud with GitHub's OIDC token: Workload Identity
Federation on GCP, an IAM role assumed with web identity on AWS, a federated
credential on Azure. No long-lived cloud key exists to store. Bind the cloud
side to the GitHub environment as well as the repo: the provider's condition
checks the `environment` claim on GCP ([gcp.md](../gcp.md#ci-identity)), and
the subject `repo:<org>/<repo>:environment:<name>` on AWS and Azure. A job
outside `prod` can then neither decrypt `prod/` nor reach the prod project: two
separate gates. The same split gives `terraform plan` a viewer and `apply`, in
its own environment, an editor.

Store a credential in sops only for a target with no OIDC support (a DNS or
CDN provider's API token, say), in the scope of the job that uses it.

## Local development

Developers open `dev/` with their own keys and read it with
`secrets-env FILE=dev/<service>.env`. Nobody but maintainers and break-glass
opens `prod/`. Where an emulator or `demo-` project works, local runs need no
secrets at all ([gcp.md](../gcp.md#firebase-emulator-guard)).

## Checks

`secrets-check` needs no key, and runs in the pre-commit hook and in CI:

- Nothing but `*.sops` is tracked under a scope folder, and every `*.sops` file
  sits in a scope that has a creation rule.
- Every file's recipients, which SOPS stores in plaintext metadata, equal its
  scope's rule. This catches a file left behind by a recipient change, and a
  file shared more widely than its scope.
- Every value is encrypted: no `encrypted_regex`, `*_suffix` or
  `mac_only_encrypted` in `.sops.yaml`, and no plaintext value in a dotenv file.
- Break-glass is a recipient of every scope.
- File and key names follow [Naming](#naming), with single hyphens in a file
  name so `--` stays the store delimiter, and every deploy environment
  folder has the same files with the same keys, `shared.env` included.

One more check runs in CI only, because it needs the network: the repo is
private. A public repo with a `secrets/` folder fails the build.

## Rotation and leaks

- **Adding a reader** re-wraps its scope's files to the new key set.
- **Removing a reader** re-wraps and makes a new data key, so a key that read
  the old data key can't open later edits. Git history still holds every past
  version, which the removed key still opens. If its private key may have
  leaked, rotate the values too.
- **A leaked value** is revoked with the provider, replaced in every file that
  holds it, and redeployed so the store gets a new version. `git revert` fixes
  nothing: history keeps the old ciphertext.

The steps for each are in the skill.

## Threat model

- **Read access to the repo** yields ciphertext only.
- **The `actions` key** opens `ci/`, history included, and is readable by any
  workflow on any branch. If it leaks, revoke the signing certificates and
  tokens it opened, not just the age key.
- **An environment key** opens its scope, history included. Its branch policy
  decides which code can read it.
- **A maintainer key** opens every scope. Break-glass does too, and stays
  offline.
- **The platform store** is the only place a running service reads secrets
  from. Its IAM is per service, and its audit log records each access.

[gh-envs]: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
