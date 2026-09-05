# guild-bot

A Discord-only replacement for GuildSpire (the guild management bot + web app used
for Diablo Immortal clans).

## Why this exists

GuildSpire's Discord bot does almost nothing except link out to their website. The
guild hates the website — it's confusing, undocumented, and everything in it is
manual. So the whole point of this project is:

**Everything happens inside Discord. Nothing links out. Ever.**

If a feature can't be done with a slash command, a button, or a popup form in
Discord, it doesn't go in.

Second rule, from the same complaint: **it must not need a manual.** Setup is one
guided command, defaults work out of the box, and every command is discoverable
from Discord's own slash-command menu.

## Scope

Four features, in this order:

1. **Event sign-ups** — post an event, people click In / Maybe / Out, the list
   updates live in the message. *(running live on the server since 2026-09-05)*
2. **Weekly recurring schedule** — regular raid nights post themselves with
   reminders. *(not started)*
3. **Guild applications** — apply via a form in Discord, officers approve/decline,
   role assigned automatically. *(not started)*
4. **Roster and ranks** — who's in, their rank, when they last showed up.
   *(not started)*

## Stack and why

- **Python + discord.py** — already installed, matches the other projects here.
- **SQLite** (`guild.db`, created automatically) — a single file next to the bot.
  Survives restarts, no database server to run or pay for.
- **No web app, no frontend, no login system.** That's the entire point.

## Where it runs

Live on an Oracle Cloud free-tier server since 2026-09-05. Nothing runs on the
home PC any more.

- **Host:** `opc@150.136.46.233` — Oracle Linux 9.8, ARM (aarch64), 1 OCPU / 6 GB.
  Instance `DiabloGuildManager`, region us-ashburn-1. Free tier, no billing enabled.
- **SSH:** uses the existing `~/.ssh/id_ed25519` key on the home PC. User is `opc`,
  not `ubuntu` — the instance was built from the default Oracle Linux image.
- **App lives in** `/opt/guild-bot`, not a home directory, to sidestep SELinux
  refusing to run services out of `/home`.
- **Managed by systemd** as `guild-bot`. Restarts itself 5 seconds after any crash
  and comes back on reboot.

Useful commands, all over SSH:

```
systemctl status guild-bot
journalctl -u guild-bot -n 50 --no-pager
sudo systemctl restart guild-bot
```

To push code changes: copy the file to the server and restart the service. There
is no automated deploy yet — `deploy/setup.sh` is a one-time bootstrap, not a
redeploy script.

### Backups

Two tiers, because the server itself is the thing most likely to disappear —
Oracle reclaims free-tier machines it judges idle for 7 days, and a bot waiting on
a websocket looks idle.

1. **On the server**, `guild-bot-backup.timer` runs `deploy/backup.sh` daily at
   00:00 GMT. It writes a dated snapshot to `/opt/guild-bot/backups/` and keeps
   the newest 14. It uses SQLite's online backup API, so it is safe to run while
   the bot is writing — no need to stop anything.
2. **On the home PC**, `deploy/pull-backups.sh` copies those snapshots into
   `backups-local/`. This is the only step that puts a copy outside Oracle, and
   **it is manual** — it has to be run by hand. Automating it would need a Windows
   scheduled task, which cannot be created without admin on this machine.

Verified on 2026-09-05 by running both: a snapshot was taken, pulled down, and the
local copy passed `PRAGMA integrity_check` with the expected 1 event and 1 sign-up
in it. Ran once.

So the exposure is whatever has happened since the last manual pull. Run the pull
after any raid night that matters.

### Other hosting notes

- Enabling Pay As You Go billing would stop the idle-reclaim policy applying
  (Always Free resources stay free). Deliberately not done — the account is
  card-free by choice.

## Running it locally instead

```
pip install -r requirements.txt
python bot.py
```

First run needs a bot token. Steps:

1. Go to <https://discord.com/developers/applications> and hit **New Application**.
2. Open the **Bot** tab, click **Reset Token**, and copy what it gives you.
3. Copy `.env.example` to `.env` and paste the token after `DISCORD_TOKEN=`.
4. Still in the portal, open **OAuth2 > URL Generator**. Tick `bot` and
   `applications.commands`, then under permissions tick **Send Messages** and
   **Embed Links**. Open the URL it builds at the bottom and invite the bot to
   your server.
5. Put your server's ID in `TEST_GUILD_ID` in `.env` so slash commands appear
   instantly instead of taking up to an hour. (Right-click the server in Discord >
   Copy Server ID. Needs Developer Mode on in Discord settings.)

The `.env` file holds the token and is never shared. No other config needed.

## Where it's up to

The event sign-up feature is deployed and connected to Discord.

Confirmed by command output on 2026-09-05, not by me watching Discord:

- The service reports `active` and `enabled`, and the log shows it authenticating
  and connecting to the Discord gateway.
- Killing the process outright brought it back automatically in under 12 seconds
  with a new PID. Ran once.

Seen in Discord by Chris on 2026-09-05, shown to me as a screenshot: `/event`
posted a sign-up sheet, he clicked In, his name appeared under In (1), and the
private "You're down as In" note appeared. I saw the screenshot and the matching
database rows, not the screen itself.

Proven live on the server, 2026-09-05:

- Clicking your current status again removes you. Chris did it at 11:38, I
  repeated it at 11:48. Both times the private note said "Taken you off the list."
  and the row disappeared from the database.
- The embed redraws on click — In (0) went to In (1) with the name listed, then
  back to In (0).
- Buttons still work on a post made *before* the bot moved hosts and restarted
  several times. That is the persistent-view setup doing its job.
- No errors in the service log across any of it.

Still unproven:

- Anyone other than Chris clicking a button. Everything so far is one account.
- More than a handful of people on one event. The name lists truncate at 1000
  characters per column and nobody has come close.

## Next after it runs

- Test with a second account that the buttons work for non-officers.
- Decide who's allowed to create events (role check on `/event`).
- Then feature 2, the recurring weekly schedule.

## Unrelated, still pending

A workspace tidy-up was planned but not approved: moving ~18 active and ~6 old
project folders out of `C:\Users\appro` into `Dev\active` and `Dev\archive`.
Nothing has been moved except this project.
