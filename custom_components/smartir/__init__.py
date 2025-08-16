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
from .hub import SmartIRHub

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SmartIR component from YAML configuration (deprecated)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SmartIR from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create or get the SmartIR Hub
    if "hub" not in hass.data[DOMAIN]:
        hub = SmartIRHub(hass, "smartir_hub")
        hass.data[DOMAIN]["hub"] = hub
        _LOGGER.info("SmartIR Hub created")
    else:
        hub = hass.data[DOMAIN]["hub"]
    
    # Read with simple keys (not CONF_ constants)
    device_type = entry.data.get("device_type", "climate")
    controller_type = entry.data.get("controller", "broadlink")
    device_code = entry.data.get("device_code")
    device_name = entry.data.get("name", f"SmartIR {device_type.title()}")
    
    # Convert to format expected by platforms (with CONF_ keys)
    platform_config = {
        CONF_DEVICE_TYPE: entry.data.get("device_type"),
        CONF_CONTROLLER_TYPE: entry.data.get("controller"),
        CONF_NAME: device_name,
        CONF_DEVICE_CODE: device_code,
        CONF_CONTROLLER_DATA: entry.data.get("controller_data"),
    }
    
    # Add optional fields
    if "delay" in entry.data:
        platform_config[CONF_DELAY] = entry.data["delay"]
    if "temperature_sensor" in entry.data:
        platform_config[CONF_TEMPERATURE_SENSOR] = entry.data["temperature_sensor"]
    if "humidity_sensor" in entry.data:
        platform_config[CONF_HUMIDITY_SENSOR] = entry.data["humidity_sensor"]
    if "power_sensor" in entry.data:
        platform_config[CONF_POWER_SENSOR] = entry.data["power_sensor"]
    if "power_sensor_restore_state" in entry.data:
        platform_config[CONF_POWER_SENSOR_RESTORE_STATE] = entry.data["power_sensor_restore_state"]
    
    # Add hub reference to config
    platform_config["hub"] = hub
    
    hass.data[DOMAIN][entry.entry_id] = platform_config

    # Register device with the hub
    hub.register_device(device_code, device_type, manufacturer="Unknown")

    _LOGGER.info(
        "SmartIR configured: device_type=%s, controller_type=%s, registered with hub", 
        device_type, 
        controller_type
    )
    
    # Forward the setup to the platform
    platforms = [device_type]
    
    # Add sensor platform for hub status (only for the first device)
    if len([k for k in hass.data[DOMAIN].keys() if k != "hub"]) == 1:
        platforms.append("sensor")
        _LOGGER.debug("Adding sensor platform for SmartIR Hub")
    
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    
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
        _LOGGER.debug("Removing sensor platform for SmartIR Hub")
    
    unload_ok = await hass.config_entries.async_unload_platforms(entry, platforms)
    
    if unload_ok:
        # Unregister device from hub
        if "hub" in hass.data[DOMAIN]:
            hub = hass.data[DOMAIN]["hub"]
            hub.unregister_device(device_code, device_type)
            
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
        
        _LOGGER.info(f"Starting download: {url} -> {dest_path}")
        
        # Ensure directory exists
        dest_dir = os.path.dirname(dest_path)
        _LOGGER.debug(f"Creating directory: {dest_dir}")
        os.makedirs(dest_dir, exist_ok=True)
        
        try:
            _LOGGER.debug(f"Opening HTTP session for: {url}")
            async with aiohttp.ClientSession() as session:
                _LOGGER.debug(f"Making GET request to: {url}")
                async with session.get(url) as response:
                    _LOGGER.info(f"HTTP response status: {response.status} for {url}")
                    if response.status == 200:
                        _LOGGER.debug(f"Opening file for writing: {dest_path}")
                        async with aiofiles.open(dest_path, 'wb') as f:
                            total_bytes = 0
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                                total_bytes += len(chunk)
                        _LOGGER.info(f"Successfully downloaded {url} to {dest_path} ({total_bytes} bytes)")
                        
                        # Verify file was actually written
                        if os.path.exists(dest_path):
                            file_size = os.path.getsize(dest_path)
                            _LOGGER.info(f"File verification: {dest_path} exists with {file_size} bytes")
                        else:
                            _LOGGER.error(f"File verification failed: {dest_path} does not exist after download")
                            raise FileNotFoundError(f"Downloaded file not found: {dest_path}")
                    else:
                        _LOGGER.error(f"HTTP error {response.status} downloading {url}")
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
        except Exception as e:
            _LOGGER.error(f"Download failed for {url}: {type(e).__name__}: {e}")
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