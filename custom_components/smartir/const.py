"""Constants for the SmartIR integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

DOMAIN = "smartir"
VERSION = "1.18.1"

CONF_CONTROLLER_TYPE = "controller_type"
CONF_DEVICE_TYPE = "device_type"
CONF_NAME = "name"
CONF_UNIQUE_ID = "unique_id"
CONF_DEVICE_CODE = "device_code"
CONF_CONTROLLER_DATA = "controller_data"
CONF_DELAY = "delay"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_HUMIDITY_SENSOR = "humidity_sensor"
CONF_POWER_SENSOR = "power_sensor"
CONF_POWER_SENSOR_RESTORE_STATE = "power_sensor_restore_state"

CONTROLLER_TYPES = {
    "broadlink": "Broadlink",
    "xiaomi": "Xiaomi IR Remote (ChuangmiIr)",
    "lookin": "LOOK.in Remote",
    "esphome": "ESPHome User-defined service for remote transmitter",
    "mqtt": "MQTT Publish service",
}

DEVICE_TYPES = {
    "climate": "Climate (Air Conditioner)",
    "fan": "Fan",
    "media_player": "Media Player (TV/Audio)",
    "light": "Light",
}


@dataclass(slots=True)
class SmartIRData:
    """Runtime data for SmartIR integration."""

    device_type: str
    controller_type: str
    name: str
    device_code: int
    controller_data: str
    delay: float = 0.5
    temperature_sensor: str | None = None
    humidity_sensor: str | None = None
    power_sensor: str | None = None
    power_sensor_restore_state: bool = False
    unique_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


# Type alias for ConfigEntry with SmartIR runtime data
type SmartIRConfigEntry = ConfigEntry[SmartIRData]
