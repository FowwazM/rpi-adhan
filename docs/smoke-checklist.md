# Deployment smoke checklist

This document takes a brand-new Raspberry Pi from a blank SD card to a working,
verified adhan appliance. Do the **Setup** section once per deployment, then work
through the numbered **validation checklist** to confirm everything works.

## Setup

### 1. Flash Raspberry Pi OS Lite (Bookworm)

Use the **Raspberry Pi Imager** on your PC:

- Choose OS: **Raspberry Pi OS Lite (64-bit)** for a Pi 3B / Pi 4. (A Pi 2 can
  only run the 32-bit build and is cast-only — no Bluetooth.)
- Before writing, open the Imager's **⚙ / Edit Settings** and set:
  - **Hostname** (e.g. `adhan`).
  - **Enable SSH** (password or public key).
  - **Username / password** — the account you'll SSH in with and run `sudo`.
  - **Wi-Fi** SSID + password (skip if using Ethernet). On a Pi 4, prefer the
    **5 GHz** band so Wi-Fi doesn't contend with Bluetooth (see the dongle table
    in `README.md`).
  - **Locale / timezone** — set the timezone to the deployment's city.
- Write the image, insert the SD card into the Pi, and power it on.

### 2. Log in and update

```bash
ssh <username>@<hostname>.local          # or ssh <username>@<pi-ip>
sudo apt-get update && sudo apt-get -y full-upgrade
```

Confirm the **system timezone matches the location** you'll put in the config —
the scheduler's day boundary uses the system clock's local time:

```bash
timedatectl                              # check the "Time zone:" line
sudo timedatectl set-timezone America/Chicago   # correct it if needed
```

### 3. (Bluetooth on Wi-Fi only) Add a USB Bluetooth dongle

If this deployment uses Bluetooth speakers **and** the Pi is on Wi-Fi (especially
a Pi 3B, or a Pi 4 on 2.4 GHz), plug in a BT 5.0 USB dongle now, and optionally
disable the onboard Bluetooth so Wi-Fi keeps the onboard radio to itself:

```bash
echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt
sudo reboot
```

Skip this entirely if there are no Bluetooth speakers, you're on Ethernet, or it's
a Pi 4 on 5 GHz (onboard is usually fine — see the dongle table in `README.md`).

### 4. Reserve a static IP for the Pi

Google Cast devices ignore mDNS/`.local` and resolve via public DNS, so the media
server must be reachable at a **stable IP**. Reserve one for the Pi's MAC in your
router's DHCP settings (or set a static IP on the Pi). Leave `network.http_host:
auto` in the config — it auto-detects this IP.

### 5. Get the code onto the Pi and run the installer

```bash
git clone rpi-adhan   # or scp / copy the repo to the Pi
sudo scripts/install.sh
```

`install.sh` installs the system packages (bluez, pipewire, …), creates the
`adhan` service user, **enables user-session audio (linger + PipeWire) and
verifies it's reachable** (watch for a `WARNING` here — this is the top failure
point), lays the app down in `/opt/adhan` with its venv, copies the example
config, generates the keep-alive tone, and installs the systemd units. It prints a
"Next steps" summary; the steps below expand on it.

### 6. Connect the Google Nest speakers

Skip this step if you have no Google speakers. The appliance discovers Cast
devices by their **friendly name** over the local network — there is no pairing.
Prerequisites:

- Each Nest / Chromecast-built-in speaker is already set up in the **Google Home
  app** and on the **same Wi-Fi/LAN and subnet** as the Pi. Cast discovery uses
  mDNS/multicast, so avoid client isolation or separate VLANs between them.
- For **synced multi-room**, create a **speaker group** in the Google Home app
  (**+** → *Create speaker group*). The group is itself a castable target and
  keeps its members in sync; casting to individual speakers can drift out of sync.

List the exact names the Pi can see (copy them verbatim into the config in the
next step — they are case-sensitive). This also confirms discovery works:

```bash
sudo -u adhan /opt/adhan/.venv/bin/python - <<'PY'
import pychromecast
casts, browser = pychromecast.get_chromecasts(timeout=10)
for cc in casts:
    print(cc.cast_info.friendly_name)
pychromecast.discovery.stop_discovery(browser)
PY
```

If a speaker or group is missing, fix discovery before continuing (same subnet,
multicast/mDNS allowed, and the device shows online in the Google Home app).

### 7. Configure `/etc/adhan/config.yaml`

The file is owned by `adhan` and mode `0640`, so edit it with sudo (start from the
copied template, which mirrors `config/config.example.yaml`):

```bash
sudo nano /etc/adhan/config.yaml
```

Set at minimum:

- `location:` — `latitude`, `longitude`, and `timezone` (IANA, matching step 2).
- `prayer_times.offline:` — `method` (e.g. `north_america` for ISNA), `madhab`
  (`shafi` or `hanafi`), and `high_latitude_rule`.
- `prayer_times.prayers:` — per-prayer `enabled` / `offset_minutes`, and the Fajr
  `mode` (`calculated`, or `before_sunrise` with `before_sunrise_minutes`).
- `audio:` — `default_file` (and `per_prayer_files.fajr` if you use a separate
  Fajr adhan), `default_volume`, and any `per_prayer_volume` (e.g. a quieter Fajr).
- `outputs.cast:` — one entry per Google target, its `name` matching a device or
  speaker-group name **exactly** as listed in step 6.
- `outputs.bluetooth.speakers:` — filled in at step 9. Set `adapter` to `auto`
  (or a specific `hciN` if you added a dongle).

Validate that the config parses before going further:

```bash
sudo -u adhan /opt/adhan/.venv/bin/python -c \
  "from adhan.config import load_config; load_config('/etc/adhan/config.yaml'); print('config OK')"
```

### 8. Add the adhan audio files

Copy your chosen MP3s into the media directory, named to match the config
(`adhan.mp3`, plus `adhan_fajr.mp3` if you set a Fajr-specific file):

```bash
sudo cp adhan.mp3 adhan_fajr.mp3 /etc/adhan/media/
sudo chown adhan:adhan /etc/adhan/media/*.mp3
```

### 9. Pair Bluetooth speakers (and/or Echos)

For each Bluetooth speaker or Echo, put it in pairing mode, then run the wizard
(pass a dongle adapter like `hci1` as an argument if you added one at step 3):

```bash
sudo -u adhan /opt/adhan/scripts/bt-pair.sh          # or: ... bt-pair.sh hci1
```

If pairing fails with `org.bluez.Error.NotReady`, the controller isn't powered.
The installer sets `AutoEnable=true` so it comes up at boot, but you can force it
once with `sudo rfkill unblock bluetooth && sudo bluetoothctl power on` (confirm
with `bluetoothctl show` → `Powered: yes`). If `bluetoothctl list` prints nothing,
there's no controller at all — plug in / fix the USB dongle, or re-enable onboard
Bluetooth by removing the `dtoverlay=disable-bt` line from step 3.

Note each speaker's MAC, add it under `outputs.bluetooth.speakers` in the config,
then write all the MACs for the reconnect watchdog:

```bash
echo 'MACS="AA:BB:CC:DD:EE:FF 11:22:33:44:55:66"' | sudo tee /etc/adhan/bt-macs.env
```

(An Echo works here as a plain Bluetooth speaker — pair it exactly the same way.)

### 10. Enable the services

```bash
sudo systemctl enable --now adhan-bt-keepalive adhan-bt-watchdog adhan
```

Setup is complete. Now work through the validation checklist below, starting with
PipeWire reachability.

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
