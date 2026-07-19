#!/usr/bin/env bash
# Maintain a PipeWire combined sink over all Bluetooth A2DP sinks and keep the
# speakers awake with a continuous near-silent stream.
set -euo pipefail

SINK_NAME="adhan_combined"
SILENCE="/opt/adhan/share/silence.wav"
# Per-speaker volume, pinned on each A2DP sink whenever the combined sink is
# (re)built, so it survives reconnects and the adhan's per-prayer volume (set on
# the combined sink) is the effective control. Some speakers report a very low
# A2DP volume and need software amplification above 100% — set BT_SINK_VOLUME in
# /etc/adhan/bt-macs.env (e.g. "1000%") if playback is too quiet.
SINK_VOLUME="${BT_SINK_VOLUME:-100%}"
CACHED_SLAVES=""

current_bt_sinks() {
  pactl list short sinks | awk '/bluez_output/ {print $2}' | sort | paste -sd, -
}

combine_module_id() {
  pactl list short modules \
    | awk -v s="sink_name=$SINK_NAME" '$0 ~ /module-combine-sink/ && index($0, s) {print $1; exit}'
}

ensure_combined_sink() {
  local slaves mid s
  slaves="$(current_bt_sinks)"
  if [[ -z "$slaves" ]]; then
    # No Bluetooth sinks: drop the now-stale combined sink and reset the cache so
    # it rebuilds cleanly when a speaker reconnects.
    mid="$(combine_module_id || true)"
    [[ -n "$mid" ]] && pactl unload-module "$mid" || true
    CACHED_SLAVES=""
    return 1
  fi
  if [[ "$slaves" != "$CACHED_SLAVES" ]]; then
    mid="$(combine_module_id || true)"
    [[ -n "$mid" ]] && pactl unload-module "$mid" || true
    pactl load-module module-combine-sink sink_name="$SINK_NAME" slaves="$slaves" >/dev/null
    # Pin each speaker to SINK_VOLUME; the adhan then scales loudness per prayer
    # via the combined sink on top of this.
    for s in ${slaves//,/ }; do
      pactl set-sink-volume "$s" "$SINK_VOLUME" || true
    done
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
