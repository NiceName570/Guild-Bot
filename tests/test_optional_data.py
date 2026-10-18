import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import ClanBot, MemberNameModal, ScheduleModal, StatsModal
from clan import Store, now_ts, report_pages, validate_stats


class OptionalDataTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "guild.db"
        self.store = Store(self.path)
        self.store.configure(100, 200, now_ts())
        self.client = ClanBot(self.store, 1, 100)
        self.timestamp = now_ts()
        self.event_id = self.store.create_event(
            100, "Test", "Message", self.timestamp + 3600, self.timestamp, 1, self.timestamp
        )
        self.store.snapshot(self.event_id, {10: "Player"})

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    def interaction(self, user=10):
        return SimpleNamespace(
            user=SimpleNamespace(id=user),
            guild_id=100,
            response=SimpleNamespace(
                is_done=lambda: False,
                send_message=AsyncMock(),
                send_modal=AsyncMock(),
                defer=AsyncMock(),
            ),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_all_blank_stats_save_going_and_render_unknown(self):
        modal = StatsModal(self.client, self.event_id, 10, [""] * 4)
        self.assertTrue(all(not field.required for field in modal.inputs))
        await modal.on_submit(self.interaction())
        row = self.store.recipient(self.event_id, 10)
        self.assertEqual(row["status"], "going")
        self.assertIsNone(row["armor"])
        text = report_pages(self.store.event(self.event_id), [row], [], self.timestamp)[0]
        self.assertIn("— / — / — / —", text)
        self.assertNotIn("None", text)

    async def test_partial_stats_retain_prior_known_prefill_without_inventing_values(self):
        self.store.respond(self.event_id, 10, "going", [1, 2, 3, 4], self.timestamp)
        self.store.respond(self.event_id, 10, "going", ["", "9", "", ""], self.timestamp)
        self.assertEqual(self.store.last_stats(100, 10), (1, 9, 3, 4))
        self.assertIsNone(self.store.recipient(self.event_id, 10)["armor"])
        self.assertEqual(Store(self.path).last_stats(100, 10), (1, 9, 3, 4))

    async def test_legacy_stats_are_preserved_by_additive_migration(self):
        with self.store.db() as conn:
            conn.execute("INSERT INTO clan_stats VALUES(100,20,1,2,3,4,?)", (self.timestamp,))
        reopened = Store(self.path)
        self.assertEqual(reopened.last_stats(100, 20), (1, 2, 3, 4))
        self.assertEqual(validate_stats(["", "  ", None, "0"]), (None, None, None, 0))

    async def test_schedule_accepts_empty_text_and_no_officers_or_recipients(self):
        schedule = self.store.schedule(100, "thursday")
        modal = ScheduleModal(self.client, schedule, True)
        modal.name_input._value = ""
        modal.body_input._value = ""
        self.assertFalse(modal.name_input.required)
        self.assertFalse(modal.body_input.required)
        interaction = self.interaction(user=1)
        await modal.on_submit(interaction)
        view = interaction.response.send_message.call_args.kwargs["view"]
        await view.action(interaction)
        saved = self.store.schedule(100, "thursday")
        self.assertTrue(saved["enabled"])
        self.assertEqual(saved["title"], schedule["title"])
        self.assertEqual(saved["body"], schedule["body"])

    async def test_blank_signup_uses_discord_name(self):
        self.store.prepare_welcome(100, 10, "joined")
        row = self.store.welcome(100, 10)
        modal = MemberNameModal(self.client, 10, row["nonce"])
        self.assertFalse(modal.name_input.required)
        modal.name_input._value = ""
        member = SimpleNamespace(id=10, bot=False, display_name="Discord name")
        guild = SimpleNamespace(fetch_member=AsyncMock(return_value=member))
        with patch.object(self.client, "get_guild", return_value=guild):
            await modal.on_submit(self.interaction())
        self.assertEqual(self.store.registered_members(100)[0]["game_name"], "Discord name")
