"""Tests for SmartIR light platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN, ColorMode
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import pytest

from custom_components.smartir.const import CONTROLLER_TYPES
from custom_components.smartir.light import (
    DEFAULT_NAME,
    SmartIRLight,
    async_setup_entry,
    async_setup_platform,
    closest_match,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_light_config() -> dict[str, Any]:
    """Create mock light configuration."""
    return {
        "unique_id": "test_light_unique_id",
        "name": "Test Light",
        "device_code": 5678,
        "controller_data": "remote.test_remote",
        "delay": 0.5,
        "power_sensor": "sensor.test_power",
    }


@pytest.fixture
def mock_light_device_data_full() -> dict[str, Any]:
    """Create mock light device data with color temp, brightness and night light."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Light Model A", "Light Model B"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "brightness": [10, 50, 100],
        "colorTemperature": [2700, 4000, 6500],
        "commands": {
            "on": "cmd_on",
            "off": "cmd_off",
            "brighten": "cmd_brighten",
            "dim": "cmd_dim",
            "colder": "cmd_colder",
            "warmer": "cmd_warmer",
            "night": "cmd_night",
        },
    }


@pytest.fixture
def mock_light_device_data_brightness_only() -> dict[str, Any]:
    """Create mock light device data supporting brightness only (no color temp)."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Light Model C"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "brightness": [10, 50, 100],
        "colorTemperature": [],
        "commands": {
            "on": "cmd_on",
            "off": "cmd_off",
            "brighten": "cmd_brighten",
            "dim": "cmd_dim",
        },
    }


@pytest.fixture
def mock_light_device_data_night_only() -> dict[str, Any]:
    """Create mock light device data supporting a night light only (no brighten/dim)."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Light Model E"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "brightness": [],
        "colorTemperature": [],
        "commands": {
            "on": "cmd_on",
            "off": "cmd_off",
            "night": "cmd_night",
        },
    }


@pytest.fixture
def mock_light_device_data_onoff_only() -> dict[str, Any]:
    """Create mock light device data supporting only on/off."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Light Model D"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "brightness": [],
        "colorTemperature": [],
        "commands": {
            "on": "cmd_on",
            "off": "cmd_off",
        },
    }


@pytest.fixture
def mock_controller() -> MagicMock:
    """Create a mock controller."""
    controller = MagicMock()
    controller.send = AsyncMock()
    return controller


def create_light_entity(
    hass: HomeAssistant,
    config: dict[str, Any],
    device_data: dict[str, Any],
    mock_controller: MagicMock,
) -> SmartIRLight:
    """Create a SmartIRLight entity with mocked controller."""
    with patch(
        "custom_components.smartir.light.get_controller",
        return_value=mock_controller,
    ):
        entity = SmartIRLight(hass, config, device_data)
        # Mock async_write_ha_state to avoid platform issues
        entity.async_write_ha_state = MagicMock()
        return entity


def _aiofiles_context(content: str) -> MagicMock:
    """Build a mock async context manager returning `content` on read()."""
    mock_file = AsyncMock()
    mock_file.read = AsyncMock(return_value=content)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_file)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    return mock_ctx


# ---------------------------------------------------------------------------
# async_setup_platform
# ---------------------------------------------------------------------------


class TestAsyncSetupPlatform:
    """Tests for async_setup_platform."""

    async def test_setup_platform_loads_existing_file(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test setup when the device json file already exists on disk."""
        async_add_entities = MagicMock()
        json_content = json.dumps(mock_light_device_data_full)

        with (
            patch("custom_components.smartir.light.os.path.isdir", return_value=True),
            patch("custom_components.smartir.light.os.path.exists", return_value=True),
            patch(
                "custom_components.smartir.light.aiofiles.open",
                return_value=_aiofiles_context(json_content),
            ),
            patch(
                "custom_components.smartir.light.Helper.downloader",
                new_callable=AsyncMock,
            ) as mock_downloader,
            patch(
                "custom_components.smartir.light.get_controller",
                return_value=mock_controller,
            ),
        ):
            await async_setup_platform(hass, mock_light_config, async_add_entities)

        mock_downloader.assert_not_called()
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], SmartIRLight)
        assert entities[0]._manufacturer == "Test Manufacturer"

    async def test_setup_platform_downloads_missing_file(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test setup downloads the device json file when missing."""
        async_add_entities = MagicMock()
        json_content = json.dumps(mock_light_device_data_full)

        with (
            patch("custom_components.smartir.light.os.path.isdir", return_value=True),
            patch("custom_components.smartir.light.os.path.exists", return_value=False),
            patch(
                "custom_components.smartir.light.aiofiles.open",
                return_value=_aiofiles_context(json_content),
            ),
            patch(
                "custom_components.smartir.light.Helper.downloader",
                new_callable=AsyncMock,
            ) as mock_downloader,
            patch(
                "custom_components.smartir.light.get_controller",
                return_value=mock_controller,
            ),
        ):
            await async_setup_platform(hass, mock_light_config, async_add_entities)

        mock_downloader.assert_called_once()
        args = mock_downloader.call_args[0]
        assert args[0] is hass
        assert args[1] == "https://raw.githubusercontent.com/foXaCe/SmartIR/main/codes/light/5678.json"
        async_add_entities.assert_called_once()

    async def test_setup_platform_download_failure_returns_early(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
    ) -> None:
        """Test setup aborts and does not add entities when download fails."""
        async_add_entities = MagicMock()

        with (
            patch("custom_components.smartir.light.os.path.isdir", return_value=True),
            patch("custom_components.smartir.light.os.path.exists", return_value=False),
            patch(
                "custom_components.smartir.light.Helper.downloader",
                new_callable=AsyncMock,
                side_effect=Exception("network error"),
            ),
        ):
            await async_setup_platform(hass, mock_light_config, async_add_entities)

        async_add_entities.assert_not_called()

    async def test_setup_platform_invalid_json_returns_early(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
    ) -> None:
        """Test setup aborts and does not add entities when the json is invalid."""
        async_add_entities = MagicMock()

        with (
            patch("custom_components.smartir.light.os.path.isdir", return_value=True),
            patch("custom_components.smartir.light.os.path.exists", return_value=True),
            patch(
                "custom_components.smartir.light.aiofiles.open",
                return_value=_aiofiles_context("not valid json"),
            ),
            patch(
                "custom_components.smartir.light.Helper.downloader",
                new_callable=AsyncMock,
            ) as mock_downloader,
        ):
            await async_setup_platform(hass, mock_light_config, async_add_entities)

        mock_downloader.assert_not_called()
        async_add_entities.assert_not_called()

    async def test_setup_platform_creates_missing_directory(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test setup creates the codes directory when it does not exist."""
        async_add_entities = MagicMock()
        json_content = json.dumps(mock_light_device_data_full)

        with (
            patch("custom_components.smartir.light.os.path.isdir", return_value=False),
            patch("custom_components.smartir.light.os.makedirs") as mock_makedirs,
            patch("custom_components.smartir.light.os.path.exists", return_value=True),
            patch(
                "custom_components.smartir.light.aiofiles.open",
                return_value=_aiofiles_context(json_content),
            ),
            patch(
                "custom_components.smartir.light.get_controller",
                return_value=mock_controller,
            ),
        ):
            await async_setup_platform(hass, mock_light_config, async_add_entities)

        mock_makedirs.assert_called_once()
        async_add_entities.assert_called_once()

    async def test_setup_platform_overrides_controller_type(
        self,
        hass: HomeAssistant,
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test setup overrides supportedController using the config entry controller type."""
        async_add_entities = MagicMock()
        json_content = json.dumps(mock_light_device_data_full)
        config = {
            "unique_id": "test_light_unique_id",
            "name": "Test Light",
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "delay": 0.5,
            "controller_type": "xiaomi",
        }

        with (
            patch("custom_components.smartir.light.os.path.isdir", return_value=True),
            patch("custom_components.smartir.light.os.path.exists", return_value=True),
            patch(
                "custom_components.smartir.light.aiofiles.open",
                return_value=_aiofiles_context(json_content),
            ),
            patch(
                "custom_components.smartir.light.get_controller",
                return_value=mock_controller,
            ) as mock_get_controller,
        ):
            await async_setup_platform(hass, config, async_add_entities)

        entities = async_add_entities.call_args[0][0]
        assert entities[0]._supported_controller == CONTROLLER_TYPES["xiaomi"]
        mock_get_controller.assert_called_once()
        assert mock_get_controller.call_args[0][1] == CONTROLLER_TYPES["xiaomi"]


class TestAsyncSetupEntry:
    """Tests for async_setup_entry."""

    async def test_setup_entry_delegates_to_helper(self, hass: HomeAssistant) -> None:
        """Test async_setup_entry delegates to async_setup_entry_platform."""
        entry = MagicMock()
        async_add_entities = MagicMock()

        with patch(
            "custom_components.smartir.helpers.async_setup_entry_platform",
            new_callable=AsyncMock,
        ) as mock_helper:
            await async_setup_entry(hass, entry, async_add_entities)

        mock_helper.assert_called_once_with(hass, entry, async_add_entities, async_setup_platform)


# ---------------------------------------------------------------------------
# closest_match
# ---------------------------------------------------------------------------


class TestClosestMatch:
    """Tests for the closest_match module function."""

    def test_value_below_first_entry(self) -> None:
        """Test a value below the first entry returns index 0."""
        assert closest_match(5, [10, 50, 100]) == 0

    def test_value_above_last_entry(self) -> None:
        """Test a value above the last entry returns the last index."""
        assert closest_match(150, [10, 50, 100]) == 2

    def test_value_equal_to_last_entry(self) -> None:
        """Test a value equal to the last entry returns the last index."""
        assert closest_match(100, [10, 50, 100]) == 2

    def test_value_exact_match_middle(self) -> None:
        """Test a value between two closer to the higher entry on a tie."""
        # Exactly halfway between 10 and 50, ties resolve to the higher index.
        assert closest_match(30, [10, 50, 100]) == 1

    def test_value_closer_to_lower_entry(self) -> None:
        """Test a value clearly closer to the lower entry."""
        assert closest_match(15, [10, 50, 100]) == 0

    def test_value_closer_to_higher_entry(self) -> None:
        """Test a value clearly closer to the higher entry."""
        assert closest_match(45, [10, 50, 100]) == 1

    def test_value_none_defaults_to_zero(self) -> None:
        """Test a None value is treated as 0."""
        assert closest_match(None, [10, 50, 100]) == 0


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestSmartIRLightProperties:
    """Tests for SmartIRLight properties."""

    def test_unique_id(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test unique_id property."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.unique_id == "test_light_unique_id"

    def test_name(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test name property."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.name == "Test Light"

    def test_default_name(
        self,
        hass: HomeAssistant,
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test default name is used when not given in config."""
        minimal_config = {"device_code": 1234, "controller_data": "remote.test_remote"}
        light = create_light_entity(hass, minimal_config, mock_light_device_data_full, mock_controller)
        assert light.name is None
        assert DEFAULT_NAME == "SmartIR Light"

    def test_device_info(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test device_info property."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        device_info = light.device_info

        assert device_info["name"] == "Test Light"
        assert device_info["manufacturer"] == "Test Manufacturer"
        assert device_info["model"] == "Light Model A, Light Model B"
        assert "5678" in device_info["sw_version"]
        assert device_info["identifiers"] == {("smartir", "test_light_unique_id")}

    def test_device_info_fallback_identifier(
        self,
        hass: HomeAssistant,
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test device_info falls back to a generated identifier without unique_id."""
        config = {"device_code": 9999, "controller_data": "remote.test_remote"}
        light = create_light_entity(hass, config, mock_light_device_data_full, mock_controller)

        device_info = light.device_info
        assert device_info["identifiers"] == {("smartir", "smartir_light_9999")}

    def test_supported_color_modes_color_temp(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test supported_color_modes returns COLOR_TEMP when colder/warmer are present."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.supported_color_modes == [ColorMode.COLOR_TEMP]
        assert light.color_mode == ColorMode.COLOR_TEMP

    def test_supported_color_modes_brightness(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_brightness_only: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test supported_color_modes returns BRIGHTNESS without color temp commands."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_brightness_only, mock_controller)
        assert light.supported_color_modes == [ColorMode.BRIGHTNESS]
        assert light.color_mode == ColorMode.BRIGHTNESS

    def test_supported_color_modes_onoff(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_onoff_only: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test supported_color_modes returns ONOFF for a plain on/off light."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_onoff_only, mock_controller)
        assert light.supported_color_modes == [ColorMode.ONOFF]
        assert light.color_mode == ColorMode.ONOFF

    def test_color_temp_kelvin_initialized_to_max(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test color_temp_kelvin is initialized to the maximum supported value."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.color_temp_kelvin == 6500

    def test_min_max_color_temp_kelvin(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test min_color_temp_kelvin and max_color_temp_kelvin properties."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.min_color_temp_kelvin == 2700
        assert light.max_color_temp_kelvin == 6500

    def test_min_max_color_temp_kelvin_empty(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_onoff_only: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test min/max color temp are None when the light has no color temperature list."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_onoff_only, mock_controller)
        assert light.min_color_temp_kelvin is None
        assert light.max_color_temp_kelvin is None

    def test_is_on_default(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test is_on defaults to True after init."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.is_on is True

    def test_is_on_false_when_off(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test is_on is False when powered off and not on by remote."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._power = STATE_OFF
        assert light.is_on is False

    def test_is_on_true_when_on_by_remote(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test is_on is True when off but detected on by remote."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._power = STATE_OFF
        light._on_by_remote = True
        assert light.is_on is True

    def test_brightness(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test brightness property reflects internal state."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.brightness == 100
        light._brightness = 42
        assert light.brightness == 42

    def test_extra_state_attributes(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test extra_state_attributes property."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        attrs = light.extra_state_attributes

        assert attrs["device_code"] == 5678
        assert attrs["manufacturer"] == "Test Manufacturer"
        assert attrs["supported_models"] == ["Light Model A", "Light Model B"]
        assert attrs["supported_controller"] == "Broadlink"
        assert attrs["commands_encoding"] == "Base64"
        assert attrs["on_by_remote"] is False


class TestSmartIRLightIcon:
    """Tests for the SmartIRLight icon property."""

    def test_icon_off(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon when the light is off."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._power = STATE_OFF
        assert light.icon == "mdi:lightbulb-off"

    def test_icon_color_temp_on(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon when on and supporting color temperature."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.icon == "mdi:lightbulb-on"

    def test_icon_brightness_on(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_brightness_only: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon when on and supporting brightness (non-night value)."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_brightness_only, mock_controller)
        light._brightness = 50
        assert light.icon == "mdi:brightness-6"

    def test_icon_night_light(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_night_only: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon shows the night light variant when brightness is 1."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_night_only, mock_controller)
        light._brightness = 1
        assert light.icon == "mdi:lightbulb-night"

    def test_icon_onoff_on(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_onoff_only: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon for a plain on/off light when on."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_onoff_only, mock_controller)
        assert light.icon == "mdi:lightbulb-on"


# ---------------------------------------------------------------------------
# async_turn_on / async_turn_off / async_toggle
# ---------------------------------------------------------------------------


class TestSmartIRLightTurnOn:
    """Tests for SmartIRLight.async_turn_on."""

    async def test_turn_on_from_off(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on the light from an off state sends the on command."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._power = STATE_OFF

        await light.async_turn_on()

        assert light._power == STATE_ON
        mock_controller.send.assert_called_once_with("cmd_on")

    async def test_turn_on_already_on_resends_power_on(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test calling turn_on while already on re-sends the power-on command to resync."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        await light.async_turn_on()

        mock_controller.send.assert_called_once_with("cmd_on")

    async def test_turn_on_no_command_when_on_by_remote(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test no command is sent when the light is off but detected on by remote."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._power = STATE_OFF
        light._on_by_remote = True

        await light.async_turn_on()

        mock_controller.send.assert_not_called()

    async def test_turn_on_with_color_temp_kelvin(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on with a target color temperature sends warmer commands."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.color_temp_kelvin == 6500

        await light.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 2700})

        assert light._colortemp == 2700
        assert mock_controller.send.call_count == 3
        mock_controller.send.assert_called_with("cmd_warmer")

    async def test_turn_on_color_temp_no_change_sends_nothing(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test requesting the current color temperature results in no command."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        await light.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 6500})

        mock_controller.send.assert_not_called()
        assert light._colortemp == 6500

    async def test_turn_on_with_brightness(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on with a target brightness sends dim commands."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        assert light.brightness == 100

        await light.async_turn_on(**{ATTR_BRIGHTNESS: 10})

        assert light._brightness == 10
        assert mock_controller.send.call_count == 3
        mock_controller.send.assert_called_with("cmd_dim")

    async def test_turn_on_with_brightness_increase(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on with a higher target brightness sends brighten commands."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._brightness = 10

        await light.async_turn_on(**{ATTR_BRIGHTNESS: 50})

        assert light._brightness == 50
        mock_controller.send.assert_called_once_with("cmd_brighten")

    async def test_turn_on_with_nightlight_brightness(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test setting brightness to 1 triggers the night light command."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        await light.async_turn_on(**{ATTR_BRIGHTNESS: 1})

        assert light._brightness == 1
        mock_controller.send.assert_called_once_with("cmd_night")


class TestSmartIRLightTurnOff:
    """Tests for SmartIRLight.async_turn_off."""

    async def test_turn_off(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test turning off the light sends the off command."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        await light.async_turn_off()

        assert light._power == STATE_OFF
        assert light.is_on is False
        mock_controller.send.assert_called_once_with("cmd_off")
        assert light.icon == "mdi:lightbulb-off"


class TestSmartIRLightToggle:
    """Tests for SmartIRLight.async_toggle."""

    async def test_toggle_turns_on_when_off(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test toggle turns the light on when it is off."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._power = STATE_OFF

        await light.async_toggle()

        assert light._power == STATE_ON
        mock_controller.send.assert_called_once_with("cmd_on")

    async def test_toggle_turns_off_when_on(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test toggle turns the light off when it is on."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        await light.async_toggle()

        assert light._power == STATE_OFF
        mock_controller.send.assert_called_once_with("cmd_off")


# ---------------------------------------------------------------------------
# send_command
# ---------------------------------------------------------------------------


class TestSmartIRLightSendCommand:
    """Tests for SmartIRLight.send_command."""

    async def test_send_command_known(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test sending a known command forwards it to the controller."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        await light.send_command("on")

        mock_controller.send.assert_called_once_with("cmd_on")
        assert light._on_by_remote is False

    async def test_send_command_with_count(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test sending a command repeats it `count` times."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        await light.send_command("brighten", 4)

        assert mock_controller.send.call_count == 4
        mock_controller.send.assert_called_with("cmd_brighten")

    async def test_send_command_unknown_logs_and_skips(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test sending an unknown command does not call the controller."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        await light.send_command("not_a_real_command")

        mock_controller.send.assert_not_called()

    async def test_send_command_swallows_controller_exception(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test an exception raised by the controller is logged and not propagated."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        mock_controller.send.side_effect = Exception("boom")

        await light.send_command("on")

        mock_controller.send.assert_called_once_with("cmd_on")


# ---------------------------------------------------------------------------
# _async_power_sensor_changed
# ---------------------------------------------------------------------------


class TestSmartIRLightPowerSensor:
    """Tests for SmartIRLight._async_power_sensor_changed."""

    async def test_power_sensor_turns_on(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test the power sensor turning on marks the light as on by remote."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._power = STATE_OFF

        new_state = MagicMock()
        new_state.state = STATE_ON
        old_state = MagicMock()
        old_state.state = STATE_OFF
        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state}

        await light._async_power_sensor_changed(event)

        assert light._on_by_remote is True
        assert light.is_on is True

    async def test_power_sensor_turns_off(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test the power sensor turning off marks the light as off."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)
        light._on_by_remote = True

        new_state = MagicMock()
        new_state.state = STATE_OFF
        old_state = MagicMock()
        old_state.state = STATE_ON
        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state}

        await light._async_power_sensor_changed(event)

        assert light._on_by_remote is False
        assert light._power == STATE_OFF

    async def test_power_sensor_no_state_change_does_nothing(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test no action is taken when old and new state are identical."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        new_state = MagicMock()
        new_state.state = STATE_ON
        old_state = MagicMock()
        old_state.state = STATE_ON
        event = MagicMock()
        event.data = {"new_state": new_state, "old_state": old_state}

        await light._async_power_sensor_changed(event)

        assert light._on_by_remote is False

    async def test_power_sensor_new_state_none_does_nothing(
        self,
        hass: HomeAssistant,
        mock_light_config: dict[str, Any],
        mock_light_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test no action is taken when the new state is None."""
        light = create_light_entity(hass, mock_light_config, mock_light_device_data_full, mock_controller)

        event = MagicMock()
        event.data = {"new_state": None, "old_state": MagicMock()}

        await light._async_power_sensor_changed(event)

        assert light._on_by_remote is False
        assert light._power == STATE_ON
