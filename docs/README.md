# SmartIR — device-code reference

> **Setup is done entirely through the Home Assistant UI** (config flow).
> See the [main README](../README.md) for installation and configuration.
> The pages below are a reference for the **device-code catalogue** and the
> command-file format per platform.

## Overview

SmartIR controls **climate devices**, **media players**, **fans** and **lights**
via infrared/RF controllers:

- [Broadlink](https://www.home-assistant.io/integrations/broadlink/)
- [Xiaomi IR Remote (ChuangmiIr)](https://www.home-assistant.io/integrations/remote.xiaomi_miio/)
- [LOOK.in Remote](http://look-in.club/devices/remote)
- [ESPHome user-defined service for a remote transmitter](https://esphome.io/components/api.html#user-defined-services)
- [MQTT publish service](https://www.home-assistant.io/docs/mqtt/service/)

Each device is driven by a **device code** — a JSON file describing its IR/RF
command set. Codes are downloaded on demand from this repository and cached
locally under `custom_components/smartir/codes/<platform>/<code>.json`
(declared as a `persistent_directory` in `hacs.json`, so user-added codes
survive updates).

## Setup (summary)

1. **Settings → Devices & Services → Add Integration → SmartIR**.
2. Pick the device type, then the controller type.
3. Enter the device code and select the controller entity
   (`controller_data`): a `remote.*` entity for Broadlink/Xiaomi/LOOK.in, an
   ESPHome service name, or an MQTT topic.

## Per-platform code catalogues

- [Climate](CLIMATE.md)
- [Media Player](MEDIA_PLAYER.md)
- [Fan](FAN.md)
- [Light](LIGHT.md)

## Contributing device codes

If your exact model is missing, a compatible code from the same manufacturer
often works. To add a new code, place a JSON file in the matching
`codes/<platform>/` folder of the repository and open a pull request. Incomplete
files and MQTT-only files are not accepted.

## See also

- [SmartIR discussion (Home Assistant Community)](https://community.home-assistant.io/t/smartir-control-your-climate-tv-and-fan-devices-via-ir-rf-controllers/)
