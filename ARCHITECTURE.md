# Architecture

SmartIR is a Home Assistant custom integration that sends IR/RF commands to
devices through a controller (Broadlink, Xiaomi, LOOKin, ESPHome, MQTT).

## Overview

```
Home Assistant entity  ──▶  Controller abstraction  ──▶  IR/RF blaster  ──▶  Device
   (climate / fan /              (controller.py)           (Broadlink…)
    media_player / light)
```

## Components

| File | Responsibility |
|------|----------------|
| `__init__.py` | Config entry setup/unload, platform forwarding |
| `config_flow.py` | UI configuration and options flow |
| `controller.py` | Controller abstraction — encodes and sends commands per controller type |
| `climate.py` | Climate entity (AC control: temperature, HVAC/fan/swing modes) |
| `fan.py` | Fan entity (speed, oscillation, direction) |
| `media_player.py` | Media player entity (power, volume, source) |
| `light.py` | Light entity (brightness, color temperature) |
| `sensor.py` | Auxiliary sensors |
| `hub.py` | Central management / bridge |
| `helpers.py` | Device-code loading and shared utilities |
| `diagnostics.py` | Diagnostics dump for support |
| `codes/` | Bundled device-code database (JSON per device) |

## Device codes

Device codes are JSON files describing the IR/RF command set for a device
model. They live in `custom_components/smartir/codes/<platform>/<code>.json`
and are loaded on demand by `helpers.py`. The `codes` directory is declared as
`persistent_directory` in `hacs.json` so user-added codes survive updates.

## Data flow

1. The user configures a device via the config flow, selecting a controller
   entity and a device code.
2. On setup, the matching code file is loaded.
3. When the entity state changes, the corresponding command is looked up in the
   code file and dispatched through `controller.py` to the physical blaster.
