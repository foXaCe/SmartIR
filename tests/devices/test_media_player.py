"""Tests for the SmartIR media player entity."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.smartir.api.exceptions import SmartIRControllerError
from custom_components.smartir.const import CONF_DEVICE_CLASS, CONF_SOURCE_NAMES, SmartIRData
from custom_components.smartir.devices.media_player import SmartIRMediaPlayer


def create_mp_entity(
    hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any], controller: MagicMock
) -> SmartIRMediaPlayer:
    """Create a SmartIRMediaPlayer entity with a mocked controller."""
    with patch("custom_components.smartir.entity.get_controller", return_value=controller):
        entity = SmartIRMediaPlayer(hass, data, device_data)
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.fixture
def mp(hass, make_smartir_data, mock_media_player_device_data, mock_controller) -> SmartIRMediaPlayer:
    """A media player with a full command set."""
    return create_mp_entity(
        hass, make_smartir_data(device_type="media_player"), mock_media_player_device_data, mock_controller
    )


class TestInit:
    """Tests for initialization, features and device class."""

    def test_initial_state_off(self, mp: SmartIRMediaPlayer) -> None:
        """The media player starts off."""
        assert mp.state == MediaPlayerState.OFF

    def test_default_device_class_is_tv(self, mp: SmartIRMediaPlayer) -> None:
        """The device class defaults to TV."""
        assert mp.device_class == MediaPlayerDeviceClass.TV

    def test_device_class_from_extra(
        self, hass, make_smartir_data, mock_media_player_device_data, mock_controller
    ) -> None:
        """A device_class in the extra data is honored."""
        data = make_smartir_data(device_type="media_player", extra={CONF_DEVICE_CLASS: "speaker"})
        mp = create_mp_entity(hass, data, mock_media_player_device_data, mock_controller)
        assert mp.device_class == MediaPlayerDeviceClass.SPEAKER

    def test_supported_features(self, mp: SmartIRMediaPlayer) -> None:
        """All features present in the command set are advertised."""
        features = mp.supported_features
        for flag in (
            MediaPlayerEntityFeature.TURN_ON,
            MediaPlayerEntityFeature.TURN_OFF,
            MediaPlayerEntityFeature.PREVIOUS_TRACK,
            MediaPlayerEntityFeature.NEXT_TRACK,
            MediaPlayerEntityFeature.VOLUME_STEP,
            MediaPlayerEntityFeature.VOLUME_MUTE,
            MediaPlayerEntityFeature.SELECT_SOURCE,
            MediaPlayerEntityFeature.PLAY_MEDIA,
        ):
            assert flag in features

    def test_minimal_has_no_features(
        self, hass, make_smartir_data, mock_media_player_device_data_minimal, mock_controller
    ) -> None:
        """An empty command set advertises no features and no sources."""
        mp = create_mp_entity(
            hass, make_smartir_data(device_type="media_player"), mock_media_player_device_data_minimal, mock_controller
        )
        assert mp.supported_features == MediaPlayerEntityFeature(0)
        assert mp.source_list == []

    def test_source_list_built_from_commands(self, mp: SmartIRMediaPlayer) -> None:
        """The source list contains all source command keys."""
        assert "HDMI 1" in mp.source_list
        assert "HDMI 2" in mp.source_list

    def test_source_names_renaming(
        self, hass, make_smartir_data, mock_media_player_device_data, mock_controller
    ) -> None:
        """A source_names mapping renames sources in the list."""
        data = make_smartir_data(device_type="media_player", extra={CONF_SOURCE_NAMES: {"HDMI 1": "Apple TV"}})
        mp = create_mp_entity(hass, data, mock_media_player_device_data, mock_controller)
        assert "Apple TV" in mp.source_list
        assert "HDMI 1" not in mp.source_list

    def test_media_content_type(self, mp: SmartIRMediaPlayer) -> None:
        """The media content type is a channel."""
        assert mp.media_content_type == MediaType.CHANNEL


class TestTurnOnOff:
    """Tests for power control."""

    async def test_turn_on(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Turning on sends the on command and sets state on (no power sensor)."""
        await mp.async_turn_on()
        assert mp.state == MediaPlayerState.ON
        mock_controller.send.assert_called_once_with("cmd_on")

    async def test_turn_off(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Turning off sends the off command and clears the source."""
        mp._state = MediaPlayerState.ON
        mp._source = "HDMI 1"
        await mp.async_turn_off()
        assert mp.state == MediaPlayerState.OFF
        assert mp.source is None
        mock_controller.send.assert_called_once_with("cmd_off")


class TestControls:
    """Tests for volume, track and source controls."""

    async def test_volume_up(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        await mp.async_volume_up()
        mock_controller.send.assert_called_once_with("cmd_volume_up")

    async def test_volume_down(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        await mp.async_volume_down()
        mock_controller.send.assert_called_once_with("cmd_volume_down")

    async def test_mute(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        await mp.async_mute_volume(True)
        mock_controller.send.assert_called_once_with("cmd_mute")

    async def test_previous_track(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        await mp.async_media_previous_track()
        mock_controller.send.assert_called_once_with("cmd_previous_channel")

    async def test_next_track(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        await mp.async_media_next_track()
        mock_controller.send.assert_called_once_with("cmd_next_channel")

    async def test_select_source(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        await mp.async_select_source("HDMI 2")
        assert mp.source == "HDMI 2"
        mock_controller.send.assert_called_once_with("cmd_hdmi2")


class TestPlayMedia:
    """Tests for async_play_media (channel change)."""

    async def test_play_channel_digits(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """A channel number sends one command per digit."""
        mp._state = MediaPlayerState.ON
        await mp.async_play_media(MediaType.CHANNEL, "12")
        mock_controller.send.assert_any_call("cmd_channel_1")
        mock_controller.send.assert_any_call("cmd_channel_2")
        assert mp.source == "Channel 12"

    async def test_play_turns_on_when_off(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """Playing media while off turns the device on first."""
        mp._state = MediaPlayerState.OFF
        await mp.async_play_media(MediaType.CHANNEL, "5")
        mock_controller.send.assert_any_call("cmd_on")

    async def test_invalid_media_type_ignored(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """A non-channel media type is ignored."""
        mp._state = MediaPlayerState.ON
        mock_controller.send.reset_mock()
        await mp.async_play_media("music", "12")
        mock_controller.send.assert_not_called()

    async def test_non_digit_media_id_ignored(self, mp: SmartIRMediaPlayer, mock_controller: MagicMock) -> None:
        """A non-numeric channel id is ignored."""
        mp._state = MediaPlayerState.ON
        mock_controller.send.reset_mock()
        await mp.async_play_media(MediaType.CHANNEL, "abc")
        mock_controller.send.assert_not_called()


class TestSendCommand:
    """Tests for send_command error handling."""

    async def test_controller_error_raises_home_assistant_error(
        self, mp: SmartIRMediaPlayer, mock_controller: MagicMock
    ) -> None:
        """A SmartIRControllerError becomes a HomeAssistantError."""
        mock_controller.send.side_effect = SmartIRControllerError("boom")
        with pytest.raises(HomeAssistantError):
            await mp.send_command("cmd_on")


class TestUpdateAndRestore:
    """Tests for async_update (power sensor) and state restoration."""

    async def test_update_without_power_sensor_is_noop(self, mp: SmartIRMediaPlayer) -> None:
        """Without a power sensor, async_update does nothing."""
        mp._state = MediaPlayerState.ON
        await mp.async_update()
        assert mp.state == MediaPlayerState.ON

    async def test_update_syncs_from_power_sensor(
        self, hass: HomeAssistant, make_smartir_data, mock_media_player_device_data, mock_controller
    ) -> None:
        """With a power sensor, async_update mirrors its on/off state."""
        data = make_smartir_data(device_type="media_player", power_sensor="sensor.tv_power")
        mp = create_mp_entity(hass, data, mock_media_player_device_data, mock_controller)

        hass.states.async_set("sensor.tv_power", STATE_ON)
        await mp.async_update()
        assert mp.state == MediaPlayerState.ON

        hass.states.async_set("sensor.tv_power", STATE_OFF)
        await mp.async_update()
        assert mp.state == MediaPlayerState.OFF

    async def test_restore_state(self, mp: SmartIRMediaPlayer) -> None:
        """The previous state is restored on add."""
        last_state = MagicMock(state="on")
        mp.async_get_last_state = AsyncMock(return_value=last_state)
        await mp.async_added_to_hass()
        assert mp.state == MediaPlayerState.ON

    async def test_restore_invalid_state_defaults_off(self, mp: SmartIRMediaPlayer) -> None:
        """An unparseable restored state falls back to off."""
        last_state = MagicMock(state="bogus")
        mp.async_get_last_state = AsyncMock(return_value=last_state)
        await mp.async_added_to_hass()
        assert mp.state == MediaPlayerState.OFF


class TestPlatformSetup:
    """Full config-entry setup exercises the thin media_player platform."""

    async def test_setup_registers_entity(
        self,
        hass: HomeAssistant,
        make_config_entry,
        mock_media_player_device_data,
        setup_smartir_entry,
        mock_remote_entity,
    ) -> None:
        """Setting up a media_player entry registers a media_player entity."""
        entry = make_config_entry(device_type="media_player")
        result, _ = await setup_smartir_entry(entry, mock_media_player_device_data)
        assert result is True
        assert any(state.entity_id.startswith("media_player.") for state in hass.states.async_all())
