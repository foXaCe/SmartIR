"""System health information for SmartIR."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

# A stable file that always exists in the code database, used only to check that
# the GitHub raw host is reachable.
_CODE_DB_CHECK_URL = "https://raw.githubusercontent.com/foXaCe/SmartIR/main/hacs.json"


@callback
def async_register(hass: HomeAssistant, register: system_health.SystemHealthRegistration) -> None:
    """Register the SmartIR system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return SmartIR system health information."""
    return {
        "configured_devices": len(hass.config_entries.async_entries(DOMAIN)),
        "code_database_reachable": system_health.async_check_can_reach_url(hass, _CODE_DB_CHECK_URL),
    }
