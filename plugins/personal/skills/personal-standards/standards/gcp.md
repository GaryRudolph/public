# GCP and Firebase Standards

How to meet the generic rules in [security.md](security.md) and [architecture.md](architecture.md) on Google Cloud and Firebase. Quotas, propagation times and launch stages change, so this file links Google's docs for the numbers instead of restating them.

## Ops Plane on IAP

The ops console and API are one Cloud Run service behind Identity-Aware Proxy, on one origin at `ops.<product domain>` (`ops.nowline.io`, with `ops.nowline.dev` for dev): the console at `/`, the API at `/api/v1`. The host, path and role naming, and why it's one origin, are in [architecture.md](architecture.md#tenant-admin-and-ops).

- **IAP on the Cloud Run service**: `iap_enabled = true` on [`google_cloud_run_v2_service`][tf-run]. The IAP service agent (`service-<project-number>@gcp-sa-iap.iam.gserviceaccount.com`) gets `roles/run.invoker`. Access is [`google_iap_web_cloud_run_service_iam_member`][tf-iap-run] with `roles/iap.httpsResourceAccessor`, bound to a group, never to a user ([IAP for Cloud Run][iap-run])
- **Custom domain**: a global external Application Load Balancer with a serverless NEG, with IAP enabled on the Cloud Run service and not on the load balancer; it can't be on both ([IAP for Cloud Run][iap-run], [serverless NEG setup][lb-serverless]). Cloud Run domain mapping is Preview; check its [launch stage][run-domains] before relying on it
- **Verify the IAP JWT on every request**: read `x-goog-iap-jwt-assertion` and check the ES256 signature against IAP's public keys, `iss` = `https://cloud.google.com/iap`, `aud` = this service's exact audience (`/projects/<project-number>/locations/<region>/services/<service>`), and the expiry. Then require `hd` to be the org's domain. Ignore the unsigned `x-goog-authenticated-user-*` headers ([signed headers][iap-jwt])
- **Key staff on `sub`** (`accounts.google.com:<id>`), never `email`. The JWT has no groups claim: authority is which IAP-protected service admitted the request, which is why `aud` is checked per service. On a `sub`'s first request, create a profile row keyed by it; the row records identity and grants nothing
- **Step-up with IAP reauthentication**: set `access_settings.reauth_settings` to method `SECURE_KEY` with [`google_iap_settings`][tf-iap-settings], and read the exact per-service `name` with `gcloud iap settings get`. Reauth is browser-only and exempts service accounts. Its cookie is IAP's own, set on the top-level private domain and valid for all of it, so a reauth on any IAP-protected host under `nowline.io`, not only under `ops.`, satisfies the others while it's valid. It sits outside the [`__Host-` rule](security.md#shared-domain-cookies), which covers the app's own cookies. The IAP JWT has no `auth_time` for Google identities, so the app can't check freshness itself ([reauthentication][iap-reauth])
- **CLIs and scripts**: the Google-managed OAuth client is internal-only and browser-only. A CLI or script calling the ops API uses an IAP programmatic OAuth client or a service-account-signed token ([programmatic authentication][iap-programmatic]). As a non-browser client it sends neither `Sec-Fetch-Site` nor `Origin`, so the [same-origin check](security.md#shared-domain-cookies) lets it through; IAP and the deny list still apply
- **Audit**: turn on [IAP audit logs][iap-audit]. The app's own [activity log](architecture.md#activity-log) still records every ops action with the actor's `sub` and the target organization; its sink is in [Activity Log](#activity-log)

## Access Groups in Terraform

- **The first ops member is a reviewed Terraform PR**: add the person's email to the ops access group with [`google_cloud_identity_group_membership`][tf-membership] and `preferred_member_key { id = "<email>" }`. Google resolves the email when the plan applies, so Terraform never needs an account id, and the app learns the `sub` from the IAP JWT. No allowlist, one-time grant or seeded database row
- **Terraform doesn't write app data**: don't look up user ids by email or create profile rows from Terraform. There's no provider data source for Workspace or Identity Platform users, the rows would drift from the app's own writes, and CI would need Workspace admin credentials
- **Group setup**: a Workspace admin creates the access group with the security label (it can't be removed later) and makes the Terraform service account its owner, so that account needs no Groups Admin role. Owners are also members, so deny the CI identity `iap.googleapis.com/webServiceVersions.accessViaIAP` with an [IAM deny policy][iam-deny], or alert on its use
- **Only org identities**: the org policy `iam.allowedPolicyMemberDomains` ([domain-restricted sharing][drs]) keeps anything outside the org from being bound
- **Offboarding**: remove the person's Terraform entry in the same change that offboards them, and never reassign a staff email. A deleted account's bindings become `deleted:user:…` and don't carry over to a new account with the same address
- **Time-boxed elevation, once roles split**: use [Privileged Access Manager][pam] or a `request.time` condition on the IAP binding, not membership expiry in Terraform. Expiry needs a premium Workspace or Cloud Identity edition, and the next apply re-creates an expired membership

## Revocation

- **Know the delays**: a group membership change reaches IAP in minutes to hours, and an IAM deny on `iap.googleapis.com/webServiceVersions.accessViaIAP` takes minutes ([access change propagation][iam-propagation]). Only an app-side check is immediate
- **Urgent revocation is an app-side deny list keyed by `sub`**, checked on every request after the JWT is verified. Follow it with the IAM deny and the Terraform PR that removes the membership

## Break-Glass

- **At the IdP, never in the app**: two or more Workspace super admin accounts, held by different people, with security keys, used for nothing else, alerted on every sign-in and drilled ([admin account best practices][ws-admins]). The ops service has no break-glass account or bypass
- **Separation of duties where staffing allows**: the author of an access-group PR isn't its approver

## Identity Platform

Tenant users sign in through Identity Platform (Firebase Auth). Ops staff sign in through IAP with Workspace accounts, a separate identity.

- **Turn off client-side account deletion**: set `client.permissions.disabled_user_deletion = true` on [`google_identity_platform_config`][tf-idp] and delete through the server. There's no before-delete blocking function, so a client-side delete would skip the never-zero-owners check
- **Custom claims go stale**: an ID token is short-lived and picks up new claims when it refreshes ([custom claims][fb-claims]), but a [session cookie][fb-cookies] keeps the claims it was minted with for its whole lifetime. So privileged decisions read roles from the database ([security.md](security.md#authorization))
- **Staff who need a product-app role aren't bound by email**: a Firebase ID token has no `hd`, and Workspace custom domains aren't a trusted provider for `email_verified`. Use a one-time claim code issued in the ops console and redeemed in the product app, or read `sub` and `hd` from the Google ID token in a `beforeSignIn` [blocking function][idp-blocking]. Don't pre-create Identity Platform users: an import collision replaces the existing user

## Firebase Emulator Guard

- **The risk**: with `FIREBASE_AUTH_EMULATOR_HOST` set, the Firebase Admin SDKs accept unsigned ID tokens and session cookies with any claims ([Auth emulator][fb-emulator]). The Python Admin SDK also skips the expiry checks and reads the variable on every verify call, so a startup check alone can't catch it being set later
- **Guard in the verify wrapper**: all token verification goes through one function, and when the variable is set, that function rejects every token unless the project id starts with `demo-` and none of `K_SERVICE`, `CLOUD_RUN_JOB` or `CLOUD_RUN_WORKER_POOL` is set ([Cloud Run environment variables][run-env]). Run the same check at startup to fail fast
- **Use `demo-` projects** for every emulator run, as Firebase recommends. Seed scripts refuse any other project and any emulator host that isn't local

## Encryption and Erasure

The generic rules are in [security.md](security.md#encryption-and-erasure).

- **Tink keysets wrapped by Cloud KMS**: per-subject (or per-tenant) [Tink][tink] keysets, each wrapped by the tenant's Cloud KMS key-encryption key ([envelope encryption][kms-envelope]). Store the wrapped keyset; the plaintext keyset exists only in memory
- **KMS key-version destruction is scheduled, not immediate** ([destroy and restore][kms-destroy]). For tenant-wide erasure, that delay counts toward the erasure window
- **Backups count toward the erasure window**: [Firestore backups][fs-backups], point-in-time recovery and Cloud SQL backups keep whatever the database held, wrapped keysets included. Use their longest retention, not the PITR window
- **BigQuery copies count too**: the [Stream Firestore to BigQuery][fs-bq] extension is a best-effort analytics copy that keeps rows the purge job deleted. Purge it separately, and never serve history from it

## Resource History Stores

The generic rules are in [architecture.md](architecture.md#resource-history).

- **Firestore**: [go/architecture.md](go/architecture.md#resource-history--firestore). Immutability is enforced by code only: IAM is granted per database and server SDKs bypass Security Rules, so turn on [Data Access audit logs][fs-audit] and keep the BigQuery copy as tamper evidence
- **Cloud SQL for PostgreSQL**: [python/architecture.md](python/architecture.md#resource-history--postgresql)

## Activity Log

The generic rules are in [architecture.md](architecture.md#activity-log).

- **The app only emits entries**: it writes them as structured Cloud Logging entries under one log name, with `roles/logging.logWriter`, and never writes the destination itself. BigQuery's permissions can't express insert-only: streaming inserts, the Storage Write API and DML `DELETE` all need `bigquery.tables.updateData` ([BigQuery access control][bq-iam])
- **A sink routes them**: a [`google_logging_project_sink`][tf-log-sink] filtered on that log name, with `unique_writer_identity = true`, and only the sink's `writer_identity` can write to the destination. Exclude the log from the `_Default` sink so there's no second copy with its own retention ([routing][log-routing])
- **Locked log bucket**: [`google_logging_project_bucket_config`][tf-log-bucket] with the policy's `retention_days` and `locked = true`. Locking can't be undone: the retention can't change, and the bucket can't be deleted while it holds entries inside retention ([log buckets][log-buckets]). Choose the retention before locking, because it becomes the log's erasure window, and put a lien on the project
- **Or a BigQuery dataset**: grant the sink's `writer_identity` `roles/bigquery.dataEditor` on that dataset only. The app's identity gets no role on the dataset and no BigQuery data role at project level either: a project-wide `roles/bigquery.dataEditor` would let it delete entries again. Set `bigquery_options.use_partitioned_tables` on the sink. The retention is the dataset's default partition expiration (`default_partition_expiration_ms`), a dataset setting rather than a sink option

[bq-iam]: https://docs.cloud.google.com/bigquery/docs/access-control
[drs]: https://docs.cloud.google.com/resource-manager/docs/organization-policy/restricting-domains
[fb-claims]: https://firebase.google.com/docs/auth/admin/custom-claims
[fb-cookies]: https://firebase.google.com/docs/auth/admin/manage-cookies
[fb-emulator]: https://firebase.google.com/docs/emulator-suite/connect_auth
[fs-audit]: https://docs.cloud.google.com/firestore/docs/audit-logging
[fs-backups]: https://docs.cloud.google.com/firestore/docs/backups
[fs-bq]: https://extensions.dev/extensions/firebase/firestore-bigquery-export
[iam-deny]: https://docs.cloud.google.com/iam/docs/deny-overview
[iam-propagation]: https://docs.cloud.google.com/iam/docs/access-change-propagation
[iap-audit]: https://docs.cloud.google.com/iap/docs/audit-log-howto
[iap-jwt]: https://docs.cloud.google.com/iap/docs/signed-headers-howto
[iap-programmatic]: https://docs.cloud.google.com/iap/docs/authentication-howto
[iap-reauth]: https://docs.cloud.google.com/iap/docs/configuring-reauth
[iap-run]: https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
[idp-blocking]: https://docs.cloud.google.com/identity-platform/docs/blocking-functions
[kms-destroy]: https://docs.cloud.google.com/kms/docs/destroy-restore
[kms-envelope]: https://docs.cloud.google.com/kms/docs/envelope-encryption
[log-buckets]: https://docs.cloud.google.com/logging/docs/buckets
[log-routing]: https://docs.cloud.google.com/logging/docs/routing/overview
[lb-serverless]: https://docs.cloud.google.com/load-balancing/docs/https/setting-up-https-serverless
[pam]: https://docs.cloud.google.com/iam/docs/pam-overview
[run-domains]: https://docs.cloud.google.com/run/docs/mapping-custom-domains
[run-env]: https://docs.cloud.google.com/run/docs/container-contract#env-vars
[tf-iap-run]: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/iap_web_cloud_run_service_iam
[tf-iap-settings]: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/iap_settings
[tf-idp]: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/identity_platform_config
[tf-log-bucket]: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/logging_project_bucket_config
[tf-log-sink]: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/logging_project_sink
[tf-membership]: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_identity_group_membership
[tf-run]: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service
[tink]: https://developers.google.com/tink
[ws-admins]: https://knowledge.workspace.google.com/admin/users/security-best-practices-for-administrator-accounts
