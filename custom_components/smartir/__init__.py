"""The SmartIR integration."""

from __future__ import annotations

import binascii
import logging
import os
import struct

import aiofiles
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

# Component absolute directory path for device codes
COMPONENT_ABS_DIR = os.path.dirname(os.path.abspath(__file__))

from .const import DOMAIN, SmartIRConfigEntry, SmartIRData

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_update_options(hass: HomeAssistant, entry: SmartIRConfigEntry) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: SmartIRConfigEntry) -> bool:
    """Set up SmartIR from a config entry."""
    # Use options if available, otherwise use data
    config_data = {**entry.data, **entry.options}

    device_type = config_data.get("device_type", "climate")
    device_name = config_data.get("name", f"SmartIR {device_type.title()}")
    controller_data = config_data.get("controller_data", "")

    # test-before-setup: the IR/RF controller entity must be available.
    if controller_data and hass.states.get(controller_data) is None:
        raise ConfigEntryNotReady(f"Controller entity '{controller_data}' is not available yet")

    # Store runtime data using the modern pattern
    entry.runtime_data = SmartIRData(
        device_type=device_type,
        controller_type=config_data.get("controller", ""),
        name=device_name,
        device_code=config_data.get("device_code", 0),
        controller_data=controller_data,
        delay=config_data.get("delay", 0.5),
        temperature_sensor=config_data.get("temperature_sensor"),
        humidity_sensor=config_data.get("humidity_sensor"),
        power_sensor=config_data.get("power_sensor"),
        power_sensor_restore_state=config_data.get("power_sensor_restore_state", False),
        unique_id=entry.unique_id,
    )

    await hass.config_entries.async_forward_entry_setups(entry, [device_type])
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartIRConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [entry.runtime_data.device_type])


class Helper:
    """Helper class for IR code conversion and device-code downloads."""

    @staticmethod
    async def downloader(hass: HomeAssistant, url: str, dest_path: str) -> None:
        """Download a device-code file to dest_path using Home Assistant's shared session."""
        dest_dir = os.path.dirname(dest_path)
        await hass.async_add_executor_job(os.makedirs, dest_dir, 0o777, True)

        session = async_get_clientsession(hass)
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status != 200:
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                )
            async with aiofiles.open(dest_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    await f.write(chunk)

    @staticmethod
    def pronto2lirc(pronto: bytearray) -> list[int]:
        """Convert a Pronto code to a LIRC pulse list."""
        codes = [int(binascii.hexlify(pronto[i : i + 2]), 16) for i in range(0, len(pronto), 2)]

        if codes[0]:
            raise ValueError("Pronto code should start with 0000")
        if len(codes) != 4 + 2 * (codes[2] + codes[3]):
            raise ValueError("Number of pulse widths does not match the preamble")

        frequency = 1 / (codes[1] * 0.241246)
        return [int(round(code / frequency)) for code in codes[4:]]

    @staticmethod
    def lirc2broadlink(pulses: list[int]) -> bytearray:
        """Convert a LIRC pulse list to a Broadlink packet."""
        array = bytearray()

        for pulse in pulses:
            pulse = int(pulse * 269 / 8192)

            if pulse < 256:
                array += bytearray(struct.pack(">B", pulse))
            else:
                array += bytearray([0x00])
                array += bytearray(struct.pack(">H", pulse))

        packet = bytearray([0x26, 0x00])
        packet += bytearray(struct.pack("<H", len(array)))
        packet += array
        packet += bytearray([0x0D, 0x05])

        # Add 0s to make ultimate packet size a multiple of 16 for 128-bit AES encryption.
        remainder = (len(packet) + 4) % 16
        if remainder:
            packet += bytearray(16 - remainder)
        return packet
