# AWS deployment preparation — us-east-2 only

**Status: local implementation tested; no AWS resources provisioned and no live
Discord session started.** Missing deployment inputs: AWS CLI/login, Discord bot
token, the builder's Discord user ID, and the target clan server ID. Do not paste
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
