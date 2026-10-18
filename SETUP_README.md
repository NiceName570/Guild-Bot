# Buddys bot — setup and running guide

This guide explains how to set up and use **buddysclanmanager** in Discord.

The bot runs on **AWS in us-east-2**, independently of this PC. It starts when
the AWS host boots and restarts if its process crashes. You can close Discord,
close this project, or turn off your PC.

## 1. What is already set up

- Private Discord configuration and the saved database are installed on AWS.
- Server Members Intent and Manage Channels are enabled.
- The private management channel exists, with 17 slash commands and private tests.
- Daily private database backups upload to S3.

Weekly schedules remain paused and the leader/four officer positions are unassigned.
Complete the following Discord steps before expecting automatic event invitations.

## 2. Choose the leader and officers

For another server, first use the
[server invite link](https://discord.com/oauth2/authorize?client_id=1561079116378406982&integration_type=0&scope=bot%20applications.commands&permissions=101392).
Choose **Add to Server** and authorize the requested channel/message permissions.
The bot owner must also be a member and run `/clan-setup` there. Each server's setup
and player data are separate. Only the configured bot owner assigns managers;
the invite link or application ID does not grant that authority. No new AWS host
or server-ID configuration change is needed.

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
The bot needs **Manage Permissions inside #clan-management** to repair access and
update the manager list. This channel-only permission has been enabled. For a new
installation, a server administrator enables it under Edit Channel > Permissions >
Advanced permissions > select buddysclanmanager > Manage Permissions > Allow > Save.
Manage Channels alone does not allow editing permission overwrites. The bot
preserves this permission during setup and manager changes.
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

## 8. How it runs on AWS

There is nothing to start on Windows. Production runs as `guild-bot.service` on
EC2 instance `i-05620ede0ebe795df` in **us-east-2 (Ohio)**. It connects outward to
Discord; no inbound server ports are open. Do not run `bot.py` locally using the
production token.

For maintenance, open AWS Console > EC2 > Instances in us-east-2, select
**BuddysClanManager**, and use **Connect > Session Manager**. Then:

```bash
sudo systemctl status guild-bot --no-pager
sudo journalctl -u guild-bot -n 50 --no-pager
sudo systemctl restart guild-bot
```

No AWS CLI installation on this PC is needed. Restarting preserves responses and
persistent invitation buttons. Open `/test-bot` again for a fresh test panel.
The scheduler checks every 30 seconds. Missed sends catch up only before event
start; failed/uncertain sends are shown for review instead of blindly resent.

## 9. Private settings and updates

Production files are under `/opt/guild-bot` on AWS. Its `.env` belongs to `clanbot`
and is readable only by that user and root. Never paste its contents into chat,
Discord, Git, or command output. Update configuration securely on the AWS host,
then restart `guild-bot`. Editing the old local `.env` does not update AWS.

The Windows checkout is for development and offline tests. Pushing GitHub does
not automatically deploy new code. Technical update and restore instructions are
in [docs/AWS.md](docs/AWS.md).

## 10. Backups and Free-plan status

Daily backups run at midnight UTC and upload to the private S3 bucket
`buddys-clanbot-673498377045-us-east-2`, under `backups/`. The host keeps 14
snapshots; S3 expires backup objects after 14 days. Download private copies outside
AWS regularly. The backup contains player data, not the separate token file.

The deployment preflight verified an active **Free plan**, $100 starting credits,
and expiry **April 17, 2027**. Hosting consumes credits and can stop sooner if they
run out. Check **AWS Settings > Billing** for the current balance. No Paid upgrade
was performed. Preserve a private database and configuration copy before expiry.

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
