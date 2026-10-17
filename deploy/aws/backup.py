"""Online SQLite backup. Run as clanbot, or against a private downloaded database."""

import argparse
import datetime as dt
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def backup(source, destination, keep=14):
    source = Path(source).resolve(strict=True)
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S-%f")
    target = destination / f"guild-{stamp}.db"
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with (
        closing(sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)) as src,
        closing(sqlite3.connect(target)) as dst,
    ):
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup integrity check failed; older backups retained.")
    for old in sorted(destination.glob("guild-*.db"), reverse=True)[keep:]:
        old.unlink()
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="/opt/guild-bot/guild.db")
    parser.add_argument("--destination", default="/opt/guild-bot/backups")
    args = parser.parse_args()
    print(backup(args.source, args.destination))
