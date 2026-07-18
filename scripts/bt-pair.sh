#!/usr/bin/env bash
# Interactive Bluetooth pairing wizard. Pairs + trusts each speaker so the
# watchdog can auto-reconnect later. Run once per deployment.
set -euo pipefail

ADAPTER="${1:-}"
if [[ -n "$ADAPTER" ]]; then
  bluetoothctl select "$ADAPTER"
fi

echo "Put your Bluetooth speaker into pairing mode, then note its MAC below."
bluetoothctl --timeout 20 scan on || true
echo
read -rp "Enter speaker MAC (AA:BB:CC:DD:EE:FF): " MAC

bluetoothctl pair "$MAC"
bluetoothctl trust "$MAC"
bluetoothctl connect "$MAC"

echo "Paired, trusted, and connected $MAC."
echo "Add this speaker to config.yaml under outputs.bluetooth.speakers."
