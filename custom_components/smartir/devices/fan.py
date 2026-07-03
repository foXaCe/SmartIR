"""SmartIR fan entity (IR/RF fans)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import DIRECTION_FORWARD, DIRECTION_REVERSE, FanEntity, FanEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.percentage import ordered_list_item_to_percentage, percentage_to_ordered_list_item

from ..api.exceptions import SmartIRControllerError
from ..const import SmartIRData
from ..entity import SmartIREntity

SPEED_OFF = "off"


class SmartIRFan(SmartIREntity, FanEntity):
    """SmartIR fan entity for controlling IR fans."""

    PLATFORM = "fan"

    def __init__(self, hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any]) -> None:
        """Initialize the fan entity from its device-code data."""
        super().__init__(hass, data, device_data)

        self._speed_list = device_data["speed"]

        self._speed: str | None = SPEED_OFF
        self._direction: str | None = None
        self._last_on_speed: str | None = None
        self._oscillating: bool | None = None
        self._support_flags = FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON

        if DIRECTION_REVERSE in self._commands and DIRECTION_FORWARD in self._commands:
            self._direction = DIRECTION_REVERSE
            self._support_flags |= FanEntityFeature.DIRECTION
        if "oscillate" in self._commands:
            self._oscillating = False
            self._support_flags |= FanEntityFeature.OSCILLATE

        self._attr_icon = "mdi:fan"

    async def async_added_to_hass(self) -> None:
        """Restore the previous state and start watching the power sensor."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            if "speed" in last_state.attributes:
                self._speed = last_state.attributes["speed"]
            # If _direction has a value the direction controls appear in the UI
            # even if DIRECTION is not in the flags.
            if "direction" in last_state.attributes and self._support_flags & FanEntityFeature.DIRECTION:
                self._direction = last_state.attributes["direction"]
            if "last_on_speed" in last_state.attributes:
                self._last_on_speed = last_state.attributes["last_on_speed"]

            if self._power_sensor:
                async_track_state_change_event(self.hass, self._power_sensor, self._async_power_sensor_changed)

    @property
    def is_on(self) -> bool:
        """Return whether the fan is on."""
        return self._on_by_remote or self._speed not in (SPEED_OFF, None)

    @property
    def percentage(self) -> int:
        """Return the current speed as a percentage."""
        if self._speed in (SPEED_OFF, None):
            return 0
        return ordered_list_item_to_percentage(self._speed_list, self._speed)

    @property
    def speed_count(self) -> int:
        """Return the number of supported speeds."""
        return len(self._speed_list)

    @property
    def oscillating(self) -> bool | None:
        """Return the oscillation state."""
        return self._oscillating

    @property
    def current_direction(self) -> str | None:
        """Return the direction state."""
        return self._direction

    @property
    def last_on_speed(self) -> str | None:
        """Return the last non-off speed."""
        return self._last_on_speed

    @property
    def supported_features(self) -> FanEntityFeature:
        """Return the supported features."""
        return self._support_flags

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return fan-specific attributes on top of the shared ones."""
        return {**super().extra_state_attributes, "last_on_speed": self._last_on_speed}

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the fan speed as a percentage."""
        if percentage == 0:
            self._speed = SPEED_OFF
        else:
            self._speed = percentage_to_ordered_list_item(self._speed_list, percentage)

        if self._speed != SPEED_OFF:
            self._last_on_speed = self._speed

        await self.send_command()
        self.async_write_ha_state()

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        self._oscillating = oscillating
        await self.send_command()
        self.async_write_ha_state()

    async def async_set_direction(self, direction: str) -> None:
        """Set the fan direction."""
        self._direction = direction
        if self._speed is not None and self._speed.lower() != SPEED_OFF:
            await self.send_command()
        self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on."""
        if percentage is None:
            percentage = ordered_list_item_to_percentage(self._speed_list, self._last_on_speed or self._speed_list[0])
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.async_set_percentage(0)

    async def send_command(self) -> None:
        """Resolve and send the IR command for the current fan state."""
        async with self._temp_lock:
            self._on_by_remote = False
            speed = self._speed or SPEED_OFF
            direction = self._direction or "default"
            oscillating = self._oscillating

            if speed.lower() == SPEED_OFF:
                command = self._commands["off"]
            elif oscillating:
                command = self._commands["oscillate"]
            else:
                command = self._commands[direction][speed]

            try:
                await self._controller.send(command)
            except SmartIRControllerError as err:
                raise self._command_error(err) from err

    @callback
    def _async_power_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle power sensor changes to reflect remote-driven power state."""
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        if new_state is None:
            return
        if old_state is not None and new_state.state == old_state.state:
            return

        if new_state.state == STATE_ON and self._speed == SPEED_OFF:
            self._on_by_remote = True
            self._speed = None
            self.async_write_ha_state()

        if new_state.state == STATE_OFF:
            self._on_by_remote = False
            if self._speed != SPEED_OFF:
                self._speed = SPEED_OFF
            self.async_write_ha_state()
