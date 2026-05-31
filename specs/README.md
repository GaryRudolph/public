# Specs

Home for cross-cutting technical specs, designs, and data-model references in
this repo — documents that describe *what we are building and why*, and that
don't belong to a single skill, tool, or language folder.

Per `standards/documentation.md`: spec filenames are lowercase-kebab with no
`-spec` suffix (the folder already implies it); `README.md` is the one
ALL_CAPS filename allowed here. Throwaway drafts and research go to `.scratch/`
(gitignored), not here.

## Index

| Spec | What it covers |
|---|---|
| [macwhisper-database.md](macwhisper-database.md) | MacWhisper's on-disk SQLite schema + `ExternalMedia/` layout, conventions (BLOB-UUID/hex, time model, soft-delete), the FTS5 mirror + triggers, media-file naming/`type` enums, schema-drift handling, and the read-only/write safety contract for the whisper tooling. |
