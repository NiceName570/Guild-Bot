# AWS production operations — us-east-2 only

## Current deployment — October 17, 2026 Eastern

The bot runs **only on AWS**, on EC2 `i-05620ede0ebe795df` (BuddysClanManager),
project `673498377045`, Region **us-east-2**. Windows is not hosting it.
Initial startup connected to Discord Gateway. An actual EC2 reboot then confirmed
automatic startup and a fresh Gateway connection. EC2 reachability checks passed.

Free plan was verified ACTIVE with $100 USD credits at preflight and expiration
`2027-04-17T16:49:03.914Z`. No Paid upgrade. EC2, public IPv4, disk, and S3 consume
credits; check the current balance in **AWS Settings > Billing**. This is not
indefinitely free hosting. Confirm Region under AWS Settings > View all projects >
Overview > Additional Info > Region before replacement work.

| Resource | Configuration |
| --- | --- |
| EC2 | Ubuntu 24.04, t3.micro, Standard CPU credits, IMDSv2 required |
| Disk | Encrypted 12 GiB gp3, vol-0f40d421956ba6e21, retained on termination |
| Network | sg-0e16b1e72465d90c9: no ingress; outbound TCP 443 and 80 |
| Management | Session Manager; no SSH key or open SSH port |
| IAM | BuddysClanBotInstanceRole / BuddysClanBotInstanceProfile; SSM and scoped backup writes |
| S3 | buddys-clanbot-673498377045-us-east-2; fully private, AES256, deny non-TLS |
| Bot | guild-bot.service, enabled at boot, automatic process restart |
| Backup | Daily midnight UTC; first integrity-checked upload succeeded |

Termination protection is enabled. Retained disks still consume credits. Backups
use temporary instance-role credentials, with no static AWS keys installed.
Production files live under `/opt/guild-bot`. `.env` and `guild.db` are mode 600,
owned by clanbot. All three schedules remain paused; finish manager assignment
and private Discord acceptance tests before enabling sends.

The single AWS process now supports every server that installs the public bot.
Commands sync globally and immediately per server on ready/join. Server-specific
scope objects isolate callbacks, onboarding, private tests and manager assignments.
No extra host or CLAN_GUILD_ID change is needed for a new server. The bot owner
still controls manager assignment everywhere. Server setup is required before
automatic welcomes; schedules begin paused. Existing DBs migrate without schema
changes. Removing the bot pauses that server's recurring schedules.

### Maintenance

AWS Console > EC2 in us-east-2 > BuddysClanManager > Connect > Session Manager.
The official AWS MCP connector also supports SSM Run Command. No local CLI needed.

```bash
sudo systemctl status guild-bot --no-pager
sudo journalctl -u guild-bot -n 50 --no-pager
sudo systemctl restart guild-bot
sudo systemctl list-timers guild-bot-backup.timer --no-pager
sudo systemctl start guild-bot-backup.service
sudo journalctl -u guild-bot-backup.service -n 20 --no-pager
```

The unprivileged service restarts after ten seconds. Repeated failures trigger
systemd's start limit; fix the cause, reset-failed, then start. Journal use is capped
at 100 MiB. Never print `.env` or tokens. Do not start another production host.

Backups keep 14 local snapshots and upload to the S3 `backups/` prefix with a 14-day
lifecycle. Download private off-AWS copies regularly and before expiry; S3 in this
project does not protect against loss of project access. Keep configuration
separately. Snapshots retain deleted live rows until rotation; expiry is asynchronous.
To restore, stop the bot, preserve a fresh backup, download the chosen snapshot,
check SQLite integrity, install as guild.db owned by clanbot mode 600, then restart
and verify Gateway. Never overwrite production with the stale Windows DB.

GitHub pushes do not deploy. Back up and stage reviewed source separately; stop
the service before replacing files, preserving `.env`, DB, backups and test-data.
`deploy/aws/setup.sh` stages dependencies/units without starting. Historical Oracle
scripts must not be used. `build_bundle.py` creates a private migration archive under
`.git`, containing credentials and consistent DB snapshots; never publish it or use
a stale local DB for routine updates. Remove deployment staging objects and their
temporary GetObject permission after verification. Keep required hosting resources.

### Historical preparation record

The older notes below preserve the paper trail. Claims that AWS is pending or a
local CLI is required are superseded above, as is the old host-only backup plan.

**Status checked October 17, 2026: bot connected locally to Discord with 17
guild slash commands; no AWS resources provisioned.** Discord credentials and IDs
are configured privately, Server Members Intent is enabled, Manage Channels is
granted, and the management channel exists. The leader/four officers are unassigned
and all weekly schedules are paused. AWS CLI/login remain pending: automatic approval review
blocked the attempted official per-user CLI installer command as "blocked by policy"
without a more specific reason. No installer was run. Do not paste
tokens or AWS credentials into chat or commit them to Git.

## Free-plan evidence checked October 17, 2026

- [Supported services in the new AWS experience](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)
  lists EC2, EBS, and VPC among Free-plan services.
- [AWS plan rules](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html):
  a Free plan ends after six months or when credits run out, whichever comes first;
  it then closes, removing access to resources/data. AWS retains content temporarily
  for 90 days. Credit eligibility is not a promise of indefinitely free hosting.
- [Plan-state API fields](https://docs.aws.amazon.com/cli/latest/reference/freetier/get-account-plan-state.html)
  include FREE/PAID, ACTIVE/EXPIRED, remaining credits, and expiration date.

Check spend/plan status in **AWS Settings > Billing**. Region must be **us-east-2**
as confirmed in AWS Settings > View all projects > Overview > Additional Info >
Region. Do not upgrade, join Organizations, or activate paid capabilities as part
of deployment. No program in this branch upgrades plans or launches infrastructure.

## Read-only preflight

AWS CLI v2.32.0+ is needed for the `aws login` workflow. It is absent from the
current PC. Install/sign-in must be completed before checking the actual project.
The sign-in skill requires explicit confirmation before invoking `aws login`.
Existing SSO workflows should be preserved if present.

Run from the repository root in PowerShell once credentials are available:

```powershell
./deploy/aws/preflight.ps1
# Or with an existing named profile:
./deploy/aws/preflight.ps1 -Profile my-profile
```

This script reads identity and plan state in us-east-2; it refuses a non-ACTIVE
FREE plan, expired plan, missing expiry, mismatched project identity, or unverified
positive USD credit balance. This is a pre-deployment gate, not a permanent budget
watchdog. Recheck immediately before resource creation; never assume chat-reported
Free status proves current eligibility. If plan-state verification is unavailable,
stop provisioning and resolve access rather than treating it as zero usage.

## Proposed host, pending live preflight and final provisioning

One small EC2 Linux instance in us-east-2 running Python under systemd, SQLite on
encrypted EBS. Start selection with t3.micro, standard CPU credit mode (not
Unlimited), Ubuntu 24.04+, no load balancer or NAT gateway, and no web listener.
Check actual permitted instance types, Region AMIs, quotas, and credit-funded cost
before choosing or launching. Public IPv4, storage, compute, and network traffic
can consume credits; do not label them unconditionally free. Do not use Spot for
this RSVP schedule. Require IMDSv2 and use least privilege instance access if an
instance profile is needed. Regional resources must stay in us-east-2.

Use outbound HTTPS for Discord. No public inbound bot port is necessary. Prefer
Session Manager if supported/configured; otherwise restrict SSH to the developer's
actual IP. Never open SSH to the entire Internet. No human IAM role assignments
are part of this project. Do not create multi-Region resources, Lambda@Edge, or
StackSets. If no safe Free-plan host is available, stop and report that limitation.

## Stage and configure the host

`deploy/aws/setup.sh` is for a newly chosen Ubuntu EC2 host; the old deploy scripts
at deploy/ are Oracle-specific historical files. The new setup script installs
dependencies, creates an unprivileged clanbot service user, stages the application
and backup services, but does not enable/start anything or copy secrets. Do not
run it on the local Windows machine or on the old Oracle host.

After staging approved source on the host, create `/opt/guild-bot/.env` from
`.env.example`, owned by clanbot with mode 600. Supply DISCORD_TOKEN,
BOT_OWNER_ID, CLAN_GUILD_ID, AWS_REGION=us-east-2. Keep the database on persistent
storage. The app does not require AWS access keys.

For a safe rollout, use a separate Discord application/token while testing. If
reusing the existing application, coordinate shutdown of the old host first so
two processes do not consume the same bot session or send duplicate invitations.
The branch does not access or stop the old server.

Enable the **Server Members Intent** in the Discord Developer Portal. Invite with
bot and applications.commands scopes. The bot needs View Channels, Send Messages,
Read Message History, Attach Files, and Manage Channels; it does not need
Administrator or Manage Roles. The owner must be a member of the target server.
Manager identities are explicit user assignments, not Discord role assignments.

Only after configuration and a final Free-plan check:

```bash
sudo systemctl enable --now guild-bot
sudo systemctl enable --now guild-bot-backup.timer
sudo systemctl status guild-bot --no-pager
```

In the target Discord server, the configured owner runs `/clan-setup`,
`/management` (select leader + four officers), `/recipients` per weekly event,
`/recipient-preview`, then `/schedule` to edit, preview, and enable each one.
Schedules default to paused to avoid unintended messages before setup is complete.
After setup, future sends need no manual approval. One process lock protects a
single database on one host; never run copies of the same production bot on
separate hosts. The application only registers guild commands to CLAN_GUILD_ID.

## Verify live before calling it deployed

1. Confirm Free-plan preflight and us-east-2 resources, service active, gateway connected.
2. Confirm only owner can assign managers; a nonmanager is denied management commands.
3. Confirm channel access with a regular member. Owners/Administrators inherently
   bypass Discord channel privacy and cannot be excluded by this bot.
4. Use a small authorized test role and a future extra event to verify actual DMs,
   Going form, decline, saved-stat prefill, edits, private list, and blocked DM status.
5. Restart and use a previously sent invitation to verify persistent buttons.
6. Verify one cancellation, no automatic reminders, and event-start closure.
7. Test the backup and download a private copy off AWS. Local automated tests mock
   Discord HTTP and do not establish live delivery or AWS functionality.

## Backups and expiry

The daily backup timer takes an online, integrity-checked SQLite snapshot, retaining
14 files under /opt/guild-bot/backups with private permissions. These snapshots
live on the same host and do not protect against losing AWS access. Download a
private copy outside AWS regularly and before credits/plan expiry. Backups can
retain previously expired event data for up to their 14-snapshot retention; deleting
90-day history applies to the live DB and Discord reports, not historical backups.
Exported audit/recipient files and user DMs are not remotely retractable.

Latest stats remain beyond the 90-day event retention. On expiry/credit exhaustion,
the Free plan closes instead of continuing paid service. Do not auto-upgrade.
If an external actor manually switches to Paid, AWS can charge: this app is not a
universal billing cap. Revalidate plan status before operating or redeploying.

Once resources actually exist, ask the owner whether to keep them or clean them up;
do not leave unneeded compute, disks, IPs, or snapshots consuming credits.
