import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import ClanBot, RSVPView, TestCorrectionModal, TestLauncher, TestPanel
from clan import Store


class PanelTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "live.db")
        self.store.set_managers(100, 1, 1, 2, [3, 4, 5, 6])
        self.client = ClanBot(self.store, 1, 100)

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    def interaction(self, uid=1, guild=None):
        return SimpleNamespace(
            user=SimpleNamespace(id=uid, display_name="Tester"),
            guild_id=guild,
            response=SimpleNamespace(
                send_message=AsyncMock(),
                send_modal=AsyncMock(),
                defer=AsyncMock(),
                is_done=lambda: False,
            ),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_launcher_persistent_and_rejects_nonmanager(self):
        view = TestLauncher(self.client)
        self.assertTrue(view.is_persistent())
        with self.assertRaises(PermissionError):
            await view.open_panel.callback(self.interaction(99))

    async def test_panel_rejects_other_manager_and_revoked_manager(self):
        panel = TestPanel(self.client, 2)
        with self.assertRaises(PermissionError):
            await panel.interaction_check(self.interaction(3))
        self.store.set_managers(100, 1, 1, 7, [3, 4, 5, 6])
        with self.assertRaises(PermissionError):
            await panel.interaction_check(self.interaction(2))

    async def test_test_event_only_sends_to_tester_and_preserves_live_stats(self):
        user = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=500)))
        with (
            patch.object(self.client, "fetch_user", new=AsyncMock(return_value=user)) as fetch,
            patch("bot.asyncio.sleep", new=AsyncMock()),
        ):
            session = self.client.test_session(1)
            await session.send_event("Tester")
        fetch.assert_awaited_once_with(1)
        self.assertEqual(self.store.rows("SELECT * FROM clan_events"), [])
        self.assertEqual(self.store.last_stats(100, 1), ("", "", "", ""))
        event = session.latest_event()
        self.assertEqual([r["user_id"] for r in session.store.recipients(event["id"])], [1])
        modal = TestCorrectionModal(session, event["id"], 1, [10, 20, 30, 40])
        await modal.on_submit(self.interaction())
        self.assertEqual(session.store.last_stats(100, 1), (10, 20, 30, 40))
        self.assertEqual(self.store.last_stats(100, 1), ("", "", "", ""))
        self.assertEqual(
            session.store.one("SELECT * FROM clan_audit WHERE action='correction'")["actor_id"], 1
        )

    async def test_test_buttons_cannot_collide_with_real_event_buttons(self):
        live = RSVPView(self.client, 1, 1)
        test = RSVPView(self.client.test_session(1), 1, 1)
        self.assertFalse(
            {b.custom_id for b in live.children} & {b.custom_id for b in test.children}
        )

    async def test_test_announcement_only_to_tester(self):
        user = SimpleNamespace(send=AsyncMock())
        panel = TestPanel(self.client, 1)
        with patch.object(self.client, "fetch_user", new=AsyncMock(return_value=user)) as fetch:
            await panel.announcement.callback(self.interaction())
        fetch.assert_awaited_once_with(1)
        user.send.assert_awaited_once()
        self.assertNotIn("view", user.send.call_args.kwargs)

    async def test_test_list_private_and_has_all_stats(self):
        panel = TestPanel(self.client, 1)
        timestamp = __import__("time").time()
        event_id = panel.session.store.create_event(
            100, "[TEST]", "test", int(timestamp) + 3600, int(timestamp) - 1, 1, int(timestamp)
        )
        panel.session.store.snapshot(event_id, {1: "Tester"})
        panel.session.store.respond(event_id, 1, "going", [1, 2, 3, 4], int(timestamp))
        interaction = self.interaction()
        await panel.test_list.callback(interaction)
        content = interaction.response.send_message.call_args.args[0]
        self.assertIn("1 / 2 / 3 / 4", content)
        self.assertTrue(interaction.response.send_message.call_args.kwargs["ephemeral"])

    async def test_calendar_preview_never_sends_messages(self):
        panel = TestPanel(self.client, 1)
        interaction = self.interaction()
        with patch.object(self.client, "fetch_user", new=AsyncMock()) as fetch:
            await panel.calendar.callback(interaction)
        fetch.assert_not_awaited()
        content = interaction.response.send_message.call_args.args[0]
        self.assertIn("Shadow War", content)
        self.assertIn("Rite of Exile / Vigil of Blades", content)

    async def test_cancellation_only_affects_isolated_event(self):
        user = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=500)))
        with (
            patch.object(self.client, "fetch_user", new=AsyncMock(return_value=user)),
            patch("bot.asyncio.sleep", new=AsyncMock()),
        ):
            panel = TestPanel(self.client, 1)
            await panel.session.send_event("Tester")
            await panel.cancel.callback(self.interaction())
        self.assertEqual(user.send.await_count, 2)
        self.assertEqual(panel.session.latest_event()["state"], "cancelled")
        self.assertEqual(self.store.rows("SELECT * FROM clan_events"), [])
