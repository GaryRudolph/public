# Secrets Repository — Makefile Targets

Recommended Makefile contract for a `<workspace>-secrets` repo. Full architecture
and script bodies: [repository.md](repository.md).

Placeholders: `<org>`, `<workspace>`, `<repo>`.

## Maintainer-local targets

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
| `verify` | Lint access map, key registry, round-trips | — |
| `clean` | Delete plaintext siblings under `src/` and `dist/` | — |

## Consumer-safe targets

Require only the consumer's **`SOPS_AGE_KEY`** for that `(repo, context)`. Safe to
run in CI, Codespaces, or GitHub Agents.

### `dist-decrypt-env` — dotenv to stdout (no disk)

Decrypts `*.env.sops` files only. Never writes plaintext env files to disk.

| Invocation | Stdout | Notes |
|------------|--------|-------|
| `make dist-decrypt-env` | All decryptable env files as dotenv `KEY=VALUE` lines | Append to `$GITHUB_ENV` in Actions |
| `make dist-decrypt-env FILE=oss.env` | One env file as dotenv lines | Logical name, no `.sops` suffix |
| `make dist-decrypt-env KEY=PUBLIC_API_URL` | Raw value only | Scans all decryptable env files; errors if key appears in more than one file |
| `make dist-decrypt-env FILE=oss.env KEY=PUBLIC_API_URL` | Raw value only | Disambiguates or avoids scanning |
| `make dist-decrypt-env KEY=PUBLIC_API_URL FORMAT=dotenv` | `PUBLIC_API_URL=value` | For `$GITHUB_ENV` export of one key |

**Environment:** `SOPS_AGE_KEY` (required).

**Script:** `dist-decrypt-env.sh` (repo root, shipped with cone-mode checkout).

### `dist-decrypt` — files to disk (no env output)

Decrypts SOPS files to **plaintext sibling files** under `dist/`. Does **not**
emit environment assignments — use `dist-decrypt-env` for dotenv secrets.

| Invocation | Output | Notes |
|------------|--------|-------|
| `make dist-decrypt` | All decryptable files to disk | `.env` → sibling file; binary → sibling file |
| `make dist-decrypt FILE=ios/AuthKey_BV7QPDLS45.p8` | One file to disk | Logical name, no `.sops` suffix |

**Environment:** `SOPS_AGE_KEY` (required).

**Script:** `dist-decrypt.sh` (repo root).

## Least-privilege hierarchy

Use the narrowest target that satisfies the job:

1. **One key, one command** (preferred for single-value needs):

   ```yaml
   - name: Use required secret for one command only
     env:
       SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
     run: PUBLIC_API_URL="$(make -C _secrets dist-decrypt-env KEY=PUBLIC_API_URL)" npm run build
   ```

2. **Export to job environment** (when later steps need env vars):

   ```yaml
   - name: Export one required secret for later steps
     env:
       SOPS_AGE_KEY: ${{ secrets.SOPS_AGE_KEY }}
     run: make -C _secrets dist-decrypt-env KEY=PUBLIC_API_URL FORMAT=dotenv >> "$GITHUB_ENV"

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
     run: make -C _secrets dist-decrypt FILE=ios/AuthKey_BV7QPDLS45.p8
   ```

## Sample Makefile excerpt

Consumer targets only; see [repository.md](repository.md) for the full Makefile
and maintainer targets.

```make
# Decrypt dotenv secrets to stdout (consumer-safe). See dist-decrypt-env.sh.
dist-decrypt-env: ## SOPS_AGE_KEY=... make dist-decrypt-env [FILE=oss.env] [KEY=...] [FORMAT=dotenv]
	@FILE="$(FILE)" KEY="$(KEY)" FORMAT="$(FORMAT)" bash ./dist-decrypt-env.sh dist

# Decrypt dist/ files to disk (consumer-safe). See dist-decrypt.sh.
dist-decrypt: ## SOPS_AGE_KEY=... make dist-decrypt [FILE=ios/AuthKey_BV7QPDLS45.p8]
	@FILE="$(FILE)" bash ./dist-decrypt.sh dist
```

## GitHub secret stores by context

Each consumer `(repo, context)` gets its own age keypair. The secret is always
named `SOPS_AGE_KEY`; only the value differs per store:

| Context | Store | Provisioning |
|---------|-------|--------------|
| `actions` | GitHub Actions | `gh secret set SOPS_AGE_KEY --app actions` |
| `codespaces` | Codespaces | `gh secret set SOPS_AGE_KEY --app codespaces` |
| `dependabot` | Dependabot | `gh secret set SOPS_AGE_KEY --app dependabot` |
| `agents` | GitHub Agents (Copilot coding agent) | `gh secret set SOPS_AGE_KEY --app agents` |

`make set-keys` maps `actions`, `codespaces`, `dependabot`, and `agents` to their
native `--app` stores. Other context names are out of scope for this contract.
