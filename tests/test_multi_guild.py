import datetime as dt
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from bot import ClanBot, MemberNameModal, OnboardingView, RSVPView, TestLauncher
from clan import Store


class MultiGuildTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "guild.db")
        self.client = ClanBot(self.store, 1, 100, multi_guild=True)
        self.store.configure(100, 200, 1)
        self.store.configure(999, 300, 1)
        self.other = self.client.guild_context(999)

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    def interaction(self, guild=999, user=1):
        return SimpleNamespace(
            guild_id=guild,
            user=SimpleNamespace(id=user, bot=False, display_name="Tester"),
            response=SimpleNamespace(send_message=AsyncMock(), is_done=lambda: False),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def test_owner_can_manage_new_server_without_granting_strangers_control(self):
        self.other.require_owner(self.interaction())
        with self.assertRaises(PermissionError):
            self.other.require_owner(self.interaction(user=2))
        with self.assertRaises(PermissionError):
            self.other.require_manager(self.interaction(guild=100))
        with self.assertRaises(PermissionError):
            self.other.require_manager(self.interaction(guild=None))

    async def test_global_router_uses_server_bound_callback_and_keeps_primary(self):
        for guild in (100, 999):
            interaction = self.interaction(guild=guild)
            await self.client.tree.get_command("schedules").callback(interaction)
            self.assertIn("Shadow War", interaction.response.send_message.call_args.args[0])
        callback = self.other.tree.get_command("schedules")
        self.assertTrue(callback.guild_only)

    async def test_manager_assignments_do_not_leak_to_other_servers(self):
        self.store.set_managers(100, 1, 1, 2, [3, 4, 5, 6])
        with self.assertRaises(PermissionError):
            await self.client.tree.get_command("members").callback(self.interaction(user=2))
        self.store.set_managers(999, 1, 1, 7, [8, 9, 10, 11])
        with self.assertRaises(PermissionError):
            self.client.require_manager(self.interaction(guild=100, user=7))

    async def test_signup_is_pinned_to_selected_server_across_dm_form(self):
        interaction = self.interaction(user=10)
        await self.client.tree.get_command("join-buddys").callback(interaction)
        view = interaction.response.send_message.call_args.kwargs["view"]
        self.assertIsInstance(view, OnboardingView)
        self.assertEqual(view.client.guild_id, 999)
        self.assertIsNone(self.store.welcome(100, 10))
        modal = MemberNameModal(view.client, 10, view.nonce)
        self.assertEqual(modal.client.guild_id, 999)
        self.assertTrue(all(":999:" in item.custom_id for item in view.children))

    async def test_test_stores_and_component_ids_are_isolated_for_same_tester(self):
        primary = self.client.test_session(1)
        other = self.other.test_session(1)
        self.assertNotEqual(primary.store.path, other.store.path)
        self.assertNotEqual(
            RSVPView(primary, 1, 1).children[0].custom_id,
            RSVPView(other, 1, 1).children[0].custom_id,
        )
        self.assertTrue(RSVPView(primary, 1, 1).children[0].custom_id.startswith("test1:"))

    async def test_generic_launcher_uses_channel_server(self):
        interaction = self.interaction()
        await TestLauncher(self.client).open_panel.callback(interaction)
        panel = interaction.response.send_message.call_args.kwargs["view"]
        self.assertEqual(panel.client.guild_id, 999)

    async def test_new_joins_only_welcomed_after_server_setup(self):
        member = SimpleNamespace(
            id=10, bot=False, guild=SimpleNamespace(id=999), joined_at=dt.datetime.now(dt.UTC)
        )
        sender = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=500)))
        with patch.object(self.client, "fetch_user", new=AsyncMock(return_value=sender)):
            await self.client.on_member_join(member)
            self.assertEqual(self.store.welcome(999, 10)["delivery"], "sent")
            self.assertIsNone(self.store.welcome(100, 10))
            member.guild.id = 555
            await self.client.on_member_join(member)
        sender.send.assert_awaited_once()

    async def test_new_server_syncs_and_removal_pauses_only_its_schedules(self):
        with self.store.db() as conn:
            conn.execute("UPDATE clan_schedules SET enabled=1")
        with patch.object(self.client, "sync_server", new=AsyncMock()) as sync:
            await self.client.on_guild_join(SimpleNamespace(id=999))
        sync.assert_awaited_once_with(999)
        await self.client.on_guild_remove(SimpleNamespace(id=999))
        self.assertFalse(self.store.schedule(999, "thursday")["enabled"])
        self.assertTrue(self.store.schedule(100, "thursday")["enabled"])

    async def test_startup_restores_server_bound_welcome_and_test_buttons(self):
        self.store.prepare_welcome(999, 10, "joined")
        session = self.other.test_session(1)
        session.store.prepare_welcome(999, 1, "test-joined")
        with (
            patch.object(self.client.tree, "sync", new=AsyncMock()) as sync,
            patch.object(self.client.scheduler, "start"),
            patch.object(self.client, "add_view") as add_view,
        ):
            await self.client.setup_hook()
        self.assertEqual(sync.await_count, 2)
        views = [call.args[0] for call in add_view.call_args_list]
        restored = [view for view in views if isinstance(view, OnboardingView)]
        self.assertEqual(len(restored), 2)
        self.assertTrue(all(view.client.guild_id == 999 for view in restored))

    async def test_rsvp_cannot_open_event_from_another_server(self):
        event = self.store.create_event(100, "Private event", "Private", 9999999999, 1, 1, 1)
        self.store.snapshot(event, {10: "Player"})
        with self.assertRaises(ValueError):
            await self.client.tree.get_command("rsvp").callback(
                self.interaction(user=10), event_id=event
            )
