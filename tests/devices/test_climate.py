"""Tests for the SmartIR climate entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.smartir.api.exceptions import CommandSendError, SmartIRControllerError
from custom_components.smartir.const import SmartIRData
from custom_components.smartir.devices.climate import SmartIRClimate


def create_climate_entity(
    hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any], controller: MagicMock
) -> SmartIRClimate:
    """Create a SmartIRClimate entity with a mocked controller."""
    with patch("custom_components.smartir.entity.get_controller", return_value=controller):
        entity = SmartIRClimate(hass, data, device_data)
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.fixture
def climate(hass, make_smartir_data, mock_climate_device_data, mock_controller) -> SmartIRClimate:
    """A climate entity built from the full device-data fixture."""
    return create_climate_entity(hass, make_smartir_data(), mock_climate_device_data, mock_controller)


class TestInit:
    """Tests for SmartIRClimate initialization."""

    def test_basic_properties(self, climate: SmartIRClimate) -> None:
        """min/max temperature and the temperature unit are read from the device data."""
        assert climate.min_temp == 16
        assert climate.max_temp == 30
        assert climate.temperature_unit == climate.hass.config.units.temperature_unit
        assert climate.target_temperature == 16
        assert climate.target_temperature_step == 1

    def test_hvac_modes_prepends_off(self, climate: SmartIRClimate) -> None:
        """OFF is always prepended to the operation modes read from the device data."""
        assert climate.hvac_modes == [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.AUTO,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
        ]
        assert climate.hvac_mode == HVACMode.OFF

    def test_fan_modes(self, climate: SmartIRClimate) -> None:
        """Fan modes are read verbatim from the device data."""
        assert climate.fan_modes == ["auto", "low", "medium", "high"]
        assert climate.fan_mode == "auto"

    def test_swing_modes_when_present(self, climate: SmartIRClimate) -> None:
        """Swing support is enabled and initialized to the first swing mode."""
        assert climate.swing_modes == ["off", "vertical"]
        assert climate.swing_mode == "off"
        assert climate.supported_features & ClimateEntityFeature.SWING_MODE

    def test_no_swing_modes(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data_no_swing, mock_controller
    ) -> None:
        """Swing support is disabled when the device data has no swingModes."""
        climate = create_climate_entity(hass, make_smartir_data(), mock_climate_device_data_no_swing, mock_controller)
        assert climate.swing_modes is None
        assert climate.swing_mode is None
        assert not (climate.supported_features & ClimateEntityFeature.SWING_MODE)

    def test_supported_features_without_swing(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data_no_swing, mock_controller
    ) -> None:
        """The base feature set omits SWING_MODE without swing support."""
        climate = create_climate_entity(hass, make_smartir_data(), mock_climate_device_data_no_swing, mock_controller)
        expected = (
            ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
        )
        assert climate.supported_features == expected


class TestDeviceInfoAndAttributes:
    """Tests for device_info and extra_state_attributes."""

    def test_device_info(self, climate: SmartIRClimate) -> None:
        """device_info reflects the entry name/manufacturer/model/config URL."""
        info = climate.device_info
        assert info["name"] == "Test Device"
        assert info["manufacturer"] == "Test Manufacturer"
        assert info["model"] == "Model A, Model B"
        assert "climate/1000.json" in info["configuration_url"]

    def test_extra_state_attributes(self, climate: SmartIRClimate) -> None:
        """extra_state_attributes exposes device-code metadata plus last_on_operation."""
        attrs = climate.extra_state_attributes
        assert attrs["device_code"] == 1000
        assert attrs["manufacturer"] == "Test Manufacturer"
        assert attrs["supported_controller"] == "Broadlink"
        assert attrs["commands_encoding"] == "Base64"
        assert attrs["last_on_operation"] is None


class TestIcon:
    """Tests for the icon property."""

    @pytest.mark.parametrize(
        ("mode", "icon"),
        [
            (HVACMode.OFF, "mdi:thermostat-off"),
            (HVACMode.HEAT, "mdi:fire"),
            (HVACMode.COOL, "mdi:snowflake"),
            (HVACMode.HEAT_COOL, "mdi:thermostat"),
            (HVACMode.AUTO, "mdi:thermostat-auto"),
            (HVACMode.DRY, "mdi:water-percent"),
            (HVACMode.FAN_ONLY, "mdi:fan"),
        ],
    )
    def test_icon_per_mode(self, climate: SmartIRClimate, mode: HVACMode, icon: str) -> None:
        """The icon reflects the current HVAC mode."""
        climate._hvac_mode = mode
        assert climate.icon == icon

    def test_icon_unknown_mode_falls_back(self, climate: SmartIRClimate) -> None:
        """An unrecognized mode falls back to the default thermostat icon."""
        climate._hvac_mode = "unknown_mode"
        assert climate.icon == "mdi:thermostat"


class TestSetTemperature:
    """Tests for async_set_temperature."""

    @pytest.fixture
    def climate(self, climate: SmartIRClimate) -> SmartIRClimate:
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        return climate

    async def test_valid_temperature(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """A valid temperature is applied and a command sent."""
        await climate.async_set_temperature(temperature=24)
        assert climate.target_temperature == 24
        assert mock_controller.send.called

    async def test_rounds_to_whole_with_precision_one(self, climate: SmartIRClimate) -> None:
        """precision=1 rounds the requested temperature to the nearest whole degree."""
        await climate.async_set_temperature(temperature=23.7)
        assert climate.target_temperature == 24

    async def test_below_min_ignored(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """A temperature below the minimum is ignored."""
        await climate.async_set_temperature(temperature=10)
        assert climate.target_temperature == 16
        mock_controller.send.assert_not_called()

    async def test_above_max_ignored(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """A temperature above the maximum is ignored."""
        await climate.async_set_temperature(temperature=35)
        assert climate.target_temperature == 16
        mock_controller.send.assert_not_called()

    async def test_none_ignored(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """No temperature key present is a no-op."""
        await climate.async_set_temperature()
        mock_controller.send.assert_not_called()

    async def test_with_hvac_mode_delegates(self, climate: SmartIRClimate) -> None:
        """Providing hvac_mode alongside temperature also switches the mode."""
        await climate.async_set_temperature(temperature=24, hvac_mode=HVACMode.HEAT)
        assert climate.target_temperature == 24
        assert climate.hvac_mode == HVACMode.HEAT

    async def test_off_mode_does_not_send_command(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """Setting a temperature while off updates the target but sends nothing."""
        climate._hvac_mode = HVACMode.OFF
        await climate.async_set_temperature(temperature=20)
        assert climate.target_temperature == 20
        mock_controller.send.assert_not_called()

    async def test_controller_error_reverts_temperature(
        self, climate: SmartIRClimate, mock_controller: MagicMock
    ) -> None:
        """A failed command reverts the target temperature and raises HomeAssistantError."""
        mock_controller.send.side_effect = SmartIRControllerError("no link")
        with pytest.raises(HomeAssistantError):
            await climate.async_set_temperature(temperature=24)
        assert climate.target_temperature == 16


class TestSetHvacMode:
    """Tests for async_set_hvac_mode."""

    @pytest.fixture
    def climate(self, climate: SmartIRClimate) -> SmartIRClimate:
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        return climate

    async def test_set_cool(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """Setting COOL updates hvac_mode and last_on_operation, and sends a command."""
        await climate.async_set_hvac_mode(HVACMode.COOL)
        assert climate.hvac_mode == HVACMode.COOL
        assert climate.last_on_operation == HVACMode.COOL
        mock_controller.send.assert_called()

    async def test_set_off_keeps_last_on_operation(self, climate: SmartIRClimate) -> None:
        """Turning off does not clear the remembered last-on operation."""
        climate._last_on_operation = HVACMode.COOL
        await climate.async_set_hvac_mode(HVACMode.OFF)
        assert climate.hvac_mode == HVACMode.OFF
        assert climate.last_on_operation == HVACMode.COOL

    async def test_controller_error_reverts_mode(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """A failed command reverts hvac_mode/last_on_operation and raises HomeAssistantError."""
        mock_controller.send.side_effect = SmartIRControllerError("no link")
        with pytest.raises(HomeAssistantError):
            await climate.async_set_hvac_mode(HVACMode.HEAT)
        assert climate.hvac_mode == HVACMode.OFF
        assert climate.last_on_operation is None


class TestSetFanMode:
    """Tests for async_set_fan_mode."""

    @pytest.fixture
    def climate(self, climate: SmartIRClimate) -> SmartIRClimate:
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        climate._target_temperature = 24
        return climate

    async def test_set_fan_mode_sends_command(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """Changing fan mode while on sends a command."""
        await climate.async_set_fan_mode("high")
        assert climate.fan_mode == "high"
        mock_controller.send.assert_called()

    async def test_set_fan_mode_when_off_skips_command(
        self, climate: SmartIRClimate, mock_controller: MagicMock
    ) -> None:
        """Changing fan mode while off updates state but sends nothing."""
        climate._hvac_mode = HVACMode.OFF
        await climate.async_set_fan_mode("high")
        assert climate.fan_mode == "high"
        mock_controller.send.assert_not_called()

    async def test_controller_error_reverts_fan_mode(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """A failed command reverts the fan mode and raises HomeAssistantError."""
        mock_controller.send.side_effect = SmartIRControllerError("no link")
        with pytest.raises(HomeAssistantError):
            await climate.async_set_fan_mode("high")
        assert climate.fan_mode == "auto"


class TestSetSwingMode:
    """Tests for async_set_swing_mode."""

    @pytest.fixture
    def climate(self, climate: SmartIRClimate) -> SmartIRClimate:
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        climate._target_temperature = 24
        return climate

    async def test_set_swing_mode_sends_command(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """Changing swing mode while on sends a command."""
        await climate.async_set_swing_mode("vertical")
        assert climate.swing_mode == "vertical"
        mock_controller.send.assert_called()

    async def test_set_swing_mode_when_off_skips_command(
        self, climate: SmartIRClimate, mock_controller: MagicMock
    ) -> None:
        """Changing swing mode while off updates state but sends nothing."""
        climate._hvac_mode = HVACMode.OFF
        await climate.async_set_swing_mode("vertical")
        assert climate.swing_mode == "vertical"
        mock_controller.send.assert_not_called()

    async def test_controller_error_reverts_swing_mode(
        self, climate: SmartIRClimate, mock_controller: MagicMock
    ) -> None:
        """A failed command reverts the swing mode and raises HomeAssistantError."""
        mock_controller.send.side_effect = SmartIRControllerError("no link")
        with pytest.raises(HomeAssistantError):
            await climate.async_set_swing_mode("vertical")
        assert climate.swing_mode == "off"


class TestTurnOnOff:
    """Tests for async_turn_on / async_turn_off."""

    async def test_turn_off(self, climate: SmartIRClimate) -> None:
        """Turning off delegates to setting HVACMode.OFF."""
        climate._hvac_mode = HVACMode.COOL
        await climate.async_turn_off()
        assert climate.hvac_mode == HVACMode.OFF

    async def test_turn_on_restores_last_operation(self, climate: SmartIRClimate) -> None:
        """Turning on restores the remembered last-on operation."""
        climate._last_on_operation = HVACMode.HEAT
        await climate.async_turn_on()
        assert climate.hvac_mode == HVACMode.HEAT

    async def test_turn_on_without_last_operation_uses_first_mode(self, climate: SmartIRClimate) -> None:
        """Without a remembered operation, the first non-off mode is used."""
        climate._last_on_operation = None
        await climate.async_turn_on()
        assert climate.hvac_mode == HVACMode.COOL


class TestSendCommand:
    """Tests for send_command."""

    @pytest.fixture
    def climate(self, climate: SmartIRClimate) -> SmartIRClimate:
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        climate._target_temperature = 24
        return climate

    async def test_off_sends_single_command(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """Turning off sends only the 'off' command."""
        climate._hvac_mode = HVACMode.OFF
        await climate.send_command()
        mock_controller.send.assert_called_once_with("test_off_command")

    async def test_sends_on_then_mode_command(self, climate: SmartIRClimate, mock_controller: MagicMock) -> None:
        """When an 'on' command exists, it precedes the mode/fan/swing/temp command."""
        await climate.send_command()
        assert mock_controller.send.call_count == 2
        mock_controller.send.assert_any_call("test_on_command")
        mock_controller.send.assert_any_call("cmd_cool_auto_off_24")

    async def test_no_on_command_sends_single_command(
        self,
        hass: HomeAssistant,
        make_smartir_data,
        mock_climate_device_data_no_swing,
        mock_controller: MagicMock,
    ) -> None:
        """Without an 'on' command, only the mode/fan/temp command is sent."""
        climate = create_climate_entity(hass, make_smartir_data(), mock_climate_device_data_no_swing, mock_controller)
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._target_temperature = 18

        await climate.send_command()

        mock_controller.send.assert_called_once_with("cmd_cool_auto_18")

    async def test_missing_command_raises_command_send_error(self, climate: SmartIRClimate) -> None:
        """A fan mode with no matching command raises CommandSendError."""
        climate._current_fan_mode = "turbo"
        with pytest.raises(CommandSendError, match="No IR command"):
            await climate.send_command()

    async def test_resets_on_by_remote(self, climate: SmartIRClimate) -> None:
        """Sending any command clears the on_by_remote flag."""
        climate._on_by_remote = True
        await climate.send_command()
        assert climate._on_by_remote is False


class TestSensorHandling:
    """Tests for temperature/humidity sensor update helpers."""

    def test_update_temp_valid(self, climate: SmartIRClimate) -> None:
        """A valid numeric state updates current_temperature."""
        state = MagicMock(state="22.5")
        climate._async_update_temp(state)
        assert climate.current_temperature == 22.5

    def test_update_temp_unknown(self, climate: SmartIRClimate) -> None:
        """An unknown state is ignored."""
        state = MagicMock(state=STATE_UNKNOWN)
        climate._async_update_temp(state)
        assert climate.current_temperature is None

    def test_update_temp_unavailable(self, climate: SmartIRClimate) -> None:
        """An unavailable state is ignored."""
        state = MagicMock(state=STATE_UNAVAILABLE)
        climate._async_update_temp(state)
        assert climate.current_temperature is None

    def test_update_temp_invalid_value(self, climate: SmartIRClimate) -> None:
        """A non-numeric state is ignored (and logged)."""
        state = MagicMock(state="not-a-number")
        climate._async_update_temp(state)
        assert climate.current_temperature is None

    def test_update_humidity_valid(self, climate: SmartIRClimate) -> None:
        """A valid numeric state updates current_humidity."""
        state = MagicMock(state="65")
        climate._async_update_humidity(state)
        assert climate.current_humidity == 65.0

    def test_update_humidity_unknown(self, climate: SmartIRClimate) -> None:
        """An unknown state is ignored."""
        state = MagicMock(state=STATE_UNKNOWN)
        climate._async_update_humidity(state)
        assert climate.current_humidity is None

    async def test_temp_sensor_changed_event_updates_and_writes_state(self, climate: SmartIRClimate) -> None:
        """The temperature-sensor-changed callback updates state and writes it."""
        event = MagicMock()
        event.data = {"new_state": MagicMock(state="19.5")}
        climate._async_temp_sensor_changed(event)
        assert climate.current_temperature == 19.5
        climate.async_write_ha_state.assert_called_once()

    async def test_temp_sensor_changed_event_none_is_noop(self, climate: SmartIRClimate) -> None:
        """A None new_state is a no-op."""
        event = MagicMock()
        event.data = {"new_state": None}
        climate._async_temp_sensor_changed(event)
        climate.async_write_ha_state.assert_not_called()

    async def test_humidity_sensor_changed_event_updates_and_writes_state(self, climate: SmartIRClimate) -> None:
        """The humidity-sensor-changed callback updates state and writes it."""
        event = MagicMock()
        event.data = {"new_state": MagicMock(state="55")}
        climate._async_humidity_sensor_changed(event)
        assert climate.current_humidity == 55.0
        climate.async_write_ha_state.assert_called_once()

    async def test_humidity_sensor_changed_event_none_is_noop(self, climate: SmartIRClimate) -> None:
        """A None new_state is a no-op."""
        event = MagicMock()
        event.data = {"new_state": None}
        climate._async_humidity_sensor_changed(event)
        climate.async_write_ha_state.assert_not_called()


class TestPowerSensor:
    """Tests for _async_power_sensor_changed."""

    @pytest.fixture
    def climate(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller
    ) -> SmartIRClimate:
        data = make_smartir_data(power_sensor="sensor.test_power", power_sensor_restore_state=True)
        climate = create_climate_entity(hass, data, mock_climate_device_data, mock_controller)
        climate._last_on_operation = HVACMode.COOL
        return climate

    def _fire(self, climate: SmartIRClimate, new: str | None, old: str | None) -> None:
        event = MagicMock()
        event.data = {
            "new_state": MagicMock(state=new) if new is not None else None,
            "old_state": MagicMock(state=old) if old is not None else None,
        }
        climate._async_power_sensor_changed(event)

    async def test_turns_on_restores_last_operation(self, climate: SmartIRClimate) -> None:
        """The power sensor turning on restores the last-on operation (restore_state=True)."""
        climate._hvac_mode = HVACMode.OFF
        self._fire(climate, STATE_ON, STATE_OFF)
        assert climate.hvac_mode == HVACMode.COOL
        assert climate._on_by_remote is True

    async def test_turns_on_without_restore_uses_first_mode(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller
    ) -> None:
        """Without restore_state, the power sensor turning on falls back to the first mode."""
        data = make_smartir_data(power_sensor="sensor.test_power", power_sensor_restore_state=False)
        climate = create_climate_entity(hass, data, mock_climate_device_data, mock_controller)
        climate._hvac_mode = HVACMode.OFF

        self._fire(climate, STATE_ON, STATE_OFF)

        assert climate.hvac_mode == HVACMode.COOL

    async def test_turns_off(self, climate: SmartIRClimate) -> None:
        """The power sensor turning off resets hvac_mode to OFF."""
        climate._hvac_mode = HVACMode.COOL
        self._fire(climate, STATE_OFF, STATE_ON)
        assert climate.hvac_mode == HVACMode.OFF
        assert climate._on_by_remote is False

    async def test_no_state_change_is_noop(self, climate: SmartIRClimate) -> None:
        """Identical old/new states are a no-op."""
        climate._hvac_mode = HVACMode.OFF
        self._fire(climate, STATE_OFF, STATE_OFF)
        assert climate.hvac_mode == HVACMode.OFF
        climate.async_write_ha_state.assert_not_called()

    async def test_new_state_none_is_noop(self, climate: SmartIRClimate) -> None:
        """A None new_state is a no-op."""
        climate._hvac_mode = HVACMode.COOL
        self._fire(climate, None, STATE_ON)
        assert climate.hvac_mode == HVACMode.COOL


class TestAddedToHass:
    """Tests for async_added_to_hass (state restoration)."""

    async def test_restores_previous_state(self, climate: SmartIRClimate) -> None:
        """A previously stored state is fully restored."""
        last_state = MagicMock()
        last_state.state = HVACMode.HEAT
        last_state.attributes = {
            "fan_mode": "high",
            "swing_mode": "vertical",
            "temperature": 25,
            "last_on_operation": HVACMode.HEAT,
        }
        climate.async_get_last_state = AsyncMock(return_value=last_state)

        await climate.async_added_to_hass()

        assert climate.hvac_mode == HVACMode.HEAT
        assert climate.fan_mode == "high"
        assert climate.swing_mode == "vertical"
        assert climate.target_temperature == 25
        assert climate.last_on_operation == HVACMode.HEAT

    async def test_restores_invalid_hvac_mode_as_off(self, climate: SmartIRClimate) -> None:
        """An unrecognized stored hvac_mode falls back to OFF."""
        last_state = MagicMock()
        last_state.state = "not_a_real_mode"
        last_state.attributes = {"fan_mode": "auto", "temperature": 20}
        climate.async_get_last_state = AsyncMock(return_value=last_state)

        await climate.async_added_to_hass()

        assert climate.hvac_mode == HVACMode.OFF

    async def test_restores_invalid_last_on_operation_as_none(self, climate: SmartIRClimate) -> None:
        """An unrecognized stored last_on_operation falls back to None."""
        last_state = MagicMock()
        last_state.state = HVACMode.OFF
        last_state.attributes = {"fan_mode": "auto", "temperature": 20, "last_on_operation": "garbage"}
        climate.async_get_last_state = AsyncMock(return_value=last_state)

        await climate.async_added_to_hass()

        assert climate.last_on_operation is None

    async def test_no_previous_state_keeps_defaults(self, climate: SmartIRClimate) -> None:
        """Without a previous state, the entity keeps its initial defaults."""
        climate.async_get_last_state = AsyncMock(return_value=None)
        await climate.async_added_to_hass()
        assert climate.hvac_mode == HVACMode.OFF

    async def test_tracks_temperature_sensor_and_seeds_initial_value(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller
    ) -> None:
        """A configured temperature sensor with a known state seeds current_temperature."""
        hass.states.async_set("sensor.temp", "21.3")
        data = make_smartir_data(temperature_sensor="sensor.temp")
        climate = create_climate_entity(hass, data, mock_climate_device_data, mock_controller)
        climate.async_get_last_state = AsyncMock(return_value=None)

        await climate.async_added_to_hass()

        assert climate.current_temperature == 21.3

    async def test_tracks_humidity_sensor_and_seeds_initial_value(
        self, hass: HomeAssistant, make_smartir_data, mock_climate_device_data, mock_controller
    ) -> None:
        """A configured humidity sensor with a known state seeds current_humidity."""
        hass.states.async_set("sensor.humidity", "48")
        data = make_smartir_data(humidity_sensor="sensor.humidity")
        climate = create_climate_entity(hass, data, mock_climate_device_data, mock_controller)
        climate.async_get_last_state = AsyncMock(return_value=None)

        await climate.async_added_to_hass()

        assert climate.current_humidity == 48.0
