# Makefile

Which key each group of targets needs:

| Targets | Key |
| --- | --- |
| `build`, `src-decrypt`, `src-encrypt`, `mint`, `rotate`, `retire`, `verify`/`test`, `set-keys` | A maintainer (source) age key: `SOPS_AGE_KEY_FILE`, or sops' default `keys.txt` |
| `dist-decrypt-env`, `dist-decrypt` | The consumer's `SOPS_AGE_KEY` for its `(repo, context)` |
| `lint`, `ci`, `pre-commit`, `doctor`, `clean`, `help` | None |

Nothing needs a source key in CI.

## Common flows

**First-time setup.** Fill in `.sops.yaml` and `breakglass.pub`, set
`OWNER` in the Makefile, then `make init`.

**Add or edit a secret.**

```bash
make src-decrypt FILE=oss.env       # plaintext sibling appears in src/
$EDITOR src/oss.env
make src-encrypt FILE=oss.env       # back to .sops; plaintext deleted
make build && make verify
git add -A && git commit            # the hook checks src/ and dist/ pair up
```

A new file is the same, starting from a plaintext file in `src/`; add a line
for it to `access.map` before `make build`.

**Add a consumer.** `make mint REPO=app CONTEXT=actions`, grant `app__actions`
in `access.map`, `make build`, commit, then
`CONFIRM_SET_KEYS=1 make set-keys REPO=app CONTEXT=actions`.

**Change access.** Edit `access.map`, `make build`, `make verify`, commit.
Revoking stops future reads at HEAD; old ciphertext stays readable in git
history, so rotate the upstream value if it matters.

**Rotate a consumer key.** `make rotate REPO=app CONTEXT=actions`, `make build`,
commit, `CONFIRM_SET_KEYS=1 make set-keys REPO=app CONTEXT=actions`.

**Remove a consumer.** Remove it from `access.map`, `make build`,
`make retire REPO=app CONTEXT=actions`, commit, then
`gh secret delete SOPS_AGE_KEY -R <owner>/app --app actions`.

## Guards

- `.gitignore` tracks only `*.sops` under `src/ dist/ keys/`.
- The pre-commit hook (`make init` wires it) refuses staged plaintext,
  `src/` changes without matching `dist/`, and `access.map` changes without
  a rebuild.
- `.github/workflows/freshness.yml` runs the same checks keylessly in CI.
- `make verify` proves every identity decrypts exactly the files it's
  granted, and that `dist/` matches `src/`.
- `set-keys` writes to GitHub, so it refuses without `CONFIRM_SET_KEYS=1`.
