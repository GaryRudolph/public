# Working in this repo

Gary's personal standards load separately: from the `personal` plugin in
Claude surfaces, or from the home-directory blocks `agents/Makefile`
installs. This file only covers the layout of this repo.

- `plugins/` is the source of truth for standards and skills. The repo-root
  `standards` and `agents/AGENTS.md` paths are symlinks into
  `plugins/personal/skills/personal-standards/`. Edit the real files.
- Keep every plugin self-contained: no paths above the plugin root, no
  top-level `bin/`. See `plugins/README.md` for the rules.
- After changing anything under `plugins/` or `agents/`, run
  `make -C agents validate test`.
- `specs/agent-distribution.md` explains why the repo is laid out this way;
  `agents/runbook.md` has the setup steps.
