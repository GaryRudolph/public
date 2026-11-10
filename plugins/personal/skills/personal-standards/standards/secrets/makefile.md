# Secrets: Makefile Targets

Recommended Makefile contracts for both strategies in [README.md](README.md):
the `secrets-*` targets a single repo adds to its own Makefile, then the
targets of an `<estate>-secrets` repo. The `personal-secrets` skill has a
tested kit for each:
[`templates/single-repo/`](../../../personal-secrets/templates/single-repo/secrets.mk)
and [`templates/secrets-repo/`](../../../personal-secrets/templates/secrets-repo/Makefile).

Placeholders: `<org>`, `<estate>`, `<repo>`, `<env>`, `<scope>`.

Contents: [Single-repo targets](#single-repo-targets) · [Estate targets](#estate-targets) · [GitHub secret stores by context](#github-secret-stores-by-context)

## Single-repo targets

Under `##@ Secrets` in the repo's own Makefile (the kit's `secrets.mk` is
included from it), running sops from `secrets/` ([single-repo.md](single-repo.md)). `FILE=` is a logical path below
`secrets/`, without `.sops` (`prod/api.env`, `ci/AuthKey_BV7QPDLS45.p8`). The
encrypted file is that name plus `.sops`, and its cleartext sibling is the name
itself ([single-repo.md](single-repo.md#layout)).

| Target | Key it needs | Purpose | Arguments |
|--------|--------------|---------|-----------|
| `secrets-env` | A reader of the scope | Dotenv to stdout, or one raw value with `KEY=`, with the scope's `shared.env` layered under the file (last value wins); never writes to disk | `FILE=` (required), `KEY=`, `FORMAT=dotenv` |
| `secrets-encrypt` | None: encrypting needs only public keys | Encrypt cleartext siblings to `*.sops` under their scope's rule, then delete the cleartext; refuses a file that's already SOPS output | `FILE=` (default: every cleartext file) |
| `secrets-decrypt` | A reader of the scope | Write `*.sops` to cleartext siblings, mode `0600`, for editing or for a tool that needs a file; asks before writing a `.env` unless `CONFIRM=1`; no env output | `FILE=` (default: every file the key opens), `CONFIRM=1` |
| `secrets-updatekeys` | A maintainer | Re-wrap every file in a scope after a recipient change; `ROTATE=1` also makes a new data key | `SCOPE=` (default all), `ROTATE=1` |
| `secrets-check` | None | The keyless checks in [single-repo.md](single-repo.md#checks); `ONLINE=1` adds the private-repo check, for CI | `ONLINE=1` |
| `secrets-doctor` | None | Tools present and an age identity found; the repo's `doctor` depends on it | none |
| `secrets-clean` | None | Delete every cleartext sibling under `secrets/`, then run `secrets-check` | none |
| `secrets-mint` | None, plus `gh` | New keypair: private half to the context's GitHub store on stdin, public half printed for `.sops.yaml` | `CONTEXT=actions\|env-<env>\|agents\|codespaces\|dependabot` |
| `secrets-sync` | The environment's key | Write a service's layered keys (`shared.env`, then `<service>.env`) to the platform's secret store as `<service>-<KEY>` (`STORE_PREFIX=` for bare names), resolving `@estate` values from the estate's `dist/`, adding a version only for a changed value; print `KEY=<service>-KEY:<version>,...` for the deploy | `ENVIRONMENT=` (a deploy environment), `SERVICE=` |

`secrets-mint` and `secrets-sync` write outside the repo, so they sit under
`##@ Danger` and refuse without `CONFIRM_MINT=1` or `CONFIRM_SYNC=1`
([makefile.md](../makefile.md#danger-guards)). A repo's `deploy` target calls
`secrets-sync` for the service it deploys and binds the printed versions.

An identity is `SOPS_AGE_KEY`, `SOPS_AGE_KEY_FILE`, or
`~/.config/sops/age/keys.txt`, which the tooling exports as `SOPS_AGE_KEY_FILE`
because sops on macOS looks in `~/Library/Application Support` instead. The
kit's `secrets-sync` writes to Google Cloud Secret Manager, in the project
`GOOGLE_CLOUD_PROJECT` names (from `deploy/<env>.env`).

## Estate targets

For the `<estate>-secrets` repo ([estate.md](estate.md)) and the members that
check out its `dist/`.

### Maintainer-local targets

Require a **source key** (maintainer personal age key or break-glass). Never run
these in consumer CI.

| Target | Purpose | Arguments |
|--------|---------|-----------|
| `init` | Wire git hooks, chmod scripts, run `doctor` | — |
| `doctor` | Verify `sops`, `age-keygen`, `gh` installed | — |
| `src-decrypt` | Decrypt `src/*.sops` to plaintext siblings for editing | `FILE=` logical path (optional; default all) |
| `src-encrypt` | Encrypt plaintext siblings back to `*.sops`, delete plaintext | `FILE=` (optional; default all) |
| `build` | Re-encrypt `src/` → `dist/` per `access.map` publish recipients | — |
| `set-keys` | Push consumer `SOPS_AGE_KEY` values to GitHub | `REPO=`, `CONTEXT=` (optional scope) |
| `mint` | Generate a new consumer keypair into `keys/repos.env.sops` | `REPO=`, `CONTEXT=` (required) |
| `rotate` | Replace an existing consumer keypair | `REPO=`, `CONTEXT=` (required) |
| `retire` | Remove a consumer keypair; refuses while `access.map` still grants it | `REPO=`, `CONTEXT=` (required) |
| `verify` | Decrypt every `dist/` file with every consumer key: grants work, denials hold, `dist/` matches `src/` | — |

`set-keys` writes to GitHub, so it sits under `##@ Danger` and refuses without
`CONFIRM_SET_KEYS=1`.

### Keyless targets

Need no age key; safe anywhere, including the secrets repo's own CI.

| Target | Purpose | Arguments |
|--------|---------|-----------|
| `lint` | `access.map` parses, files pair up, no tracked plaintext, break-glass is a recipient | — |
| `ci` | `lint`, plus `src/`↔`dist/` pairing over a commit range | `RANGE=<base>..<head>` (optional) |
| `clean` | Delete plaintext siblings under `src/` and `dist/` | — |

### Consumer-safe targets

Require only the consumer's **`SOPS_AGE_KEY`** for that `(repo, context)`. Safe to
run in CI, Codespaces, or GitHub Agents.

#### `dist-decrypt-env` — dotenv to stdout (no disk)

Decrypts `*.env.sops` files only. Never writes plaintext env files to disk.

| Invocation | Stdout | Notes |
|------------|--------|-------|
| `make dist-decrypt-env` | All decryptable env files as dotenv `KEY=VALUE` lines | Append to `$GITHUB_ENV` in Actions |
| `make dist-decrypt-env FILE=ci/sentry.env` | One env file as dotenv lines | Logical name, no `.sops` suffix |
| `make dist-decrypt-env KEY=AUTH_TOKEN` | Raw value only | Scans all decryptable env files; errors if key appears in more than one file |
| `make dist-decrypt-env FILE=ci/sentry.env KEY=AUTH_TOKEN` | Raw value only | Disambiguates or avoids scanning |
| `make dist-decrypt-env KEY=AUTH_TOKEN FORMAT=dotenv` | `AUTH_TOKEN=value` | For `$GITHUB_ENV` export of one key |

**Environment:** `SOPS_AGE_KEY` (required).

**Script:** `dist-decrypt-env.sh` (repo root, shipped with cone-mode checkout).

#### `dist-decrypt` — files to disk (no env output)

Decrypts SOPS files to **plaintext sibling files** under `dist/`. Does **not**
emit environment assignments — use `dist-decrypt-env` for dotenv secrets.

| Invocation | Output | Notes |
|------------|--------|-------|
| `make dist-decrypt` | All decryptable files to disk | `.env` → sibling file; binary → sibling file |
| `make dist-decrypt FILE=ci/AuthKey_BV7QPDLS45.p8` | One file to disk | Logical name, no `.sops` suffix |

**Environment:** `SOPS_AGE_KEY` (required).

**Script:** `dist-decrypt.sh` (repo root).

### Least-privilege hierarchy

Use the narrowest target that satisfies the job:

1. **One key, one command** (preferred for single-value needs):

   ```yaml
   - name: Use required secret for one command only
     env:
       SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
     run: AUTH_TOKEN="$(make -C _secrets dist-decrypt-env KEY=AUTH_TOKEN)" npm run build
   ```

2. **Export to job environment** (when later steps need env vars):

   ```yaml
   - name: Export one required secret for later steps
     env:
       SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
     run: make -C _secrets dist-decrypt-env KEY=AUTH_TOKEN FORMAT=dotenv >> "$GITHUB_ENV"

   - name: Export all decryptable env secrets for later steps
     env:
       SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
     run: make -C _secrets dist-decrypt-env >> "$GITHUB_ENV"
   ```

3. **Decrypt files to disk** (binary secrets, signing material):

   ```yaml
   - name: Decrypt signing files to disk
     env:
       SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
     run: make -C _secrets dist-decrypt FILE=ci/AuthKey_BV7QPDLS45.p8
   ```

### Sample Makefile excerpt

Consumer targets only; the kit has the full Makefile and maintainer targets.

```make
# Decrypt dotenv secrets to stdout (consumer-safe). See dist-decrypt-env.sh.
dist-decrypt-env: ## SOPS_AGE_KEY=... make dist-decrypt-env [FILE=ci/sentry.env] [KEY=...] [FORMAT=dotenv]
	@FILE="$(FILE)" KEY="$(KEY)" FORMAT="$(FORMAT)" bash ./dist-decrypt-env.sh dist

# Decrypt dist/ files to disk (consumer-safe). See dist-decrypt.sh.
dist-decrypt: ## SOPS_AGE_KEY=... make dist-decrypt [FILE=ci/AuthKey_BV7QPDLS45.p8]
	@FILE="$(FILE)" bash ./dist-decrypt.sh dist
```

## GitHub secret stores by context

Each `(repo, context)` gets its own age keypair, used by both strategies. The
secret is always named `SOPS_AGE_KEY`; only the value differs per store. When a
repo secret and an environment secret share a name, a job in that environment
sees the environment's.

| Context | Store | Provisioning |
|---------|-------|--------------|
| `actions` | GitHub Actions, repo level | `gh secret set SOPS_AGE_KEY --app actions` |
| `env-<env>` | GitHub Actions, environment `<env>` | `gh secret set SOPS_AGE_KEY --env <env>` |
| `codespaces` | Codespaces | `gh secret set SOPS_AGE_KEY --app codespaces` |
| `dependabot` | Dependabot | `gh secret set SOPS_AGE_KEY --app dependabot` |
| `agents` | GitHub Agents (Copilot coding agent) | `gh secret set SOPS_AGE_KEY --app agents` |

A single repo's `secrets-mint` and the estate kit's `make mint` and
`make set-keys` cover every row.
