# Raspberry Pi Adhan Appliance

Plays the adhan at the five daily prayer times to Google Nest and Bluetooth
speakers (including Echos used as Bluetooth speakers), from a single Raspberry Pi.

See `docs/plan-spec.md` for the design and `docs/plan-impl.md` for the build plan.

## Quick start

    git clone <repo> && cd rpi-adhan-v2
    sudo scripts/install.sh
    # then follow the printed next steps

## Usage

    adhan run                 # run the service (normally via systemd)
    adhan status              # print the current schedule / last results
    adhan test-play dhuhr     # play a prayer now to verify outputs

Note: `test-play` uses a throwaway state file, so it never overwrites the live
`state.json` that `adhan status` reads; the `--state` flag does not apply to it.

## Do I need a Bluetooth dongle?

| Setup | Dongle? |
|---|---|
| All Google Nest, no Bluetooth | No |
| Pi 4 on Ethernet or 5 GHz Wi-Fi, <=2 BT speakers | Usually no |
| Pi 4 on 2.4 GHz Wi-Fi with BT speakers | Recommended |
| Pi 3B on Wi-Fi, casting + BT speakers | Recommended (~required) |
| 3+ BT speakers | Add one dongle (still just one) |

One dongle serves all Bluetooth speakers via the combined sink.

## Development

    python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
    .venv/bin/pytest --cov
