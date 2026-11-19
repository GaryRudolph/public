# Security Standards

Contents: [Authentication](#authentication) · [Authorization](#authorization) · [Shared-Domain Cookies](#shared-domain-cookies) · [Input Validation](#input-validation) · [Security Headers](#security-headers) · [API Security](#api-security) · [Encryption and Erasure](#encryption-and-erasure) · [Secrets Management](#secrets-management) · [Explicit CLI Identity](#explicit-cli-identity) · [Logging](#logging) · [Dependency Security](#dependency-security) · [Cross-Language Security Parallels](#cross-language-security-parallels) · [Security Checklist — Before Deployment](#security-checklist--before-deployment) · [Regular Security Tasks](#regular-security-tasks) · [Language-Specific Security](#language-specific-security) · [Platform-Specific Security](#platform-specific-security)

## Authentication

- **Passwords** ([NIST SP 800-63B-4] §3.1.1.2): at least 15 characters when the password is the only factor, 8 when it's part of MFA; accept at least 64, counting each Unicode code point as one character. No composition rules and no periodic changes; force one on evidence of compromise. Check each new password against a blocklist of breached, common and context-specific values (the service name, the username) and say why it was rejected. Never truncate, store hints or ask security questions; allow paste and password managers
- **Password hashing**: argon2id ([RFC 9106]) for new hashes, starting from §4's second recommended parameters (t=3, 64 MiB, p=4) and tuning to the hardware ([OWASP Password Storage]); never MD5, SHA-1 or a fast hash. Store the hash as a PHC string so its parameters travel with it, and rehash at the next login when they change. NFC-normalize before hashing; compare in constant time. bcrypt is acceptable only for hashes that already exist, never for new ones: it reads at most 72 bytes and must reject longer input rather than truncate, and 64 non-ASCII characters can exceed that
- **Tokens**: short-lived access tokens with minimal payloads; refresh tokens with server-side rotation; cryptographically secure generation
- **JWTs**: follow the JWT BCP ([RFC 8725]) — pin the accepted algorithms, always set and require `exp`, check `iss` and `aud` when more than one service issues or accepts tokens
- **OAuth 2.0**: follow the Security BCP ([RFC 9700]) — authorization code with PKCE ([RFC 7636]) for every client; no implicit or password grants
- **Native apps** (iOS, Android): sign in through the system browser (`ASWebAuthenticationSession`, Custom Tabs), never an embedded web view ([RFC 8252])
- **Sessions**: cookies ([RFC 6265]) marked Secure, HttpOnly, SameSite=Strict, with the `__Host-` prefix ([Shared-Domain Cookies](#shared-domain-cookies)); 15-30 min lifetime for sensitive apps; don't use default cookie names
- **MFA**: TOTP ([RFC 6238]) or WebAuthn hardware keys; allow small time-step window for clock drift

## Authorization

- **Separate authn from authz**: check permissions at the service layer, not just the UI ([ASVS 5.0] 8.3.1)
- **Identity is `iss` + `sub`**: key accounts, memberships and grants on the issuer and subject, never on email. Only that pair is stable and unique; an email can be reassigned, shared or unverified ([OIDC Core] §5.7). Keep the email for display and contact
- **No default or first-visitor admins**: no account is privileged out of the box ([ASVS 5.0] 6.3.2), and nothing internet-reachable makes the first person to sign up or open a setup page an owner or admin
- **Bootstrap only through infrastructure**: the first privileged principal comes from a path that already needs infrastructure access, such as a reviewed IaC change, a management CLI run inside the deployment, or a single-use secret that expires. Log every bootstrap grant
- **Never zero owners**: every path that removes ownership (role change, member removal, account deletion) checks in the same transaction that the organization keeps at least one owner. Where the IdP allows it, turn off client-side account deletion and delete through the server, so no path skips the check
- **Read privileged authority server-side**: take roles from the authoritative store on each request, not from claims in long-lived tokens, so a revocation applies without waiting for tokens to expire ([ASVS 5.0] 8.3.2). For urgent revocation, also check a deny list keyed by the principal (`iss` + `sub`)
- **Break-glass lives at the IdP**: no app-level break-glass account, backdoor role or bypass flag. Recovery goes through the identity provider's own admin accounts: at least two, held by different people, with security keys, alerted on use and drilled
- **Separation of duties where staffing allows**: whoever proposes a privileged-access change (an IaC PR) isn't the one who approves it, and nobody approves their own grant
- **Staff access to customer data is audited**: every ops action is recorded with the actor's `sub` and the target organization, and so is every staff read of tenant data. The [activity log](architecture.md#activity-log) is optional for products but required for the ops plane. Time-limited support sessions with a justification are optional; add them when a product needs them
- **Dev-only auth shortcuts fail closed**: emulators, fake verifiers, seeded admins and bypass flags work only in local development. The guard sits where tokens are verified, not only at startup, and anywhere else it rejects every token rather than falling back. GCP and Firebase specifics: [gcp.md](gcp.md#firebase-emulator-guard)

Tenant roles and the ops plane are in [architecture.md](architecture.md#tenant-admin-and-ops).

## Shared-Domain Cookies

Hosts under one registrable domain (`app.example.com`, `api.example.com`, `ops.example.com`) are same-site to each other, so `SameSite` doesn't separate them, and any of them can set a cookie for the whole domain. These rules apply to every service that shares a registrable domain with another, and to environments that share one ([Environment Domains](architecture.md#environment-domains) keeps prod off any domain a non-prod environment uses).

- **`__Host-` prefix on session and CSRF cookies**: the browser accepts the cookie only with `Secure`, `Path=/` and no `Domain`, so it stays host-only and a sibling can't set or overwrite it ([RFC 6265bis] §4.1.3.2; in the RFC Editor queue, shipped in browsers)
- **Never `Domain=`** on a credential cookie: it's sent to every sibling, including one that's compromised or serves user content
- **State-changing requests must be same-origin**: accept an unsafe method on a cookie-authenticated endpoint only with `Sec-Fetch-Site: same-origin` or `none` ([Fetch Metadata]; `none` is a user-initiated request, such as a bookmark, that no other site can trigger), or, when the browser doesn't send that header, an `Origin` that exactly matches the service's own origin ([RFC 6454] §7). `same-site` isn't enough, since siblings are same-site. A request with neither header isn't from a current browser, so it passes this check and still needs its credentials. Go 1.25's `http.CrossOriginProtection` is a close variant: it compares the `Origin` host with the `Host` header and ignores the scheme, which HSTS covers
- **HSTS covers the whole domain**: send `Strict-Transport-Security` with `includeSubDomains` from the registrable domain itself (`https://example.com/`), and preload it where you can ([hstspreload.org]). A header from `app.example.com` covers only that host and its subdomains ([RFC 6797] §6.1.2), and any sibling reachable over plain HTTP lets a network attacker plant cookies
- **User-authored active content off the product domain**: uploaded HTML, SVG and user-built pages are served from a separate registrable domain, or with `Content-Security-Policy: sandbox` and never `allow-same-origin` ([CSP3]), so they run in an opaque origin

## Input Validation

- Validate all fields: type, length, range, format, allowed characters
- Use schema validation libraries (Pydantic, Codable, kotlinx.serialization)
- Sanitize HTML: whitelist allowed tags, strip everything else
- Parameterized queries for all database access — never concatenate user input into SQL
- File uploads: check size, MIME type (declared and actual), generate safe filenames

## Security Headers

- `Strict-Transport-Security` ([RFC 6797]) — enforce HTTPS, with `includeSubDomains` when hosts share a registrable domain ([Shared-Domain Cookies](#shared-domain-cookies)); TLS 1.2 minimum, 1.3 preferred ([RFC 9325])
- `Content-Security-Policy` — restrict resource loading. A JSON-only API sends `default-src 'none'; frame-ancestors 'none'`: it loads nothing, and `frame-ancestors` doesn't fall back to `default-src` ([CSP3 frame-ancestors]). When the service also serves HTML (Swagger UI), scope this policy to the API routes and give the HTML its own
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY` — the legacy fallback; browsers ignore it when an enforced policy has `frame-ancestors`
- `Referrer-Policy` — limit referrer leakage

## API Security

- **Rate limits** on all endpoints, stricter on auth; return `429` ([RFC 6585]) with `Retry-After` ([RFC 9110]) as an RFC 9457 problem ([architecture.md](architecture.md#error-responses-rfc-9457)). No `X-RateLimit-*` headers; quota headers follow the `RateLimit` draft ([architecture.md](architecture.md#api-design))
- **Key per-client limits on the real client IP**: behind a proxy, take it from the forwarding header your proxies write, trusting only their hops. A client-written entry lets anyone pick a fresh bucket or exhaust someone else's
- **API responses default to `Cache-Control: no-store`** ([RFC 9111] §5.2.2.5), errors included: a `404` is heuristically cacheable ([RFC 9110] §15.1), and a hidden resource's `404` depends on who asks. A handler opts in to caching
- **A shared-cacheable response at a URL that also accepts credentials sends `Vary` on the credential**: `Authorization`, or `Cookie` for cookie sessions, so a CDN keys anonymous and authenticated requests apart ([RFC 9111] §4.1). Marking a response to an `Authorization` request `public`, `s-maxage` or `must-revalidate` lets a shared cache reuse it for other requests (§3.5); a cookie request has no such guard
- **If the CDN won't key on the credential**, put it in the CDN's cache key or don't cache that URL. Test caching through the CDN, not just the origin
- **API keys**: store only hashed keys; include expiration and scope

## Encryption and Erasure

For personal data that has to be erasable from stores nobody edits: revisions ([Resource History](architecture.md#resource-history)), exports and backups. Erasure destroys keys instead of rewriting history.

- **Key hierarchy**: a keyset per subject, or per tenant when the tenant is the unit of erasure, wrapped by a per-tenant KMS key-encryption key (envelope encryption). Store only the wrapped keyset, never a plaintext key next to the data
- **Revisions are encrypted like the head**: same fields, same keys; an unchanged field carries its ciphertext forward. Secrets (password hashes, API keys, tokens) live outside versioned resources, so they never enter history
- **Erase by crypto-shredding**: once every copy of the keyset is gone (the live store and its backups), or the tenant's KEK is destroyed, the head, every revision, every export and every backup are unreadable
- **The erasure window is the longest retention of any copy that could bring data back**: keyset-store backups, database backups and analytics copies. A backup that holds a wrapped keyset stays readable while its KEK exists. Write the window down; it isn't the point-in-time-recovery window
- **Ask counsel** whether that window satisfies GDPR [Art. 17][GDPR] for the product; this standard doesn't claim it does

## Secrets Management

- Never commit **plaintext** secrets to source repositories
- Don't treat non-secret config as a secret: project ids, service account emails and public web config are committed, not hidden in CI settings ([architecture.md](architecture.md#ci-configuration))
- Commit secrets only as SOPS + age ciphertext, and only to private repos: in a private repo's own `secrets/` folder, or in the estate's private secrets repo once two repos share a value or a public repo needs one. Deployed services read them from the platform's secret store, never by decrypting ([Secrets Management](secrets/README.md))
- Validate required secrets at startup; never log secrets
- Support multiple active keys during rotation (current + previous)

## Explicit CLI Identity

Several sessions run at once against different organizations, and a CLI's default account, project or context is one file in the home directory that all of them share. A session that switches it, or trusts it, acts on whichever organization the last session left there. So every command an agent or a script runs, and every command an agent hands a person, names its identity, and none of them changes the default. A person's own command line is out of scope: they know to check it.

- **Name it on the command**: when a CLI takes an account, organization, project, subscription, profile or context as a flag, pass it on every command that touches a remote, reads included. This covers an agent's own tool calls, commands handed to a person, Makefiles, scripts and CI
- **Google user credentials also need a quota project**: an `--account` with a user's credentials bills API quota to a quota project, which otherwise comes from the shared default or is missing (`quota project not set`, or a 403 naming the wrong project). Name it alongside the account: `--billing-project=<id>` on gcloud, `GOOGLE_CLOUD_QUOTA_PROJECT=<id>` for client libraries, `billing_project` with `user_project_override = true` in Terraform's `google` provider. It's usually the same project as `--project`, and never set with `gcloud auth application-default set-quota-project`. Service-account credentials bill their own project and don't need it
- **Credential helpers borrow another CLI's default**: a flag can pick the target while the credential still comes from some other tool's active account. GKE's `gke-gcloud-auth-plugin` uses gcloud's, AKS's `kubelogin` in `azurecli` mode uses az's, and `gcloud auth configure-docker` or `az acr login` push as whoever is active there. Name the account for the helper too: `CLOUDSDK_CORE_ACCOUNT=<email> kubectl --context <name> ...`, an EKS kubeconfig written with `aws eks update-kubeconfig --profile <name>`, and registry pushes from a `DOCKER_CONFIG` of their own, logged in with a token minted for the named account
- **Defaults hide beyond the account**: a resource group, location, region, DevOps organization, default catalog or bundle target set once and read by every later command picks the wrong place as surely as the wrong account does. Pass those too (`-g`, `--location`, `--region`, `--org`, `-t`, fully qualified `catalog.schema.table` names)
- **No flag, then an env var on that one command**: `CLOUDSDK_CORE_ACCOUNT=dev@example.com bq ls`, not an `export` earlier in the session, so the command is complete when copied on its own
- **Never change the shared default**: no `gcloud config set account|project`, `gcloud config configurations activate`, `gcloud auth application-default login` or `set-quota-project` to switch orgs, `gh auth switch`, `kubectl config use-context`, `az account set`, `az configure --defaults`, `az devops configure --defaults`, `firebase use`, `docker context use`, `vercel switch` or `terraform workspace select`. Adding a credential is fine; activating it is the problem, so use `gcloud auth login --no-activate` where the tool allows it
- **A person's own shell stays as it is**: whatever their command line sets (a directory-scoped environment, exports in a startup file, an active gcloud configuration) is theirs to manage. Scripts, Makefiles, agent tool calls and every command an agent hands a person never rely on it: an agent's shell may not load the person's environment, and the person may paste the command anywhere, so each one names its identity on the command, matching what the repo documents
- **Try every way around the default first**: a flag, then an env var or token on the command, then a config directory of its own for that command (`CLOUDSDK_CONFIG`, `KUBECONFIG`, `GH_CONFIG_DIR`, `AWS_CONFIG_FILE`, `DOCKER_CONFIG`, `AZURE_CONFIG_DIR`, `DATABRICKS_CONFIG_FILE`, `TF_CLI_CONFIG_FILE`)
- **When only the default works, stop and ask**: this is the exception. Before changing it, stop and tell the Owner which tool, which default and what value, so they can hold every other session that uses that CLI; one session at a time holds a global default. Wait for a go-ahead (a non-answer is no go-ahead), do only the work that needs it, then say it's done and what the default is now, so the Owner can release the next session. A runner pushes before it asks, as in any wait
- **The active default is not evidence**: which account and project the work wants comes from the repo (its `AGENTS.md`, README, Makefile variables, tfvars, `.firebaserc`) or from the Owner, never from `gcloud config get account` or the current kube context. If the repo doesn't say, ask before the first remote command
- **Repos say which identity they use**: a repo that drives these CLIs names its account and project per environment in one place, such as Makefile variables (`GCP_PROJECT ?= example-dev`, `GCP_ACCOUNT ?= dev@example.com`) that every target passes on. CI keeps its own identity ([gcp.md](gcp.md#ci-identity)) and still passes the project
- **Exempt**: commands that touch no remote (`gcloud components list`, `kubectl config get-contexts`) and tools with no notion of an account

| Tool | Name it with | Instead of |
|------|--------------|------------|
| `gcloud` | `--account=<email> --project=<id> --billing-project=<id>`, or `--configuration=<name>` for a named configuration | `gcloud config set`, `gcloud config configurations activate` |
| `gsutil` | `gcloud storage ... --account=<email> --project=<id>` (gsutil takes no account flag) | the active gcloud account |
| `bq` | `--project_id=<id>`, with `CLOUDSDK_CORE_ACCOUNT=<email>` and `CLOUDSDK_BILLING_QUOTA_PROJECT=<id>` on the command | the active gcloud account and project |
| Google client libraries | `GOOGLE_APPLICATION_CREDENTIALS=<file>` naming that identity's own credential file (an ADC file written under a `CLOUDSDK_CONFIG` of its own, or a service-account impersonation file), or an explicit credential object in code; plus `GOOGLE_CLOUD_QUOTA_PROJECT=<id>` for user credentials and the project set in the call | application default credentials from whichever login ran last |
| Terraform `google` provider | `GOOGLE_OAUTH_ACCESS_TOKEN=(gcloud auth print-access-token --account=<email>)` on the command, or `impersonate_service_account` in the provider; `project` in the provider, and `billing_project` with `user_project_override = true` for user credentials | application default credentials from whichever login ran last |
| `firebase` | `--account <email> --project <id>` | `firebase use`, the logged-in default |
| `gh` | `--repo <owner>/<repo>`, with `GH_TOKEN=(gh auth token --user <login>)` on the command when more than one account is logged in | `gh auth switch` |
| `aws` | `--profile <name> --region <region>` | a default profile or an exported `AWS_PROFILE` |
| `az` | `--subscription <id>`, plus `-g <group>` and `--location <region>` where the command takes them | `az account set`, `az configure --defaults` |
| `az devops`, `az boards`, `az repos`, `az pipelines` | `--org https://dev.azure.com/<org> --project <name>` | `az devops configure --defaults` |
| Azure SDKs | a specific credential, not `DefaultAzureCredential`, which falls through to a managed identity or the az login: `EnvironmentCredential` with `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` and `AZURE_CLIENT_SECRET` or `AZURE_CLIENT_CERTIFICATE_PATH`, read from where the repo keeps them, or `AzureCliCredential` run with `AZURE_CONFIG_DIR=<dir>` logged in as that identity. The subscription is separate: `AZURE_SUBSCRIPTION_ID` or the client's argument | the az CLI's current login, tenant and subscription |
| Terraform `azurerm` provider | the caller: `ARM_CLIENT_ID` with `ARM_CLIENT_SECRET`, `ARM_CLIENT_CERTIFICATE_PATH` or OIDC, or CLI auth run with `AZURE_CONFIG_DIR=<dir>`; the target: `ARM_TENANT_ID` and `ARM_SUBSCRIPTION_ID` (or `subscription_id` in the provider) | the az CLI's current login, tenant and subscription |
| `kubectl` | `--context <name> --namespace <ns>`, plus the helper's account on GKE (`CLOUDSDK_CORE_ACCOUNT=<email>`) and AKS (`AZURE_CONFIG_DIR` or a `kubelogin` mode with its own credential) | `kubectl config use-context`, the helper CLI's active account |
| `helm` | `--kube-context <name> --namespace <ns>` | the current kube context |
| `docker` | `--context <name>`; registry pushes with `DOCKER_CONFIG=<dir>` logged in for that account (`gcloud auth print-access-token --account=<email>` into `docker login -u oauth2accesstoken --password-stdin`) | `docker context use`, `docker login` (one credential per registry host), `gcloud auth configure-docker` and `az acr login` on the active account |
| `terraform` | `TF_WORKSPACE=<name>` on the command | `terraform workspace select`, which every session in that checkout shares |
| `databricks` | `--profile <name>` (or `DATABRICKS_CONFIG_PROFILE=<name>` on the command), a profile for the account host with `account_id` for `databricks account ...`, `-t <target>` on every `databricks bundle` command, `--warehouse-id <id>` and fully qualified `catalog.schema.table` names | the `[DEFAULT]` profile, the bundle target marked `default: true`, the workspace's default catalog |
| Terraform `databricks` provider | `profile` naming that identity's profile, or `host` together with that identity's credentials (`client_id` and `client_secret`, or a token read from where the repo keeps it), with inherited `DATABRICKS_*` auth variables cleared; never `host` alone, which picks the workspace, not the caller | the `[DEFAULT]` profile, or a `DATABRICKS_TOKEN` or other auth variable the session inherited |
| `snow` (Snowflake CLI) | `-c <connection>` | `default_connection_name` |
| `vercel` | `--scope <team>` | `vercel switch` |
| HCP Terraform (`terraform` with a `cloud` block) | that organization's own named token on the command, `TF_TOKEN_app_terraform_io=<token>` (the host with dots as underscores), read from where the repo keeps it, plus `TF_CLOUD_ORGANIZATION=<org>` when the `cloud` block doesn't name one | `terraform login`, which keeps one token per host for every session |

## Logging

- **Every line carries the request id and, once authenticated, the user id**; the request id is the one in the `{Product}-Request-Id` header and the problem's `instance` ([architecture.md](architecture.md#custom-headers)), so one request's lines and its error response join up
- **Never tokens, credentials or user content**: no `Authorization` or `Cookie` values, passwords, API keys or session ids, and no request or response bodies
- **Error strings and subprocess output can quote user input**: a parser, validator or constraint error can echo a value, and a tool's stderr can echo anything. Treat them as user content: turn input errors into problems without logging their text, and log a subprocess's exit status, not its output

## Dependency Security

- Lock files with hash verification
- **Vulnerability scanning**: a blocking check on every PR plus a scheduled run, since a new advisory can fail code that hasn't changed. Which `make` target runs it is the project's call
- **Reachability matters**: govulncheck fails only on vulnerabilities in code that's called, so a failure is worth fixing. `npm audit` has no reachability and no per-advisory ignore, so don't block on it on the same terms. Other tools: pip-audit, Dependabot, Renovate
- Pin versions; review new dependencies before adding

## Cross-Language Security Parallels

| Concept | Python | Swift / iOS | Kotlin / Android | Go |
|---|---|---|---|---|
| Secure storage | env vars, secrets manager | Keychain | EncryptedSharedPreferences, Keystore | env vars, GCP Secret Manager |
| Cryptography | `cryptography` lib | CryptoKit | Android Keystore, javax.crypto | `crypto/*`, `golang.org/x/crypto` |
| Input validation | Pydantic | Codable + manual | kotlinx.serialization + manual | go-playground/validator |
| Static analysis | Bandit, Ruff `S` rules | Xcode analyzer | detekt security rules | gosec, govulncheck |
| Network security | HTTPS enforcement | App Transport Security | Network Security Configuration | security-headers middleware |

## Security Checklist — Before Deployment

- [ ] Secrets committed only as SOPS + age ciphertext ([secrets/README.md](secrets/README.md)); services read them from the platform's secret store
- [ ] HTTPS enforced
- [ ] Security headers configured; JSON API routes send `default-src 'none'; frame-ancestors 'none'`
- [ ] API responses default to `no-store`; cacheable URLs that accept credentials `Vary` on them, tested through the CDN
- [ ] Rate limiting implemented, keyed on the real client IP
- [ ] Input validation on all endpoints
- [ ] Parameterized queries for all DB access
- [ ] Authentication and authorization implemented
- [ ] No default or first-visitor admins; privileged bootstrap only through infrastructure
- [ ] Dev-only auth shortcuts fail closed outside local development
- [ ] Session cookies use `__Host-`; state-changing requests are checked for same origin
- [ ] Password rules follow NIST SP 800-63B-4; passwords hashed with argon2id (bcrypt only for hashes that already exist)
- [ ] Vulnerability scan blocks PRs and runs on a schedule
- [ ] Error messages don't leak sensitive info
- [ ] Logs carry user and request ids, never tokens, credentials or user content

## Regular Security Tasks

- [ ] Rotate secrets and API keys
- [ ] Review access logs
- [ ] Update dependencies
- [ ] Run security scans
- [ ] Review permissions

## Language-Specific Security

- **[Python](python/security.md)**
- **[Swift / iOS](swift/security.md)**
- **[Kotlin / Android](kotlin/security.md)**
- **[Go](go/security.md)**

## Platform-Specific Security

- **[GCP and Firebase](gcp.md)** — IAP on Cloud Run, access groups in Terraform, revocation, break-glass, Identity Platform, the emulator guard, KMS keysets and erasure copies, activity-log sinks

[ASVS 5.0]: https://owasp.org/www-project-application-security-verification-standard/
[CSP3]: https://www.w3.org/TR/CSP3/#directive-sandbox
[CSP3 frame-ancestors]: https://www.w3.org/TR/CSP3/#directive-frame-ancestors
[Fetch Metadata]: https://www.w3.org/TR/fetch-metadata/
[GDPR]: https://eur-lex.europa.eu/eli/reg/2016/679/oj
[hstspreload.org]: https://hstspreload.org/
[NIST SP 800-63B-4]: https://pages.nist.gov/800-63-4/sp800-63b.html#passwordver
[OIDC Core]: https://openid.net/specs/openid-connect-core-1_0.html#ClaimStability
[OWASP Password Storage]: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
[RFC 6238]: https://www.rfc-editor.org/rfc/rfc6238
[RFC 6265]: https://www.rfc-editor.org/rfc/rfc6265
[RFC 6265bis]: https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis#section-4.1.3.2
[RFC 6454]: https://www.rfc-editor.org/rfc/rfc6454
[RFC 6585]: https://www.rfc-editor.org/rfc/rfc6585
[RFC 6797]: https://www.rfc-editor.org/rfc/rfc6797
[RFC 7636]: https://www.rfc-editor.org/rfc/rfc7636
[RFC 8252]: https://www.rfc-editor.org/rfc/rfc8252
[RFC 8725]: https://www.rfc-editor.org/rfc/rfc8725
[RFC 9106]: https://www.rfc-editor.org/rfc/rfc9106
[RFC 9110]: https://www.rfc-editor.org/rfc/rfc9110
[RFC 9111]: https://www.rfc-editor.org/rfc/rfc9111
[RFC 9325]: https://www.rfc-editor.org/rfc/rfc9325
[RFC 9700]: https://www.rfc-editor.org/rfc/rfc9700
