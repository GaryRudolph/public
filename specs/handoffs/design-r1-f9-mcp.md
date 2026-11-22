# r1.f9 design: name the MCP tools that may run, prompt on the rest

The Owner's decision (walk on #45, https://github.com/GaryRudolph/public/issues/45#issuecomment-7074013504): allow MCP writes that have a rollback (version history) or are creates the Owner deletes afterward. Prompt on anything that sends to people, changes sharing or can't be recovered. Notion, Google Docs, Figma and Miro keep their wildcards minus the sharing and permission tools. Slack and Google Workspace allow reads and prompt on send. Firebase allows reads and prompts on writes, deletes and deploys.

Today `agents/allowlists/personal.json` `mcp.allow` holds seven server wildcards (`notion:*` ... `googleworkspace:*`), so every tool on those servers runs without a prompt in all three harnesses.

## Options

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

## Sources, and how sure

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

## Per-server classes

Classes: read, rollback (a write with version history or Trash), create, send (to people, or delegates to an agent that acts), share (sharing or access change, or a bearer download link), unrecoverable (delete, deploy, spend, or undocumented). The per-tool record, with what each tool does, is in the wave's output file. The table lists the prompted tools by name; every other tool on the server is allowed (the exact names are under "New entries").

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

## New entries

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

## Rendering per target

| target | `notion:notion-search` | `server:*` (still valid in the meta) | change |
|---|---|---|---|
| Cursor IDE `mcpAllowlist` | `notion:notion-search` | `server:*` | none |
| Cursor CLI `permissions.allow` | `Mcp(notion:notion-search)` | `Mcp(server:*)` | none |
| Claude Code `permissions.allow` | `mcp__notion__notion-search` | `mcp__server__*` | split at the first `:`; today it keeps only the server and appends `__*` |
| Gemini policy | none | none | none (MCP is out of scope there) |

The Claude Code change in `render_target_schema`, for both `mcp.allow` and `mcp.deny`: a small jq function, `def claude_mcp: index(":") as $i | "mcp__" + .[:$i] + "__" + .[$i+1:];`. A `*` tool part yields `mcp__<server>__*` as before. An entry with no `:`, or an empty server or tool part, fails the render instead of producing `mcp____`.

## What s2 does differently from its text

1. **No ask list.** Leave union, promotion, passthrough, status and diff alone; `permissions.ask` stays the user's.
2. **The meta goes from 7 entries to 217**, per "New entries" above, not seven rewritten entries.
3. **T15 doesn't read `personal.json`.** T8 and T15 render the fixture `$META` (`notion:*`, `slack:*`, line 49), so changing `personal.json` can't make them fail. Keep those wildcard assertions; they still cover the `server:*` form. Then:
   - Add `"figma:get_screenshot"` to the fixture's `mcp.allow`. Assert `mcp__figma__get_screenshot` and `Mcp(figma:get_screenshot)` render, and that neither `mcp__figma__*` nor `Mcp(figma:*)` does.
   - Add a new test that installs from the real `$AGENTS_DIR/allowlists/personal.json`. This is the test that fails against the old entries. For each of the seven keys, no target holds `<key>:*`, `Mcp(<key>:*)` or `mcp__<key>__*`.
   - In the same test, none of these renders in any target: `slack:slack_send_message`, `slack:slack_schedule_message`, `googleworkspace:send_message`, `googleworkspace:reply`, `googleworkspace:forward`, `googleworkspace:share_file`, `googleworkspace:create_event`, `firebase:firestore_update_document`, `firebase:firestore_delete_document`, `firebase:realtimedatabase_set_data`, `firebase:firebase_deploy`, `firebase:messaging_send_message`, `miro-mcp:board_share`, `miro-mcp:space_share`, `miro-mcp:board_role_update`, `miro-mcp:space_role_update`, `notion:notion-move-pages`, `notion:notion-create-comment`.
   - Notion, Figma and Google Docs have no sharing tool to name, so the no-wildcard assertion is what covers them.
4. **`specs/reviews/r1/f9.md` Evidence:** give the counts per key and the names of the new tests, not all 217 entries.

## Follow-ups (not in m3)

- Cursor's `permissions.json` reference documents `mcpAllowlist` but not the `mcpDenylist` the installer writes. `mcp.deny` is empty, so nothing depends on it today.
- Claude Code names tools from claude.ai connectors `mcp__claude_ai_<server>__<tool>`. The meta doesn't cover them, so they prompt.
- Re-check the names when a server's docs change. A renamed read tool prompts until someone adds it, which is the safe direction.
