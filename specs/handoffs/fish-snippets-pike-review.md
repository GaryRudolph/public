Agents now write any shell command they hand Gary in fish, fenced `fish`, since bash snippets that set variables break when pasted into his shell. The rule lives in the always-loaded `core.md` and outranks a harness default that says to fence `bash`.

## Review guide

Review tier: [check], because `core.md` changes what every agent session does.
Blast radius: agent replies, handoffs, plans and runbooks in Gary's own repos; scripts, Makefiles, CI and team repos are out of scope. Docs only, a revert is safe.
Review time: ~4 min

1. [check] `plugins/personal/skills/personal-standards/core.md`: new Workflow bullet "Write shell commands for me in fish"
2. [skim] `plugins/personal/skills/personal-standards/standards/documentation.md`: new "Shell Snippets" section and Contents link
3. [skip] `plugins/personal/cursor/rules/personal-core.mdc` (`make -C agents cursor-core-rule`)

## Validation

- `make -C agents validate test`: pass, core.md still splits into three SessionStart parts under the hook cap

## Rollback

Revert the squash commit.

<details>
<summary>[check] Agent behavior</summary>

| Situation | Before | After |
| --- | --- | --- |
| Command for Gary to run | harness default, `bash` | fish, fenced `fish` |
| Export a variable | `export NAME=value` | `set -gx NAME value` |
| One command's value | `NAME=value cmd` | same (fish 3.1+) |
| Scripts, Makefiles, CI, agent's own tool calls | own shell | unchanged |
| Repo docs written in another shell | n/a | follow the repo |

</details>

<details>
<summary>Decisions</summary>

- Scoped to commands Gary types by hand: shebang scripts and CI stay POSIX `sh` or bash so they run anywhere.
- Left the existing `bash`-fenced examples in the Go, Python, git and secrets standards alone; most are plain commands that run the same in fish.

</details>
