#!/usr/bin/env bash
# Reconnect trusted Bluetooth speakers with per-device exponential backoff when
# they drop. MACs are passed as arguments by the systemd unit.
set -euo pipefail

MACS=("$@")
if [[ ${#MACS[@]} -eq 0 ]]; then
  echo "No MACs configured; exiting." >&2
  exit 0
fi

declare -A BACKOFF NEXT
for m in "${MACS[@]}"; do
  BACKOFF["$m"]=2
  NEXT["$m"]=0
done

while true; do
  now=$(date +%s)
  for MAC in "${MACS[@]}"; do
    if bluetoothctl info "$MAC" | grep -q "Connected: yes"; then
      BACKOFF["$MAC"]=2
      NEXT["$MAC"]=0
    elif (( now >= NEXT["$MAC"] )); then
      echo "Reconnecting $MAC (backoff ${BACKOFF[$MAC]}s)"
      bluetoothctl connect "$MAC" || true
      NEXT["$MAC"]=$(( now + BACKOFF["$MAC"] ))
      next=$(( BACKOFF["$MAC"] * 2 ))
      (( next > 120 )) && next=120
      BACKOFF["$MAC"]=$next
    fi
  done
  sleep 2
done
