"""SmartIR media player entity (IR/RF TVs and audio devices)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from ..api.exceptions import SmartIRControllerError
from ..const import CONF_DEVICE_CLASS, CONF_SOURCE_NAMES, SmartIRData
from ..entity import SmartIREntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_DEVICE_CLASS = "tv"

_DEVICE_CLASSES = {
    "tv": MediaPlayerDeviceClass.TV,
    "speaker": MediaPlayerDeviceClass.SPEAKER,
    "receiver": MediaPlayerDeviceClass.RECEIVER,
}
_ICONS = {"tv": "mdi:television", "speaker": "mdi:speaker", "receiver": "mdi:audio-video"}


class SmartIRMediaPlayer(SmartIREntity, MediaPlayerEntity):
    """SmartIR media player entity for controlling IR TVs and audio devices."""

    PLATFORM = "media_player"

    def __init__(self, hass: HomeAssistant, data: SmartIRData, device_data: dict[str, Any]) -> None:
        """Initialize the media player entity from its device-code data."""
        super().__init__(hass, data, device_data)

        self._state: MediaPlayerState = MediaPlayerState.OFF
        self._sources_list: list[str] = []
        self._source: str | None = None
        self._support_flags = MediaPlayerEntityFeature(0)

        raw_device_class = data.extra.get(CONF_DEVICE_CLASS, DEFAULT_DEVICE_CLASS)
        self._attr_device_class = _DEVICE_CLASSES.get(raw_device_class, MediaPlayerDeviceClass.TV)

        commands = self._commands
        if commands.get("off") is not None:
            self._support_flags |= MediaPlayerEntityFeature.TURN_OFF
        if commands.get("on") is not None:
            self._support_flags |= MediaPlayerEntityFeature.TURN_ON
        if commands.get("previousChannel") is not None:
            self._support_flags |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if commands.get("nextChannel") is not None:
            self._support_flags |= MediaPlayerEntityFeature.NEXT_TRACK
        if commands.get("volumeDown") is not None or commands.get("volumeUp") is not None:
            self._support_flags |= MediaPlayerEntityFeature.VOLUME_STEP
        if commands.get("mute") is not None:
            self._support_flags |= MediaPlayerEntityFeature.VOLUME_MUTE

        if commands.get("sources") is not None:
            self._support_flags |= MediaPlayerEntityFeature.SELECT_SOURCE | MediaPlayerEntityFeature.PLAY_MEDIA

            for source, new_name in data.extra.get(CONF_SOURCE_NAMES, {}).items():
                if source in commands["sources"]:
                    if new_name is not None:
                        commands["sources"][new_name] = commands["sources"][source]
                    del commands["sources"][source]

            self._sources_list = list(commands["sources"])

        self._attr_icon = _ICONS.get(raw_device_class, "mdi:television")

    async def async_added_to_hass(self) -> None:
        """Restore the previous state."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                self._state = MediaPlayerState(last_state.state)
            except ValueError:
                self._state = MediaPlayerState.OFF

    @property
    def should_poll(self) -> bool:
        """Poll to keep the state in sync with an optional power sensor."""
        return True

    @property
    def state(self) -> MediaPlayerState:
        """Return the current state."""
        return self._state

    @property
    def media_content_type(self) -> str:
        """Return the content type of the current media."""
        return MediaType.CHANNEL

    @property
    def source_list(self) -> list[str]:
        """Return the list of available sources."""
        return self._sources_list

    @property
    def source(self) -> str | None:
        """Return the current source."""
        return self._source

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the supported features."""
        return self._support_flags

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self.send_command(self._commands["off"])
        if self._power_sensor is None:
            self._state = MediaPlayerState.OFF
            self._source = None
            self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self.send_command(self._commands["on"])
        if self._power_sensor is None:
            self._state = MediaPlayerState.ON
            self.async_write_ha_state()

    async def async_media_previous_track(self) -> None:
        """Send the previous-track command."""
        await self.send_command(self._commands["previousChannel"])
        self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Send the next-track command."""
        await self.send_command(self._commands["nextChannel"])
        self.async_write_ha_state()

    async def async_volume_down(self) -> None:
        """Send the volume-down command."""
        await self.send_command(self._commands["volumeDown"])
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Send the volume-up command."""
        await self.send_command(self._commands["volumeUp"])
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Send the mute command."""
        await self.send_command(self._commands["mute"])
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select a source."""
        self._source = source
        await self.send_command(self._commands["sources"][source])
        self.async_write_ha_state()

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        """Change channel through the play_media service."""
        if self._state == MediaPlayerState.OFF:
            await self.async_turn_on()

        if media_type != MediaType.CHANNEL:
            _LOGGER.error("Invalid media type")
            return
        if not media_id.isdigit():
            _LOGGER.error("media_id must be a channel number")
            return

        self._source = f"Channel {media_id}"
        for digit in media_id:
            await self.send_command(self._commands["sources"][f"Channel {digit}"])
        self.async_write_ha_state()

    async def send_command(self, command: str) -> None:
        """Send a raw command through the controller."""
        async with self._temp_lock:
            try:
                await self._controller.send(command)
            except SmartIRControllerError as err:
                raise self._command_error(err) from err

    async def async_update(self) -> None:
        """Sync the state from an optional power sensor."""
        if self._power_sensor is None:
            return

        power_state = self.hass.states.get(self._power_sensor)
        if power_state:
            if power_state.state == STATE_OFF:
                self._state = MediaPlayerState.OFF
                self._source = None
            elif power_state.state == STATE_ON:
                self._state = MediaPlayerState.ON
