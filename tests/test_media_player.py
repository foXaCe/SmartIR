"""Tests for SmartIR media player platform."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.media_player.const import MediaPlayerEntityFeature, MediaType
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import pytest

from custom_components.smartir.media_player import (
    DEFAULT_NAME,
    SmartIRMediaPlayer,
    async_setup_platform,
)


@pytest.fixture
def mock_media_player_config() -> dict[str, Any]:
    """Create mock media player configuration."""
    return {
        "unique_id": "test_media_player_unique_id",
        "name": "Test Media Player",
        "device_code": 5678,
        "controller_data": "remote.test_remote",
        "delay": 0.5,
        "device_class": "tv",
    }


@pytest.fixture
def mock_media_player_device_data_full() -> dict[str, Any]:
    """Create mock media player device data with a full command set."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": ["Model A", "Model B"],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "commands": {
            "off": "cmd_off",
            "on": "cmd_on",
            "previousChannel": "cmd_previous_channel",
            "nextChannel": "cmd_next_channel",
            "volumeDown": "cmd_volume_down",
            "volumeUp": "cmd_volume_up",
            "mute": "cmd_mute",
            "sources": {
                "HDMI 1": "cmd_hdmi1",
                "HDMI 2": "cmd_hdmi2",
                "Channel 0": "cmd_channel_0",
                "Channel 1": "cmd_channel_1",
                "Channel 2": "cmd_channel_2",
                "Channel 3": "cmd_channel_3",
                "Channel 4": "cmd_channel_4",
                "Channel 5": "cmd_channel_5",
                "Channel 6": "cmd_channel_6",
                "Channel 7": "cmd_channel_7",
                "Channel 8": "cmd_channel_8",
                "Channel 9": "cmd_channel_9",
            },
        },
    }


@pytest.fixture
def mock_media_player_device_data_minimal() -> dict[str, Any]:
    """Create mock media player device data without optional commands."""
    return {
        "manufacturer": "Test Manufacturer",
        "supportedModels": [],
        "supportedController": "Broadlink",
        "commandsEncoding": "Base64",
        "commands": {},
    }


@pytest.fixture
def mock_controller() -> MagicMock:
    """Create a mock controller."""
    controller = MagicMock()
    controller.send = AsyncMock()
    return controller


def create_media_player_entity(
    hass: HomeAssistant,
    config: dict[str, Any],
    device_data: dict[str, Any],
    mock_controller: MagicMock,
) -> SmartIRMediaPlayer:
    """Create a SmartIRMediaPlayer entity with mocked controller."""
    with patch(
        "custom_components.smartir.media_player.get_controller",
        return_value=mock_controller,
    ):
        entity = SmartIRMediaPlayer(hass, config, device_data)
        # Mock async_write_ha_state to avoid platform issues
        entity.async_write_ha_state = MagicMock()
        return entity


class TestAsyncSetupPlatform:
    """Tests for async_setup_platform."""

    def _make_aiofiles_cm(self, content: str) -> MagicMock:
        """Build a mock async context manager compatible with aiofiles.open()."""
        mock_file = MagicMock()
        mock_file.read = AsyncMock(return_value=content)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_file)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm

    async def test_setup_creates_entity(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that setup creates a media player entity when the JSON file exists."""
        content = json.dumps(mock_media_player_device_data_full)
        async_add_entities = MagicMock()

        with (
            patch("custom_components.smartir.media_player.os.path.isdir", return_value=True),
            patch("custom_components.smartir.media_player.os.path.exists", return_value=True),
            patch("aiofiles.open", return_value=self._make_aiofiles_cm(content)),
            patch("custom_components.smartir.media_player.get_controller", return_value=mock_controller),
        ):
            await async_setup_platform(hass, mock_media_player_config, async_add_entities)

        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], SmartIRMediaPlayer)
        assert entities[0].unique_id == "test_media_player_unique_id"

    async def test_setup_creates_missing_directory(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that setup creates the device code directory if missing."""
        content = json.dumps(mock_media_player_device_data_full)
        async_add_entities = MagicMock()

        with (
            patch("custom_components.smartir.media_player.os.path.isdir", return_value=False),
            patch("custom_components.smartir.media_player.os.makedirs") as mock_makedirs,
            patch("custom_components.smartir.media_player.os.path.exists", return_value=True),
            patch("aiofiles.open", return_value=self._make_aiofiles_cm(content)),
            patch("custom_components.smartir.media_player.get_controller", return_value=mock_controller),
        ):
            await async_setup_platform(hass, mock_media_player_config, async_add_entities)

        mock_makedirs.assert_called_once()
        async_add_entities.assert_called_once()

    async def test_setup_downloads_missing_file(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that setup downloads the device code file when it does not exist."""
        content = json.dumps(mock_media_player_device_data_full)
        async_add_entities = MagicMock()
        mock_downloader = AsyncMock()

        with (
            patch("custom_components.smartir.media_player.os.path.isdir", return_value=True),
            patch("custom_components.smartir.media_player.os.path.exists", return_value=False),
            patch("custom_components.smartir.Helper.downloader", mock_downloader),
            patch("aiofiles.open", return_value=self._make_aiofiles_cm(content)),
            patch("custom_components.smartir.media_player.get_controller", return_value=mock_controller),
        ):
            await async_setup_platform(hass, mock_media_player_config, async_add_entities)

        mock_downloader.assert_called_once()
        async_add_entities.assert_called_once()

    async def test_setup_download_failure_aborts(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that a download failure aborts setup without raising."""
        async_add_entities = MagicMock()
        mock_downloader = AsyncMock(side_effect=Exception("network error"))

        with (
            patch("custom_components.smartir.media_player.os.path.isdir", return_value=True),
            patch("custom_components.smartir.media_player.os.path.exists", return_value=False),
            patch("custom_components.smartir.Helper.downloader", mock_downloader),
            patch("custom_components.smartir.media_player.get_controller", return_value=mock_controller),
        ):
            await async_setup_platform(hass, mock_media_player_config, async_add_entities)

        async_add_entities.assert_not_called()

    async def test_setup_invalid_json_aborts(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that invalid JSON content aborts setup without raising."""
        async_add_entities = MagicMock()

        with (
            patch("custom_components.smartir.media_player.os.path.isdir", return_value=True),
            patch("custom_components.smartir.media_player.os.path.exists", return_value=True),
            patch("aiofiles.open", return_value=self._make_aiofiles_cm("not valid json")),
            patch("custom_components.smartir.media_player.get_controller", return_value=mock_controller),
        ):
            await async_setup_platform(hass, mock_media_player_config, async_add_entities)

        async_add_entities.assert_not_called()

    async def test_setup_controller_type_override(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that a config-entry controller_type overrides the JSON supportedController."""
        content = json.dumps(mock_media_player_device_data_full)
        async_add_entities = MagicMock()
        config = {
            "unique_id": "test_media_player_unique_id",
            "name": "Test Media Player",
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "delay": 0.5,
            "controller_type": "xiaomi",
        }

        with (
            patch("custom_components.smartir.media_player.os.path.isdir", return_value=True),
            patch("custom_components.smartir.media_player.os.path.exists", return_value=True),
            patch("aiofiles.open", return_value=self._make_aiofiles_cm(content)),
            patch("custom_components.smartir.media_player.get_controller", return_value=mock_controller),
        ):
            await async_setup_platform(hass, config, async_add_entities)

        entities = async_add_entities.call_args[0][0]
        assert entities[0]._supported_controller == "Xiaomi IR Remote (ChuangmiIr)"


class TestSmartIRMediaPlayerInit:
    """Tests for SmartIRMediaPlayer initialization."""

    def test_init_basic_properties(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test basic property initialization."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )

        assert entity.unique_id == "test_media_player_unique_id"
        assert entity.name == "Test Media Player"
        assert entity.device_class == "tv"
        assert entity.state == STATE_OFF
        assert entity.should_poll is True

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
            "commands": {},
        }

        entity = create_media_player_entity(hass, minimal_config, device_data, mock_controller)

        assert entity.unique_id is None
        assert entity.name is None
        assert entity.device_class is None

    def test_init_sources_list(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that sources list is populated from commands."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )

        assert "HDMI 1" in entity.source_list
        assert "HDMI 2" in entity.source_list
        assert "Channel 0" in entity.source_list
        assert entity.source is None

    def test_init_no_sources(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_minimal: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that source_list is empty when no sources are defined."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_minimal, mock_controller
        )

        assert entity.source_list == []
        assert entity.source is None

    def test_init_source_names_rename(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that source_names config renames a source."""
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "source_names": {"HDMI 1": "Apple TV"},
        }

        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)

        assert "Apple TV" in entity.source_list
        assert "HDMI 1" not in entity.source_list
        assert entity._commands["sources"]["Apple TV"] == "cmd_hdmi1"

    def test_init_source_names_removal(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that source_names config with a None new name only removes the source."""
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "source_names": {"HDMI 2": None},
        }

        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)

        assert "HDMI 2" not in entity.source_list
        assert "HDMI 2" not in entity._commands["sources"]

    def test_init_device_class_default_fallback(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that an unknown device_class falls back to the television icon."""
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "device_class": "unknown_class",
        }

        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)

        assert entity.icon == "mdi:television-off"


class TestSmartIRMediaPlayerSupportedFeatures:
    """Tests for the supported_features property."""

    def test_supported_features_full(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test supported features with a full command set."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )

        expected = (
            MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.SELECT_SOURCE
            | MediaPlayerEntityFeature.PLAY_MEDIA
        )
        assert entity.supported_features == expected

    def test_supported_features_minimal(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_minimal: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test supported features with no optional commands."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_minimal, mock_controller
        )

        assert entity.supported_features == 0

    def test_supported_features_volume_step_up_only(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that VOLUME_STEP is set if only volumeUp is present."""
        device_data = {
            "manufacturer": "Test",
            "supportedModels": ["Model"],
            "supportedController": "Broadlink",
            "commandsEncoding": "Base64",
            "commands": {"volumeUp": "cmd_volume_up"},
        }
        entity = create_media_player_entity(hass, mock_media_player_config, device_data, mock_controller)

        assert entity.supported_features & MediaPlayerEntityFeature.VOLUME_STEP


class TestSmartIRMediaPlayerProperties:
    """Tests for SmartIRMediaPlayer properties."""

    @pytest.fixture
    def entity(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRMediaPlayer:
        """Create an entity for testing."""
        return create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )

    def test_media_title(self, entity: SmartIRMediaPlayer) -> None:
        """Test media_title always returns None."""
        assert entity.media_title is None

    def test_media_content_type(self, entity: SmartIRMediaPlayer) -> None:
        """Test media_content_type returns CHANNEL."""
        assert entity.media_content_type == MediaType.CHANNEL

    def test_device_info(self, entity: SmartIRMediaPlayer) -> None:
        """Test device_info property."""
        device_info = entity.device_info
        assert device_info["name"] == "Test Media Player"
        assert device_info["manufacturer"] == "Test Manufacturer"
        assert device_info["model"] == "Model A, Model B"
        assert "5678" in device_info["sw_version"]
        assert "5678" in device_info["configuration_url"]
        assert device_info["suggested_area"] == "Living Room"
        assert ("smartir", "test_media_player_unique_id") in device_info["identifiers"]

    def test_device_info_fallback_identifier(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test device_info identifier fallback when unique_id is missing."""
        config = {"device_code": 999, "controller_data": "remote.test_remote"}
        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)

        device_info = entity.device_info
        assert ("smartir", "smartir_media_player_999") in device_info["identifiers"]

    def test_device_info_no_models_fallback(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_minimal: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test device_info model fallback to Unknown when supportedModels is empty."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_minimal, mock_controller
        )

        assert entity.device_info["model"] == "Unknown"

    def test_extra_state_attributes(self, entity: SmartIRMediaPlayer) -> None:
        """Test extra_state_attributes property."""
        attrs = entity.extra_state_attributes
        assert attrs["device_code"] == 5678
        assert attrs["manufacturer"] == "Test Manufacturer"
        assert attrs["supported_models"] == ["Model A", "Model B"]
        assert attrs["supported_controller"] == "Broadlink"
        assert attrs["commands_encoding"] == "Base64"


class TestSmartIRMediaPlayerIcon:
    """Tests for the icon property."""

    def _make_entity(
        self,
        hass: HomeAssistant,
        device_class: str,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRMediaPlayer:
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "device_class": device_class,
        }
        return create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)

    def test_icon_tv_off(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon for a TV that is off."""
        entity = self._make_entity(hass, "tv", mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_OFF
        assert entity.icon == "mdi:television-off"
        assert entity._attr_icon == "mdi:television"

    def test_icon_tv_on(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon for a TV that is on."""
        entity = self._make_entity(hass, "tv", mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_ON
        assert entity.icon == "mdi:television"

    def test_icon_tv_other_state(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon for a TV in a state other than on/off."""
        entity = self._make_entity(hass, "tv", mock_media_player_device_data_full, mock_controller)
        entity._state = "playing"
        assert entity.icon == "mdi:television"

    def test_icon_speaker_off(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon for a speaker that is off."""
        entity = self._make_entity(hass, "speaker", mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_OFF
        assert entity.icon == "mdi:speaker"
        assert entity._attr_icon == "mdi:speaker"

    def test_icon_speaker_on(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon for a speaker that is on."""
        entity = self._make_entity(hass, "speaker", mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_ON
        assert entity.icon == "mdi:speaker"

    def test_icon_receiver(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon for a receiver."""
        entity = self._make_entity(hass, "receiver", mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_OFF
        assert entity.icon == "mdi:audio-video"
        assert entity._attr_icon == "mdi:audio-video"

    def test_icon_unknown_device_class(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test icon fallback for an unknown device class."""
        entity = self._make_entity(hass, "weird", mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_ON
        assert entity.icon == "mdi:television"


class TestSmartIRMediaPlayerCommands:
    """Tests for SmartIRMediaPlayer command methods."""

    @pytest.fixture
    def entity(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRMediaPlayer:
        """Create an entity for testing (no power sensor)."""
        return create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )

    async def test_turn_off_no_power_sensor(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test turning off updates state when no power sensor is configured."""
        entity._state = STATE_ON
        entity._source = "HDMI 1"

        await entity.async_turn_off()

        mock_controller.send.assert_called_once_with("cmd_off")
        assert entity.state == STATE_OFF
        assert entity.source is None
        entity.async_write_ha_state.assert_called_once()

    async def test_turn_off_with_power_sensor(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test turning off does not update state when a power sensor is configured."""
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "power_sensor": "sensor.test_power",
        }
        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_ON

        await entity.async_turn_off()

        mock_controller.send.assert_called_once_with("cmd_off")
        assert entity.state == STATE_ON
        entity.async_write_ha_state.assert_not_called()

    async def test_turn_on_no_power_sensor(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test turning on updates state when no power sensor is configured."""
        entity._state = STATE_OFF

        await entity.async_turn_on()

        mock_controller.send.assert_called_once_with("cmd_on")
        assert entity.state == STATE_ON
        entity.async_write_ha_state.assert_called_once()

    async def test_turn_on_with_power_sensor(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test turning on does not update state when a power sensor is configured."""
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "power_sensor": "sensor.test_power",
        }
        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)

        await entity.async_turn_on()

        mock_controller.send.assert_called_once_with("cmd_on")
        assert entity.state == STATE_OFF
        entity.async_write_ha_state.assert_not_called()

    async def test_media_previous_track(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test previous track command."""
        await entity.async_media_previous_track()

        mock_controller.send.assert_called_once_with("cmd_previous_channel")
        entity.async_write_ha_state.assert_called_once()

    async def test_media_next_track(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test next track command."""
        await entity.async_media_next_track()

        mock_controller.send.assert_called_once_with("cmd_next_channel")
        entity.async_write_ha_state.assert_called_once()

    async def test_volume_down(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test volume down command."""
        await entity.async_volume_down()

        mock_controller.send.assert_called_once_with("cmd_volume_down")
        entity.async_write_ha_state.assert_called_once()

    async def test_volume_up(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test volume up command."""
        await entity.async_volume_up()

        mock_controller.send.assert_called_once_with("cmd_volume_up")
        entity.async_write_ha_state.assert_called_once()

    async def test_mute_volume(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test mute command."""
        await entity.async_mute_volume(True)

        mock_controller.send.assert_called_once_with("cmd_mute")
        entity.async_write_ha_state.assert_called_once()

    async def test_select_source(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test selecting a source."""
        await entity.async_select_source("HDMI 1")

        assert entity.source == "HDMI 1"
        mock_controller.send.assert_called_once_with("cmd_hdmi1")
        entity.async_write_ha_state.assert_called_once()

    async def test_play_media_channel(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test selecting a channel via play_media."""
        entity._state = STATE_ON

        await entity.async_play_media(MediaType.CHANNEL, "12")

        assert entity.source == "Channel 12"
        assert mock_controller.send.call_count == 2
        mock_controller.send.assert_any_call("cmd_channel_1")
        mock_controller.send.assert_any_call("cmd_channel_2")
        entity.async_write_ha_state.assert_called_once()

    async def test_play_media_turns_on_first_when_off(
        self, entity: SmartIRMediaPlayer, mock_controller: MagicMock
    ) -> None:
        """Test play_media turns on the device first if it is off."""
        entity._state = STATE_OFF

        await entity.async_play_media(MediaType.CHANNEL, "5")

        # First call is the "on" command (from async_turn_on), then the channel command.
        assert mock_controller.send.call_count == 2
        mock_controller.send.assert_any_call("cmd_on")
        mock_controller.send.assert_any_call("cmd_channel_5")
        assert entity.source == "Channel 5"

    async def test_play_media_invalid_media_type(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test play_media with an invalid media type logs an error and does nothing."""
        entity._state = STATE_ON

        await entity.async_play_media("music", "5")

        mock_controller.send.assert_not_called()
        assert entity.source is None

    async def test_play_media_non_digit_channel(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test play_media with a non-digit media_id logs an error and does nothing."""
        entity._state = STATE_ON

        await entity.async_play_media(MediaType.CHANNEL, "abc")

        mock_controller.send.assert_not_called()
        assert entity.source is None


class TestSmartIRMediaPlayerSendCommand:
    """Tests for the send_command method."""

    @pytest.fixture
    def entity(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> SmartIRMediaPlayer:
        """Create an entity for testing."""
        return create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )

    async def test_send_command_calls_controller(self, entity: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Test send_command forwards the command to the controller."""
        await entity.send_command("some_command")

        mock_controller.send.assert_called_once_with("some_command")

    async def test_send_command_swallows_exception(
        self, entity: SmartIRMediaPlayer, mock_controller: MagicMock
    ) -> None:
        """Test send_command does not raise when the controller fails."""
        mock_controller.send.side_effect = Exception("boom")

        await entity.send_command("some_command")

        mock_controller.send.assert_called_once_with("some_command")


class TestSmartIRMediaPlayerUpdate:
    """Tests for async_update (power sensor polling)."""

    async def test_update_no_power_sensor(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test async_update does nothing without a power sensor."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )
        entity._state = STATE_ON

        await entity.async_update()

        assert entity.state == STATE_ON

    async def test_update_power_sensor_unknown_entity(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test async_update does nothing if the power sensor state is unavailable."""
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "power_sensor": "sensor.does_not_exist",
        }
        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_ON

        await entity.async_update()

        assert entity.state == STATE_ON

    async def test_update_power_sensor_off(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test async_update sets state off and clears source when power sensor is off."""
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "power_sensor": "sensor.test_power",
        }
        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_ON
        entity._source = "HDMI 1"
        hass.states.async_set("sensor.test_power", STATE_OFF)

        await entity.async_update()

        assert entity.state == STATE_OFF
        assert entity.source is None

    async def test_update_power_sensor_on(
        self,
        hass: HomeAssistant,
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test async_update sets state on when power sensor is on."""
        config = {
            "device_code": 5678,
            "controller_data": "remote.test_remote",
            "power_sensor": "sensor.test_power",
        }
        entity = create_media_player_entity(hass, config, mock_media_player_device_data_full, mock_controller)
        entity._state = STATE_OFF
        hass.states.async_set("sensor.test_power", STATE_ON)

        await entity.async_update()

        assert entity.state == STATE_ON


class TestSmartIRMediaPlayerAddedToHass:
    """Tests for async_added_to_hass (state restoration)."""

    async def test_added_to_hass_restores_state(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that a previously stored state is restored."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )

        mock_last_state = MagicMock()
        mock_last_state.state = STATE_ON
        entity.async_get_last_state = AsyncMock(return_value=mock_last_state)

        await entity.async_added_to_hass()

        assert entity.state == STATE_ON

    async def test_added_to_hass_no_previous_state(
        self,
        hass: HomeAssistant,
        mock_media_player_config: dict[str, Any],
        mock_media_player_device_data_full: dict[str, Any],
        mock_controller: MagicMock,
    ) -> None:
        """Test that state stays at default when there is no previous state."""
        entity = create_media_player_entity(
            hass, mock_media_player_config, mock_media_player_device_data_full, mock_controller
        )
        entity.async_get_last_state = AsyncMock(return_value=None)

        await entity.async_added_to_hass()

        assert entity.state == STATE_OFF


class TestDefaultName:
    """Sanity test for the DEFAULT_NAME constant."""

    def test_default_name_value(self) -> None:
        """Test DEFAULT_NAME has the expected value."""
        assert DEFAULT_NAME == "SmartIR Media Player"
