# Buddys clan manager — developer handoff

## Current AWS-only handoff — October 17, 2026 Eastern

The owner's latest instruction is AWS hosting only. **Do not restart bot.py on
Windows or configure Windows autostart.** No local bot process is running.
Production is EC2 `i-05620ede0ebe795df` (BuddysClanManager) in us-east-2, project
`673498377045`. Official AWS MCP authentication replaced the need for a local CLI;
the earlier blocked installer was not retried or bypassed.

Verified: initial Gateway connection, integrity-checked private S3 backup, actual
EC2 reboot, then automatic service startup and a fresh Gateway connection.
Private config and DB are mode 600 owned by clanbot; backup timer enabled.
Configuration, DB and isolated test databases were migrated. The local copy is
now stale and must not overwrite production. All 80 automated tests passed.

Post-deployment /clan-setup failed with Discord Forbidden because Manage Channels
does not permit changing channel overwrites. Owner explicitly approved Manage
Permissions only in #clan-management; enabled through Discord channel settings.
Setup and /management now preserve that channel-only bot permission and explain
the missing permission before attempting edits. Regression tests cover repeated
setup, manager changes, private access, and failure before edits when missing.

Free plan ACTIVE at preflight, $100 USD credits, expiration April 17, 2027.
No Paid upgrade. Check current credits in AWS Settings > Billing. Required hosting
resources stay for the requested AWS-only service. See docs/AWS.md for maintenance,
resources and backup/restore. First backup: backups/guild-20261018-032843-871440.db
in private bucket buddys-clanbot-673498377045-us-east-2. Export off-AWS before expiry.

Repository is PUBLIC: https://github.com/NiceName570/guild-bot, branch
clan-manager-aws. Branch authorship was corrected to NiceName570 with authorization;
old attribution is preserved in a private local Git bundle. Main remains unchanged;
no PR opened. Pushing GitHub does not deploy production.

Remaining: owner assigns leader/four officers, exercises /test-bot privately,
registers/selects recipients, inspects previews and enables schedules when ready.
All three schedules stayed paused at migration. No real clan invitation was sent
to test hosting. Live RSVP/new-join/recurring-send acceptance remains unverified.

Deployment source additions: cloud_backup.py for scoped same-Region S3 uploads,
requirements.txt for boto3, build_bundle.py for private migration snapshots, and
updated setup/systemd backup configuration. No static AWS keys installed.
Never commit .env, DBs, archives, logs, or signed URLs.

## Historical implementation snapshot

The snapshot below preserves the paper trail. Its local-running status, private
repository wording, old commit attribution, AWS blocker and local launch steps
are superseded by the current section above. Follow docs/AWS.md for operation.

Snapshot: October 17, 2026. This is an implementation and operations handoff, not a
claim of complete production rollout. Preserve the original project and paper trail.

## Start here

- Private repository: https://github.com/NiceName570/guild-bot
- Working branch: `clan-manager-aws`. Do not merge or replace `main` without approval.
- Windows checkout: `C:\Users\crucial\Desktop\DiscordBot4Buddys\guild-bot`
- Parent workspace: `C:\Users\crucial\Desktop\DiscordBot4Buddys`
- Follow the parent AGENTS.md and CLAUDE.md, especially the new AWS experience rules.
- Original main commit: `bd6c8717e4b03528942c269296bbdcd180357c84`.
- Last implementation commit before this documentation update:
  `b39f571316d49ce75236891762582ef9d3b1e554`.
- No PR has been opened and main has not been modified.

Read README.md for usage, docs/APPROVED_SPEC.md for the approved base design,
SETUP_README.md for the owner's step-by-step setup/running guide,
docs/BUILD_LOG.md for the chronological record, and docs/AWS.md for deployment.
The original main README is preserved in docs/ORIGINAL_README.md. Its Oracle
deployment statements are historical, not newly verified.

## Verified current state

Rechecked directly through Discord REST, the local DB, process inventory, and the
latest gateway log during this documentation update:

| Item | State |
| --- | --- |
| Discord bot | `buddysclanmanager` |
| Target server | `CallMeFort's server`, ID `1558180921008586894` |
| Application ID | `1561079116378406982` |
| Registered guild commands | 17; see README command table |
| Private configuration | All five supplied Discord fields present; no values printed |
| Server Members Intent | Enabled in the developer portal; gateway accepted connection |
| Manage Channels | Explicitly approved by owner, granted, and REST-verified |
| Management channel | Settings row exists; channel was created via setup |
| Manager assignments | 0 stored; configured owner still has implicit owner access |
| Weekly schedules | thursday, saturday, sunday exist; all enabled=0 |
| Live events / active registrations | 0 / 0 at this snapshot |
| Welcome records | 0 at this snapshot |
| Latest local gateway log | Connected, no traceback observed |
| AWS CLI | Not found on PATH or the checked standard installation path |
| AWS plan / credits / expiry | User reports Free; not authenticated or live-verified |
| AWS resources | None created by this work |

The bot is currently a background Python process on this Windows PC, **not an AWS
service**. At the snapshot, launcher PID was 17608 and worker PID 23308. PIDs are
transient: verify process executable, command line, and parent relationship before
stopping anything. It has no Windows boot/startup service configured. Local uptime
depends on this PC/session remaining available. Initial process launch is not
proof that every user-facing interaction has been tested live.

## Requirements that must remain intact

Discord-only clan management. Four officers, one leader, and the developer/owner
are the six managers. Only the configured owner can assign or replace managers.
Members see only their own private flows. Discord owners/Administrators inherently
bypass channel permission privacy; do not promise the bot can prevent that.

Eastern time means America/New_York with daylight saving changes:

| Invitation DM | Event | Start |
| --- | --- | --- |
| Wednesday 5 PM | Shadow War | Thursday 8 PM |
| Friday 5 PM | Shadow War | Saturday 8 PM |
| Saturday 5 PM | Rite of Exile / Vigil of Blades — both names | Sunday 8 PM |

Once enabled, schedules send automatically. Managers can edit invitation text and
send manual announcements/extra events from slash commands with previews. The
owner explicitly rejected automatic reminders to avoid spam; do not add them.

Going opens a required four-stat form: armor, armor penetration, potency,
resistance. Accept nonnegative whole numbers and correctly grouped commas. Prefill
latest stats. Only successful submission marks Going. Not going saves without
stats. Responses/corrections close at event start. Preserve each event's stats,
full paginated recipient list, delivery status, and correction actor/time/history.
Keep live event history 90 days and latest stats beyond that.

## New-member onboarding

Added after the original interview, at the owner's explicit request:

1. A new human joins the configured server; send one welcome DM asking whether
   they belong to Buddys. Ignore bots/other servers.
2. Yes opens an in-game-name form. Submit only after checking the user remains in
   the server. Saving creates an active, self-reported clan registration.
3. Active registrations automatically join the recipient set for future recurring
   invitations, alongside selected roles and explicit users, deduplicated.
4. Registration does not mark any RSVP Going, enable paused schedules, assign a
   Discord role, rename the Discord user, or grant manager access.
5. No declines automatic enrollment. Explicit manager-selected roles/users remain
   independent recipient sources; No is not a global block against those selections.
6. Leaving deactivates registration. Rejoining creates a new confirmation nonce;
   old welcome forms cannot enroll the user again.
7. Existing members are not mass-DMed. A persisted activation time allows missed
   joins during downtime to be caught up once on reconnect.
8. `/join-buddys` lets current users sign up/update their name privately, including
   when DMs are blocked. `/members` is a manager-only registration/delivery report.

Welcome buttons persist across restart. Failed/uncertain deliveries are recorded
and not blindly resent. Membership is declared by the user, not verified against
an external game roster. Current event recipient snapshots are not retroactively
expanded when someone registers; new registrations apply to future snapshots.

## Code and local files

| File / directory | Purpose |
| --- | --- |
| bot.py | Gateway lifecycle, slash commands, forms, persistent buttons, scheduler, dispatch, onboarding, test panel |
| clan.py | SQLite store, calendar/timezone, validation, audit, reports, membership/onboarding rules |
| configure_discord.py | Local Tkinter setup window; masked token; atomic user-restricted .env save |
| instance_lock.py | OS-held single-process lock on the chosen database |
| guild.db | Private live SQLite state; excluded from Git |
| test-data/ | Per-tester DBs and local launcher metadata; excluded from Git |
| backups/ | Local online DB snapshots; excluded from Git |
| bot-run4-error.log | Latest local Discord gateway/errors log; excluded from Git |
| bot-run4-output.log | Latest local stdout log; excluded from Git |
| bot-error.log, bot-run2/3-*.log | Earlier startup evidence; do not overwrite unnecessarily |
| deploy/aws/ | Free-plan preflight, Ubuntu staging, systemd and backup files |
| deploy/ top-level scripts | Historical Oracle setup; do not run these for AWS |
| requirements-frozen.txt | Locked runtime packages used for the current tested build |
| tests/ | 77 passing automated cases as of the implementation snapshot |

Do not print or commit .env, DISCORD_TOKEN, AWS credentials, databases, test player
data, or logs. The private local .env contains BOT_OWNER_ID, CLAN_GUILD_ID,
DISCORD_TOKEN, DISCORD_APPLICATION_ID, DISCORD_PUBLIC_KEY, and AWS_REGION=us-east-2.
Application ID/public key are metadata; gateway login uses the token. No OpenAI or
AI-provider credentials are required. Preserve existing settings when reopening
the local setup window; it does not connect or start the bot.

New tables use clan_ prefixes. Old public events/rsvps tables are not destroyed or
silently converted into private DM responses. Keep the Oracle host/database
untouched unless the owner separately authorizes work on it.

## Test controls and evidence

The owner received a persistent **Test bot** launcher in a private Discord DM.
`/test-bot` opens the same private panel. Each test panel is bound to the manager
who opened it, including revocation checks. Test messages go only to that manager.

Buttons: Test event DM, Test list, Test announcement, Test correction, Cancel test
event, Preview calendar, and Test new-member signup. The real RSVP/form/delivery
logic is reused with separate per-tester DBs and component namespaces so live
event IDs/stats cannot collide. Test events last one hour. Persistent invitation
and welcome buttons restore after restart; temporary panel sessions should be
reopened through Test bot after a restart.

Last full implementation validation: **77 tests passed**, Ruff check/format passed,
and Git whitespace checks passed. Tests mock outbound Discord calls and AWS CLI
responses. They cover DST, access/revocation, validation/prefill, delivery failures,
idempotence, cancellation, pagination, retention, backup integrity, preflight,
isolated tests, onboarding/rejoin/decline, and active-member recipient resolution.

Known live evidence: token authenticated, gateway connected, 17 commands registered,
owner is in the server, Manage Channels granted, Test bot launcher DM delivered and
read back. No real new join, end-to-end event RSVP, actual recurring send, or AWS
host operation has been independently observed in this work. Do not claim those
are verified simply because the automated suite passes.

```powershell
# Offline; no login, AWS request, or member DM:
./.venv/Scripts/python.exe -m unittest discover -s tests -v
./.venv/Scripts/ruff.exe check bot.py clan.py configure_discord.py instance_lock.py tests deploy/aws/backup.py
```

Ruff 0.17.1 is installed only as local development tooling, not in the runtime lock.
Dependency consistency and script syntax were checked earlier; tests are not
necessary for documentation-only changes unless source behavior changes again.

## Safe local operation

The current process is already running. Do not launch a second bot just to inspect
it. One database lock prevents duplicate processes on this host, but separate DBs
or separate hosts can still connect using the same bot token.

Inspect current bot processes with Get-CimInstance Win32_Process, keeping output to
PID, parent, executable and command line only. Never expose process environment or
the .env contents. Check log tails and private DB metadata when diagnosing.

Before a schema change, take an online backup:

```powershell
./.venv/Scripts/python.exe deploy/aws/backup.py --source guild.db --destination backups
```

This was run before onboarding rollout. After verifying the specific current
worker's identity, stop only that bot process if restarting is necessary. Relaunch
from this checkout with `./.venv/Scripts/python.exe bot.py` (or a hidden Start-Process
with separate stdout/error logs), then verify gateway connection, process health,
and expected guild commands. Starting can send due invitations and onboarding DMs;
it is not a read-only check. Keep earlier logs for the paper trail.

## Next work, in order

1. Owner selects leader and four distinct officers using `/management`. `/clan-setup`
   has already run; repeat only to repair its channel permissions if needed.
2. User exercises the private test panel, including in-game-name signup and failed-DM
   handling. Do not create fake production registrations or contact clan members
   merely to prove a test.
3. Existing members opt in with `/join-buddys`, or managers select recipient roles/
   users. Registered members are always included. Review `/recipient-preview` per event.
4. Enable each schedule only after intended recipients, message preview, and private
   manager permissions are checked. All schedules are paused at this snapshot.
5. Resolve AWS installation/authentication through a permitted path. Then run the
   read-only preflight and complete the approved Free-plan us-east-2 deployment.
6. Before moving the same bot token to AWS, stop the verified local worker to avoid
   two sessions. Transfer private DB/config through an authorized secure route,
   verify on-host service/buttons/DM flow, and obtain an off-AWS backup.

## AWS constraints and exact blocker

Owner chose the new AWS experience **Free plan**, **us-east-2 (Ohio)**, and **zero
out-of-pocket spending**. No paid upgrade, paid continuation, cross-Region work,
Lambda@Edge, or StackSets. Proposed host: one EC2 Linux instance with encrypted
durable storage and systemd; instance type/AMI/permissions/cost are not yet selected
against the real project. All resources must be in us-east-2.

The owner authorized installing AWS CLI, but the combined official per-user MSI
download/signature-verification/install command was rejected by automatic approval
review **before execution**, returning only **"blocked by policy"**. It was not
retried using a different execution route. Do not bypass that rejection or claim
the CLI was installed. User-assisted official installation is a possible next step.

The signing-in-to-aws skill requires specific confirmation before `aws login`.
No AWS login has been attempted. Once authorized credentials are available,
deploy/aws/preflight.ps1 reads identity and Free-plan state, and refuses missing/
expired/non-Free status, unknown expiry, depleted/unverified credits, or mismatched
identity. Actual Free-plan status/credits/expiry remain unverified.

AWS documentation checked earlier says the Free plan closes at credit exhaustion
or six months, whichever comes first; it is not indefinitely free EC2 hosting.
See docs/AWS.md for source links. A preflight is not a universal billing cap if
someone independently upgrades the project. Do not create resources until the
live plan check passes. Once resources exist, ask whether to keep or clean them up.

## Reliability limitations to preserve in the next handoff

- A Discord send and SQLite commit cannot be exactly-once across a network crash.
  Sent/failed/uncertain messages are not automatically retried. Show uncertainty.
- The full live event list refreshes on a 30-second tick. Test list refresh is manual.
- Local backups on the same PC/instance do not cover losing that host or AWS access.
  Download/export a private copy off AWS before expiry. Historical backup retention
  may keep data longer than the live 90-day event policy.
- Guild owners/Administrators can read private channels despite bot overwrites.
- Registered membership is self-reported; there is no external game API verification.
- Local process operation, a successful token check, mocked tests, and a complete
  AWS deployment are different evidence levels. Report each accurately.
