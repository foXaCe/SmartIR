"""Tests for the SmartIR IR/RF controller implementations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.smartir.api.controller import (
    BROADLINK_CONTROLLER,
    ESPHOME_CONTROLLER,
    LOOKIN_CONTROLLER,
    MQTT_CONTROLLER,
    SEND_ATTEMPTS,
    XIAOMI_CONTROLLER,
    AbstractController,
    BroadlinkController,
    ESPHomeController,
    LookinController,
    MQTTController,
    XiaomiController,
    get_controller,
)
from custom_components.smartir.api.exceptions import (
    CommandConversionError,
    CommandSendError,
    UnsupportedControllerError,
    UnsupportedEncodingError,
)


def _controller(hass, name, encoding, data="remote.blaster", delay=0.1):
    return get_controller(hass, name, encoding, data, delay)


# ---------------------------------------------------------------------------
# get_controller / encoding validation
# ---------------------------------------------------------------------------


class TestGetController:
    """Tests for the get_controller factory."""

    @pytest.mark.parametrize(
        ("controller_name", "encoding", "expected_cls"),
        [
            (BROADLINK_CONTROLLER, "Base64", BroadlinkController),
            (XIAOMI_CONTROLLER, "Pronto", XiaomiController),
            (MQTT_CONTROLLER, "Raw", MQTTController),
            (LOOKIN_CONTROLLER, "Pronto", LookinController),
            (ESPHOME_CONTROLLER, "Raw", ESPHomeController),
        ],
    )
    def test_returns_matching_controller(self, hass: HomeAssistant, controller_name, encoding, expected_cls) -> None:
        """get_controller returns an instance of the class matching the requested controller."""
        controller = _controller(hass, controller_name, encoding)
        assert isinstance(controller, expected_cls)

    def test_unsupported_controller_raises(self, hass: HomeAssistant) -> None:
        """An unknown controller name raises UnsupportedControllerError."""
        with pytest.raises(UnsupportedControllerError, match="is not supported"):
            _controller(hass, "DoesNotExist", "Base64")


class TestCheckEncoding:
    """Tests for each controller's encoding validation."""

    def test_broadlink_invalid_encoding(self, hass: HomeAssistant) -> None:
        """Broadlink rejects an unsupported encoding."""
        with pytest.raises(UnsupportedEncodingError, match="not supported by the Broadlink"):
            BroadlinkController(hass, BROADLINK_CONTROLLER, "InvalidEncoding", "remote.test", 0.5)

    def test_xiaomi_invalid_encoding(self, hass: HomeAssistant) -> None:
        """Xiaomi rejects Base64 (not in its supported list)."""
        with pytest.raises(UnsupportedEncodingError, match="not supported by the Xiaomi"):
            XiaomiController(hass, XIAOMI_CONTROLLER, "Base64", "remote.test", 0.5)

    def test_mqtt_invalid_encoding(self, hass: HomeAssistant) -> None:
        """MQTT only supports Raw."""
        with pytest.raises(UnsupportedEncodingError, match="not supported by the MQTT"):
            MQTTController(hass, MQTT_CONTROLLER, "Base64", "smartir/command", 0.5)

    def test_lookin_invalid_encoding(self, hass: HomeAssistant) -> None:
        """LOOKin rejects Base64."""
        with pytest.raises(UnsupportedEncodingError, match="not supported by the LOOKin"):
            LookinController(hass, LOOKIN_CONTROLLER, "Base64", "192.168.1.100", 0.5)

    def test_esphome_invalid_encoding(self, hass: HomeAssistant) -> None:
        """ESPHome only supports Raw."""
        with pytest.raises(UnsupportedEncodingError, match="not supported by the ESPHome"):
            ESPHomeController(hass, ESPHOME_CONTROLLER, "Base64", "send_ir_command", 0.5)


# ---------------------------------------------------------------------------
# send() per controller
# ---------------------------------------------------------------------------


class TestBroadlinkSend:
    """Tests for BroadlinkController.send."""

    async def test_send_base64(self, hass: HomeAssistant) -> None:
        """A Base64 command is forwarded, b64-prefixed, to remote.send_command."""
        calls = async_mock_service(hass, "remote", "send_command")
        ctrl = _controller(hass, BROADLINK_CONTROLLER, "Base64")
        await ctrl.send("JgBGAAAB")
        assert len(calls) == 1
        assert calls[0].data["command"] == ["b64:JgBGAAAB"]
        assert calls[0].data["delay_secs"] == 0.1

    async def test_send_hex_converted_to_base64(self, hass: HomeAssistant) -> None:
        """A Hex command is converted to Base64 before being sent."""
        calls = async_mock_service(hass, "remote", "send_command")
        ctrl = _controller(hass, BROADLINK_CONTROLLER, "Hex")
        await ctrl.send("26004600")
        assert calls[0].data["command"][0].startswith("b64:")

    async def test_send_hex_invalid_raises_conversion_error(self, hass: HomeAssistant) -> None:
        """Invalid hex content raises CommandConversionError."""
        ctrl = _controller(hass, BROADLINK_CONTROLLER, "Hex")
        with pytest.raises(CommandConversionError, match="Hex to Base64"):
            await ctrl.send("nothex!!")

    async def test_send_pronto_converted(self, hass: HomeAssistant) -> None:
        """A Pronto command is converted via pronto2lirc + lirc2broadlink."""
        calls = async_mock_service(hass, "remote", "send_command")
        ctrl = _controller(hass, BROADLINK_CONTROLLER, "Pronto")
        await ctrl.send("0000 0071 0001 0000 0060 0018")
        assert calls[0].data["command"][0].startswith("b64:")

    async def test_send_pronto_invalid_raises_conversion_error(self, hass: HomeAssistant) -> None:
        """Invalid pronto content raises CommandConversionError."""
        ctrl = _controller(hass, BROADLINK_CONTROLLER, "Pronto")
        with pytest.raises(CommandConversionError, match="Pronto to Base64"):
            await ctrl.send("0001 006D 0001 0001 0010 0020")

    async def test_send_list_of_commands(self, hass: HomeAssistant) -> None:
        """A list of commands is forwarded as a batch, each prefixed with b64:."""
        calls = async_mock_service(hass, "remote", "send_command")
        ctrl = _controller(hass, BROADLINK_CONTROLLER, "Base64")
        await ctrl.send(["JgABAA==", "JgACAA=="])
        assert calls[0].data["command"] == ["b64:JgABAA==", "b64:JgACAA=="]


class TestXiaomiSend:
    """Tests for XiaomiController.send."""

    async def test_send_prefixes_encoding(self, hass: HomeAssistant) -> None:
        """The command is prefixed with the lowercased encoding."""
        calls = async_mock_service(hass, "remote", "send_command")
        ctrl = _controller(hass, XIAOMI_CONTROLLER, "Raw")
        await ctrl.send("0102030405")
        assert calls[0].data["command"] == "raw:0102030405"
        assert calls[0].data["entity_id"] == "remote.blaster"


class TestMqttSend:
    """Tests for MQTTController.send."""

    async def test_send_publishes_to_topic(self, hass: HomeAssistant) -> None:
        """The command is published as the payload on the configured topic."""
        calls = async_mock_service(hass, "mqtt", "publish")
        ctrl = _controller(hass, MQTT_CONTROLLER, "Raw", data="ir/topic")
        await ctrl.send("payload")
        assert calls[0].data == {"topic": "ir/topic", "payload": "payload"}


class TestESPHomeSend:
    """Tests for ESPHomeController.send."""

    async def test_send_calls_user_defined_service(self, hass: HomeAssistant) -> None:
        """The JSON command is parsed and forwarded to the user-defined ESPHome service."""
        calls = async_mock_service(hass, "esphome", "my_service")
        ctrl = _controller(hass, ESPHOME_CONTROLLER, "Raw", data="my_service")
        await ctrl.send('{"a": 1}')
        assert calls[0].data == {"command": {"a": 1}}


class TestLookinSend:
    """Tests for LookinController.send (HTTP)."""

    async def test_send_ok(self, hass: HomeAssistant) -> None:
        """A successful HTTP GET does not raise."""
        ctrl = _controller(hass, LOOKIN_CONTROLLER, "Raw", data="192.168.1.10")

        response = MagicMock()
        response.raise_for_status = MagicMock()
        session = MagicMock()
        session.get.return_value.__aenter__ = AsyncMock(return_value=response)
        session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("custom_components.smartir.api.controller.async_get_clientsession", return_value=session):
            await ctrl.send("ABCDEF")

        session.get.assert_called_once()
        url = session.get.call_args[0][0]
        assert url == "http://192.168.1.10/commands/ir/raw/ABCDEF"

    async def test_send_pronto_encoding_uses_prontohex_path(self, hass: HomeAssistant) -> None:
        """The 'pronto' encoding maps to the 'prontohex' URL segment."""
        ctrl = _controller(hass, LOOKIN_CONTROLLER, "Pronto", data="192.168.1.10")

        response = MagicMock()
        response.raise_for_status = MagicMock()
        session = MagicMock()
        session.get.return_value.__aenter__ = AsyncMock(return_value=response)
        session.get.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("custom_components.smartir.api.controller.async_get_clientsession", return_value=session):
            await ctrl.send("0000")

        url = session.get.call_args[0][0]
        assert "/commands/ir/prontohex/" in url

    async def test_send_error_raises_command_send_error_after_retries(self, hass: HomeAssistant) -> None:
        """A persistent network failure raises CommandSendError after all attempts."""
        ctrl = _controller(hass, LOOKIN_CONTROLLER, "Raw", data="192.168.1.10")
        session = MagicMock()
        session.get.side_effect = aiohttp.ClientError("boom")

        with (
            patch("custom_components.smartir.api.controller.async_get_clientsession", return_value=session),
            patch("custom_components.smartir.api.controller.asyncio.sleep", new=AsyncMock()),
            pytest.raises(CommandSendError),
        ):
            await ctrl.send("ABCDEF")

        assert session.get.call_count == SEND_ATTEMPTS


# ---------------------------------------------------------------------------
# Retry/backoff behaviour shared by all controllers
# ---------------------------------------------------------------------------


class TestRetryBehaviour:
    """Tests for AbstractController._async_retry / _async_call_with_retry."""

    def _broadlink(self, hass) -> BroadlinkController:
        return BroadlinkController(hass, BROADLINK_CONTROLLER, "Base64", "remote.blaster", 0.1)

    async def test_service_call_uses_blocking(self) -> None:
        """The service call is issued with blocking=True so errors propagate."""
        hass = MagicMock()
        hass.services.async_call = AsyncMock()
        ctrl = self._broadlink(hass)

        await ctrl._async_call_with_retry("remote", "send_command", {"a": 1})

        hass.services.async_call.assert_awaited_once_with("remote", "send_command", {"a": 1}, blocking=True)

    async def test_retry_succeeds_after_transient_failures(self) -> None:
        """Two transient failures then a success deliver the command without raising."""
        hass = MagicMock()
        hass.services.async_call = AsyncMock(
            side_effect=[HomeAssistantError("drop 1"), HomeAssistantError("drop 2"), None]
        )
        ctrl = self._broadlink(hass)

        with patch("custom_components.smartir.api.controller.asyncio.sleep", new=AsyncMock()) as sleep:
            await ctrl._async_call_with_retry("remote", "send_command", {})

        assert hass.services.async_call.await_count == 3
        assert sleep.await_count == 2
        # Backoff grows with the attempt number (SEND_BACKOFF * attempt).
        first_backoff = sleep.await_args_list[0].args[0]
        second_backoff = sleep.await_args_list[1].args[0]
        assert second_backoff > first_backoff

    async def test_retry_raises_after_all_attempts_fail(self) -> None:
        """Every attempt failing raises CommandSendError after SEND_ATTEMPTS tries."""
        hass = MagicMock()
        hass.services.async_call = AsyncMock(side_effect=HomeAssistantError("device unreachable"))
        ctrl = self._broadlink(hass)

        with (
            patch("custom_components.smartir.api.controller.asyncio.sleep", new=AsyncMock()),
            pytest.raises(CommandSendError, match="failed after 3 attempts"),
        ):
            await ctrl._async_call_with_retry("remote", "send_command", {})

        assert hass.services.async_call.await_count == SEND_ATTEMPTS

    async def test_broadlink_send_retries_end_to_end(self) -> None:
        """A full Broadlink send() retries the underlying service call transparently."""
        hass = MagicMock()
        hass.services.async_call = AsyncMock(side_effect=[HomeAssistantError("x"), None])
        ctrl = self._broadlink(hass)

        with patch("custom_components.smartir.api.controller.asyncio.sleep", new=AsyncMock()):
            await ctrl.send("JgABAA==")

        assert hass.services.async_call.await_count == 2
        assert hass.services.async_call.await_args.kwargs["blocking"] is True

    def test_abstract_controller_cannot_be_instantiated(self, hass: HomeAssistant) -> None:
        """AbstractController is an ABC and cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractController(hass, "X", "Base64", "remote.test", 0.5)  # type: ignore[abstract]
