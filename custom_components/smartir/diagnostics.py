"""Diagnostics support for SmartIR."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import DOMAIN, SmartIRConfigEntry

# Keys to redact from diagnostics
TO_REDACT = {
    "controller_data",
    "unique_id",
    "entry_id",
}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: SmartIRConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data

    # Build diagnostics data
    diagnostics_data = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": dict(entry.data),
            "options": dict(entry.options),
            "source": entry.source,
            "unique_id": entry.unique_id,
        },
        "runtime_data": {
            "device_type": data.device_type,
            "controller_type": data.controller_type,
            "name": data.name,
            "device_code": data.device_code,
            "controller_data": data.controller_data,
            "delay": data.delay,
            "temperature_sensor": data.temperature_sensor,
            "humidity_sensor": data.humidity_sensor,
            "power_sensor": data.power_sensor,
            "power_sensor_restore_state": data.power_sensor_restore_state,
            "unique_id": data.unique_id,
        },
        "integration_info": {
            "domain": DOMAIN,
            "device_type": data.device_type,
            "controller_type": data.controller_type,
            "device_code": data.device_code,
        },
    }

    # Redact sensitive data
    return async_redact_data(diagnostics_data, TO_REDACT)
