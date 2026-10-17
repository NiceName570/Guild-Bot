import tempfile
import unittest
from pathlib import Path

from dotenv import dotenv_values

from configure_discord import save_config, validate


class ConfigureTests(unittest.TestCase):
    def values(self):
        return {
            "BOT_OWNER_ID": "123456789012345678",
            "DISCORD_APPLICATION_ID": "223456789012345678",
            "DISCORD_PUBLIC_KEY": "a" * 64,
            "DISCORD_TOKEN": "EXAMPLE_ONLY_NOT_A_REAL_TOKEN_12345",
            "CLAN_GUILD_ID": "",
        }

    def test_validation(self):
        for key, bad in (
            ("BOT_OWNER_ID", "abc"),
            ("DISCORD_APPLICATION_ID", "123"),
            ("DISCORD_PUBLIC_KEY", "not-a-key"),
            ("DISCORD_TOKEN", "Bot secret"),
        ):
            values = self.values()
            values[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(values)

    def test_private_save_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("CLAN_GUILD_ID=323456789012345678\nEXTRA='keep me'\n")
            save_config(path, self.values())
            result = dotenv_values(path)
            self.assertEqual(result["CLAN_GUILD_ID"], "323456789012345678")
            self.assertEqual(result["EXTRA"], "keep me")
            self.assertEqual(result["DISCORD_TOKEN"], self.values()["DISCORD_TOKEN"])
            self.assertEqual(result["AWS_REGION"], "us-east-2")
            self.assertFalse(list(Path(directory).glob(".discord-config-*")))

    def test_failed_validation_does_not_replace_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            original = "EXTRA=keep\n"
            path.write_text(original)
            values = self.values()
            values["DISCORD_TOKEN"] = "invalid"
            with self.assertRaises(ValueError):
                save_config(path, values)
            self.assertEqual(path.read_text(), original)
