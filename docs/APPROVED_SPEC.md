# Approved clan manager requirements

Approved by the project owner in this chat on October 17, 2026, following a
grill-me interview. Implementation branch: `clan-manager-aws` in
`NiceName570/guild-bot`. Target is another clan's Discord server, not the
developer's personal Discord server. Keep the original repo and main branch.

## Purpose and calendar

Automatically DM selected clan players a generated, editable event invitation.
No website or separate member login. All scheduling and management are in Discord.

| Invitation | Event | Start |
| --- | --- | --- |
| Wednesday 5 PM | Shadow War | Thursday 8 PM |
| Friday 5 PM | Shadow War | Saturday 8 PM |
| Saturday 5 PM | Rite of Exile / Vigil of Blades (both names) | Sunday 8 PM |

All times use America/New_York, automatically following daylight saving time.
The dates are calculated, not manually entered each week. Once configured,
invitations go out automatically without a per-event approval. Managers can edit
the generated message wording. No automatic reminders: the owner explicitly
rejected the proposed two-hour reminder to avoid spam.

## Access

Exactly six management positions: the bot's builder/owner, one clan leader, four
officers. Only the bot owner assigns or replaces those people. Officers and leader
must not promote or replace managers. Management commands check individual user
IDs, not administrative permissions. Owner ID and target server ID are private
deployment settings. A member's server nickname plus mention identifies them.

Only those six see the full event list and use management actions. Ordinary
members only see their own invitation and response. Discord's platform-level
server owner/Administrator channel-access bypass is an unavoidable limitation,
disclosed during implementation; keep Administrator limited to trusted people.

## Recipients and player flow

Each weekly event saves selected Discord roles, individual players, or both.
Resolve role membership at invitation time. Include human members of the target
server only and deduplicate overlap. Changes to role membership affect later
invitations. Managers can inspect resolved recipients before enabling schedules.

Each DM has Going and Not going buttons, no Maybe choice.

- Going opens a form requiring armor, armor penetration, potency, and resistance.
- All four values must be whole numbers >= 0; accept correctly grouped commas.
- Prefill the player's latest stats so they can confirm or update them.
- Do not mark Going if the form is closed or invalid.
- Not going immediately saves a decline without collecting stats.
- Players can change responses/stats until event start; then responses close.
- Each event preserves its own submitted stats; latest stats remain for future forms.
- If DMs fail, record the failure on the full private list. `/rsvp` lets an invited
  player access only their own invitation ephemerally inside the server.

## Manager view and actions

The private list includes every selected player: Going, Not going, or Awaiting
response; all four stats if Going; DM delivery status/failure; RSVP totals. Page
large lists rather than truncating players. Update after responses and deliveries.
All six can correct responses/stats before closure, with actor, time, before/after
recorded. Completed lists remain viewable. Keep event history/audits 90 days and
latest stats beyond that. Clean Discord report messages as well as database rows.

Managers can send manual DM announcements without RSVP or extra event invitations
with RSVP, using saved recipient selections and an editable preview before send.
They can cancel a single occurrence; close its RSVP, send one cancellation notice
to invitation recipients, and leave future weekly occurrences intact.

Recover missed invitations after downtime only before the event starts. Never
automatically resend a delivery already recorded as sent. An interrupted/uncertain
network send is observable for review instead of automatically retried: exactly-once
delivery cannot be guaranteed across a Discord HTTP request and a local DB commit.

## Hosting and costs

AWS new experience Free plan only; selected Region us-east-2 (Ohio), confirmed by
the owner. Zero out-of-pocket spending, no automatic paid-plan upgrade or paid
continuation. Stop at expiry/credit exhaustion. Verify actual active plan, credits,
and expiry before provisioning. An always-running single EC2 host and persistent
SQLite storage are the proposed deployment, retaining Python/discord.py. EC2 is
listed as supported, but the actual project's permissions/eligibility remain
unverified until AWS authentication is available.

## Implementation boundaries

Never reuse a running Oracle bot session concurrently with the same token.
Existing Oracle deployment and old database remain untouched. Legacy events/rsvps
tables are preserved if an old DB is opened; new tables have a clan_ prefix. Old
public signup buttons are not migrated into private DM responses. The original
README is saved verbatim in ORIGINAL_README.md, including its historical evidence
and unverified hosting claims. No old server status has been checked in this build.
