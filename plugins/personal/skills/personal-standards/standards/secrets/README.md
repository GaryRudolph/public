# Secrets Management

Secrets are committed as SOPS + age ciphertext, and every reader holds its own
age key. **Never commit a plaintext secret**, and keep config (ids, origins,
public web keys) out of secret files: it's plaintext and committed
([architecture.md](../architecture.md#ci-configuration)).

## Two strategies

| | Use it for | Standard |
|---|---|---|
| **Single repo** (the default) | Values only one repo uses, encrypted in that repo's `secrets/` folder | [single-repo.md](single-repo.md) |
| **Estate** | Values two or more repos in an estate use, in a private `<estate>-secrets` repo | [estate.md](estate.md), written as the differences from a single repo |

A value lives in exactly one place. It starts in the repo that needs it and
moves to the estate when a second repo needs it
([estate.md](estate.md#when-a-value-moves-to-the-estate)). A repo can use both
at once: its own `secrets/` and estate grants open with the same key.

## What both share

- **Every value is encrypted**, so a secret can't be committed in plaintext
  because of its name. Files end in `.sops`, and a decrypted sibling can't be
  staged.
- **Scopes:** `ci/` holds what CI builds, signs and publishes with, signing
  material included. `<env>/` holds each environment's runtime secrets.
- **One key per reader:** people have their own keys. CI has one per
  `(repo, context)`: `<repo>__actions` opens `ci/`, and `<repo>__env-<env>`, in
  that GitHub environment, opens `<env>/`. Every store names the secret
  `SOPS_AGE_KEY`, and a job sees one key.
- **Deployed services never decrypt.** The deploy job copies each service's
  listed keys into the platform's secret store, and the service reads them from
  there. Cloud credentials come from OIDC, never from sops
  ([single-repo.md](single-repo.md#deployed-services)).

## Where code runs

| Where | What it opens |
|---|---|
| GitHub Actions workflow jobs | `ci/`, with the `actions` key |
| Deploy jobs | `<env>/`, with that environment's key, behind its branch policy |
| GitHub Agents, Codespaces, Dependabot | `dev/` at most, with their own store keys |
| Claude Code cloud environments | `dev/` at most, with that environment's key |
| A developer's machine | `dev/`, with their own key; maintainers open everything |
| Cloud Run, Firebase Functions, other deployed services | Only their listed keys, from the platform's secret store ([gcp.md](../gcp.md#runtime-secrets)) |
| Apps and browsers | Nothing. A shipped binary can't keep a secret; CI does the signing |

## Least-privilege consumption

Prefer the narrowest form the toolchain allows:

1. **One value, one command:** the value goes inline to the command that needs
   it, and nothing lands in the job environment.
2. **Export to the job environment:** dotenv appended to `$GITHUB_ENV`, only
   for the keys later steps use.
3. **Decrypt files to disk:** only when the toolchain needs a file (a `.p8` or
   `.p12`), mode `0600`, removed when the job ends.

Target names for each tier: [makefile.md](makefile.md).

## Documentation map

| File | Purpose |
|------|---------|
| [single-repo.md](single-repo.md) | The full model: scopes, layout, identities, `.sops.yaml`, CI, deployed services, checks, rotation, threat model |
| [estate.md](estate.md) | How the estate secrets repo differs: `access.map`, `src/` and `dist/`, the key registry, the Secrets App, the kit |
| [makefile.md](makefile.md) | Makefile targets for both strategies |
| [`personal-secrets` skill](../../../personal-secrets/SKILL.md) | Procedures, plus the tested kit for the estate repo |
