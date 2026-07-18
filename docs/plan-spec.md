# Raspberry Pi Adhan Appliance — Design Spec

- **Date:** 2026-07-18
- **Status:** Draft (awaiting review)
- **Supersedes:** The original Home Assistant OS–based adhan system (Word-doc install + per-ecosystem YAML in `Config/`)
- **Scope of this spec:** Full design; **Phase 1 is the implementation target**. Phase 2 items are called out explicitly.

---

## 1. Overview

A single Raspberry Pi runs a small, config-driven service that plays the Islamic adhan (call to prayer) at the five daily prayer times to a mix of **Google Home/Nest**, **Amazon Echo**, and **Bluetooth** speakers. It replaces a heavyweight Home Assistant OS install and a 24-step manual setup with a **purpose-built appliance**: offline prayer-time calculation, a repeatable installer, and a clean plugin boundary for output transports.

### Goals

1. **Robust and unattended** — computes prayer times offline (no internet dependency, no daily-restart hack) and plays reliably for years.
2. **Easy, repeatable deployment** — one golden install + a single per-client `config.yaml`. This is the primary product driver; the maintainer redeploys this for family/friends/clients.
3. **All three speaker ecosystems** — Google Nest (network cast), Amazon Echo, and Bluetooth speakers, from **one** Raspberry Pi.
4. **Extensible** — new output transports (AirPlay/Sonos/DLNA/Snapcast) and new time sources (Mawaqit) drop in behind stable interfaces without touching the core.

### Non-goals

- Not a general-purpose home-automation platform (that was the old HA approach we are deliberately shedding).
- Not multi-Pi. **Hard constraint: exactly one Raspberry Pi per deployment.** No satellite Pis, no Snapcast satellite nodes.
- Not sample-accurate whole-house sync across *Bluetooth* rooms (physically impossible on one host — see §9).
- No cloud services or subscriptions in Phase 1.

---

## 2. Background — why redo it

The original system worked but is fragile and hard to replicate. Confirmed issues:

- Bundled Home Assistant OS images are years out of date (HAOS 6.4/6.5/3.13).
- ~24 manual setup steps in a Word document; error-prone and not repeatable.
- The Google Home automation has a duplicate `entity_id` YAML key, so **only one** of the two speakers actually plays.
- A daily `homeassistant.restart` at 01:00 was needed only to refresh prayer-time sensors — an obsolete hack.
- The Amazon path relied on an unofficial integration (Alexa Media Player via HACS) **plus** a third-party "MyPod" Alexa skill.
- The External Speaker path used a third-party Local VLC add-on over telnet.
- No Bluetooth support, no volume control, no observability ("did it actually play?").

### Key findings from current (2025–2026) research that shape this design

- **Prayer times:** the modern robust choice is **offline calculation** with the `adhanpy` library (pure-Python, no runtime deps, Meeus astronomical algorithms, full method list, Shafi/Hanafi Asr, high-latitude rules, per-prayer offsets). Notably, Home Assistant's own `islamic_prayer_times` integration is *less* robust here because it calls the Aladhan **web API** — internet-bound. We compute locally instead.
- **Google Nest is the easy ecosystem:** cast a local MP3 to a **Google speaker group** (one synced target). The only hard constraint is that the media URL must use an **IP address**, because Chromecasts ignore the LAN's mDNS/DHCP DNS and resolve via public DNS.
- **Amazon Echo cannot play a custom/full MP3 through any supported API.** The official HA Alexa integration is TTS-only; Alexa Media Player rejects custom media URLs ("Direct music streaming isn't supported" — Amazon marked it won't-fix). Every cloud workaround needs a public HTTPS URL + a trimmed clip + a fragile Amazon login.
- **The unlock:** an Echo is *also* a plain Bluetooth speaker. Pairing the Pi to the Echo over Bluetooth plays the **full adhan, locally, no cloud** — the *same* mechanism as the Bluetooth-speaker requirement. This collapses two of the three ecosystems into one local transport. (Proven by the `kamranzafar/piprayer` project, tested on an Echo.)
- **Bluetooth is reliable only with discipline:** full Linux (Raspberry Pi OS, **not** the locked-down HAOS), a current BlueZ + PipeWire stack, a **silent keep-alive stream** so speakers don't sleep, and an **auto-reconnect watchdog**. The dominant failure mode is the speaker falling asleep.
- **Bluetooth fan-out:** a single Bluetooth adapter can hold multiple A2DP links; **PipeWire's combined sink** plays the same audio to all of them at once. ~2 speakers per adapter is reliable on current software; 3+ gets flaky. This is a "validate on hardware" capability, not a guarantee.

---

## 3. Requirements

### Functional

- FR1. Compute the five prayer times for the current date and location, offline.
- FR2. Support calculation method, madhab (Shafi/Hanafi Asr), high-latitude rule, and **per-prayer minute offsets**.
- FR3. Support a **Fajr mode** of either the calculated Fajr time or "N minutes before sunrise" (the original system used 30 minutes before sunrise).
- FR4. Allow any prayer to be individually enabled/disabled.
- FR5. Play a per-prayer adhan file (with a distinct Fajr file) at a per-prayer volume (e.g., a quieter Fajr).
- FR6. Play to **Google Nest** speakers/groups over the network.
- FR7. Play to **Bluetooth** speakers (including Echos used as Bluetooth speakers), multiple simultaneously via a combined sink.
- FR8. Play to all configured outputs for a given prayer concurrently.
- FR9. Recompute the schedule daily and survive DST transitions.
- FR10. Retry a failed output and record the outcome; expose current state (next prayer, last result per output, speaker health) for inspection.

### Non-functional

- NFR1. **One Raspberry Pi**, Raspberry Pi OS Lite (Bookworm), Pi 4 recommended / Pi 3B supported (see §9).
- NFR2. **Repeatable install** — a single installer + one `config.yaml` is the entire per-site delta.
- NFR3. **No internet dependency** for core operation (Phase 1). No cloud, no subscription.
- NFR4. **Observable** — structured logs + a machine-readable state file.
- NFR5. **Testable to ≥95% coverage** on core logic via interface fakes (hardware glue isolated behind interfaces).
- NFR6. **Secure by default** — least-privilege service user, restricted config/media permissions, local-only HTTP bound to the LAN, no secrets in logs.
- NFR7. **Extensible** — stable `TimeProvider` and `Player` interfaces; versioned config schema.

### Decisions locked with the maintainer

| Decision | Choice |
|---|---|
| Architecture | Purpose-built Python appliance on Raspberry Pi OS Lite |
| Prayer times | Offline (`adhanpy`) by default; Mawaqit as a **Phase 2** source option |
| Setup UX | Config file + installer first; **web UI is Phase 2** |
| Deployment scale | ~2–3 speakers across the house, mixed ecosystems |
| Alexa strategy | Echo-as-Bluetooth-speaker (local); cloud path is an optional future escape hatch only |
| Failure handling | Retry + health-check + logs + `state.json`; **no push notifications** (clients already have prayer apps) |
| Hardware | Pi 4 recommended; Pi 3B supported |

---

## 4. Architecture

```
                    ┌──────────────────────────────────────────────────┐
   Prayer source ──►│            Raspberry Pi  (Pi OS Lite)             │
  offline (adhanpy) │                                                   │
                    │  [Time Provider]  adhanpy (offline) │ Mawaqit(P2) │
                    │        │  today's 5 times (tz-aware, DST-correct)  │
                    │        ▼                                          │
                    │  [Scheduler]  APScheduler — daily regen @00:01,   │
                    │        │       one-shot job per enabled prayer    │
                    │        ▼                                          │
                    │  [Orchestrator]  resolve adhan file + volume       │
                    │        │         (Fajr special / quieter)         │
                    │        ▼   parallel fan-out                        │
                    │  [OutputManager] ──┬───────────────┐              │
                    │                    ▼               ▼              │
                    │            [CastPlayer]      [BluetoothPlayer]     │
                    │            pychromecast      PipeWire combine-sink │
                    │            + local HTTP srv  → BlueZ A2DP (1..n)   │
                    │                    │               │              │
                    │  [Reliability: retry + health-check]              │
                    │  [Observability: JSON logs + state.json] ◄─ Web(P2)│
                    └────┼───────────────────────────┼──────────────────┘
                    WiFi/LAN │                   Bluetooth A2DP │
                             ▼                                  ▼
                    Nest speaker group              BT speakers + Echos
                    (synced, any count)             (~2 per adapter)
```

### Component responsibilities, interfaces, and dependencies

Each component has one purpose, a defined interface, and is testable in isolation.

**Config Loader** — loads and validates `config.yaml` into a typed model (pydantic v2), versioned. *Depends on:* filesystem. *Consumed by:* everything.

**Time Provider** *(interface)* — computes the day's prayer schedule.
```python
class PrayerSchedule:  # aware datetimes keyed by prayer, plus sunrise
    fajr: datetime; sunrise: datetime; dhuhr: datetime
    asr: datetime; maghrib: datetime; isha: datetime

class TimeProvider(Protocol):
    def get_schedule(self, day: date) -> PrayerSchedule: ...
```
- Phase 1: `OfflineProvider` (adhanpy). Phase 2: `MawaqitProvider`.
- Post-computation transforms (per-prayer offsets, Fajr "before sunrise" mode) live in a thin `ScheduleAdjuster`, keeping providers pure.

**Scheduler** — an APScheduler `BackgroundScheduler`. A cron job at 00:01 local recomputes the day's schedule and registers one-shot `DateTrigger` jobs for each enabled prayer; on startup it schedules the remainder of today. `misfire_grace_time` lets a briefly-busy Pi still fire. *Depends on:* Time Provider, Orchestrator. Clock is injectable for tests.

**Orchestrator** — on a prayer event, resolves the adhan file (per-prayer override, Fajr file) and the volume (per-prayer override), then calls the Output Manager. *Depends on:* Media Manager, Output Manager.

**Media Manager** — resolves prayer → file path; owns the **local HTTP server** (aiohttp/`http.server`) that serves the media directory to Cast devices over the Pi's LAN IP:port. Serves only the media dir, no directory listing. *Consumed by:* CastPlayer (URL) and BluetoothPlayer (file path).

**Output layer** *(Player interface + Output Manager)*:
```python
class Player(Protocol):
    name: str
    def health_check(self) -> HealthStatus: ...
    def play(self, media: MediaRef, volume: float) -> PlayResult: ...
```
- `CastPlayer` — pychromecast. Targets a **Google speaker group** (preferred, synced) or named device(s). Reads current volume → sets announce volume → plays the HTTP URL → waits for completion (polls player state) → restores volume. Media must be a Chromecast-native format (MP3) at an **IP-based URL**.
- `BluetoothPlayer` — plays to a PipeWire **combined sink** aggregating the paired A2DP sinks, so all Bluetooth speakers sound together. Per-speaker node volume; overall via the combined sink. Playback via a PipeWire/PulseAudio client (`pw-play`/`paplay`/libpulse).
- `OutputManager` — fans a single play request out to all enabled players concurrently (thread pool / asyncio) and aggregates per-player `PlayResult`s.

**Reliability** — wraps each player call in retry-with-backoff and a pre-flight `health_check` (cast device reachable; BT sink connected). Final failures are logged and recorded in `state.json`. No external notification.

**Observability** — structured JSON logging to journald + a rotating file, and `state.json` (next prayer, today's schedule, last result per prayer per output, speaker health, service start time). Phase 2 web UI simply renders `state.json`.

**Bluetooth connection manager** *(systemd-managed, outside the Python app)* — a headless auto-accept pairing agent, device `trust`, a **silent keep-alive** stream per A2DP sink so speakers never sleep, and a **reconnect watchdog** that reissues `connect <MAC>` with exponential backoff on disconnect/reboot. Adapter selection is configurable; the installer can disable onboard BT when a USB dongle is used.

**Installer & packaging** — Phase 1: a Python package + systemd unit(s) + an `install.sh` that apt-installs dependencies (pipewire, bluez, libpulse, python3-venv…), creates the venv, lays down `/etc/adhan/`, runs the **Bluetooth pairing wizard** (`adhan pair`), installs and enables the systemd services, and reserves/records the LAN IP. A **golden SD image** is a Phase 2 convenience on top.

---

## 5. Data flow

**Daily regeneration (00:01 local, and on startup):**
1. Scheduler triggers regeneration.
2. Time Provider computes `PrayerSchedule` for `today`.
3. `ScheduleAdjuster` applies per-prayer offsets and the Fajr mode.
4. Scheduler registers a one-shot job per enabled prayer; writes today's schedule + next prayer to `state.json`.
5. DST is handled implicitly because all datetimes are tz-aware for the configured IANA zone.

**Adhan firing (per prayer):**
1. One-shot job fires → Orchestrator.
2. Orchestrator resolves file + volume (Fajr specials applied).
3. Output Manager fans out to CastPlayer and BluetoothPlayer concurrently.
4. Each player: health-check → set volume → play → (Cast) restore volume; retries on failure.
5. Per-output results recorded in `state.json`; structured log line emitted.

---

## 6. Configuration (`/etc/adhan/config.yaml`)

Single per-site file, validated on load, versioned. Example:

```yaml
version: 1

location:
  latitude: 29.7007851
  longitude: -95.8028693
  timezone: America/Chicago        # IANA tz; drives DST automatically

prayer_times:
  source: offline                  # offline | mawaqit (mawaqit = Phase 2)
  offline:
    method: north_america          # ISNA and the full adhanpy method list
    madhab: hanafi                 # shafi | hanafi  (affects Asr)
    high_latitude_rule: middle_of_the_night
  prayers:
    fajr:
      enabled: true
      mode: before_sunrise         # calculated | before_sunrise
      before_sunrise_minutes: 30   # used only when mode = before_sunrise
      offset_minutes: 0
    dhuhr:   { enabled: true, offset_minutes: 0 }
    asr:     { enabled: true, offset_minutes: 0 }
    maghrib: { enabled: true, offset_minutes: 0 }
    isha:    { enabled: true, offset_minutes: 0 }

audio:
  default_file: adhan.mp3          # relative to /etc/adhan/media/
  per_prayer_files:
    fajr: adhan_fajr.mp3           # Fajr-specific adhan
  default_volume: 0.6              # 0.0–1.0
  per_prayer_volume:
    fajr: 0.4                      # quieter Fajr

outputs:
  cast:
    - name: "Downstairs group"     # Google Home app speaker-group or device name
  bluetooth:
    adapter: auto                  # auto | hci0 | hci1 ...
    keepalive: true
    speakers:
      - { name: "JBL Charge 5",     mac: "AA:BB:CC:DD:EE:FF" }
      - { name: "Echo Dot Bedroom", mac: "11:22:33:44:55:66" }

network:
  http_host: auto                  # Pi's reserved LAN IP (Chromecast needs an IP, not .local)
  http_port: 8127

reliability:
  retry_attempts: 2
  retry_backoff_seconds: 5
  misfire_grace_seconds: 300       # still fire if the Pi was briefly busy

logging:
  level: INFO
  json: true
```

---

## 7. Hardware and the Bluetooth-dongle decision

**Pi compatibility:**

| Model | Verdict | Notes |
|---|---|---|
| Pi 4 Model B | **Recommended** | BT 5.0, dual-band (5 GHz) Wi-Fi, USB 3.0, most headroom. |
| Pi 3 Model B / B+ | **Supported** | Onboard Wi-Fi + BT 4.1/4.2, 64-bit; fine for 2–3 speakers. 2.4 GHz-only Wi-Fi on the B. |
| Pi 2 Model B | Oldest compatible; **not recommended** | No onboard Wi-Fi/BT (USB dongles required), 32-bit. Viable only for a **cast-only** (no Bluetooth) install. |
| Pi 1 / Pi Zero v1 | Avoid | Single-core ARMv6; too weak. |

**Do I need a USB Bluetooth dongle?** The onboard radio is a combo Wi-Fi+BT chip sharing one antenna; contention appears when the Pi casts over Wi-Fi *and* streams Bluetooth at the same instant. Bluetooth is in the 2.4 GHz band, so 5 GHz Wi-Fi (Pi 4 / Pi 3B+) sidesteps the clash.

| Scenario | Dongle? |
|---|---|
| Any Pi, **0 Bluetooth speakers** (all Nest) | No |
| Pi 4 on **Ethernet** or **5 GHz Wi-Fi**, ≤2 BT speakers | **Usually no** |
| Pi 4 on **2.4 GHz Wi-Fi**, BT speakers | **Recommended** |
| Pi 3B on **Ethernet**, ≤2 BT speakers | Usually no |
| Pi 3B on **Wi-Fi**, casting + BT speakers | **Recommended (≈required)** |
| Any Pi, **3+ BT speakers** or bulletproof reliability | Add one dongle (still just one) |

One dongle (BT 5.0, e.g. RTL8761B, ~$12) serves **all** the Bluetooth speakers via the combined sink — never one-per-speaker. For hands-off client installs where the network band can't be guaranteed, carrying one dongle per Pi is cheap insurance.

---

## 8. Bluetooth reliability design

The three measures that make Bluetooth dependable, all owned by the systemd-level connection manager (not the Python app):

1. **Dedicated radio (when needed):** a USB dongle per §7; installer optionally disables onboard BT (`dtoverlay=disable-bt`) so Wi-Fi keeps the onboard chip.
2. **Silent keep-alive stream** to each A2DP sink so speakers never idle into sleep — the single highest-leverage fix.
3. **Reconnect watchdog:** a systemd service watching BlueZ connection state, reissuing `connect <MAC>` with exponential backoff after disconnect/power-cycle/reboot; devices are `trust`ed and paired once via the install wizard.

**Fan-out:** a PipeWire `module-combine-sink` aggregates all paired A2DP sinks; the adhan plays once to the combined sink and reaches every Bluetooth speaker. Cross-room Bluetooth sync is approximate (independent per-device latency) — acceptable for rooms you can't occupy simultaneously; PipeWire per-node latency offsets narrow the gap.

**Speaker-choice guidance (documented for deployers):** prefer speakers whose firmware auto-reconnects and whose app can disable auto-power-off; that single factor is the biggest predictor of multi-year reliability.

---

## 9. Error handling and edge cases

- **Cast device unreachable / asleep:** health-check fails fast → retry with backoff → record failure; other outputs still play.
- **Bluetooth speaker disconnected at prayer time:** watchdog is already reconnecting; play still attempts and retries within the misfire grace window.
- **Pi was off/asleep at prayer time:** `misfire_grace_seconds` fires a late adhan if within grace; beyond grace it is skipped and logged (an adhan hours late is worse than none).
- **DST / timezone change:** tz-aware datetimes + daily regen handle it; a prayer near the DST jump is computed against the correct offset for that date.
- **Config invalid:** service refuses to start with a clear validation error (fail loud, not silently wrong).
- **Media file missing:** validated at load and pre-flight; the affected prayer logs an error rather than crashing the service.
- **Chromecast `.local` URL:** prevented — `network.http_host` must resolve to an IP; `auto` detects the LAN IP.
- **Two prayers within the misfire window / overlapping playback:** playback is serialized per output; queued rather than overlapped.

---

## 10. Testing strategy (TDD, ≥95% core coverage)

Red → Green → Refactor throughout. Hardware is behind interfaces so the core is fully testable without a Pi.

- **Time Provider (unit):** cross-check `adhanpy` output for fixed date/location against published reference times per method + madhab; verify offsets and Fajr "before sunrise" math; DST-boundary dates.
- **Scheduler (unit):** injected clock (freezegun); daily regen registers correct jobs; misfire grace behavior; DST rollover.
- **Config (unit):** valid/invalid schemas; defaults; version handling.
- **Media Manager (unit/integration):** file resolution incl. Fajr override; HTTP server serves only the media dir, rejects traversal, binds to the configured IP.
- **Output Manager + Players (unit):** fake `Player`s verify concurrent fan-out and result aggregation; retry/backoff on induced failures; volume set/restore on a fake Cast controller.
- **Contract tests:** every real and fake `Player`/`TimeProvider` satisfies the interface contract.
- **Hardware smoke checklist (manual, per deploy):** cast to the real group; Bluetooth combined-sink playback; keep-alive holds a speaker awake; watchdog recovers after a speaker power-cycle.

---

## 11. Security

- Dedicated non-root service user in the `audio`/`bluetooth` groups; least privilege.
- `/etc/adhan/config.yaml` mode `0640`, owned by the service user; secrets (Phase 2 Mawaqit creds) never logged.
- Local HTTP server binds to the LAN interface only, serves a single directory, no listing, no upload.
- No inbound cloud exposure in Phase 1.

---

## 12. Observability

- **Structured JSON logs** to journald + rotating file: each adhan attempt logs prayer, per-output result, latency, retries.
- **`state.json`:** `service_started_at`, `next_prayer` (name + time), `today_schedule`, `last_results` (per prayer → per output: timestamp, success, error), `speaker_health`. This is the contract the Phase 2 web UI renders and the basis for any future health endpoint.

---

## 13. Extensibility and future interconnection

- **New transports:** implement `Player` (AirPlay, Sonos, DLNA, Snapcast) — no core changes.
- **New time sources:** implement `TimeProvider` (Mawaqit, Aladhan fallback).
- **External integration:** an optional **event publish** (MQTT topic and/or local HTTP/webhook) emitting adhan events so Home Assistant or other systems can subscribe later. (Phase 2+.)
- **Alexa cloud escape hatch:** for a client who needs their Echo to stay fully functional during the adhan, a future `VoiceMonkeyPlayer` implements `Player` via the cloud announce path — additive, not in Phase 1.
- **Versioned config schema** with a migration path for fleet-wide upgrades.

---

## 14. Phasing

**Phase 1 (this implementation cycle):**
- Offline time provider + schedule adjuster + scheduler.
- Config loader/validation; media manager + local HTTP server.
- CastPlayer, BluetoothPlayer, Output Manager; reliability (retry + health).
- Bluetooth connection manager (pairing wizard, keep-alive, watchdog) + systemd units.
- Structured logging + `state.json`.
- `install.sh` installer and documentation.
- Test suite to the coverage target.

**Phase 2 (future):**
- Local web setup/status UI (renders `state.json`, edits `config.yaml`).
- Mawaqit time source.
- Golden SD image.
- Optional MQTT/HTTP event publish; additional transports as needed.

---

## 15. Prior art to build on (not from scratch)

- **`nofaily/athan-automation`** — Python + pychromecast, Chromecast **speaker groups**, per-prayer volumes, systemd. Base for the Cast path.
- **`kamranzafar/piprayer`** — Bluetooth via the Linux audio stack, **tested with an Echo over Bluetooth**. Reference for the BT/Echo path.
- **`achaudhry/adhan`** — popular Pi adhan clock; reference for the daily-schedule + pre/post hook pattern.
- Swap their `praytimes.py` for **`adhanpy`** (offline, modern, testable).

---

## 16. Open questions / risks

- **R1 — Multi-A2DP fan-out ceiling:** 2 Bluetooth speakers on one adapter is expected-reliable but must be **validated on the actual hardware/dongle** before promising 3+.
- **R2 — Cast group quirks:** raw pychromecast handles Google groups less gracefully than HA; targeting the group entity and relying on Google's own sync is the mitigation, to be verified per deployment.
- **R3 — Speaker firmware variance:** Bluetooth reconnect reliability is partly the speaker's firmware; documented in the deployer guidance (§8).

---

## 17. Success criteria

- A fresh Pi goes from flashed OS to working adhan via **one installer run + one `config.yaml` edit + the pairing wizard**.
- Five daily adhans play on all configured Nest and Bluetooth outputs, at correct times, through DST, with no internet and no manual restarts.
- A Bluetooth speaker that sleeps or power-cycles is reconnected automatically before the next prayer.
- `state.json` and logs accurately reflect what played where.
- Core logic ≥95% test coverage; hardware paths covered by the smoke checklist.
