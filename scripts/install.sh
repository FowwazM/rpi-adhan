#!/usr/bin/env bash
# One-shot installer for the adhan appliance on Raspberry Pi OS Lite (Bookworm).
set -euo pipefail

APP_DIR=/opt/adhan
CFG_DIR=/etc/adhan
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "== Installing system packages =="
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip \
  bluez pipewire pipewire-pulse wireplumber libspa-0.2-bluetooth pulseaudio-utils

echo "== Creating service user =="
id adhan &>/dev/null || sudo useradd --system --create-home --groups audio,bluetooth adhan

echo "== Bluetooth adapter power =="
# Unblock the radio and make adapters power on automatically at boot, so the
# keep-alive/watchdog/playback services find a ready controller (avoids
# org.bluez.Error.NotReady). Harmless on Bluetooth-free deployments.
sudo rfkill unblock bluetooth 2>/dev/null || true
if [[ -f /etc/bluetooth/main.conf ]]; then
  if grep -qE '^[[:space:]]*AutoEnable[[:space:]]*=' /etc/bluetooth/main.conf; then
    sudo sed -i -E 's/^[[:space:]]*AutoEnable[[:space:]]*=.*/AutoEnable=true/' /etc/bluetooth/main.conf
  elif grep -q '^\[Policy\]' /etc/bluetooth/main.conf; then
    sudo sed -i '/^\[Policy\]/a AutoEnable=true' /etc/bluetooth/main.conf
  else
    printf '\n[Policy]\nAutoEnable=true\n' | sudo tee -a /etc/bluetooth/main.conf >/dev/null
  fi
  sudo systemctl restart bluetooth || true
fi

echo "== Enabling user-session audio (PipeWire) for the service account =="
sudo loginctl enable-linger adhan
ADHAN_UID="$(id -u adhan)"
# Start PipeWire in the adhan user session (socket-activated; tolerate first-run races).
sudo -u adhan XDG_RUNTIME_DIR="/run/user/${ADHAN_UID}" \
  systemctl --user enable --now pipewire pipewire-pulse wireplumber || true

echo "== Verifying PipeWire is reachable for the adhan user =="
pw_ok=0
for _ in $(seq 1 10); do
  if sudo -u adhan XDG_RUNTIME_DIR="/run/user/${ADHAN_UID}" pactl info >/dev/null 2>&1; then
    pw_ok=1
    break
  fi
  sleep 1
done
if [[ "$pw_ok" -ne 1 ]]; then
  echo "WARNING: PipeWire is not reachable for user 'adhan' — Bluetooth audio will not work" >&2
  echo "         until this is fixed. Check: sudo -u adhan XDG_RUNTIME_DIR=/run/user/${ADHAN_UID} systemctl --user status pipewire" >&2
fi

echo "== Laying down application =="
sudo mkdir -p "$APP_DIR" "$CFG_DIR/media" /var/lib/adhan "$APP_DIR/share"
sudo rm -rf "$APP_DIR/src" "$APP_DIR/scripts"
sudo cp -r "$REPO_DIR/src" "$APP_DIR/"
sudo cp "$REPO_DIR/pyproject.toml" "$APP_DIR/"
sudo cp -r "$REPO_DIR/scripts" "$APP_DIR/"
sudo chmod +x "$APP_DIR"/scripts/*.sh

echo "== Python venv =="
sudo python3 -m venv "$APP_DIR/.venv"
sudo "$APP_DIR/.venv/bin/pip" install -e "$APP_DIR"

echo "== Config =="
[[ -f "$CFG_DIR/config.yaml" ]] || sudo cp "$REPO_DIR/config/config.example.yaml" "$CFG_DIR/config.yaml"
[[ -f "$CFG_DIR/bt-macs.env" ]] || echo 'MACS=""' | sudo tee "$CFG_DIR/bt-macs.env" >/dev/null

echo "== Keep-alive tone =="
# 30s near-silent 50Hz tone at low volume.
command -v sox >/dev/null || sudo apt-get install -y sox
sudo sox -n -r 44100 -c 2 "$APP_DIR/share/silence.wav" synth 30 sine 50 vol 0.02

echo "== systemd units =="
sudo cp "$REPO_DIR"/systemd/*.service /etc/systemd/system/
for svc in adhan adhan-bt-keepalive; do
  sudo mkdir -p "/etc/systemd/system/${svc}.service.d"
  printf '[Service]\nEnvironment=XDG_RUNTIME_DIR=/run/user/%s\n' "$ADHAN_UID" \
    | sudo tee "/etc/systemd/system/${svc}.service.d/runtime.conf" >/dev/null
done
sudo chown -R adhan:adhan "$APP_DIR" "$CFG_DIR" /var/lib/adhan
sudo chmod 0640 "$CFG_DIR/config.yaml"
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
