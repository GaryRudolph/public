# Secrets Management

Standards for externalizing secrets out of application source repos. The default
rule: **never commit plaintext secrets to a source repository.**

## Where secrets live

Secrets belong in one of:

- **Environment variables** at runtime (local `.env` gitignored, CI secrets)
- **Managed secret stores** (cloud KMS, platform secret managers)
- **A dedicated encrypted secrets repository** — a private repo holding SOPS +
  age ciphertext, consumed by CI at deploy time

This section documents the third option as a **candidate reference architecture**
for estate-wide secret management. It is not a universal default; adopt it when
GitHub-only tooling and per-repo access control fit your estate.

An **estate** is the operational scope served by one secrets repo: an org,
product line, workspace, app family, or single project. Choose the boundary that
matches today's access-control needs; split later if the estate grows.

## When to use the secrets repository pattern

Good fit:

- Multiple repos share secrets with different access levels
- You want version-controlled secret changes with review, without plaintext in git
- CI needs secrets but you refuse an always-on key that can read editable source
- Pure-frontend and server-backed projects share the same model

Tradeoffs to accept:

- **Git history is permanent** — committed ciphertext (and any leaked key) exposes
  historical secret values; rotating a leaked value means revoking at the upstream
  provider, not just `git revert`.
- **Centralized key custody** — `keys/repos.env.sops` holds every consumer private
  key, encrypted to maintainer source keys; a maintainer key compromise exposes all
  consumer contexts.
- **Operational overhead** — maintainers run local `make build` after every
  source change; `dist/` must stay in sync with `src/`.

## Least-privilege consumption hierarchy

Prefer the narrowest mechanism that satisfies the toolchain:

1. **One key, one command** — `make dist-decrypt-env KEY=...` emits the raw value
   for inline injection; nothing lands in the job environment.
2. **Export to the job environment** — `make dist-decrypt-env KEY=... FORMAT=dotenv
   >> "$GITHUB_ENV"` for one key, or `make dist-decrypt-env >> "$GITHUB_ENV"` for
   all decryptable env files the context key can open.
3. **Decrypt files to disk** — `make dist-decrypt FILE=...` (or all files) only
   when the toolchain requires files on disk (binary certs, `.p8`, `.p12`, etc.).
   `dist-decrypt` never emits environment assignments.

See [makefile.md](makefile.md) for the full target contract and GitHub Actions
examples.

## Threat model (summary)

- **`src/`** — readable only by maintainer personal keys + offline break-glass. No
  CI key can decrypt source.
- **`dist/`** — each file encrypted to its mapped consumer `(repo, context)` keys
  + break-glass. The Secrets GitHub App only grants ciphertext download.
- **Consumer key leak** — attacker decrypts only files that key is a recipient of,
  including git history for those files. `make rotate` stops *future* access; rotate
  the upstream secret values too if the private key may have leaked.
- **Secrets App key leak** — attacker downloads ciphertext they still cannot decrypt.
- **Break-glass key** — opens everything; offline only.

Full detail: [repository.md](repository.md#threat-model).

## Documentation map

| File | Purpose |
|------|---------|
| [repository.md](repository.md) | Candidate reference architecture: repo layout, access matrix, scripts, runbook |
| [makefile.md](makefile.md) | Makefile target contract for maintainers and consumers |
