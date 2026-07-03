"""Helper functions for SmartIR."""

import hashlib
import json
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import DOMAIN, SmartIRConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry_platform(
    hass: "HomeAssistant",
    entry: SmartIRConfigEntry,
    async_add_entities: "AddEntitiesCallback",
    platform_setup_fn,
) -> None:
    """Set up SmartIR platform from a config entry."""
    data = entry.runtime_data

    # Generate unique_id if not provided
    unique_id = data.unique_id
    if not unique_id:
        # Create a unique identifier based on device_code, controller_data, and device_type
        unique_string = f"smartir_{data.device_type}_{data.device_code}_{data.controller_data}"
        unique_id = f"smartir_{hashlib.md5(unique_string.encode()).hexdigest()[:16]}"

    # Build config dict for backward compatibility with platform setup functions
    config = {
        "device_type": data.device_type,
        "controller": data.controller_type,
        "name": data.name,
        "device_code": data.device_code,
        "controller_data": data.controller_data,
        "delay": data.delay,
        "temperature_sensor": data.temperature_sensor,
        "humidity_sensor": data.humidity_sensor,
        "power_sensor": data.power_sensor,
        "power_sensor_restore_state": data.power_sensor_restore_state,
        "unique_id": unique_id,
    }

    await platform_setup_fn(hass, config, async_add_entities)


async def download_device_codes(
    hass, device_type: str, device_code: int, update_progress=None
) -> dict[str, Any] | None:
    """Download device codes from GitHub repository.

    Args:
        hass: Home Assistant instance
        device_type: Type of device (climate, fan, media_player, light)
        device_code: Device code to download
        update_progress: Optional callback to update download progress

    Returns:
        Device codes dictionary or None if download failed
    """
    base_url = "https://raw.githubusercontent.com/smartHomeHub/SmartIR/master/codes"
    url = f"{base_url}/{device_type}/{device_code}.json"

    try:
        async with aiohttp.ClientSession() as session:
            if update_progress:
                await update_progress(f"Downloading codes for {device_type} device {device_code}...")

            async with session.get(url) as response:
                if response.status == 200:
                    device_data = await response.json()
                    return device_data
                elif response.status == 404:
                    _LOGGER.error(f"Device code {device_code} not found")
                    if update_progress:
                        await update_progress(f"Device code {device_code} not found")
                    return None
                else:
                    if update_progress:
                        await update_progress(f"Download failed: HTTP {response.status}")
                    return None

    except aiohttp.ClientError as e:
        _LOGGER.error(f"Network error: {e}")
        if update_progress:
            await update_progress(f"Network error: {e!s}")
        return None
    except json.JSONDecodeError as e:
        _LOGGER.error(f"Invalid JSON: {e}")
        if update_progress:
            await update_progress("Invalid device code format")
        return None
    except Exception as e:
        _LOGGER.error(f"Download error: {e}")
        if update_progress:
            await update_progress(f"Unexpected error: {e!s}")
        return None


def create_device_info(name: str, model: str, manufacturer: str, sw_version: str = None) -> dict[str, Any]:
    """Create device info dictionary for Home Assistant entities.

    Args:
        name: Device name
        model: Device model
        manufacturer: Device manufacturer
        sw_version: Optional software version

    Returns:
        Device info dictionary
    """
    device_info = {
        "identifiers": {(DOMAIN, name)},
        "name": name,
        "model": model,
        "manufacturer": manufacturer,
    }

    if sw_version:
        device_info["sw_version"] = sw_version

    return device_info
