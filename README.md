# Buddys Discord clan manager

Automatic private event invitations and RSVP stats for a Diablo Immortal clan.
Built on the existing Python/discord.py bot on branch `clan-manager-aws`.

**Status checked October 17, 2026:** `buddysclanmanager` is running on the developer's
Windows PC in the configured clan server, with **17 guild slash commands** registered.
Server Members Intent is enabled, Manage Channels is granted, and the management
channel has been created. The leader/four officers have not yet been assigned, and
all three weekly schedules are **paused**. There are no live events or confirmed
clan registrations in the current database. **AWS deployment is not complete.**

The current build passed **77 automated tests**. These include mocked Discord
interactions; a real event RSVP, new-member signup, and scheduled send still need
user verification in Discord. The original Oracle bot was not contacted or changed.
Its historical evidence is preserved in [docs/ORIGINAL_README.md](docs/ORIGINAL_README.md).

For another developer or a fresh chat, start with **[HANDOFF.md](HANDOFF.md)**.

For step-by-step Discord setup and instructions to run the bot, use
**[SETUP_README.md](SETUP_README.md)**.

## Weekly schedule

| Send invitation | Event | Event starts |
| --- | --- | --- |
| Wednesday 5 PM | Shadow War | Thursday 8 PM |
| Friday 5 PM | Shadow War | Saturday 8 PM |
| Saturday 5 PM | Rite of Exile / Vigil of Blades | Sunday 8 PM |

America/New_York throughout, following daylight saving time. No automatic reminders.
Schedules begin paused and send automatically once managers configure and enable
them. Registered Buddys members, selected roles, and individually selected players
are combined and deduplicated. Registration does not enable a paused schedule.

Going opens a form for armor, armor penetration, potency, and resistance, prefilled
with the player's latest values. All four valid numbers are required before the
response becomes Going. Not going needs no form. Responses close at event start.

The owner, leader, and four officers see a private, automatically updated list of
every recipient, RSVP, stats, and DM delivery outcome. Only the configured bot
owner can assign those six positions. Discord server owners/Administrators can
bypass channel permissions; the bot cannot prevent that platform behavior.

## Local setup

Python 3.11+ (3.12 tested):

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-frozen.txt
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item .env.example .env }
```

For a local setup window with a masked token field, run
`./.venv/Scripts/pythonw.exe configure_discord.py`. It asks for your Discord user
ID, application ID, public key, token, and optional clan server ID. Save privately
writes a user-restricted `.env` without starting the bot or making network calls.
Existing setting values are preserved; the file is rewritten in normalized form.

Or fill in `.env` privately: DISCORD_TOKEN, BOT_OWNER_ID (the builder's Discord user
ID), CLAN_GUILD_ID (the target clan's server ID), AWS_REGION=us-east-2. Enable the
Server Members Intent in the Discord Developer Portal. The bot needs Manage
Channels, View Channels, Send Messages, Read Message History, Attach Files, and
applications.commands; Administrator is unnecessary. Setup requires the bot owner
to be a member of that server.

**Starting connects to Discord and can send due invitations once schedules are
enabled.** Use a separate test application/token or coordinate shutdown of the old
host before using its token. No secrets or real player data are in this branch.

```powershell
./.venv/Scripts/python.exe bot.py
```

The owner runs `/clan-setup`, `/management`, then `/recipients` and
`/recipient-preview` for each schedule. `/schedule` opens the message editor and
preview; Save schedule enables automatic delivery. `/schedules` shows state.

## Discord commands

### New-member signup

New human members of the configured server receive one private welcome asking
whether they belong to **Buddys**. Yes opens an in-game-name form; submitting it
automatically adds them to future recurring event invitations, alongside saved
role/player selections. It does not RSVP Going, assign Discord roles, rename
members, or grant management access. No declines automatic enrollment. Leaving the
server deactivates registration; rejoining requires confirmation again. Existing
members are not mass-DMed. Joins missed during downtime after activation are caught
up once. Welcome buttons survive restarts. Membership is self-reported.

Use `/join-buddys` to sign up or change your in-game name if DMs are blocked.
Managers can use `/members` for the private registration list and welcome DM failures.
The test panel's **Test new-member signup** button exercises the flow privately
without enrolling the tester in the real roster.

### Private testing

**Try it privately:** use `/test-bot` or the **Test bot** button already sent to the
configured owner's DMs. Open a fresh panel after a bot restart. The test panel
can DM an RSVP invitation or announcement only to you, show your test list,
exercise corrections/cancellation, and preview the calendar. Test events/stats
use separate ignored test-data databases. No clan recipient roles are contacted.
Test DM buttons survive restarts; test events close after one hour. A Test bot
button is also posted in the management channel when `/clan-setup` runs.

### Command reference

| Command | Access / purpose |
| --- | --- |
| `/test-bot` | Six managers: private testing panel; only the tester receives test messages |
| `/join-buddys` | Members: confirm clan membership and save/update in-game name |
| `/members` | Six managers: private membership registrations and welcome delivery status |
| `/clan-setup` | Owner only: create/repair private management channel |
| `/management` | Owner only: assign leader + four officers |
| `/recipients` | Six managers: select roles/players to add or remove per schedule |
| `/recipient-preview` | Six managers: inspect every current recipient privately |
| `/schedule` | Six managers: edit message, preview, enable/pause recurring sends |
| `/schedules` | Six managers: show weekly calendar and status |
| `/events` | Six managers: complete event calendar with IDs |
| `/report` | Six managers: refresh all pages of an event list |
| `/correct` | Six managers: correct RSVP/stats before start; audit retained |
| `/cancel-event` | Six managers: confirm one cancellation; one notice per delivered invitation |
| `/announce` | Six managers: editable DM announcement preview, then send without RSVP |
| `/extra-event` | Six managers: editable extra RSVP event preview, then schedule |
| `/audit` | Six managers: private complete event change history |
| `/rsvp` | Players: list only their own open invitations, or open one with event_id |

Managers' commands are enforced by user ID at execution, including form submissions
and confirmation clicks. Slash menu visibility is not authorization. No one gains
manager powers from a Discord role or Administrator alone.

## Reliability and retention

SQLite stores each event/recipient before dispatch. Persistent DM buttons survive
restarts. Catch up missed sends only before event start. An OS process lock prevents
two local processes owning the same DB. Do not run production copies on two hosts.
Sent/failed/uncertain deliveries are never automatically resent. A crash or timeout
between Discord accepting a DM and the DB recording it is marked uncertain for
manager review, because distributed exactly-once delivery is not guaranteed.

Private lists refresh on the 30-second scheduler tick; all recipients are paginated,
not truncated. The bot checks the report channel's explicit permissions before
publishing sensitive data. Delivery pauses if that privacy configuration is exposed.
It cannot retract data already read/copied or stop a Discord admin bypass.

Live event lists and audits expire after 90 days; latest stats remain. Historical
backups may retain expired rows until those backups rotate. Old public-signup DB
tables remain unchanged, but old public buttons are not migrated to this private
flow. Do not replace or delete an old DB without a private verified backup.

## AWS and validation

AWS Free plan only, us-east-2. See [docs/AWS.md](docs/AWS.md) for the read-only plan
preflight, proposed EC2 deployment, private configuration, backups, and live checks.
Free-plan EC2 consumes credits; hosting is not indefinitely free. The plan closes
at credit exhaustion or its duration limit. Nothing auto-upgrades or creates cloud
resources. Actual project plan/credits/permissions still need live verification.

Run offline validation (no Discord login, AWS calls, or player DMs):

```powershell
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Source: `bot.py` (Discord UI/dispatch), `clan.py` (SQLite/rules/calendar),
`instance_lock.py` (single-process protection), `deploy/aws/` (staging/preflight).
Full decisions: [docs/APPROVED_SPEC.md](docs/APPROVED_SPEC.md).

## Finish clan setup

1. The configured owner runs `/management` and chooses the leader and four officers.
   Exactly six distinct people have management access, including the owner.
2. Existing clan members can use `/join-buddys`; new arrivals get the welcome DM.
   Managers may also select roles/individuals with `/recipients` per schedule.
3. Review `/recipient-preview`. Confirm the players who will actually receive DMs.
4. Use `/test-bot` to exercise event responses, stats, corrections, cancellation,
   announcements, onboarding, and the calendar using only the tester's account.
5. Use `/schedule` separately for thursday, saturday, and sunday, review the preview,
   and save with enabled=true. This enables real automatic messages at the listed times.
6. Complete the AWS preflight and deployment in [docs/AWS.md](docs/AWS.md) when
   installation/authentication is available. Do not confuse local uptime with AWS hosting.

Do not run a second production process while the current bot is running. See the
handoff for current local paths, backup, restart, and verification instructions.
