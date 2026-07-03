"""Helper functions for SmartIR."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
import hashlib
from typing import TYPE_CHECKING, Any

from .const import SmartIRConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

PlatformSetupFn = Callable[["HomeAssistant", dict[str, Any], "AddEntitiesCallback"], Awaitable[None]]


async def async_setup_entry_platform(
    hass: HomeAssistant,
    entry: SmartIRConfigEntry,
    async_add_entities: AddEntitiesCallback,
    platform_setup_fn: PlatformSetupFn,
) -> None:
    """Set up a SmartIR platform from a config entry."""
    data = entry.runtime_data

    # Generate a stable unique_id if the config entry does not carry one.
    unique_id = data.unique_id
    if not unique_id:
        unique_string = f"smartir_{data.device_type}_{data.device_code}_{data.controller_data}"
        digest = hashlib.md5(unique_string.encode(), usedforsecurity=False).hexdigest()[:16]
        unique_id = f"smartir_{digest}"

    # Build config dict for backward compatibility with the platform setup functions.
    config: dict[str, Any] = {
        "device_type": data.device_type,
        "controller": data.controller_type,
        "name": data.name,
        "device_code": data.device_code,
        "controller_data": data.controller_data,
        "delay": data.delay,
        "temperature_sensor": data.temperature_sensor,
        "humidity_sensor": data.humidity_sensor,
        "power_sensor": data.power_sensor,
        "power_sensor_restore_state": data.power_sensor_restore_state,
        "unique_id": unique_id,
    }

    await platform_setup_fn(hass, config, async_add_entities)
