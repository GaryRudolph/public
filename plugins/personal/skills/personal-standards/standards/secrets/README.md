# Secrets Management

Secrets are committed as SOPS + age ciphertext, and every reader holds its own
age key. **Never commit a plaintext secret**, and keep config (ids, origins,
public web keys) out of secret files: it's plaintext and committed
([architecture.md](../architecture.md#ci-configuration)).

## Two strategies

| | Use it for | Standard |
|---|---|---|
| **Single repo** (the default for a private repo) | Values only one private repo uses, encrypted in that repo's `secrets/` folder | [single-repo.md](single-repo.md) |
| **Estate** | Values two or more repos in an estate use, and any secret a public repo needs, in a private `<estate>-secrets` repo | [estate.md](estate.md), written as the differences from a single repo |

A value lives in exactly one place. It starts in the repo that needs it and
moves to the estate when a second repo needs it
([estate.md](estate.md#when-a-value-moves-to-the-estate)). A repo can use both
at once: its own `secrets/` and estate grants open with the same key.

## Public repos

**A public repo has no `secrets/` folder.** The ciphertext would be safe today,
but the repo loses the first gate (who can fetch it at all), and its history is
public and permanent: a key that leaks in five years opens every value the repo
ever held, for anyone. The file and key names also publish what you hold and
how often it changes.

A public repo gets what it needs in this order:

1. **No secret at all.** Use OIDC wherever the target accepts it: trusted
   publishing to npm, PyPI, crates.io and RubyGems, workload identity
   federation to a cloud ([single-repo.md](single-repo.md#cloud-credentials-dont-come-from-sops)),
   `GITHUB_TOKEN` for the repo itself, and a GitHub App token for writes to
   another repo (a Homebrew tap).
2. **An estate grant.** A public repo is an ordinary member: its CI checks out
   the private `<estate>-secrets` repo's `dist/` and decrypts with its own
   `SOPS_AGE_KEY`, so the ciphertext stays private
   ([estate.md](estate.md#consumer-side)).
3. **A plain GitHub secret**, only for a value this repo alone uses when there's
   no estate to put it in. Use an environment secret for anything that deploys
   or publishes, and no sops.

Rules that apply only to public repos:

- **Never run fork code with a secret in reach.** Workflows triggered by
  `pull_request` from a fork get no secrets, which is the protection. Never
  check out a PR's head in a `pull_request_target` or `workflow_run` workflow
  that holds a secret.
- **Protect every environment that holds a key.** Public repos get deployment
  branch policies and required reviewers on every plan
  ([deployments and environments][gh-envs]), so use both on anything that
  publishes.
- **Before making a private repo public**, move its `secrets/` values to the
  estate and rotate every one of them upstream. Deleting the folder isn't
  enough, because the history goes public with the repo.

## What both share

- **Every value is encrypted**, so a secret can't be committed in plaintext
  because of its name. Files end in `.sops`, and a decrypted sibling can't be
  staged.
- **Scopes, one per set of permissions:** `ci/` holds what any CI job may read,
  signing material included. Every other scope is a GitHub environment: a
  deploy environment's runtime secrets (`prod/`), or what one privileged job
  needs (`terraform-prod/` for `apply`, while `plan` reads `ci/`).
- **One key per reader:** people have their own keys. CI has one per
  `(repo, context)`: `<repo>__actions` opens `ci/`, and `<repo>__env-<name>`, in
  that GitHub environment, opens `<name>/`. Every store names the secret
  `SOPS_AGE_KEY`, and a job sees one key.
- **Files are named for their consumer** (`prod/api.env`, `ci/deskhound.env`),
  with each scope's optional `shared.env` layered under every consumer's file
  (last value wins), and keys are the environment variable names, spelled the
  same in every repo ([single-repo.md](single-repo.md#naming)). You edit a cleartext `api.env`;
  `api.env.sops` is what's committed.
- **Deployed services never decrypt.** The deploy job copies each service's
  keys (`shared.env`, then its own file) into that service's own secrets in the
  platform's store (`api--RESEND_API_KEY`), and the service reads them from
  there under the bare name. Cloud credentials come from OIDC, never from sops
  ([single-repo.md](single-repo.md#deployed-services)).

## Where code runs

| Where | What it opens |
|---|---|
| GitHub Actions workflow jobs | `ci/`, with the `actions` key |
| Deploy jobs and privileged jobs | Their environment's scope, with that environment's key, behind its branch policy |
| GitHub Agents, Codespaces, Dependabot | `dev/` at most, with their own store keys |
| Claude Code cloud environments | `dev/` at most, with that environment's key |
| A developer's machine | `dev/`, with their own key; maintainers open everything |
| Cloud Run, Firebase Functions, other deployed services | Only their own secrets (`shared.env` plus their file), from the platform's secret store ([gcp.md](../gcp.md#runtime-secrets)) |
| Apps and browsers | Nothing. A shipped binary can't keep a secret; CI does the signing |
| A public repo's CI | Its estate grants, or a plain GitHub secret; never a `secrets/` folder ([Public repos](#public-repos)) |

## Least-privilege consumption

Prefer the narrowest form the toolchain allows:

1. **One value, one command:** the value goes inline to the command that needs
   it, and nothing lands in the job environment.
2. **Export to the job environment:** dotenv appended to `$GITHUB_ENV`, only
   for the keys later steps use.
3. **Decrypt files to disk:** only when the toolchain needs a file (a `.p8` or
   `.p12`), mode `0600`, removed when the job ends.

Target names for each tier: [makefile.md](makefile.md).

## Rotation and break-glass

age keys don't expire, so rotation is a schedule kept by people, not a date a
key enforces. Both strategies keep the same one.

| Key | Rotate | Also rotate when |
|---|---|---|
| Maintainer and developer keys, CI and environment keys | Every 9 months | Its holder leaves, or it may have leaked |
| Break-glass | Every 12 months | A custodian changes, or it may have leaked |

- **Never rotate both in one change.** The two schedules meet every 36 months.
  When they do, finish the regular rotation first, then break-glass, so one key
  you know works is always in place.
- **Drill break-glass at every regular rotation**: decrypt one file per scope
  with it. The drill is what catches a lost copy or a forgotten passphrase.
  Rotating on a schedule doesn't.
- **Break-glass is held offline in two copies, by two people.** A new one goes
  into every rule beside the old one. The old one comes out only after a drill
  with the new one passes, and the removal makes a new data key.
- **Destroy every copy of a rotated key.** History still holds ciphertext the
  old key opens, so a copy that survives undoes the rotation.
- **Record the month each key was minted** in `.sops.yaml`: in the comment
  beside each key for a single repo, and in the header for the estate's
  maintainer and break-glass keys. That's how the next rotation's due date is
  known.

Rotating a key doesn't rotate the values it opened. Rotate a value at its
provider when the key may have leaked, or when the provider's own credential
expires: an Apple distribution certificate lasts a year.

The steps are in the `personal-secrets` skill.

## Documentation map

| File | Purpose |
|------|---------|
| [single-repo.md](single-repo.md) | The full model: scopes, layout, identities, `.sops.yaml`, CI, deployed services, checks, rotation, threat model |
| [estate.md](estate.md) | How the estate secrets repo differs: `access.map`, `src/` and `dist/`, the key registry, the Secrets App, the kit |
| [makefile.md](makefile.md) | Makefile targets for both strategies |
| [`personal-secrets` skill](../../../personal-secrets/SKILL.md) | Procedures for both strategies, plus a tested kit for each |

[gh-envs]: https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments
