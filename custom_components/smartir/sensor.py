"""SmartIR Hub sensor platform."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SmartIRConfigEntry

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartIRConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartIR hub sensor from a config entry."""
    # Hub functionality is currently disabled
    # TODO: Re-enable when SmartIRHub is implemented
    pass


class SmartIRHubSensor(SensorEntity):
    """Sensor entity for SmartIR Hub status."""

    _attr_has_entity_name = True

    def __init__(self, hub):
        """Initialize the hub sensor."""
        self._hub = hub
        self._attr_unique_id = f"{DOMAIN}_hub_status"
        self._attr_name = "SmartIR Hub"
        self._attr_icon = "mdi:hub"
        self._attr_state_class = None

    @property
    def device_info(self):
        """Return device information."""
        return self._hub.device_info

    @property
    def state(self):
        """Return the state of the hub."""
        return self._hub.devices_count

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "devices"

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "devices_count": self._hub.devices_count,
            "active_devices": list(self._hub.active_devices),
            "integration_version": "1.18.1",
            "domain": DOMAIN,
            "status": "online" if self._hub.devices_count > 0 else "idle",
        }

    @property
    def available(self):
        """Return if the hub is available."""
        return True
