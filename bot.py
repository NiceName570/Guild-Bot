"""Discord-only clan manager. Importing does not connect or send messages."""

from __future__ import annotations

import asyncio
import datetime as dt
import io
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Literal

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from clan import (
    DEFAULT_BODY,
    EASTERN,
    STAT_LABELS,
    Store,
    now_ts,
    parse_eastern,
    report_pages,
    validate_stats,
)

LOG = logging.getLogger("clan")
ScheduleKey = Literal["thursday", "saturday", "sunday"]


async def private_reply(interaction, text, **kwargs):
    if interaction.response.is_done():
        return await interaction.followup.send(text, ephemeral=True, **kwargs)
    return await interaction.response.send_message(text, ephemeral=True, **kwargs)


def invitation(event):
    return (
        f"**{discord.utils.escape_markdown(event['title'])}**\n"
        f"<t:{event['starts_at']}:F> · Eastern schedule\n\n{event['body']}"
    )


def channel_overwrites(guild, people):
    return {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
        ),
        **{
            person: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )
            for person in people
            if person.id != guild.me.id
        },
    }


def check_private(channel, allowed_ids):
    """Fail closed on permission drift; Discord administrator bypass is unavoidable."""
    if channel.overwrites_for(channel.guild.default_role).view_channel is not False:
        raise PermissionError(
            "Manager channel is no longer private. Ask the bot owner to repair setup."
        )
    for target, overwrite in channel.overwrites.items():
        if overwrite.view_channel is True and (
            not isinstance(target, discord.Member) or target.id not in allowed_ids
        ):
            raise PermissionError("Manager channel grants access to an unselected person or role.")


class SafeView(discord.ui.View):
    async def on_error(self, interaction, error, item):
        LOG.error("Component failed: %s", type(error).__name__)
        text = (
            str(error)
            if isinstance(error, (ValueError, PermissionError))
            else "That action failed. Try again or contact the bot owner."
        )
        await private_reply(interaction, text)


class StatsModal(discord.ui.Modal):
    def __init__(self, client, event_id, subject_id, values, manager_id=None):
        super().__init__(
            title="Confirm your four stats" if not manager_id else "Correct player stats",
            timeout=600,
        )
        self.client, self.event_id, self.subject_id = client, event_id, subject_id
        self.manager_id = manager_id
        self.inputs = []
        for label, value in zip(STAT_LABELS, values):
            field = discord.ui.TextInput(
                label=label,
                required=True,
                max_length=25,
                default=str(value) if value != "" else None,
            )
            self.inputs.append(field)
            self.add_item(field)

    async def on_submit(self, interaction):
        if self.manager_id:
            self.client.require_manager(interaction)
            if interaction.user.id != self.manager_id:
                raise PermissionError("This correction belongs to a different manager.")
        elif interaction.user.id != self.subject_id:
            raise PermissionError("You can only update your own response.")
        try:
            values = validate_stats([field.value for field in self.inputs])
        except ValueError as exc:
            await private_reply(interaction, str(exc), view=RetryStatsView(self))
            return
        self.client.store.respond(
            self.event_id, self.subject_id, "going", values, now_ts(), self.manager_id
        )
        await private_reply(interaction, "Saved: **Going**. Your four stats are recorded.")

    async def on_error(self, interaction, error):
        LOG.error("Stats form failed: %s", type(error).__name__)
        await private_reply(
            interaction,
            str(error)
            if isinstance(error, (ValueError, PermissionError))
            else "Could not save your stats. Please try again.",
        )


class RetryStatsView(SafeView):
    def __init__(self, modal):
        super().__init__(timeout=600)
        self.modal = modal

    @discord.ui.button(label="Fix stats", style=discord.ButtonStyle.primary)
    async def retry(self, interaction, button):
        if interaction.user.id != (self.modal.manager_id or self.modal.subject_id):
            raise PermissionError("This form belongs to someone else.")
        await interaction.response.send_modal(
            StatsModal(
                self.modal.client,
                self.modal.event_id,
                self.modal.subject_id,
                [field.value for field in self.modal.inputs],
                self.modal.manager_id,
            )
        )


class RSVPView(SafeView):
    def __init__(self, client, event_id, recipient_id):
        super().__init__(timeout=None)
        self.client, self.event_id, self.recipient_id = client, event_id, recipient_id
        for choice, label, style in [
            ("going", "Going", discord.ButtonStyle.success),
            ("not_going", "Not going", discord.ButtonStyle.secondary),
        ]:
            button = discord.ui.Button(
                label=label,
                style=style,
                custom_id=f"{getattr(client, 'component_namespace', 'clan')}:{event_id}:{recipient_id}:{choice}",
            )
            button.callback = self.going if choice == "going" else self.not_going
            self.add_item(button)

    def validate(self, interaction):
        if interaction.user.id != self.recipient_id:
            raise PermissionError("Only the invited player can answer this invitation.")
        event = self.client.store.event(self.event_id)
        if event["state"] == "cancelled" or now_ts() >= event["starts_at"]:
            raise ValueError("This event is closed or cancelled.")
        if not self.client.store.recipient(self.event_id, self.recipient_id):
            raise PermissionError("You are not on this event's list.")
        return event

    async def going(self, interaction):
        event = self.validate(interaction)
        values = self.client.store.last_stats(event["guild_id"], self.recipient_id)
        await interaction.response.send_modal(
            StatsModal(self.client, self.event_id, self.recipient_id, values)
        )

    async def not_going(self, interaction):
        self.validate(interaction)
        self.client.store.respond(self.event_id, self.recipient_id, "not_going", (), now_ts())
        await private_reply(interaction, "Saved: **Not going**. No stats needed.")


class ScheduleModal(discord.ui.Modal):
    def __init__(self, client, schedule, enabled):
        super().__init__(title=f"Edit {schedule['key']} invitation")
        self.client, self.schedule, self.enabled = client, schedule, enabled
        self.name_input = discord.ui.TextInput(
            label="Event name", default=schedule["title"], max_length=100
        )
        self.body_input = discord.ui.TextInput(
            label="Invitation message",
            default=schedule["body"],
            style=discord.TextStyle.paragraph,
            max_length=1500,
        )
        self.add_item(self.name_input)
        self.add_item(self.body_input)

    async def on_submit(self, interaction):
        self.client.require_manager(interaction)
        if self.enabled and not self.client.store.targets(self.schedule["id"]):
            raise ValueError("Select at least one role or player with /recipients first.")
        draft = {"body": self.body_input.value}
        title = self.name_input.value
        draft["render"] = lambda: (
            f"**{self.schedule['key']} schedule preview**\n"
            f"Event: {title}\nStarts: 8 PM Eastern · sends: previous day 5 PM Eastern\n"
            f"After saving: {'Enabled' if self.enabled else 'Paused'}\n\n{draft['body']}"
        )

        async def save(click):
            self.client.store.edit_schedule(
                self.schedule["id"], title, draft["body"], self.enabled, click.user.id
            )
            await private_reply(
                click, "Saved. Scheduled invitations use this wording automatically."
            )

        await private_reply(
            interaction,
            draft["render"](),
            view=ConfirmView(self.client, interaction.user.id, save, "Save schedule", draft),
        )

    async def on_error(self, interaction, error):
        await private_reply(
            interaction,
            str(error)
            if isinstance(error, (ValueError, PermissionError))
            else "Could not save the schedule. Please try again.",
        )


class RecipientsView(SafeView):
    def __init__(self, client, schedule, remove, creator):
        super().__init__(timeout=600)
        self.client, self.schedule, self.remove, self.creator = (
            client,
            schedule,
            remove,
            creator,
        )
        roles = discord.ui.RoleSelect(placeholder="Choose roles", min_values=1, max_values=25)
        users = discord.ui.UserSelect(
            placeholder="Choose individual players", min_values=1, max_values=25
        )

        async def choose_roles(interaction):
            await self.save(interaction, "role", roles.values)

        async def choose_users(interaction):
            await self.save(interaction, "user", users.values)

        roles.callback, users.callback = choose_roles, choose_users
        self.add_item(roles)
        self.add_item(users)

    async def save(self, interaction, kind, values):
        self.client.require_manager(interaction)
        if interaction.user.id != self.creator:
            raise PermissionError("Open your own /recipients selection.")
        for value in values:
            if kind == "role" and (value.is_default() or value.managed):
                raise ValueError(
                    "Choose a clan role, rather than @everyone or an integration role."
                )
            if kind == "user" and (value.bot or not interaction.guild.get_member(value.id)):
                raise ValueError("Choose human members of this server.")
        for value in values:
            self.client.store.target(self.schedule["id"], kind, value.id, self.remove)
        await private_reply(interaction, self.client.target_summary(self.schedule))


class ConfirmView(SafeView):
    def __init__(self, client, creator, action, label="Send", edit=None):
        super().__init__(timeout=600)
        self.client, self.creator, self.action, self.edit = (
            client,
            creator,
            action,
            edit,
        )
        self.used = False
        send = discord.ui.Button(label=label, style=discord.ButtonStyle.success)
        send.callback = self.confirm
        self.add_item(send)
        if edit:
            button = discord.ui.Button(label="Edit message", style=discord.ButtonStyle.secondary)
            button.callback = self.edit_message
            self.add_item(button)

    async def interaction_check(self, interaction):
        self.client.require_manager(interaction)
        if interaction.user.id != self.creator:
            raise PermissionError("This preview belongs to another manager.")
        if self.used:
            raise ValueError("Already confirmed. Open a new preview to make changes.")
        return True

    async def confirm(self, interaction):
        self.used = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)
        await self.action(interaction)

    async def edit_message(self, interaction):
        await interaction.response.send_modal(DraftModal(self))


class DraftModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Edit message")
        self.view = view
        self.field = discord.ui.TextInput(
            label="Message",
            style=discord.TextStyle.paragraph,
            default=view.edit["body"],
            max_length=1500,
        )
        self.add_item(self.field)

    async def on_submit(self, interaction):
        await self.view.interaction_check(interaction)
        self.view.edit["body"] = self.field.value
        await interaction.response.edit_message(content=self.view.edit["render"](), view=self.view)

    async def on_error(self, interaction, error):
        await private_reply(
            interaction,
            str(error)
            if isinstance(error, (ValueError, PermissionError))
            else "Could not edit the message.",
        )


class TestSession:
    """One tester's separate database; never resolves or messages real recipient roles."""

    def __init__(self, client, user_id):
        self.client, self.user_id = client, user_id
        self.component_namespace = f"test{user_id}"
        self.require_manager = client.require_manager
        self.fetch_user = client.fetch_user
        directory = Path(client.store.path).parent / "test-data"
        self.store = Store(directory / f"{client.guild_id}-{user_id}.db")
        self.store.cleanup(now_ts())

    def latest_event(self):
        row = self.store.one("SELECT * FROM clan_events ORDER BY id DESC LIMIT 1")
        if not row:
            raise ValueError("Click Test event DM first.")
        return row

    async def send_event(self, name):
        timestamp = now_ts()
        event_id = self.store.create_event(
            self.client.guild_id,
            "[TEST] Shadow War",
            DEFAULT_BODY,
            timestamp + 3600,
            timestamp - 1,
            self.user_id,
            timestamp,
        )
        self.store.snapshot(event_id, {self.user_id: name})
        event = self.store.event(event_id)
        await ClanBot.deliver_recipients(self, event)
        return self.store.recipient(event_id, self.user_id)


class TestLauncher(SafeView):
    def __init__(self, client):
        super().__init__(timeout=None)
        self.client = client

    @discord.ui.button(
        label="Test bot", emoji="🧪", style=discord.ButtonStyle.primary, custom_id="clan:test-panel"
    )
    async def open_panel(self, interaction, button):
        # A DM has no guild_id; bind authorization to the configured server explicitly.
        if interaction.guild_id not in (
            None,
            self.client.guild_id,
        ) or not self.client.store.is_manager(
            self.client.guild_id, interaction.user.id, self.client.owner_id
        ):
            raise PermissionError("Only the selected managers can test this bot.")
        await private_reply(
            interaction, TestPanel.DESCRIPTION, view=TestPanel(self.client, interaction.user.id)
        )


class TestPanel(SafeView):
    DESCRIPTION = (
        "**Private bot test panel**\n"
        "Test event DMs, Going/Not going, the four-stat form, saved-stat prefill, "
        "announcements, corrections, cancellation, and the response list.\n"
        "Only **you** receive test messages. Test responses and stats are stored separately "
        "from the clan's real events. Test events close after one hour.\n"
        "Use Test list after replying to see the updated result."
    )

    def __init__(self, client, user_id):
        super().__init__(timeout=900)
        self.client, self.user_id = client, user_id
        self.session = client.test_session(user_id)

    async def interaction_check(self, interaction):
        if (
            interaction.user.id != self.user_id
            or not self.client.store.is_manager(
                self.client.guild_id, interaction.user.id, self.client.owner_id
            )
            or interaction.guild_id not in (None, self.client.guild_id)
        ):
            raise PermissionError("Open your own authorized test panel.")
        return True

    @discord.ui.button(label="Test event DM", style=discord.ButtonStyle.success)
    async def event_dm(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        row = await self.session.send_event(interaction.user.display_name)
        if row["delivery"] == "sent":
            await private_reply(
                interaction,
                "Test invitation sent to your DMs. Try Going and the stats form, "
                "then Not going. Test list shows your saved response.",
            )
        else:
            await private_reply(
                interaction,
                f"Test DM delivery: **{row['delivery']}**. "
                "Check your Discord DM settings. Use Test list to see the failure.",
            )

    @discord.ui.button(label="Test list", style=discord.ButtonStyle.secondary)
    async def test_list(self, interaction, button):
        event = self.session.latest_event()
        pages = report_pages(
            event,
            self.session.store.recipients(event["id"]),
            self.session.store.rows(
                "SELECT * FROM clan_audit WHERE event_id=? ORDER BY id", (event["id"],)
            ),
            now_ts(),
        )
        await private_reply(interaction, "**TEST DATA — only you**\n" + pages[0])

    @discord.ui.button(label="Test announcement", style=discord.ButtonStyle.secondary)
    async def announcement(self, interaction, button):
        user = await self.client.fetch_user(self.user_id)
        await interaction.response.defer(ephemeral=True)
        await user.send(
            "**[TEST] Clan announcement**\nThis is a test announcement sent only to you. "
            "There are no RSVP buttons on announcements."
        )
        await private_reply(interaction, "Test announcement sent only to you.")

    @discord.ui.button(label="Test correction", style=discord.ButtonStyle.secondary)
    async def correction(self, interaction, button):
        event = self.session.latest_event()
        if event["state"] == "cancelled" or now_ts() >= event["starts_at"]:
            raise ValueError("Create a new test event first; this one is closed.")
        # No manager_id: all test actions are bound to the tester, including DMs.
        # Record as a manager correction on submit through the isolated session.
        await interaction.response.send_modal(
            TestCorrectionModal(
                self.session,
                event["id"],
                self.user_id,
                self.session.store.last_stats(self.client.guild_id, self.user_id),
            )
        )

    @discord.ui.button(label="Cancel test event", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        event = self.session.latest_event()
        if event["state"] == "cancelled":
            raise ValueError("Already cancelled. Click Test event DM to create another.")
        await interaction.response.defer(ephemeral=True)
        self.session.store.cancel(event["id"], self.user_id)
        await ClanBot.send_cancellations(self.session, self.session.store.event(event["id"]))
        await private_reply(
            interaction,
            "Test event cancelled. The cancellation notice goes only to you. "
            "Its Going/Not going buttons now reject further changes.",
        )

    @discord.ui.button(label="Preview calendar", style=discord.ButtonStyle.secondary, row=1)
    async def calendar(self, interaction, button):
        from clan import DEFAULT_SCHEDULES, occurrences

        lines = ["**Calendar preview — no invitations will be sent**"]
        for _, title, weekday in DEFAULT_SCHEDULES:
            starts, sends = next(occurrences(weekday, now_ts()))
            lines.append(f"**{title}**\nDM: <t:{sends}:F>\nEvent: <t:{starts}:F>")
        lines.append("Eastern schedule with daylight saving changes. No automatic reminders.")
        await private_reply(interaction, "\n\n".join(lines))


class TestCorrectionModal(StatsModal):
    async def on_submit(self, interaction):
        if interaction.user.id != self.subject_id or not self.client.client.store.is_manager(
            self.client.client.guild_id, interaction.user.id, self.client.client.owner_id
        ):
            raise PermissionError("Only this authorized tester can correct the test response.")
        try:
            values = validate_stats([field.value for field in self.inputs])
        except ValueError as exc:
            await private_reply(
                interaction, str(exc) + " Open Test correction again to fix the values."
            )
            return
        self.client.store.respond(
            self.event_id, self.subject_id, "going", values, now_ts(), self.subject_id
        )
        await private_reply(
            interaction, "Test correction saved and audited. Test list shows who changed it."
        )


class ClanBot(discord.Client):
    def __init__(self, store, owner_id, guild_id):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.store, self.owner_id, self.guild_id = store, owner_id, guild_id
        self.tree = app_commands.CommandTree(self)
        self.dispatch_lock = asyncio.Lock()
        self.last_cleanup = 0
        self.test_sessions = {}
        self.register_commands()

    def test_session(self, user_id):
        if user_id not in self.test_sessions:
            self.test_sessions[user_id] = TestSession(self, user_id)
        return self.test_sessions[user_id]

    def require_owner(self, interaction):
        if interaction.guild_id != self.guild_id or interaction.user.id != self.owner_id:
            raise PermissionError(
                "Only the configured bot owner can do that in the configured server."
            )

    def require_manager(self, interaction):
        if interaction.guild_id != self.guild_id or not self.store.is_manager(
            self.guild_id, interaction.user.id, self.owner_id
        ):
            raise PermissionError("Only the six selected managers can use that command.")

    def target_summary(self, schedule):
        targets = self.store.targets(schedule["id"])
        roles = [f"<@&{t['target_id']}>" for t in targets if t["kind"] == "role"]
        users = [f"<@{t['target_id']}>" for t in targets if t["kind"] == "user"]
        text = (
            f"**{schedule['key']} recipients**\nRoles: {', '.join(roles) or 'None'}\n"
            f"Players: {', '.join(users) or 'None'}\nSelections are saved. Enable via /schedule."
        )
        if len(text) > 1900:
            return f"Saved {len(roles)} roles and {len(users)} players. Use /recipient-preview for the full list."
        return text

    async def setup_hook(self):
        self.add_view(TestLauncher(self))
        directory = Path(self.store.path).parent / "test-data"
        if directory.exists():
            for path in directory.glob(f"{self.guild_id}-*.db"):
                user_text = path.stem.split("-")[-1]
                if not user_text.isdecimal():
                    continue
                session = self.test_session(int(user_text))
                for row in session.store.rows(
                    "SELECT r.* FROM clan_recipients r JOIN clan_events e ON "
                    "e.id=r.event_id WHERE e.starts_at>? AND e.state!='cancelled'",
                    (now_ts(),),
                ):
                    self.add_view(
                        RSVPView(session, row["event_id"], row["user_id"]),
                        message_id=row["message_id"],
                    )
        for row in self.store.rows(
            "SELECT r.event_id,r.user_id,r.message_id FROM clan_recipients r "
            "JOIN clan_events e ON e.id=r.event_id WHERE e.starts_at>? AND e.state!='cancelled'",
            (now_ts(),),
        ):
            self.add_view(
                RSVPView(self, row["event_id"], row["user_id"]),
                message_id=row["message_id"],
            )
        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.scheduler.start()

    async def on_ready(self):
        LOG.info("Connected as bot %s; configured server %s", self.user.id, self.guild_id)

    async def close(self):
        self.scheduler.cancel()
        await super().close()

    async def report_channel(self, guild):
        setting = self.store.settings(guild.id)
        if not setting:
            raise ValueError("Run /clan-setup first.")
        channel = await guild.fetch_channel(setting["channel_id"])
        if not isinstance(channel, discord.TextChannel):
            raise ValueError("Manager report channel must be a text channel.")
        allowed = {
            self.owner_id,
            self.user.id,
            *[m["user_id"] for m in self.store.managers(guild.id)],
        }
        check_private(channel, allowed)
        return channel

    async def resolve_targets(self, guild, schedule_id):
        targets = self.store.targets(schedule_id)
        role_ids = {t["target_id"] for t in targets if t["kind"] == "role"}
        user_ids = {t["target_id"] for t in targets if t["kind"] == "user"}
        people = {}
        # REST enumeration avoids an incomplete member cache at send time.
        async for member in guild.fetch_members(limit=None):
            if not member.bot and (
                member.id in user_ids or role_ids.intersection(r.id for r in member.roles)
            ):
                people[member.id] = member.display_name
        return people

    async def refresh_report(self, event):
        guild = self.get_guild(event["guild_id"])
        if guild is None:
            raise ValueError("The bot is not connected to the configured server.")
        channel = await self.report_channel(guild)
        pages = report_pages(
            event,
            self.store.recipients(event["id"]),
            self.store.rows(
                "SELECT * FROM clan_audit WHERE event_id=? ORDER BY id", (event["id"],)
            ),
            now_ts(),
        )
        saved = {
            row["page"]: row["message_id"]
            for row in self.store.rows(
                "SELECT * FROM clan_reports WHERE event_id=?", (event["id"],)
            )
        }
        for index, content in enumerate(pages):
            message = None
            if index in saved:
                try:
                    message = await channel.fetch_message(saved[index])
                    await message.edit(
                        content=content, allowed_mentions=discord.AllowedMentions.none()
                    )
                except discord.NotFound:
                    message = None
            if message is None:
                message = await channel.send(
                    content, allowed_mentions=discord.AllowedMentions.none()
                )
                with self.store.db() as conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO clan_reports VALUES(?,?,?)",
                        (event["id"], index, message.id),
                    )
        for index, message_id in saved.items():
            if index >= len(pages):
                try:
                    await channel.get_partial_message(message_id).delete()
                except discord.NotFound:
                    pass
                with self.store.db() as conn:
                    conn.execute(
                        "DELETE FROM clan_reports WHERE event_id=? AND page=?",
                        (event["id"], index),
                    )

    async def dispatch_event(self, event):
        guild = self.get_guild(event["guild_id"])
        if guild is None:
            return
        await self.report_channel(guild)
        if not event["snapshotted"]:
            if event["schedule_id"] is None:
                raise ValueError("Extra event is missing its recipient snapshot.")
            self.store.snapshot(
                event["id"], await self.resolve_targets(guild, event["schedule_id"])
            )
        await self.deliver_recipients(event)

    async def deliver_recipients(self, event):
        for row in self.store.recipients(event["id"]):
            current = self.store.event(event["id"])
            if current["state"] == "cancelled" or now_ts() >= current["starts_at"]:
                break
            if not self.store.claim(event["id"], row["user_id"]):
                continue
            try:
                user = await self.fetch_user(row["user_id"])
                message = await user.send(
                    invitation(current),
                    view=RSVPView(self, event["id"], row["user_id"]),
                )
            except (discord.Forbidden, discord.NotFound):
                self.store.delivery(
                    event["id"],
                    row["user_id"],
                    "failed",
                    error="DM unavailable or player not found",
                )
            except Exception as exc:
                self.store.delivery(
                    event["id"],
                    row["user_id"],
                    "uncertain",
                    error=f"Delivery needs review ({type(exc).__name__})",
                )
                LOG.warning(
                    "Uncertain event DM: event=%s user=%s type=%s",
                    event["id"],
                    row["user_id"],
                    type(exc).__name__,
                )
            else:
                self.store.delivery(event["id"], row["user_id"], "sent", message.id)
            await asyncio.sleep(0.3)

    async def send_cancellations(self, event):
        for row in self.store.recipients(event["id"]):
            if row["delivery"] not in ("sent", "uncertain") or not self.store.claim(
                event["id"], row["user_id"], True
            ):
                continue
            try:
                user = await self.fetch_user(row["user_id"])
                await user.send(
                    f"**Cancelled: {discord.utils.escape_markdown(event['title'])}**\n"
                    f"<t:{event['starts_at']}:F>\nThis occurrence has been cancelled."
                )
            except (discord.Forbidden, discord.NotFound):
                self.store.delivery(event["id"], row["user_id"], "failed", cancellation=True)
            except Exception:
                self.store.delivery(event["id"], row["user_id"], "uncertain", cancellation=True)
            else:
                self.store.delivery(event["id"], row["user_id"], "sent", cancellation=True)
            await asyncio.sleep(0.3)

    @tasks.loop(seconds=30)
    async def scheduler(self):
        async with self.dispatch_lock:
            timestamp = now_ts()
            self.store.materialize(timestamp)
            due = self.store.rows(
                "SELECT e.* FROM clan_events e LEFT JOIN clan_schedules s ON s.id=e.schedule_id "
                "WHERE e.state='scheduled' AND e.sends_at<=? AND e.starts_at>? "
                "AND (e.schedule_id IS NULL OR s.enabled=1)",
                (timestamp, timestamp),
            )
            for event in due:
                try:
                    await self.dispatch_event(event)
                except Exception as exc:
                    LOG.warning(
                        "Event dispatch paused: event=%s type=%s",
                        event["id"],
                        type(exc).__name__,
                    )
            for event in self.store.rows("SELECT * FROM clan_events WHERE state='cancelled'"):
                try:
                    await self.send_cancellations(event)
                except Exception as exc:
                    LOG.warning(
                        "Cancellation dispatch paused: event=%s type=%s",
                        event["id"],
                        type(exc).__name__,
                    )
            for event in self.store.rows(
                "SELECT * FROM clan_events WHERE state='scheduled' AND starts_at<=?",
                (timestamp,),
            ):
                with self.store.db() as conn:
                    conn.execute(
                        "UPDATE clan_events SET state='closed' WHERE id=?",
                        (event["id"],),
                    )
                    conn.execute("INSERT OR IGNORE INTO clan_dirty VALUES(?)", (event["id"],))
                    conn.execute(
                        "UPDATE clan_recipients SET delivery='expired',delivery_error='Event started before delivery' "
                        "WHERE event_id=? AND delivery='pending'",
                        (event["id"],),
                    )
            for row in self.store.rows("SELECT event_id FROM clan_dirty"):
                # Clear before awaiting so concurrent replies can queue another refresh.
                with self.store.db() as conn:
                    conn.execute("DELETE FROM clan_dirty WHERE event_id=?", (row["event_id"],))
                try:
                    await self.refresh_report(self.store.event(row["event_id"]))
                except Exception as exc:
                    with self.store.db() as conn:
                        conn.execute(
                            "INSERT OR IGNORE INTO clan_dirty VALUES(?)",
                            (row["event_id"],),
                        )
                    LOG.warning(
                        "Private report update paused: event=%s type=%s",
                        row["event_id"],
                        type(exc).__name__,
                    )
            if timestamp - self.last_cleanup >= 3600:
                await self.cleanup(timestamp)
                self.last_cleanup = timestamp

    async def cleanup(self, timestamp):
        for event in self.store.rows(
            "SELECT * FROM clan_events WHERE starts_at<?", (timestamp - 90 * 86400,)
        ):
            try:
                channel = await self.report_channel(self.get_guild(event["guild_id"]))
                for row in self.store.rows(
                    "SELECT message_id FROM clan_reports WHERE event_id=?",
                    (event["id"],),
                ):
                    try:
                        await channel.get_partial_message(row["message_id"]).delete()
                    except discord.NotFound:
                        pass
            except Exception:
                LOG.warning("Expired report deletion needs attention: event=%s", event["id"])
                continue
            with self.store.db() as conn:
                conn.execute("DELETE FROM clan_events WHERE id=?", (event["id"],))
        with self.store.db() as conn:
            conn.execute(
                "DELETE FROM clan_audit WHERE event_id IS NULL AND created_at<?",
                (timestamp - 90 * 86400,),
            )

    @scheduler.before_loop
    async def before_scheduler(self):
        await self.wait_until_ready()

    @scheduler.error
    async def scheduler_error(self, error):
        LOG.error("Scheduler stopped unexpectedly: %s", type(error).__name__)
        # systemd restarts rather than leaving a connected but inert bot.
        await self.close()

    def register_commands(self):
        @self.tree.command(
            name="test-bot", description="Managers: open your private bot test buttons"
        )
        @app_commands.guild_only()
        async def test_bot(interaction: discord.Interaction):
            self.require_manager(interaction)
            await private_reply(
                interaction, TestPanel.DESCRIPTION, view=TestPanel(self, interaction.user.id)
            )

        @self.tree.error
        async def command_error(interaction, error):
            original = getattr(error, "original", error)
            LOG.error("Command failed: %s", type(original).__name__)
            await private_reply(
                interaction,
                str(original)
                if isinstance(original, (ValueError, PermissionError))
                else "That command failed. Check the bot permissions or contact the bot owner.",
            )

        @self.tree.command(
            name="clan-setup",
            description="Owner: create or repair the private manager channel",
        )
        @app_commands.guild_only()
        async def setup(interaction: discord.Interaction):
            self.require_owner(interaction)
            await interaction.response.defer(ephemeral=True)
            guild = interaction.guild
            ids = {
                self.owner_id,
                *[m["user_id"] for m in self.store.managers(guild.id)],
            }
            people = [await guild.fetch_member(uid) for uid in ids]
            overwrites = channel_overwrites(guild, people)
            setting = self.store.settings(guild.id)
            if setting:
                channel = await guild.fetch_channel(setting["channel_id"])
                if not isinstance(channel, discord.TextChannel):
                    raise ValueError("Configured manager channel is not a text channel.")
                await channel.edit(
                    overwrites=overwrites,
                    reason="Bot owner repaired manager-only permissions",
                )
            else:
                channel = await guild.create_text_channel(
                    "clan-management",
                    overwrites=overwrites,
                    reason="Private clan event lists; selected managers only",
                )
            self.store.configure(guild.id, channel.id, now_ts())
            await channel.send(
                "**Bot testing** — only the manager who clicks receives test messages.",
                view=TestLauncher(self),
            )
            await private_reply(
                interaction,
                f"Private channel: {channel.mention}. Next use /management, /recipients, then /schedule. "
                "Discord server owners and administrators can bypass channel permissions.",
            )

        @self.tree.command(
            name="management",
            description="Owner: assign the leader and exactly four officers",
        )
        @app_commands.guild_only()
        async def management(
            interaction: discord.Interaction,
            leader: discord.Member,
            officer1: discord.Member,
            officer2: discord.Member,
            officer3: discord.Member,
            officer4: discord.Member,
        ):
            self.require_owner(interaction)
            members = [leader, officer1, officer2, officer3, officer4]
            if any(m.bot for m in members) or len({self.owner_id, *[m.id for m in members]}) != 6:
                raise ValueError("Choose five different human members, excluding yourself.")
            setting = self.store.settings(interaction.guild_id)
            if not setting:
                raise ValueError("Run /clan-setup first.")
            await interaction.response.defer(ephemeral=True)
            channel = await interaction.guild.fetch_channel(setting["channel_id"])
            owner = await interaction.guild.fetch_member(self.owner_id)
            await channel.edit(
                overwrites=channel_overwrites(interaction.guild, [owner, *members]),
                reason="Bot owner updated the six manager assignments",
            )
            self.store.set_managers(
                interaction.guild_id,
                interaction.user.id,
                self.owner_id,
                leader.id,
                [m.id for m in members[1:]],
            )
            await private_reply(
                interaction,
                "Saved: you, the leader, and four officers. Only you can change these assignments.",
            )

        @self.tree.command(
            name="recipients",
            description="Managers: add or remove scheduled invitation roles and players",
        )
        @app_commands.guild_only()
        async def recipients(
            interaction: discord.Interaction,
            schedule: ScheduleKey,
            remove: bool = False,
        ):
            self.require_manager(interaction)
            selected = self.store.schedule(interaction.guild_id, schedule)
            await private_reply(
                interaction,
                self.target_summary(selected),
                view=RecipientsView(self, selected, remove, interaction.user.id),
            )

        @self.tree.command(
            name="recipient-preview",
            description="Managers: review all current recipients of a schedule",
        )
        @app_commands.guild_only()
        async def recipient_preview(interaction: discord.Interaction, schedule: ScheduleKey):
            self.require_manager(interaction)
            await interaction.response.defer(ephemeral=True)
            selected = self.store.schedule(interaction.guild_id, schedule)
            people = await self.resolve_targets(interaction.guild, selected["id"])
            content = (
                "\n".join(f"{uid}\t{name}" for uid, name in people.items())
                or "No players selected."
            )
            await private_reply(
                interaction,
                f"{len(people)} unique players selected for {schedule}.",
                file=discord.File(io.BytesIO(content.encode()), filename="recipients.txt"),
            )

        @self.tree.command(
            name="schedule",
            description="Managers: edit an automatic weekly invitation and enable or pause it",
        )
        @app_commands.guild_only()
        async def schedule(
            interaction: discord.Interaction,
            schedule: ScheduleKey,
            enabled: bool = True,
        ):
            self.require_manager(interaction)
            if len(self.store.managers(interaction.guild_id)) != 6:
                raise ValueError("The owner must assign all six positions with /management first.")
            selected = self.store.schedule(interaction.guild_id, schedule)
            await interaction.response.send_modal(ScheduleModal(self, selected, enabled))

        @self.tree.command(
            name="schedules",
            description="Managers: see the automatic event calendar and recipient settings",
        )
        @app_commands.guild_only()
        async def schedules(interaction: discord.Interaction):
            self.require_manager(interaction)
            lines = ["**Eastern calendar (daylight saving aware)**"]
            for row in self.store.rows(
                "SELECT * FROM clan_schedules WHERE guild_id=? ORDER BY weekday",
                (interaction.guild_id,),
            ):
                lines.append(
                    f"{row['key']}: {row['title']} · invitations previous day 5 PM · starts 8 PM · "
                    f"{'Enabled' if row['enabled'] else 'Paused'} · {len(self.store.targets(row['id']))} target selections"
                )
            await private_reply(interaction, "\n".join(lines))

        @self.tree.command(
            name="events",
            description="Managers: see event IDs, dates, and open or closed status",
        )
        @app_commands.guild_only()
        async def events(interaction: discord.Interaction):
            self.require_manager(interaction)
            self.store.materialize(now_ts())
            rows = self.store.rows(
                "SELECT * FROM clan_events WHERE guild_id=? ORDER BY starts_at DESC",
                (interaction.guild_id,),
            )
            text = (
                "\n".join(
                    f"#{e['id']} {e['title']} | {dt.datetime.fromtimestamp(e['starts_at'], EASTERN).isoformat()} | {e['state']}"
                    for e in rows
                )
                or "Enable a schedule to generate events."
            )
            await private_reply(
                interaction,
                "Event calendar:",
                file=discord.File(io.BytesIO(text.encode()), filename="events.txt"),
            )

        @self.tree.command(
            name="report", description="Managers: refresh the full private event list"
        )
        @app_commands.guild_only()
        async def report(interaction: discord.Interaction, event_id: int):
            self.require_manager(interaction)
            event = self.store.event(event_id, interaction.guild_id)
            await interaction.response.defer(ephemeral=True)
            async with self.dispatch_lock:
                await self.refresh_report(event)
            await private_reply(
                interaction, "Updated the full list in the private manager channel."
            )

        @self.tree.command(
            name="rsvp",
            description="Open your own event invitation privately, including if its DM failed",
        )
        @app_commands.guild_only()
        async def rsvp(interaction: discord.Interaction, event_id: int | None = None):
            if interaction.guild_id != self.guild_id:
                raise PermissionError("Use this in the configured clan server.")
            if event_id is None:
                rows = self.store.rows(
                    "SELECT e.* FROM clan_events e JOIN clan_recipients r ON r.event_id=e.id "
                    "WHERE e.guild_id=? AND r.user_id=? AND e.starts_at>? AND e.state='scheduled' ORDER BY e.starts_at",
                    (interaction.guild_id, interaction.user.id, now_ts()),
                )
                text = "\n".join(
                    f"#{row['id']} · {row['title']} · <t:{row['starts_at']}:F>" for row in rows
                )
                await private_reply(
                    interaction,
                    "**Your open invitations**\n"
                    + (text or "No open invitations.")
                    + "\nUse /rsvp with an event_id to answer.",
                )
                return
            event = self.store.event(event_id, interaction.guild_id)
            if not self.store.recipient(event_id, interaction.user.id):
                raise PermissionError("You are not on this event's invitation list.")
            if event["state"] == "cancelled" or now_ts() >= event["starts_at"]:
                raise ValueError("This event is closed or cancelled.")
            await private_reply(
                interaction,
                invitation(event),
                view=RSVPView(self, event_id, interaction.user.id),
            )

        @self.tree.command(
            name="correct",
            description="Managers: correct a player's RSVP and record the change",
        )
        @app_commands.guild_only()
        async def correct(
            interaction: discord.Interaction,
            event_id: int,
            player: discord.Member,
            status: Literal["going", "not_going"],
        ):
            self.require_manager(interaction)
            event = self.store.event(event_id, interaction.guild_id)
            if status == "going":
                await interaction.response.send_modal(
                    StatsModal(
                        self,
                        event_id,
                        player.id,
                        self.store.last_stats(event["guild_id"], player.id),
                        interaction.user.id,
                    )
                )
            else:
                self.store.respond(event_id, player.id, status, (), now_ts(), interaction.user.id)
                await private_reply(interaction, "Corrected to Not going. The change is recorded.")

        @self.tree.command(
            name="cancel-event",
            description="Managers: cancel one occurrence and notify invited players once",
        )
        @app_commands.guild_only()
        async def cancel(interaction: discord.Interaction, event_id: int):
            self.require_manager(interaction)
            event = self.store.event(event_id, interaction.guild_id)
            if event["state"] == "cancelled" or now_ts() >= event["starts_at"]:
                raise ValueError("This event is already cancelled or closed.")

            async def action(click):
                self.store.cancel(event_id, click.user.id)
                await private_reply(
                    click,
                    "Cancelled. Cancellation DMs and the manager list will update shortly.",
                )

            await private_reply(
                interaction,
                f"Cancel **{event['title']}**, <t:{event['starts_at']}:F>? "
                "This sends one cancellation notice to players who received an invitation.",
                view=ConfirmView(self, interaction.user.id, action, "Cancel this event"),
            )

        @self.tree.command(
            name="announce",
            description="Managers: preview and send a DM announcement without RSVP buttons",
        )
        @app_commands.guild_only()
        async def announce(
            interaction: discord.Interaction,
            recipients_from: ScheduleKey,
            message: app_commands.Range[str, 1, 1500],
        ):
            self.require_manager(interaction)
            await interaction.response.defer(ephemeral=True)
            schedule = self.store.schedule(interaction.guild_id, recipients_from)
            people = await self.resolve_targets(interaction.guild, schedule["id"])
            if not people:
                raise ValueError("No players selected. Use /recipients first.")
            batch = uuid.uuid4().hex
            draft = {"body": message}
            draft["render"] = lambda: (
                f"**Announcement preview — {len(people)} players**\n\n{draft['body']}"
            )

            async def action(click):
                sent = failed = uncertain = 0
                for uid in people:
                    with self.store.db() as conn:
                        claim = conn.execute(
                            "INSERT OR IGNORE INTO clan_announcement_deliveries VALUES(?,?,'sending')",
                            (batch, uid),
                        )
                    if not claim.rowcount:
                        continue
                    try:
                        user = await self.fetch_user(uid)
                        await user.send(draft["body"])
                    except (discord.Forbidden, discord.NotFound):
                        state = "failed"
                        failed += 1
                    except Exception:
                        state = "uncertain"
                        uncertain += 1
                    else:
                        state = "sent"
                        sent += 1
                    with self.store.db() as conn:
                        conn.execute(
                            "UPDATE clan_announcement_deliveries SET state=? WHERE batch=? AND user_id=?",
                            (state, batch, uid),
                        )
                    await asyncio.sleep(0.3)
                await private_reply(
                    click,
                    f"Announcement complete. Sent: {sent}; failed: {failed}; uncertain: {uncertain}.",
                )

            await private_reply(
                interaction,
                draft["render"](),
                view=ConfirmView(self, interaction.user.id, action, edit=draft),
            )

        @self.tree.command(
            name="extra-event",
            description="Managers: preview and schedule an extra RSVP invitation",
        )
        @app_commands.guild_only()
        @app_commands.describe(
            starts="YYYY-MM-DD HH:MM Eastern, 24-hour clock",
            sends="Invitation time: YYYY-MM-DD HH:MM Eastern",
        )
        async def extra_event(
            interaction: discord.Interaction,
            recipients_from: ScheduleKey,
            title: app_commands.Range[str, 1, 100],
            starts: str,
            sends: str,
            message: app_commands.Range[str, 1, 1500] = DEFAULT_BODY,
        ):
            self.require_manager(interaction)
            start_ts, send_ts = parse_eastern(starts), parse_eastern(sends)
            if start_ts <= now_ts() or send_ts >= start_ts:
                raise ValueError("The event must start in the future, after its invitation time.")
            await interaction.response.defer(ephemeral=True)
            schedule = self.store.schedule(interaction.guild_id, recipients_from)
            people = await self.resolve_targets(interaction.guild, schedule["id"])
            if not people:
                raise ValueError("No players selected. Use /recipients first.")
            draft = {"body": message}
            draft["render"] = lambda: (
                f"**Extra event preview — {len(people)} players**\n"
                f"Send: <t:{send_ts}:F>\n"
                + invitation({"title": title, "starts_at": start_ts, "body": draft["body"]})
            )

            async def action(click):
                if now_ts() >= start_ts:
                    raise ValueError("The event start time has passed. Create a new event.")
                event_id = self.store.create_event(
                    interaction.guild_id,
                    title,
                    draft["body"],
                    start_ts,
                    send_ts,
                    click.user.id,
                    now_ts(),
                )
                self.store.snapshot(event_id, people)
                await private_reply(
                    click, f"Scheduled event #{event_id} for {len(people)} players."
                )

            await private_reply(
                interaction,
                draft["render"](),
                view=ConfirmView(self, interaction.user.id, action, "Schedule", draft),
            )

        @self.tree.command(
            name="audit",
            description="Managers: inspect the complete event response and correction history",
        )
        @app_commands.guild_only()
        async def audit(interaction: discord.Interaction, event_id: int):
            self.require_manager(interaction)
            self.store.event(event_id, interaction.guild_id)
            rows = self.store.rows(
                "SELECT * FROM clan_audit WHERE event_id=? ORDER BY id", (event_id,)
            )
            payload = json.dumps(rows, indent=2).encode()
            await private_reply(
                interaction,
                "Event history:",
                file=discord.File(io.BytesIO(payload), filename=f"event-{event_id}-history.json"),
            )


def main():
    load_dotenv(Path(__file__).with_name(".env"))
    token = os.getenv("DISCORD_TOKEN", "")
    try:
        owner_id = int(os.environ["BOT_OWNER_ID"])
        guild_id = int(os.environ["CLAN_GUILD_ID"])
        if owner_id <= 0 or guild_id <= 0:
            raise ValueError
    except (KeyError, ValueError):
        raise SystemExit(
            "Set BOT_OWNER_ID and CLAN_GUILD_ID to your Discord user ID and the target clan server ID."
        )
    if not token:
        raise SystemExit("Set DISCORD_TOKEN in the private .env file before running the bot.")
    if os.getenv("AWS_REGION", "us-east-2") != "us-east-2":
        raise SystemExit("This deployment is restricted to the approved AWS Region us-east-2.")
    path = os.getenv("CLAN_DB_PATH", str(Path(__file__).with_name("guild.db")))
    from instance_lock import instance_lock

    with instance_lock(path + ".lock"):
        client = ClanBot(Store(path), owner_id, guild_id)
        client.run(token, log_level=logging.INFO)


if __name__ == "__main__":
    main()
