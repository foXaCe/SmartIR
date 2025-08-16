"""SmartIR Hub sensor platform."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hub import SmartIRHubEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SmartIR hub sensor from a config entry."""
    # Only create hub sensor for the first entry or a specific hub entry
    if "hub" in hass.data[DOMAIN]:
        hub = hass.data[DOMAIN]["hub"]
        
        # Check if hub sensor already exists
        existing_sensors = [
            entity for entity in hass.data.get("entity_registry", {}).get("entities", {}).values()
            if entity.get("unique_id") == f"{DOMAIN}_hub_status"
        ]
        
        if not existing_sensors:
            hub_sensor = SmartIRHubSensor(hub)
            async_add_entities([hub_sensor])
            _LOGGER.info("SmartIR Hub sensor created")


class SmartIRHubSensor(SensorEntity):
    """Sensor entity for SmartIR Hub status."""
    
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
            "status": "online" if self._hub.devices_count > 0 else "idle"
        }
    
    @property
    def available(self):
        """Return if the hub is available."""
        return True