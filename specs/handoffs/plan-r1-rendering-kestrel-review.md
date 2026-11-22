Fixes three r1 findings in how the allowlist meta reaches the harnesses. Shell allows and denies were written into Claude Code's and Cursor CLI's permission lists as bare strings neither tool reads (f1); the global allowlist auto-approved reading 1Password secrets and GET-shaped exfiltration (f4); and seven MCP server wildcards auto-approved sends, sharing changes, deletes and deploys (f9). m3 of the [r1 remediation plan](https://github.com/GaryRudolph/public/issues/45#issuecomment-7074103845), built on #90 (installer state) and #89 (the scout's Cursor CLI exact form). Decisions are the Owner's [walk outcomes](https://github.com/GaryRudolph/public/issues/45#issuecomment-7074013504) plus the f9 design note below.

Fixes r1.f1
Fixes r1.f4
Fixes r1.f9
Part of #45
Queue: r1-fixes-lantern 3

## Review guide

Review tier: [study] [security], because it changes what every agent harness runs without asking.
Blast radius: every Claude Code, Cursor CLI and Cursor IDE session on a machine that runs `make -C agents install`. Shell allows and denies start applying in Claude Code and Cursor CLI for the first time, and 217 named MCP tools replace 7 wildcards. Reinstalling the previous meta reverts it (f11's sidecar baseline swaps entries cleanly).
Review time: ~15 min

1. [study] [security] [`agents/lib/allowlists.sh`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-4e5964bcd418ec0b78ed29d961f19d9e5277a6784e224c5faabe9090e9db6d9e): `cli_allow`/`cli_deny`/`claude_bash`/`claude_mcp` in `render_target_schema`, `validate_meta`
2. [study] [security] [`agents/allowlists/personal.json`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-aa0ab1641187d66fc9efb431996dceea054aeb8897a07cb1544f377efeb130a0): six f4 removals; `mcp.allow` from 7 wildcards to 217 named tools (read it against the design note below)
3. [check] [`agents/lib/allowlists-test.sh`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-6173c3c7684e5cbe52650c479a0c7f4335af0fcccbe2523e982cd5ce4a366545): T14/T15 fixed; T41/T41b (real meta), T42/T42b (each form), T43 (upgrade from a bare-string install)
4. [check] [security] [`plugins/workstation/skills/personal-allowlist-scout/scripts/scan.py`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-f3dd3193617cf699f178a55dc31c43feb318a8a6d9298f0be32ea5f73a4bb9c1): `--output`/`--pre`/`--upload-pack` are Destructive; a bare entry covers nothing
5. [check] [`plugins/workstation/skills/personal-allowlist-scout/tests/test_render_scan.py`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-1a8dc52bb8472ea43bf380a22a5fa084dcd4421662bfffe4dc0107149f7140d0)
6. [skim] [`plugins/personal/skills/personal-standards/standards/security.md`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-81e4085835b2bca076b14e5d9cd3feb6a9514adeee8cc4b63a3ef685c0f5e679): new "Agent Tool Permissions"
7. [skim] [`plugins/workstation/skills/personal-allowlist-scout/reference.md`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-cffe8a3546fa098f9bd7883c4f7c1453dab3d0afea926162ad3f37e6a5289164), [`agents/cursor/hooks/enforce-denylist.sh`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-e272933772c7c2203e67e55053f2c533bc08847a01ea6a0a55403ad1be9cc387) (header claim)
8. [skim] [`specs/reviews/r1/f1.md`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-e77353d97eb2f42fa7ec51b702de1ff3fa2ea6adbb75bed2aab864d2a0f8ef3b), [`specs/reviews/r1/f4.md`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-a2f093bd9a38169bb1bb4830a2196eaa4c880d469397ad346974ef7fb96b34d8), [`specs/reviews/r1/f9.md`](https://github.com/GaryRudolph/public/compare/main...claude/charming-ramanujan-l3dgpq#diff-dc61e897bf1c41273a276a98efb64918131f07d2904d2576382062ff5b3af282): fix claims

## Validation

- `make -C agents validate test`: VALIDATION_RESULT
- New assertions checked against the old code: T41 fails 25 against the old seven-wildcard meta; T43 and friends fail 33 against the old renderer; with the six f4 entries restored in a meta copy, T41 fails 30 (6 per target); the five `UnsafeFlags` never-proposed tests fail against the old `scan.py`.
- Not run: a live Claude Code or Cursor CLI session reading the rendered files (no workstation here). The forms follow Claude Code's permissions docs (read 2026-11-22) and the scout's `reference.md` section 3.

## Rollback

Revert the squash commit and run `make -C agents install`. The installer's baseline is this org's last-rendered sidecar, so the old bare strings and wildcards come back in place of the new entries, and nothing gets promoted to user-managed.

<details open>
<summary>[study] Contracts: what each harness gets</summary>

| Meta entry | Claude Code | Cursor CLI | Cursor IDE |
| --- | --- | --- | --- |
| allow `git status` | was bare; now `Bash(git status:*)` | was bare; now `Shell(git:status)` (exact) | `git status` |
| allow `ls` | was bare; now `Bash(ls:*)` | was bare; now `Shell(ls)` | `ls` |
| deny `rm -rf /` | was bare; now `Bash(rm -rf /:*)` | was bare; now `Shell(rm:-rf /*)` (prefix) | `rm -rf /` |
| deny `rm -rf /*` | was bare; now `Bash(rm -rf /*)` | was bare; now `Shell(rm:-rf /*)` | `rm -rf /*` |
| mcp `notion:notion-search` | was `mcp__notion__*`; now `mcp__notion__notion-search` | `Mcp(notion:notion-search)` | `notion:notion-search` |

Gemini is unchanged. A Cursor CLI allow with `*`, `?` or a colon in its first word gets no rule; none in `personal.json` does. A malformed MCP entry, or a Cursor CLI deny with a colon in its first word, stops the install before any target is written (`validate_meta`).

Cursor CLI denies are prefixes by the Owner's call (2026-11-22), so `rm -rf / --no-preserve-root` is denied too. The cost is over-blocking, e.g. `rm -rf /tmp/x`, which is the safe direction. Claude Code's docs call `:*` an equivalent trailing wildcard and don't deprecate it. An entry already holding `*` is written as-is, because `rm -rf /*:*` means `rm -rf /* *` and would miss the entry itself.

</details>

<details>
<summary>[check] Upgrade path</summary>

T43 starts from a HOME rendered by the old installer: bare shell strings, plus `mcp__notion__*`/`Mcp(slack:*)` wildcards, in both the live files and this org's sidecars. After `install` only wrapped entries remain, the old wildcards are gone, the user-managed sidecars stay empty, and a second install changes nothing.

</details>

<details>
<summary>Decisions: the f9 design note (enumerate, no ask list)</summary>

### r1.f9 design: name the MCP tools that may run, prompt on the rest

The Owner's decision (walk on #45, https://github.com/GaryRudolph/public/issues/45#issuecomment-7074013504): allow MCP writes that have a rollback (version history) or are creates the Owner deletes afterward. Prompt on anything that sends to people, changes sharing or can't be recovered. Notion, Google Docs, Figma and Miro keep their wildcards minus the sharing and permission tools. Slack and Google Workspace allow reads and prompt on send. Firebase allows reads and prompts on writes, deletes and deploys.

Today `agents/allowlists/personal.json` `mcp.allow` holds seven server wildcards (`notion:*` ... `googleworkspace:*`), so every tool on those servers runs without a prompt in all three harnesses.

#### Options

A deny blocks the call; it doesn't prompt. A tool that matches no allow entry prompts in every harness. That leaves two ways to make a tool prompt:

- **(a) Name the allowed tools.** `mcp.allow` lists `server:tool` for each tool that may run. Every other tool prompts, including one a server adds later.
- **(b) Add `mcp.ask`.** Keep the wildcard and render the excluded tools as Claude Code `permissions.ask`. Harnesses with no ask list still need names.

| | (a) name the tools | (b) wildcard plus `mcp.ask` |
|---|---|---|
| A server adds a tool | It prompts (fails closed) | Claude Code runs it without asking (fails open); Cursor needs names anyway |
| Claude Code | `mcp__<server>__<tool>` is documented | `ask` beats `allow` ("deny, then ask, then allow") |
| Cursor IDE `permissions.json` | `server:tool` documented, case-insensitive | No ask list documented |
| Cursor CLI `cli-config.json` | `Mcp(server:tool)` documented | Only `allow` and `deny` documented |
| Installer | No change to the state code | `permissions.ask` is the user's passthrough since #90; owning it adds a third list to sidecar, union, promotion, passthrough, status and diff |
| Upkeep | Re-check the names when a server changes | The ask list goes stale the same way, and it fails open |

**Choice: (a).** It is the only option that fails closed, and the only one that works the same way in all three harnesses. It also leaves the #90 installer code alone. Its cost: a read tool a server adds later prompts until someone adds its name, and the meta grows from 7 entries to 217.

The public docs already trail the live servers. Google's Gmail page lists 10 tools, and Drive's lists 8. The connected Gmail server exposes about 30 tools and Drive 17, including `send_message`, `forward`, `share_file` and `trash_file`. Under a wildcard, any tool missing from the docs would run without a prompt.

Partial globs (`mcp__github__get_*`) are left out. Claude Code accepts them in allow rules; Cursor's docs disagree on whether they work. A glob would also fail open for a new tool whose name happens to match.

#### Sources, and how sure

Every page was read on 2026-11-22; Miro's page shows a last update of 2026-11-13, and the others have no date. The server keys are names the Owner chose in each harness's MCP config. A key that points at a different implementation gets tool names that match nothing here, so its tools prompt.

| key | server | source | sure |
|---|---|---|---|
| `notion` | Notion's hosted MCP (`mcp.notion.com`) | developers.notion.com/guides/mcp/tools-{search,comments,pages,databases,files,skills-agents,calendars} | high |
| `slack` | Slack's hosted MCP (`mcp.slack.com/mcp`) | docs.slack.dev/ai/slack-mcp-server (capabilities, 2 exact names); docs.runlayer.com/servers/slack-official (13 names); this session's live tool list (27 names) | medium-high |
| `miro-mcp` | Miro's hosted MCP | developers.miro.com/docs/miro-mcp-tools (46 tools; `board_list_items`, `context_*`, `diagram_*`, `doc_*` and `table_*` removed) | high |
| `firebase` | `npx firebase-tools@latest mcp` | firebase.google.com/docs/ai-assistance/mcp-server (69 tools) | high |
| `figma` | Figma MCP, remote and desktop | developers.figma.com/docs/figma-mcp-server/tools-and-prompts (44 tools) | high |
| `googledocs` | Google's Docs MCP (`docsmcp.googleapis.com/mcp/v1`) | developers.google.com/workspace/docs/api/reference/mcp (`read_doc`, `update_doc`, plus the `update_doc` tool page) | medium: the name fits and the live server matches, but the key is the Owner's choice |
| `googleworkspace` | One of Google's Workspace endpoints. Google's setup guide (developers.google.com/workspace/guides/configure-mcp-servers) tells other clients to name the server `googleworkspace`, but every product has its own URL | each product's `/reference/mcp` page, plus this session's live Gmail, Drive and Sheets lists | low on which endpoint. Could not confirm, so the key allows only the read tools of every Workspace endpoint (Classroom left out). Whichever endpoint it is, its sends, writes and shares prompt |

#### Per-server classes

Classes: read, rollback (a write with version history or Trash), create, send (to people, or delegates to an agent that acts), share (sharing or access change, or a bearer download link), unrecoverable (delete, deploy, spend, or undocumented). The per-tool record, with what each tool does, is in the appendix at the end of this note. The table lists the prompted tools by name; every other tool on the server is allowed (the exact names are under "New entries").

| key | allowed | prompted |
|---|---|---|
| notion (70) | 37 read, 11 rollback (`update-page`, `restore-*`, `delete-pages` and `delete-databases`, which go to Trash and `restore-pages` brings back, `update-data-source`, views, `upload-skill`, `update-enabled-skills`, `set-discussion-resolved`), 6 create | send: `create-comment`, `update-comment`, `create-suggested-edit`, `resolve-suggested-edit`, `set-comment-reaction`, `calendar-create-events`, `calendar-update-events`, `calendar-cancel-events`, `spawn-session`, `send-message-to-session`. Share: `move-pages` (into another teamspace), `get-file-download-urls`. Unrecoverable: `delete-comment`, `update-folder` (removes files), `convert-page-to-skill`, `stop-session` |
| slack (27) | 14 read (`search_*`, `read_*`, `list_*`, `get_reactions`) | send: `send_message`, `schedule_message`, `add_reaction`, `create_conversation`, `complete_file_upload`. Write: `send_message_draft`, `create_canvas`, `update_canvas`, `create_list`, `update_list`, `add_list_record`, `update_list_record`, `get_file_upload_url` |
| miro-mcp (46) | 21 read, 6 rollback (`canvas_update_from_svg`, `*_update_metadata`, `board_restore`, `comment_resolve`), 7 create | share: `board_share`, `board_role_update`, `space_share`, `space_role_update`, `board_move`, `board_move_to_team`, `image_get_url`. Send: `comment_create`, `comment_reply`, `blog_post_create`, `blog_post_update`. Unrecoverable: `section_delete` |
| firebase (69) | 38 read (get, list, query, logs, rules, `deploy_status`, `developerknowledge_*`) | write: `firebase_init`, `firebase_update_environment`, `firebase_login`, `firebase_logout`, `firebase_create_*`, `auth_update_user`, `auth_set_sms_region_policy`, `crashlytics_create_note`, `crashlytics_update_issue`, `realtimedatabase_set_data`, `dataconnect_build`, `dataconnect_execute`, `remoteconfig_update_template`, `firestore_add_document`, `firestore_update_*`, `firestore_create_*`. Delete: `crashlytics_delete_note`, `firestore_delete_*`. Deploy: `firebase_deploy`. Send: `messaging_send_message`. Share: `storage_get_object_download_url` |
| figma (44) | 25 read, 4 rollback (`use_figma`, `upload_assets`, Code Connect `add_code_connect_map`, `send_code_connect_mappings`), 10 create (`create_new_file`, `generate_*`, `html_to_figma`, `send_code_to_figma`, `create_generative_plugin`, `create_shader`, `weave_upload_asset`). No sharing tool exists | unrecoverable: `update_generative_plugin`, `update_shader` (overwrite source, no history documented), `weave_run_tool`, `weave_run_model` (spend credits), `weave_cancel_tool_run` |
| googledocs (2) | `read_doc` read; `update_doc` rollback (Docs version history). No sharing tool exists | none today. Any later tool prompts |
| googleworkspace | 36 read: Gmail, Drive, Calendar, Chat, People, Sheets, Slides, Docs, Universal Search | everything else: Gmail drafts, labels, send, reply, forward, trash and spam; Drive create, copy, update, `share_file`, `trash_file`, `request_access`; Calendar create, update, delete and respond; Chat `send_message`, mark read or unread, settings; Sheets, Slides and Docs updates; all of Classroom |

Places where the general rule overrides the shorthand for one server:

- On Notion, a calendar event, comment, suggestion or agent session reaches other people, so it prompts.
- `notion-move-pages` and Miro's `board_move` can change who sees a page or board, so they prompt.
- Signed download links (`notion-get-file-download-urls`, Miro `image_get_url`, Firebase `storage_get_object_download_url`) count as sharing and prompt.
- Notion deletes go to Trash, which `notion-restore-pages` brings back, so they are allowed. The Owner may want to change this one.

#### New entries

`mcp.allow` becomes these 217 `"<key>:<tool>"` strings, grouped by key in this order, one block per key separated by a blank line. `mcp.deny` stays `[]`.

```text
notion: notion-search notion-connector-search notion-fetch notion-list-private-pages notion-list-shared-pages notion-list-favorite-pages notion-list-recent-pages notion-list-page-backlinks notion-query-meeting-notes notion-get-self notion-get-teams notion-get-groups notion-get-users notion-get-tool-access notion-get-async-task notion-get-version-changes notion-view-version notion-get-comments notion-get-suggested-edit notion-query-data-sources notion-query-multiple-data-sources notion-download-attachment notion-get-enabled-skills notion-download-skill notion-memory-search notion-search-agents notion-query-sessions notion-search-sessions notion-get-session-status notion-wait-session notion-list-session-events notion-read-session-event notion-calendar-list-calendars notion-calendar-list-events notion-calendar-list-coworkers-events notion-calendar-list-calendar-resources notion-calendar-list-contacts notion-update-page notion-restore-version notion-restore-pages notion-delete-pages notion-delete-databases notion-update-data-source notion-create-view notion-update-view notion-upload-skill notion-update-enabled-skills notion-set-discussion-resolved notion-create-pages notion-duplicate-page notion-create-database notion-create-file-upload notion-create-attachment notion-create-folder
slack: slack_search_public slack_search_public_and_private slack_search_channels slack_search_users slack_search_emojis slack_read_channel slack_read_thread slack_read_canvas slack_read_file slack_read_list slack_read_user_profile slack_list_channel_members slack_list_user_channels slack_get_reactions
miro-mcp: canvas_read_as_svg canvas_search canvas_get_canvas_composer_skill canvas_load_format_skill canvas_get_html_upload_url board_search_boards content_search board_show board_get_space content_item_list_roles space_list space_list_boards space_list_children blog_post_list table_get_latest_update_history comment_list_comments image_get_data image_get_upload_url user_who_am_i user_search_organization_users get_brand_context canvas_update_from_svg board_update_metadata space_update_metadata section_update_metadata board_restore comment_resolve canvas_create_from_svg board_create board_create_format space_create section_create image_create import-claude-design-from-url
firebase: firebase_get_project firebase_list_apps firebase_list_projects firebase_get_sdk_config firebase_get_environment firebase_get_security_rules firebase_validate_security_rules firebase_read_resources firebase_deploy_status apphosting_fetch_logs apphosting_list_backends auth_get_users crashlytics_get_issue crashlytics_list_events crashlytics_batch_get_events crashlytics_list_notes crashlytics_get_report realtimedatabase_get_data dataconnect_list_services functions_get_logs functions_list_functions remoteconfig_get_template firestore_get_document firestore_list_documents firestore_list_collections firestore_query_collection firestore_run_aggregation_query firestore_get_database firestore_list_databases firestore_get_index firestore_list_indexes firestore_get_backup firestore_list_backups firestore_get_backup_schedule firestore_list_backup_schedules developerknowledge_search_documents developerknowledge_answer_query developerknowledge_get_documents
figma: download_assets export_video get_comments get_design_context get_figjam get_metadata get_motion_context get_screenshot get_variable_defs get_code_connect_map get_code_connect_suggestions get_context_for_code_connect get_libraries search_design_system list_generative_plugins get_generative_plugin list_shaders get_shader list_file_shaders whoami weave_list_tools weave_get_tool_inputs weave_get_tool_run_output weave_find_model weave_get_model_run_output use_figma upload_assets add_code_connect_map send_code_connect_mappings create_new_file generate_diagram generate_figma_design generate_image generate_vector_illustration html_to_figma send_code_to_figma create_generative_plugin create_shader weave_upload_asset
googledocs: read_doc update_doc
googleworkspace: search_threads get_thread get_message get_draft list_drafts list_labels download_gmail_attachment search_files list_recent_files read_file_content download_file_content get_file_metadata get_file_permissions list_file_revisions list_shared_drives get_shared_drive_metadata list_calendars list_events get_event search_events suggest_time list_messages search_conversations search_messages list_memberships get_notification_settings search_directory_people search_contacts get_user_profile get_spreadsheet get_values read_presentation read_slide_page read_slide_page_thumbnail read_doc search_corpus
```

Counts: notion 54, slack 14, miro-mcp 34, firebase 38, figma 39, googledocs 2, googleworkspace 36.

#### Rendering per target

| target | `notion:notion-search` | `server:*` (still valid in the meta) | change |
|---|---|---|---|
| Cursor IDE `mcpAllowlist` | `notion:notion-search` | `server:*` | none |
| Cursor CLI `permissions.allow` | `Mcp(notion:notion-search)` | `Mcp(server:*)` | none |
| Claude Code `permissions.allow` | `mcp__notion__notion-search` | `mcp__server__*` | split at the first `:`; today it keeps only the server and appends `__*` |
| Gemini policy | none | none | none (MCP is out of scope there) |

The Claude Code change in `render_target_schema`, for both `mcp.allow` and `mcp.deny`, is this jq function:

```jq
def claude_mcp:
  if test("^[^:]+:.+$")
  then index(":") as $i | "mcp__" + .[:$i] + "__" + .[$i+1:]
  else error("bad mcp entry: " + .)
  end;
```

An entry needs a non-empty server before the first `:` and a non-empty tool part after it; `*` is a valid tool part. Anything else stops the render with an error instead of producing a rule such as `mcp____tool`. Checked with jq 1.7:

| entry | result |
|---|---|
| `notion:notion-search` | `mcp__notion__notion-search` |
| `notion:*` | `mcp__notion__*` |
| `nocolon` | error `bad mcp entry: nocolon` (exit 5) |
| `:tool` | error `bad mcp entry: :tool` (exit 5) |
| `server:` | error `bad mcp entry: server:` (exit 5) |

#### What s2 does differently from its text

1. **No ask list.** Leave union, promotion, passthrough, status and diff alone; `permissions.ask` stays the user's.
2. **The meta goes from 7 entries to 217**, per "New entries" above, not seven rewritten entries.
3. **T15 doesn't read `personal.json`.** T8 and T15 render the fixture `$META` (`notion:*`, `slack:*`, line 49), so changing `personal.json` can't make them fail. Keep those wildcard assertions; they still cover the `server:*` form. Then:
   - Add `"figma:get_screenshot"` to the fixture's `mcp.allow`. Assert `mcp__figma__get_screenshot` and `Mcp(figma:get_screenshot)` render, and that neither `mcp__figma__*` nor `Mcp(figma:*)` does.
   - Add a new test that installs from the real `$AGENTS_DIR/allowlists/personal.json`. This is the test that fails against the old entries. For each of the seven keys, no target holds `<key>:*`, `Mcp(<key>:*)` or `mcp__<key>__*`.
   - In the same test, none of these renders in any target: `slack:slack_send_message`, `slack:slack_schedule_message`, `googleworkspace:send_message`, `googleworkspace:reply`, `googleworkspace:forward`, `googleworkspace:share_file`, `googleworkspace:create_event`, `firebase:firestore_update_document`, `firebase:firestore_delete_document`, `firebase:realtimedatabase_set_data`, `firebase:firebase_deploy`, `firebase:messaging_send_message`, `miro-mcp:board_share`, `miro-mcp:space_share`, `miro-mcp:board_role_update`, `miro-mcp:space_role_update`, `notion:notion-move-pages`, `notion:notion-create-comment`.
   - Notion, Figma and Google Docs have no sharing tool to name, so the no-wildcard assertion is what covers them.
4. **`specs/reviews/r1/f9.md` Evidence:** give the counts per key and the names of the new tests, not all 217 entries.

#### Follow-ups (not in m3)

- Cursor's `permissions.json` reference documents `mcpAllowlist` but not the `mcpDenylist` the installer writes. `mcp.deny` is empty, so nothing depends on it today.
- Claude Code names tools from claude.ai connectors `mcp__claude_ai_<server>__<tool>`. The meta doesn't cover them, so they prompt.
- Re-check the names when a server's docs change. A renamed read tool prompts until someone adds it, which is the safe direction.

#### Appendix: per-tool record

<details>
<summary>Every tool on the seven servers: what it does, class, allowed or prompted</summary>

A = allowed, P = prompted. Sources are in the Sources table above; every page was read on 2026-11-22. Each line gives the tool, what it does where the name doesn't say, its class and whether it is allowed or prompted.

##### notion (Notion hosted MCP; each name below drops the `notion-` prefix)
Read, A: search (pages and databases); connector-search (connected apps); fetch (open a page, database or connected result); list-private-pages, list-shared-pages, list-favorite-pages, list-recent-pages, list-page-backlinks; query-meeting-notes; get-self; get-teams; get-groups; get-users; get-tool-access; get-async-task (status of a create or update); get-version-changes; view-version; get-comments; get-suggested-edit; query-data-sources; query-multiple-data-sources; download-attachment; get-enabled-skills; download-skill; memory-search; search-agents; query-sessions; search-sessions; get-session-status; wait-session; list-session-events; read-session-event; calendar-list-calendars; calendar-list-events; calendar-list-coworkers-events; calendar-list-calendar-resources; calendar-list-contacts.
Rollback, A:
- update-page (content and properties; version history)
- restore-version (revert a page to a past version)
- restore-pages (recover pages from Trash)
- delete-pages and delete-databases (move to Trash)
- update-data-source (fields and layout)
- create-view, update-view
- upload-skill (replaces a page's content; version history)
- update-enabled-skills (own settings)
- set-discussion-resolved (can be reopened)

Create, A: create-pages, duplicate-page, create-database, create-file-upload, create-attachment, create-folder.
Send, P:
- create-comment (notifies people)
- update-comment (others see it; no history)
- create-suggested-edit (teammates review it)
- resolve-suggested-edit (accepting or rejecting a teammate's suggestion)
- set-comment-reaction
- calendar-create-events, calendar-update-events, calendar-cancel-events (notify attendees)
- spawn-session, send-message-to-session (hand work to a Custom Agent that acts with its own access)

Share, P: move-pages (moving into a teamspace can change who sees a page); get-file-download-urls (temporary bearer links).
Unrecoverable or undocumented, P:
- delete-comment
- update-folder (can remove files; recovery not documented)
- convert-page-to-skill (rollback not documented)
- stop-session

##### slack (Slack hosted MCP)
Read, A:
- search_public, search_public_and_private (messages and files)
- search_channels, search_users, search_emojis
- read_channel, read_thread, read_canvas (as markdown), read_file, read_list, read_user_profile
- list_channel_members, list_user_channels, get_reactions

Send, P:
- send_message, schedule_message, add_reaction
- create_conversation (channel, group DM or IM)
- complete_file_upload (can share to a channel)

Write, P (the Owner's Slack rule allows reads only): send_message_draft, create_canvas, update_canvas, create_list, update_list, add_list_record, update_list_record, get_file_upload_url.

##### miro-mcp (Miro hosted MCP)
Read, A:
- canvas_read_as_svg, canvas_search
- canvas_get_canvas_composer_skill, canvas_load_format_skill (authoring instructions)
- canvas_get_html_upload_url (reserves upload slots; part of a create)
- board_search_boards (deprecated), content_search, board_show, board_get_space
- content_item_list_roles (who has access)
- space_list, space_list_boards, space_list_children
- blog_post_list, table_get_latest_update_history, comment_list_comments
- image_get_data, image_get_upload_url
- user_who_am_i, user_search_organization_users, get_brand_context

Rollback, A: canvas_update_from_svg (board diff; board history); board_update_metadata, space_update_metadata, section_update_metadata (rename); board_restore (from trash); comment_resolve (can be undone).
Create, A: canvas_create_from_svg, board_create, board_create_format, space_create, section_create, image_create, import-claude-design-from-url.
Share, P: board_share, board_role_update, space_share, space_role_update, board_move (into a space or folder whose members differ), board_move_to_team, image_get_url (bearer link).
Send, P: comment_create, comment_reply, blog_post_create, blog_post_update (space feed).
Unrecoverable, P: section_delete.

##### firebase (`firebase-tools@latest mcp`)
Read, A:
- firebase_get_project, firebase_list_apps, firebase_list_projects, firebase_get_sdk_config, firebase_get_environment
- firebase_get_security_rules, firebase_validate_security_rules (syntax check)
- firebase_read_resources (built-in docs), firebase_deploy_status
- apphosting_fetch_logs, apphosting_list_backends
- auth_get_users
- crashlytics_get_issue, crashlytics_list_events, crashlytics_batch_get_events, crashlytics_list_notes, crashlytics_get_report
- realtimedatabase_get_data, dataconnect_list_services
- functions_get_logs, functions_list_functions, remoteconfig_get_template
- firestore get, list and query: document, documents, collections, aggregation query, database(s), index(es), backup(s), backup schedule(s)
- developerknowledge_search_documents, developerknowledge_answer_query, developerknowledge_get_documents

Write, P:
- firebase_login, firebase_logout
- firebase_update_environment (switches the active project)
- firebase_init (writes local files)
- firebase_create_project, firebase_create_app, firebase_create_android_sha
- auth_update_user, auth_set_sms_region_policy
- crashlytics_create_note, crashlytics_update_issue
- realtimedatabase_set_data
- dataconnect_build (compiles and may write generated files), dataconnect_execute (can run mutations)
- remoteconfig_update_template (publish or roll back)
- firestore_add_document, firestore_update_document
- firestore_create_database, firestore_update_database, firestore_create_index
- firestore_create_backup_schedule, firestore_update_backup_schedule

Delete, P: crashlytics_delete_note, firestore_delete_document, firestore_delete_database, firestore_delete_index, firestore_delete_backup, firestore_delete_backup_schedule.
Deploy, P: firebase_deploy. Send, P: messaging_send_message (push notification). Share, P: storage_get_object_download_url (long-lived token URL).

##### figma (Figma MCP, remote and desktop)
Read, A:
- download_assets, export_video, get_comments
- get_design_context, get_figjam, get_metadata, get_motion_context, get_screenshot, get_variable_defs
- get_code_connect_map, get_code_connect_suggestions, get_context_for_code_connect
- get_libraries, search_design_system
- list_generative_plugins, get_generative_plugin, list_shaders, get_shader, list_file_shaders
- whoami
- weave_list_tools, weave_get_tool_inputs, weave_get_tool_run_output, weave_find_model, weave_get_model_run_output

Rollback, A: use_figma (edits files; version history); upload_assets; add_code_connect_map and send_code_connect_mappings (can be edited or removed).
Create, A: create_new_file (in drafts), generate_diagram, generate_figma_design, generate_image, generate_vector_illustration, html_to_figma, send_code_to_figma, create_generative_plugin, create_shader, weave_upload_asset.
Unrecoverable, P: update_generative_plugin and update_shader (overwrite source; no history documented); weave_run_tool and weave_run_model (spend credits); weave_cancel_tool_run.

##### googledocs (Google Docs MCP)
- read_doc (JSON of a document): read, A.
- update_doc (`documents.batchUpdate`: text, styles, tables, tabs, suggestions; no sharing): rollback through Docs version history, A.

##### googleworkspace (Google Workspace MCP endpoint, unconfirmed)
Read, A:
- Gmail: search_threads, get_thread, get_message, get_draft, list_drafts, list_labels, download_gmail_attachment
- Drive: search_files, list_recent_files, read_file_content, download_file_content, get_file_metadata, get_file_permissions, list_file_revisions, list_shared_drives, get_shared_drive_metadata
- Calendar: list_calendars, list_events, get_event, search_events, suggest_time
- Chat: list_messages, search_conversations, search_messages, list_memberships, get_notification_settings
- People: search_directory_people, search_contacts, get_user_profile
- Sheets: get_spreadsheet, get_values
- Slides: read_presentation, read_slide_page, read_slide_page_thumbnail
- Docs: read_doc
- Universal Search: search_corpus

P, everything else:
- Gmail: create_draft, update_draft, delete_draft, send_message, reply, forward, labels, trash and untrash, spam, sensitive labels
- Drive: create_file, copy_file, update_file, share_file, trash_file, request_access
- Calendar: create_event, update_event, delete_event, respond_to_event
- Chat: send_message, mark_as_read, mark_as_unread, update_notification_settings
- Sheets: update_spreadsheet, update_values, update_formulas, insert_dimension, append_values, batch_clear_values, copy_sheet_to_another_spreadsheet
- Slides: update_presentation
- Docs: update_doc (the Owner's Workspace rule allows reads only)
- Classroom: every tool

</details>

</details>

<details>
<summary>Follow-ups</summary>

- Codebase review of `main` after merge (the r1 milestone gate).
- `scan.py` reads `Bash(cmd)` with no `:*` as a prefix, but Claude Code treats it as exact.
- Cursor's docs don't document the `mcpDenylist` the installer writes. `mcp.deny` is empty, so nothing depends on it.
- claude.ai connector tools (`mcp__claude_ai_<server>__*`) aren't in the meta, so they prompt.
- `agents/lib/` now differs from the Agerpoint bok. Not ported, per the walk.

</details>

https://claude.ai/code/session_01BNKwNabpkmZRk6qF5ESbtP

Assisted-by: Claude Code
