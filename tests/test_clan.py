import datetime as dt
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from bot import ClanBot, ConfirmView, RSVPView, StatsModal, check_private
from clan import (
    DEFAULT_BODY,
    EASTERN,
    STAT_FIELDS,
    Store,
    now_ts,
    occurrences,
    parse_eastern,
    parse_stat,
    report_pages,
    validate_stats,
)
from instance_lock import instance_lock


class StoreFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "guild.db"
        self.store = Store(self.path)
        self.timestamp = now_ts()
        self.store.configure(100, 200, self.timestamp)
        self.store.set_managers(100, 1, 1, 2, [3, 4, 5, 6])
        self.event_id = self.store.create_event(
            100,
            "Shadow War",
            DEFAULT_BODY,
            self.timestamp + 10000,
            self.timestamp - 1,
            1,
            self.timestamp,
        )
        self.store.snapshot(self.event_id, {10: "Hero", 11: "Second"})

    def tearDown(self):
        self.temp.cleanup()


class ScheduleTests(unittest.TestCase):
    def test_all_days_and_eastern_hours(self):
        timestamp = parse_eastern("2026-10-19 09:00")
        for weekday in (3, 5, 6):
            start, send = next(occurrences(weekday, timestamp))
            starts = dt.datetime.fromtimestamp(start, EASTERN)
            sends = dt.datetime.fromtimestamp(send, EASTERN)
            self.assertEqual((starts.weekday(), starts.hour), (weekday, 20))
            self.assertEqual((sends.weekday(), sends.hour), (weekday - 1, 17))

    def test_dst_changes_utc_but_not_eastern_hours(self):
        start, send = next(occurrences(6, parse_eastern("2026-10-31 18:00")))
        self.assertEqual(dt.datetime.fromtimestamp(start, EASTERN).hour, 20)
        self.assertEqual(dt.datetime.fromtimestamp(send, EASTERN).hour, 17)
        self.assertEqual(start - send, 28 * 3600)

    def test_spring_change(self):
        start, send = next(occurrences(6, parse_eastern("2026-03-07 18:00")))
        self.assertEqual(start - send, 26 * 3600)

    def test_invalid_ambiguous_nonexistent_times_rejected(self):
        for text in ("tomorrow", "2026-03-08 02:30", "2026-11-01 01:30"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_eastern(text)

    def test_no_past_event_catchup(self):
        timestamp = parse_eastern("2026-10-22 20:00")
        self.assertTrue(all(start > timestamp for start, send in occurrences(3, timestamp)))

    def test_stats(self):
        self.assertEqual(validate_stats(["0", "5,000", "123", "999"]), (0, 5000, 123, 999))
        for text in (
            "",
            "-1",
            "1.5",
            "abc",
            "1e4",
            "1,2",
            "NaN",
            "9223372036854775808",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_stat(text)
        with self.assertRaises(ValueError):
            validate_stats([1, 2, 3])


class StoreTests(StoreFixture, unittest.TestCase):
    def test_schedule_edit_updates_unsent_only(self):
        schedule = self.store.schedule(100, "sunday")
        self.store.target(schedule["id"], "user", 10)
        self.store.edit_schedule(schedule["id"], "Original", DEFAULT_BODY, True, 1)
        self.store.materialize(self.timestamp)
        events = self.store.rows(
            "SELECT * FROM clan_events WHERE schedule_id=? ORDER BY starts_at", (schedule["id"],)
        )
        self.store.snapshot(events[0]["id"], {10: "Hero"})
        self.store.edit_schedule(schedule["id"], "Updated", "New message", True, 1)
        self.assertEqual(self.store.event(events[0]["id"])["title"], "Original")
        self.assertEqual(self.store.event(events[1]["id"])["body"], "New message")

    def test_online_backup_integrity(self):
        from deploy.aws.backup import backup

        target = backup(self.path, Path(self.temp.name) / "backups")
        restored = Store(target)
        self.assertEqual(len(restored.recipients(self.event_id)), 2)

    def test_only_owner_assigns_positions(self):
        with self.assertRaises(PermissionError):
            self.store.set_managers(100, 2, 1, 2, [3, 4, 5, 6])
        self.assertTrue(self.store.is_manager(100, 6, 1))
        self.assertFalse(self.store.is_manager(100, 7, 1))

    def test_six_unique_people(self):
        with self.assertRaises(ValueError):
            self.store.set_managers(100, 1, 1, 1, [3, 4, 5, 6])
        self.assertEqual(len(self.store.managers(100)), 6)

    def test_going_requires_complete_valid_form_atomically(self):
        with self.assertRaises(ValueError):
            self.store.respond(self.event_id, 10, "going", [1, 2, "", 4], self.timestamp)
        row = self.store.recipient(self.event_id, 10)
        self.assertEqual(row["status"], "awaiting")
        self.assertIsNone(row["armor"])
        self.assertEqual(self.store.last_stats(100, 10), ("", "", "", ""))

    def test_decline_no_stats_and_prefill_preserved(self):
        self.store.respond(self.event_id, 10, "going", [1, 2, 3, 4], self.timestamp)
        self.store.respond(self.event_id, 10, "not_going", [], self.timestamp + 1)
        row = self.store.recipient(self.event_id, 10)
        self.assertEqual(row["status"], "not_going")
        self.assertTrue(all(row[key] is None for key in STAT_FIELDS))
        self.assertEqual(self.store.last_stats(100, 10), (1, 2, 3, 4))

    def test_uninvited_cannot_respond(self):
        with self.assertRaises(PermissionError):
            self.store.respond(self.event_id, 999, "going", [1, 2, 3, 4], self.timestamp)

    def test_close_checked_again_on_form_submission(self):
        event = self.store.event(self.event_id)
        with self.assertRaises(ValueError):
            self.store.respond(self.event_id, 10, "going", [1, 2, 3, 4], event["starts_at"])

    def test_cancel_blocks_response(self):
        self.store.cancel(self.event_id, 2)
        with self.assertRaises(ValueError):
            self.store.respond(self.event_id, 10, "not_going", [], self.timestamp)

    def test_correction_audit_contains_before_and_after(self):
        self.store.respond(self.event_id, 10, "going", [1, 2, 3, 4], self.timestamp, 2)
        row = self.store.one("SELECT * FROM clan_audit WHERE action='correction'")
        self.assertEqual((row["actor_id"], row["subject_id"]), (2, 10))
        self.assertIn("before", row["detail"])

    def test_snapshot_idempotent(self):
        self.store.snapshot(self.event_id, {12: "Later"})
        self.assertEqual({r["user_id"] for r in self.store.recipients(self.event_id)}, {10, 11})

    def test_no_duplicate_delivery_claims(self):
        self.assertTrue(self.store.claim(self.event_id, 10))
        self.assertFalse(self.store.claim(self.event_id, 10))
        self.store.delivery(self.event_id, 10, "sent", 900)
        self.assertFalse(self.store.claim(self.event_id, 10))

    def test_restart_marks_inflight_uncertain_without_retry(self):
        self.store.claim(self.event_id, 10)
        reopened = Store(self.path)
        self.assertEqual(reopened.recipient(self.event_id, 10)["delivery"], "uncertain")
        self.assertFalse(reopened.claim(self.event_id, 10))

    def test_materialize_idempotent_including_cancelled_occurrences(self):
        schedule = self.store.schedule(100, "thursday")
        self.store.target(schedule["id"], "user", 10)
        self.store.edit_schedule(schedule["id"], "Shadow War", DEFAULT_BODY, True, 1)
        self.store.materialize(self.timestamp)
        events = self.store.rows("SELECT * FROM clan_events WHERE schedule_id=?", (schedule["id"],))
        self.store.cancel(events[0]["id"], 2)
        self.store.materialize(self.timestamp)
        self.assertEqual(
            len(
                self.store.rows("SELECT * FROM clan_events WHERE schedule_id=?", (schedule["id"],))
            ),
            len(events),
        )
        self.assertEqual(self.store.event(events[0]["id"])["state"], "cancelled")

    def test_schedule_requires_targets(self):
        schedule = self.store.schedule(100, "sunday")
        with self.assertRaises(ValueError):
            self.store.edit_schedule(schedule["id"], schedule["title"], DEFAULT_BODY, True, 1)

    def test_history_cleanup_keeps_latest_stats_and_other_events(self):
        self.store.respond(self.event_id, 10, "going", [1, 2, 3, 4], self.timestamp)
        self.store.cleanup(self.timestamp + 10000 + 91 * 86400)
        self.assertFalse(self.store.recipients(self.event_id))
        self.assertFalse(
            self.store.rows("SELECT * FROM clan_audit WHERE event_id=?", (self.event_id,))
        )
        self.assertEqual(self.store.last_stats(100, 10), (1, 2, 3, 4))

    def test_deleted_event_ids_never_reused_by_old_dm_buttons(self):
        with self.store.db() as conn:
            conn.execute("DELETE FROM clan_events")
        new_id = self.store.create_event(
            100,
            "New",
            DEFAULT_BODY,
            self.timestamp + 20000,
            self.timestamp,
            1,
            self.timestamp,
        )
        self.assertGreater(new_id, self.event_id)

    def test_legacy_tables_untouched(self):
        with self.store.db() as conn:
            conn.execute("CREATE TABLE events(message_id INTEGER PRIMARY KEY,title TEXT)")
            conn.execute("INSERT INTO events VALUES(1,'Original event')")
        Store(self.path)
        self.assertEqual(self.store.one("SELECT title FROM events")["title"], "Original event")

    def test_report_pagination_keeps_every_recipient_and_failure(self):
        extra = self.store.create_event(
            100,
            "Large",
            DEFAULT_BODY,
            self.timestamp + 5000,
            self.timestamp - 1,
            1,
            self.timestamp,
        )
        self.store.snapshot(extra, {uid: f"Player {uid}" for uid in range(1000, 1150)})
        self.store.delivery(extra, 1000, "failed", error="DM unavailable")
        pages = report_pages(
            self.store.event(extra), self.store.recipients(extra), [], self.timestamp
        )
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(page) <= 2000 for page in pages))
        combined = "".join(pages)
        for uid in range(1000, 1150):
            self.assertEqual(combined.count(f"<@{uid}>"), 1)
        self.assertIn("DM: failed", combined)

    def test_instance_lock_excludes_second_process(self):
        with instance_lock(self.path.with_suffix(".lock")):
            with self.assertRaises(RuntimeError):
                with instance_lock(self.path.with_suffix(".lock")):
                    pass


class DiscordTests(StoreFixture, unittest.IsolatedAsyncioTestCase):
    async def test_member_rsvp_lists_only_own_invitations(self):
        interaction = self.interaction(10)
        command = self.client.tree.get_command("rsvp")
        await command.callback(interaction)
        content = interaction.response.send_message.call_args.args[0]
        self.assertIn(f"#{self.event_id}", content)
        self.assertTrue(interaction.response.send_message.call_args.kwargs["ephemeral"])
        other = self.interaction(99)
        await command.callback(other)
        self.assertIn("No open invitations", other.response.send_message.call_args.args[0])

    async def test_expired_event_is_closed_without_sending(self):
        with self.store.db() as conn:
            conn.execute(
                "UPDATE clan_events SET starts_at=? WHERE id=?", (self.timestamp - 1, self.event_id)
            )
        with (
            patch.object(self.client, "dispatch_event", new=AsyncMock()) as dispatch,
            patch.object(self.client, "refresh_report", new=AsyncMock()),
            patch.object(self.client, "cleanup", new=AsyncMock()),
        ):
            await self.client.scheduler.coro(self.client)
        dispatch.assert_not_awaited()
        self.assertEqual(self.store.event(self.event_id)["state"], "closed")
        self.assertTrue(
            all(r["delivery"] == "expired" for r in self.store.recipients(self.event_id))
        )

    async def test_scheduler_catches_up_before_start(self):
        with (
            patch.object(self.client, "dispatch_event", new=AsyncMock()) as dispatch,
            patch.object(self.client, "refresh_report", new=AsyncMock()),
            patch.object(self.client, "cleanup", new=AsyncMock()),
        ):
            await self.client.scheduler.coro(self.client)
        dispatch.assert_awaited_once()

    async def test_new_response_during_report_keeps_dirty_flag(self):
        async def refresh(event):
            self.store.respond(event["id"], 10, "not_going", [], now_ts())

        with (
            patch.object(self.client, "dispatch_event", new=AsyncMock()),
            patch.object(self.client, "refresh_report", new=refresh),
            patch.object(self.client, "cleanup", new=AsyncMock()),
        ):
            await self.client.scheduler.coro(self.client)
        self.assertTrue(
            self.store.one("SELECT * FROM clan_dirty WHERE event_id=?", (self.event_id,))
        )

    async def test_exposed_channel_blocks_dms(self):
        with (
            patch.object(self.client, "get_guild", return_value=SimpleNamespace(id=100)),
            patch.object(
                self.client, "report_channel", new=AsyncMock(side_effect=PermissionError("Exposed"))
            ),
            patch.object(self.client, "fetch_user", new=AsyncMock()) as fetch,
        ):
            with self.assertRaises(PermissionError):
                await self.client.dispatch_event(self.store.event(self.event_id))
        fetch.assert_not_awaited()

    def setUp(self):
        super().setUp()
        self.client = ClanBot(self.store, 1, 100)

    async def asyncTearDown(self):
        await self.client.close()

    def interaction(self, user=10, guild=100):
        response = SimpleNamespace(
            send_modal=AsyncMock(),
            send_message=AsyncMock(),
            edit_message=AsyncMock(),
            is_done=lambda: False,
        )
        return SimpleNamespace(
            user=SimpleNamespace(id=user),
            guild_id=guild,
            response=response,
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_commands_register_and_serialize_without_network(self):
        expected = {
            "join-buddys",
            "members",
            "test-bot",
            "clan-setup",
            "management",
            "recipients",
            "recipient-preview",
            "schedule",
            "schedules",
            "events",
            "report",
            "rsvp",
            "correct",
            "cancel-event",
            "announce",
            "extra-event",
            "audit",
        }
        self.assertEqual({c.name for c in self.client.tree.get_commands()}, expected)
        for command in self.client.tree.get_commands():
            payload = command.to_dict(self.client.tree)
            self.assertLessEqual(len(payload["description"]), 100)

    async def test_nonmanagers_and_other_servers_rejected(self):
        for interaction in (self.interaction(10), self.interaction(2, 999)):
            with self.assertRaises(PermissionError):
                self.client.require_manager(interaction)
        with self.assertRaises(PermissionError):
            self.client.require_owner(self.interaction(2))

    async def test_going_opens_form_without_recording_response(self):
        interaction = self.interaction()
        view = RSVPView(self.client, self.event_id, 10)
        await view.going(interaction)
        modal = interaction.response.send_modal.call_args.args[0]
        self.assertEqual(len(modal.inputs), 4)
        self.assertEqual(self.store.recipient(self.event_id, 10)["status"], "awaiting")
        self.assertTrue(view.is_persistent())

    async def test_invitation_cannot_be_used_by_another_player(self):
        with self.assertRaises(PermissionError):
            await RSVPView(self.client, self.event_id, 10).going(self.interaction(11))

    async def test_form_persists_all_stats(self):
        modal = StatsModal(self.client, self.event_id, 10, [10, 20, 30, 40])
        await modal.on_submit(self.interaction())
        self.assertEqual(self.store.recipient(self.event_id, 10)["status"], "going")
        self.assertEqual(self.store.last_stats(100, 10), (10, 20, 30, 40))

    async def test_decline_does_not_open_form(self):
        interaction = self.interaction()
        await RSVPView(self.client, self.event_id, 10).not_going(interaction)
        interaction.response.send_modal.assert_not_called()
        self.assertEqual(self.store.recipient(self.event_id, 10)["status"], "not_going")

    async def test_revoked_manager_cannot_submit_open_correction(self):
        modal = StatsModal(self.client, self.event_id, 10, [1, 2, 3, 4], manager_id=2)
        self.store.set_managers(100, 1, 1, 7, [3, 4, 5, 6])
        with self.assertRaises(PermissionError):
            await modal.on_submit(self.interaction(2))

    async def test_invalid_form_offers_retry_without_saving(self):
        interaction = self.interaction()
        modal = StatsModal(self.client, self.event_id, 10, ["abc", 2, 3, 4])
        await modal.on_submit(interaction)
        self.assertEqual(self.store.recipient(self.event_id, 10)["status"], "awaiting")
        self.assertIn("view", interaction.response.send_message.call_args.kwargs)

    async def test_current_roles_and_individuals_deduplicated(self):
        schedule = self.store.schedule(100, "sunday")
        self.store.target(schedule["id"], "role", 50)
        self.store.target(schedule["id"], "user", 10)

        async def members(limit=None):
            for uid, roles, bot in [
                (10, [50], False),
                (11, [50], False),
                (12, [], False),
                (13, [50], True),
            ]:
                yield SimpleNamespace(
                    id=uid,
                    roles=[SimpleNamespace(id=r) for r in roles],
                    bot=bot,
                    display_name=str(uid),
                )

        guild = SimpleNamespace(id=100, fetch_members=members)
        self.assertEqual(set(await self.client.resolve_targets(guild, schedule["id"])), {10, 11})

    async def test_repeated_dispatch_does_not_resend(self):
        guild = SimpleNamespace(id=100)
        user = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=900)))
        with (
            patch.object(self.client, "get_guild", return_value=guild),
            patch.object(self.client, "report_channel", new=AsyncMock()),
            patch.object(self.client, "fetch_user", new=AsyncMock(return_value=user)),
            patch("bot.asyncio.sleep", new=AsyncMock()),
        ):
            await self.client.dispatch_event(self.store.event(self.event_id))
            await self.client.dispatch_event(self.store.event(self.event_id))
        self.assertEqual(user.send.await_count, 2)
        self.assertTrue(all(r["delivery"] == "sent" for r in self.store.recipients(self.event_id)))

    async def test_failed_dm_is_observable_without_retry(self):
        user = SimpleNamespace(
            send=AsyncMock(
                side_effect=discord.Forbidden(
                    SimpleNamespace(status=403, reason="Forbidden"), "Cannot DM"
                )
            )
        )
        with (
            patch.object(self.client, "get_guild", return_value=SimpleNamespace(id=100)),
            patch.object(self.client, "report_channel", new=AsyncMock()),
            patch.object(self.client, "fetch_user", new=AsyncMock(return_value=user)),
            patch("bot.asyncio.sleep", new=AsyncMock()),
        ):
            await self.client.dispatch_event(self.store.event(self.event_id))
            await self.client.dispatch_event(self.store.event(self.event_id))
        self.assertEqual(user.send.await_count, 2)
        self.assertTrue(
            all(r["delivery"] == "failed" for r in self.store.recipients(self.event_id))
        )

    async def test_uncertain_network_send_is_not_retried(self):
        user = SimpleNamespace(send=AsyncMock(side_effect=TimeoutError()))
        with (
            patch.object(self.client, "get_guild", return_value=SimpleNamespace(id=100)),
            patch.object(self.client, "report_channel", new=AsyncMock()),
            patch.object(self.client, "fetch_user", new=AsyncMock(return_value=user)),
            patch("bot.asyncio.sleep", new=AsyncMock()),
        ):
            await self.client.dispatch_event(self.store.event(self.event_id))
            await self.client.dispatch_event(self.store.event(self.event_id))
        self.assertEqual(user.send.await_count, 2)
        self.assertEqual(self.store.recipient(self.event_id, 10)["delivery"], "uncertain")

    async def test_cancel_notice_sent_only_once_to_delivered_players(self):
        self.store.delivery(self.event_id, 10, "sent", 900)
        self.store.delivery(self.event_id, 11, "failed", error="DM blocked")
        self.store.cancel(self.event_id, 2)
        user = SimpleNamespace(send=AsyncMock())
        with (
            patch.object(self.client, "fetch_user", new=AsyncMock(return_value=user)),
            patch("bot.asyncio.sleep", new=AsyncMock()),
        ):
            await self.client.send_cancellations(self.store.event(self.event_id))
            await self.client.send_cancellations(self.store.event(self.event_id))
        user.send.assert_awaited_once()

    async def test_manager_preview_bound_to_creator_and_revocation(self):
        view = ConfirmView(self.client, 2, AsyncMock())
        with self.assertRaises(PermissionError):
            await view.interaction_check(self.interaction(3))
        self.store.set_managers(100, 1, 1, 7, [3, 4, 5, 6])
        with self.assertRaises(PermissionError):
            await view.interaction_check(self.interaction(2))

    async def test_public_report_channel_rejected(self):
        channel = SimpleNamespace(
            guild=SimpleNamespace(default_role=object()),
            overwrites_for=lambda role: discord.PermissionOverwrite(view_channel=True),
            overwrites={},
        )
        with self.assertRaises(PermissionError):
            check_private(channel, {1, 2, 3, 4, 5, 6})


if __name__ == "__main__":
    unittest.main()
