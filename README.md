# Discord clan manager

Automatic private event invitations and RSVP stats for a Diablo Immortal clan.
Built on the existing Python/discord.py bot on branch `clan-manager-aws`.

**Status:** implemented and tested locally; connected to the target Discord server
on October 17, 2026, with 14 guild slash commands registered. Manager-channel
setup is pending Manage Channels permission and manager/recipient assignments;
automatic invitations are not configured. Not deployed to AWS yet. The original Oracle bot was not changed or
contacted. Its historical notes are preserved in [docs/ORIGINAL_README.md](docs/ORIGINAL_README.md).

## Weekly schedule

| Send invitation | Event | Event starts |
| --- | --- | --- |
| Wednesday 5 PM | Shadow War | Thursday 8 PM |
| Friday 5 PM | Shadow War | Saturday 8 PM |
| Saturday 5 PM | Rite of Exile / Vigil of Blades | Sunday 8 PM |

America/New_York throughout, following daylight saving time. No automatic reminders.
Schedules begin paused and send automatically once managers configure and enable
them. Roles and individually selected players are combined and deduplicated.

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
Copy-Item .env.example .env
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

**Try it privately:** use `/test-bot` or the **Test bot** button. The test panel
can DM an RSVP invitation or announcement only to you, show your test list,
exercise corrections/cancellation, and preview the calendar. Test events/stats
use separate ignored test-data databases. No clan recipient roles are contacted.
Test DM buttons survive restarts; test events close after one hour. A Test bot
button is also posted in the management channel when `/clan-setup` runs.

| Command | Access / purpose |
| --- | --- |
| `/test-bot` | Six managers: private testing panel; only the tester receives test messages |
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
