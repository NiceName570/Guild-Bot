"""Build a private deployment archive; no AWS credentials or network calls needed."""

import hashlib
import io
import json
import sqlite3
import tarfile
import tempfile
import time
from contextlib import closing
from pathlib import Path

from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parents[2]
    import sys

    sys.path.insert(0, str(root))
    from configure_discord import restrict_file

    values = dotenv_values(root / ".env")
    keys = (
        "DISCORD_TOKEN",
        "BOT_OWNER_ID",
        "CLAN_GUILD_ID",
        "DISCORD_APPLICATION_ID",
        "DISCORD_PUBLIC_KEY",
    )
    if not all(values.get(key) for key in keys):
        raise RuntimeError("Private Discord configuration is incomplete.")
    destination = root / ".git" / "aws-deployment"
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / f"clanbot-package-{time.time_ns()}.tar.gz"
    archive_path.touch(exist_ok=False)
    restrict_file(archive_path)
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        stage = Path(temporary)
        database_source = Path(values.get("CLAN_DB_PATH") or root / "guild.db")

        def snapshot(source, target):
            with (
                closing(sqlite3.connect(f"{source.resolve().as_uri()}?mode=ro", uri=True)) as src,
                closing(sqlite3.connect(target)) as dst,
            ):
                src.backup(dst)
                if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("Database snapshot integrity check failed.")

        snapshot(database_source, stage / "guild.db")
        tests = root / "test-data"
        if tests.exists():
            (stage / "test-data").mkdir()
            for source in tests.glob("*.db"):
                snapshot(source, stage / "test-data" / source.name)
        content = "".join(f"{key}='{values[key]}'\n" for key in keys)
        content += "AWS_REGION='us-east-2'\nCLAN_DB_PATH='/opt/guild-bot/guild.db'\n"
        files = [
            "bot.py",
            "clan.py",
            "instance_lock.py",
            "requirements-frozen.txt",
            "deploy/aws/setup.sh",
            "deploy/aws/backup.py",
            "deploy/aws/cloud_backup.py",
            "deploy/aws/requirements.txt",
            "deploy/aws/guild-bot.service",
            "deploy/aws/guild-bot-backup.service",
            "deploy/aws/guild-bot-backup.timer",
        ]
        with tarfile.open(archive_path, "w:gz") as archive:
            for name in files:
                archive.add(root / name, arcname=name)
            archive.add(stage / "guild.db", arcname="guild.db")
            if (stage / "test-data").exists():
                archive.add(stage / "test-data", arcname="test-data")
            data = content.encode()
            info = tarfile.TarInfo(".env")
            info.size, info.mode = len(data), 0o600
            archive.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    metadata = {"path": str(archive_path), "sha256": digest, "bytes": archive_path.stat().st_size}
    (destination / "bundle.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
