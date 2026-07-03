"""SmartIR Hub/Bridge for managing all devices."""

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, VERSION

_LOGGER = logging.getLogger(__name__)


class SmartIRHub:
    """Representation of SmartIR Hub/Bridge device."""

    def __init__(self, hass: HomeAssistant, entry_id: str):
        """Initialize the SmartIR Hub."""
        self.hass = hass
        self.entry_id = entry_id
        self._devices_count = 0
        self._active_devices = set()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the SmartIR Hub."""
        return DeviceInfo(
            identifiers={(DOMAIN, "smartir_hub")},
            name="SmartIR Hub",
            manufacturer="SmartIR",
            model="Integration Hub",
            sw_version=VERSION,
            configuration_url="https://github.com/smartHomeHub/SmartIR",
            entry_type="service",
            suggested_area="System",
        )

    def register_device(self, device_code: str, device_type: str, manufacturer: str = None):
        """Register a new device with the hub."""
        device_id = f"{device_type}_{device_code}"
        if device_id not in self._active_devices:
            self._active_devices.add(device_id)
            self._devices_count += 1

    def unregister_device(self, device_code: str, device_type: str):
        """Unregister a device from the hub."""
        device_id = f"{device_type}_{device_code}"
        if device_id in self._active_devices:
            self._active_devices.remove(device_id)
            self._devices_count -= 1

    @property
    def devices_count(self) -> int:
        """Return the number of registered devices."""
        return self._devices_count

    @property
    def active_devices(self) -> set:
        """Return the set of active device IDs."""
        return self._active_devices.copy()


class SmartIRHubEntity(Entity):
    """Entity representation of the SmartIR Hub for diagnostics."""

    def __init__(self, hub: SmartIRHub):
        """Initialize the hub entity."""
        self._hub = hub
        self._attr_unique_id = f"{DOMAIN}_hub_status"
        self._attr_name = "SmartIR Hub Status"
        self._attr_icon = "mdi:hub"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return self._hub.device_info

    @property
    def state(self) -> str:
        """Return the state of the hub."""
        return "online" if self._hub.devices_count > 0 else "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "devices_count": self._hub.devices_count,
            "active_devices": list(self._hub.active_devices),
            "integration_version": VERSION,
            "domain": DOMAIN,
        }

    @property
    def available(self) -> bool:
        """Return if the hub is available."""
        return True
