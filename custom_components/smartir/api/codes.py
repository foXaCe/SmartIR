"""Device-code database access for SmartIR.

Device-code files are shipped in the repository under ``codes/<platform>/`` and
downloaded on demand to a local cache (``<component>/codes/<platform>/``) the
first time a given code is used. This module also holds the pure IR-code
conversion helpers used by the Broadlink controller.
"""

from __future__ import annotations

import binascii
import json
import logging
import os
import struct
from typing import Any

import aiofiles
import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import CODES_BASE_URL, CUSTOM_CODES_DIR
from .exceptions import DeviceDataError, DeviceDataNotFound

_LOGGER = logging.getLogger(__name__)

# <component>/ (parent of this api/ package), used to locate the codes cache.
_COMPONENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _codes_dir(platform: str) -> str:
    """Return the local cache directory for a platform's device codes."""
    return os.path.join(_COMPONENT_DIR, "codes", platform)


async def async_download_code(hass: HomeAssistant, url: str, dest_path: str) -> None:
    """Download a device-code file to ``dest_path`` using HA's shared session."""
    await hass.async_add_executor_job(os.makedirs, os.path.dirname(dest_path), 0o777, True)

    session = async_get_clientsession(hass)
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
        if response.status != 200:
            raise aiohttp.ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
            )
        async with aiofiles.open(dest_path, "wb") as file:
            async for chunk in response.content.iter_chunked(8192):
                await file.write(chunk)


async def _async_resolve_codes_path(hass: HomeAssistant, platform: str, device_code: int) -> str:
    """Resolve the on-disk path of a device-code file.

    Resolution order (first hit wins):

    1. custom user directory (``<config>/smartir_custom_codes/<platform>/``) —
       persistent across integration updates, takes priority;
    2. bundled/cached codes (``<component>/codes/<platform>/``);
    3. download from the upstream database into the bundled cache.

    Raises :class:`DeviceDataNotFound` if the code is nowhere and cannot be
    downloaded.
    """
    filename = f"{device_code}.json"

    custom_path = hass.config.path(CUSTOM_CODES_DIR, platform, filename)
    if await hass.async_add_executor_job(os.path.isfile, custom_path):
        _LOGGER.debug("SmartIR: codes for %s/%s loaded from the custom directory", platform, device_code)
        return custom_path

    bundled_path = os.path.join(_codes_dir(platform), filename)
    if await hass.async_add_executor_job(os.path.isfile, bundled_path):
        _LOGGER.debug("SmartIR: codes for %s/%s loaded from bundled codes", platform, device_code)
        return bundled_path

    url = f"{CODES_BASE_URL}/{platform}/{device_code}.json"
    try:
        await async_download_code(hass, url, bundled_path)
    except (aiohttp.ClientError, OSError) as err:
        raise DeviceDataNotFound(f"Could not download device code {device_code} for {platform}: {err}") from err
    _LOGGER.info("SmartIR: downloaded codes for %s/%s", platform, device_code)
    return bundled_path


async def async_load_device_data(hass: HomeAssistant, platform: str, device_code: int) -> dict[str, Any]:
    """Return the parsed device-code data for a platform/code.

    Resolves the file via :func:`_async_resolve_codes_path` (custom → bundled →
    download). Raises :class:`DeviceDataNotFound` if it cannot be retrieved and
    :class:`DeviceDataError` if it cannot be parsed.
    """
    json_path = await _async_resolve_codes_path(hass, platform, device_code)

    try:
        async with aiofiles.open(json_path) as file:
            content = await file.read()
        data: dict[str, Any] = json.loads(content)
    except (OSError, json.JSONDecodeError) as err:
        raise DeviceDataError(f"Invalid device-code file {json_path}: {err}") from err
    return data


def pronto2lirc(pronto: bytearray) -> list[int]:
    """Convert a Pronto code to a LIRC pulse list."""
    codes = [int(binascii.hexlify(pronto[i : i + 2]), 16) for i in range(0, len(pronto), 2)]

    if codes[0]:
        raise ValueError("Pronto code should start with 0000")
    if len(codes) != 4 + 2 * (codes[2] + codes[3]):
        raise ValueError("Number of pulse widths does not match the preamble")

    frequency = 1 / (codes[1] * 0.241246)
    return [int(round(code / frequency)) for code in codes[4:]]


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

    # Pad to a multiple of 16 for 128-bit AES encryption.
    remainder = (len(packet) + 4) % 16
    if remainder:
        packet += bytearray(16 - remainder)
    return packet
