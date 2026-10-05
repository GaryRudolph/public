# Research: round two follow-ups

Six tracks, each checked by an independent verifier who re-ran the code and re-read the sources (2026-10-05). The full raw outputs died with the container's scratch space. This file keeps the conclusions, the corrections the verifiers made, and the open decisions.

## 1. Resource history

**Recommendation: a head record plus append-only full-snapshot revisions.** This is your App Engine parent-plus-child-versions pattern. AWS documents the same shape for DynamoDB ("v0 = latest" version items), and S3 object versions, GCS generations, Drive revisions and Confluence page versions all follow it. It is not event sourcing.

**Naming.** Call them *revisions*: `/books/{id}/revisions/{n}`. versioning.md already uses "version" for API contracts and artifacts, and Drive and MediaWiki say "revisions".

**Head and revisions:**
- **Head:** the current state, plus an integer `revision`, `state`, `createdAt` and `updatedAt`.
- **Revisions:** keyed `(resourceId, revision)`, insert-only. Each holds a full snapshot plus `revision`, `createdAt` (that commit's time), `actor` (a principal id, never an email), `requestId` and `schemaVersion`. No `{from, to}` pairs. The current state is a revision too, so `GET …/revisions/{n}` works the same for every `n`.
- **Same transaction.** Head and revision are written in the same transaction as the mutation.
- **Counter rules:** the revision is an integer per resource, starting at 1 and incremented once per committed change. It's never reused; the counter lives on the head, so it survives purges. This doesn't conflict with random ids, because it's scoped under the parent and allocated inside the parent's transaction.

**Concurrency and writes:**
- **ETag:** `ETag: "<revision>"`. `If-Match` compares against it and returns `412` on mismatch, which is how GCS uses `generation`. Use strong tags. JSON and protobuf representations get distinct tags (`"7"` vs `"7-pb"`), and so does in-app gzip (chi's `Compress` doesn't do this). Parse the leading integer. Keep Cloud CDN's dynamic compression, which weakens ETags, off write paths.
- **No-op writes:** a write that changes nothing creates no revision.

**Lifecycle and timestamps:**
- **Delete:** `DELETE` writes a revision with state `DELETED`. The delete time is that revision's `createdAt` (equal to the head's `updatedAt`), so there's no `deleteTime`.
- **Undelete and restore:** undelete is a new `ACTIVE` revision; restore copies snapshot `n` into a new revision. History is never rewound.
- **`createdAt` stays on the head:** it's the default sort key with random ids, and retention may purge revision 1.

**Encryption and erasure:**
- **Encryption:** revisions are encrypted exactly like the head, and unchanged fields carry their ciphertext forward. Use per-subject (or per-tenant) Tink keysets wrapped by a per-tenant Cloud KMS KEK.
- **Erasure:** crypto-shredding makes the head, every revision, exports and backups unreadable at once. The erasure window is the *longest* of the keyset store's backups, Firestore backups (up to 14 weeks), Cloud SQL backups and any BigQuery copy, not 7 days. Whether that satisfies GDPR Art. 17 is a question for counsel.
- **Activity log:** `{time, actor, method, resource, revision, requestId, outcome}` with no field values, so it needs no field-level encryption. Actor ids are still pseudonymous personal data, so the log needs retention and access control. Revisions already answer who changed what, so the activity log mainly covers reads, exports and actions that don't create a revision.

**Housekeeping:**
- **Retention:** set per resource type, and never purge the current revision. Use a purge job, not Firestore TTL. Store `schemaVersion` and upcast on read; never rewrite old rows.
- **Large fields:** immutable GCS objects, referenced by the revision and carried forward when unchanged.

**API surface:**
- `GET …/revisions` (newest first, paginated), `GET …/revisions/{n}` (`{revision, createdAt, actor, snapshot}`), and `POST …/revisions/{n}:restore` (with `If-Match` on the head).
- If the parent is `DELETED`, these return 404 unless `showDeleted=true`.
- Reading history needs at least the parent's read permission; consider a separate permission, since history shows values that were removed.
- Recommend no diff endpoint until a client needs one; clients compare snapshots. If one is added, pick between RFC 7396 (the house PATCH format, so it can be replayed) and RFC 6902 (precise for arrays and explicit nulls).

**Firestore (Go):**
- **Layout:** `books/{id}` plus `books/{id}/revisions/{n}`, written in one `RunTransaction`: `tx.Get` the head, check 404/412, `tx.Set` the head, `tx.Create` the revision. Order by the integer field, not the doc id.
- **Indexing:** exempt the `snapshot` map from indexing, and run cross-entity history in BigQuery.
- **Enforcement is code-only.** IAM is per database, and server SDKs bypass Security Rules. Mitigate with Data Access audit logs, plus the BigQuery copy as tamper evidence.
- **The Stream Firestore to BigQuery extension is a best-effort analytics copy:** it can drop data during reconfiguration and keeps purged rows. Never use it as the history API.
- **Purge:** Go has no recursive delete. Delete revisions first with `BulkWriter`, check results, re-list until none are left, then delete the head.

**Postgres (Python):**
- **Schema:** a head table plus `<table>_revisions(id, revision, created_at, actor, request_id, schema_version, snapshot jsonb)`, maintained by one generic trigger pair. jsonb over typed mirror tables: no history migrations, and truly immutable. Store ciphertext as base64 text.
- **Grants:** the app role has no `DELETE` on the head and only `SELECT` on revisions. A separate purger role owns deletes.
- **Optimistic concurrency:** SQLAlchemy `version_id_col`, with `StaleDataError` mapped to 412.
- **Hardening (the verifier reproduced a bypass):**
  - The `SECURITY DEFINER` functions set `search_path = pg_catalog, pg_temp` and schema-qualify the table, or the app role can redirect history into a temp table.
  - A non-login owner role owns the functions and tables; the app role never owns tables.
  - Use `clock_timestamp()`, not `now()`, so revision times can't go backwards under concurrency.
  - Reject an empty `app.actor`.
- **No native option:** Postgres still has no system-versioned tables (the PG 19 docs say to emulate them with triggers).

**Why not the alternatives:**
- **Event sourcing:** projections and upcasting cost, and events carry values.
- **SQL:2011 temporal tables:** not in Postgres, and no actor.
- **CDC:** asynchronous, no actor, and a second copy to erase. Use it for analytics only.
- **Point-in-time recovery:** 7 days, so it's for recovery, not business history.

**Where it goes:** architecture.md gets a "Resource history" section with the generic rules. security.md gets the keyset hierarchy and the erasure window. go/ and python/architecture.md get the store specifics.

## 2. Timestamp naming

**Use `createdAt` / `updatedAt`, and `<verb>At` for every instant (`expiresAt`, `lastLoginAt`, `archivedAt`).**
- **Specs:** `*At` is the plurality across 41 public API specs (about 26 of 41), including GitHub, Shopify GraphQL, Linear, Vercel, Confluence, Stripe's `*_at` instants, Square, DigitalOcean, OpenAI and Anthropic.
- **Tools:** every tool that generates timestamp names uses it: Rails, Laravel, Sequelize, Mongoose, GORM, Supabase. Ecto's `inserted_at` is close.
- **Who doesn't:** Google (`createTime`), Kubernetes (`*Time`, `creationTimestamp`) and Microsoft (`*DateTime`) each go their own way.
- **Label:** no RFC or widely adopted spec settles it, so label it a house convention.

**Rules that come with it:**
- **Format:** RFC 3339 UTC with `Z` (RFC 9557 updates its meaning: UTC known, local offset unknown), in JSON bodies and query parameters only. Headers keep their own formats: IMF-fixdate for `Sunset`, `Last-Modified` and `Retry-After`; `@<epoch>` for `Deprecation`.
- **Precision:** truncate to microseconds on write; that's Firestore's, Postgres's and BigQuery's precision.
- **Python defaults are wrong:** pydantic writes naive datetimes with no offset and keeps local offsets. Use `AwareDatetime` plus a UTC serializer, and `timestamptz`.
- **Go defaults are wrong:** `encoding/json` keeps local offsets, and `omitempty` doesn't drop a zero `time.Time`. Use `.UTC()` and `omitzero`.
- **Protobuf:** `google.protobuf.Timestamp` for instants (ProtoJSON writes RFC 3339 `Z`). For interop, dates are `string` and durations are `int64 …Seconds`, because ProtoJSON renders `google.type.Date` as an object and `Duration` as `"5400s"`.
- **`createdAt` is server-set and `readOnly`.** Add a separate client-time field (Square's `client_created_at`) only if offline creation needs one.
- **Sorting:** with random ids, list endpoints sort on `(createdAt, id)` for stable pagination.
- **Purge time:** if a deleted resource exposes when it will be purged, reuse `expiresAt` (Cloud Run v2 does this) rather than inventing a name.

## 3. Admin bootstrap

**Practice:**
- **Mature tools** bootstrap through a path that already requires infrastructure access: a management CLI (Django `createsuperuser`, Mastodon `tootctl`, Discourse `rake admin:create`), a one-time expiring secret (GitLab's 24-hour `initial_root_password`, Jenkins), or first-boot config (Keycloak's *temporary* bootstrap admin).
- **"First visitor becomes admin"** (Gitea, Mattermost, Strapi) is only safe on a private network.
- **Email allowlists** (Discourse `DISCOURSE_DEVELOPER_EMAILS`) become a permanent backdoor: Discourse re-grants admin on every login, even after removal.
- **Staff access to customer tenants** in SaaS is a separate plane: corporate SSO, phishing-resistant MFA, time-limited elevation with a justification, and audit (Google's *Building Secure and Reliable Systems*, Okta and Salesforce support-access grants, GitLab Admin Mode, GitHub sudo mode).

**Recommendation for your stack** (needs a Workspace or Cloud Identity org):
- **Platform admins:**
  - A separate admin Cloud Run service behind IAP, with access granted by Google Groups bound in Terraform. The bootstrap is a reviewed Terraform PR, so there's no in-app window and no allowlist.
  - Split privileges with separate IAP services (`admin-read`, `admin-write`) rather than server-side group lookups, which would need a Workspace admin role for the service account.
  - Step-up through IAP reauthentication (`SECURE_KEY`). IAP's JWT has no `auth_time` for Google identities.
  - Key staff on `sub`.
- **Break-glass:** at least two standing Workspace super-admin accounts with security keys and separate daily accounts. Alert on every use and drill at least every 90 days. Don't gate break-glass on a PAM approval, which locks you out exactly when approvers are missing.
- **Tenant owners:**
  - The creator is the owner, written in the creating transaction.
  - "Never zero owners" is enforced transactionally across every path that removes ownership.
  - Disable client-side account deletion in Identity Platform (there is no before-delete hook) and route deletion through the server.
  - Orphaned tenants are recovered with an admin-plane `:assignOwner` that needs a justification, a second approver and an audit entry.
  - Tenant MFA is TOTP; Identity Platform has no WebAuthn second factor.
- **Local dev:**
  - The emulator in a `demo-<app>` project, plus `make dev-seed` that creates a dev admin and refuses to run against anything but `demo-` on localhost.
  - **Required guard:** with `FIREBASE_AUTH_EMULATOR_HOST` set, both Admin SDKs accept unsigned tokens with arbitrary claims. Python also skips the expiry checks and re-reads the variable on every verify call. So the guard lives in the single token-verify wrapper, not just at startup: fail closed unless the project is `demo-` and the code isn't running on Cloud Run.

**Generic rules for security.md:**
- No first-visitor-wins setup for privileged roles on anything internet-reachable.
- Bootstrap only through infrastructure access or a one-time expiring secret; bootstrap grants are temporary, logged and alerted.
- Identify principals by `iss` + `sub`, never by email (OIDC Core §5.7). An allowlist may only bind once to a subject with a verified email *and* domain (`hd`).
- Read privileged authority server-side from the authoritative store, not from long-lived token claims.
- Enforce "never zero owners" transactionally.
- Break-glass: at least two accounts, phishing-resistant MFA, alerted and drilled.
- Staff access to customer data: a separate plane with time-limited elevation and audit.
- Dev-only auth shortcuts fail closed outside local development.

The IAP, Groups, Identity Platform and emulator specifics go in a GCP/Firebase section, not security.md.

## 4. AI attribution

**What GitHub actually does:**
- The squash commit's author is **the PR's opener**, not the merger. Claude Code on the web opens PRs as `GaryRudolph`, so every squash on `main` is already authored by you, committed by `web-flow`, and Verified. Your model (AI author on the branch, you on `main`) is what already happens.
- What leaks is *trailers*:
  - The repo's squash default (`COMMIT_MESSAGES`) copies every branch commit message, trailers included.
  - GitHub appends `Co-authored-by: Claude <noreply@anthropic.com>` once per distinct commit author who isn't the PR opener. That email maps to the GitHub user `claude`, which gets the contribution credit.
- **Rebase merge** keeps Claude as the author on `main`, and git.md still recommends it "for clean branches".
- **Merge queue** ignores custom merge messages.

**Conventions:** Linux (`Assisted-by:`; since 2026-08 it uses `LLM` with no product or model name; agents never add `Signed-off-by`), Fedora (adopted 2025-10: "The contributor is always the author and is fully accountable"), Eclipse, LLVM and OpenInfra all use a human author plus an `Assisted-by:` trailer. Apache also permits `Co-authored-by` for a tool. GitHub's Copilot agent does the inverse (Copilot author, human co-author). AI-only output isn't copyrightable (Thaler, cert denied 2026-03), which supports the human-author model.

**Claude Code:**
- **The setting:** `attribution.commit` and `attribution.pr` are free strings, so `"Assisted-by: Claude Code"` works. `attribution.sessionUrl` controls `Claude-Session:`.
- **It's an instruction to the model, and a CLAUDE.md or memory rule beats it.** The ban currently lives only in git.md, which isn't in context when committing, so the harness default wins. That's why 18 of 50 commits on `main` carry a Claude co-author, including commits you made directly on `main` (4787426, 45af4d1).
- **Cloud reach:** cloud sessions read only the repo's `.claude/settings.json`, not user settings, and plugins can't carry the setting. This session never received core.md either; only the repo's AGENTS.md loaded. The dependable levers in cloud are repo files.

**Recommendation (human author plus `Assisted-by`), with mechanics:**
1. **Each repo:** squash commit message = PR title and description, and merge commits and rebase merges turned off. Remove git.md's "Rebase and merge" bullet.
2. **PR descriptions** end with `Assisted-by: Claude Code` (`attribution.pr`). When merging with the button, delete GitHub's `Co-authored-by: Claude` line in the message box. Alternatively merge through the REST/MCP merge API with an explicit `commit_message`; whether GitHub still appends co-author lines there is untested.
3. **Workstation:** you're already the author through `git config`. Set `attribution.commit` to `Assisted-by: Claude Code` in `~/.claude/settings.json` (install it from `agents/Makefile`), and in each repo's `.claude/settings.json` for cloud. Put the rule in core.md (always loaded) and in each repo's AGENTS.md.
4. **Optional, cloud:** set `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL` as environment variables in your personal cloud environment (environment menu, then Edit). Branch commits are then authored by you and still committed and signed by Claude, and GitHub adds no co-author. Verified status is untested until one push. Not needed if you're fine with Claude as the branch author.
5. **Enforcement:**
   - A required PR check (Actions) that an agent-assisted PR's description has `Assisted-by:`.
   - A push-to-`main` job that alarms if an agent co-author lands.
   - Ruleset commit-metadata restrictions are Enterprise-only.
6. **Human pair co-authors:** add them as `Co-authored-by` in the PR description. Co-author lines in branch commit messages don't survive a squash.
7. **DCO repos:** the human signs off, and the sign-off has to match the commit author, so use `GIT_AUTHOR_*` there.

**Proposed core.md line:**
> - **AI attribution**: you're the author; disclose the agent with an `Assisted-by: Claude Code` trailer, never an agent `Co-authored-by` or `Signed-off-by`; squash commits use the PR title and description (see git.md "AI Agent Behavior")

git.md gets the matching longer bullet, plus Merging and footer updates. Then run `make -C agents cursor-core-rule`.

## 5. Custom headers

**The RFCs back your pattern directly:**
- RFC 9110 §16.3.2.1: "limited-use fields … are encouraged to use a name that includes that use (or an abbreviation) as a prefix; for example, if the Foo Application needs a Description field, it might use 'Foo-Desc'". Also "Field names ought not be prefixed with 'X-'".
- RFC 6648 §3 says a name "could incorporate the organization's name".
- Newer vendor headers follow it: `Stripe-Version`, `Fly-Request-Id`, `Twilio-Request-Id`, `anthropic-version`, and OCI's `Docker-Content-Digest`. Older `X-` families persist where they shipped first.

**Proposed architecture.md text** (the rule row cites RFCs; the namespace choice is labeled a house convention):
- **Rule row:** `Custom headers | A standard header if one fits; otherwise {Product}-Name (Nowline-Request-Id), never X- | RFC 9110 §16.3.2.1, RFC 6648 §3`
- **Namespace:**
  - The namespace is the product name users see, shared by every service in it (`Nowline-`, not `NowlineApi-`); use the company name only for a header that spans products.
  - Names use letters, digits and hyphens, Title-Case, acronyms as words (`-Id`). Read them case-insensitively, since HTTP/2 sends lowercase.
  - A shipped name is permanent.
  - Registered and platform `X-` headers (`X-Content-Type-Options`, `X-Forwarded-For`) are used as they are.
- **Request id:**
  - `{Product}-Request-Id: <uuid>` on every response the service generates, minted by the service and never read from the request.
  - The problem `instance` is the same id as `urn:uuid:…`, and every log line has it.
  - Cross-service correlation uses `traceparent`: accept it, propagate it, log its trace id, don't echo it, and don't honor a public client's sampled flag (W3C §7.2).
- **CORS:** browser clients need custom headers listed in `Access-Control-Expose-Headers` and `Access-Control-Allow-Headers`.

**Renames:**
- `X-Schema-Version` → `Acme-Version` (versioning.md:28).
- `X-Version` → `{Product}-Build`, or drop it (versioning.md:277, :285).
- `X-Token-Id` → `Authorization: Bearer` (python/architecture.md:275).
- httprate's `X-RateLimit-*` → configure `WithResponseHeaders`, and its default text 429 → `WithLimitHandler` problem.

**Implementation notes:** chi's `RequestID`, Envoy and asgi-correlation-id all default to `X-Request-Id` and trust inbound values, so use a small custom middleware. In Python, the 500 handler must set the header itself, because ASGI middleware sits inside `ServerErrorMiddleware`.

## 6. Branch-based commit and push policy

A drafted patch (9 files) is in `draft-branch-commit-policy.diff`. It passes `make -C agents validate test` on a scratch clone. The verifier asked for the fixes below, which aren't in the diff yet.

**The policy:**
- **Task branch (fixed list):** a branch the agent cut this session, one the harness assigned (`claude/…`), or one you named for the work. Any other non-shared branch, including your own existing feature branches, gets a one-time ask at the first pause; the draft's catch-all definition would auto-push your local commits.
- **Shared branch:** `main`, the default branch, `release/*`, a branch with an open PR targeting it or someone else's open PR from it, or a merged branch. Commit and push only when asked (unchanged).
- **On a task branch, commit each finished step without asking:**
  - Stage only your own paths.
  - **Runners push after every commit,** because a reclaimed VM loses unpushed work. **Workstations push at will.**
  - A non-fast-forward rejection means rebase; any other rejection means stop and report.
  - Rewrite only your own commits, with `--force-with-lease --force-if-includes` (a bare lease is defeated by background fetches; reproduced).
  - Opening or merging PRs, tags and remote branch deletes still wait for you.
- **On `main` at the start:** a runner cuts a branch (as today). A workstation proposes the branch name at its first pause (`git switch -c` carries uncommitted edits along). No answer means it stays on `main` and commits nothing. A project can opt into automatic cutting in its own AGENTS.md.
- **Subagents** commit their steps only when the dispatch prompt says so, and never push, branch or switch; the parent reviews and pushes. The git instructions are spelled out in every dispatch prompt, because subagents may not see core.md.
- **STOP gates and orchestrate:**
  - On a task branch the wave is already committed and pushed when the gate asks, so the question is only about the plan and names the commit range. Never "approve, commit, push?".
  - On `main`, the commit is offered as its own explicit choice.
  - The review beat reads `git diff <from>` from the last Review log range, since the working tree is clean after commits.
  - Branch and identity checks run per repo for multi-repo waves.
- **Enforcement:** a plugin PreToolUse hook that blocks `git push` to the default branch and blocks any push from a subagent, rather than a GitHub ruleset that would also force your own pushes through PRs.
- **Harness conflict:** Claude Code's built-in Bash instructions say "Commit or push only when the user asks. If on the default branch, branch first." core.md has to win as a user instruction, or set `includeGitInstructions: false`.

## Sources

**History:**
- AWS DynamoDB sort-key versioning; S3 delete markers; GCS request preconditions.
- Drive revisions; MediaWiki API:Revisions; Confluence v2 versions; Stripe events.
- Firestore quotas, best practices, indexes, TTL, delete, PITR, backups and manage-databases; the firebase/extensions firestore-bigquery-export README.
- PostgreSQL 19 temporal tables and `CREATE FUNCTION` security docs; SQLAlchemy versioning; Hibernate Envers; django-simple-history; MariaDB system-versioned tables.
- Azure event sourcing pattern; Cloud KMS envelope encryption; BigQuery AEAD; GDPR Art. 17 and Recital 26.
- RFC 9110, RFC 6902, RFC 7396, AIP-162.

**Timestamps:** vendor OpenAPI specs (GitHub, Shopify, Stripe, Square, DigitalOcean, OpenAI, Anthropic SDK, Cloudflare, Vercel, Linear, Confluence, Auth0, Azure common-types, Google discovery docs); RFC 3339, RFC 9557, RFC 9745; the Firestore data types page; swift-foundation's ISO 8601 source.

**Admin bootstrap:**
- Product docs and source: Gitea, Mattermost, Strapi, Jenkins, GitLab, Vault, Argo CD, Keycloak, Grafana, Directus, Django, Sentry, Mastodon, Discourse.
- Google OIDC; OIDC Core §5.7.
- Firebase custom claims, emulator, session-management and blocking-function docs; Identity Platform.
- IAP for Cloud Run, IAP signed headers and reauthentication; the Cloud Run container contract; GCP PAM.
- Entra emergency access; AWS root-user best practices; Google super-admin best practices; *Building Secure and Reliable Systems* ch. 5; Salesforce and Okta support access; GitLab Admin Mode; GitHub sudo mode.

**Attribution:**
- GitHub changelog 2019-12-19 (squash attribution); GitHub docs on squash settings, merging, auto-merge, multiple authors and rulesets; the GraphQL and REST merge APIs; the gh manual.
- Linux coding-assistants.rst and commit 816d999; Fedora, Eclipse, LLVM, OpenInfra and Apache AI policies; Gentoo, NetBSD and QEMU bans; Git SubmittingPatches.
- Claude Code settings reference and self-hosted deploy docs; GitHub Copilot agent docs; the DCO app.

**Headers:** RFC 6648, RFC 9110 §16.3, RFC 9651, RFC 9113 §8.2; the IANA HTTP Field Name Registry; W3C Trace Context; the Fetch spec (CORS); docs from Stripe, Anthropic, OpenAI, Fly, Cloudflare, Twilio, Heroku, OCI, GitHub, Shopify, Slack, Google, AWS, Azure and Vercel; chi, Envoy, asgi-correlation-id and httprate source.

**Commit policy:** Claude Code cloud-environments, self-hosted, sub-agents and settings docs; git-push docs (`--force-if-includes`); GitHub Copilot and Cursor cloud agent docs; Codex config docs.
