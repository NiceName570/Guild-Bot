#!/usr/bin/env bash
# Run once on the server. Expects the project staged in /tmp/guild-bot-staging.
set -euo pipefail

sudo dnf install -y -q python3-pip

sudo mkdir -p /opt/guild-bot
sudo chown opc:opc /opt/guild-bot
cp -r /tmp/guild-bot-staging/. /opt/guild-bot/

cd /opt/guild-bot
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt

chmod 600 /opt/guild-bot/.env

sudo cp /opt/guild-bot/deploy/guild-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now guild-bot
