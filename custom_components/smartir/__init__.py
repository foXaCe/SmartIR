import binascii
import logging
import struct
import os

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

# Component absolute directory path for device codes
COMPONENT_ABS_DIR = os.path.dirname(os.path.abspath(__file__))

from .const import (
    DOMAIN, 
    VERSION,
    CONF_CONTROLLER_TYPE, 
    CONF_DEVICE_TYPE,
    CONF_NAME,
    CONF_DEVICE_CODE,
    CONF_CONTROLLER_DATA,
    CONF_DELAY,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_POWER_SENSOR,
    CONF_POWER_SENSOR_RESTORE_STATE
)
# from .hub import SmartIRHub  # Temporary disable

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SmartIR component from YAML configuration (deprecated)."""
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SmartIR from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create or get the SmartIR Hub - Temporary disabled
    # if "hub" not in hass.data[DOMAIN]:
    #     hub = SmartIRHub(hass, "smartir_hub")
    #     hass.data[DOMAIN]["hub"] = hub
    #     _LOGGER.info("SmartIR Hub created")
    # else:
    #     hub = hass.data[DOMAIN]["hub"]
    hub = None  # Temporary
    
    # Use options if available, otherwise use data
    config_data = {**entry.data, **entry.options}
    
    # Read with simple keys (not CONF_ constants)
    device_type = config_data.get("device_type", "climate")
    controller_type = config_data.get("controller", "broadlink")
    device_code = config_data.get("device_code")
    device_name = config_data.get("name", f"SmartIR {device_type.title()}")
    
    # Convert to format expected by platforms (with CONF_ keys)
    platform_config = {
        CONF_DEVICE_TYPE: config_data.get("device_type"),
        CONF_CONTROLLER_TYPE: config_data.get("controller"),
        CONF_NAME: device_name,
        CONF_DEVICE_CODE: device_code,
        CONF_CONTROLLER_DATA: config_data.get("controller_data"),
    }
    
    # Add optional fields
    if "delay" in config_data:
        platform_config[CONF_DELAY] = config_data["delay"]
    if "temperature_sensor" in config_data:
        platform_config[CONF_TEMPERATURE_SENSOR] = config_data["temperature_sensor"]
    if "humidity_sensor" in config_data:
        platform_config[CONF_HUMIDITY_SENSOR] = config_data["humidity_sensor"]
    if "power_sensor" in config_data:
        platform_config[CONF_POWER_SENSOR] = config_data["power_sensor"]
    if "power_sensor_restore_state" in config_data:
        platform_config[CONF_POWER_SENSOR_RESTORE_STATE] = config_data["power_sensor_restore_state"]
    
    # Add hub reference to config
    platform_config["hub"] = hub
    
    hass.data[DOMAIN][entry.entry_id] = platform_config

    # Forward the setup to the platform
    platforms = [device_type]

    # Add sensor platform for hub status (only for the first device)
    if len([k for k in hass.data[DOMAIN].keys() if k != "hub"]) == 1:
        platforms.append("sensor")
    
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    
    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device_type = entry.data.get("device_type", "climate")
    device_code = entry.data.get("device_code")
    
    # Determine platforms to unload
    platforms = [device_type]
    
    # Check if this is the last device (unload sensor platform too)
    remaining_devices = len([k for k in hass.data[DOMAIN].keys() if k != "hub" and k != entry.entry_id])
    if remaining_devices == 0:
        platforms.append("sensor")
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    
    if unload_ok:
        # Unregister device from hub - Temporary disabled
        # if "hub" in hass.data[DOMAIN]:
        #     hub = hass.data[DOMAIN]["hub"]
        #     hub.unregister_device(device_code, device_type)
            
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class Helper():
    """Helper class for IR code conversion."""

    @staticmethod
    async def downloader(url, dest_path):
        """Download a file from URL to destination path."""
        import aiohttp
        import aiofiles

        # Ensure directory exists
        dest_dir = os.path.dirname(dest_path)
        os.makedirs(dest_dir, exist_ok=True)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        async with aiofiles.open(dest_path, 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)

                        if not os.path.exists(dest_path):
                            raise FileNotFoundError(f"Downloaded file not found: {dest_path}")
                    else:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
        except Exception as e:
            _LOGGER.error(f"Download failed for {url}: {e}")
            raise

    @staticmethod
    def pronto2lirc(pronto):
        codes = [int(binascii.hexlify(pronto[i:i+2]), 16) for i in range(0, len(pronto), 2)]

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
                array += bytearray(struct.pack('>B', pulse))
            else:
                array += bytearray([0x00])
                array += bytearray(struct.pack('>H', pulse))

        packet = bytearray([0x26, 0x00])
        packet += bytearray(struct.pack('<H', len(array)))
        packet += array
        packet += bytearray([0x0d, 0x05])

        # Add 0s to make ultimate packet size a multiple of 16 for 128-bit AES encryption.
        remainder = (len(packet) + 4) % 16
        if remainder:
            packet += bytearray(16 - remainder)
        return packet