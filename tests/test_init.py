"""Tests for SmartIR integration setup."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.smartir import CONFIG_SCHEMA, async_setup_entry
from custom_components.smartir.const import DOMAIN


async def test_config_schema_present() -> None:
    """The integration exposes a config-entry-only CONFIG_SCHEMA."""
    assert CONFIG_SCHEMA is not None


async def test_setup_entry_not_ready_without_controller(hass: HomeAssistant) -> None:
    """async_setup_entry raises ConfigEntryNotReady when the controller is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "device_type": "climate",
            "controller": "broadlink",
            "controller_data": "remote.does_not_exist",
            "device_code": 1000,
        },
    )
    entry.add_to_hass(hass)

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)


async def test_setup_entry_not_ready_via_config_entries(hass: HomeAssistant) -> None:
    """A setup retry is scheduled when the controller entity is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "device_type": "climate",
            "controller": "broadlink",
            "controller_data": "remote.does_not_exist",
            "device_code": 1000,
        },
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_domain_constant() -> None:
    """Test DOMAIN constant is correct."""
    assert DOMAIN == "smartir"


async def test_helper_pronto2lirc_invalid() -> None:
    """Test pronto2lirc with invalid code."""
    from custom_components.smartir import Helper

    # This should fail because the preamble doesn't start with 0000
    with pytest.raises(ValueError, match="Pronto code should start with 0000"):
        Helper.pronto2lirc(bytearray.fromhex("0001006D0001000100100020"))


async def test_helper_lirc2broadlink() -> None:
    """Test lirc2broadlink conversion."""
    from custom_components.smartir import Helper

    # Test with simple pulses
    pulses = [1000, 500, 1000, 500]
    result = Helper.lirc2broadlink(pulses)

    # Check result is a bytearray
    assert isinstance(result, bytearray)
    # Check header bytes
    assert result[0] == 0x26
    assert result[1] == 0x00
