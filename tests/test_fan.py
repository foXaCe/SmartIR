"""Tests for SmartIR fan platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.fan import DIRECTION_FORWARD, DIRECTION_REVERSE, FanEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import pytest

from custom_components.smartir.const import CONF_CONTROLLER_TYPE, CONTROLLER_TYPES
from custom_components.smartir.fan import (
    SPEED_OFF,
    SmartIRFan,
    async_setup_platform,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_fan_config() -> dict[str, Any]:
    """Create mock fan configuration."""
    return {
        "unique_id": "test_fan_unique_id",
        "name": "Test Fan",
        "device_code": 5678,
        "controller_data": "remote.test_remote",
        "delay": 0.5,
        "power_sensor": "sensor.test_power",
    }


@pytest.fixture
def mock_fan_device_data_default() -> dict[str, Any]:
    """Fan device data without direction or oscillate support (uses 'default' direction)."""
    return {
        "manufacturer": "Test Fan Manufacturer",
        "supportedModels": ["Fan Model A", "Fan Model B"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "speed": ["low", "medium", "high"],
        "commands": {
            "off": "cmd_off",
            "default": {
                "low": "cmd_default_low",
                "medium": "cmd_default_medium",
                "high": "cmd_default_high",
            },
        },
    }


@pytest.fixture
def mock_fan_device_data_full() -> dict[str, Any]:
    """Fan device data with direction and oscillate support."""
    return {
        "manufacturer": "Test Fan Manufacturer",
        "supportedModels": ["Fan Model C"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "speed": ["low", "medium", "high"],
        "commands": {
            "off": "cmd_off",
            "oscillate": "cmd_oscillate",
            "forward": {
                "low": "cmd_forward_low",
                "medium": "cmd_forward_medium",
                "high": "cmd_forward_high",
            },
            "reverse": {
                "low": "cmd_reverse_low",
                "medium": "cmd_reverse_medium",
                "high": "cmd_reverse_high",
            },
        },
    }


@pytest.fixture
def mock_controller() -> MagicMock:
    """Create a mock IR/RF controller."""
    controller = MagicMock()
    controller.send = AsyncMock()
    return controller


def create_fan_entity(
    hass: HomeAssistant,
    config: dict[str, Any],
    device_data: dict[str, Any],
    mock_controller: MagicMock,
) -> SmartIRFan:
    """Create a SmartIRFan entity with a mocked controller."""
    with patch(
        "custom_components.smartir.fan.get_controller",
        return_value=mock_controller,
    ):
        entity = SmartIRFan(hass, config, device_data)
        # Mock async_write_ha_state to avoid platform issues
        entity.async_write_ha_state = MagicMock()
        return entity


# ---------------------------------------------------------------------------
# async_setup_platform
# ---------------------------------------------------------------------------


class TestAsyncSetupPlatform:
    """Tests for async_setup_platform."""

    async def _patched_setup(self, hass, config, device_data, mock_controller, *, file_exists=True, isdir=True):
        """Run async_setup_platform with disk/network access fully mocked."""
        async_add_entities = MagicMock()
        json_content = json.dumps(device_data)

        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value=json_content)
        mock_file_cm = MagicMock()
        mock_file_cm.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("custom_components.smartir.fan.os.path.isdir", return_value=isdir),
            patch("custom_components.smartir.fan.os.makedirs") as mock_makedirs,
            patch("custom_components.smartir.fan.os.path.exists", return_value=file_exists),
            patch("custom_components.smartir.fan.aiofiles.open", return_value=mock_file_cm),
            patch("custom_components.smartir.fan.get_controller", return_value=mock_controller),
        ):
            await async_setup_platform(hass, config, async_add_entities)

        return async_add_entities, mock_makedirs

    async def test_creates_entity_from_existing_file(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that an entity is created when the device JSON already exists on disk."""
        async_add_entities, _ = await self._patched_setup(
            hass, mock_fan_config, mock_fan_device_data_default, mock_controller
        )

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], SmartIRFan)
        assert entities[0].unique_id == "test_fan_unique_id"

    async def test_creates_directory_when_missing(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that the codes directory is created when missing."""
        async_add_entities, mock_makedirs = await self._patched_setup(
            hass, mock_fan_config, mock_fan_device_data_default, mock_controller, isdir=False
        )

        mock_makedirs.assert_called_once()
        async_add_entities.assert_called_once()

    async def test_downloads_when_file_missing(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that the device file is downloaded when not present locally."""
        async_add_entities_mock = MagicMock()
        json_content = json.dumps(mock_fan_device_data_default)

        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value=json_content)
        mock_file_cm = MagicMock()
        mock_file_cm.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("custom_components.smartir.fan.os.path.isdir", return_value=True),
            patch("custom_components.smartir.fan.os.path.exists", return_value=False),
            patch(
                "custom_components.smartir.fan.Helper.downloader",
                new_callable=AsyncMock,
            ) as mock_downloader,
            patch("custom_components.smartir.fan.aiofiles.open", return_value=mock_file_cm),
            patch("custom_components.smartir.fan.get_controller", return_value=mock_controller),
        ):
            await async_setup_platform(hass, mock_fan_config, async_add_entities_mock)

        mock_downloader.assert_called_once()
        async_add_entities_mock.assert_called_once()

    async def test_download_failure_aborts_setup(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
    ) -> None:
        """Test that a download failure aborts setup without raising."""
        async_add_entities_mock = MagicMock()

        with (
            patch("custom_components.smartir.fan.os.path.isdir", return_value=True),
            patch("custom_components.smartir.fan.os.path.exists", return_value=False),
            patch(
                "custom_components.smartir.fan.Helper.downloader",
                new_callable=AsyncMock,
                side_effect=Exception("network unreachable"),
            ),
        ):
            await async_setup_platform(hass, mock_fan_config, async_add_entities_mock)

        async_add_entities_mock.assert_not_called()

    async def test_invalid_json_aborts_setup(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
    ) -> None:
        """Test that invalid JSON content aborts setup without raising."""
        async_add_entities_mock = MagicMock()

        mock_file = AsyncMock()
        mock_file.read = AsyncMock(return_value="not valid json")
        mock_file_cm = MagicMock()
        mock_file_cm.__aenter__ = AsyncMock(return_value=mock_file)
        mock_file_cm.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("custom_components.smartir.fan.os.path.isdir", return_value=True),
            patch("custom_components.smartir.fan.os.path.exists", return_value=True),
            patch("custom_components.smartir.fan.aiofiles.open", return_value=mock_file_cm),
        ):
            await async_setup_platform(hass, mock_fan_config, async_add_entities_mock)

        async_add_entities_mock.assert_not_called()

    async def test_controller_type_override_from_config_entry(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that controller_type in config overrides the JSON supportedController."""
        config = dict(mock_fan_config)
        config[CONF_CONTROLLER_TYPE] = "xiaomi"

        async_add_entities, _ = await self._patched_setup(hass, config, mock_fan_device_data_default, mock_controller)

        entities = async_add_entities.call_args[0][0]
        assert entities[0]._supported_controller == CONTROLLER_TYPES["xiaomi"]


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestSmartIRFanInit:
    """Tests for SmartIRFan initialization."""

    def test_init_basic_properties(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test basic property initialization."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)

        assert fan.unique_id == "test_fan_unique_id"
        assert fan.name == "Test Fan"
        assert fan.speed_count == 3

    def test_init_without_direction_or_oscillate(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that direction and oscillate support are disabled without matching commands."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)

        assert fan.current_direction is None
        assert fan.oscillating is None
        assert fan.supported_features == (
            FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
        )

    def test_init_with_direction_and_oscillate(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that direction and oscillate support are enabled when commands are present."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_full, mock_controller)

        assert fan.current_direction == DIRECTION_REVERSE
        assert fan.oscillating is False
        assert fan.supported_features == (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
            | FanEntityFeature.DIRECTION
            | FanEntityFeature.OSCILLATE
        )

    def test_init_default_values(
        self,
        hass: HomeAssistant,
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test default values when optional config keys are missing."""
        minimal_config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
        }

        fan = create_fan_entity(hass, minimal_config, mock_fan_device_data_default, mock_controller)

        assert fan.unique_id is None
        assert fan.name is None
        assert fan.last_on_speed is None
        assert fan.state == SPEED_OFF


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestSmartIRFanProperties:
    """Tests for SmartIRFan properties."""

    @pytest.fixture
    def fan_entity(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRFan:
        """Create a fan entity for testing."""
        return create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)

    def test_device_info(self, fan_entity: SmartIRFan) -> None:
        """Test device info property."""
        device_info = fan_entity.device_info
        assert device_info["name"] == "Test Fan"
        assert device_info["manufacturer"] == "Test Fan Manufacturer"
        assert device_info["model"] == "Fan Model A, Fan Model B"
        assert "5678" in device_info["sw_version"]
        assert ("smartir", "test_fan_unique_id") in device_info["identifiers"]

    def test_device_info_fallback_identifier(
        self,
        hass: HomeAssistant,
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test device info falls back to a generated identifier without unique_id."""
        config = {"device_code": 5678, "controller_data": "remote.test_remote"}
        fan = create_fan_entity(hass, config, mock_fan_device_data_default, mock_controller)

        device_info = fan.device_info
        assert ("smartir", "smartir_fan_5678") in device_info["identifiers"]

    def test_extra_state_attributes(self, fan_entity: SmartIRFan) -> None:
        """Test extra state attributes property."""
        attrs = fan_entity.extra_state_attributes
        assert attrs["device_code"] == 5678
        assert attrs["manufacturer"] == "Test Fan Manufacturer"
        assert attrs["supported_models"] == ["Fan Model A", "Fan Model B"]
        assert attrs["supported_controller"] == "Broadlink"
        assert attrs["commands_encoding"] == "Base64"
        assert attrs["last_on_speed"] is None

    def test_percentage_when_off(self, fan_entity: SmartIRFan) -> None:
        """Test percentage is 0 when the fan is off."""
        assert fan_entity.percentage == 0

    def test_percentage_when_on(self, fan_entity: SmartIRFan) -> None:
        """Test percentage reflects the current speed."""
        from homeassistant.util.percentage import ordered_list_item_to_percentage

        fan_entity._speed = "medium"
        expected = ordered_list_item_to_percentage(["low", "medium", "high"], "medium")
        assert fan_entity.percentage == expected

    def test_speed_count(self, fan_entity: SmartIRFan) -> None:
        """Test speed_count reflects the number of speeds."""
        assert fan_entity.speed_count == 3

    def test_last_on_speed_initially_none(self, fan_entity: SmartIRFan) -> None:
        """Test last_on_speed is None before any speed is set."""
        assert fan_entity.last_on_speed is None


# ---------------------------------------------------------------------------
# Icon
# ---------------------------------------------------------------------------


class TestSmartIRFanIcon:
    """Tests for SmartIRFan icon property."""

    @pytest.fixture
    def fan_entity(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRFan:
        """Create a fan entity with oscillate support for testing."""
        return create_fan_entity(hass, mock_fan_config, mock_fan_device_data_full, mock_controller)

    def test_icon_off(self, fan_entity: SmartIRFan) -> None:
        """Test icon when fan is off."""
        fan_entity._speed = SPEED_OFF
        fan_entity._on_by_remote = False
        assert fan_entity.icon == "mdi:fan-off"

    def test_icon_on_default(self, fan_entity: SmartIRFan) -> None:
        """Test icon when fan is on without oscillation or preset."""
        fan_entity._speed = "low"
        fan_entity._oscillating = False
        assert fan_entity.icon == "mdi:fan"

    def test_icon_on_oscillating(self, fan_entity: SmartIRFan) -> None:
        """Test icon when fan is oscillating."""
        fan_entity._speed = "low"
        fan_entity._oscillating = True
        assert fan_entity.icon == "mdi:rotate-360"

    def test_icon_preset_sleep(self, fan_entity: SmartIRFan) -> None:
        """Test icon for sleep preset mode."""
        fan_entity._speed = "low"
        fan_entity._oscillating = False
        fan_entity._preset_mode = "sleep"
        assert fan_entity.icon == "mdi:sleep"

    def test_icon_preset_nature(self, fan_entity: SmartIRFan) -> None:
        """Test icon for nature preset mode."""
        fan_entity._speed = "low"
        fan_entity._oscillating = False
        fan_entity._preset_mode = "nature"
        assert fan_entity.icon == "mdi:leaf"

    def test_icon_preset_auto(self, fan_entity: SmartIRFan) -> None:
        """Test icon for auto preset mode."""
        fan_entity._speed = "low"
        fan_entity._oscillating = False
        fan_entity._preset_mode = "auto"
        assert fan_entity.icon == "mdi:fan-auto"

    def test_icon_preset_unknown(self, fan_entity: SmartIRFan) -> None:
        """Test icon falls back to default for an unrecognized preset mode."""
        fan_entity._speed = "low"
        fan_entity._oscillating = False
        fan_entity._preset_mode = "turbo"
        assert fan_entity.icon == "mdi:fan"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class TestSmartIRFanState:
    """Tests for SmartIRFan state property."""

    @pytest.fixture
    def fan_entity(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRFan:
        """Create a fan entity for testing."""
        return create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)

    def test_state_off(self, fan_entity: SmartIRFan) -> None:
        """Test state is off when speed is off and not on by remote."""
        fan_entity._speed = SPEED_OFF
        fan_entity._on_by_remote = False
        assert fan_entity.state == SPEED_OFF

    def test_state_on_with_speed(self, fan_entity: SmartIRFan) -> None:
        """Test state is on when speed is set."""
        fan_entity._speed = "low"
        assert fan_entity.state == STATE_ON

    def test_state_on_by_remote(self, fan_entity: SmartIRFan) -> None:
        """Test state is on when turned on by remote even without a speed."""
        fan_entity._speed = SPEED_OFF
        fan_entity._on_by_remote = True
        assert fan_entity.state == STATE_ON


# ---------------------------------------------------------------------------
# async_set_percentage
# ---------------------------------------------------------------------------


class TestSmartIRFanSetPercentage:
    """Tests for SmartIRFan async_set_percentage method."""

    @pytest.fixture
    def fan_entity(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRFan:
        """Create a fan entity for testing."""
        return create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)

    async def test_set_percentage_zero_turns_off(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting percentage to 0 turns the fan off."""
        await fan_entity.async_set_percentage(0)

        assert fan_entity.percentage == 0
        assert fan_entity.last_on_speed is None
        mock_controller.send.assert_called_once_with("cmd_off")

    async def test_set_percentage_sets_speed(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting a non-zero percentage sets the corresponding speed."""
        from homeassistant.util.percentage import ordered_list_item_to_percentage

        percentage = ordered_list_item_to_percentage(["low", "medium", "high"], "medium")
        await fan_entity.async_set_percentage(percentage)

        assert fan_entity._speed == "medium"
        assert fan_entity.last_on_speed == "medium"
        mock_controller.send.assert_called_once_with("cmd_default_medium")

    async def test_set_percentage_writes_state(
        self,
        fan_entity: SmartIRFan,
    ) -> None:
        """Test setting percentage triggers a state write."""
        await fan_entity.async_set_percentage(0)
        fan_entity.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# async_turn_on / async_turn_off
# ---------------------------------------------------------------------------


class TestSmartIRFanTurnOnOff:
    """Tests for SmartIRFan async_turn_on and async_turn_off methods."""

    @pytest.fixture
    def fan_entity(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRFan:
        """Create a fan entity for testing."""
        return create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)

    async def test_turn_on_with_percentage(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on with an explicit percentage."""
        from homeassistant.util.percentage import ordered_list_item_to_percentage

        percentage = ordered_list_item_to_percentage(["low", "medium", "high"], "high")
        await fan_entity.async_turn_on(percentage=percentage)

        assert fan_entity._speed == "high"
        mock_controller.send.assert_called_once_with("cmd_default_high")

    async def test_turn_on_without_percentage_uses_last_on_speed(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on without a percentage restores the last known speed."""
        fan_entity._last_on_speed = "medium"

        await fan_entity.async_turn_on()

        assert fan_entity._speed == "medium"

    async def test_turn_on_without_percentage_or_last_speed_uses_first(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on without percentage or last speed falls back to the first speed."""
        fan_entity._last_on_speed = None

        await fan_entity.async_turn_on()

        assert fan_entity._speed == "low"

    async def test_turn_off(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test turning off the fan."""
        fan_entity._speed = "high"

        await fan_entity.async_turn_off()

        assert fan_entity._speed == SPEED_OFF
        assert fan_entity.state == SPEED_OFF
        mock_controller.send.assert_called_once_with("cmd_off")


# ---------------------------------------------------------------------------
# async_oscillate
# ---------------------------------------------------------------------------


class TestSmartIRFanOscillate:
    """Tests for SmartIRFan async_oscillate method."""

    @pytest.fixture
    def fan_entity(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRFan:
        """Create a fan entity with oscillate support for testing."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_full, mock_controller)
        fan._speed = "low"
        return fan

    async def test_oscillate_on(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test enabling oscillation sends the oscillate command."""
        await fan_entity.async_oscillate(True)

        assert fan_entity.oscillating is True
        mock_controller.send.assert_called_once_with("cmd_oscillate")
        fan_entity.async_write_ha_state.assert_called_once()

    async def test_oscillate_off(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test disabling oscillation sends the direction/speed command."""
        fan_entity._direction = DIRECTION_REVERSE

        await fan_entity.async_oscillate(False)

        assert fan_entity.oscillating is False
        mock_controller.send.assert_called_once_with("cmd_reverse_low")


# ---------------------------------------------------------------------------
# async_set_direction
# ---------------------------------------------------------------------------


class TestSmartIRFanSetDirection:
    """Tests for SmartIRFan async_set_direction method."""

    @pytest.fixture
    def fan_entity(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRFan:
        """Create a fan entity with direction support for testing."""
        return create_fan_entity(hass, mock_fan_config, mock_fan_device_data_full, mock_controller)

    async def test_set_direction_when_off_does_not_send_command(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting direction while off updates state but sends no command."""
        fan_entity._speed = SPEED_OFF

        await fan_entity.async_set_direction(DIRECTION_FORWARD)

        assert fan_entity.current_direction == DIRECTION_FORWARD
        mock_controller.send.assert_not_called()
        fan_entity.async_write_ha_state.assert_called_once()

    async def test_set_direction_when_on_sends_command(
        self,
        fan_entity: SmartIRFan,
        mock_controller: MagicMock,
    ) -> None:
        """Test setting direction while running sends the matching command."""
        fan_entity._speed = "medium"

        await fan_entity.async_set_direction(DIRECTION_FORWARD)

        assert fan_entity.current_direction == DIRECTION_FORWARD
        mock_controller.send.assert_called_once_with("cmd_forward_medium")
        fan_entity.async_write_ha_state.assert_called_once()


# ---------------------------------------------------------------------------
# send_command
# ---------------------------------------------------------------------------


class TestSmartIRFanSendCommand:
    """Tests for SmartIRFan send_command method."""

    async def test_send_command_off(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test sending the off command."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)
        fan._speed = SPEED_OFF

        await fan.send_command()

        mock_controller.send.assert_called_once_with("cmd_off")
        assert fan._on_by_remote is False

    async def test_send_command_default_direction(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test sending a speed command via the 'default' direction."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)
        fan._speed = "high"

        await fan.send_command()

        mock_controller.send.assert_called_once_with("cmd_default_high")

    async def test_send_command_oscillate(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test sending the oscillate command takes precedence over direction/speed."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_full, mock_controller)
        fan._speed = "low"
        fan._oscillating = True

        await fan.send_command()

        mock_controller.send.assert_called_once_with("cmd_oscillate")

    async def test_send_command_direction_and_speed(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test sending a direction+speed command when not oscillating."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_full, mock_controller)
        fan._speed = "high"
        fan._oscillating = False
        fan._direction = DIRECTION_REVERSE

        await fan.send_command()

        mock_controller.send.assert_called_once_with("cmd_reverse_high")

    async def test_send_command_resets_on_by_remote(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that sending any command resets the on_by_remote flag."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)
        fan._speed = "low"
        fan._on_by_remote = True

        await fan.send_command()

        assert fan._on_by_remote is False

    async def test_send_command_handles_controller_exception(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that a controller exception is caught and does not propagate."""
        fan = create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)
        fan._speed = "low"
        mock_controller.send.side_effect = Exception("boom")

        # Should not raise.
        await fan.send_command()

        mock_controller.send.assert_called_once()


# ---------------------------------------------------------------------------
# _async_power_sensor_changed
# ---------------------------------------------------------------------------


class TestSmartIRFanPowerSensor:
    """Tests for SmartIRFan power sensor handling."""

    @pytest.fixture
    def fan_entity(
        self,
        hass: HomeAssistant,
        mock_fan_config: dict[str, Any],
        mock_fan_device_data_default: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRFan:
        """Create a fan entity for testing."""
        return create_fan_entity(hass, mock_fan_config, mock_fan_device_data_default, mock_controller)

    async def test_power_sensor_turns_on_by_remote(
        self,
        fan_entity: SmartIRFan,
    ) -> None:
        """Test the power sensor turning on while fan is off marks it as on by remote."""
        fan_entity._speed = SPEED_OFF

        new_state = MagicMock()
        new_state.state = STATE_ON
        old_state = MagicMock()
        old_state.state = STATE_OFF

        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state, "entity_id": "sensor.test_power"}

        await fan_entity._async_power_sensor_changed(event)

        assert fan_entity._on_by_remote is True
        assert fan_entity._speed is None
        fan_entity.async_write_ha_state.assert_called_once()

    async def test_power_sensor_turns_off(
        self,
        fan_entity: SmartIRFan,
    ) -> None:
        """Test the power sensor turning off resets speed and on_by_remote."""
        fan_entity._speed = "low"
        fan_entity._on_by_remote = False

        new_state = MagicMock()
        new_state.state = STATE_OFF
        old_state = MagicMock()
        old_state.state = STATE_ON

        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state, "entity_id": "sensor.test_power"}

        await fan_entity._async_power_sensor_changed(event)

        assert fan_entity._on_by_remote is False
        assert fan_entity._speed == SPEED_OFF
        fan_entity.async_write_ha_state.assert_called_once()

    async def test_power_sensor_no_state_change(
        self,
        fan_entity: SmartIRFan,
    ) -> None:
        """Test that no action is taken when old and new states are identical."""
        fan_entity._speed = "low"

        new_state = MagicMock()
        new_state.state = STATE_ON
        old_state = MagicMock()
        old_state.state = STATE_ON

        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state, "entity_id": "sensor.test_power"}

        await fan_entity._async_power_sensor_changed(event)

        assert fan_entity._speed == "low"
        fan_entity.async_write_ha_state.assert_not_called()

    async def test_power_sensor_new_state_none(
        self,
        fan_entity: SmartIRFan,
    ) -> None:
        """Test that a None new_state is a no-op."""
        fan_entity._speed = "low"

        event = MagicMock()
        event.data = {"new_state": None, "old_state": MagicMock(), "entity_id": "sensor.test_power"}

        await fan_entity._async_power_sensor_changed(event)

        assert fan_entity._speed == "low"
        fan_entity.async_write_ha_state.assert_not_called()
