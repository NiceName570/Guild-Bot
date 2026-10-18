# Build record — October 17, 2026

## Inputs and preserved evidence

- Project owner approved docs/APPROVED_SPEC.md requirements and the new branch name
  `clan-manager-aws` in this chat. No paid hosting or plan upgrade authorized.
- Cloned private NiceName570/guild-bot into the previously non-Git workspace's
  `guild-bot/` subdirectory. Parent AGENTS.md and CLAUDE.md retained unchanged.
- Source main commit: bd6c8717e4b03528942c269296bbdcd180357c84.
- docs/ORIGINAL_README.md is byte-for-byte the original main README. Legacy deploy/
  scripts remain as historical Oracle artifacts; new AWS files are in deploy/aws/.
- Did not connect to, stop, modify, or verify the old Oracle deployment. Did not
  read a production database, bot token, or AWS credentials.

## Implemented

Python/discord.py and SQLite; automatic weekly Eastern calendar; saved role/player
targets; owner-only six-position assignment; private manager channel permission
checks; persistent DM buttons; four-stat forms and prefill; declines; start-time
closure; current-event snapshots; manual previews/messages/extra events; audited
corrections; cancellation notices; 90-day live history cleanup; online backups;
at-most-once claims with explicit uncertain delivery; OS-held process lock.

Private player `/rsvp` can show only that player's open invitation IDs, so failed
DM recipients do not need access to the managers' calendar. All lists are paginated.
Automatic reminders were explicitly rejected and are absent.

## Verification

Windows, Python 3.12, discord.py 2.7.1, dependencies recorded in
requirements-frozen.txt. Rerun via README commands; Ruff 0.17.1 used for lint/format.

- 52 unittest cases passed, including mocked Discord commands/components/dispatch,
  access and revocation, invalid/incomplete forms, decline without stats, prefill,
  DST spring/fall timing, missed sends and expiry, delivery failures and uncertain
  sends, cancellation deduplication, large roster pagination, audit/retention,
  nonreused event IDs, process exclusion, legacy table preservation, backup integrity,
  and simulated AWS CLI Free-plan gate (accept active Free; reject Paid/expired/
  depleted/missing expiry/mismatched project).
- Ruff check passed; Ruff format check passed; pip dependency consistency passed.
- PowerShell parser accepted deploy/aws/preflight.ps1; Git Bash syntax check passed
  for deploy/aws/setup.sh. No actual Linux setup/service execution performed.
- git diff --check passed. Historical README byte comparison passed before commit.
- A backup test initially exposed unclosed SQLite connections on Windows. Fixed
  with explicit connection closing, then full 52-case suite passed.

## Limits and pending work

No AWS resources created; no live Discord connection, commands registered remotely,
or DMs sent. AWS CLI absent on this PC, so actual AWS identity, Free-plan state,
remaining credits, expiry, allowed EC2 type and live host are unverified. Asked the
owner whether to install the CLI. Need BOT_OWNER_ID, CLAN_GUILD_ID and a privately
configured bot token before live tests. Never paste secrets into chat or Git.

Server owners/Administrators can bypass Discord channel privacy. Exact-once DM
delivery across network crashes is not promised: uncertain sends stop for manager
review. Same-host backups are not an off-AWS recovery copy. No live migration of
legacy public event responses has been performed.

AWS public documentation confirms service availability and finite Free-plan rules;
see docs/AWS.md for exact source links and the required live preflight. AWS Free
stops at plan expiry/credit exhaustion. No paid continuation or automated upgrade;
the preflight is not an ongoing universal billing cap if someone independently
changes the AWS plan.

## Follow-up: actual local setup window

The owner clarified they wanted an actual configuration prompt, not a text prompt.
Added configure_discord.py: local Tkinter window for owner user ID, application ID,
public key, masked token, and optional server ID. Saving validates formats,
preserves other setting values, restricts the empty temporary file to the current
Windows user before writing secrets, then atomically replaces ignored .env. No bot
startup or network activity. Three dedicated configuration tests passed, covering
validation, private file save and preservation, and failure without overwrite.
Application metadata is recorded without changing the gateway login mechanism.

## Follow-up: local Discord connection

Owner requested startup after private configuration was completed. First startup
authenticated but Discord rejected the gateway due to Server Members Intent being
disabled. Opened the app's Bot page in the signed-in developer portal, enabled only
Server Members Intent, and saved; Discord confirmed "Bot successfully updated!".
Restarted locally; gateway connection succeeded. Read-only Discord REST verification
confirmed the bot is in the configured target guild, 14 guild commands are present,
and the configured owner is a member. Token was neither printed nor committed.

Bot lacks Manage Channels; Send Messages, Attach Files, and Read Message History
were present. Asked before granting Manage Channels, which can edit/delete server
channels in addition to creating the private manager channel. No management channel
or recurring schedules configured yet, and no invitations or announcements sent.
The running local Python process is temporary local hosting, not AWS deployment.

Attempted to download, signature-verify, and run AWS's official per-user CLI MSI.
Automatic approval review rejected the command before execution with "blocked by
policy"; it supplied no additional reason. Installer not run; did not retry via
another execution path. AWS CLI/authentication and real Free-plan verification
remain pending. No AWS resources created and no AWS login invocation attempted.

## Follow-up: private test buttons

Owner requested a test button for events and other features. Added persistent
Test bot launcher and /test-bot, with a private panel for test event DM, real RSVP
buttons/stats form, list, announcement, audited correction, cancellation, and a
calendar preview. Test recipient is hard-bound to the manager who opened the
panel. Test databases and component IDs are separate from production, so test
stats and event IDs cannot alter or collide with real events. Test buttons restore
on restart; test events close after one hour. No real recipient roles are resolved.
The launcher is available before full clan setup and is posted by /clan-setup.

## Follow-up: automatic new-member signup

Owner requested a welcome on server join asking Buddys membership and in-game name,
with automatic signup. Implemented one DM per human join in the configured guild,
Yes -> name modal -> active self-reported registration, No -> no automatic enrollment.
Confirmed registrations join future recurring invitation recipient lists alongside
explicit roles/users, deduplicated, with in-game and Discord names. Never auto-RSVP
Going or grant manager powers/Discord roles. Departure deactivates; rejoin invalidates
old forms and requires reconfirmation. Existing members are not mass-messaged.
On reconnect, joins since persisted feature activation are caught up idempotently.
Failed/uncertain welcomes are not blindly resent; /join-buddys is the private fallback
and /members is the manager-only signup/delivery list. Persistent welcome buttons,
current-server membership check before form submission, strict per-user controls,
and isolated Test new-member signup button added. Schema changes are additive.

## Documentation and handoff refresh — October 17, 2026

At the owner's request, updated README.md and docs/AWS.md and wrote HANDOFF.md.
Read-only live checks confirmed 17 guild commands, Manage Channels granted, one
management settings row, no stored manager assignments, all three schedules paused,
zero live events/active registrations/welcome rows, and a connected latest gateway
log without a traceback. Worker/launcher process identities were checked. Full
private Discord configuration is present and remains excluded from Git.
Manage Channels was granted after the owner's explicit confirmation in chat and
verified by Discord REST; this resolves the earlier permission-blocked snapshot.
The current management channel was set up after that earlier snapshot.
README/handoff distinguish local hosting from pending AWS deployment and document
the installer policy rejection, next steps, safe operation, testing evidence,
privacy boundaries, and later-requested onboarding/testing features. Historical
entries and the original README remain preserved. No source behavior or live
configuration changed during this documentation update.

## AWS-only deployment — October 17, 2026 Eastern / October 18 UTC

Owner explicitly requested fixing offline hosting and running only on AWS.
Official AWS MCP authenticated to project 673498377045, allowing deployment without
the previously blocked local CLI installer. Verified Free/ACTIVE, $100 credits,
expiry April 17, 2027; no Paid upgrade. All resources are in us-east-2 except
global IAM. Windows bot remained stopped and no autostart was added.

Created private encrypted S3 staging/backup bucket, scoped EC2 role/profile,
outbound-only security group, and t3.micro Ubuntu host i-05620ede0ebe795df with
encrypted retained 12 GiB disk, IMDSv2 and Standard CPU credits. Used consistent
SQLite snapshots and private checksum-verified configuration transfer. Initial
Python upload hit local certificate trust failure; native Windows TLS upload
succeeded without disabling verification. No secret values were printed.

Systemd bot connected to Gateway. First integrity-checked backup uploaded privately
to S3 (118784 bytes, AES256). Rebooted EC2 and observed automatic service startup
and a new Gateway session; backup timer enabled. Configuration/database permissions
verified 600 clanbot. All EC2 reachability checks passed. Removed staging archive
from host and S3, and removed temporary S3 read permission from instance role.
Daily backups retain 14 local files; S3 backup lifecycle is 14 days.

Added cloud_backup.py, boto3 dependency, private build_bundle.py and updated setup
and backup units. Updated README/setup/handoff/AWS guide for AWS-only hosting,
preserving historical snapshots. A long documentation shell edit was blocked before
execution with only blocked-by-policy reason; direct file patches completed it.
All 77 tests, Ruff check/format and whitespace validation passed. Manager assignment,
live player acceptance, and enabling paused schedules remain owner setup tasks.
No real clan invitation was sent for deployment verification. Required AWS resources
are kept to provide requested hosting; temporary staging resources were removed.

## Manager-channel permission fix — October 17, 2026 Eastern

Owner supplied a screenshot of /clan-setup failing. AWS journal showed Forbidden;
live REST confirmed Manage Channels present but Manage Roles absent, including the
channel's Manage Permissions overwrite. Discord documentation confirms overwrite
edits require this separate permission. Owner explicitly approved granting Manage
Permissions only in #clan-management. Enabled and saved on the bot member's channel
overwrite through Discord's web UI; no guild role permission was expanded.

Fixed setup and manager updates to retain the approved bot overwrite, rather than
remove it and fail on the following edit. Missing permission now produces actionable
instructions before editing. Added regressions for repeated setup, manager changes,
privacy and missing permission. All 80 tests and Ruff checks passed. Backed up the
live DB, installed the patch on AWS, matched source hashes, and restarted the cloud
service. No local production process was started.

Live verification after deployment: Discord accepted a no-change overwrite update
with HTTP 200, bot channel Manage Permissions remained enabled, @everyone View
Channel remained denied, and the access list was unchanged. AWS Gateway reconnected.
The slash command itself still awaits the configured owner's retry; the browser
session used for the permission repair belongs to the server owner.

## Multi-server support — October 17, 2026 Eastern

Owner authorized use in any server that installs the app. Removed the production
single-server restriction while preserving the configured owner's exclusive power
to assign each server's six managers. One Gateway and scheduler serve all servers;
GuildScope binds command callbacks, modal state, welcome flows and tests to a fixed
server without mutating a global server ID. Existing guild-scoped SQLite tables
are unchanged. New servers require owner setup before automatic onboarding; their
schedules default paused. Removing the bot pauses that server's recurring schedules.

Global commands plus per-guild sync on ready/join support existing and new installs.
Persistent welcome/test views restore for all server databases. Test component
namespaces include the server for secondary servers, retaining legacy primary IDs.
Live read-only inspection found the public bot already installed in Buddiez and
CallMeFort's server. Default install permissions were zero; updated the app's server
install defaults to 101392 (Manage Channels, View Channel, Send Messages, Attach
Files, Read Message History), retaining existing user-install settings. This changes
future authorization requests, not existing guild grants. No Administrator or guild
Manage Roles requested. Channel-only Manage Permissions still needs a server admin
after channel creation. An invite URL is documented in README and setup guide.

Validation: all 90 automated tests passed, including owner/manager isolation,
cross-server RSVP rejection, fixed DM signup scope, per-server test stores/buttons,
restart restoration, new-server sync and server-specific removal handling. Ruff
check/format and Git whitespace checks passed. Production rollout follows this
entry; live player RSVP/new-join acceptance remains a separate manual check.
