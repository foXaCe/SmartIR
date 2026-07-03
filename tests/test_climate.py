"""Tests for SmartIR climate platform."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from custom_components.smartir.climate import (
    DEFAULT_NAME,
    SmartIRClimate,
)


@pytest.fixture
def mock_climate_config() -> dict[str, Any]:
    """Create mock climate configuration."""
    return {
        "unique_id": "test_climate_unique_id",
        "name": "Test Climate",
        "device_code": 1234,
        "controller_data": "remote.test_remote",
        "delay": 0.5,
        "temperature_sensor": "sensor.test_temperature",
        "humidity_sensor": "sensor.test_humidity",
        "power_sensor": "sensor.test_power",
        "power_sensor_restore_state": True,
    }


@pytest.fixture
def mock_climate_device_data_with_commands() -> dict[str, Any]:
    """Create mock climate device data with full commands structure."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Model A", "Model B"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "minTemperature": 16,
        "maxTemperature": 30,
        "precision": 1,
        "operationModes": ["cool", "heat", "auto", "dry", "fan_only"],
        "fanModes": ["auto", "low", "medium", "high"],
        "swingModes": ["off", "vertical"],
        "commands": {
            "off": "test_off_command",
            "on": "test_on_command",
            "cool": {
                "auto": {
                    "off": {"16": "cmd_cool_auto_off_16", "24": "cmd_cool_auto_off_24"},
                    "vertical": {"16": "cmd_cool_auto_vert_16", "24": "cmd_cool_auto_vert_24"},
                },
                "low": {
                    "off": {"16": "cmd_cool_low_off_16"},
                },
            },
            "heat": {
                "auto": {
                    "off": {"20": "cmd_heat_auto_off_20"},
                },
            },
        },
    }


@pytest.fixture
def mock_climate_device_data_no_swing() -> dict[str, Any]:
    """Create mock climate device data without swing modes."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Model C"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "minTemperature": 18,
        "maxTemperature": 28,
        "precision": 1,
        "operationModes": ["cool", "heat"],
        "fanModes": ["auto", "low", "high"],
        "commands": {
            "off": "test_off_command",
            "cool": {
                "auto": {"16": "cmd_cool_auto_16", "24": "cmd_cool_auto_24"},
                "low": {"16": "cmd_cool_low_16"},
            },
            "heat": {
                "auto": {"20": "cmd_heat_auto_20"},
            },
        },
    }


@pytest.fixture
def mock_controller() -> MagicMock:
    """Create a mock controller."""
    controller = MagicMock()
    controller.send = AsyncMock()
    return controller


def create_climate_entity(
    hass: HomeAssistant,
    config: dict[str, Any],
    device_data: dict[str, Any],
    mock_controller: MagicMock,
) -> SmartIRClimate:
    """Create a SmartIRClimate entity with mocked controller."""
    with patch(
        "custom_components.smartir.climate.get_controller",
        return_value=mock_controller,
    ):
        entity = SmartIRClimate(hass, config, device_data)
        # Mock async_write_ha_state to avoid platform issues
        entity.async_write_ha_state = MagicMock()
        return entity


class TestSmartIRClimateInit:
    """Tests for SmartIRClimate initialization."""

    def test_init_basic_properties(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test basic property initialization."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

        assert climate.unique_id == "test_climate_unique_id"
        assert climate.name == "Test Climate"
        assert climate.min_temp == 16
        assert climate.max_temp == 30
        assert climate.temperature_unit == hass.config.units.temperature_unit

    def test_init_hvac_modes(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test HVAC modes initialization."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

        expected_modes = [HVACMode.OFF, HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO, HVACMode.DRY, HVACMode.FAN_ONLY]
        assert climate.hvac_modes == expected_modes

    def test_init_fan_modes(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test fan modes initialization."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

        assert climate.fan_modes == ["auto", "low", "medium", "high"]

    def test_init_swing_modes(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test swing modes initialization."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

        assert climate.swing_modes == ["off", "vertical"]
        assert climate.swing_mode == "off"

    def test_init_no_swing_modes(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_no_swing: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test initialization without swing modes."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_no_swing, mock_controller
        )

        assert climate.swing_modes is None
        assert climate.swing_mode is None

    def test_init_default_values(
        self,
        hass: HomeAssistant,
        mock_controller: MagicMock,
    ) -> None:
        """Test default values when config keys are missing."""
        minimal_config = {
            "device_code": 1234,
            "controller_data": "remote.test_remote",
        }
        device_data = {
            "manufacturer": "Test",
            "supportedModels": ["Model"],
            "supportedController": "Broadlink",
            "commandsEncoding": "Base64",
            "minTemperature": 16,
            "maxTemperature": 30,
            "precision": 1,
            "operationModes": ["cool"],
            "fanModes": ["auto"],
            "commands": {"off": "cmd", "cool": {"auto": {"16": "cmd"}}},
        }

        climate = create_climate_entity(hass, minimal_config, device_data, mock_controller)

        assert climate.name == DEFAULT_NAME
        assert climate.unique_id is None


class TestSmartIRClimateProperties:
    """Tests for SmartIRClimate properties."""

    def test_supported_features_with_swing(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test supported features with swing mode."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

        expected = (
            ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
        )
        assert climate.supported_features == expected

    def test_supported_features_without_swing(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_no_swing: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test supported features without swing mode."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_no_swing, mock_controller
        )

        expected = (
            ClimateEntityFeature.TURN_OFF
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
        )
        assert climate.supported_features == expected

    def test_device_info(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test device info property."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

        device_info = climate.device_info
        assert device_info["name"] == "Test Climate"
        assert device_info["manufacturer"] == "Test Manufacturer"
        assert device_info["model"] == "Model A, Model B"
        assert "1234" in device_info["sw_version"]

    def test_extra_state_attributes(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test extra state attributes property."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

        attrs = climate.extra_state_attributes
        assert attrs["device_code"] == 1234
        assert attrs["manufacturer"] == "Test Manufacturer"
        assert attrs["supported_models"] == ["Model A", "Model B"]
        assert attrs["supported_controller"] == "Broadlink"
        assert attrs["commands_encoding"] == "Base64"

    def test_target_temperature_step(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test target temperature step property."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

        assert climate.target_temperature_step == 1


class TestSmartIRClimateIcon:
    """Tests for SmartIRClimate icon property."""

    @pytest.fixture
    def climate_entity(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity for testing."""
        return create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )

    def test_icon_off(self, climate_entity: SmartIRClimate) -> None:
        """Test icon when off."""
        climate_entity._hvac_mode = HVACMode.OFF
        assert climate_entity.icon == "mdi:thermostat-off"

    def test_icon_heat(self, climate_entity: SmartIRClimate) -> None:
        """Test icon in heat mode."""
        climate_entity._hvac_mode = HVACMode.HEAT
        assert climate_entity.icon == "mdi:fire"

    def test_icon_cool(self, climate_entity: SmartIRClimate) -> None:
        """Test icon in cool mode."""
        climate_entity._hvac_mode = HVACMode.COOL
        assert climate_entity.icon == "mdi:snowflake"

    def test_icon_auto(self, climate_entity: SmartIRClimate) -> None:
        """Test icon in auto mode."""
        climate_entity._hvac_mode = HVACMode.AUTO
        assert climate_entity.icon == "mdi:thermostat-auto"

    def test_icon_dry(self, climate_entity: SmartIRClimate) -> None:
        """Test icon in dry mode."""
        climate_entity._hvac_mode = HVACMode.DRY
        assert climate_entity.icon == "mdi:water-percent"

    def test_icon_fan_only(self, climate_entity: SmartIRClimate) -> None:
        """Test icon in fan_only mode."""
        climate_entity._hvac_mode = HVACMode.FAN_ONLY
        assert climate_entity.icon == "mdi:fan"

    def test_icon_heat_cool(self, climate_entity: SmartIRClimate) -> None:
        """Test icon in heat_cool mode."""
        climate_entity._hvac_mode = HVACMode.HEAT_COOL
        assert climate_entity.icon == "mdi:thermostat"

    def test_icon_unknown_mode(self, climate_entity: SmartIRClimate) -> None:
        """Test icon for unknown mode falls back to default."""
        climate_entity._hvac_mode = "unknown_mode"
        assert climate_entity.icon == "mdi:thermostat"


class TestSmartIRClimateState:
    """Tests for SmartIRClimate state property."""

    def test_state_when_off(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test state property when off."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )
        climate._hvac_mode = HVACMode.OFF

        assert climate.state == HVACMode.OFF

    def test_state_when_cooling(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test state property when cooling."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )
        climate._hvac_mode = HVACMode.COOL

        assert climate.state == HVACMode.COOL


class TestSmartIRClimateSetTemperature:
    """Tests for SmartIRClimate async_set_temperature method."""

    @pytest.fixture
    def climate_entity(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity for testing."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        return climate

    async def test_set_temperature_valid(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting a valid temperature."""
        await climate_entity.async_set_temperature(temperature=24)

        assert climate_entity.target_temperature == 24
        # Controller sends "on" command then mode command
        assert mock_controller.send.call_count >= 1

    async def test_set_temperature_rounds_to_whole(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test that temperature is rounded to whole number with precision 1."""
        await climate_entity.async_set_temperature(temperature=23.7)

        assert climate_entity.target_temperature == 24

    async def test_set_temperature_below_min(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting temperature below minimum is ignored."""
        await climate_entity.async_set_temperature(temperature=10)

        assert climate_entity.target_temperature == 16  # unchanged from min
        mock_controller.send.assert_not_called()

    async def test_set_temperature_above_max(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting temperature above maximum is ignored."""
        await climate_entity.async_set_temperature(temperature=35)

        assert climate_entity.target_temperature == 16  # unchanged from min
        mock_controller.send.assert_not_called()

    async def test_set_temperature_none(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting temperature with None value."""
        await climate_entity.async_set_temperature(temperature=None)

        mock_controller.send.assert_not_called()

    async def test_set_temperature_with_hvac_mode(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting temperature also sets HVAC mode when provided."""
        await climate_entity.async_set_temperature(temperature=24, hvac_mode=HVACMode.HEAT)

        assert climate_entity.target_temperature == 24
        assert climate_entity.hvac_mode == HVACMode.HEAT


class TestSmartIRClimateSetHvacMode:
    """Tests for SmartIRClimate async_set_hvac_mode method."""

    @pytest.fixture
    def climate_entity(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity for testing."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        return climate

    async def test_set_hvac_mode_cool(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting HVAC mode to cool."""
        await climate_entity.async_set_hvac_mode(HVACMode.COOL)

        assert climate_entity.hvac_mode == HVACMode.COOL
        assert climate_entity.last_on_operation == HVACMode.COOL
        mock_controller.send.assert_called()

    async def test_set_hvac_mode_off(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting HVAC mode to off."""
        climate_entity._last_on_operation = HVACMode.COOL
        await climate_entity.async_set_hvac_mode(HVACMode.OFF)

        assert climate_entity.hvac_mode == HVACMode.OFF
        assert climate_entity.last_on_operation == HVACMode.COOL  # unchanged

    async def test_set_hvac_mode_updates_last_on_operation(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test that setting non-off mode updates last_on_operation."""
        assert climate_entity.last_on_operation is None

        await climate_entity.async_set_hvac_mode(HVACMode.HEAT)
        assert climate_entity.last_on_operation == HVACMode.HEAT

        await climate_entity.async_set_hvac_mode(HVACMode.COOL)
        assert climate_entity.last_on_operation == HVACMode.COOL


class TestSmartIRClimateSetFanMode:
    """Tests for SmartIRClimate async_set_fan_mode method."""

    @pytest.fixture
    def climate_entity(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity for testing."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        climate._target_temperature = 24
        return climate

    async def test_set_fan_mode(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting fan mode."""
        await climate_entity.async_set_fan_mode("high")

        assert climate_entity.fan_mode == "high"
        mock_controller.send.assert_called_once()

    async def test_set_fan_mode_when_off(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting fan mode when HVAC is off doesn't send command."""
        climate_entity._hvac_mode = HVACMode.OFF
        await climate_entity.async_set_fan_mode("high")

        assert climate_entity.fan_mode == "high"
        mock_controller.send.assert_not_called()


class TestSmartIRClimateSetSwingMode:
    """Tests for SmartIRClimate async_set_swing_mode method."""

    @pytest.fixture
    def climate_entity(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity for testing."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        climate._target_temperature = 24
        return climate

    async def test_set_swing_mode(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting swing mode."""
        await climate_entity.async_set_swing_mode("vertical")

        assert climate_entity.swing_mode == "vertical"
        # Controller sends "on" command then mode command
        assert mock_controller.send.call_count >= 1

    async def test_set_swing_mode_when_off(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting swing mode when HVAC is off doesn't send command."""
        climate_entity._hvac_mode = HVACMode.OFF
        await climate_entity.async_set_swing_mode("vertical")

        assert climate_entity.swing_mode == "vertical"
        mock_controller.send.assert_not_called()


class TestSmartIRClimateTurnOnOff:
    """Tests for SmartIRClimate async_turn_on and async_turn_off methods."""

    @pytest.fixture
    def climate_entity(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity for testing."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        climate._target_temperature = 24
        return climate

    async def test_async_turn_off(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test turning off the climate entity."""
        climate_entity._hvac_mode = HVACMode.COOL
        await climate_entity.async_turn_off()

        assert climate_entity.hvac_mode == HVACMode.OFF

    async def test_async_turn_on_with_last_operation(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on restores last operation mode."""
        climate_entity._last_on_operation = HVACMode.HEAT
        await climate_entity.async_turn_on()

        assert climate_entity.hvac_mode == HVACMode.HEAT

    async def test_async_turn_on_without_last_operation(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on without last operation uses first available mode."""
        climate_entity._last_on_operation = None
        await climate_entity.async_turn_on()

        assert climate_entity.hvac_mode == HVACMode.COOL  # First mode after OFF


class TestSmartIRClimateSendCommand:
    """Tests for SmartIRClimate send_command method."""

    @pytest.fixture
    def climate_entity(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity for testing."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_with_commands, mock_controller
        )
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._current_swing_mode = "off"
        climate._target_temperature = 24
        return climate

    async def test_send_command_off(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test sending off command."""
        climate_entity._hvac_mode = HVACMode.OFF
        await climate_entity.send_command()

        mock_controller.send.assert_called_once_with("test_off_command")

    async def test_send_command_with_swing(
        self,
        climate_entity: SmartIRClimate,
        mock_controller: MagicMock,
    ) -> None:
        """Test sending command with swing mode."""
        climate_entity._hvac_mode = HVACMode.COOL
        climate_entity._current_fan_mode = "auto"
        climate_entity._current_swing_mode = "off"
        climate_entity._target_temperature = 16

        await climate_entity.send_command()

        # Should send "on" command first, then the operation command
        assert mock_controller.send.call_count == 2

    async def test_send_command_without_swing(
        self,
        hass: HomeAssistant,
        mock_climate_config: dict[str, Any],
        mock_climate_device_data_no_swing: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test sending command without swing mode."""
        climate = create_climate_entity(
            hass, mock_climate_config, mock_climate_device_data_no_swing, mock_controller
        )
        climate._hvac_mode = HVACMode.COOL
        climate._current_fan_mode = "auto"
        climate._target_temperature = 16

        await climate.send_command()

        # Should send "on" command (if exists) and operation command
        assert mock_controller.send.call_count >= 1


class TestSmartIRClimateSensors:
    """Tests for SmartIRClimate sensor handling."""

    @pytest.fixture
    def climate_entity_with_sensors(
        self,
        hass: HomeAssistant,
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity with sensors configured."""
        config = {
            "unique_id": "test_climate",
            "name": "Test Climate",
            "device_code": 1234,
            "controller_data": "remote.test_remote",
            "temperature_sensor": "sensor.test_temp",
            "humidity_sensor": "sensor.test_humidity",
            "power_sensor": "sensor.test_power",
        }
        return create_climate_entity(hass, config, mock_climate_device_data_with_commands, mock_controller)

    def test_update_temp_valid(
        self,
        climate_entity_with_sensors: SmartIRClimate,
    ) -> None:
        """Test updating temperature from valid sensor state."""
        mock_state = MagicMock()
        mock_state.state = "22.5"

        climate_entity_with_sensors._async_update_temp(mock_state)

        assert climate_entity_with_sensors.current_temperature == 22.5

    def test_update_temp_unknown(
        self,
        climate_entity_with_sensors: SmartIRClimate,
    ) -> None:
        """Test updating temperature from unknown state."""
        mock_state = MagicMock()
        mock_state.state = STATE_UNKNOWN

        climate_entity_with_sensors._async_update_temp(mock_state)

        assert climate_entity_with_sensors.current_temperature is None

    def test_update_temp_unavailable(
        self,
        climate_entity_with_sensors: SmartIRClimate,
    ) -> None:
        """Test updating temperature from unavailable state."""
        mock_state = MagicMock()
        mock_state.state = STATE_UNAVAILABLE

        climate_entity_with_sensors._async_update_temp(mock_state)

        assert climate_entity_with_sensors.current_temperature is None

    def test_update_temp_invalid(
        self,
        climate_entity_with_sensors: SmartIRClimate,
    ) -> None:
        """Test updating temperature from invalid state."""
        mock_state = MagicMock()
        mock_state.state = "invalid"

        climate_entity_with_sensors._async_update_temp(mock_state)

        assert climate_entity_with_sensors.current_temperature is None

    def test_update_humidity_valid(
        self,
        climate_entity_with_sensors: SmartIRClimate,
    ) -> None:
        """Test updating humidity from valid sensor state."""
        mock_state = MagicMock()
        mock_state.state = "65"

        climate_entity_with_sensors._async_update_humidity(mock_state)

        assert climate_entity_with_sensors.current_humidity == 65.0

    def test_update_humidity_unknown(
        self,
        climate_entity_with_sensors: SmartIRClimate,
    ) -> None:
        """Test updating humidity from unknown state."""
        mock_state = MagicMock()
        mock_state.state = STATE_UNKNOWN

        climate_entity_with_sensors._async_update_humidity(mock_state)

        assert climate_entity_with_sensors.current_humidity is None


class TestSmartIRClimatePowerSensor:
    """Tests for SmartIRClimate power sensor handling."""

    @pytest.fixture
    def climate_entity_with_power_sensor(
        self,
        hass: HomeAssistant,
        mock_climate_device_data_with_commands: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRClimate:
        """Create a climate entity with power sensor configured."""
        config = {
            "unique_id": "test_climate",
            "name": "Test Climate",
            "device_code": 1234,
            "controller_data": "remote.test_remote",
            "power_sensor": "sensor.test_power",
            "power_sensor_restore_state": True,
        }
        climate = create_climate_entity(hass, config, mock_climate_device_data_with_commands, mock_controller)
        climate._last_on_operation = HVACMode.COOL
        return climate

    async def test_power_sensor_turns_on(
        self,
        climate_entity_with_power_sensor: SmartIRClimate,
    ) -> None:
        """Test power sensor turning on activates climate."""
        climate_entity_with_power_sensor._hvac_mode = HVACMode.OFF

        new_state = MagicMock()
        new_state.state = STATE_ON
        old_state = MagicMock()
        old_state.state = STATE_OFF

        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state, "entity_id": "sensor.test_power"}

        await climate_entity_with_power_sensor._async_power_sensor_changed(event)

        assert climate_entity_with_power_sensor.hvac_mode == HVACMode.COOL

    async def test_power_sensor_turns_off(
        self,
        climate_entity_with_power_sensor: SmartIRClimate,
    ) -> None:
        """Test power sensor turning off deactivates climate."""
        climate_entity_with_power_sensor._hvac_mode = HVACMode.COOL

        new_state = MagicMock()
        new_state.state = STATE_OFF
        old_state = MagicMock()
        old_state.state = STATE_ON

        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state, "entity_id": "sensor.test_power"}

        await climate_entity_with_power_sensor._async_power_sensor_changed(event)

        assert climate_entity_with_power_sensor.hvac_mode == HVACMode.OFF

    async def test_power_sensor_no_change(
        self,
        climate_entity_with_power_sensor: SmartIRClimate,
    ) -> None:
        """Test power sensor with no state change does nothing."""
        climate_entity_with_power_sensor._hvac_mode = HVACMode.OFF

        new_state = MagicMock()
        new_state.state = STATE_OFF
        old_state = MagicMock()
        old_state.state = STATE_OFF

        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state, "entity_id": "sensor.test_power"}

        await climate_entity_with_power_sensor._async_power_sensor_changed(event)

        assert climate_entity_with_power_sensor.hvac_mode == HVACMode.OFF

    async def test_power_sensor_new_state_none(
        self,
        climate_entity_with_power_sensor: SmartIRClimate,
    ) -> None:
        """Test power sensor with None new state does nothing."""
        climate_entity_with_power_sensor._hvac_mode = HVACMode.COOL

        event = MagicMock()
        event.data = {"new_state": None, "old_state": MagicMock(), "entity_id": "sensor.test_power"}

        await climate_entity_with_power_sensor._async_power_sensor_changed(event)

        assert climate_entity_with_power_sensor.hvac_mode == HVACMode.COOL  # unchanged