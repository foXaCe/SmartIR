"""SmartIR climate entity (IR/RF air conditioners)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ATTR_HVAC_MODE, HVAC_MODES, ClimateEntityFeature, HVACMode
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_WHOLE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..api.exceptions import CommandSendError, SmartIRControllerError
from ..const import SmartIRData
from ..entity import SmartIREntity

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (
    ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
)


class SmartIRClimate(SmartIREntity, ClimateEntity):
    """SmartIR climate entity for controlling IR air conditioners."""

    PLATFORM = "climate"

    def __init__(self, hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any]) -> None:
        """Initialize the climate entity from its device-code data."""
        super().__init__(hass, data, device_data)

        self._temperature_sensor = data.temperature_sensor
        self._humidity_sensor = data.humidity_sensor
        self._power_sensor_restore_state = data.power_sensor_restore_state

        self._min_temperature: float = device_data["minTemperature"]
        self._max_temperature: float = device_data["maxTemperature"]
        self._precision: float = device_data["precision"]

        valid_hvac_modes = [HVACMode(x) for x in device_data["operationModes"] if x in HVAC_MODES]
        self._operation_modes: list[HVACMode] = [HVACMode.OFF, *valid_hvac_modes]
        self._fan_modes: list[str] = device_data["fanModes"]
        self._swing_modes: list[str] | None = device_data.get("swingModes")

        self._target_temperature: float = self._min_temperature
        self._hvac_mode: HVACMode = HVACMode.OFF
        self._current_fan_mode: str = self._fan_modes[0]
        self._current_swing_mode: str | None = None
        self._last_on_operation: HVACMode | None = None

        self._current_temperature: float | None = None
        self._current_humidity: float | None = None

        self._unit = hass.config.units.temperature_unit

        self._support_flags = SUPPORT_FLAGS
        self._support_swing = False
        if self._swing_modes:
            self._support_flags |= ClimateEntityFeature.SWING_MODE
            self._current_swing_mode = self._swing_modes[0]
            self._support_swing = True

    async def async_added_to_hass(self) -> None:
        """Restore the previous state and start watching linked sensors."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._hvac_mode = HVACMode(last_state.state)
            except ValueError:
                self._hvac_mode = HVACMode.OFF
            self._current_fan_mode = last_state.attributes["fan_mode"]
            self._current_swing_mode = last_state.attributes.get("swing_mode")
            self._target_temperature = last_state.attributes["temperature"]
            last_on = last_state.attributes.get("last_on_operation")
            if last_on is not None:
                try:
                    self._last_on_operation = HVACMode(last_on)
                except ValueError:
                    self._last_on_operation = None

        if self._temperature_sensor:
            async_track_state_change_event(self.hass, self._temperature_sensor, self._async_temp_sensor_changed)
            temp_state = self.hass.states.get(self._temperature_sensor)
            if temp_state and temp_state.state != STATE_UNKNOWN:
                self._async_update_temp(temp_state)

        if self._humidity_sensor:
            async_track_state_change_event(self.hass, self._humidity_sensor, self._async_humidity_sensor_changed)
            humidity_state = self.hass.states.get(self._humidity_sensor)
            if humidity_state and humidity_state.state != STATE_UNKNOWN:
                self._async_update_humidity(humidity_state)

        if self._power_sensor:
            async_track_state_change_event(self.hass, self._power_sensor, self._async_power_sensor_changed)

    @property
    def icon(self) -> str:
        """Return an icon reflecting the current HVAC mode."""
        return {
            HVACMode.OFF: "mdi:thermostat-off",
            HVACMode.HEAT: "mdi:fire",
            HVACMode.COOL: "mdi:snowflake",
            HVACMode.HEAT_COOL: "mdi:thermostat",
            HVACMode.AUTO: "mdi:thermostat-auto",
            HVACMode.DRY: "mdi:water-percent",
            HVACMode.FAN_ONLY: "mdi:fan",
        }.get(self._hvac_mode, "mdi:thermostat")

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit."""
        return self._unit

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature."""
        return self._min_temperature

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature."""
        return self._max_temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature."""
        return self._target_temperature

    @property
    def target_temperature_step(self) -> float:
        """Return the supported target temperature step."""
        return self._precision

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the available HVAC modes."""
        return self._operation_modes

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        return self._hvac_mode

    @property
    def last_on_operation(self) -> str | None:
        """Return the last non-off operation."""
        return self._last_on_operation

    @property
    def fan_modes(self) -> list[str]:
        """Return the available fan modes."""
        return self._fan_modes

    @property
    def fan_mode(self) -> str:
        """Return the current fan mode."""
        return self._current_fan_mode

    @property
    def swing_modes(self) -> list[str] | None:
        """Return the available swing modes."""
        return self._swing_modes

    @property
    def swing_mode(self) -> str | None:
        """Return the current swing mode."""
        return self._current_swing_mode

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature from the linked sensor."""
        return self._current_temperature

    @property
    def current_humidity(self) -> float | None:
        """Return the current humidity from the linked sensor."""
        return self._current_humidity

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return the supported features."""
        return self._support_flags

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return climate-specific attributes on top of the shared ones."""
        return {**super().extra_state_attributes, "last_on_operation": self._last_on_operation}

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        hvac_mode = kwargs.get(ATTR_HVAC_MODE)
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            return

        if temperature < self._min_temperature or temperature > self._max_temperature:
            _LOGGER.warning("The temperature value is out of min/max range")
            return

        previous_temperature = self._target_temperature
        if self._precision == PRECISION_WHOLE:
            self._target_temperature = round(temperature)
        else:
            self._target_temperature = round(temperature, 1)

        if hvac_mode:
            await self.async_set_hvac_mode(hvac_mode)
            return

        if self._hvac_mode.lower() != HVACMode.OFF:
            try:
                await self.send_command()
            except SmartIRControllerError as err:
                self._target_temperature = previous_temperature
                self.async_write_ha_state()
                raise self._command_error(err) from err

        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC operation mode."""
        previous_mode = self._hvac_mode
        previous_last_on = self._last_on_operation

        self._hvac_mode = hvac_mode
        if hvac_mode != HVACMode.OFF:
            self._last_on_operation = hvac_mode

        try:
            await self.send_command()
        except SmartIRControllerError as err:
            self._hvac_mode = previous_mode
            self._last_on_operation = previous_last_on
            self.async_write_ha_state()
            raise self._command_error(err) from err

        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        previous_fan_mode = self._current_fan_mode
        self._current_fan_mode = fan_mode

        if self._hvac_mode.lower() != HVACMode.OFF:
            try:
                await self.send_command()
            except SmartIRControllerError as err:
                self._current_fan_mode = previous_fan_mode
                self.async_write_ha_state()
                raise self._command_error(err) from err
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""
        previous_swing_mode = self._current_swing_mode
        self._current_swing_mode = swing_mode

        if self._hvac_mode.lower() != HVACMode.OFF:
            try:
                await self.send_command()
            except SmartIRControllerError as err:
                self._current_swing_mode = previous_swing_mode
                self.async_write_ha_state()
                raise self._command_error(err) from err
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the air conditioner off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn the air conditioner on, restoring the last operation."""
        if self._last_on_operation is not None:
            await self.async_set_hvac_mode(self._last_on_operation)
        else:
            await self.async_set_hvac_mode(self._operation_modes[1])

    async def send_command(self) -> None:
        """Resolve and send the IR command for the current state.

        Raises :class:`SmartIRControllerError` when the command cannot be
        delivered, so callers can revert optimistic state.
        """
        async with self._temp_lock:
            self._on_by_remote = False
            operation_mode = self._hvac_mode
            fan_mode = self._current_fan_mode
            swing_mode = self._current_swing_mode
            target_temperature = f"{self._target_temperature:g}"

            if operation_mode.lower() == HVACMode.OFF:
                await self._controller.send(self._commands["off"])
                return

            if "on" in self._commands:
                await self._controller.send(self._commands["on"])
                await asyncio.sleep(self._delay)

            try:
                if self._support_swing:
                    command = self._commands[operation_mode][fan_mode][swing_mode][target_temperature]
                else:
                    command = self._commands[operation_mode][fan_mode][target_temperature]
            except KeyError as err:
                raise CommandSendError(
                    f"No IR command for mode={operation_mode}, fan={fan_mode}, "
                    f"swing={swing_mode}, temp={target_temperature}"
                ) from err

            await self._controller.send(command)

    @callback
    def _async_temp_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle temperature sensor changes."""
        new_state = event.data["new_state"]
        if new_state is None:
            return
        self._async_update_temp(new_state)
        self.async_write_ha_state()

    @callback
    def _async_humidity_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle humidity sensor changes."""
        new_state = event.data["new_state"]
        if new_state is None:
            return
        self._async_update_humidity(new_state)
        self.async_write_ha_state()

    @callback
    def _async_power_sensor_changed(self, event: Event[EventStateChangedData]) -> None:
        """Handle power sensor changes to reflect remote-driven power state."""
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        if new_state is None:
            return
        if old_state is not None and new_state.state == old_state.state:
            return

        if new_state.state == STATE_ON and self._hvac_mode == HVACMode.OFF:
            self._on_by_remote = True
            if self._power_sensor_restore_state and self._last_on_operation is not None:
                self._hvac_mode = self._last_on_operation
            elif len(self._operation_modes) > 1:
                # The device was turned on by remote and we cannot know the exact
                # mode; fall back to the first available operating mode.
                self._hvac_mode = self._operation_modes[1]
            self.async_write_ha_state()

        if new_state.state == STATE_OFF:
            self._on_by_remote = False
            if self._hvac_mode != HVACMode.OFF:
                self._hvac_mode = HVACMode.OFF
            self.async_write_ha_state()

    @callback
    def _async_update_temp(self, state: State) -> None:
        """Update the current temperature from the sensor state."""
        try:
            if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._current_temperature = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from temperature sensor: %s", ex)

    @callback
    def _async_update_humidity(self, state: State) -> None:
        """Update the current humidity from the sensor state."""
        try:
            if state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._current_humidity = float(state.state)
        except ValueError as ex:
            _LOGGER.error("Unable to update from humidity sensor: %s", ex)
