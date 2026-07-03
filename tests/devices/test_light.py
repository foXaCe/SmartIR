"""Tests for the SmartIR light entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DEFAULT_MAX_KELVIN,
    DEFAULT_MIN_KELVIN,
    ColorMode,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.smartir.api.exceptions import SmartIRControllerError
from custom_components.smartir.const import SmartIRData
from custom_components.smartir.devices.light import SmartIRLight


def create_light_entity(
    hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any], controller: MagicMock
) -> SmartIRLight:
    """Create a SmartIRLight entity with a mocked controller."""
    with patch("custom_components.smartir.entity.get_controller", return_value=controller):
        entity = SmartIRLight(hass, data, device_data)
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.fixture
def light(hass, make_smartir_data, mock_light_device_data, mock_controller) -> SmartIRLight:
    """A light with color-temperature, brightness and night-light support."""
    return create_light_entity(hass, make_smartir_data(device_type="light"), mock_light_device_data, mock_controller)


class TestInit:
    """Tests for SmartIRLight initialization and color modes."""

    def test_color_temp_mode(self, light: SmartIRLight) -> None:
        """colder/warmer commands enable COLOR_TEMP and preset the max color temp."""
        assert light.color_mode == ColorMode.COLOR_TEMP
        assert light.supported_color_modes == {ColorMode.COLOR_TEMP}
        assert light.color_temp_kelvin == 6500

    def test_brightness_only_mode(
        self, hass, make_smartir_data, mock_light_device_data_brightness_only, mock_controller
    ):
        """brighten/dim without color temp enable BRIGHTNESS mode."""
        light = create_light_entity(
            hass, make_smartir_data(device_type="light"), mock_light_device_data_brightness_only, mock_controller
        )
        assert light.color_mode == ColorMode.BRIGHTNESS
        assert light.brightness == 100

    def test_night_only_mode(self, hass, make_smartir_data, mock_light_device_data_night_only, mock_controller):
        """A night command alone enables BRIGHTNESS support."""
        light = create_light_entity(
            hass, make_smartir_data(device_type="light"), mock_light_device_data_night_only, mock_controller
        )
        assert light.color_mode == ColorMode.BRIGHTNESS

    def test_onoff_only_mode(self, hass, make_smartir_data, mock_light_device_data_onoff_only, mock_controller):
        """Only on/off commands fall back to ONOFF mode."""
        light = create_light_entity(
            hass, make_smartir_data(device_type="light"), mock_light_device_data_onoff_only, mock_controller
        )
        assert light.color_mode == ColorMode.ONOFF

    def test_color_temp_bounds(self, light: SmartIRLight) -> None:
        """min/max color temperature come from the device data."""
        assert light.min_color_temp_kelvin == 2700
        assert light.max_color_temp_kelvin == 6500

    def test_color_temp_bounds_default_without_color_temp(
        self, hass, make_smartir_data, mock_light_device_data_onoff_only, mock_controller
    ):
        """Without color temperatures, the HA defaults are returned."""
        light = create_light_entity(
            hass, make_smartir_data(device_type="light"), mock_light_device_data_onoff_only, mock_controller
        )
        assert light.min_color_temp_kelvin == DEFAULT_MIN_KELVIN
        assert light.max_color_temp_kelvin == DEFAULT_MAX_KELVIN

    def test_is_on_defaults_true(self, light: SmartIRLight) -> None:
        """A fresh light assumes it is on (state restored later)."""
        assert light.is_on is True


class TestDeviceInfoAndAttributes:
    """Tests for device_info and extra_state_attributes."""

    def test_device_info(self, light: SmartIRLight) -> None:
        """device_info reflects the manufacturer/model from the device data."""
        info = light.device_info
        assert info["manufacturer"] == "Test Manufacturer"
        assert info["model"] == "Light Model A, Light Model B"

    def test_extra_state_attributes(self, light: SmartIRLight) -> None:
        """extra_state_attributes exposes the shared metadata plus on_by_remote."""
        attrs = light.extra_state_attributes
        assert attrs["device_code"] == 1000
        assert attrs["on_by_remote"] is False


class TestTurnOnOff:
    """Tests for async_turn_on / async_turn_off."""

    async def test_turn_off(self, light: SmartIRLight, mock_controller: MagicMock) -> None:
        """Turning off sets power off and sends the off command."""
        await light.async_turn_off()
        assert light.is_on is False
        mock_controller.send.assert_called_once_with("cmd_off")

    async def test_turn_on_from_off_sends_on(self, light: SmartIRLight, mock_controller: MagicMock) -> None:
        """Turning on from off sends the on command."""
        light._power = STATE_OFF
        await light.async_turn_on()
        assert light.is_on is True
        mock_controller.send.assert_any_call("cmd_on")

    async def test_turn_on_color_temp_sends_warmer(self, light: SmartIRLight, mock_controller: MagicMock) -> None:
        """Lowering the color temperature sends 'warmer' step(s)."""
        light._power = STATE_ON
        light._colortemp = 6500
        await light.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 2700})
        mock_controller.send.assert_any_call("cmd_warmer")

    async def test_turn_on_brightness_sends_step(self, light: SmartIRLight, mock_controller: MagicMock) -> None:
        """Changing brightness sends brighten/dim step commands."""
        light._power = STATE_ON
        light._brightness = 10
        await light.async_turn_on(**{ATTR_BRIGHTNESS: 100})
        mock_controller.send.assert_any_call("cmd_brighten")

    async def test_turn_on_brightness_one_uses_night(self, light: SmartIRLight, mock_controller: MagicMock) -> None:
        """A brightness of 1 maps to the night-light command when available."""
        light._power = STATE_ON
        await light.async_turn_on(**{ATTR_BRIGHTNESS: 1})
        assert light.brightness == 1
        mock_controller.send.assert_any_call("cmd_night")


class TestToggle:
    """Tests for async_toggle."""

    async def test_toggle_when_on_turns_off(self, light: SmartIRLight, mock_controller: MagicMock) -> None:
        """Toggling an on light turns it off."""
        light._power = STATE_ON
        await light.async_toggle()
        assert light.is_on is False

    async def test_toggle_when_off_turns_on(self, light: SmartIRLight) -> None:
        """Toggling an off light turns it on."""
        light._power = STATE_OFF
        light._on_by_remote = False
        await light.async_toggle()
        assert light.is_on is True


class TestSendCommand:
    """Tests for send_command."""

    async def test_unknown_command_is_ignored(self, light: SmartIRLight, mock_controller: MagicMock) -> None:
        """An unknown command is logged and not sent."""
        await light.send_command("does_not_exist")
        mock_controller.send.assert_not_called()

    async def test_command_sent_count_times(self, light: SmartIRLight, mock_controller: MagicMock) -> None:
        """The command is sent 'count' times."""
        await light.send_command("brighten", count=3)
        assert mock_controller.send.call_count == 3

    async def test_controller_error_raises_home_assistant_error(
        self, light: SmartIRLight, mock_controller: MagicMock
    ) -> None:
        """A SmartIRControllerError becomes a HomeAssistantError."""
        mock_controller.send.side_effect = SmartIRControllerError("boom")
        with pytest.raises(HomeAssistantError):
            await light.send_command("on")


class TestAddedToHass:
    """Tests for async_added_to_hass (state restoration)."""

    async def test_restores_state(self, light: SmartIRLight) -> None:
        """Brightness and color temperature are restored from the last state."""
        last_state = MagicMock(state=STATE_OFF)
        last_state.attributes = {ATTR_BRIGHTNESS: 50, ATTR_COLOR_TEMP_KELVIN: 4000}
        light.async_get_last_state = AsyncMock(return_value=last_state)

        await light.async_added_to_hass()

        assert light._power == STATE_OFF
        assert light.brightness == 50
        assert light.color_temp_kelvin == 4000

    async def test_no_previous_state(self, light: SmartIRLight) -> None:
        """Without a previous state the defaults are kept."""
        light.async_get_last_state = AsyncMock(return_value=None)
        await light.async_added_to_hass()
        assert light.is_on is True


class TestPowerSensor:
    """Tests for _async_power_sensor_changed."""

    @pytest.fixture
    def light(self, hass, make_smartir_data, mock_light_device_data, mock_controller) -> SmartIRLight:
        data = make_smartir_data(device_type="light", power_sensor="sensor.test_power")
        return create_light_entity(hass, data, mock_light_device_data, mock_controller)

    def _fire(self, light: SmartIRLight, new: str | None, old: str | None) -> None:
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(state=new) if new is not None else None,
            "old_state": MagicMock(state=old) if old is not None else None,
        }
        light._async_power_sensor_changed(event)

    def test_turns_on_by_remote(self, light: SmartIRLight) -> None:
        """The power sensor turning on marks the light on by remote."""
        self._fire(light, STATE_ON, STATE_OFF)
        assert light._on_by_remote is True

    def test_turns_off(self, light: SmartIRLight) -> None:
        """The power sensor turning off clears the power state."""
        self._fire(light, STATE_OFF, STATE_ON)
        assert light._on_by_remote is False
        assert light._power == STATE_OFF

    def test_no_state_change_is_noop(self, light: SmartIRLight) -> None:
        """Identical old/new states are a no-op."""
        self._fire(light, STATE_ON, STATE_ON)
        light.async_write_ha_state.assert_not_called()


class TestPlatformSetup:
    """Full config-entry setup exercises the thin light platform."""

    async def test_setup_registers_entity(
        self, hass: HomeAssistant, make_config_entry, mock_light_device_data, setup_smartir_entry, mock_remote_entity
    ) -> None:
        """Setting up a light entry registers a light entity."""
        entry = make_config_entry(device_type="light")
        result, _ = await setup_smartir_entry(entry, mock_light_device_data)
        assert result is True
        assert any(state.entity_id.startswith("light.") for state in hass.states.async_all())
