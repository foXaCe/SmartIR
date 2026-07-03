"""Tests for SmartIR helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.core import HomeAssistant

from custom_components.smartir.const import SmartIRData
from custom_components.smartir.helpers import async_setup_entry_platform


async def test_setup_entry_platform_generates_unique_id(hass: HomeAssistant) -> None:
    """A stable unique_id is generated when the entry has none."""
    data = SmartIRData(
        device_type="climate",
        controller_type="broadlink",
        name="AC",
        device_code=1000,
        controller_data="remote.blaster",
    )
    entry = MagicMock()
    entry.runtime_data = data
    setup_fn = AsyncMock()

    await async_setup_entry_platform(hass, entry, MagicMock(), setup_fn)

    setup_fn.assert_awaited_once()
    _, config, _ = setup_fn.await_args.args
    assert config["unique_id"].startswith("smartir_")
    assert config["device_code"] == 1000
    assert config["controller"] == "broadlink"


async def test_setup_entry_platform_keeps_existing_unique_id(hass: HomeAssistant) -> None:
    """An existing unique_id is preserved."""
    data = SmartIRData(
        device_type="fan",
        controller_type="mqtt",
        name="Fan",
        device_code=2000,
        controller_data="remote.fan",
        unique_id="fixed_id",
    )
    entry = MagicMock()
    entry.runtime_data = data
    setup_fn = AsyncMock()

    await async_setup_entry_platform(hass, entry, MagicMock(), setup_fn)

    _, config, _ = setup_fn.await_args.args
    assert config["unique_id"] == "fixed_id"
