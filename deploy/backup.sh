#!/usr/bin/env bash
# Dated snapshot of guild.db. Uses SQLite's online backup so it is safe to run
# while the bot is writing. Keeps the 14 most recent.
set -euo pipefail

DEST=/opt/guild-bot/backups
mkdir -p "$DEST"
STAMP=$(date -u +%Y%m%d-%H%M%S)

/opt/guild-bot/venv/bin/python - "$DEST/guild-$STAMP.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect("/opt/guild-bot/guild.db")
dst = sqlite3.connect(sys.argv[1])
with dst:
    src.backup(dst)
dst.close(); src.close()
PY

ls -1t "$DEST"/guild-*.db | tail -n +15 | xargs -r rm -f
