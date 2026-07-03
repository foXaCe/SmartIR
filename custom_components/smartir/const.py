"""Constants for the SmartIR integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

DOMAIN: Final = "smartir"

# Base URL of the device-code database (downloaded on demand and cached locally
# under <component>/codes/<platform>/<code>.json).
CODES_BASE_URL: Final = "https://raw.githubusercontent.com/foXaCe/SmartIR/main/codes"

# User directory (under the HA config dir, resolved via hass.config.path) that
# holds custom device codes. It survives integration updates and takes priority
# over the bundled/downloaded codes.
CUSTOM_CODES_DIR: Final = "smartir_custom_codes"

# Default inter-command delay, in seconds.
DEFAULT_DELAY: Final = 0.5

# Configuration keys (single source of truth — do NOT redefine in platforms).
CONF_CONTROLLER_TYPE: Final = "controller"
CONF_DEVICE_TYPE: Final = "device_type"
CONF_NAME: Final = "name"
CONF_UNIQUE_ID: Final = "unique_id"
CONF_DEVICE_CODE: Final = "device_code"
CONF_CONTROLLER_DATA: Final = "controller_data"
CONF_DELAY: Final = "delay"
CONF_TEMPERATURE_SENSOR: Final = "temperature_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_POWER_SENSOR: Final = "power_sensor"
CONF_POWER_SENSOR_RESTORE_STATE: Final = "power_sensor_restore_state"
CONF_SOURCE_NAMES: Final = "source_names"
CONF_DEVICE_CLASS: Final = "device_class"

CONTROLLER_TYPES: Final[dict[str, str]] = {
    "broadlink": "Broadlink",
    "xiaomi": "Xiaomi IR Remote (ChuangmiIr)",
    "lookin": "LOOK.in Remote",
    "esphome": "ESPHome User-defined service for remote transmitter",
    "mqtt": "MQTT Publish service",
}

DEVICE_TYPES: Final[dict[str, str]] = {
    "climate": "Climate (Air Conditioner)",
    "fan": "Fan",
    "media_player": "Media Player (TV/Audio)",
    "light": "Light",
}


@dataclass(slots=True)
class SmartIRData:
    """Runtime data for a SmartIR config entry."""

    device_type: str
    controller_type: str
    name: str
    device_code: int
    controller_data: str
    entry_id: str
    delay: float = DEFAULT_DELAY
    temperature_sensor: str | None = None
    humidity_sensor: str | None = None
    power_sensor: str | None = None
    power_sensor_restore_state: bool = False
    unique_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# Type alias for a ConfigEntry carrying SmartIR runtime data.
type SmartIRConfigEntry = ConfigEntry[SmartIRData]
