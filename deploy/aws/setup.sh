#!/usr/bin/env bash
# Run ONLY on the chosen EC2 Ubuntu 24.04+ host, after AWS Free preflight passes.
# Stages files but deliberately does not start the Discord bot.
set -euo pipefail
umask 077
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
if [[ "$ROOT" == /opt/guild-bot ]]; then
    echo 'Stage the source in a separate directory before running setup.' >&2
    exit 1
fi
if [[ ! -f "$ROOT/requirements-frozen.txt" ]]; then
    echo 'Missing dependency lock file.' >&2
    exit 1
fi
sudo apt-get update -qq
sudo apt-get install -y python3-venv
if ! id clanbot >/dev/null 2>&1; then
    sudo useradd --system --home /opt/guild-bot --shell /usr/sbin/nologin clanbot
fi
sudo install -d -m 700 -o clanbot -g clanbot /opt/guild-bot
for file in bot.py clan.py instance_lock.py requirements-frozen.txt; do
    sudo install -m 600 -o clanbot -g clanbot "$ROOT/$file" "/opt/guild-bot/$file"
done
sudo install -m 600 -o clanbot -g clanbot "$ROOT/deploy/aws/backup.py" /opt/guild-bot/backup.py
sudo install -m 600 -o clanbot -g clanbot "$ROOT/deploy/aws/cloud_backup.py" /opt/guild-bot/cloud_backup.py
sudo install -m 600 -o clanbot -g clanbot "$ROOT/deploy/aws/requirements.txt" /opt/guild-bot/aws-requirements.txt
sudo -u clanbot python3 -m venv /opt/guild-bot/venv
sudo -u clanbot /opt/guild-bot/venv/bin/pip install -r /opt/guild-bot/requirements-frozen.txt
sudo -u clanbot /opt/guild-bot/venv/bin/pip install -r /opt/guild-bot/aws-requirements.txt
sudo install -m 644 "$ROOT/deploy/aws/guild-bot.service" /etc/systemd/system/guild-bot.service
sudo install -m 644 "$ROOT/deploy/aws/guild-bot-backup.service" /etc/systemd/system/guild-bot-backup.service
sudo install -m 644 "$ROOT/deploy/aws/guild-bot-backup.timer" /etc/systemd/system/guild-bot-backup.timer
sudo systemctl daemon-reload
echo 'Staged only. Configure the private .env and complete the AWS/Discord checks in docs/AWS.md before starting.'
