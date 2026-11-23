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
| Cursor CLI | The installer, `~/.cursor/cli-config.json` | `Shell(<base>:<args>)`, exact by our reading (untested, below); no rule for one word | `Shell(<base>:<args>*)` | `Mcp(server:tool)` | none |
| Gemini CLI | The installer, `~/.gemini/policies/<org>-managed.toml` | `commandRegex`, exact | `commandPrefix` | none | none |

Cursor IDE alone still matches allows as prefixes. `permissions.json` has no
documented exact form, and the Owner's call (2026-11-23, r1.f1 m4) is to keep it that
way: `git log`, `make test` and `git fetch` keep auto-running there, and
`enforce-denylist.sh` keeps enforcing the denies the IDE ignores, unchanged,
so `hooks.sh` stays the same in every repo that shares it. Cursor CLI and
Gemini stay with the installer too, since neither can take allows from a
plugin or extension (below).

A Gemini allow is a `commandRegex` that matches only the entry:
`git log` becomes `commandRegex = "git log\""`. Gemini searches
`\x00"command":"(?:<regex>)` in the JSON of the tool's arguments, so the
entry is JSON-escaped, then RE2-escaped, then closed with the value's ending
`"` (`gemini_allow_regex` in [`../lib/allowlist.jq`](../lib/allowlist.jq)).
Gemini splits compound commands and checks each part, and a redirection still
asks. A compound of allowed commands (`git status && git diff`) matches no
rule as a whole: interactive Gemini upgrades it to allow when every part is
allowed and its workspace, git-trust and dangerous-command checks pass, but
headless Gemini (`gemini -p`) starts from deny and refuses it. Run the parts
as separate calls there; no rule form allows the chain without widening.

## What each harness offers

Checked 2026-11-23 against the vendor docs, and for Gemini its source at
v0.70.0 (links below, pinned to that tag). "Hook `allow`" is what a hook answering allow does to
the approval prompt.

| Target | Org or team control | A plugin or extension can carry | Hook `allow` | Exact-match form |
| --- | --- | --- | --- | --- |
| Cursor IDE | Team dashboard Run Mode controls (Enterprise) win over `permissions.json` and the IDE list, and users can't add entries; MDM can push `~/.cursor/permissions.json` | Hooks (the `.cursor-plugin` `hooks` key; command hooks only, merged after enterprise, team, project and user hooks). No permission rules | Not documented to skip the prompt; forum reports say it only doesn't block. `deny` blocks in every mode. `ask` prompts for `beforeShellExecution` (3.28, documented for Auto-review), not for `preToolUse` | None documented. Entries are prefixes; `base:argsglob` exists (`npm:install*`), but the docs don't say whether `git:log` is exact |
| Cursor CLI | Team settings win over both config files; the admin command denylist and team MCP config apply in the CLI | Plugins load (`/plugin`, `--plugin-dir`) and their hooks run. No permission rules | Not documented to skip the prompt; treat it as only not blocking. `ask` prompts (Oct 2026) | `Shell(base:args)`, where args is a glob; the docs don't say exact or prefix. `Shell(word)` is any arguments |
| Gemini CLI | Admin policy tier (5) in a root-owned system dir (`/etc/gemini-cli/policies`, macOS `/Library/Application Support/GeminiCli/policies`) outranks the user tier (4). The Management Console sets strict mode, extensions, MCP and skills, but no command rules | Hooks (`hooks/hooks.json`, which the personal plugin already ships) and `policies/*.toml` at tier 2, where `allow` and yolo rules are dropped | A `BeforeTool` hook runs before the policy check; only its deny or `ask` changes the outcome | `commandRegex`, searched as `\x00"command":"(?:<re>)` in the sorted args, each top-level pair wrapped in `\0`, so a pattern ending in `"` pins the end. RE2. Compound commands are split and each part checked; a redirection turns allow into ask |

What follows from it:

- No harness lets a plugin or extension carry allows, and a hook's `allow`
  never skips a prompt. Allows stay a local file everywhere, unless a Cursor
  Enterprise dashboard or a root-installed Gemini admin dir takes them.
- A plugin hook can carry denies and asks for both Cursor IDE and Cursor CLI,
  with no install step.
- Gemini denies belong in the same user-tier file as the allows. An extension's
  tier 2 deny ranks below any user-tier allow.
- A repo can widen Cursor. A per-repo `.cursor/permissions.json` is
  concatenated with the user's, so a cloned repo can add allows. A project
  `.cursor/cli.json` reportedly replaces the global permissions block, which
  would drop the global denies (Cursor staff on the forum, not the docs).

The docs leave three things open. Each needs a test on a Mac:

- whether `git:log` in `permissions.json` and `Shell(git:log)` in
  `cli-config.json` match `git log` alone;
- whether `*` in a CLI args glob crosses spaces and slashes;
- whether a hook's `ask` prompts in Allowlist mode, or for a command already on
  the allowlist.

Sources: Cursor [permissions.json](https://cursor.com/docs/reference/permissions),
[hooks](https://cursor.com/docs/agent/hooks),
[plugins](https://cursor.com/docs/reference/plugins),
[run modes](https://cursor.com/docs/agent/security/run-modes),
[CLI permissions](https://cursor.com/docs/cli/reference/permissions),
[CLI changelog](https://cursor.com/docs/cli/changelog); Gemini
[policy engine](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/reference/policy-engine.md),
[extensions](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/extensions/reference.md),
[hooks](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/hooks/index.md),
[enterprise](https://github.com/google-gemini/gemini-cli/blob/v0.70.0/docs/cli/enterprise.md),
and `packages/core/src/policy/{utils,stable-stringify,config,policy-engine}.ts`
and `packages/core/src/scheduler/scheduler.ts` for the regex anchor and the
`\0` pair wrapping, the dropped extension allows, the compound-command
upgrade and the hook order.
