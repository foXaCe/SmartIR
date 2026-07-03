import binascii
import logging
import os
import struct

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

# Component absolute directory path for device codes
COMPONENT_ABS_DIR = os.path.dirname(os.path.abspath(__file__))

from .const import (
    SmartIRConfigEntry,
    SmartIRData,
)

# from .hub import SmartIRHub  # Temporary disable

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SmartIR component from YAML configuration (deprecated)."""
    return True


async def async_update_options(hass: HomeAssistant, entry: SmartIRConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: SmartIRConfigEntry) -> bool:
    """Set up SmartIR from a config entry."""
    # Use options if available, otherwise use data
    config_data = {**entry.data, **entry.options}

    # Read with simple keys (not CONF_ constants)
    device_type = config_data.get("device_type", "climate")
    device_name = config_data.get("name", f"SmartIR {device_type.title()}")

    # Store runtime data using the modern pattern
    entry.runtime_data = SmartIRData(
        device_type=device_type,
        controller_type=config_data.get("controller", ""),
        name=device_name,
        device_code=config_data.get("device_code", 0),
        controller_data=config_data.get("controller_data", ""),
        delay=config_data.get("delay", 0.5),
        temperature_sensor=config_data.get("temperature_sensor"),
        humidity_sensor=config_data.get("humidity_sensor"),
        power_sensor=config_data.get("power_sensor"),
        power_sensor_restore_state=config_data.get("power_sensor_restore_state", False),
        unique_id=entry.unique_id,
    )

    # Forward the setup to the platform
    platforms = [device_type]

    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SmartIRConfigEntry) -> bool:
    """Unload a config entry."""
    device_type = entry.runtime_data.device_type

    # Determine platforms to unload
    platforms = [device_type]

    return await hass.config_entries.async_unload_platforms(entry, platforms)


async def async_reload_entry(hass: HomeAssistant, entry: SmartIRConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class Helper:
    """Helper class for IR code conversion."""

    @staticmethod
    async def downloader(url, dest_path):
        """Download a file from URL to destination path."""
        import aiofiles
        import aiohttp

        # Ensure directory exists
        dest_dir = os.path.dirname(dest_path)
        os.makedirs(dest_dir, exist_ok=True)

        try:
            async with aiohttp.ClientSession() as session, session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(dest_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)

                    if not os.path.exists(dest_path):
                        raise FileNotFoundError(f"Downloaded file not found: {dest_path}")
                else:
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info, history=response.history, status=response.status
                    )
        except Exception as e:
            _LOGGER.error(f"Download failed for {url}: {e}")
            raise

    @staticmethod
    def pronto2lirc(pronto):
        codes = [int(binascii.hexlify(pronto[i : i + 2]), 16) for i in range(0, len(pronto), 2)]

        if codes[0]:
            raise ValueError("Pronto code should start with 0000")
        if len(codes) != 4 + 2 * (codes[2] + codes[3]):
            raise ValueError("Number of pulse widths does not match the preamble")

        frequency = 1 / (codes[1] * 0.241246)
        return [int(round(code / frequency)) for code in codes[4:]]

    @staticmethod
    def lirc2broadlink(pulses):
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
