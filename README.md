# SmartIR

[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/smartHomeHub/SmartIR.svg)](https://github.com/smartHomeHub/SmartIR/releases)

SmartIR is a custom integration for Home Assistant to control IR (infrared) devices such as air conditioners, fans, TVs, and lights using various IR controllers.

## Features

- **Climate Control** - Control air conditioners with temperature, fan modes, swing modes, and HVAC modes
- **Fan Control** - Control fans with speed, direction, and oscillation
- **Media Player** - Control TVs and audio devices with power, volume, source selection
- **Light Control** - Control IR-based lights with brightness and color temperature
- **Multiple Controllers** - Support for Broadlink, Xiaomi, LOOKin, ESPHome, and MQTT controllers
- **State Restoration** - Remembers device states after Home Assistant restarts
- **Power Sensor Integration** - Sync device state with external power sensors

## Supported Controllers

| Controller | Description |
|------------|-------------|
| Broadlink | Broadlink RM series IR blasters |
| Xiaomi | Xiaomi ChuangmiIr IR Remote |
| LOOKin | LOOK.in Remote |
| ESPHome | ESPHome-based IR transmitters |
| MQTT | MQTT-based IR controllers |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add `https://github.com/smartHomeHub/SmartIR` with category "Integration"
5. Search for "SmartIR" and install it
6. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/smartHomeHub/SmartIR/releases)
2. Extract and copy the `custom_components/smartir` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Via UI (Recommended)

1. Go to **Settings** > **Devices & Services**
2. Click **Add Integration**
3. Search for "SmartIR"
4. Follow the configuration wizard:
   - Select device type (Climate, Fan, Media Player, Light)
   - Select your IR controller type
   - Enter the device code and controller entity

### Device Codes

Device codes contain the IR commands for specific devices. Browse available codes:

- [Climate Codes](https://github.com/smartHomeHub/SmartIR/tree/master/codes/climate)
- [Fan Codes](https://github.com/smartHomeHub/SmartIR/tree/master/codes/fan)
- [Media Player Codes](https://github.com/smartHomeHub/SmartIR/tree/master/codes/media_player)
- [Light Codes](https://github.com/smartHomeHub/SmartIR/tree/master/codes/light)

If your device is not listed, you can [create your own device code](https://github.com/smartHomeHub/SmartIR/wiki/Creating-Device-Codes) or request one via GitHub issues.

## Configuration Options

| Option | Description | Default |
|--------|-------------|---------|
| `name` | Friendly name for the device | SmartIR {Type} |
| `device_code` | Device code number | Required |
| `controller_data` | IR controller entity | Required |
| `delay` | Delay between commands (seconds) | 0.5 |
| `temperature_sensor` | External temperature sensor (climate only) | Optional |
| `humidity_sensor` | External humidity sensor (climate only) | Optional |
| `power_sensor` | Power sensor to sync state | Optional |

## Usage Examples

### Climate Control

After setup, your climate device will appear with controls for:
- Power on/off
- Temperature adjustment
- HVAC mode (heat, cool, auto, dry, fan_only)
- Fan speed
- Swing mode (if supported)

### Automation Example

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
2. Check the device code is correct for your device model
3. Ensure the IR blaster has line-of-sight to the device
4. Try increasing the `delay` value

### State not syncing

1. Configure a `power_sensor` to detect device power state
2. Enable `power_sensor_restore_state` for automatic state sync

### Logs

Enable debug logging to troubleshoot issues:

```yaml
logger:
  default: info
  logs:
    custom_components.smartir: debug
```

## Removal

To remove SmartIR from your Home Assistant installation:

### Via HACS

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Find "SmartIR" and click on it
4. Click the three dots menu and select "Remove"
5. Restart Home Assistant

### Manual Removal

1. Delete the `custom_components/smartir` folder from your `config/custom_components/` directory
2. Remove any SmartIR device entries from **Settings** > **Devices & Services**
3. Restart Home Assistant

**Note:** Device codes stored in the `codes/` directory will be preserved. Delete `config/custom_components/smartir/codes/` if you want to remove them as well.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

### Adding Device Codes

See the [wiki](https://github.com/smartHomeHub/SmartIR/wiki) for instructions on creating and submitting device codes.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits

- Original project by [smartHomeHub](https://github.com/smartHomeHub)
- All contributors who have submitted device codes
