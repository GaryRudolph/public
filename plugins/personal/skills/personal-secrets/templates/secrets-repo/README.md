# <estate>-secrets

Secrets for the <estate> estate, stored as SOPS + age ciphertext. Nothing
here is plaintext: only `*.sops` files are tracked under `src/`, `dist/`,
and `keys/`.

- `src/` holds the editable originals, readable only by maintainers and
  break-glass.
- `dist/` is what consumer CI checks out. Each file there is encrypted to
  the `(repo, context)` keys that `access.map` grants it.
- `access.map` is the source of truth for who can decrypt what.

Run `make` to list targets; [Makefile.md](Makefile.md) covers the common
flows. The architecture is Gary Rudolph's secrets standard
(`standards/secrets/` in GaryRudolph/public).
