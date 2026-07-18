#!/usr/bin/env bash
# Maintain a PipeWire combined sink over all Bluetooth A2DP sinks and keep the
# speakers awake with a continuous near-silent stream. Does NOT change sink
# volume (the adhan controls that per playback); loudness here is per-stream.
set -euo pipefail

SINK_NAME="adhan_combined"
SILENCE="/opt/adhan/share/silence.wav"
CACHED_SLAVES=""

current_bt_sinks() {
  pactl list short sinks | awk '/bluez_output/ {print $2}' | sort | paste -sd, -
}

combine_module_id() {
  pactl list short modules \
    | awk -v s="sink_name=$SINK_NAME" '$0 ~ /module-combine-sink/ && index($0, s) {print $1; exit}'
}

ensure_combined_sink() {
  local slaves mid
  slaves="$(current_bt_sinks)"
  [[ -z "$slaves" ]] && return 1
  if [[ "$slaves" != "$CACHED_SLAVES" ]]; then
    mid="$(combine_module_id || true)"
    [[ -n "$mid" ]] && pactl unload-module "$mid" || true
    pactl load-module module-combine-sink sink_name="$SINK_NAME" slaves="$slaves" >/dev/null
    CACHED_SLAVES="$slaves"
  fi
  return 0
}

while true; do
  if ensure_combined_sink; then
    # Continuous near-silent keep-alive (low stream volume ~10% of 65536),
    # replayed back-to-back so the A2DP link never idles into sleep.
    paplay --device="$SINK_NAME" --volume=6554 "$SILENCE" || true
  else
    sleep 5   # no Bluetooth sinks connected yet
  fi
done
