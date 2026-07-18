#!/usr/bin/env bash
# Reconnect trusted Bluetooth speakers with exponential backoff when they drop.
# MACs are passed as arguments by the systemd unit (from config at install time).
set -euo pipefail

MACS=("$@")
if [[ ${#MACS[@]} -eq 0 ]]; then
  echo "No MACs configured; exiting." >&2
  exit 0
fi

declare -A BACKOFF
for m in "${MACS[@]}"; do BACKOFF["$m"]=2; done

while true; do
  for MAC in "${MACS[@]}"; do
    if bluetoothctl info "$MAC" | grep -q "Connected: yes"; then
      BACKOFF["$MAC"]=2
    else
      echo "Reconnecting $MAC (backoff ${BACKOFF[$MAC]}s)"
      bluetoothctl connect "$MAC" || true
      sleep "${BACKOFF[$MAC]}"
      next=$(( BACKOFF["$MAC"] * 2 ))
      (( next > 120 )) && next=120
      BACKOFF["$MAC"]=$next
    fi
  done
  sleep 10
done
