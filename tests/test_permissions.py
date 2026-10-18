import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from bot import ClanBot, require_channel_permission_management
from clan import Store, now_ts


class ChannelPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "guild.db")
        self.store.configure(100, 200, now_ts())
        self.client = ClanBot(self.store, 1, 100)
        self.owner = MagicMock(id=1, bot=False)
        self.bot_member = MagicMock(id=10, bot=True)
        self.guild = SimpleNamespace(
            id=100,
            me=self.bot_member,
            default_role=MagicMock(id=100),
            fetch_member=AsyncMock(return_value=self.owner),
            fetch_channel=AsyncMock(),
        )
        self.channel = MagicMock(spec=discord.TextChannel)
        self.channel.id = 200
        self.channel.name = "clan-management"
        self.channel.guild = self.guild
        self.channel.permissions_for.return_value = discord.Permissions(manage_roles=True)
        self.channel.edit = AsyncMock()
        self.channel.send = AsyncMock()
        self.guild.fetch_channel.return_value = self.channel
        self.interaction = SimpleNamespace(
            user=self.owner,
            guild_id=100,
            guild=self.guild,
            response=SimpleNamespace(defer=AsyncMock(), is_done=lambda: True),
            followup=SimpleNamespace(send=AsyncMock()),
        )

    async def asyncTearDown(self):
        await self.client.close()
        self.temp.cleanup()

    async def test_repeated_setup_preserves_channel_permission_and_privacy(self):
        command = self.client.tree.get_command("clan-setup")
        for _ in range(2):
            await command.callback(self.interaction)
            overwrites = self.channel.edit.call_args.kwargs["overwrites"]
            self.assertTrue(overwrites[self.bot_member].manage_roles)
            self.assertFalse(overwrites[self.guild.default_role].view_channel)
            self.assertIsNone(overwrites[self.owner].manage_roles)

    async def test_management_keeps_permission_only_for_bot(self):
        members = [MagicMock(id=number, bot=False) for number in range(2, 7)]
        people = {member.id: member for member in [self.owner, *members]}
        self.guild.fetch_member.side_effect = lambda uid: people[uid]
        await self.client.tree.get_command("management").callback(self.interaction, *members)
        overwrites = self.channel.edit.call_args.kwargs["overwrites"]
        self.assertTrue(overwrites[self.bot_member].manage_roles)
        for member in [self.owner, *members]:
            self.assertIsNone(overwrites[member].manage_roles)
        self.assertFalse(overwrites[self.guild.default_role].view_channel)

    async def test_missing_permission_gives_actionable_error_before_edit(self):
        self.channel.permissions_for.return_value = discord.Permissions(manage_channels=True)
        with self.assertRaisesRegex(PermissionError, "Enable Manage Permissions"):
            await self.client.tree.get_command("clan-setup").callback(self.interaction)
        self.channel.edit.assert_not_awaited()
        self.channel.send.assert_not_awaited()
        with self.assertRaises(PermissionError):
            require_channel_permission_management(self.channel)

    async def test_partial_management_saves_and_preserves_omitted_positions(self):
        leader = MagicMock(id=2, bot=False)
        officer = MagicMock(id=3, bot=False)
        people = {1: self.owner, 2: leader, 3: officer}
        self.guild.fetch_member.side_effect = lambda uid: people[uid]
        command = self.client.tree.get_command("management")
        self.assertTrue(all(not p.required for p in command.parameters))
        await command.callback(self.interaction, leader=leader, officer1=self.owner)
        self.assertEqual(
            self.store.managers(100),
            [{"slot": "leader", "user_id": 2}, {"slot": "owner", "user_id": 1}],
        )
        await command.callback(self.interaction, officer3=officer)
        self.assertTrue(self.store.is_manager(100, 2, 1))
        self.assertTrue(self.store.is_manager(100, 3, 1))
        await command.callback(self.interaction, clear="officer3")
        self.assertFalse(self.store.is_manager(100, 3, 1))
        self.assertNotIn(officer, self.channel.edit.call_args.kwargs["overwrites"])

    async def test_blank_management_is_valid_with_only_owner(self):
        await self.client.tree.get_command("management").callback(self.interaction)
        self.assertEqual(self.store.managers(100), [{"slot": "owner", "user_id": 1}])
