"""Base entity and shared platform setup for SmartIR."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api import async_load_device_data, get_controller
from .api.exceptions import DeviceDataError, DeviceDataNotFound
from .const import CONTROLLER_TYPES, DOMAIN, SmartIRConfigEntry, SmartIRData


async def async_setup_smartir_platform(
    hass: HomeAssistant,
    entry: SmartIRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    platform: str,
    entity_cls: type[SmartIREntity],
) -> None:
    """Load the device-code data and add the single entity for this entry.

    Raises :class:`ConfigEntryNotReady` if the device code cannot be downloaded
    (transient — HA retries). A malformed code file (:class:`DeviceDataError`)
    fails setup permanently, as it requires user intervention.
    """
    data = entry.runtime_data
    issue_id = f"device_data_{entry.entry_id}"

    try:
        device_data = await async_load_device_data(hass, platform, data.device_code)
    except (DeviceDataNotFound, DeviceDataError) as err:
        # Surface a repair issue guiding the user to fix the device code, then
        # let HA retry (network may recover; a genuinely wrong code stays broken
        # and the issue tells the user to reconfigure).
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="device_data_unavailable",
            translation_placeholders={"code": str(data.device_code), "platform": platform},
        )
        raise ConfigEntryNotReady(str(err)) from err

    ir.async_delete_issue(hass, DOMAIN, issue_id)

    # The controller selected in the config flow overrides the one declared in
    # the device-code file (the user knows which blaster they actually own).
    if data.controller_type in CONTROLLER_TYPES:
        device_data["supportedController"] = CONTROLLER_TYPES[data.controller_type]

    async_add_entities([entity_cls(hass, data, device_data)])


class SmartIREntity(RestoreEntity):
    """Base class shared by all SmartIR entities.

    Holds the runtime data, the resolved IR/RF controller and a consistent
    device registry entry. Subclasses set :attr:`PLATFORM` and add their own
    platform-specific state and services.
    """

    _attr_has_entity_name = True
    _attr_name = None
    PLATFORM: str = ""

    def __init__(self, hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any]) -> None:
        """Initialize the shared entity state."""
        self.hass = hass
        self._data = data
        self._device_code = data.device_code
        self._controller_data = data.controller_data
        self._delay = data.delay
        self._power_sensor = data.power_sensor

        self._manufacturer: str = device_data["manufacturer"]
        self._supported_models: list[str] = device_data["supportedModels"]
        self._supported_controller: str = device_data["supportedController"]
        self._commands_encoding: str = device_data["commandsEncoding"]
        self._commands: dict[str, Any] = device_data["commands"]

        self._on_by_remote = False
        self._temp_lock = asyncio.Lock()

        # unique_id/device identity are keyed on the config entry id (v2 format),
        # migrated from the legacy "smartir_{type}_{code}_{controller}" scheme by
        # async_migrate_entry in __init__.py.
        self._attr_unique_id = f"{data.entry_id}_{self.PLATFORM}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, data.entry_id)},
            name=data.name,
            manufacturer=self._manufacturer,
            model=", ".join(self._supported_models) if self._supported_models else "Unknown",
            configuration_url=(
                f"https://github.com/foXaCe/SmartIR/blob/main/codes/{self.PLATFORM}/{self._device_code}.json"
            ),
        )

        self._controller = get_controller(
            hass,
            self._supported_controller,
            self._commands_encoding,
            self._controller_data,
            self._delay,
        )

    def _command_error(self, err: Exception) -> HomeAssistantError:
        """Return a translatable error for a failed IR/RF command delivery."""
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"error": str(err)},
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device-code metadata shared by all SmartIR entities."""
        return {
            "device_code": self._device_code,
            "manufacturer": self._manufacturer,
            "supported_models": self._supported_models,
            "supported_controller": self._supported_controller,
            "commands_encoding": self._commands_encoding,
        }
