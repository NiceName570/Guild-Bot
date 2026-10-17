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
