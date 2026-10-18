# Buddys bot — setup and running guide

This guide explains how to set up and use **buddysclanmanager** in Discord.

The bot currently runs on the developer's **Windows PC**. AWS hosting is prepared
but has not been deployed. Keeping this PC awake and connected keeps the local bot
available. It does not automatically start when Windows starts.

## 1. What is already set up on this PC

- The application, bot token, your Discord user ID, and clan server ID are saved
  privately in the local `.env` file.
- Server Members Intent is enabled.
- The bot has Manage Channels permission.
- The private management channel has been created.
- The bot has 17 slash commands and a private **Test bot** button.

The last checked state had all weekly schedules paused and the leader/four officer
positions unassigned. Complete the following Discord steps before expecting real
automatic event invitations.

## 2. Choose the leader and officers

In the clan's Discord server, run:

```text
/management
```

Select the **leader** and **four officers** in the command fields. Choose five
different people; do not select yourself. You are already the configured owner,
making six managers in total.

**Only you can assign or change these positions.** The leader and officers can
manage events and see the private lists, but cannot replace managers.

If the management channel ever needs its access repaired, run `/clan-setup`.
Discord server owners and people with Administrator can bypass private-channel
permissions; keep that permission limited to trusted people.

## 3. Add clan members to invitations

New people joining the server automatically get a private welcome:

1. **Are you a member of Buddys?**
2. **Yes** opens a form asking for their **in-game name**.
3. Submitting their name adds them to future event invitations.
4. **No** does not add them through automatic registration.

Existing members, or people whose welcome DM was blocked, can run:

```text
/join-buddys
```

This is also how a player updates their saved in-game name. Membership is
self-reported. Registration does not automatically mark the player Going for events.

Managers can additionally use `/recipients` to select roles or individual players
for each weekly event. Registered Buddys members are included automatically, along
with those selections. Duplicate players receive only one invitation. Declining
automatic registration does not override a manager's explicit role/player selection.

Use `/members` to see the private registration list and welcome DM failures.
Use `/recipient-preview` for each schedule to review who will receive invitations.

## 4. Test before enabling real events

Click **Test bot** in your DMs, or run:

```text
/test-bot
```

The panel includes:

| Button | What to try |
| --- | --- |
| Test event DM | Receive an event invitation yourself; try Going, stats, and Not going |
| Test list | See your latest saved RSVP, stats, and delivery status |
| Test announcement | Receive a plain announcement without RSVP buttons |
| Test correction | Change test stats and record who made the correction |
| Cancel test event | Cancel the test occurrence and receive its cancellation notice |
| Preview calendar | Check the upcoming send and event times without sending anything |
| Test new-member signup | Try the Buddys membership question and in-game-name form |

**Only you receive your test messages.** Test records are stored separately from
real clan events and registrations. Test events close after one hour. Open a new
test panel after a bot restart. Use Test list again after responding to refresh it.

## 5. Turn on the three weekly schedules

Run `/schedule`, choose **thursday**, set **enabled** to **true**, and submit.
Edit the event name/message in the form, inspect the preview, then click
**Save schedule**. Repeat for **saturday** and **sunday**.

The six management positions must be assigned, and the schedule needs either
selected recipients or at least one confirmed Buddys registration before enabling.

| Invitation sends | Event | Event starts |
| --- | --- | --- |
| Wednesday 5 PM | Shadow War | Thursday 8 PM |
| Friday 5 PM | Shadow War | Saturday 8 PM |
| Saturday 5 PM | Rite of Exile / Vigil of Blades | Sunday 8 PM |

All times are **Eastern local time**, with automatic daylight saving changes.
There are **no automatic reminders**.

Use `/schedules` to check enabled/paused status. To pause one, use `/schedule` with
enabled=false and save the preview. Pausing stops its future invitation dispatch;
it does not cancel already-sent invitations. Use `/cancel-event` for a cancellation.

Once enabled, the bot generates the dates and sends invitations automatically.
You do not need to run a command for each weekly event.

## 6. What a player does

The player receives an event DM with **Going** and **Not going** buttons.

- **Going:** fill in armor, armor penetration, potency, and resistance. Previous
  stats are prefilled if available. All four values must be whole numbers of zero
  or higher; `5,000` is accepted. Submit the form to save Going.
- **Not going:** records the decline without asking for stats.
- Closing the form without submitting does not record a new Going response.
- Players can change their response or stats until the event starts.

If the event DM fails, managers see the delivery failure. The player can run
`/rsvp` in the server to privately list their open invitations, then use `/rsvp`
with the event_id to answer. They cannot see anyone else's responses.

## 7. What managers can do

| Command | Purpose |
| --- | --- |
| `/events` | Get event IDs, dates, and status |
| `/report` | Refresh the full private list for an event |
| `/correct` | Correct a player's RSVP/stats before start; the change is recorded |
| `/audit` | Read the event's response/correction history |
| `/announce` | Preview/edit a manual DM announcement, then send it |
| `/extra-event` | Preview/edit and schedule an extra RSVP event |
| `/cancel-event` | Confirm cancellation of one occurrence and notify invitation recipients once |

The private event list shows all recipients, Going / Not going / Awaiting response,
submitted stats, and delivery outcomes. It refreshes on the scheduler tick, normally
within about 30 seconds, and uses multiple pages for a large clan.

Live event history is kept for 90 days. Latest player stats remain for future forms.

## 8. How to start or stop it on Windows

The project is here:

```text
C:\Users\crucial\Desktop\DiscordBot4Buddys\guild-bot
```

The bot was already started in the background during setup. **Do not start a second
copy while it is running.** If it has stopped, open PowerShell and run:

```powershell
Set-Location 'C:\Users\crucial\Desktop\DiscordBot4Buddys\guild-bot'
./.venv/Scripts/python.exe bot.py
```

Leave this PowerShell window open while using that foreground launch. Look for
`connected to Gateway` in its output. To stop a foreground launch, press **Ctrl+C**.
If it reports another bot process is using the database, a copy is already running;
do not delete the lock/database to bypass it.

For the existing background copy, use the process-verification/restart instructions
in [HANDOFF.md](HANDOFF.md), rather than closing random Python processes. Closing
Discord itself does not stop the Python bot.

The bot checks schedules every 30 seconds and stores its state in `guild.db`.
Restarting preserves responses and persistent DM buttons. If an invitation time
was missed during downtime, it catches up only if the event has not started.
Uncertain/failed sends are recorded instead of automatically spamming a retry.
If the PC sleeps, shuts down, or loses Internet, the bot cannot send while offline.

## 9. Change private settings or install dependencies again

To reopen the local setup form:

```powershell
Set-Location 'C:\Users\crucial\Desktop\DiscordBot4Buddys\guild-bot'
./.venv/Scripts/pythonw.exe configure_discord.py
```

The token is masked and saved privately. This form saves settings; it does not
start or restart the bot. Restart the existing bot after changing its configuration.
Never paste the token into Discord, share `.env`, or commit it to Git.

If setting up a fresh checkout on Windows with Python 3.11+ installed:

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-frozen.txt
./.venv/Scripts/pythonw.exe configure_discord.py
```

Fill in all five Discord fields, including the target clan server ID, before
starting. Keep AWS_REGION at the approved `us-east-2`. The bot must be installed
in the target server with Server Members Intent enabled and the permissions listed
in [README.md](README.md). Only one host should use the production bot token.

## 10. Backups and AWS

Take a private online database backup from the project folder:

```powershell
./.venv/Scripts/python.exe deploy/aws/backup.py --source guild.db --destination backups
```

Keep `.env`, `guild.db`, and backups private. The backup command does not include
the token file; preserve that securely and separately. Keep an additional copy
away from the running PC before moving hosts.

AWS is **not hosting this bot yet**. The approved target is Free plan, us-east-2,
with no out-of-pocket spending. Installation/authentication and a live plan check
are still pending; see [docs/AWS.md](docs/AWS.md) and [HANDOFF.md](HANDOFF.md).
Do not start an AWS copy while the local production copy is still running.

## Common problems

| Problem | Check |
| --- | --- |
| No slash commands | Bot online, correct server, applications.commands scope |
| PrivilegedIntentsRequired | Enable Server Members Intent in the application's Bot settings |
| Cannot create/repair manager channel | Bot needs Manage Channels |
| Events are not sending | `/schedules` enabled, recipients present, bot online, invitation time reached |
| Player is not getting DMs | Player's DM settings; `/members` for welcome failure or event list for invitation failure |
| Existing player never got the welcome | Expected: existing members use `/join-buddys`; no mass welcome is sent |
| Test form changed nothing on the real list | Expected: test data is intentionally separate |
| Manager cannot change positions | Expected: only the configured owner can use `/management` |

For full technical details, current implementation evidence, and remaining work,
read [HANDOFF.md](HANDOFF.md).
