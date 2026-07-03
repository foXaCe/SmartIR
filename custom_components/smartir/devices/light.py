"""SmartIR light entity (IR/RF lights)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..api.exceptions import SmartIRControllerError
from ..const import SmartIRData
from ..entity import SmartIREntity
from ..helpers import closest_match

_LOGGER = logging.getLogger(__name__)

CMD_BRIGHTNESS_INCREASE = "brighten"
CMD_BRIGHTNESS_DECREASE = "dim"
CMD_COLORMODE_COLDER = "colder"
CMD_COLORMODE_WARMER = "warmer"
CMD_POWER_ON = "on"
CMD_POWER_OFF = "off"
CMD_NIGHTLIGHT = "night"


class SmartIRLight(SmartIREntity, LightEntity):
    """SmartIR light entity for controlling IR lights."""

    PLATFORM = "light"

    def __init__(self, hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any]) -> None:
        """Initialize the light entity from its device-code data."""
        super().__init__(hass, data, device_data)

        self._brightnesses: list[int] = device_data["brightness"]
        self._colortemps: list[int] = device_data["colorTemperature"]

        self._power = STATE_ON
        self._brightness: int | None = None
        self._colortemp: int | None = None
        self._support_color_mode = ColorMode.UNKNOWN
        self._support_brightness = False

        if CMD_COLORMODE_COLDER in self._commands and CMD_COLORMODE_WARMER in self._commands:
            self._colortemp = self.max_color_temp_kelvin
            self._support_color_mode = ColorMode.COLOR_TEMP

        if CMD_NIGHTLIGHT in self._commands or (
            CMD_BRIGHTNESS_INCREASE in self._commands and CMD_BRIGHTNESS_DECREASE in self._commands
        ):
            self._brightness = 100
            self._support_brightness = True
            if self._support_color_mode == ColorMode.UNKNOWN:
                self._support_color_mode = ColorMode.BRIGHTNESS

        if (
            CMD_POWER_OFF in self._commands
            and CMD_POWER_ON in self._commands
            and self._support_color_mode == ColorMode.UNKNOWN
        ):
            self._support_color_mode = ColorMode.ONOFF

        self._attr_icon = "mdi:lightbulb"

    async def async_added_to_hass(self) -> None:
        """Restore the previous state and start watching the power sensor."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._power = last_state.state
            if ATTR_BRIGHTNESS in last_state.attributes:
                self._brightness = last_state.attributes[ATTR_BRIGHTNESS]
            if ATTR_COLOR_TEMP_KELVIN in last_state.attributes:
                self._colortemp = last_state.attributes[ATTR_COLOR_TEMP_KELVIN]

        if self._power_sensor:
            async_track_state_change_event(self.hass, self._power_sensor, self._async_power_sensor_changed)

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {self._support_color_mode}

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        return self._support_color_mode

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the current color temperature in Kelvin."""
        return self._colortemp

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the minimum supported color temperature in Kelvin."""
        return self._colortemps[0] if self._colortemps else DEFAULT_MIN_KELVIN

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the maximum supported color temperature in Kelvin."""
        return self._colortemps[-1] if self._colortemps else DEFAULT_MAX_KELVIN

    @property
    def is_on(self) -> bool:
        """Return whether the light is on."""
        return self._power == STATE_ON or self._on_by_remote

    @property
    def brightness(self) -> int | None:
        """Return the current brightness."""
        return self._brightness

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return light-specific attributes on top of the shared ones."""
        return {**super().extra_state_attributes, "on_by_remote": self._on_by_remote}

    async def async_turn_on(self, **params: Any) -> None:
        """Turn the light on, applying brightness/color-temperature steps."""
        did_something = False

        if self._power != STATE_ON and not self._on_by_remote:
            self._power = STATE_ON
            did_something = True
            await self.send_command(CMD_POWER_ON)

        if ATTR_COLOR_TEMP_KELVIN in params and self._support_color_mode == ColorMode.COLOR_TEMP:
            target = params.get(ATTR_COLOR_TEMP_KELVIN)
            old_color_temp = closest_match(self._colortemp, self._colortemps)
            new_color_temp = closest_match(target, self._colortemps)

            steps = new_color_temp - old_color_temp
            did_something = True
            if steps < 0:
                cmd = CMD_COLORMODE_WARMER
                steps = abs(steps)
            else:
                cmd = CMD_COLORMODE_COLDER

            if steps > 0 and cmd:
                # Resync by going the full range when heading for an extreme.
                if new_color_temp in (len(self._colortemps) - 1, 0):
                    steps = len(self._colortemps)
                self._colortemp = self._colortemps[new_color_temp]
                await self.send_command(cmd, steps)

        if ATTR_BRIGHTNESS in params and self._support_brightness:
            # Special case: brightness of 1 maps to the night light, if fitted.
            if params.get(ATTR_BRIGHTNESS) == 1 and CMD_NIGHTLIGHT in self._commands:
                self._brightness = 1
                self._power = STATE_ON
                did_something = True
                await self.send_command(CMD_NIGHTLIGHT)

            elif self._brightnesses:
                target = params.get(ATTR_BRIGHTNESS)
                old_brightness = closest_match(self._brightness, self._brightnesses)
                new_brightness = closest_match(target, self._brightnesses)
                did_something = True
                steps = new_brightness - old_brightness
                if steps < 0:
                    cmd = CMD_BRIGHTNESS_DECREASE
                    steps = abs(steps)
                else:
                    cmd = CMD_BRIGHTNESS_INCREASE

                if steps > 0 and cmd:
                    # Resync by going the full range when heading for an extreme.
                    if new_brightness in (len(self._brightnesses) - 1, 0):
                        steps = len(self._colortemps)
                    self._brightness = self._brightnesses[new_brightness]
                    await self.send_command(cmd, steps)

        # If nothing happened and the light is not known to be on, issue the on
        # command anyway (we may be out of sync when there is no power monitor).
        if not did_something and not self._on_by_remote:
            self._power = STATE_ON
            await self.send_command(CMD_POWER_ON)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._power = STATE_OFF
        await self.send_command(CMD_POWER_OFF)
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the light."""
        await (self.async_turn_off() if self.is_on else self.async_turn_on())

    async def send_command(self, cmd: str, count: int = 1) -> None:
        """Send ``cmd`` ``count`` times through the controller."""
        if cmd not in self._commands:
            _LOGGER.error("Unknown command '%s'", cmd)
            return
        remote_cmd = self._commands[cmd]
        async with self._temp_lock:
            self._on_by_remote = False
            try:
                for _ in range(count):
                    await self._controller.send(remote_cmd)
            except SmartIRControllerError as err:
                raise self._command_error(err) from err

    @callback
    def _async_power_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle power sensor changes to reflect remote-driven power state."""
        new_state = event.data["new_state"]
        if new_state is None:
            return
        old_state = event.data["old_state"]
        if old_state is not None and new_state.state == old_state.state:
            return

        if new_state.state == STATE_ON:
            self._on_by_remote = True
            self.async_write_ha_state()

        if new_state.state == STATE_OFF:
            self._on_by_remote = False
            self._power = STATE_OFF
            self.async_write_ha_state()
