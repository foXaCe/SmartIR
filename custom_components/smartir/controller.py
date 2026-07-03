"""IR Controller implementations for SmartIR."""

from abc import ABC, abstractmethod
from base64 import b64encode
import binascii
import json
import logging

import aiohttp
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import Helper

_LOGGER = logging.getLogger(__name__)

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


class SmartIRControllerError(Exception):
    """Base exception for SmartIR controller errors."""


class UnsupportedControllerError(SmartIRControllerError):
    """Raised when an unsupported controller is requested."""


class UnsupportedEncodingError(SmartIRControllerError):
    """Raised when an unsupported encoding is used."""


class CommandConversionError(SmartIRControllerError):
    """Raised when command conversion fails."""


class CommandSendError(SmartIRControllerError):
    """Raised when sending a command fails."""


def get_controller(hass, controller, encoding, controller_data, delay):
    """Return a controller compatible with the specification provided."""
    controllers = {
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
    """Representation of a controller."""

    def __init__(self, hass, controller, encoding, controller_data, delay):
        """Initialize the controller."""
        self.check_encoding(encoding)
        self.hass = hass
        self._controller = controller
        self._encoding = encoding
        self._controller_data = controller_data
        self._delay = delay

    @abstractmethod
    def check_encoding(self, encoding):
        """Check if the encoding is supported by the controller."""

    @abstractmethod
    async def send(self, command):
        """Send a command."""


class BroadlinkController(AbstractController):
    """Controls a Broadlink device."""

    def check_encoding(self, encoding):
        """Check if the encoding is supported by the controller."""
        if encoding not in BROADLINK_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the Broadlink controller.")

    async def send(self, command):
        """Send a command."""
        commands = []

        if not isinstance(command, list):
            command = [command]

        for _command in command:
            if self._encoding == ENC_HEX:
                try:
                    _command = binascii.unhexlify(_command)
                    _command = b64encode(_command).decode("utf-8")
                except (binascii.Error, ValueError) as err:
                    raise CommandConversionError("Error while converting Hex to Base64 encoding") from err

            if self._encoding == ENC_PRONTO:
                try:
                    _command = _command.replace(" ", "")
                    _command = bytearray.fromhex(_command)
                    _command = Helper.pronto2lirc(_command)
                    _command = Helper.lirc2broadlink(_command)
                    _command = b64encode(_command).decode("utf-8")
                except (ValueError, TypeError) as err:
                    raise CommandConversionError("Error while converting Pronto to Base64 encoding") from err

            commands.append("b64:" + _command)

        service_data = {
            ATTR_ENTITY_ID: self._controller_data,
            "command": commands,
            "delay_secs": self._delay,
        }

        await self.hass.services.async_call("remote", "send_command", service_data)


class XiaomiController(AbstractController):
    """Controls a Xiaomi device."""

    def check_encoding(self, encoding):
        """Check if the encoding is supported by the controller."""
        if encoding not in XIAOMI_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the Xiaomi controller.")

    async def send(self, command):
        """Send a command."""
        service_data = {
            ATTR_ENTITY_ID: self._controller_data,
            "command": self._encoding.lower() + ":" + command,
        }

        await self.hass.services.async_call("remote", "send_command", service_data)


class MQTTController(AbstractController):
    """Controls a MQTT device."""

    def check_encoding(self, encoding):
        """Check if the encoding is supported by the controller."""
        if encoding not in MQTT_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the MQTT controller.")

    async def send(self, command):
        """Send a command."""
        service_data = {"topic": self._controller_data, "payload": command}

        await self.hass.services.async_call("mqtt", "publish", service_data)


class LookinController(AbstractController):
    """Controls a LOOKin device."""

    def check_encoding(self, encoding):
        """Check if the encoding is supported by the controller."""
        if encoding not in LOOKIN_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the LOOKin controller.")

    async def send(self, command):
        """Send a command."""
        encoding = self._encoding.lower().replace("pronto", "prontohex")
        url = f"http://{self._controller_data}/commands/ir/{encoding}/{command}"

        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    _LOGGER.warning("LOOKin controller returned status %s", response.status)
        except aiohttp.ClientError as err:
            _LOGGER.error("Failed to send command to LOOKin controller: %s", err)
            raise CommandSendError(f"Failed to send command to LOOKin controller: {err}") from err


class ESPHomeController(AbstractController):
    """Controls an ESPHome device."""

    def check_encoding(self, encoding):
        """Check if the encoding is supported by the controller."""
        if encoding not in ESPHOME_COMMANDS_ENCODING:
            raise UnsupportedEncodingError("The encoding is not supported by the ESPHome controller.")

    async def send(self, command):
        """Send a command."""
        service_data = {"command": json.loads(command)}

        await self.hass.services.async_call("esphome", self._controller_data, service_data)
