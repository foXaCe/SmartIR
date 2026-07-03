"""Tests for SmartIR integration setup."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
import pytest

from custom_components.smartir.const import DOMAIN


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup returns True."""
    from custom_components.smartir import async_setup

    result = await async_setup(hass, {})
    assert result is True


async def test_domain_constant() -> None:
    """Test DOMAIN constant is correct."""
    assert DOMAIN == "smartir"


async def test_helper_pronto2lirc_invalid() -> None:
    """Test pronto2lirc with invalid code."""
    from custom_components.smartir import Helper

    # This should fail because the preamble doesn't start with 0000
    with pytest.raises(ValueError, match="Pronto code should start with 0000"):
        Helper.pronto2lirc(bytes.fromhex("0001006D0001000100100020"))


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
