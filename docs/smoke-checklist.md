# Deployment smoke checklist

Run on the target Raspberry Pi after `scripts/install.sh` and configuration
(`/etc/adhan/config.yaml`, adhan MP3s in `/etc/adhan/media/`, Bluetooth speakers
paired via `scripts/bt-pair.sh`, MACs written to `/etc/adhan/bt-macs.env`).

## 0. PipeWire reachability (validate FIRST — the top deployment risk)

- [ ] `loginctl show-user adhan | grep Linger` shows `Linger=yes`.
- [ ] After a COLD REBOOT (no interactive login), `/run/user/$(id -u adhan)` exists.
- [ ] `sudo -u adhan XDG_RUNTIME_DIR=/run/user/$(id -u adhan) systemctl --user status pipewire pipewire-pulse wireplumber` shows all three active.
- [ ] `sudo -u adhan XDG_RUNTIME_DIR=/run/user/$(id -u adhan) pactl info` succeeds (a server is reachable).
- [ ] `sudo systemctl status adhan adhan-bt-keepalive` shows both active (not restart-looping on a missing PipeWire socket).

## 1. Prayer schedule

- [ ] `sudo -u adhan /opt/adhan/.venv/bin/adhan --state /var/lib/adhan/state.json status` prints the next prayer and today's schedule.
- [ ] Cross-check the computed times against aladhan.com for the client's location, method, and madhab.

## 2. Playback

- [ ] `adhan ... test-play dhuhr` plays on every configured Google Nest target (cast reaches the device via the Pi's IP URL, not `.local`).
- [ ] `adhan ... test-play dhuhr` plays on every Bluetooth speaker simultaneously (via the `adhan_combined` sink).
- [ ] Fajr plays the Fajr-specific file at the quieter Fajr volume (`adhan ... test-play fajr`).
- [ ] Running `test-play` does NOT change `adhan status` output (it uses a throwaway state).

## 3. Bluetooth resilience

- [ ] `pactl list short sinks` shows a `adhan_combined` sink with all paired speakers as slaves.
- [ ] Leave the system idle 30+ minutes: the Bluetooth speaker has NOT gone to sleep (keep-alive working).
- [ ] Power-cycle a Bluetooth speaker; within ~1 minute `bluetoothctl info <mac>` shows `Connected: yes` again (watchdog), and it is back in the `adhan_combined` slave list (keep-alive rebuilt the sink).

## 4. Durability

- [ ] Reboot the Pi; `adhan status` shows the schedule and services are active, with no interactive login.
- [ ] Let a real prayer time pass and confirm the adhan plays and `state.json` records success per output.
- [ ] Confirm playback still fires the day after (daily 00:01 regeneration) and across a DST boundary if applicable.
