"""Tests for the SmartIR controller send() implementations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.smartir.controller import (
    BROADLINK_CONTROLLER,
    ESPHOME_CONTROLLER,
    LOOKIN_CONTROLLER,
    MQTT_CONTROLLER,
    XIAOMI_CONTROLLER,
    CommandConversionError,
    CommandSendError,
    get_controller,
)


def _controller(hass, name, encoding, data="remote.blaster", delay=0.1):
    return get_controller(hass, name, encoding, data, delay)


async def test_broadlink_send_base64(hass: HomeAssistant) -> None:
    """Broadlink base64 command is forwarded to remote.send_command."""
    calls = async_mock_service(hass, "remote", "send_command")
    ctrl = _controller(hass, BROADLINK_CONTROLLER, "Base64")
    await ctrl.send("JgBGAAAB")
    assert len(calls) == 1
    assert calls[0].data["command"] == ["b64:JgBGAAAB"]
    assert calls[0].data["delay_secs"] == 0.1


async def test_broadlink_send_hex(hass: HomeAssistant) -> None:
    """Broadlink hex commands are converted to base64."""
    calls = async_mock_service(hass, "remote", "send_command")
    ctrl = _controller(hass, BROADLINK_CONTROLLER, "Hex")
    await ctrl.send("26004600")
    assert calls[0].data["command"][0].startswith("b64:")


async def test_broadlink_send_hex_invalid(hass: HomeAssistant) -> None:
    """Invalid hex raises a CommandConversionError."""
    ctrl = _controller(hass, BROADLINK_CONTROLLER, "Hex")
    with pytest.raises(CommandConversionError):
        await ctrl.send("nothex!!")


async def test_broadlink_send_list(hass: HomeAssistant) -> None:
    """A list of commands is sent as a batch."""
    calls = async_mock_service(hass, "remote", "send_command")
    ctrl = _controller(hass, BROADLINK_CONTROLLER, "Base64")
    await ctrl.send(["JgABAA==", "JgACAA=="])
    assert calls[0].data["command"] == ["b64:JgABAA==", "b64:JgACAA=="]


async def test_xiaomi_send(hass: HomeAssistant) -> None:
    """Xiaomi commands are prefixed with the encoding."""
    calls = async_mock_service(hass, "remote", "send_command")
    ctrl = _controller(hass, XIAOMI_CONTROLLER, "Raw")
    await ctrl.send("0102030405")
    assert calls[0].data["command"] == "raw:0102030405"


async def test_mqtt_send(hass: HomeAssistant) -> None:
    """MQTT commands are published to the configured topic."""
    calls = async_mock_service(hass, "mqtt", "publish")
    ctrl = _controller(hass, MQTT_CONTROLLER, "Raw", data="ir/topic")
    await ctrl.send("payload")
    assert calls[0].data == {"topic": "ir/topic", "payload": "payload"}


async def test_esphome_send(hass: HomeAssistant) -> None:
    """ESPHome commands call the user-defined service with parsed JSON."""
    calls = async_mock_service(hass, "esphome", "my_service")
    ctrl = _controller(hass, ESPHOME_CONTROLLER, "Raw", data="my_service")
    await ctrl.send('{"a": 1}')
    assert calls[0].data == {"command": {"a": 1}}


async def test_lookin_send_ok(hass: HomeAssistant) -> None:
    """LOOKin sends an HTTP GET and succeeds on status 200."""
    ctrl = _controller(hass, LOOKIN_CONTROLLER, "Raw", data="192.168.1.10")

    response = MagicMock()
    response.status = 200
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    session.get.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch("custom_components.smartir.controller.async_get_clientsession", return_value=session):
        await ctrl.send("ABCDEF")
    session.get.assert_called_once()


async def test_lookin_send_error(hass: HomeAssistant) -> None:
    """A network failure raises CommandSendError."""
    import aiohttp

    ctrl = _controller(hass, LOOKIN_CONTROLLER, "Raw", data="192.168.1.10")
    session = MagicMock()
    session.get.side_effect = aiohttp.ClientError("boom")

    with (
        patch("custom_components.smartir.controller.async_get_clientsession", return_value=session),
        pytest.raises(CommandSendError),
    ):
        await ctrl.send("ABCDEF")
