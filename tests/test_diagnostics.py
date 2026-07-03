"""Tests for SmartIR diagnostics."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.smartir.const import SmartIRData
from custom_components.smartir.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_redacts_sensitive_data(hass: HomeAssistant) -> None:
    """Sensitive fields are redacted in the diagnostics dump."""
    data = SmartIRData(
        device_type="climate",
        controller_type="broadlink",
        name="AC",
        device_code=1000,
        controller_data="remote.secret",
        unique_id="uid",
    )
    entry = MagicMock()
    entry.runtime_data = data
    entry.entry_id = "e1"
    entry.version = 1
    entry.domain = "smartir"
    entry.title = "AC"
    entry.data = {"controller_data": "remote.secret"}
    entry.options = {}
    entry.source = "user"
    entry.unique_id = "uid"

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["runtime_data"]["controller_data"] == "**REDACTED**"
    assert result["config_entry"]["data"]["controller_data"] == "**REDACTED**"
    assert result["runtime_data"]["unique_id"] == "**REDACTED**"
    assert result["integration_info"]["device_code"] == 1000
    assert result["runtime_data"]["device_type"] == "climate"
