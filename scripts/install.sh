#!/usr/bin/env bash
# One-shot installer for the adhan appliance on Raspberry Pi OS Lite (Bookworm).
set -euo pipefail

APP_DIR=/opt/adhan
CFG_DIR=/etc/adhan
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Installing system packages =="
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip \
  bluez pipewire pipewire-pulse wireplumber pulseaudio-utils shellcheck

echo "== Creating service user =="
id adhan &>/dev/null || sudo useradd --system --create-home --groups audio,bluetooth adhan

echo "== Laying down application =="
sudo mkdir -p "$APP_DIR" "$CFG_DIR/media" /var/lib/adhan "$APP_DIR/share"
sudo cp -r "$REPO_DIR/src" "$REPO_DIR/pyproject.toml" "$APP_DIR/"
sudo cp -r "$REPO_DIR/scripts" "$APP_DIR/"
sudo chmod +x "$APP_DIR"/scripts/*.sh

echo "== Python venv =="
sudo python3 -m venv "$APP_DIR/.venv"
sudo "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

echo "== Config =="
[[ -f "$CFG_DIR/config.yaml" ]] || sudo cp "$REPO_DIR/config/config.example.yaml" "$CFG_DIR/config.yaml"

echo "== Keep-alive tone =="
# 30s near-silent 50Hz tone at low volume.
sudo bash -c "command -v sox >/dev/null || apt-get install -y sox"
sudo sox -n -r 44100 -c 2 "$APP_DIR/share/silence.wav" synth 30 sine 50 vol 0.02

echo "== systemd units =="
sudo cp "$REPO_DIR"/systemd/*.service /etc/systemd/system/
sudo chown -R adhan:adhan "$APP_DIR" "$CFG_DIR" /var/lib/adhan
sudo systemctl daemon-reload

cat <<'EOF'

Next steps:
  1. Edit /etc/adhan/config.yaml (location, method, speakers, volumes).
  2. Drop adhan MP3s into /etc/adhan/media/ (adhan.mp3, adhan_fajr.mp3).
  3. Pair Bluetooth speakers:   sudo -u adhan /opt/adhan/scripts/bt-pair.sh
  4. Write MACs:  echo 'MACS="AA:.. 11:.."' | sudo tee /etc/adhan/bt-macs.env
  5. Enable services:
       sudo systemctl enable --now adhan-bt-keepalive adhan-bt-watchdog adhan
  6. Check:  sudo -u adhan /opt/adhan/.venv/bin/adhan --state /var/lib/adhan/state.json status
EOF
