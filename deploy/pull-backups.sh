#!/usr/bin/env bash
# Copy database snapshots from the server down to this PC.
# Run it whenever; it is the only thing that puts a copy outside Oracle.
set -euo pipefail

HOST=opc@150.136.46.233
DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups-local"

mkdir -p "$DEST"
scp -q "$HOST:/opt/guild-bot/backups/*.db" "$DEST"/
echo "local snapshots now in $DEST:"
ls -1t "$DEST" | head -5
