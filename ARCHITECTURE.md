# Architecture

SmartIR is a Home Assistant custom integration that controls IR/RF devices
(air conditioners, fans, lights, TVs) by sending pre-recorded command codes
through a controller (Broadlink, Xiaomi, LOOK.in, ESPHome, MQTT). It is a
command-only integration (`iot_class: assumed_state`): there is no feedback
channel, so entity state is deduced from the last command sent.

## Overview

```
HA entity            setup helper            api layer                 HA / network
(devices/*.py)  ──▶  (entity.py)     ──▶  get_controller() ──▶  remote.send_command /
climate/fan/          async_setup_          (api/controller)      mqtt.publish /
light/media_player    smartir_platform      async_load_device_    esphome service /
                                            data (api/codes)      LOOK.in HTTP
```

## Layout

```
custom_components/smartir/
├── __init__.py          # entry setup/unload/migrate; runtime_data
├── const.py             # DOMAIN, CONF_*, CONTROLLER_TYPES, SmartIRData (single source of truth)
├── entity.py            # SmartIREntity base + async_setup_smartir_platform (shared setup)
├── config_flow.py       # ConfigFlow (v2) + OptionsFlow (modern selectors)
├── diagnostics.py       # config-entry diagnostics (with redaction)
├── system_health.py     # device count + code-database reachability
├── helpers.py           # pure helpers (closest_match)
├── api/
│   ├── controller.py    # 5 controllers + get_controller() factory + retry
│   ├── codes.py         # device-code download/cache/parse + Pronto/LIRC conversion
│   └── exceptions.py    # typed exception hierarchy (SmartIRError → …)
├── devices/
│   ├── climate.py       # SmartIRClimate
│   ├── fan.py           # SmartIRFan
│   ├── light.py         # SmartIRLight
│   └── media_player.py  # SmartIRMediaPlayer
├── climate.py fan.py light.py media_player.py   # thin platforms (async_setup_entry only)
├── icon.json            # entity/state icon translations
├── quality_scale.yaml   # Quality Scale rule tracking
├── strings.json, translations/{en,fr}.json
└── codes/               # runtime cache of downloaded device codes (gitignored, HACS persistent)
```

## Responsibilities

- **`__init__.py`** — builds `entry.runtime_data` (a `SmartIRData`), forwards to
  the single platform matching the configured `device_type`, registers the
  options update listener, and migrates v1 → v2 config entries
  (`async_migrate_entry`). Raises `ConfigEntryNotReady` if the controller entity
  is not yet available (test-before-setup).
- **`entity.py`** — `async_setup_smartir_platform()` loads the device-code data,
  applies the controller chosen in the flow, and adds the single entity. On a
  code-load failure it raises a repair issue and `ConfigEntryNotReady`.
  `SmartIREntity` centralises `unique_id`, `DeviceInfo`, the controller instance,
  and the translatable command-failure error.
- **`api/`** — the only layer that talks to the outside world. `controller.py`
  turns an abstract command into a concrete HA service call (or LOOK.in HTTP
  request), retried with backoff. `codes.py` downloads and caches device-code
  files. No HA entity logic lives here.
- **`devices/`** — one module per device type, holding the entity class and its
  platform-specific state/services. No file/network I/O and no cross-device
  logic.

## Data flow

1. The user configures a device through the config flow (device type →
   controller → device code + controller entity + optional sensors).
2. On setup, `async_load_device_data` returns the code set (downloading and
   caching it under `codes/<platform>/<code>.json` on first use).
3. A single entity is created and attached to a device keyed on the config entry
   id.
4. On a service call, the entity looks up the command in its code set and
   dispatches it through its controller, which retries delivery and raises
   `HomeAssistantError` if it ultimately fails (the entity reverts optimistic
   state).

## Identity & migration

Entity `unique_id` is `f"{entry_id}_{device_type}"` and the device identifier is
`(DOMAIN, entry_id)` (schema v2). Entries created with the legacy
`smartir_{type}_{code}_{controller}` scheme (v1) are migrated in place by
`async_migrate_entry`, preserving entity ids and history.

## Extending

- **New device type / platform** — add `devices/<type>.py` with a
  `SmartIREntity` subclass (set `PLATFORM`), add a thin `<type>.py` platform that
  calls `async_setup_smartir_platform`, and register the type in
  `DEVICE_TYPES` (const.py) and the config flow.
- **New controller** — add a subclass in `api/controller.py`, register it in
  `get_controller`, and add it to `CONTROLLER_TYPES` (const.py).
