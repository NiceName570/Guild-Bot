# Hosting and update procedures

Use one host for the production token. Current production is AWS in us-east-2.
This guide documents alternatives; it does not deploy to Oracle or start a local bot.

## Shared requirements

- Python 3.11+; Python 3.12 is the tested version. Install requirements-frozen.txt.
- Persistent writable storage for guild.db and test-data; reliable outbound HTTPS
  and Discord Gateway access. The application opens no inbound web server port.
- A Discord application, bot token, Guild Install and Server Members Intent enabled.
- Bot owner is a member of every server they intend to configure.
- Discord permissions from README, including channel-only Manage Permissions.
- Private .env and backups, plus an independent backup before migration or updates.

Create a virtual environment and install the locked runtime:

```bash
python3 -m venv venv
./venv/bin/python -m pip install -r requirements-frozen.txt
```

Copy .env.example to .env only if .env does not already exist. Fill it privately:

| Field | Purpose |
| --- | --- |
| DISCORD_TOKEN | Bot login credential; never share or commit it. |
| BOT_OWNER_ID | Your Discord user ID; the only identity allowed to assign managers. |
| CLAN_GUILD_ID | Default/legacy server ID; does not restrict additional server installs. |
| AWS_REGION | Keep us-east-2; the current application checks this value even on other hosts. |
| CLAN_DB_PATH | Optional absolute path to persistent SQLite storage. |
| DISCORD_APPLICATION_ID / DISCORD_PUBLIC_KEY | Application metadata; not required by the Gateway login itself. |

On Linux, restrict .env to the service user with mode 600. No static AWS keys are
needed for the core bot. The AWS backup helper separately needs the instance role.
Use a separate test bot token when running a development instance beside production.

## AWS: current hosting

Use the existing project/host for maintenance; do not launch another production copy.
Required components are EC2, encrypted persistent EBS storage, an instance profile,
outbound networking, and private S3 for cloud backups. All Regional AWS resources
for this project must be in us-east-2. Verify the project Region in AWS Settings >
View all projects > Overview > Additional Info > Region. Check plan, remaining
credits and expiry in AWS Settings > Billing before provisioning anything new.
Free-plan credits are finite; this bot does not upgrade plans.

For a replacement Ubuntu 24.04+ host, stage reviewed source outside /opt/guild-bot
and run deploy/aws/setup.sh. This installs dependencies, an unprivileged clanbot
user and systemd units; it deliberately does not copy secrets or start the service.
Install the current private production .env, a consistent DB snapshot and test-data
with correct ownership/permissions before starting. Never migrate the stale local DB.

Configure /etc/clanbot-backup.env with AWS_REGION and CLAN_BACKUP_BUCKET. The role
needs scoped s3:PutObject on the private backups prefix. Do not copy AWS keys into
the application. See [AWS operations](AWS.md) for existing resources and exact paths.

```bash
sudo systemctl enable --now guild-bot
sudo systemctl enable --now guild-bot-backup.timer
sudo systemctl status guild-bot --no-pager
sudo journalctl -u guild-bot -n 50 --no-pager
sudo systemctl start guild-bot-backup.service
```

The timer runs at midnight UTC; the current setup keeps 14 local snapshots and
uses a 14-day S3 lifecycle. Download private copies outside the AWS project regularly.

### Adding a feature or another AWS service later

1. Inspect current source, private operational notes, and live service/DB state.
   Decide whether the change belongs in bot.py (Discord), clan.py (data/rules),
   tests, or a separate cloud integration. Keep server and test-data isolation.
2. Take an online production backup and check integrity. Preserve private .env
   separately. For schema changes, prefer additive migration and test old DB input.
3. Implement and run appropriate offline tests. Importing modules does not log in
   or send DMs. A real bot process can send due messages, so use a test token for it.
4. For a new AWS service, verify selected Region, Free-plan availability and costs.
   Add only the service permissions the instance role needs, scoped to its resources.
   Separate secret configuration from source. Do not add cross-Region resources.
5. Commit and push reviewed code. There is no automatic GitHub deployment pipeline.
6. Stage files from an exact commit on the AWS host over verified HTTPS/private
   transfer; compare hashes. Preserve live DB, .env, backups and test-data. Keep the
   previous code for rollback. Stop the service before applying a DB migration.
7. Install matching code/dependencies with clanbot ownership and private permissions.
   Restart guild-bot; if units changed, daemon-reload first. Never replace the live
   DB with a local development snapshot just to ship code.
8. Verify service health, Gateway connection, slash-command registration, DB
   integrity, persistent buttons and the private /test-bot panel. Confirm backup
   upload. Do not enable schedules or message real clan members solely for testing.
9. Record changed files, exact deployed commit/hashes, validation and limitations in
   the local summary log/handoff. Remove temporary deployment artifacts and access;
   retain hosting resources required for the active bot.

If a migration cannot be rolled back safely, restore code and data together from
the verified backup with the service stopped. Avoid blindly retrying uncertain DMs.

## Oracle Cloud: alternative Linux host

You need an Oracle Cloud account and an available Linux VM with persistent disk.
Verify current plan eligibility, capacity and costs before provisioning; no current
free-capacity claim is made here. The original Oracle installation is historical
and has not been contacted or updated by the AWS rollout.

For an Ubuntu VM, use the shared Python/configuration steps above and a systemd
service running under a dedicated service user. Reuse the bot service's startup,
restart, working-directory and write-permission pattern, adapting usernames/paths.
The bot's core Discord/SQLite runtime does not need AWS access. Keep the current
AWS_REGION setting as noted above, but do not install the AWS S3 backup service
unless you intentionally configure AWS access. Use deploy/aws/backup.py for local
online snapshots and arrange a private off-host backup destination of your choice.

Top-level deploy/setup.sh and deploy/guild-bot.service target the older Oracle
Linux/opc installation. They are not a verified installer for this current build:
they use old paths/dependencies and start the service immediately. Review/adapt them
before use; do not execute against the old host or a live production DB casually.

To move production: stop AWS, make a final consistent snapshot, transfer configuration
and state privately, start exactly one Oracle service, then verify it. Keep the old
host stopped while retaining a recoverable backup until the new host is confirmed.

## Always-on local Windows machine: alternative host

Current production remains on AWS; do not run these steps using its token while
AWS is connected. A separate test application/token is safe for development.

```powershell
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements-frozen.txt
# Only if .env does not exist:
Copy-Item .env.example .env
# Optional masked local setup form:
./.venv/Scripts/pythonw.exe configure_discord.py
# After private configuration and ensuring no other production host is active:
./.venv/Scripts/python.exe bot.py
```

The setup form saves configuration; it does not start the bot. Keep the foreground
terminal running, or configure an appropriate service/startup manager yourself.
Windows startup is not configured by this repository. Keep the machine awake and
online. The Discord desktop client itself does not need to remain open.

Take a private online snapshot with:

```powershell
./.venv/Scripts/python.exe deploy/aws/backup.py --source guild.db --destination backups
```

Keep another copy outside that machine. For a Linux local host, use the shared
Python steps and a suitable service manager. No AWS or Oracle account is needed
for local hosting of the core bot.
