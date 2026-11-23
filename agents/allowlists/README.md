# Allowlists

`personal.json` is the one canonical allowlist: which shell commands, MCP tools
and web domains an agent may use without asking, and which it may never use.
Every harness gets its rules rendered from this file. Edit it here, never in a
harness's own settings.

## Format

One JSON object. Every key is optional; anything else stops the render
(`meta_check` in [`../lib/allowlist.jq`](../lib/allowlist.jq)).

| Key | Lists | An entry is |
| --- | --- | --- |
| `shell` | `allow`, `deny` | A command line as an agent writes it: `git status`, `rm -rf /` |
| `mcp` | `allow`, `deny` | `server:tool`, or `server:*` for every tool on that server |
| `webfetch` | `allow`, `deny` | A domain, or `*.domain` for its subdomains |
| `read` | `deny` | A path pattern an agent may not read: `~/.ssh/**`, `./.env` |
| `write` | `deny` | A path pattern an agent may not edit |

Every list is an array of non-empty strings. Shell entries are trimmed and
their runs of whitespace collapsed (unless they quote) before any target sees
them.

What each list means:

- **allow:** the exact entry runs without a prompt. A shell allow covers that
  command line and nothing longer, because a prefix would also approve the
  flags that run programs or write files (`git fetch --upload-pack=`,
  `rg --pre`, `sort -o`). Where a harness can't express "exactly this", it
  gets the nearest form that doesn't widen it, or no rule (table below).
- **deny:** the entry and anything that starts with it is refused. Denies
  match the command text, not the program, so they stop the forms an agent
  usually writes; they aren't a security boundary.
- Anything on neither list prompts.

MCP allows name each tool: a server wildcard would approve a tool the server
adds later, such as one that sends or shares. The PR that named them (#98)
has the per-server classes.

## Where it goes

| Target | Gets the file through | Shell allow | Shell deny | MCP | Web, read, write |
| --- | --- | --- | --- | --- | --- |
| Claude Code (CLI, IDE, cloud) | Managed settings the Owner pastes into each org ([`../org/`](../org/README.md)) | `Bash(<entry>)`, exact | `Bash(<entry>:*)` | `mcp__server__tool` | `WebFetch(domain:)`, `Read()`, `Edit()` denies |
| Claude Code, local | The installer, each config dir's `settings.json` (until the managed settings are live) | same | same | same | same |
| Cursor IDE | The installer, `~/.cursor/permissions.json` | raw prefix | not read by Cursor; the installed hook enforces it | `server:tool` | none |
| Cursor CLI | The installer, `~/.cursor/cli-config.json` | `Shell(<base>:<args>)`, exact; no rule for one word | `Shell(<base>:<args>*)` | `Mcp(server:tool)` | none |
| Gemini CLI | The installer, `~/.gemini/policies/<org>-managed.toml` | `commandPrefix` | `commandPrefix` | none | none |

Cursor IDE and Gemini still match allows as prefixes; closing that is the next
milestone of `specs/handoffs/plan-allowlist-managed-heron.md`.
