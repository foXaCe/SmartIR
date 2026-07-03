"""Tests for the SmartIR fan entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.fan import DIRECTION_FORWARD, DIRECTION_REVERSE, FanEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.percentage import ordered_list_item_to_percentage
import pytest

from custom_components.smartir.api.exceptions import SmartIRControllerError
from custom_components.smartir.const import SmartIRData
from custom_components.smartir.devices.fan import SPEED_OFF, SmartIRFan


def create_fan_entity(
    hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any], controller: MagicMock
) -> SmartIRFan:
    """Create a SmartIRFan entity with a mocked controller."""
    with patch("custom_components.smartir.entity.get_controller", return_value=controller):
        entity = SmartIRFan(hass, data, device_data)
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.fixture
def fan(hass, make_smartir_data, mock_fan_device_data, mock_controller) -> SmartIRFan:
    """A fan entity built without direction/oscillate support (uses 'default')."""
    return create_fan_entity(hass, make_smartir_data(device_type="fan"), mock_fan_device_data, mock_controller)


@pytest.fixture
def fan_full(hass, make_smartir_data, mock_fan_device_data_full, mock_controller) -> SmartIRFan:
    """A fan entity built with direction and oscillate support."""
    return create_fan_entity(hass, make_smartir_data(device_type="fan"), mock_fan_device_data_full, mock_controller)


class TestInit:
    """Tests for SmartIRFan initialization."""

    def test_speed_count(self, fan: SmartIRFan) -> None:
        """speed_count reflects the number of speeds in the device data."""
        assert fan.speed_count == 3

    def test_no_direction_or_oscillate_by_default(self, fan: SmartIRFan) -> None:
        """Without matching commands, direction and oscillate support are disabled."""
        assert fan.current_direction is None
        assert fan.oscillating is None
        assert fan.supported_features == (
            FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
        )

    def test_direction_and_oscillate_enabled_when_supported(self, fan_full: SmartIRFan) -> None:
        """Direction/oscillate support is enabled when the matching commands exist."""
        assert fan_full.current_direction == DIRECTION_REVERSE
        assert fan_full.oscillating is False
        assert fan_full.supported_features == (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.OSCILLATE
        )

    def test_initial_state_is_off(self, fan: SmartIRFan) -> None:
        """The fan starts off with no last-on speed remembered."""
        assert fan.is_on is False
        assert fan.last_on_speed is None
        assert fan.percentage == 0


class TestDeviceInfoAndAttributes:
    """Tests for device_info and extra_state_attributes."""

    def test_device_info(self, fan: SmartIRFan) -> None:
        """device_info reflects the manufacturer/model from the device data."""
        info = fan.device_info
        assert info["manufacturer"] == "Test Manufacturer"
        assert info["model"] == "Fan Model A"

    def test_extra_state_attributes(self, fan: SmartIRFan) -> None:
        """extra_state_attributes exposes the shared metadata plus last_on_speed."""
        attrs = fan.extra_state_attributes
        assert attrs["device_code"] == 1000
        assert attrs["last_on_speed"] is None


class TestPercentageAndSpeed:
    """Tests for percentage/speed helpers."""

    def test_percentage_when_on(self, fan: SmartIRFan) -> None:
        """percentage reflects the currently selected speed."""
        fan._speed = "medium"
        expected = ordered_list_item_to_percentage(["low", "medium", "high"], "medium")
        assert fan.percentage == expected

    def test_percentage_zero_when_off(self, fan: SmartIRFan) -> None:
        """percentage is 0 while off."""
        fan._speed = SPEED_OFF
        assert fan.percentage == 0

    def test_is_on_true_when_on_by_remote(self, fan: SmartIRFan) -> None:
        """is_on is True when detected on by remote even with no speed set."""
        fan._speed = SPEED_OFF
        fan._on_by_remote = True
        assert fan.is_on is True


class TestSetPercentage:
    """Tests for async_set_percentage."""

    async def test_zero_turns_off(self, fan: SmartIRFan, mock_controller: MagicMock) -> None:
        """Setting percentage to 0 turns the fan off."""
        await fan.async_set_percentage(0)
        assert fan.percentage == 0
        assert fan.last_on_speed is None
        mock_controller.send.assert_called_once_with("test_off_command")

    async def test_nonzero_sets_speed_and_remembers_it(self, fan: SmartIRFan, mock_controller: MagicMock) -> None:
        """A non-zero percentage sets the matching speed and remembers it."""
        percentage = ordered_list_item_to_percentage(["low", "medium", "high"], "medium")
        await fan.async_set_percentage(percentage)
        assert fan._speed == "medium"
        assert fan.last_on_speed == "medium"
        mock_controller.send.assert_called_once_with("test_medium_command")

    async def test_writes_state(self, fan: SmartIRFan) -> None:
        """Setting percentage writes the new state."""
        await fan.async_set_percentage(0)
        fan.async_write_ha_state.assert_called_once()


class TestTurnOnOff:
    """Tests for async_turn_on / async_turn_off."""

    async def test_turn_on_with_percentage(self, fan: SmartIRFan, mock_controller: MagicMock) -> None:
        """An explicit percentage sets the matching speed."""
        percentage = ordered_list_item_to_percentage(["low", "medium", "high"], "high")
        await fan.async_turn_on(percentage=percentage)
        assert fan._speed == "high"
        mock_controller.send.assert_called_once_with("test_high_command")

    async def test_turn_on_without_percentage_uses_last_on_speed(self, fan: SmartIRFan) -> None:
        """Without a percentage, the remembered last-on speed is restored."""
        fan._last_on_speed = "medium"
        await fan.async_turn_on()
        assert fan._speed == "medium"

    async def test_turn_on_without_percentage_or_last_speed_uses_first(self, fan: SmartIRFan) -> None:
        """Without a percentage or remembered speed, the first speed is used."""
        fan._last_on_speed = None
        await fan.async_turn_on()
        assert fan._speed == "low"

    async def test_turn_off(self, fan: SmartIRFan, mock_controller: MagicMock) -> None:
        """Turning off sets the speed to off and sends the off command."""
        fan._speed = "high"
        await fan.async_turn_off()
        assert fan._speed == SPEED_OFF
        mock_controller.send.assert_called_once_with("test_off_command")


class TestOscillate:
    """Tests for async_oscillate."""

    async def test_oscillate_on_sends_oscillate_command(self, fan_full: SmartIRFan, mock_controller: MagicMock) -> None:
        """Enabling oscillation sends the oscillate command."""
        fan_full._speed = "low"
        await fan_full.async_oscillate(True)
        assert fan_full.oscillating is True
        mock_controller.send.assert_called_once_with("cmd_oscillate")

    async def test_oscillate_off_sends_direction_speed_command(
        self, fan_full: SmartIRFan, mock_controller: MagicMock
    ) -> None:
        """Disabling oscillation sends the direction+speed command."""
        fan_full._speed = "low"
        fan_full._direction = DIRECTION_REVERSE
        await fan_full.async_oscillate(False)
        assert fan_full.oscillating is False
        mock_controller.send.assert_called_once_with("cmd_reverse_low")


class TestSetDirection:
    """Tests for async_set_direction."""

    async def test_when_off_updates_state_without_command(
        self, fan_full: SmartIRFan, mock_controller: MagicMock
    ) -> None:
        """Setting direction while off updates state but sends nothing."""
        fan_full._speed = SPEED_OFF
        await fan_full.async_set_direction(DIRECTION_FORWARD)
        assert fan_full.current_direction == DIRECTION_FORWARD
        mock_controller.send.assert_not_called()

    async def test_when_on_sends_command(self, fan_full: SmartIRFan, mock_controller: MagicMock) -> None:
        """Setting direction while running sends the matching command."""
        fan_full._speed = "medium"
        await fan_full.async_set_direction(DIRECTION_FORWARD)
        assert fan_full.current_direction == DIRECTION_FORWARD
        mock_controller.send.assert_called_once_with("cmd_forward_medium")


class TestSendCommand:
    """Tests for send_command."""

    async def test_off(self, fan: SmartIRFan, mock_controller: MagicMock) -> None:
        """The off command is sent when the speed is off."""
        fan._speed = SPEED_OFF
        await fan.send_command()
        mock_controller.send.assert_called_once_with("test_off_command")
        assert fan._on_by_remote is False

    async def test_default_direction(self, fan: SmartIRFan, mock_controller: MagicMock) -> None:
        """The 'default' direction is used when no direction support is enabled."""
        fan._speed = "high"
        await fan.send_command()
        mock_controller.send.assert_called_once_with("test_high_command")

    async def test_oscillate_takes_precedence(self, fan_full: SmartIRFan, mock_controller: MagicMock) -> None:
        """Oscillation takes precedence over direction/speed when enabled."""
        fan_full._speed = "low"
        fan_full._oscillating = True
        await fan_full.send_command()
        mock_controller.send.assert_called_once_with("cmd_oscillate")

    async def test_direction_and_speed(self, fan_full: SmartIRFan, mock_controller: MagicMock) -> None:
        """A direction+speed command is sent when not oscillating."""
        fan_full._speed = "high"
        fan_full._oscillating = False
        fan_full._direction = DIRECTION_REVERSE
        await fan_full.send_command()
        mock_controller.send.assert_called_once_with("cmd_reverse_high")

    async def test_controller_error_raises_home_assistant_error(
        self, fan: SmartIRFan, mock_controller: MagicMock
    ) -> None:
        """A SmartIRControllerError from the controller becomes a HomeAssistantError."""
        fan._speed = "low"
        mock_controller.send.side_effect = SmartIRControllerError("boom")
        with pytest.raises(HomeAssistantError):
            await fan.send_command()


class TestAddedToHass:
    """Tests for async_added_to_hass (state restoration)."""

    async def test_restores_speed_and_last_on_speed(self, fan: SmartIRFan) -> None:
        """A previously stored speed/last_on_speed is restored."""
        last_state = MagicMock()
        last_state.attributes = {"speed": "medium", "last_on_speed": "high"}
        fan.async_get_last_state = AsyncMock(return_value=last_state)

        await fan.async_added_to_hass()

        assert fan._speed == "medium"
        assert fan.last_on_speed == "high"

    async def test_restores_direction_only_when_supported(self, fan_full: SmartIRFan) -> None:
        """The direction is restored only when DIRECTION is a supported feature."""
        last_state = MagicMock()
        last_state.attributes = {"direction": DIRECTION_FORWARD}
        fan_full.async_get_last_state = AsyncMock(return_value=last_state)

        await fan_full.async_added_to_hass()

        assert fan_full.current_direction == DIRECTION_FORWARD

    async def test_no_previous_state_keeps_defaults(self, fan: SmartIRFan) -> None:
        """Without a previous state, defaults are kept."""
        fan.async_get_last_state = AsyncMock(return_value=None)
        await fan.async_added_to_hass()
        assert fan._speed == SPEED_OFF


class TestPowerSensor:
    """Tests for _async_power_sensor_changed."""

    @pytest.fixture
    def fan(self, hass: HomeAssistant, make_smartir_data, mock_fan_device_data, mock_controller) -> SmartIRFan:
        data = make_smartir_data(device_type="fan", power_sensor="sensor.test_power")
        return create_fan_entity(hass, data, mock_fan_device_data, mock_controller)

    def _fire(self, fan: SmartIRFan, new: str | None, old: str | None) -> None:
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(state=new) if new is not None else None,
            "old_state": MagicMock(state=old) if old is not None else None,
        }
        fan._async_power_sensor_changed(event)

    def test_turns_on_by_remote(self, fan: SmartIRFan) -> None:
        """The power sensor turning on while off marks the fan as on by remote."""
        fan._speed = SPEED_OFF
        self._fire(fan, STATE_ON, STATE_OFF)
        assert fan._on_by_remote is True
        assert fan._speed is None
        fan.async_write_ha_state.assert_called_once()

    def test_turns_off(self, fan: SmartIRFan) -> None:
        """The power sensor turning off resets speed and on_by_remote."""
        fan._speed = "low"
        self._fire(fan, STATE_OFF, STATE_ON)
        assert fan._on_by_remote is False
        assert fan._speed == SPEED_OFF

    def test_no_state_change_is_noop(self, fan: SmartIRFan) -> None:
        """Identical old/new states are a no-op."""
        fan._speed = "low"
        self._fire(fan, STATE_ON, STATE_ON)
        assert fan._speed == "low"
        fan.async_write_ha_state.assert_not_called()

    def test_new_state_none_is_noop(self, fan: SmartIRFan) -> None:
        """A None new_state is a no-op."""
        fan._speed = "low"
        self._fire(fan, None, STATE_ON)
        assert fan._speed == "low"
        fan.async_write_ha_state.assert_not_called()


class TestPlatformSetup:
    """Full config-entry setup exercises the thin fan platform."""

    async def test_setup_registers_entity(
        self, hass: HomeAssistant, make_config_entry, mock_fan_device_data, setup_smartir_entry, mock_remote_entity
    ) -> None:
        """Setting up a fan entry registers a fan entity."""
        entry = make_config_entry(device_type="fan")
        result, _ = await setup_smartir_entry(entry, mock_fan_device_data)
        assert result is True
        assert any(state.entity_id.startswith("fan.") for state in hass.states.async_all())
