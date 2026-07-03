# SmartIR

[![hacs][hacsbadge]][hacs]
[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)
[![CI][ci-shield]][ci]
[![hassfest][hassfest-shield]][hassfest]
[![Maintenance][maintenance-shield]][maintenance]

_Custom Home Assistant integration to control IR/RF devices — air conditioners, fans, TVs and lights — through Broadlink, Xiaomi, LOOKin, ESPHome and MQTT controllers._

## Features

- **Climate Control** — Control air conditioners with temperature, fan modes, swing modes, and HVAC modes
- **Fan Control** — Control fans with speed, direction, and oscillation
- **Media Player** — Control TVs and audio devices with power, volume, source selection
- **Light Control** — Control IR-based lights with brightness and color temperature
- **Multiple Controllers** — Broadlink, Xiaomi, LOOKin, ESPHome, and MQTT
- **State Restoration** — Remembers device states after Home Assistant restarts
- **Power Sensor Integration** — Sync device state with an external power sensor

## Supported Controllers

| Controller | Description |
|------------|-------------|
| Broadlink | Broadlink RM series IR blasters |
| Xiaomi | Xiaomi ChuangmiIr IR Remote |
| LOOKin | LOOK.in Remote |
| ESPHome | ESPHome-based IR transmitters |
| MQTT | MQTT-based IR controllers |

## Requirements

- Home Assistant ≥ 2025.5.0
- One supported IR/RF controller integration configured in Home Assistant

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Click the three-dots menu → **Custom repositories**
3. Add `https://github.com/foXaCe/SmartIR` with category **Integration**
4. Search for "SmartIR" and install it
5. Restart Home Assistant
6. **Settings** → **Devices & Services** → **Add Integration** → "SmartIR"

### Manual

1. Download the latest release from [GitHub Releases][releases]
2. Copy the `custom_components/smartir` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant
4. Add the integration from the UI

## Configuration

### Via UI

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "SmartIR"
4. Follow the configuration wizard:
   - Select device type (Climate, Fan, Media Player, Light)
   - Select your IR controller type
   - Enter the device code and controller entity

### Device Codes

Device codes contain the IR commands for specific devices. Browse the codes bundled with this integration:

- [Climate codes](https://github.com/foXaCe/SmartIR/tree/main/custom_components/smartir/codes/climate)

If your device is not listed, you can create your own device code or request one via [GitHub issues][issues].

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `device_code` | Device code number | Required |
| `controller_data` | IR controller entity | Required |
| `delay` | Delay between commands (seconds) | 0.5 |
| `temperature_sensor` | External temperature sensor (climate only) | Optional |
| `humidity_sensor` | External humidity sensor (climate only) | Optional |
| `power_sensor` | Power sensor to sync state | Optional |

## Automation Example

```yaml
automation:
  - alias: "Turn on AC when hot"
    trigger:
      - platform: numeric_state
        entity_id: sensor.room_temperature
        above: 28
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.smartir_ac
        data:
          temperature: 24
          hvac_mode: cool
```

## Troubleshooting

### Device not responding

1. Verify your IR controller is working correctly
2. Check the device code matches your device model
3. Ensure the IR blaster has line-of-sight to the device
4. Try increasing the `delay` value

### Logs

Enable debug logging to troubleshoot issues:

```yaml
logger:
  default: info
  logs:
    custom_components.smartir: debug
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)

## Credits

- Original project by [smartHomeHub](https://github.com/smartHomeHub/SmartIR)
- All contributors who have submitted device codes

<!-- Badges -->
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/foXaCe/SmartIR.svg?style=for-the-badge
[releases]: https://github.com/foXaCe/SmartIR/releases
[issues]: https://github.com/foXaCe/SmartIR/issues
[license-shield]: https://img.shields.io/github/license/foXaCe/SmartIR.svg?style=for-the-badge
[ci-shield]: https://img.shields.io/github/actions/workflow/status/foXaCe/SmartIR/ci.yml?branch=main&style=for-the-badge
[ci]: https://github.com/foXaCe/SmartIR/actions/workflows/ci.yml
[hassfest-shield]: https://img.shields.io/github/actions/workflow/status/foXaCe/SmartIR/hassfest.yml?branch=main&style=for-the-badge&label=hassfest
[hassfest]: https://github.com/foXaCe/SmartIR/actions/workflows/hassfest.yml
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg?style=for-the-badge
[maintenance]: https://github.com/foXaCe/SmartIR
