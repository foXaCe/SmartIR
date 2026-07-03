"""SmartIR light platform (config-entry setup only)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SmartIRConfigEntry
from .devices.light import SmartIRLight
from .entity import async_setup_smartir_platform

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartIRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SmartIR light entity from a config entry."""
    await async_setup_smartir_platform(hass, entry, async_add_entities, "light", SmartIRLight)
