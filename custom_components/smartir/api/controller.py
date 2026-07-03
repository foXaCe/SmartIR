"""IR/RF controller implementations for SmartIR.

Each controller translates an abstract command (from a device-code file) into a
concrete Home Assistant service call (or HTTP request for LOOKin) toward the
physical IR/RF blaster. Delivery is retried with a backoff because IR/RF links
are unreliable (e.g. a Broadlink RM over WiFi may drop the outgoing packet).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from base64 import b64encode
import binascii
from collections.abc import Awaitable, Callable
import json
import logging
from typing import Any, cast

import aiohttp
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .codes import lirc2broadlink, pronto2lirc
from .exceptions import (
    CommandConversionError,
    CommandSendError,
    UnsupportedControllerError,
    UnsupportedEncodingError,
)

_LOGGER = logging.getLogger(__name__)

# Retry policy for command delivery over unreliable IR/RF links.
SEND_ATTEMPTS = 3
SEND_BACKOFF = 0.4

BROADLINK_CONTROLLER = "Broadlink"
XIAOMI_CONTROLLER = "Xiaomi"
MQTT_CONTROLLER = "MQTT"
LOOKIN_CONTROLLER = "LOOKin"
ESPHOME_CONTROLLER = "ESPHome"

ENC_BASE64 = "Base64"
ENC_HEX = "Hex"
ENC_PRONTO = "Pronto"
ENC_RAW = "Raw"

BROADLINK_COMMANDS_ENCODING = [ENC_BASE64, ENC_HEX, ENC_PRONTO]
XIAOMI_COMMANDS_ENCODING = [ENC_PRONTO, ENC_RAW]
MQTT_COMMANDS_ENCODING = [ENC_RAW]
LOOKIN_COMMANDS_ENCODING = [ENC_PRONTO, ENC_RAW]
ESPHOME_COMMANDS_ENCODING = [ENC_RAW]


def get_controller(
    hass: HomeAssistant,
    controller: str,
    encoding: str,
    controller_data: str,
    delay: float,
) -> AbstractController:
    """Return a controller matching the requested specification."""
    controllers: dict[str, type[AbstractController]] = {
        BROADLINK_CONTROLLER: BroadlinkController,
        XIAOMI_CONTROLLER: XiaomiController,
        MQTT_CONTROLLER: MQTTController,
        LOOKIN_CONTROLLER: LookinController,
        ESPHOME_CONTROLLER: ESPHomeController,
    }
    try:
        return controllers[controller](hass, controller, encoding, controller_data, delay)
    except KeyError as err:
        raise UnsupportedControllerError(f"The controller '{controller}' is not supported.") from err


class AbstractController(ABC):
    """Base class for all IR/RF controllers."""

    def __init__(
        self,
        hass: HomeAssistant,
        controller: str,
        encoding: str,
        controller_data: str,
        delay: float,
    ) -> None:
        """Initialize the controller."""
        self.check_encoding(encoding)
        self.hass = hass
        self._controller = controller
        self._encoding = encoding
        self._controller_data = controller_data
        self._delay = delay

    @abstractmethod
    def check_encoding(self, encoding: str) -> None:
        """Validate that the encoding is supported by the controller."""

    @abstractmethod
    async def send(self, command: str | list[str]) -> None:
        """Send a command."""

    async def _async_retry(self, action: Callable[[], Awaitable[Any]], describe: str) -> None:
        """Run ``action`` with a bounded retry/backoff, shared by all controllers.

        Raises :class:`CommandSendError` if every attempt fails, so callers can
        revert optimistic state instead of silently dropping the command.
        """
        last_err: Exception | None = None
        for attempt in range(1, SEND_ATTEMPTS + 1):
            try:
                await action()
                return
            except Exception as err:  # noqa: BLE001 - re-raised as CommandSendError below
                last_err = err
                _LOGGER.warning("SmartIR: %s attempt %s/%s failed: %s", describe, attempt, SEND_ATTEMPTS, err)
                if attempt < SEND_ATTEMPTS:
                    await asyncio.sleep(SEND_BACKOFF * attempt)

        raise CommandSendError(f"{describe} failed after {SEND_ATTEMPTS} attempts: {last_err}") from last_err

    async def _async_call_with_retry(self, domain: str, service: str, service_data: dict[str, Any]) -> None:
        """Call a HA service with ``blocking=True``, retried on failure.

        ``blocking=True`` propagates the service error (e.g. device unreachable)
        so a transient hiccup can be retried instead of silently dropping it.
        """
        await self._async_retry(
            lambda: self.hass.services.async_call(domain, service, service_data, blocking=True),
            f"{domain}.{service}",
        )


class BroadlinkController(AbstractController):
    """Controls a Broadlink device."""

    def check_encoding(self, encoding: str) -> None:
        """Validate the encoding."""
        if encoding not in BROADLINK_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the Broadlink controller.")

    async def send(self, command: str | list[str]) -> None:
        """Send a command."""
        commands: list[str] = []
        raw_commands = command if isinstance(command, list) else [command]

        for raw in raw_commands:
            if self._encoding == ENC_HEX:
                try:
                    encoded = b64encode(binascii.unhexlify(raw)).decode("utf-8")
                except (binascii.Error, ValueError) as err:
                    raise CommandConversionError("Error while converting Hex to Base64 encoding") from err
            elif self._encoding == ENC_PRONTO:
                try:
                    pulses = pronto2lirc(bytearray.fromhex(raw.replace(" ", "")))
                    encoded = b64encode(lirc2broadlink(pulses)).decode("utf-8")
                except (ValueError, TypeError) as err:
                    raise CommandConversionError("Error while converting Pronto to Base64 encoding") from err
            else:
                encoded = raw
            commands.append("b64:" + encoded)

        service_data: dict[str, Any] = {
            ATTR_ENTITY_ID: self._controller_data,
            "command": commands,
            "delay_secs": self._delay,
        }

        await self._async_call_with_retry("remote", "send_command", service_data)


class XiaomiController(AbstractController):
    """Controls a Xiaomi device."""

    def check_encoding(self, encoding: str) -> None:
        """Validate the encoding."""
        if encoding not in XIAOMI_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the Xiaomi controller.")

    async def send(self, command: str | list[str]) -> None:
        """Send a command."""
        service_data: dict[str, Any] = {
            ATTR_ENTITY_ID: self._controller_data,
            "command": f"{self._encoding.lower()}:{command}",
        }

        await self._async_call_with_retry("remote", "send_command", service_data)


class MQTTController(AbstractController):
    """Controls an MQTT device."""

    def check_encoding(self, encoding: str) -> None:
        """Validate the encoding."""
        if encoding not in MQTT_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the MQTT controller.")

    async def send(self, command: str | list[str]) -> None:
        """Send a command."""
        service_data: dict[str, Any] = {"topic": self._controller_data, "payload": command}

        await self._async_call_with_retry("mqtt", "publish", service_data)


class LookinController(AbstractController):
    """Controls a LOOKin device over HTTP."""

    def check_encoding(self, encoding: str) -> None:
        """Validate the encoding."""
        if encoding not in LOOKIN_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the LOOKin controller.")

    async def send(self, command: str | list[str]) -> None:
        """Send a command over HTTP with the shared retry policy."""
        encoding = self._encoding.lower().replace("pronto", "prontohex")
        url = f"http://{self._controller_data}/commands/ir/{encoding}/{command}"
        session = async_get_clientsession(self.hass)

        async def _do_request() -> None:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                response.raise_for_status()

        await self._async_retry(_do_request, "LOOKin")


class ESPHomeController(AbstractController):
    """Controls an ESPHome device."""

    def check_encoding(self, encoding: str) -> None:
        """Validate the encoding."""
        if encoding not in ESPHOME_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the ESPHome controller.")

    async def send(self, command: str | list[str]) -> None:
        """Send a command."""
        service_data: dict[str, Any] = {"command": json.loads(cast(str, command))}

        await self._async_call_with_retry("esphome", self._controller_data, service_data)
