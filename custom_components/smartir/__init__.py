"""The SmartIR integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_CONTROLLER_DATA,
    CONF_CONTROLLER_TYPE,
    CONF_DELAY,
    CONF_DEVICE_CLASS,
    CONF_DEVICE_CODE,
    CONF_DEVICE_TYPE,
    CONF_HUMIDITY_SENSOR,
    CONF_NAME,
    CONF_POWER_SENSOR,
    CONF_POWER_SENSOR_RESTORE_STATE,
    CONF_SOURCE_NAMES,
    CONF_TEMPERATURE_SENSOR,
    DEFAULT_DELAY,
    DOMAIN,
    SmartIRConfigEntry,
    SmartIRData,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_update_options(hass: HomeAssistant, entry: SmartIRConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: SmartIRConfigEntry) -> bool:
    """Migrate a config entry to the current version.

    v1 → v2: the entity unique_id and device identifier are re-keyed from the
    legacy ``smartir_{type}_{code}_{controller}`` scheme onto the config entry id
    (``{entry_id}_{device_type}`` / ``(DOMAIN, entry_id)``), so they stay stable
    across controller/code changes and multiple instances.
    """
    if entry.version > 2:
        # Downgrade from a newer schema is not supported.
        return False

    if entry.version == 1:
        device_type = {**entry.data, **entry.options}.get(CONF_DEVICE_TYPE, "climate")
        new_unique_id = f"{entry.entry_id}_{device_type}"

        @callback
        def _migrate_unique_id(reg_entry: er.RegistryEntry) -> dict[str, str] | None:
            if reg_entry.unique_id == new_unique_id:
                return None
            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, entry.entry_id, _migrate_unique_id)

        device_reg = dr.async_get(hass)
        new_identifiers = {(DOMAIN, entry.entry_id)}
        for device in dr.async_entries_for_config_entry(device_reg, entry.entry_id):
            if device.identifiers != new_identifiers:
                device_reg.async_update_device(device.id, new_identifiers=new_identifiers)

        hass.config_entries.async_update_entry(entry, version=2)
        _LOGGER.info("Migrated SmartIR entry '%s' to version 2", entry.title)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: SmartIRConfigEntry) -> bool:
    """Set up SmartIR from a config entry."""
    config_data = {**entry.data, **entry.options}

    device_type = config_data.get(CONF_DEVICE_TYPE, "climate")
    device_name = config_data.get(CONF_NAME, f"SmartIR {device_type.title()}")
    controller_data = config_data.get(CONF_CONTROLLER_DATA, "")

    # test-before-setup: the IR/RF controller entity must be available.
    if controller_data and hass.states.get(controller_data) is None:
        raise ConfigEntryNotReady(f"Controller entity '{controller_data}' is not available yet")

    extra = {key: config_data[key] for key in (CONF_DEVICE_CLASS, CONF_SOURCE_NAMES) if key in config_data}

    entry.runtime_data = SmartIRData(
        device_type=device_type,
        controller_type=config_data.get(CONF_CONTROLLER_TYPE, ""),
        name=device_name,
        device_code=int(config_data.get(CONF_DEVICE_CODE, 0)),
        controller_data=controller_data,
        entry_id=entry.entry_id,
        delay=config_data.get(CONF_DELAY, DEFAULT_DELAY),
        temperature_sensor=config_data.get(CONF_TEMPERATURE_SENSOR),
        humidity_sensor=config_data.get(CONF_HUMIDITY_SENSOR),
        power_sensor=config_data.get(CONF_POWER_SENSOR),
        power_sensor_restore_state=config_data.get(CONF_POWER_SENSOR_RESTORE_STATE, False),
        unique_id=entry.unique_id,
        extra=extra,
    )

    await hass.config_entries.async_forward_entry_setups(entry, [device_type])
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartIRConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [entry.runtime_data.device_type])
