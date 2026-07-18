#!/usr/bin/env bash
# Maintain a PipeWire combined sink over all Bluetooth A2DP sinks and keep the
# speakers awake with a continuous near-silent stream.
set -euo pipefail

SINK_NAME="adhan_combined"

create_combined_sink() {
  # Collect current bluez A2DP sink names.
  mapfile -t BT_SINKS < <(pactl list short sinks | awk '/bluez_output/ {print $2}')
  if [[ ${#BT_SINKS[@]} -eq 0 ]]; then
    return 1
  fi
  if ! pactl list short sinks | awk '{print $2}' | grep -qx "$SINK_NAME"; then
    local joined
    joined=$(IFS=,; echo "${BT_SINKS[*]}")
    pactl load-module module-combine-sink sink_name="$SINK_NAME" slaves="$joined" >/dev/null
  fi
  return 0
}

while true; do
  if create_combined_sink; then
    # ~1% volume sine keeps A2DP links active; -1 amplitude near silence.
    pactl set-sink-volume "$SINK_NAME" 100% || true
    paplay --device="$SINK_NAME" /opt/adhan/share/silence.wav || true
  fi
  sleep 30
done
