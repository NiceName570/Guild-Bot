import datetime as dt
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord

from bot import ClanBot, MemberNameModal, OnboardingView, TestPanel, send_welcome
from clan import Store


class OnboardingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "live.db")
        self.client = ClanBot(self.store, 1, 100)
        self.member = SimpleNamespace(
            id=10,
            bot=False,
            guild=SimpleNamespace(id=100),
            display_name="Discord nickname",
            joined_at=dt.datetime.now(dt.UTC),
            roles=[],
        )

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    def interaction(self, user=10):
        return SimpleNamespace(
            user=SimpleNamespace(id=user),
            guild_id=None,
            response=SimpleNamespace(
                send_modal=AsyncMock(),
                send_message=AsyncMock(),
                defer=AsyncMock(),
                is_done=lambda: True,
            ),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    def welcome(self):
        self.store.prepare_welcome(100, 10, "join1")
        return self.store.welcome(100, 10)

    async def test_join_sends_one_welcome_even_if_event_repeated(self):
        sender = SimpleNamespace(send=AsyncMock(return_value=SimpleNamespace(id=500)))
        with patch.object(self.client, "fetch_user", new=AsyncMock(return_value=sender)):
            await self.client.on_member_join(self.member)
            await self.client.on_member_join(self.member)
        sender.send.assert_awaited_once()
        self.assertEqual(self.store.welcome(100, 10)["delivery"], "sent")
        self.assertFalse(self.store.registered_members(100))

    async def test_other_server_and_bots_not_welcomed(self):
        with patch.object(self.client, "fetch_user", new=AsyncMock()) as fetch:
            self.member.guild.id = 999
            await self.client.on_member_join(self.member)
            self.member.guild.id = 100
            self.member.bot = True
            await self.client.on_member_join(self.member)
        fetch.assert_not_awaited()

    async def test_yes_opens_form_without_enrolling_until_submitted(self):
        row = self.welcome()
        view = OnboardingView(self.client, 10, row["nonce"])
        interaction = self.interaction()
        await view.yes(interaction)
        interaction.response.send_modal.assert_awaited_once()
        self.assertFalse(self.store.registered_members(100))
        self.assertTrue(view.is_persistent())

    async def test_name_submission_enrolls_and_adds_future_targets_without_role(self):
        row = self.welcome()
        modal = MemberNameModal(self.client, 10, row["nonce"])
        modal.name_input._value = "GameHero"
        guild = SimpleNamespace(id=100, fetch_member=AsyncMock(return_value=self.member))

        async def members(limit=None):
            yield self.member
            yield SimpleNamespace(id=99, bot=False, roles=[], display_name="Unregistered")

        guild.fetch_members = members
        with patch.object(self.client, "get_guild", return_value=guild):
            await modal.on_submit(self.interaction())
        self.store.configure(100, 200, 1)
        recipients = await self.client.resolve_targets(
            guild, self.store.schedule(100, "thursday")["id"]
        )
        self.assertEqual(recipients, {10: "GameHero (Discord nickname)"})
        self.assertFalse(self.store.rows("SELECT * FROM clan_recipients"))
        self.assertFalse(self.store.managers(100))

    async def test_no_does_not_enroll_and_removes_existing_auto_registration(self):
        row = self.welcome()
        self.store.register_member(100, 10, row["nonce"], "Hero")
        await OnboardingView(self.client, 10, row["nonce"]).no(self.interaction())
        self.assertFalse(self.store.registered_members(100))
        self.assertEqual(self.store.welcome(100, 10)["state"], "not_member")

    async def test_confirmed_members_allow_schedule_without_manual_role_selection(self):
        row = self.welcome()
        self.store.register_member(100, 10, row["nonce"], "Hero")
        self.store.configure(100, 200, 1)
        schedule = self.store.schedule(100, "thursday")
        self.store.edit_schedule(schedule["id"], schedule["title"], schedule["body"], True, 1)
        self.assertEqual(self.store.schedule(100, "thursday")["enabled"], 1)

    async def test_restart_during_welcome_is_uncertain_and_not_resent(self):
        row = self.welcome()
        self.store.welcome_delivery(100, 10, row["nonce"], "sending")
        reopened = Store(self.store.path)
        self.assertEqual(reopened.welcome(100, 10)["delivery"], "uncertain")
        self.assertFalse(reopened.prepare_welcome(100, 10, "join1"))

    async def test_cannot_answer_for_someone_else(self):
        row = self.welcome()
        with self.assertRaises(PermissionError):
            await OnboardingView(self.client, 10, row["nonce"]).yes(self.interaction(11))

    async def test_left_member_deactivated_and_old_forms_rejected(self):
        row = self.welcome()
        self.store.register_member(100, 10, row["nonce"], "Hero")
        await self.client.on_member_remove(self.member)
        self.assertFalse(self.store.registered_members(100))
        with self.assertRaises(ValueError):
            self.store.register_member(100, 10, row["nonce"], "Hero")

    async def test_rejoin_requires_new_confirmation_and_rejects_old_nonce(self):
        old = self.welcome()
        self.store.register_member(100, 10, old["nonce"], "Hero")
        self.store.prepare_welcome(100, 10, "join2")
        self.assertFalse(self.store.registered_members(100))
        with self.assertRaises(ValueError):
            self.store.register_member(100, 10, old["nonce"], "Hero")
        self.assertNotEqual(self.store.welcome(100, 10)["nonce"], old["nonce"])

    async def test_invalid_game_names_do_not_enroll(self):
        row = self.welcome()
        for name in ("   ", "x" * 33, "hi\nthere", "@everyone", "<@123>"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.store.register_member(100, 10, row["nonce"], name)

    async def test_failed_welcome_is_recorded_and_not_retried(self):
        sender = SimpleNamespace(
            send=AsyncMock(
                side_effect=discord.Forbidden(
                    SimpleNamespace(status=403, reason="Forbidden"), "Blocked DM"
                )
            )
        )
        with patch.object(self.client, "fetch_user", new=AsyncMock(return_value=sender)):
            await send_welcome(self.client, self.member)
            await send_welcome(self.client, self.member)
        sender.send.assert_awaited_once()
        self.assertEqual(self.store.welcome(100, 10)["delivery"], "failed")

    async def test_missing_server_member_cannot_submit_signup(self):
        row = self.welcome()
        modal = MemberNameModal(self.client, 10, row["nonce"])
        modal.name_input._value = "Hero"
        guild = SimpleNamespace(
            fetch_member=AsyncMock(
                side_effect=discord.NotFound(
                    SimpleNamespace(status=404, reason="Not found"), "Not found"
                )
            )
        )
        with (
            patch.object(self.client, "get_guild", return_value=guild),
            self.assertRaises(ValueError),
        ):
            await modal.on_submit(self.interaction())
        self.assertFalse(self.store.registered_members(100))

    async def test_test_panel_signup_is_isolated(self):
        sender = SimpleNamespace(
            id=1, bot=False, send=AsyncMock(return_value=SimpleNamespace(id=500))
        )
        with patch.object(self.client, "fetch_user", new=AsyncMock(return_value=sender)):
            panel = TestPanel(self.client, 1)
            await panel.onboarding.callback(self.interaction(1))
        self.assertIsNone(self.store.welcome(100, 1))
        self.assertEqual(panel.session.store.welcome(100, 1)["delivery"], "sent")
        self.assertFalse(self.store.registered_members(100))
