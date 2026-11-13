# Handoff: session proxy port mismatch on the gcp-linux runner

Symptoms only, as observed from inside one session. For a bug report to Anthropic about `claude self-hosted-runner`; not work for this repo. Remove this file before the branch merges.

## Session

- Session: `cse_01BNKwNYMcvjXv32ytkne5ih` (claude.ai/code/session_01BNKwNYMcvjXv32ytkne5ih)
- Environment: `gcp-linux`, self-hosted runner on Google Cloud Run, client label `linux-65edb9e9`
- Runner command (PID 1): `claude self-hosted-runner --client-label linux-65edb9e9 --base-dir /scratch/workspace --capacity 1 --remove-session-state --confine-repo-settings enforce --environment-secret-file ...`
- Claude Code: 2.1.323 (`--print --sdk-url .../v1/code/sessions/cse_01BN...`)
- Repo: GaryRudolph/public, branch `claude/session-lifecycle-cloud-run-evei3b`

## What failed

Every `git push` to github.com, from 06:27 UTC on:

    fatal: unable to access 'https://github.com/GaryRudolph/public/': Failed to connect to 127.0.0.1 port 34997 after 0 ms: Couldn't connect to server

Eight attempts between 06:27 and 06:31, with backoff, all the same. `curl http://127.0.0.1:34997/__agentproxy/status` also refused. No git network command had been run earlier in the session, so there's no earlier success to compare with.

## What the session state showed (06:37 to 06:42 UTC)

- **Git config points at 34997.** `$GIT_CONFIG_GLOBAL` = `/scratch/workspace/_sessions/cse_01BNKwNYMcvjXv32ytkne5ih.gitconfig`, modified 06:26, holds `http.https://github.com/.proxy http://127.0.0.1:34997` and `http.https://github.com/.sslcainfo .../ccr/ca-bundle.crt`.
- **The proxy README says 34997 too.** `.../ccr/README.md`: "Outbound HTTPS from this session goes through a local proxy at http://127.0.0.1:34997 (set via HTTPS_PROXY)". README and `ca-bundle.crt` both modified 06:26:11; `ccr/bin` is from 06:16:45.
- **The only listening TCP socket is 127.0.0.1:39971** (`/proc/net/tcp`). Nothing listens on 34997.
- **39971 is the agent proxy.** `GET 127.0.0.1:39971/__agentproxy/status` returns `"enabled": true, "port": 39971`, the same `caBundlePath`, `"gitConfigInjection": false`, `"gitConfigConflicts": ["git_http_proxy_configured", "git_ssl_cainfo_configured"]`, `"recentRelayFailures": []`.
- **No proxy env vars in the Bash tool's shell.** `env` shows no `HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY` or `ALL_PROXY`, though the README says HTTPS_PROXY is set.
- **No restart.** Container boot 06:16:34; PID 1 runner 06:16:35; Claude process (PID 111) 06:16:43; all still running at 06:41. Only one session directory under `/scratch/workspace/_sessions/`.

## Timeline (UTC)

- 06:16:34-06:16:45: container, runner, Claude process start; `ccr/bin` written.
- 06:26:11: `ccr/README.md` and `ccr/ca-bundle.crt` rewritten; the gitconfig is also modified at 06:26. Around the same minute the session left plan mode (the plan was approved) and ran its first commands outside it.
- 06:27-06:31: pushes fail against 34997.
- ~06:38: `git -c http.https://github.com/.proxy=http://127.0.0.1:39971 push` succeeds on the first try. The config file was left as it was.

## What can't be seen from inside

Which port the proxy listened on before 06:26, and what rewrote the README, CA bundle and gitconfig at 06:26. The facts above don't show whether the proxy moved ports or the files were written with the wrong one.

## Workaround

Per command: `git -c http.https://github.com/.proxy=http://127.0.0.1:<port from /proc/net/tcp or the status endpoint> push ...`. Editing the gitconfig would also work but wasn't done.
