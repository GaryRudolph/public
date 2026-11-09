# secrets/

Encrypted secrets for this repo: SOPS + age, per the personal secrets
standard (`standards/secrets/single-repo.md`). Only `*.sops` is committed;
the cleartext you edit sits beside it and is gitignored.

| Scope | Opened by | Holds |
|---|---|---|
| `ci/` | Maintainers, break-glass, the repo's Actions key | What CI builds, signs and publishes with |
| `dev/` | Maintainers, break-glass, developers, the `dev` environment key | Runtime secrets for dev |
| `prod/` | Maintainers, break-glass, the `prod` environment key | Runtime secrets for prod |

`.sops.yaml` names every key. `make help` lists the `secrets-*` targets:
`secrets-decrypt FILE=prod/api.env`, edit, `secrets-encrypt FILE=prod/api.env`,
`secrets-clean`.
