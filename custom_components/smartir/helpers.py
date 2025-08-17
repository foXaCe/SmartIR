"""Helper functions for SmartIR."""
import hashlib
import aiohttp
import asyncio
import json
import logging
import os
from typing import Optional, Dict, Any

from .const import DOMAIN, CONF_CONTROLLER_TYPE, CONTROLLER_TYPES

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry_platform(hass, entry, async_add_entities, platform_setup_fn):
    """Set up SmartIR platform from a config entry."""
    config = hass.data[DOMAIN][entry.entry_id].copy()
    
    # Generate unique_id if not provided
    if not config.get("unique_id"):
        device_code = config.get("device_code", "unknown")
        controller_data = config.get("controller_data", "unknown")
        device_type = config.get("device_type", "unknown")
        
        # Create a unique identifier based on device_code, controller_data, and device_type
        unique_string = f"smartir_{device_type}_{device_code}_{controller_data}"
        unique_id = hashlib.md5(unique_string.encode()).hexdigest()[:16]
        config["unique_id"] = f"smartir_{unique_id}"
    
    await platform_setup_fn(hass, config, async_add_entities)


async def download_device_codes(hass, device_type: str, device_code: int, update_progress=None) -> Optional[Dict[str, Any]]:
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
        session = aiohttp.ClientSession()
        try:
            if update_progress:
                await update_progress(f"Downloading codes for {device_type} device {device_code}...")
            
            async with session.get(url) as response:
                if response.status == 200:
                    device_data = await response.json()
                    _LOGGER.info(f"Successfully downloaded codes for {device_type} device {device_code}")
                    return device_data
                elif response.status == 404:
                    _LOGGER.error(f"Device code {device_code} not found for {device_type}")
                    if update_progress:
                        await update_progress(f"Device code {device_code} not found")
                    return None
                else:
                    _LOGGER.error(f"Failed to download codes: HTTP {response.status}")
                    if update_progress:
                        await update_progress(f"Download failed: HTTP {response.status}")
                    return None
        finally:
            await session.close()
            
    except aiohttp.ClientError as e:
        _LOGGER.error(f"Network error downloading device codes: {e}")
        if update_progress:
            await update_progress(f"Network error: {str(e)}")
        return None
    except json.JSONDecodeError as e:
        _LOGGER.error(f"Invalid JSON in device codes: {e}")
        if update_progress:
            await update_progress(f"Invalid device code format")
        return None
    except Exception as e:
        _LOGGER.error(f"Unexpected error downloading device codes: {e}")
        if update_progress:
            await update_progress(f"Unexpected error: {str(e)}")
        return None


def create_device_info(name: str, model: str, manufacturer: str, sw_version: str = None) -> Dict[str, Any]:
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